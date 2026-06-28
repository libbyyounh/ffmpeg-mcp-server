# ---- Stage 1: system deps (ffmpeg) ----
# This layer rarely changes, will be cached in registry and not re-pushed
FROM python:3.11-slim AS base

ARG USE_CN_MIRROR=0

RUN if [ "$USE_CN_MIRROR" = "1" ]; then \
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources || \
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list; \
    fi

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Stage 2: python deps ----
FROM base AS deps

WORKDIR /app

ARG PIP_INDEX=""
ARG UV_INDEX=""

COPY pyproject.toml uv.lock ./

RUN if [ -n "$PIP_INDEX" ]; then \
        pip install --no-cache-dir uv -i "$PIP_INDEX"; \
    else \
        pip install --no-cache-dir uv; \
    fi

RUN if [ -n "$UV_INDEX" ]; then \
        UV_INDEX_URL="$UV_INDEX" uv sync --no-install-project; \
    else \
        uv sync --no-install-project; \
    fi

# ---- Stage 3: final image ----
FROM deps AS final

WORKDIR /app

COPY README.md ./
COPY src/ ./src/

RUN uv sync

ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8032
ENV PYTHONUNBUFFERED=1

EXPOSE 8032

RUN mkdir -p /videos /output
VOLUME ["/videos", "/output"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8032/health || exit 1

CMD ["uv", "run", "ffmpeg-mcp"]
