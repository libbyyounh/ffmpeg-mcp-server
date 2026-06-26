# HTTP REST API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add REST HTTP API endpoints to the existing ffmpeg-mcp-server, exposing all 16 MCP tools as standard REST endpoints under `/api/` prefix.

**Architecture:** New `http_routes.py` file defines Starlette Route handlers that directly call the existing `cut_video` and `task_manager` core modules. Routes are mounted onto the existing Starlette app in `server.py` during SSE mode startup. Same process, same port, shared auth middleware.

**Tech Stack:** Python, Starlette (already a dependency via mcp[cli]), uvicorn

**Spec:** `docs/superpowers/specs/2026-06-26-http-api-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/ffmpeg_mcp/http_routes.py` | All 16 REST API route handlers + utility functions |
| Modify | `src/ffmpeg_mcp/server.py` | Mount `http_routes.routes` onto the Starlette app (~5 lines) |

No other files touched. No new dependencies.

---

### Task 1: Create http_routes.py — utility functions + sync GET endpoints

**Files:**
- Create: `src/ffmpeg_mcp/http_routes.py`

- [ ] **Step 1: Create http_routes.py with utility functions and sync GET endpoints**

Create `src/ffmpeg_mcp/http_routes.py` with the following content:

```python
# http_routes.py
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse
import os

import ffmpeg_mcp.cut_video as cut_video
import ffmpeg_mcp.utils as utils
from ffmpeg_mcp.task_manager import task_manager
from ffmpeg_mcp.server import get_file_url
import threading
import base64 as b64
import mimetypes


# --- Utility functions ---

def success(data, message="success"):
    return JSONResponse({"code": 0, "data": data, "message": message})

def error(message, code=1, status_code=400):
    return JSONResponse({"code": code, "data": None, "message": message}, status_code=status_code)


# --- Sync GET endpoints ---

async def find_video_path(request: Request):
    """GET /api/find_video_path?root_path=&video_name="""
    root_path = request.query_params.get("root_path")
    video_name = request.query_params.get("video_name")
    if not root_path or not video_name:
        return error("root_path and video_name are required")

    VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.ts'}
    target_stem, target_ext = os.path.splitext(video_name)
    if target_ext.lower() not in VIDEO_EXTS:
        target_stem = f"{target_stem}{target_ext}"
        target_ext = ""

    for root, dirs, files in os.walk(root_path):
        for file in files:
            stem, ext = os.path.splitext(file)
            if stem.lower() == target_stem.lower():
                if (not target_ext or ext.lower() in VIDEO_EXTS):
                    return success({"path": os.path.join(root, file)})
    return success({"path": ""})


async def get_video_info(request: Request):
    """GET /api/get_video_info?video_path="""
    video_path = request.query_params.get("video_path")
    if not video_path:
        return error("video_path is required")
    video_path = utils.ensure_local_path(video_path)
    result = cut_video.get_video_info(video_path)
    return success(result)


async def get_audio_info(request: Request):
    """GET /api/get_audio_info?audio_path="""
    audio_path = request.query_params.get("audio_path")
    if not audio_path:
        return error("audio_path is required")
    audio_path = utils.ensure_local_path(audio_path)
    result = cut_video.get_audio_info(audio_path)
    return success(result)


async def download_video(request: Request):
    """GET /api/download_video?video_path=&base64=false"""
    video_path = request.query_params.get("video_path")
    base64_param = request.query_params.get("base64", "false").lower() == "true"
    if not video_path:
        return error("video_path is required")

    video_path = utils.ensure_local_path(video_path)
    if not os.path.exists(video_path):
        return error(f"文件不存在: {video_path}", status_code=404)

    abs_path = os.path.abspath(video_path)
    allowed_dirs = ["/videos", "/output", os.getcwd()]
    is_allowed = any(abs_path.startswith(os.path.abspath(d)) for d in allowed_dirs)
    if not is_allowed:
        return error("权限拒绝：只能访问 /videos 或 /output 目录下的文件", status_code=403)

    file_size = os.path.getsize(abs_path)
    mime_type, _ = mimetypes.guess_type(abs_path)

    result = {
        "filename": os.path.basename(abs_path),
        "mime_type": mime_type or "application/octet-stream",
        "size": file_size,
        "path": abs_path,
        "url": get_file_url(abs_path)
    }

    if base64_param:
        if file_size > 200 * 1024 * 1024:
            return error(f"文件太大 ({file_size / (1024 * 1024):.2f}MB)，超过 200MB 限制")
        try:
            with open(abs_path, "rb") as f:
                content = f.read()
                result["base64_data"] = b64.b64encode(content).decode("utf-8")
        except Exception as e:
            return error(f"读取文件失败: {str(e)}", status_code=500)

    return success(result)


async def get_task_status(request: Request):
    """GET /api/get_task_status/{task_id}"""
    task_id = request.path_params["task_id"]
    status = task_manager.get_task_status(task_id)
    if not status:
        return error(f"Task ID {task_id} not found", status_code=404)
    return success(status)


async def list_output_videos(request: Request):
    """GET /api/list_output_videos"""
    VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.ts'}
    output_dir = "/output"
    if not os.path.exists(output_dir):
        output_dir = os.path.join(os.getcwd(), "output")
        if not os.path.exists(output_dir):
            return success([])

    video_files = []
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if os.path.splitext(file)[1].lower() in VIDEO_EXTS:
                video_files.append(os.path.abspath(os.path.join(root, file)))
    return success(video_files)


async def list_videos_folder(request: Request):
    """GET /api/list_videos_folder"""
    VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.ts'}
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_file_dir, "../../"))
    videos_dir = "/videos" if os.path.exists("/videos") else os.path.join(project_root, "videos")

    if not os.path.exists(videos_dir):
        return success([])

    video_files = []
    for root, dirs, files in os.walk(videos_dir):
        for file in files:
            if os.path.splitext(file)[1].lower() in VIDEO_EXTS:
                video_files.append(os.path.abspath(os.path.join(root, file)))
    return success(video_files)
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/ffmpeg_mcp/http_routes.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add src/ffmpeg_mcp/http_routes.py
git commit -m "feat(http-api): add utility functions and sync GET endpoints"
```

