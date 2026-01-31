# 使用 Python 3.11 官方镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 使用清华源替换默认源
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources || \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list

# 安装系统依赖和 FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 验证 FFmpeg 安装
RUN ffmpeg -version && ffprobe -version && ffplay -version || true

# 复制项目文件
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/

# 安装 uv (快速的 Python 包管理器)
RUN pip install --no-cache-dir uv -i https://pypi.tuna.tsinghua.edu.cn/simple

# 使用 uv 安装项目依赖
RUN uv sync

# 设置环境变量
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8032
ENV PYTHONUNBUFFERED=1
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 暴露端口
EXPOSE 8032

# 创建视频处理工作目录
RUN mkdir -p /videos /output
VOLUME ["/videos", "/output"]

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8032/ || exit 1

# 运行服务
CMD ["uv", "run", "ffmpeg-mcp"]
