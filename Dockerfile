# syntax=docker/dockerfile:1

ARG APP_VERSION=0.2.7

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ARG APP_VERSION=0.2.7
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} \
    APP_ENV=production \
    STATIC_DIR=/app/static \
    DATA_DIR=/app/data \
    UPLOAD_DIR=/app/uploads \
    # 同容器内嵌 Redis（入口脚本拉起）；本地开发可留空走进程内降级
    REDIS_URL=redis://127.0.0.1:6379/0 \
    EMBEDDED_REDIS=1 \
    PATH="/usr/local/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates redis-server \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend-build /src/frontend/dist /app/static
COPY VERSION /app/VERSION
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

RUN mkdir -p /app/data /app/uploads/avatars \
    && printf '%s' "${APP_VERSION}" > /app/VERSION \
    && chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

WORKDIR /app/backend
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
