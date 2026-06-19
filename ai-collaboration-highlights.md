# AI Collaboration Highlights — Network Intelligence (TSI)

**Project repo**: https://github.com/SatyamOzaR/ts-nim
**Tools used**: Cursor IDE + Claude (Sonnet 4.x)
**Build window**: April 16–17, 2026 (~620 turns over 2 days)
**Outcome**: Production-deployable full-stack relationship-graph product — Neo4j (Aura) + FastAPI backend + custom MCP server with 10 tools + Next.js chat UI with React Flow graph visualization. Local via Docker Compose, deployed on Railway.

**Companion files**:
- `cursor-transcript.md` — cleaned, readable Markdown export of the agent transcript (~246 KB, 79 user turns + assistant replies + tool-call summaries; large code diffs and `[REDACTED]` reasoning blocks are summarized for readability)
- `cursor-transcript.jsonl` — raw, unedited Cursor agent export (~796 KB; secrets redacted)

This document is a curated reel of **7 representative moments** from the build that show specific collaboration patterns — planning, catching a hallucination, debugging from real evidence, course-correcting on architecture, etc. Each highlight cites line numbers in `cursor-transcript.md` so you can read the surrounding context directly.

---

## How I think about working with AI on a build like this

Three rules I actually used (visible in the transcript):

1. **Don't write code from a spec until the model has questioned it.** The original spec had bugs (CORS missing, Neo4j healthcheck race, `KNOWS` edge directed when LinkedIn connections are mutual, MCP server had no way to find the backend). I had Claude review the plan against the spec before any phase started. That review caught 7 issues, fixed in the plan rather than in debugging hours later.

2. **Don't trust AI knowledge of library APIs. Verify against the installed package.** The first run crashed because the model assumed the standalone `fastmcp` package's API instead of `mcp==1.9.2`. The fix came from running `inspect.signature` inside the running container, not from another web search.

3. **Iterate with real evidence, not narrative.** When the deployed app returned 502 three times in a row, I didn't accept the first plausible-looking fix. We ran `docker run --entrypoint env`, read the standalone `server.js` source, and tracked down the actual cause: Docker was setting `HOSTNAME` to the container ID and Next.js was binding to that.

---

## Highlight 1 — Plan-first, code-second

**Turns 1–4** (`cursor-transcript.md`, lines 15–471)

After the user pasted a 300-line spec, the first move was *not* to start scaffolding. It was clarifying questions:

> Should the chat be purely a tool-calling UI (user picks a tool, fills params, sees structured results), or do you want an actual LLM in the loop?
>
> For Neo4j: AuraDB only, or add a local container for dev?
>
> The repo is named 'tsi-network'. Build inside `ts-nim/` or alongside it?

Then a **cost audit** when I said "make sure everything we use should be free." This caught that HuggingFace TGI without a GPU would be unusable for a demo, and we pivoted to Google Gemini's free tier (and later OpenRouter) using OpenAI-compatible endpoints so the provider stays swappable.

Then a **plan review pass** that found 7 concrete issues before any code was written:

> 1. CORS missing — the FastAPI backend will receive browser requests from the frontend on `:3000`. Without CORS middleware, every request will fail.
> 2. MCP server has no `BACKEND_URL` env var — it would have no way to find the backend.
> 3. KNOWS edge direction bug — LinkedIn connections are mutual, but the spec uses directed traversal (`-[:KNOWS*..5]->`).
> 4. Neo4j startup race condition — `depends_on: [neo4j]` only waits for the container to start, not for Neo4j to accept connections.
> 5. Confusing project root — the plan says both "create at ts-nim/" and shows "tsi-network/"…
> 6. Frontend env var inconsistency — `NEXT_PUBLIC_BACKEND_URL` is hardcoded in docker-compose but not in `.env.example`…
> 7. MCP server `env_file` missing — the docker-compose snippet doesn't pass `API_KEY` to the mcp-server service.

**What this shows**: AI is most valuable when used to argue *with* a spec, not just implement it. Every issue caught here would have cost 30+ minutes of "why doesn't this work?" later.

---

## Highlight 2 — Catching a hallucinated API on the first `docker compose up`

**Turn 7** (`cursor-transcript.md`, lines 736–852)

First end-to-end run. Three of four containers came up clean. The MCP server crashed:

```
mcp-server-1  | Traceback (most recent call last):
mcp-server-1  |   File "/app/main.py", line 103, in <module>
mcp-server-1  |     mcp.run(transport="sse", host="0.0.0.0", port=8001)
mcp-server-1  | TypeError: FastMCP.run() got an unexpected keyword argument 'host'
mcp-server-1 exited with code 1
```

The model had assumed `mcp.run(transport="sse", host="0.0.0.0", port=8001)` based on patterns from the standalone `fastmcp` package. The installed `mcp==1.9.2` doesn't accept those kwargs on `run()` — they go on the constructor as `**settings`.