---

### Task 2: Add sync POST endpoints (delete_videos, play_video)

**Files:**
- Modify: `src/ffmpeg_mcp/http_routes.py`

- [ ] **Step 1: Append sync POST endpoints to http_routes.py**

Add the following at the end of `http_routes.py` (before the routes list):

```python
# --- Sync POST endpoints ---

async def delete_videos(request: Request):
    """POST /api/delete_videos — Body: {"video_paths": [...]}"""
    body = await request.json()
    video_paths = body.get("video_paths")
    if not video_paths or not isinstance(video_paths, list):
        return error("video_paths is required and must be a list")

    results = {"success": [], "failed": []}
    allowed_dirs = ["/videos", "/output", os.getcwd()]
    abs_allowed_dirs = [os.path.abspath(d) for d in allowed_dirs]

    for path in video_paths:
        try:
            abs_path = os.path.abspath(path)
            is_allowed = any(abs_path.startswith(allowed) for allowed in abs_allowed_dirs)
            if not is_allowed:
                results["failed"].append({"path": path, "reason": "权限拒绝：仅限删除 /videos 或 /output 目录下的文件"})
                continue
            if not os.path.exists(abs_path):
                results["failed"].append({"path": path, "reason": "文件不存在"})
                continue
            os.remove(abs_path)
            results["success"].append(path)
        except Exception as e:
            results["failed"].append({"path": path, "reason": str(e)})

    return success(results)


async def play_video(request: Request):
    """POST /api/play_video — Body: {"video_path": "...", "speed": 1, "loop": 1}
    ⚠️ 仅限本地开发环境，服务器/Docker 下不可用
    """
    body = await request.json()
    video_path = body.get("video_path")
    if not video_path:
        return error("video_path is required")

    speed = body.get("speed", 1)
    loop = body.get("loop", 1)
    video_path = utils.ensure_local_path(video_path)
    result = cut_video.video_play(video_path, speed=speed, loop=loop)
    return success(result)
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/ffmpeg_mcp/http_routes.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add src/ffmpeg_mcp/http_routes.py
git commit -m "feat(http-api): add delete_videos and play_video POST endpoints"
```

