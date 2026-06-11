# Build context MUST be the repository root (parent of backend/), not backend/ alone.
#
# Render example:
#   Root Directory:  (leave empty or ".")
#   Dockerfile Path: backend/Dockerfile
#
# Local:
#   docker build -f backend/Dockerfile -t smarterp .

# ── Frontend (Vite) ───────────────────────────────────────────────────────────
FROM node:20-alpine AS web
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json ./
COPY postcss.config.js tailwind.config.js ./
COPY src ./src
COPY public ./public
# Same-origin deploy: API is /auth, /analytics (no /api prefix). Override if API is on another host.
ARG VITE_API_URL=
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ── API (FastAPI) ───────────────────────────────────────────────────────────
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends freetds-dev freetds-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --default-timeout=120 --retries 5 -r requirements.txt
COPY backend/ .
COPY --from=web /src/dist ./static

ENV MSSQL_DRIVER=pymssql
ENV NODE_ENV=production
ENV SERVE_FRONTEND=1

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-3000}
