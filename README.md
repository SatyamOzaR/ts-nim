# Network Intelligence

Relationship graph intelligence tool for capital markets BD teams. Ingest LinkedIn exports, find warm introduction paths, and query your team's network via chat or MCP.

## Quick Start (Local)

```bash
# 1. Copy env file and configure
cp .env.example .env
# Edit .env:
#   - Set LLM_API_KEY with your OpenRouter key (free at https://openrouter.ai/keys)
#   - Or set GEMINI_API_KEY from https://aistudio.google.com/apikey
#   - Chat works without either key (falls back to regex intent matching)

# 2. Start all services
docker compose up --build

# 3. Open the app
# Chat UI: http://localhost:3000
# Graph:   http://localhost:3000/graph
# Neo4j:   http://localhost:7474 (neo4j/password)
# API:     http://localhost:8000/health
```

## Import LinkedIn Connections

1. Go to LinkedIn → Settings → Data Privacy → **Get a copy of your data**
2. Select "Connections" and request the archive
3. Download the CSV when ready
4. In the app, click **Import CSV**, enter your name, and upload the file

A sample CSV is included at `data/sample_connections.csv` for testing.

## Connect MCP Server to Claude Desktop

**Prerequisites:** Node.js must be installed (for `npx`).

Add the `tsi-network` entry to your Claude Desktop config:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "tsi-network": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://localhost:8001/sse?api_key=tsi_demo_key_123"
      ]
    }
  }
}
```

For a Railway-deployed MCP server, replace the URL:

```json
"http://YOUR_MCP_SERVER.railway.app/sse?api_key=YOUR_API_KEY"
```

Restart Claude Desktop after saving. You should see the Network Intelligence tools (search_network, warm_path, score_relationship, import_connections) in the tools menu.

Then ask Claude things like:

- "Search our network for contacts at Goldman Sachs"
- "Find a warm path from Paras Mehta to the CIO at Barclays"
- "What's the relationship strength for james_mitchell_barclays?"

## Sample Queries (Chat UI)

- "Who do we know at Goldman Sachs?"
- "Find a warm path to the CIO at Barclays"
- "Show me our strongest connections at hedge funds"
- "Who are the partners in our network?"

## Deploy to Railway

Dockerfiles expect the **full repository** as the build context (same as `docker compose build`: `context: .` and `dockerfile: backend/Dockerfile`, etc.). Paths inside each Dockerfile are `backend/...`, `mcp-server/...`, `frontend/...`.

On Railway, **do not** set Root Directory to a subfolder — that shrinks the context and breaks `COPY` (e.g. `requirements.txt` not found). Instead:

1. **Settings → Source → Root Directory:** leave **empty** (repo root).
2. **Variables:** set [`RAILWAY_DOCKERFILE_PATH`](https://docs.railway.com/builds/dockerfiles#custom-dockerfile-path) so Railway knows which Dockerfile to use:

| Service    | `RAILWAY_DOCKERFILE_PATH`   |
| ---------- | --------------------------- |
| backend    | `backend/Dockerfile`        |
| mcp-server | `mcp-server/Dockerfile`     |
| frontend   | `frontend/Dockerfile`       |

Use **Neo4j Aura** (free tier) for the graph.

### Step 1: Create a Railway project

Go to [railway.app](https://railway.app) → **New Project** → **Empty Project**.

### Step 2: Neo4j (Aura)

Create a database at [console.neo4j.io](https://console.neo4j.io), copy the `neo4j+s://…` URI and credentials. You will set `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` on the backend service.

### Step 3: Add Backend

1. Click **+ New** → **GitHub Repo** → select this repo
2. **Root Directory:** empty **·** `RAILWAY_DOCKERFILE_PATH` = `backend/Dockerfile`
3. Add variables:
   - `NEO4J_URI` = `neo4j+s://YOUR_INSTANCE.databases.neo4j.io`
   - `NEO4J_USER` = (from Aura)
   - `NEO4J_PASSWORD` = (from Aura)
   - `API_KEY` = `your_api_key`
   - `LLM_PROVIDER` = `openrouter`
   - `LLM_API_KEY` = `sk-or-v1-your_key`
   - `LLM_BASE_URL` = `https://openrouter.ai/api/v1`
   - `LLM_MODEL` = `google/gemini-2.5-flash`
   - `FRONTEND_URL` = (set after frontend deploys)
   - `PORT` = `8000`
