# 使用 Python 3.11 官方镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 构建参数：是否使用国内镜像源（本地构建传入 USE_CN_MIRROR=1 启用）
ARG USE_CN_MIRROR=0

# 可选：使用清华源替换默认源（仅在国内构建时启用）
RUN if [ "$USE_CN_MIRROR" = "1" ]; then \
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources || \
        sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list; \
    fi

# 安装系统依赖和 FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 验证 FFmpeg 安装
RUN ffmpeg -version && ffprobe -version

# 复制项目文件
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# 构建参数：pip/uv 镜像源（默认官方源）
ARG PIP_INDEX=""
ARG UV_INDEX=""

# 安装 uv (快速的 Python 包管理器)
RUN if [ -n "$PIP_INDEX" ]; then \
        pip install --no-cache-dir uv -i "$PIP_INDEX"; \
    else \
        pip install --no-cache-dir uv; \
    fi

# 使用 uv 安装项目依赖
RUN if [ -n "$UV_INDEX" ]; then \
        UV_INDEX_URL="$UV_INDEX" uv sync; \
    else \
        uv sync; \
    fi

# 设置环境变量
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8032
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 8032

# 创建视频处理工作目录
RUN mkdir -p /videos /output
VOLUME ["/videos", "/output"]

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8032/health || exit 1

# 运行服务
CMD ["uv", "run", "ffmpeg-mcp"]