---

### Task 3: Add async POST endpoints

**Files:**
- Modify: `src/ffmpeg_mcp/http_routes.py`

- [ ] **Step 1: Append all 7 async endpoints to http_routes.py**

Add the following before the routes list:

```python
# --- Async POST endpoints (return task_id) ---

async def clip_video(request: Request):
    """POST /api/clip_video"""
    body = await request.json()
    video_path = body.get("video_path")
    if not video_path:
        return error("video_path is required")

    start = body.get("start")
    end = body.get("end")
    duration = body.get("duration")
    output_path = body.get("output_path")
    time_out = body.get("time_out", 300)

    task_id = task_manager.create_task("clip_video", body)

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_path = utils.ensure_local_path(video_path)
            result = cut_video.clip_video_ffmpeg(local_path, start=start, end=end, duration=duration, output_path=output_path, time_out=time_out)
            if isinstance(result, (set, list, tuple)) and len(result) >= 3:
                status, log, path = list(result)
                task_manager.update_task(task_id, "COMPLETED", result={"status": status, "log": log, "path": path, "url": get_file_url(path)})
            else:
                task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return success({"task_id": task_id, "status": "PENDING"}, "Task submitted successfully")


async def concat_videos(request: Request):
    """POST /api/concat_videos"""
    body = await request.json()
    input_files = body.get("input_files")
    if not input_files or not isinstance(input_files, list):
        return error("input_files is required and must be a list")

    output_path = body.get("output_path")
    fast = body.get("fast", True)

    task_id = task_manager.create_task("concat_videos", body)

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_files = [utils.ensure_local_path(f) for f in input_files]
            result = cut_video.concat_videos(local_files, output_path, fast)
            if isinstance(result, (tuple, list)) and len(result) >= 2:
                code, log = result[:2]
                task_manager.update_task(task_id, "COMPLETED", result={"status": code, "log": log})
            else:
                task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return success({"task_id": task_id, "status": "PENDING"}, "Task submitted successfully")


async def concat_videos_with_mp3(request: Request):
    """POST /api/concat_videos_with_mp3"""
    body = await request.json()
    video_paths = body.get("video_paths")
    audio_path = body.get("audio_path")
    if not video_paths or not isinstance(video_paths, list):
        return error("video_paths is required and must be a list")
    if not audio_path:
        return error("audio_path is required")

    output_path = body.get("output_path")
    mute_video_audio = body.get("mute_video_audio", True)
    order = body.get("order", "sequence")

    task_id = task_manager.create_task("concat_videos_with_mp3", body)

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_videos = [utils.ensure_local_path(v) for v in video_paths]
            local_audio = utils.ensure_local_path(audio_path)
            result = cut_video.concat_videos_with_mp3(local_videos, local_audio, output_path, mute_video_audio, order)
            if isinstance(result, (tuple, list)) and len(result) >= 3:
                status, log, path = result[0], result[1], result[2]
                task_manager.update_task(task_id, "COMPLETED", result={"status": status, "log": log, "path": path, "url": get_file_url(path)})
            else:
                task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return success({"task_id": task_id, "status": "PENDING"}, "Task submitted successfully")


async def concat_videos_with_mp3_video_first(request: Request):
    """POST /api/concat_videos_with_mp3_video_first"""
    body = await request.json()
    video_paths = body.get("video_paths")
    audio_path = body.get("audio_path")
    if not video_paths or not isinstance(video_paths, list):
        return error("video_paths is required and must be a list")
    if not audio_path:
        return error("audio_path is required")

    output_path = body.get("output_path")
    mute_video_audio = body.get("mute_video_audio", True)
    order = body.get("order", "sequence")

    task_id = task_manager.create_task("concat_videos_with_mp3_video_first", body)

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_videos = [utils.ensure_local_path(v) for v in video_paths]
            local_audio = utils.ensure_local_path(audio_path)
            result = cut_video.concat_videos_with_mp3_video_first(local_videos, local_audio, output_path, mute_video_audio, order)
            if isinstance(result, (tuple, list)) and len(result) >= 3:
                status, log, path = result[0], result[1], result[2]
                task_manager.update_task(task_id, "COMPLETED", result={"status": status, "log": log, "path": path, "url": get_file_url(path)})
            else:
                task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return success({"task_id": task_id, "status": "PENDING"}, "Task submitted successfully")


async def overlay_video(request: Request):
    """POST /api/overlay_video"""
    body = await request.json()
    background = body.get("background_video")
    overlay = body.get("overlay_video")
    if not background:
        return error("background_video is required")
    if not overlay:
        return error("overlay_video is required")

    output_path = body.get("output_path")
    position = body.get("position", 1)
    dx = body.get("dx", 0)
    dy = body.get("dy", 0)

    task_id = task_manager.create_task("overlay_video", body)

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_bg = utils.ensure_local_path(background)
            local_ov = utils.ensure_local_path(overlay)
            result = cut_video.overlay_video(local_bg, local_ov, output_path, position, dx, dy)
            if isinstance(result, (set, list, tuple)) and len(result) >= 3:
                status, log, path = list(result)
                task_manager.update_task(task_id, "COMPLETED", result={"status": status, "log": log, "path": path, "url": get_file_url(path)})
            else:
                task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return success({"task_id": task_id, "status": "PENDING"}, "Task submitted successfully")


async def scale_video(request: Request):
    """POST /api/scale_video"""
    body = await request.json()
    video_path = body.get("video_path")
    width = body.get("width")
    height = body.get("height")
    if not video_path:
        return error("video_path is required")
    if width is None:
        return error("width is required")
    if height is None:
        return error("height is required")

    output_path = body.get("output_path")
    task_id = task_manager.create_task("scale_video", body)

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_path = utils.ensure_local_path(video_path)
            status, log, path = cut_video.scale_video(local_path, width, height, output_path)
            task_manager.update_task(task_id, "COMPLETED", result={"status": status, "log": log, "path": path, "url": get_file_url(path)})
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return success({"task_id": task_id, "status": "PENDING"}, "Task submitted successfully")


async def extract_frames_from_video(request: Request):
    """POST /api/extract_frames_from_video"""
    body = await request.json()
    video_path = body.get("video_path")
    if not video_path:
        return error("video_path is required")

    fps = body.get("fps", 0)
    output_folder = body.get("output_folder")
    format_val = body.get("format", 0)
    total_frames = body.get("total_frames", 0)

    task_id = task_manager.create_task("extract_frames", body)

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_path = utils.ensure_local_path(video_path)
            result = cut_video.extract_frames_from_video(local_path, fps, output_folder, format_val, total_frames)
            task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return success({"task_id": task_id, "status": "PENDING"}, "Task submitted successfully")
```

