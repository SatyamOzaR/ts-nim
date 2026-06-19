# Build context = repository root (see docker-compose). Railway: Root Directory empty + RAILWAY_DOCKERFILE_PATH=frontend/Dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .
# Empty default so Railway builds do not bake localhost; local compose passes NEXT_PUBLIC_BACKEND_URL.
ARG NEXT_PUBLIC_BACKEND_URL=
ARG NEXT_PUBLIC_API_KEY=
ENV NEXT_PUBLIC_BACKEND_URL=$NEXT_PUBLIC_BACKEND_URL
ENV NEXT_PUBLIC_API_KEY=$NEXT_PUBLIC_API_KEY
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
# Next standalone binds process.env.HOSTNAME; Docker sets it to the container id, which can
# make the server listen on the wrong interface (502 / connection refused from the edge).
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
COPY frontend/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
ENTRYPOINT ["/docker-entrypoint.sh"]
