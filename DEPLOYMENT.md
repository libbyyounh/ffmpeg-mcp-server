# FFmpeg MCP Docker 部署指南

## 🎯 概述

此项目已成功改造为支持 Docker 部署的 HTTP API 服务，可以让其他大模型通过 HTTP 调用 FFmpeg 视频处理功能。

## ✨ 改造内容

### 1. **代码改造**
- ✅ `server.py`: 添加 HTTP/SSE 传输模式支持
- ✅ `ffmpeg.py`: 扩展 Linux 平台支持（使用系统 FFmpeg）
- ✅ 通过环境变量配置服务器参数

### 2. **Docker 支持**
- ✅ `Dockerfile`: 完整的 Docker 镜像构建配置
- ✅ `docker-compose.yml`: 一键启动配置
- ✅ `.dockerignore`: 优化构建性能
- ✅ `.env.example`: 环境变量模板

### 3. **文档和工具**
- ✅ `README.md`: 更新部署文档
- ✅ `API_EXAMPLES.md`: 详细的 API 使用示例
- ✅ `DEPLOYMENT.md`: 部署总结（本文件）
- ✅ `start.sh`: 快速启动脚本
- ✅ `test_client.py`: 测试客户端

## 🚀 快速开始

### 方法一：使用启动脚本（推荐）

```bash
# 1. 运行启动脚本
./start.sh

# 2. 测试服务
python3 test_client.py
```

### 方法二：手动启动

```bash
# 1. 创建必要目录
mkdir -p videos output

# 2. 复制环境变量配置
cp .env.example .env

# 3. 启动服务
docker-compose up -d --build

# 4. 查看日志
docker-compose logs -f
```

## 📡 服务访问

- **服务地址**: `http://localhost:8032`
- **传输协议**: SSE (Server-Sent Events)
- **MCP 协议**: 标准 MCP over HTTP

## 🔧 配置说明

### 环境变量

在 `.env` 文件中配置：

```bash
MCP_TRANSPORT=sse      # 传输方式: stdio 或 sse
MCP_HOST=0.0.0.0       # 监听地址
MCP_PORT=8032          # 监听端口
```

### 目录映射

| 容器内路径 | 宿主机路径 | 说明 |
|-----------|-----------|------|
| `/videos` | `./videos` | 输入视频目录 |
| `/output` | `./output` | 输出视频目录 |

## 📚 API 使用

### 可用工具

1. **find_video_path** - 查找视频文件
2. **get_video_info** - 获取视频信息
3. **clip_video** - 裁剪视频
4. **concat_videos** - 拼接视频
5. **overlay_video** - 视频叠加（画中画）
6. **scale_video** - 视频缩放
7. **extract_frames_from_video** - 提取视频帧
8. **play_video** - 播放视频

详细使用方法请参考 `API_EXAMPLES.md`

### Python 调用示例

```python
import requests
import json

def call_ffmpeg_tool(tool_name, arguments):
    response = requests.post(
        "http://localhost:8032/message",
        headers={"Content-Type": "application/json"},
        json={
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
    )
    return response.json()

# 获取视频信息
result = call_ffmpeg_tool("get_video_info", {
    "video_path": "/videos/test.mp4"
})
print(result)

# 裁剪视频
result = call_ffmpeg_tool("clip_video", {
    "video_path": "/videos/input.mp4",
    "start": "00:01:00",
    "duration": 30,
    "output_path": "/output/clip.mp4"
})
print(result)
```

### cURL 调用示例

```bash
# 获取视频信息
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "get_video_info",
      "arguments": {
        "video_path": "/videos/test.mp4"
      }
    }
  }'
```

## 🤖 AI 模型集成

### 集成方式

其他大模型可以通过以下方式调用此服务：

1. **直接 HTTP 调用**: 使用 POST 请求调用 MCP 工具
2. **MCP 客户端**: 使用标准 MCP 客户端库
3. **自定义封装**: 根据 API_EXAMPLES.md 创建客户端

