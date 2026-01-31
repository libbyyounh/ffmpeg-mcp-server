#!/bin/bash

# FFmpeg MCP Server 快速启动脚本

set -e

echo "🎬 FFmpeg MCP Server - Quick Start"
echo "=================================="

# 创建必要的目录
echo "📁 Creating directories..."
mkdir -p videos output

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
fi

# 构建并启动服务
echo "🚀 Building and starting FFmpeg MCP Server..."
docker compose up -d --build

# 等待服务启动
echo "⏳ Waiting for server to start..."
sleep 5

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo "✅ FFmpeg MCP Server is running!"
    echo ""
    echo "📡 Server URL: http://localhost:8032"
    echo "📚 API Documentation: See API_EXAMPLES.md"
    echo ""
    echo "📋 Useful commands:"
    echo "   View logs:        docker-compose logs -f"
    echo "   Stop server:      docker-compose down"
    echo "   Restart server:   docker-compose restart"
    echo ""
    echo "📂 Directories:"
    echo "   Input videos:     ./videos/"
    echo "   Output videos:    ./output/"
else
    echo "❌ Failed to start server. Check logs with: docker-compose logs"
    exit 1
fi
