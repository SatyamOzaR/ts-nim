import json
import logging
import os
import re
import asyncio

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from routers.auth import verify_api_key
from services.graph_service import (
    find_path_options,
    get_score_details,
    mutual_connections,
    network_summary,
    recent_additions,
    search_graph,
    stale_relationships,
    team_coverage_stats,
    top_contacts,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# OpenAI-format tool definitions (used by OpenRouter and any OpenAI-compatible API)
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "find_warm_path",
            "description": "Find warm introduction paths from a TSI team member to a target person. The UI shows multiple strategies (fewest hops, strongest ties, teammate handoffs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_member": {"type": "string", "description": "Full name of the TSI team member who is the starting point"},
                    "target_name": {"type": "string", "description": "Name or role of the target person to reach"},
                    "target_company": {"type": "string", "description": "Company the target works at"},
                },
                "required": ["source_member", "target_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_by_company_or_role",
            "description": "Search the network for contacts by company name and/or role/title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company name to filter by"},
                    "role": {"type": "string", "description": "Role or title to filter by"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_relationship_strength",
            "description": "Get detailed relationship strength score breakdown for a specific contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "person_id": {"type": "string", "description": "The unique person ID (slug) of the contact"},
                },
                "required": ["person_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_contacts",
            "description": "List the strongest relationships in the network, ranked by strength score. Use for questions like 'who are our best contacts?', 'show strongest relationships', 'who has most interactions?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_member": {"type": "string", "description": "Filter to one TSI team member's relationships (optional)"},
                    "limit": {"type": "integer", "description": "Number of contacts to return (default 10)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stale_relationships",
            "description": "Find relationships that have gone cold — no recorded interaction in the last N months. Use for 'which contacts haven't we touched?', 'who have we neglected?', 'relationship health check'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "months": {"type": "integer", "description": "Number of months of inactivity to flag as stale (default 12)"},
                    "source_member": {"type": "string", "description": "Filter to one team member (optional)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "team_coverage_stats",
            "description": "Show per-team-member network stats: how many contacts each person has, average relationship strength, total interactions. Use for 'who has the biggest network?', 'team coverage breakdown', 'who should own this intro?'",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "network_summary",
            "description": "Overall network health dashboard: total contacts, companies covered, strong vs cold relationships, top companies by depth. Use for 'network overview', 'how is our network?', 'coverage summary'.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mutual_connections",
            "description": "Find people who are connected to BOTH of two targets — useful for finding bridges between two companies or people. Use for 'who knows both X and Y?', 'mutual connections between X and Y'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_a": {"type": "string", "description": "First person name or company"},
                    "target_b": {"type": "string", "description": "Second person name or company"},
                },
                "required": ["target_a", "target_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recent_additions",
            "description": "List contacts connected or interacted with in the last N days. Use for 'recent activity', 'new connections', 'who have we met recently?'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Lookback window in days (default 30)"},
                    "source_member": {"type": "string", "description": "Filter to one team member (optional)"},
                },
            },
        },
    },
]

# Gemini-native function declarations
GEMINI_TOOLS = [
    {
        "function_declarations": [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "parameters": t["function"]["parameters"],
            }
            for t in OPENAI_TOOLS
        ]
    }
]

SYSTEM_PROMPT = """You are a relationship intelligence assistant for a capital markets BD team.
You help find warm introduction paths, search the network, and analyze relationship strength.

IMPORTANT: Only call tools when the user explicitly wants to SEE data. Do NOT call tools for general chat or clarifications.

Tool routing guide:
- "Who do we know at X?" / "Contacts at X" → search_by_company_or_role(company=X)
- "Find all [role]s we know" → search_by_company_or_role(role=...)
- "Find a path / warm intro to X" → find_warm_path
- "How strong is our relationship with X?" → score_relationship_strength
- "Who are our strongest / top contacts?" / "who has most interactions?" → top_contacts
- "Which relationships have gone cold?" / "who haven't we touched?" → stale_relationships
- "How many connections does each team member have?" / "who covers what?" → team_coverage_stats
- "Network overview / health / summary" → network_summary
- "Who knows both X and Y?" / "mutual connections" → mutual_connections
- "Recent connections / activity / new contacts" → recent_additions

Path results include multiple algorithm options (fewest hops, strongest ties, teammate handoffs). Mention briefly that the user can compare strategies in the tabs.

Be concise and professional. Tool results are displayed as visual cards to the user."""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    source_member: str = ""