4. Go to **Settings** → **Networking** → **Generate Domain**

### Step 4: Add MCP Server

1. Click **+ New** → **GitHub Repo** → select this repo
2. **Root Directory:** empty **·** `RAILWAY_DOCKERFILE_PATH` = `mcp-server/Dockerfile`
3. Add variables:
   - `BACKEND_URL` = `http://backend.railway.internal:8000`
   - `API_KEY` = `your_api_key`
   - `PORT` = `8001`
4. Go to **Settings** → **Networking** → **Generate Domain**

### Step 5: Add Frontend

1. Click **+ New** → **GitHub Repo** → select this repo
2. **Root Directory:** empty **·** `RAILWAY_DOCKERFILE_PATH` = `frontend/Dockerfile`
3. Add build-time variables:
   - `NEXT_PUBLIC_BACKEND_URL` = `https://YOUR_BACKEND.railway.app`
   - `NEXT_PUBLIC_API_KEY` = `your_api_key`
   - `PORT` = `3000`
4. Go to **Settings** → **Networking** → **Generate Domain**

### Step 6: Update Backend CORS

Go back to the backend service and set:
- `FRONTEND_URL` = `https://YOUR_FRONTEND.railway.app`

Redeploy the backend.

### If you see **502** on public URLs

- **Use the URL without a port:** Open `https://YOUR-SERVICE.up.railway.app` only — not `:3000` / `:8000` on the public hostname (the edge proxy is on 443).
- **Wrong port:** Railway sets `PORT` on the container; backend and Next read it. Redeploy after pulling the latest images.
- **Frontend 502:** Containers set `HOSTNAME` to the container id; Next.js standalone used to bind there. The frontend image uses `docker-entrypoint.sh` to force `HOSTNAME=0.0.0.0` before `node server.js`. Pull latest and redeploy if you still see 502.
- **Backend crash on boot:** Usually Neo4j — set `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` on the backend. Check **Deployments → View logs** for tracebacks.
- **Frontend can’t reach API:** Set `NEXT_PUBLIC_BACKEND_URL` to your backend’s **public** `https://…` URL and rebuild the frontend (those vars are compile-time for Next).

## Architecture

| Service    | Port      | Description                           |
| ---------- | --------- | ------------------------------------- |
| Frontend   | 3000      | Next.js chat UI + graph visualization |
| Backend    | 8000      | FastAPI with Neo4j graph queries      |
| MCP Server | 8001      | SSE transport for Claude Desktop      |
| Neo4j      | 7474/7687 | Graph database (Community Edition)    |

## Environment Variables

| Variable         | Description                               | Default                        |
| ---------------- | ----------------------------------------- | ------------------------------ |
| `LLM_PROVIDER`   | `openrouter` (default) or `gemini`        | `openrouter`                   |
| `LLM_API_KEY`    | OpenRouter API key (free tier works)      | -                              |
| `LLM_BASE_URL`   | OpenAI-compatible API endpoint            | `https://openrouter.ai/api/v1` |
| `LLM_MODEL`      | LLM model name                            | `google/gemini-2.5-flash`      |
| `GEMINI_API_KEY` | Google AI Studio key (if provider=gemini) | -                              |
| `API_KEY`        | API key for backend/MCP auth              | `tsi_demo_key_123`             |
| `NEO4J_URI`      | Neo4j connection URI                      | `bolt://neo4j:7687`            |
| `NEO4J_USER`     | Neo4j username                            | `neo4j`                        |
| `NEO4J_PASSWORD` | Neo4j password                            | `password`                     |
| `FRONTEND_URL`   | Frontend URL for CORS                     | `http://localhost:3000`        |
| `CORS_ORIGINS`   | Extra CORS origins (comma-separated)      | -                              |

## Relationship Scoring

Each connection gets a strength score (0.0 - 1.0) based on:

| Signal             | Weight | Logic                                                             |
| ------------------ | ------ | ----------------------------------------------------------------- |
| Recency            | 30%    | When you connected (<1yr: 1.0, 1-3yr: 0.6, 3+yr: 0.3)             |
| Seniority          | 25%    | Contact's title (C-suite: 1.0, VP: 0.7, Manager: 0.4, Other: 0.2) |
| Shared Connections | 25%    | Team members who know them (3+: 1.0, 2: 0.6, 1: 0.2)              |
| Source Diversity   | 20%    | Appears in multiple team exports (Yes: 1.0, No: 0.0)              |
