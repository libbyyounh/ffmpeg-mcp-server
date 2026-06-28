FROM python:3.11-slim

WORKDIR /app

ARG USE_CN_MIRROR=0
ARG PIP_INDEX=""
ARG UV_INDEX=""

ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8032

# 让 uv 不创建项目内 .venv，直接装到系统 Python
ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN if [ "$USE_CN_MIRROR" = "1" ]; then \
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources || true; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

RUN if [ -n "$PIP_INDEX" ]; then \
        pip install --no-cache-dir uv -i "$PIP_INDEX"; \
    else \
        pip install --no-cache-dir uv; \
    fi

RUN if [ -n "$UV_INDEX" ]; then \
        UV_INDEX_URL="$UV_INDEX" uv sync --frozen --no-dev; \
    else \
        uv sync --frozen --no-dev; \
    fi

RUN mkdir -p /videos /output

EXPOSE 8032

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8032/health || exit 1

CMD ["uv", "run", "ffmpeg-mcp"]