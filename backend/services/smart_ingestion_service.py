"""LLM-powered universal ingestion: accepts any file type, extracts contacts/interactions."""

from __future__ import annotations

import asyncio
import json
import logging
import os

import httpx

from services.file_extraction import extract_text
from services.ingestion_service import upsert_contact, upsert_interaction

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 20  # safety cap on agentic loop iterations

INGEST_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "upsert_contact",
            "description": (
                "Add or merge a person into the network graph. "
                "Call this for every individual contact you find in the files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string", "description": "Contact's first name"},
                    "last_name":  {"type": "string", "description": "Contact's last name"},
                    "company":    {"type": "string", "description": "Company the contact works at"},
                    "role":       {"type": "string", "description": "Job title or role (optional)"},
                    "connected_on": {
                        "type": "string",
                        "description": "Date of first connection, ISO format YYYY-MM-DD (optional)",
                    },
                    "email": {"type": "string", "description": "Email address if available (optional)"},
                },
                "required": ["first_name", "last_name", "company"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upsert_interaction",
            "description": (
                "Record an email thread, meeting, call, or other interaction "
                "between the team member and a contact. "
                "Use this for signals from email exports, calendar files, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name":    {"type": "string", "description": "Full name of the contact"},
                    "contact_company": {"type": "string", "description": "Company the contact works at"},
                    "interaction_type": {
                        "type": "string",
                        "enum": ["email", "meeting", "call", "other"],
                        "description": "Type of interaction",
                    },
                    "occurred_at": {
                        "type": "string",
                        "description": "Date the interaction occurred, ISO format YYYY-MM-DD",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Brief one-line note (topic, context) — do NOT include raw email body",
                    },
                },
                "required": ["contact_name", "interaction_type", "occurred_at"],
            },
        },
    },
]

SYSTEM_PROMPT = """\
You are a network intelligence data extractor.
Your job is to extract every person the team member has (or has had) a relationship with \
from the provided file contents, then call the appropriate tools to record them.

Rules:
- Call upsert_contact for each distinct person found (LinkedIn connections, email participants, \
meeting attendees, contacts listed in documents).
- Call upsert_interaction for each email thread, meeting, or call you find evidence of \
(email exports, calendar .ics files, meeting notes).
- Do NOT store raw email bodies — use a one-line note at most.
- Skip the team member themselves — only record external contacts.
- After all tool calls are done, write a short plain-text summary of what you extracted \
(e.g. "Extracted 12 contacts and 4 interactions from 2 files.").
"""


def _build_user_message(member_name: str, files: list[tuple[str, bytes]]) -> str:
    blocks: list[str] = [f"Team member: {member_name}\n"]
    for filename, raw in files:
        text = extract_text(filename, raw)
        if not text.strip():
            blocks.append(f"--- FILE: {filename} ---\n[empty or unreadable]\n")
        else:
            blocks.append(f"--- FILE: {filename} ---\n{text}\n")
    return "\n".join(blocks)


async def _call_llm(
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> dict:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    body: dict = {"model": model, "messages": messages, "max_tokens": 4096}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    for attempt in range(3):
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=body,
            )
        if resp.status_code in (429, 503) and attempt < 2:
            await asyncio.sleep((attempt + 1) * 5)
            continue
        resp.raise_for_status()
        return resp.json()
    return {}


async def _execute_tool_call(member_name: str, name: str, args: dict) -> str:
    if name == "upsert_contact":
        return await upsert_contact(
            member_name=member_name,
            first_name=args.get("first_name", ""),
            last_name=args.get("last_name", ""),
            company=args.get("company", ""),
            role=args.get("role", ""),
            connected_on=args.get("connected_on", ""),
            email=args.get("email", ""),
        )
    if name == "upsert_interaction":
        return await upsert_interaction(
            member_name=member_name,
            contact_name=args.get("contact_name", ""),
            contact_company=args.get("contact_company", ""),
            interaction_type=args.get("interaction_type", "other"),
            occurred_at=args.get("occurred_at", ""),
            notes=args.get("notes", ""),
        )
    return "unknown_tool"


async def smart_ingest(
    member_name: str,
    files: list[tuple[str, bytes]],
) -> dict:
    """
    Run LLM-powered ingestion over a list of (filename, raw_bytes) pairs.
    Returns {imported, merged, skipped, interactions, summary}.
    """
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.environ.get("LLM_MODEL", "google/gemini-2.5-flash")

    if not api_key:
        return {
            "imported": 0,
            "merged": 0,
            "skipped": 0,
            "interactions": 0,
            "summary": "LLM unavailable (LLM_API_KEY not set). No contacts extracted.",
        }

    user_content = _build_user_message(member_name, files)
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    counts = {"imported": 0, "merged": 0, "skipped": 0, "interactions": 0}
    summary_text = ""

    for _ in range(_MAX_TOOL_ROUNDS):
        data = await _call_llm(api_key, base_url, model, messages, INGEST_TOOLS)
        if not data or "choices" not in data:
            break

        choice = data["choices"][0]
        message = choice["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            # LLM finished — grab the text summary
            summary_text = message.get("content", "")
            break

        # Execute every tool call in this round
        tool_results: list[dict] = []
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"]["arguments"])
            result = await _execute_tool_call(member_name, fn_name, fn_args)

            if fn_name == "upsert_contact":
                if result == "imported":
                    counts["imported"] += 1
                elif result == "merged":
                    counts["merged"] += 1
                else:
                    counts["skipped"] += 1
            elif fn_name == "upsert_interaction":
                if result == "ok":
                    counts["interactions"] += 1

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

        messages.extend(tool_results)

    return {
        **counts,
        "summary": summary_text or (
            f"Extracted {counts['imported']} new contacts, "
            f"merged {counts['merged']}, "
            f"recorded {counts['interactions']} interactions."
        ),
    }
