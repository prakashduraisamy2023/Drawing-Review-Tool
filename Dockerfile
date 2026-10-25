
# Stage 1: Build React frontend
FROM node:24-bookworm-slim AS frontend-builder

WORKDIR /build/frontend

RUN npm install -g pnpm@12.15.0

COPY frontend/package.json frontend/pnpm-lock.yaml ./

RUN pnpm install --frozen-lockfile

COPY frontend/ ./

RUN pnpm run build


# Stage 2: Python + FastAPI application
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DRAWING_DEMO_MODE=true
ENV DRAWING_LEVEL3_ENABLED=true
ENV DRAWING_LEVEL4_ENABLED=true
ENV DRAWING_STORAGE_DIR=/app/data/output/drawings

COPY backend/requirements.txt /app/backend/requirements.txt

RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ /app/backend/
COPY config/ /app/config/

COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

RUN mkdir -p /app/data/output/drawings

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