Fix loop, in order:

1. Don't accept the first plausible code change.
2. Run `inspect.signature` inside the container to see the real signature.
3. Inspect `FastMCP.__init__`: settings live there.
4. Move `host`/`port` to `FastMCP("Network Intelligence", host="0.0.0.0", port=8001)`.

Final assistant summary:

> The fix was moving `host` and `port` from `mcp.run()` to the `FastMCP()` constructor, which is where the `mcp==1.9.2` SDK expects them (via `**settings` kwargs).

**What this shows**: AI-generated code against fast-moving libraries (the MCP SDK was barely 6 months old at this point) ages badly. The cheapest defense is to verify the API against the *installed* package, not the model's memory.

---

## Highlight 3 — Real debugging beats guessing

**Turn 24** (`cursor-transcript.md`, lines 2201–2344)

After wiring up Claude Desktop with the MCP server config, the `initialize` handshake succeeded but every `tools/list` request timed out with `BrokenResourceError`. The SSE stream was being closed.

Instead of guessing fixes, the workflow was:

1. Read the MCP server container logs end-to-end.
2. Re-read every tool implementation (in case one was throwing on import and killing the process).
3. Check what version of `mcp` was installed (`1.9.2`).
4. Web-search for known SSE issues in that version.
5. Look up the latest version (`1.27.0` — major gap).

> Major version gap — `1.9.2` vs latest `1.27.0`. Let me upgrade the MCP server SDK and check for any API changes.

After upgrading: SSE connection stayed stable, `tools/list` returned, Claude Desktop saw all tools.

**What this shows**: when AI is debugging a runtime issue, the right move is to make it read evidence (container logs, package source, actual versions installed), not generate plausible hypotheses to try one by one.

---

## Highlight 4 — User-driven architectural pivot mid-build

**Turn 67** (`cursor-transcript.md`, lines 5605–5808)

After we shipped LinkedIn-CSV ingestion, the conversation turned to email + calendar signals. Claude proposed a clean adapter architecture (one canonical graph, pluggable ingestion adapters per source). I pushed back with a more interesting idea:

> what if we make our ingestion pieline powered by llm, so user uploads upto 5 files of any extension then llm decides fields from them, then call ingestion tools?

This was a real pivot — from "write a parser per source format" to "let an LLM introspect any file (CSV, EML, ICS, JSON, vCard, free-form CRM exports) and route the extracted records to the existing ingestion tools via function calling."

The model walked through what it would take, then implemented:

- Multi-file upload UI replaced the CSV-only uploader.
- Backend `/api/ingest/llm` endpoint that extracts text per file type.
- An LLM with structured tool-calling over the existing ingestion service.
- The same MCP tools became reusable as the LLM's action surface.

**What this shows**: best collaboration pattern is the human raises the abstraction level, the AI fills in the implementation. The pivot would have been extremely tedious to scope and execute by hand; with Claude executing the rewrites in parallel, it was done in about 30 minutes.

---

## Highlight 5 — Expanding the tool surface from real usage

**Turns 71–72** (`cursor-transcript.md`, lines 6126–6843)

Original spec had 4 MCP tools: `import_connections`, `warm_path`, `score_relationship`, `search_network`.

After actually testing the system in Claude Desktop, we sat down and wrote out the questions a CEO/CXO/CTO would ask about a relationship network:

> 1. "Who are our strongest relationships?" → need `top_contacts` (sorted by strength)
> 2. "Who has gone cold / hasn't been touched in 6+ months?" → need `stale_relationships`
> 3. "How many contacts at each company? Show with strength" → existing `search_network` doesn't sort
> 4. "Which team member has the best coverage?" → need `team_coverage_stats`
> 5. "Who do we know who knows both X and Y?" → need `mutual_connections`
> 6. "What contacts were added recently?" → need `recent_additions`
> 7. "Network health summary?" → need `network_summary`

Every gap became a new MCP tool. By the end, the server exposed 10 tools, all reachable from Claude Desktop:

| Question style | Tool |
|---|---|
| "Who are our strongest contacts?" | `top_relationships` |
| "Which relationships have gone cold?" | `cold_relationships` |
| "Who on the team has the biggest network?" | `team_coverage` |
| "Network health overview" | `network_health` |
| "Who knows both Goldman Sachs and TPG Capital?" | `bridges_between` |
| "Who have we added / met recently?" | `recent_activity` |
| "Find a warm intro to X at Y company" | `warm_path` |
| "Who do we know at [company]?" | `search_network` |
| "How strong is our relationship with [person]?" | `score_relationship` |
| "Import LinkedIn export" | `import_connections` |

**What this shows**: tool surface design is downstream of real user questions, not upstream of them. The 4-tool spec was a reasonable starting point; the 10-tool surface came from actually using the system.

---

