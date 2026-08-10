# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    MAA_CONFIG_DIR=/etc/maa \
    PATH="/usr/local/bin:${PATH}" \
    # 将 MaaCore / 资源落到可挂载目录，避免重建容器丢包
    XDG_DATA_HOME=/var/lib/maa/xdg-data \
    XDG_CACHE_HOME=/var/lib/maa/xdg-cache \
    XDG_STATE_HOME=/var/lib/maa/xdg-state \
    XDG_CONFIG_HOME=/etc/maa-xdg-config \
    LD_LIBRARY_PATH=/var/lib/maa/xdg-data/maa/lib

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        adb \
        ca-certificates \
        curl \
        git \
        xz-utils \
        libstdc++6 \
        libgcc-s1 \
        libatomic1 \
        libssl3 \
        zlib1g \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/lib/maa/xdg-data /var/lib/maa/xdg-cache /var/lib/maa/xdg-state

# 默认任务 / profile / cli 配置
COPY maa-config/ /etc/maa/

# 仅预装 maa-cli 二进制（体积小、构建稳）；MaaCore 由 entrypoint 首次拉取
RUN curl -fsSL https://raw.githubusercontent.com/MaaAssistantArknights/maa-cli/main/install.sh \
    | MAA_INSTALL_DIR=/usr/local/bin bash \
    && maa --version

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY docker_ops.py main.py maa_token.py entrypoint.sh /app/
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-u", "main.py"]