- [ ] **Step 2: Append the routes list at the end of http_routes.py**

```python
# --- Route table ---

routes = [
    # Sync GET
    Route("/api/find_video_path", find_video_path, methods=["GET"]),
    Route("/api/get_video_info", get_video_info, methods=["GET"]),
    Route("/api/get_audio_info", get_audio_info, methods=["GET"]),
    Route("/api/download_video", download_video, methods=["GET"]),
    Route("/api/get_task_status/{task_id}", get_task_status, methods=["GET"]),
    Route("/api/list_output_videos", list_output_videos, methods=["GET"]),
    Route("/api/list_videos_folder", list_videos_folder, methods=["GET"]),
    # Sync POST
    Route("/api/delete_videos", delete_videos, methods=["POST"]),
    Route("/api/play_video", play_video, methods=["POST"]),
    # Async POST
    Route("/api/clip_video", clip_video, methods=["POST"]),
    Route("/api/concat_videos", concat_videos, methods=["POST"]),
    Route("/api/concat_videos_with_mp3", concat_videos_with_mp3, methods=["POST"]),
    Route("/api/concat_videos_with_mp3_video_first", concat_videos_with_mp3_video_first, methods=["POST"]),
    Route("/api/overlay_video", overlay_video, methods=["POST"]),
    Route("/api/scale_video", scale_video, methods=["POST"]),
    Route("/api/extract_frames_from_video", extract_frames_from_video, methods=["POST"]),
]
```