### 推荐集成模式

```
AI 模型 → HTTP Client → FFmpeg MCP Server → FFmpeg → 视频处理结果
```

### 示例：让 AI 模型理解服务

向 AI 模型提供以下上下文：

```
你可以访问一个运行在 http://localhost:8032 的 FFmpeg MCP 服务器。
该服务器提供以下视频处理工具：

1. get_video_info(video_path) - 获取视频元数据
2. clip_video(video_path, start, end/duration, output_path) - 裁剪视频
3. concat_videos(input_files[], output_path, fast) - 合并视频
4. overlay_video(background, overlay, position, dx, dy) - 视频叠加
5. scale_video(video_path, width, height) - 调整尺寸
6. extract_frames_from_video(video_path, fps, format) - 提取帧

所有输入视频位于 /videos/ 目录，输出应保存到 /output/ 目录。
```

## 🔍 测试和验证

### 1. 健康检查

```bash
curl http://localhost:8032/
```

### 2. 运行测试客户端

```bash
python3 test_client.py
```

### 3. 手动测试工具

```bash
# 将测试视频放入 videos 目录
cp ~/test.mp4 ./videos/

# 调用 API 获取信息
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "get_video_info",
      "arguments": {"video_path": "/videos/test.mp4"}
    }
  }'
```

## 🐛 故障排查

### 服务无法启动

```bash
# 查看日志
docker-compose logs

# 检查端口占用
lsof -i :8032

# 重新构建
docker-compose down
docker-compose up -d --build
```

### FFmpeg 执行失败

```bash
# 进入容器检查
docker exec -it ffmpeg-mcp-server bash

# 验证 FFmpeg
ffmpeg -version

# 检查文件权限
ls -la /videos
ls -la /output
```

### 路径问题

- ✅ 容器内使用: `/videos/file.mp4` 和 `/output/result.mp4`
- ❌ 不要使用: `./videos/file.mp4` 或相对路径

## 📊 性能优化

### 资源限制

在 `docker-compose.yml` 中调整：

```yaml
deploy:
  resources:
    limits:
      cpus: '4'        # 增加 CPU 限制
      memory: 4G       # 增加内存限制
```

### 并发处理

当前版本单实例处理请求。如需并发，可以：

1. 启动多个实例（不同端口）
2. 使用负载均衡器分发请求
3. 使用消息队列实现异步处理

## 🔒 安全建议

1. **生产环境**: 添加认证中间件
2. **文件访问**: 限制文件路径范围
3. **资源限制**: 设置合理的超时和资源配额
4. **网络隔离**: 仅暴露必要端口
5. **日志审计**: 记录所有操作

## 📈 后续改进建议

- [ ] 添加认证和授权
- [ ] 实现任务队列和异步处理
- [ ] 添加进度回调
- [ ] 支持更多视频格式和编码
- [ ] 实现视频缓存
- [ ] 添加 Prometheus 监控
- [ ] 实现速率限制

## 🆘 支持

遇到问题？

1. 查看 `API_EXAMPLES.md` 获取详细示例
2. 运行 `test_client.py` 验证服务
3. 查看 Docker 日志排查问题
4. 提交 GitHub Issue

## ✅ 验收清单

部署成功的标志：

- [x] Docker 容器正常运行
- [x] 健康检查返回 200
- [x] test_client.py 执行成功
- [x] 能够获取视频信息
- [x] 能够成功处理视频

## 📝 更新日志

### v0.2.0 (2026-01-31)
- ✅ 添加 HTTP/SSE 支持
- ✅ 添加 Linux 平台支持
- ✅ 完整 Docker 部署方案
- ✅ API 文档和示例
- ✅ 测试工具和脚本

恭喜！🎉 你的 FFmpeg MCP 服务器已经可以通过 HTTP 让其他大模型调用了！