async def _execute_tool(name: str, args: dict) -> dict:
    if name == "find_warm_path":
        options = await find_path_options(
            args.get("source_member", ""),
            args.get("target_name", ""),
            args.get("target_company"),
        )
        return {"type": "path", "data": {"options": options}}
    elif name == "search_by_company_or_role":
        results = await search_graph(args.get("company"), args.get("role"))
        return {"type": "search", "data": results}
    elif name == "score_relationship_strength":
        details = await get_score_details(args.get("person_id", ""))
        return {"type": "score", "data": details}
    elif name == "top_contacts":
        results = await top_contacts(args.get("source_member"), args.get("limit", 10))
        return {"type": "search", "data": results}
    elif name == "stale_relationships":
        results = await stale_relationships(args.get("months", 12), args.get("source_member"))
        return {"type": "search", "data": results}
    elif name == "team_coverage_stats":
        results = await team_coverage_stats()
        return {"type": "search", "data": results}
    elif name == "network_summary":
        data = await network_summary()
        return {"type": "summary", "data": data}
    elif name == "mutual_connections":
        results = await mutual_connections(args.get("target_a", ""), args.get("target_b", ""))
        return {"type": "search", "data": results}
    elif name == "recent_additions":
        results = await recent_additions(args.get("days", 30), args.get("source_member"))
        return {"type": "search", "data": results}
    return {"type": "error", "data": "Unknown tool"}


def _fallback_intent(message: str) -> tuple[str, dict] | None:
    msg = message.lower()

    path_match = re.search(
        r"(?:path|intro|introduction|connect|reach).*?(?:to|at)\s+(?:the\s+)?(.+?)(?:\s+at\s+)(.+)",
        msg,
    )
    if path_match:
        return "find_warm_path", {
            "target_name": path_match.group(1).strip(),
            "target_company": path_match.group(2).strip().rstrip("?. "),
        }

    company_match = re.search(
        r"(?:who|know|connections?|contacts?|people).*?(?:at|from)\s+(.+)",
        msg,
    )
    if company_match:
        return "search_by_company_or_role", {
            "company": company_match.group(1).strip().rstrip("?. "),
        }

    role_match = re.search(
        r"(?:find|search|show).*?(cio|cto|ceo|cfo|partner|director|vp|md|managing director)",
        msg,
    )
    if role_match:
        return "search_by_company_or_role", {"role": role_match.group(1).strip()}

    return None


# ---------------------------------------------------------------------------
# OpenAI-compatible LLM call (works with OpenRouter, OpenAI, etc.)
# ---------------------------------------------------------------------------

async def _call_openai_compatible(
    api_key: str, base_url: str, model: str,
    messages: list[dict], tools: list[dict] | None = None,
) -> dict:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body: dict = {"model": model, "messages": messages, "max_tokens": 2048}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    for attempt in range(3):
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(endpoint, headers=headers, json=body)
        if resp.status_code in (429, 503) and attempt < 2:
            wait = (attempt + 1) * 5
            logger.warning("LLM rate limited (%d), retrying in %ds...", resp.status_code, wait)
            await asyncio.sleep(wait)
            continue
        if resp.status_code != 200:
            logger.error("LLM API error %d: %s", resp.status_code, resp.text[:500])
            resp.raise_for_status()
        return resp.json()
    return {}


async def _chat_openai(
    api_key: str, base_url: str, model: str,
    request: ChatRequest,
) -> dict:
    system = SYSTEM_PROMPT
    if request.source_member:
        system += f"\n\nThe current user/team member is: {request.source_member}. Use this as the source_member when calling find_warm_path."

    messages = [{"role": "system", "content": system}]
    for msg in request.history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": request.message})

    data = await _call_openai_compatible(api_key, base_url, model, messages, OPENAI_TOOLS)
    choice = data["choices"][0]
    message = choice["message"]

    if message.get("tool_calls"):
        tool_call = message["tool_calls"][0]
        tool_name = tool_call["function"]["name"]
        tool_args = json.loads(tool_call["function"]["arguments"])

        if tool_name == "find_warm_path" and request.source_member and "source_member" not in tool_args:
            tool_args["source_member"] = request.source_member

        tool_result = await _execute_tool(tool_name, tool_args)

        messages.append(message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": json.dumps(tool_result),
        })

        follow_up = await _call_openai_compatible(api_key, base_url, model, messages)
        return {
            "text": follow_up["choices"][0]["message"]["content"],
            "tool_name": tool_name,
            "tool_result": tool_result,
        }

    return {"text": message.get("content", ""), "tool_name": None, "tool_result": None}