## Highlight 6 — The 502 saga: not accepting "looks fixed"

**Turns 45–50** (`cursor-transcript.md`, lines 3968–4475)

The Railway deploy returned 502 on every public URL. Three rounds of debugging:

**Round 1** — "Probably PORT binding." Set `ENV PORT` and `CMD ["uvicorn", "...", "--host", "0.0.0.0", "--port", "$PORT"]`. Realized `$$` in Dockerfile shell-form CMD is the shell PID, not an escaped `$`. Switched to a `docker-entrypoint.sh`. Pushed.

**Round 2** — User: `still 502`. Inspected the Next.js standalone `server.js`:

> Next.js standalone does `hostname = process.env.HOSTNAME || '0.0.0.0'`, so it was binding to that name instead of all interfaces.

Added `frontend/docker-entrypoint.sh` that exports `HOSTNAME=0.0.0.0` before exec'ing `node server.js`. Pushed.

**Round 3** — User: `still 502`. Now the actual root cause:

> Docker sets `HOSTNAME` to the short container id (e.g. `35d820b4605b`). The server then binds using that value, which can mean it's not listening where Railway's proxy connects → connection refused and 502.
>
> Your `docker-entrypoint.sh` fixes that *only if* that entrypoint actually runs. If Railway uses a custom start command like `node server.js`, the entrypoint is skipped and the bad `HOSTNAME` stays.

Final fix: added `ENV HOSTNAME=0.0.0.0` directly in the runner stage of the Dockerfile, so the bind address is correct *even when the entrypoint isn't used*. Verified locally with `docker run --entrypoint env`:

```
HOSTNAME=0.0.0.0
```

**What this shows**: every "fix" should be re-verified, not assumed. Three rounds is fine — what's not fine is calling the second one "done" without reproducing the original failure first.

---

## Highlight 7 — Self-correction when the AI's first read is wrong

**Around line 6351** (during a TypeScript build error)

While debugging a TypeScript build error, Claude initially fixated on the line number the compiler reported:

> The error message is pointing to line 181, but that's likely just where TypeScript detected the issue — the actual problem could be in a nearby expression. Since `data` is `Record<string, unknown>`, something like `{data.last_touch as string}` might be causing the type mismatch when rendered in JSX.

Then immediately corrected itself:

> Actually wait, the error is pointing to the comment `{/* Per-dimension bars */}`. That's actually not the comment itself but that the TypeScript compiler says line 181 col 7 is the problem. Let me look at what's around that comment.
>
> ...the real issue might be that `unknown` type doesn't have a defined truthy check in JSX conditionals, so the `{(data.interaction_count as number) > 0 || data.last_touch}` pattern is problematic. I think the cleanest solution is to define a proper typed interface for the `ScoreCard` component instead of relying on `Record<string, unknown>`.

That's the kind of mid-thought correction I want from a coding partner. Misleading line numbers in TypeScript errors are common; not anchoring on them and re-reading the surrounding expression is the right reflex.

---

## Things I'd do differently next time

- **Pin SDK versions in `requirements.txt` from day one.** A floating `mcp[cli]` would have given us 1.27.0 from the start and skipped Highlight 3 entirely. (Conversely, with `mcp==1.9.2` pinned, the upgrade decision is conscious instead of accidental.)
- **Move credentials handling into the very first phase, not phase 8.** The transcript originally had Aura credentials and an OpenRouter key inline (both since rotated and redacted in the shipped artifacts). A `secrets.md` checklist as turn 1 of any future build would prevent that.
- **Compress the plan-iteration phase further.** Spending the first 4 turns iterating on a plan was high-leverage; spending more on it would have been higher-leverage. A 30-minute "plan critique" session before any code is written is consistently the best ROI move.
- **Keep more meta-notes in-flight.** Half the value of going back through this transcript was finding patterns I didn't realize I was using (like the "verify against installed package" rule). A short "what just worked / what just failed" note at the end of each session would make those patterns visible at the time.

---

## Where to read more

- **Full readable transcript**: `cursor-transcript.md` — 246 KB, 79 user turns, all assistant replies and tool-call summaries kept; large code diffs and `[REDACTED]` thinking blocks are condensed for readability.
- **Raw unedited export**: `cursor-transcript.jsonl` — 796 KB, the original Cursor agent log. Secrets redacted; otherwise byte-for-byte identical to what Cursor produced.
- **Final shipped code**: https://github.com/SatyamOzaR/ts-nim
  - MCP server with 10 tools: [`/mcp-server`](https://github.com/SatyamOzaR/ts-nim/tree/main/mcp-server)
  - FastAPI backend + Neo4j services: [`/backend`](https://github.com/SatyamOzaR/ts-nim/tree/main/backend)
  - Next.js chat + React Flow graph UI: [`/frontend`](https://github.com/SatyamOzaR/ts-nim/tree/main/frontend)
