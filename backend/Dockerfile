# Build context = repository root (see docker-compose). Railway: Root Directory empty + RAILWAY_DOCKERFILE_PATH=backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Defaults (override at runtime). Do not bake API_KEY — set via env / secrets.
ENV NEO4J_URI=neo4j+s://YOUR_INSTANCE.databases.neo4j.io
ENV NEO4J_USER=neo4j
ENV NEO4J_PASSWORD=
ENV API_KEY=
ENV LLM_PROVIDER=openrouter
ENV LLM_API_KEY=
ENV LLM_BASE_URL=https://openrouter.ai/api/v1
ENV LLM_MODEL=google/gemini-2.5-flash
ENV GEMINI_API_KEY=
ENV FRONTEND_URL=http://localhost:3000
ENV CORS_ORIGINS=

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