- [ ] **Step 3: Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/ffmpeg_mcp/http_routes.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 4: Commit**

```bash
git add src/ffmpeg_mcp/http_routes.py
git commit -m "feat(http-api): add all async POST endpoints and route table"
```

---

### Task 4: Modify server.py to mount REST routes

**Files:**
- Modify: `src/ffmpeg_mcp/server.py:580-611`

- [ ] **Step 1: Add route mounting in server.py main() function**

In `src/ffmpeg_mcp/server.py`, locate the SSE mode block (around line 581). After `app = mcp.sse_app()` and before the auth middleware setup, add the REST routes import and mounting.

Replace this section:

```python
    if transport == 'sse':
        try:
            # FastMCP.sse_app 是一个方法，调用 it 返回 Starlette 实例
            app = mcp.sse_app()
            
            # 添加 Token 认证中间件
```

With:

```python
    if transport == 'sse':
        try:
            # FastMCP.sse_app 是一个方法，调用 it 返回 Starlette 实例
            app = mcp.sse_app()

            # 挂载 REST API 路由
            from ffmpeg_mcp.http_routes import routes
            app.routes.extend(routes)
            print(f"REST API mounted: {len(routes)} endpoints under /api/")

            # 添加 Token 认证中间件
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('src/ffmpeg_mcp/server.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add src/ffmpeg_mcp/server.py
git commit -m "feat(http-api): mount REST routes in SSE mode startup"
```

---

### Task 5: Manual verification

- [ ] **Step 1: Install the package in development mode**

Run: `pip install -e .`
Expected: Successfully installed ffmpeg-mcp

- [ ] **Step 2: Start the server in SSE mode (without auth token for quick test)**

Run: `MCP_TRANSPORT=sse MCP_PORT=8032 python -m ffmpeg_mcp.server`
Expected output includes:
```
REST API mounted: 16 endpoints under /api/
Server running on transport: sse
SSE server starting with modified app on http://0.0.0.0:8032
```

- [ ] **Step 3: Test sync endpoints**

In another terminal:

```bash
# Health check
curl http://localhost:8032/health

# List output videos (empty list expected)
curl http://localhost:8032/api/list_output_videos

# List videos folder (empty list expected)
curl http://localhost:8032/api/list_videos_folder

# Get video info with missing param (400 expected)
curl http://localhost:8032/api/get_video_info

# Get task status with fake ID (404 expected)
curl http://localhost:8032/api/get_task_status/nonexistent
```

Expected responses:
- `/health`: 200 OK
- `/api/list_output_videos`: `{"code": 0, "data": [], "message": "success"}`
- `/api/list_videos_folder`: `{"code": 0, "data": [], "message": "success"}`
- `/api/get_video_info` (no param): `{"code": 1, "data": null, "message": "video_path is required"}` (HTTP 400)
- `/api/get_task_status/nonexistent`: `{"code": 1, "data": null, "message": "Task ID nonexistent not found"}` (HTTP 404)

- [ ] **Step 4: Test async endpoint (clip_video with a real video if available)**

If a test video exists in `/videos/` or `./videos/`:

```bash
# Submit async clip task
curl -X POST -H "Content-Type: application/json" \
  -d '{"video_path":"/videos/test.mp4","start":0,"duration":5}' \
  http://localhost:8032/api/clip_video

# Use the returned task_id to check status
curl http://localhost:8032/api/get_task_status/<task_id>
```

Expected:
- Submit: `{"code": 0, "data": {"task_id": "...", "status": "PENDING"}, "message": "Task submitted successfully"}`
- Status: eventually `{"code": 0, "data": {"status": "COMPLETED", ...}, "message": "success"}`

- [ ] **Step 5: Stop the server**

Press `Ctrl+C` to stop the server.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat(http-api): complete REST API implementation for all 16 MCP tools"
```
