# syntax=docker/dockerfile:1

ARG APP_VERSION=0.1.5

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ARG APP_VERSION=0.1.5
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} \
    STATIC_DIR=/app/static \
    DATA_DIR=/app/data \
    UPLOAD_DIR=/app/uploads \
    UPDATE_ENABLED=false \
    UPDATE_COMPOSE_FILE=/deploy/compose.yml \
    UPDATE_COMPOSE_SERVICE=app \
    PATH="/usr/local/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# docker CLI + compose plugin：管理端一键更新时通过挂载的 docker.sock 调用
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker/compose-bin:v2.32.4 /docker-compose \
    /usr/local/lib/docker/cli-plugins/docker-compose

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend-build /src/frontend/dist /app/static
COPY VERSION /app/VERSION

RUN mkdir -p /app/data /app/uploads/avatars /deploy \
    && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose \
    && printf '%s' "${APP_VERSION}" > /app/VERSION

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