# ---------------------------------------------------------------------------
# Gemini native LLM call (for Google API keys that don't work with OpenAI compat)
# ---------------------------------------------------------------------------

async def _call_gemini_native(
    api_key: str, model: str, contents: list[dict],
    system_prompt: str, tools: list[dict] | None = None,
) -> dict:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body: dict = {
        "contents": contents,
        "system_instruction": {"parts": [{"text": system_prompt}]},
    }
    if tools:
        body["tools"] = tools

    for attempt in range(3):
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                endpoint,
                headers={"Content-Type": "application/json", "X-goog-api-key": api_key},
                json=body,
            )
        if resp.status_code in (429, 503) and attempt < 2:
            await asyncio.sleep((attempt + 1) * 5)
            continue
        if resp.status_code != 200:
            logger.error("Gemini error %d: %s", resp.status_code, resp.text[:500])
            resp.raise_for_status()
        return resp.json()
    return {}


async def _chat_gemini(api_key: str, model: str, request: ChatRequest) -> dict:
    system = SYSTEM_PROMPT
    if request.source_member:
        system += f"\n\nThe current user/team member is: {request.source_member}. Use this as the source_member when calling find_warm_path."

    contents = []
    for msg in request.history:
        role = "model" if msg.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg.content}]})
    contents.append({"role": "user", "parts": [{"text": request.message}]})

    data = await _call_gemini_native(api_key, model, contents, system, GEMINI_TOOLS)
    parts = data["candidates"][0]["content"].get("parts", [])
    fn_call = next((p.get("functionCall") for p in parts if "functionCall" in p), None)

    if fn_call:
        tool_name = fn_call["name"]
        tool_args = fn_call.get("args", {})
        if tool_name == "find_warm_path" and request.source_member and "source_member" not in tool_args:
            tool_args["source_member"] = request.source_member

        tool_result = await _execute_tool(tool_name, tool_args)

        fc_part = next(p for p in parts if "functionCall" in p)
        fn_response: dict = {"name": tool_name, "response": tool_result}
        if "id" in fn_call:
            fn_response["id"] = fn_call["id"]

        contents.append({"role": "model", "parts": [fc_part]})
        contents.append({"role": "model", "parts": [{"functionResponse": fn_response}]})

        follow_up = await _call_gemini_native(api_key, model, contents, system)
        follow_parts = follow_up["candidates"][0]["content"].get("parts", [])
        text = next((p["text"] for p in follow_parts if "text" in p), "")
        return {"text": text, "tool_name": tool_name, "tool_result": tool_result}

    text = next((p["text"] for p in parts if "text" in p), "")
    return {"text": text, "tool_name": None, "tool_result": None}


# ---------------------------------------------------------------------------
# Main chat endpoint
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat(
    request: ChatRequest,
    _key: str = Depends(verify_api_key),
):
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    llm_api_key = os.environ.get("LLM_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.environ.get("LLM_MODEL", "google/gemini-2.5-flash")

    has_key = bool(llm_api_key) or (bool(gemini_key) and gemini_key != "your_gemini_api_key_here")

    if not has_key:
        intent = _fallback_intent(request.message)
        if intent:
            tool_name, tool_args = intent
            if tool_name == "find_warm_path" and request.source_member:
                tool_args["source_member"] = request.source_member
            tool_result = await _execute_tool(tool_name, tool_args)
            return {"text": "Here are the results for your query:", "tool_name": tool_name, "tool_result": tool_result}
        return {
            "text": "I can help you find warm paths, search contacts, or check relationship strength. Try 'Who do we know at Goldman Sachs?' or 'Find a path to the CIO at Barclays'.",
            "tool_name": None, "tool_result": None,
        }

    try:
        if provider == "gemini" or (not llm_api_key and gemini_key):
            return await _chat_gemini(gemini_key, model, request)
        else:
            return await _chat_openai(llm_api_key, base_url, model, request)

    except Exception as exc:
        logger.exception("LLM call failed, falling back to intent parser")
        intent = _fallback_intent(request.message)
        if intent:
            tool_name, tool_args = intent
            if tool_name == "find_warm_path" and request.source_member:
                tool_args["source_member"] = request.source_member
            tool_result = await _execute_tool(tool_name, tool_args)
            return {"text": "(LLM unavailable, using fallback) Here are the results:", "tool_name": tool_name, "tool_result": tool_result}
        return {"text": f"Sorry, I encountered an error: {exc}", "tool_name": None, "tool_result": None}
