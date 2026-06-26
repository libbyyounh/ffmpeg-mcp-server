# HTTP REST API 设计文档

> 日期：2026-06-26
> 状态：已批准
> 方案：A — RPC 直映射

## 1. 背景

当前项目是一个基于 FFmpeg 的 MCP 服务，通过 MCP 协议（stdio 或 SSE）提供视频处理工具。现有 MCP 工具共 16 个，涵盖视频剪辑、拼接、叠加、缩放、信息查询等能力。

需要为其他后端服务提供标准 HTTP REST API，使其无需 MCP 客户端即可调用这些视频处理能力。

## 2. 设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| API 风格 | RPC 直映射（方案 A） | 工具型 API，调用方关心"执行操作"而非"管理资源" |
| API 范围 | 15 个 MCP 工具（排除 play_video） | play_video 需要本地播放器，后端服务场景无意义 |
| 认证方式 | 复用现有 Bearer Token | 统一认证，MCP_AUTH_TOKEN 环境变量 |
| 服务模式 | 同一进程同一端口 | 最小改动，MCP SSE 和 REST API 共存 |
| `play_video` | 已移除 | ffplay 需要本地播放器，MCP 和 HTTP 均不保留 |
| `get_task_status` 不存在时 | 返回 404 | REST 语义更正确，与 MCP 的 200+error 有差异，已在 spec 中注明 |

## 3. 架构

```
                         ┌─────────────────────────────────┐
                         │      uvicorn (port 8032)        │
                         │         Starlette App           │
                         ├─────────────────────────────────┤
                         │     TokenAuthMiddleware         │
                         │   (Bearer Token，两种协议共用)    │
                         ├──────────────┬──────────────────┤
                         │   /sse/*     │   /api/*         │
                         │   MCP SSE    │   REST API       │
                         │   (现有)      │   (新增)          │
                         ├──────────────┴──────────────────┤
                         │      共享核心业务层               │
                         │  cut_video / task_manager /     │
                         │  utils / ffmpeg                 │
                         ├─────────────────────────────────┤
                         │   静态文件服务                    │
                         │   /output/*  /videos/*          │
                         └─────────────────────────────────┘
```

- REST API 路由挂在 `/api/` 前缀下，和 MCP SSE 的 `/sse` 路径互不干扰
- 认证中间件已有的 `TokenAuthMiddleware` 同时保护两种协议
- 所有 REST 端点直接调用核心模块（`cut_video`、`task_manager` 等），不经过 MCP 层
- 新增 `http_routes.py` 文件集中定义所有 REST 路由

## 4. 端点映射

### 4.1 同步端点（直接返回结果）

| 方法 | 端点 | 对应 MCP 工具 | 参数方式 |
|------|------|--------------|----------|
| `GET` | `/api/find_video_path` | `find_video_path` | 查询参数 `?root_path=&video_name=` |
| `GET` | `/api/get_video_info` | `get_video_info` | 查询参数 `?video_path=` |
| `GET` | `/api/get_audio_info` | `get_audio_info` | 查询参数 `?audio_path=` |
| `GET` | `/api/download_video` | `download_video` | 查询参数 `?video_path=&base64=false` |
| `GET` | `/api/get_task_status/{task_id}` | `get_task_status` | 路径参数（UUID 格式） |
| `GET` | `/api/list_output_videos` | `list_output_videos` | 无参数 |
| `GET` | `/api/list_videos_folder` | `list_videos_folder` | 无参数 |
| `POST` | `/api/delete_videos` | `delete_videos` | Body: `{"video_paths": [...]}` |

### 4.2 异步端点（提交任务，返回 task_id）

| 方法 | 端点 | 对应 MCP 工具 | Body 参数 |
|------|------|--------------|-----------|
| `POST` | `/api/clip_video` | `clip_video` | `video_path`, `start?`, `end?`, `duration?`, `output_path?`, `time_out?` |
| `POST` | `/api/concat_videos` | `concat_videos` | `input_files[]`, `output_path?`, `fast?` |
| `POST` | `/api/concat_videos_with_mp3` | `concat_videos_with_mp3` | `video_paths[]`, `audio_path`, `output_path?`, `mute_video_audio?`, `order?` |
| `POST` | `/api/concat_videos_with_mp3_video_first` | `concat_videos_with_mp3_video_first` | `video_paths[]`, `audio_path`, `output_path?`, `mute_video_audio?`, `order?` |
| `POST` | `/api/overlay_video` | `overlay_video` | `background_video`, `overlay_video`, `output_path?`, `position?`, `dx?`, `dy?` |
| `POST` | `/api/scale_video` | `scale_video` | `video_path`, `width`, `height`, `output_path?` |
| `POST` | `/api/extract_frames_from_video` | `extract_frames_from_video` | `video_path`, `fps?`, `output_folder?`, `format?`, `total_frames?` |

### 4.3 设计规则

- 查询类（只读、无副作用）→ `GET` + 查询参数
- 操作类（有副作用、需要复杂参数）→ `POST` + JSON body
- `play_video` 不暴露为 HTTP API（ffplay 需要本地播放器）

## 5. 请求/响应格式

### 5.1 通用响应结构

```json
{
  "code": 0,
  "data": { ... },
  "message": "success"
}
```

- `code`: 0 表示成功，非 0 表示失败
- `data`: 业务数据，失败时为 null
- `message`: 描述信息

### 5.2 同步端点响应示例

```json
// GET /api/get_video_info?video_path=/videos/test.mp4
{
  "code": 0,
  "data": {
    "streams": [...],
    "format": {...}
  },
  "message": "success"
}
```

