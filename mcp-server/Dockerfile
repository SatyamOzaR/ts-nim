# Build context = repository root (see docker-compose). Railway: Root Directory empty + RAILWAY_DOCKERFILE_PATH=mcp-server/Dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PORT=8001
ENV BACKEND_URL=http://backend:8000
ENV API_KEY=

COPY mcp-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-server/ .

CMD ["python", "main.py"]