### 5.3 异步端点响应示例

```json
// POST /api/clip_video
// 请求体: {"video_path": "/videos/test.mp4", "start": 10, "end": 30}
{
  "code": 0,
  "data": {
    "task_id": "uuid-xxx",
    "status": "PENDING"
  },
  "message": "Task submitted successfully"
}
```

### 5.4 任务状态查询响应

```json
// GET /api/get_task_status/uuid-xxx
{
  "code": 0,
  "data": {
    "id": "uuid-xxx",
    "status": "COMPLETED",
    "tool": "clip_video",
    "params": { "video_path": "/videos/test.mp4", "start": 10, "end": 30 },
    "result": {
      "status": 0,
      "log": "...",
      "path": "/output/test_clip.mp4",
      "url": "http://host:8032/output/test_clip.mp4"
    },
    "error": null,
    "start_time": 1719400000.0,
    "end_time": 1719400005.0
  },
  "message": "success"
}
```

任务状态值：`PENDING` | `RUNNING` | `COMPLETED` | `FAILED`

### 5.5 HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| `200` | 请求成功（包括任务提交成功、查询成功、任务执行失败但请求本身成功） |
| `400` | 参数错误（缺少必填参数、类型错误） |
| `401` | 认证失败（缺少或无效的 Bearer Token） |
| `404` | 资源不存在（task_id 不存在、文件不存在）。注：与 MCP 工具返回 200+error 不同，REST API 使用 404 更符合 HTTP 语义 |
| `500` | 服务器内部错误 |

**注意**：异步任务执行失败时，HTTP 状态码仍为 `200`，通过 `data.status === "FAILED"` 和 `data.error` 判断业务失败。

### 5.6 异步端点参数校验规则

- **参数格式校验**（缺少必填字段、类型错误）→ 在提交任务前完成，返回 `400`
- **业务校验**（文件不存在、格式不支持等）→ 放到后台线程中执行，通过 task status 返回 `FAILED` + `error`

## 6. 认证

复用现有 `MCP_AUTH_TOKEN` 环境变量。

- 请求头：`Authorization: Bearer <token>`
- 未设置 `MCP_AUTH_TOKEN` 时，所有请求免认证（与现有 MCP SSE 行为一致）
- `/health` 和 `/` 端点免认证（现有行为）
- `/output/*` 和 `/videos/*` 静态文件免认证（现有行为）

## 7. 文件结构变更

```
src/ffmpeg_mcp/
├── server.py          # 修改：启动时挂载 REST 路由（约 5 行改动）
├── http_routes.py     # 新增：所有 REST API 路由定义（约 250 行）
├── cut_video.py       # 不动
├── task_manager.py    # 不动
├── utils.py           # 不动
├── ffmpeg.py          # 不动
└── typedef.py         # 不动
```

依赖变化：无。`starlette` 已经是 `mcp[cli]` 的依赖。

## 8. 实现要点

### 8.1 http_routes.py 核心结构

```python
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse
import ffmpeg_mcp.cut_video as cut_video
import ffmpeg_mcp.utils as utils
from ffmpeg_mcp.task_manager import task_manager
import threading

def success(data, message="success"):
    return JSONResponse({"code": 0, "data": data, "message": message})

def error(message, code=1, status_code=400):
    return JSONResponse({"code": code, "data": None, "message": message}, status_code=status_code)

# 同步端点示例
async def get_video_info(request: Request):
    video_path = request.query_params.get("video_path")
    if not video_path:
        return error("video_path is required")
    result = cut_video.get_video_info(utils.ensure_local_path(video_path))
    return success(result)

# 异步端点示例
async def clip_video(request: Request):
    body = await request.json()
    video_path = body.get("video_path")
    if not video_path:
        return error("video_path is required")
    # 创建 task → 启动线程 → 返回 task_id
    task_id = task_manager.create_task("clip_video", body)
    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_path = utils.ensure_local_path(video_path)
            result = cut_video.clip_video_ffmpeg(local_path, ...)
            task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))
    threading.Thread(target=run_task).start()
    return success({"task_id": task_id, "status": "PENDING"}, "Task submitted successfully")

# get_task_status 端点（返回 404 而非 MCP 的 200+error）
async def get_task_status(request: Request):
    task_id = request.path_params["task_id"]
    status = task_manager.get_task_status(task_id)
    if not status:
        return error(f"Task ID {task_id} not found", status_code=404)
    return success(status)

# 路由表
routes = [
    Route("/api/find_video_path", find_video_path, methods=["GET"]),
    Route("/api/get_video_info", get_video_info, methods=["GET"]),
    Route("/api/get_task_status/{task_id}", get_task_status, methods=["GET"]),
    Route("/api/clip_video", clip_video, methods=["POST"]),
    # ... 其余 12 个端点
]
```

### 8.2 server.py 修改

```python
# main() 函数中，SSE 模式下挂载 REST 路由
if transport == 'sse':
    app = mcp.sse_app()
    # 新增：挂载 REST API 路由
    from ffmpeg_mcp.http_routes import routes
    app.routes.extend(routes)
    # ... 其余不变
```

## 9. 调用示例

```bash
# 获取视频信息
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8032/api/get_video_info?video_path=/videos/test.mp4"

# 剪辑视频（异步）
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"video_path":"/videos/test.mp4","start":10,"end":30}' \
  "http://localhost:8032/api/clip_video"

# 查询任务状态
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8032/api/get_task_status/uuid-xxx"

# 拼接视频
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input_files":["/videos/a.mp4","/videos/b.mp4"]}' \
  "http://localhost:8032/api/concat_videos"
```
