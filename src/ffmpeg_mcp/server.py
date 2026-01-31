# server.py
import os
import sys
cur_path=os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, cur_path+"/..")
from typing import List
from mcp.server.fastmcp import FastMCP
import ffmpeg_mcp.cut_video as cut_video
import ffmpeg_mcp.utils as utils
from ffmpeg_mcp.task_manager import task_manager
import threading



# Create an MCP server
mcp = FastMCP("ffmpeg-mcp")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

class TokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):
        # 允许健康检查、根路径以及静态资源路径 (/videos, /output) 直接访问
        path = request.url.path
        if path in ["/health", "/"] or path.startswith("/videos/") or path.startswith("/output/"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"detail": "Missing or invalid Authorization header"}, 
                status_code=401
            )
        
        token = auth_header.split(" ")[1]
        if token != self.token:
            return JSONResponse(
                {"detail": "Unauthorized"}, 
                status_code=401
            )
        
        return await call_next(request)

def get_base_url():
    """获取服务器基础 URL，优先使用外部配置的 MCP_EXTERNAL_URL"""
    external_url = os.getenv('MCP_EXTERNAL_URL')
    if external_url:
        return external_url.rstrip('/')
        
    host = os.getenv('MCP_HOST', 'localhost')
    if host == '0.0.0.0':
        host = 'localhost' # 默认本地访问使用 localhost
    port = os.getenv('MCP_PORT', '8032')
    return f"http://{host}:{port}"

def get_file_url(file_path):
    """根据文件物理路径生成可访问的静态 URL"""
    if not file_path:
        return ""
    abs_path = os.path.abspath(file_path)
    base_url = get_base_url()
    
    if abs_path.startswith("/output"):
        rel_path = os.path.relpath(abs_path, "/output")
        return f"{base_url}/output/{rel_path}"
    elif abs_path.startswith("/videos"):
        rel_path = os.path.relpath(abs_path, "/videos")
        return f"{base_url}/videos/{rel_path}"
    
    # 回退逻辑：如果映射在当前目录
    cwd = os.getcwd()
    if abs_path.startswith(os.path.join(cwd, "output")):
        rel_path = os.path.relpath(abs_path, os.path.join(cwd, "output"))
        return f"{base_url}/output/{rel_path}"
    elif abs_path.startswith(os.path.join(cwd, "videos")):
        rel_path = os.path.relpath(abs_path, os.path.join(cwd, "videos"))
        return f"{base_url}/videos/{rel_path}"
        
    return ""
@mcp.tool()
def find_video_path(root_path, video_name):
    """
    可以查找视频文件路径，查找文件路径，递归查找精确匹配文件名的视频文件路径（支持带或不带扩展名）
    参数：
    root_path - 要搜索的根目录
    video_name - 视频文件名（可以带扩展名，但会忽略扩展名匹配）
    返回：
    首个匹配的视频文件完整路径，找不到时返回空字符串
    """
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
                    return os.path.join(root, file)
    return ""

@mcp.tool()
def clip_video(video_path, start=None, end=None,duration = None, output_path=None,time_out=300):
    """
    智能视频剪辑函数
    
    参数：
    video_path : str - 源视频文件路径
    start : int/float/str - 开始时间（支持秒数、MM:SS、HH:MM:SS格式,默认为视频开头,如果不传该参数，或者该参数为负数，从视频结尾往前剪辑）
    end : int/float/str - 结束时间（同上，默认为视频结尾）
    duration:  int/float/str - 裁剪时长，end和duration必须有一个
    output_path: str - 裁剪后视频输出路径，如果不传入，会有一个默认的输出路径
    time_out: int - 命令行执行超时时间，默认为300s
    返回：
    error - 错误码
    str - ffmpeg执行过程中所有日志
    str - 生成的剪辑文件路径
    示例：
    clip_video("input.mp4", "00:01:30", "02:30")
    """
    task_id = task_manager.create_task("clip_video", {
        "video_path": video_path, "start": start, "end": end, "duration": duration, "output_path": output_path
    })

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_video_path = utils.ensure_local_path(video_path)
            result = cut_video.clip_video_ffmpeg(local_video_path, start=start, end=end, duration=duration, output_path=output_path, time_out=time_out)
            if isinstance(result, (set, list, tuple)) and len(result) >= 3:
                status, log, path = list(result)
                task_manager.update_task(task_id, "COMPLETED", result={"status": status, "log": log, "path": path, "url": get_file_url(path)})
            else:
                task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return {"task_id": task_id, "status": "PENDING", "message": "Task submitted successfully"}

@mcp.tool()
def concat_videos(input_files: List[str], output_path: str = None, 
                      fast: bool = True):
    """
    使用FFmpeg拼接多个视频文件
    
    参数:
    input_files (List[str]): 输入视频文件路径列表
    output_path (str): 合并后的输出文件路径,如果不传入，会一个默认的输出路径
    fast (bool): 拼接方法，可选值："True"（默认，要求所有视频必须具有相同的编码格式、分辨率、帧率等参数）| "False(当不确定合并的视频编码格式、分辨率、帧率等参数是否相同的情况下，这个参数应该是False)"
    
    返回:
    执行日志
    
    注意:
    1. 当fast=True时，要求所有视频必须具有相同的编码格式、分辨率、帧率等参数
    2. 推荐视频文件使用相同编码参数，避免拼接失败
    3. 输出文件格式由output_path后缀决定（如.mp4/.mkv）
    """
    task_id = task_manager.create_task("concat_videos", {
        "input_files": input_files, "output_path": output_path, "fast": fast
    })

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_input_files = [utils.ensure_local_path(f) for f in input_files]
            result = cut_video.concat_videos(local_input_files, output_path, fast)
            if isinstance(result, (tuple, list)) and len(result) >= 2:
                code, log = result[:2]
                task_manager.update_task(task_id, "COMPLETED", result={"status": code, "log": log, "url": "Use list_output_videos to find the exact path if not specified"})
            else:
                task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return {"task_id": task_id, "status": "PENDING", "message": "Task submitted successfully"}

@mcp.tool()
def get_video_info(video_path: str):
    """
    获取视频信息，包括时长，帧率，codec等
    
    参数:
    video_path (str): 输入视频文件路径
    返回:
    视频详细信息
    """
    video_path = utils.ensure_local_path(video_path)
    return cut_video.get_video_info(video_path)

@mcp.tool()
def play_video(video_path, speed = 1, loop = 1):
    """
    使用 ffplay 播放视频文件，支持mkv,mp4,mov,avi,3gp等等

    参数：
    video_path(str) - 视频文件的路径。
    speed(float) - 浮点型,播放速率,建议0.5-2之间。
    loop(int) - 整形,是否循环播放,1:不循环,播放后就退出,0: 循环播放。
    """
    video_path = utils.ensure_local_path(video_path)
    return cut_video.video_play(video_path,speed=speed,loop=loop)


@mcp.tool()
def overlay_video(background_video, overlay_video, output_path: str = None, position: int = 1,  dx = 0, dy = 0):
    """
    两个视频叠加，注意不是拼接长度，而是画中画效果

    参数：
    background_video(str) - 背景视频文件的路径。
    overlay_video(str) - 前景视频文件路径。
    output_path(str) - 输出路径
    position(enum) - 相对位置，TopLeft=1: 左上角,TopCenter=2: 上居中, TopRight=3: 右上角 RightCenter=4: 右居中 BottomRight=5: 右下角 BottomCenter=6: 下居中 BottomLeft=7: 左下角 LeftCenter=8: 左居中 Center=9: 居中
    dx(int) - 整形,前景视频坐标x偏移值
    dy(int) - 整形,前景视频坐标y偏移值
    """
    task_id = task_manager.create_task("overlay_video", {
        "background_video": background_video, "overlay_video": overlay_video, "output_path": output_path, "position": position
    })

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_background = utils.ensure_local_path(background_video)
            local_overlay = utils.ensure_local_path(overlay_video)
            result = cut_video.overlay_video(local_background, local_overlay, output_path, position, dx, dy)
            if isinstance(result, (set, list, tuple)) and len(result) >= 3:
                status, log, path = list(result)
                task_manager.update_task(task_id, "COMPLETED", result={"status": status, "log": log, "path": path, "url": get_file_url(path)})
            else:
                task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return {"task_id": task_id, "status": "PENDING", "message": "Task submitted successfully"}
       
@mcp.tool()   
def scale_video(video_path, width, height,output_path: str = None):
    """
    视频缩放

    参数：
    width(int) - 目标宽度。
    height(int) - 目标高度。
    output_path(str) - 输出路径
    """ 
    task_id = task_manager.create_task("scale_video", {
        "video_path": video_path, "width": width, "height": height, "output_path": output_path
    })

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_video_path = utils.ensure_local_path(video_path)
            status, log, path = cut_video.scale_video(local_video_path, width, height, output_path)
            task_manager.update_task(task_id, "COMPLETED", result={"status": status, "log": log, "path": path, "url": get_file_url(path)})
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return {"task_id": task_id, "status": "PENDING", "message": "Task submitted successfully"}

@mcp.tool()   
def extract_frames_from_video(video_path,fps=0, output_folder=None, format=0, total_frames=0):
    """
    提取视频中的图像。

    参数：
    video_path(str) - 视频路径。
    fps(int) - 每多少秒抽一帧，如果传0，代表全部都抽,传1，代表每一秒抽1帧。
    output_folder(str) - 把图片输出到哪个目录
    format(int) - 抽取的图片格式，0：代表png 1:jpg 2:webp
    total_frames(int) - 最多抽取多少张，0代表不限制
    """ 
    task_id = task_manager.create_task("extract_frames", {
        "video_path": video_path, "fps": fps, "format": format, "total_frames": total_frames
    })

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_video_path = utils.ensure_local_path(video_path)
            result = cut_video.extract_frames_from_video(local_video_path, fps, output_folder, format, total_frames)
            task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return {"task_id": task_id, "status": "PENDING", "message": "Task submitted successfully"}

@mcp.tool()
def download_video(video_path: str, base64: bool = False):
    """
    根据路径获取视频文件。
    默认返回可访问的远程 URL。如果 base64=True，则返回 Base64 编码的二进制数据。
    
    参数：
    video_path : str - 视频文件路径（绝对路径）
    base64 : bool - 是否返回 Base64 编码的二进制数据，默认为 False
    """
    import base64 as b64
    import mimetypes
    
    video_path = utils.ensure_local_path(video_path)
    if not os.path.exists(video_path):
        return {"error": f"文件不存在: {video_path}"}
    
    # 基本安全检查：确保文件在允许的目录下
    abs_path = os.path.abspath(video_path)
    # 获取项目根目录和其他允许目录
    allowed_dirs = ["/videos", "/output", os.getcwd()]
    is_allowed = False
    for d in allowed_dirs:
        if abs_path.startswith(os.path.abspath(d)):
            is_allowed = True
            break
    
    if not is_allowed:
        return {"error": "权限拒绝：只能访问 /videos 或 /output 目录下的文件"}
        
    file_size = os.path.getsize(abs_path)
    mime_type, _ = mimetypes.guess_type(abs_path)
    
    result = {
        "filename": os.path.basename(abs_path),
        "mime_type": mime_type or "application/octet-stream",
        "size": file_size,
        "path": abs_path,
        "url": get_file_url(abs_path)
    }

    if base64:
        # 文件大小检查 (暂定限制 200MB，仅在 Base64 模式下生效)
        if file_size > 200 * 1024 * 1024:
            return {"error": f"文件太大 ({file_size / (1024 * 1024):.2f}MB)，超过 200MB 限制。建议直接通过 URL 访问。"}
            
        try:
            with open(abs_path, "rb") as f:
                content = f.read()
                result["base64_data"] = b64.b64encode(content).decode("utf-8")
        except Exception as e:
            return {"error": f"读取文件失败: {str(e)}"}
            
    return result

@mcp.tool()
def get_task_status(task_id: str):
    """
    查询异步任务的状态。
    
    参数：
    task_id (str): 任务 ID
    """
    status = task_manager.get_task_status(task_id)
    if status:
        return status
    return {"error": f"Task ID {task_id} not found"}

@mcp.tool()
def list_output_videos():
    """
    列出 /output 目录下的所有视频文件。
    
    返回：
    List[str] - 视频文件的绝对路径列表
    """
    VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.ts'}
    output_dir = "/output"
    if not os.path.exists(output_dir):
        output_dir = os.path.join(os.getcwd(), "output")
        if not os.path.exists(output_dir):
            return []
            
    video_files = []
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if os.path.splitext(file)[1].lower() in VIDEO_EXTS:
                video_files.append(os.path.abspath(os.path.join(root, file)))
    return video_files

@mcp.tool()
def list_videos_folder():
    """
    列出 /videos 目录下的所有视频文件。
    该目录通常包含下载的远程视频或用户上传的视频。
    
    返回：
    List[str] - 视频文件的绝对路径列表
    """
    VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.ts'}
    
    # Logic consistent with utils.py ensuring we look at the right 'videos' folder
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_file_dir, "../../"))
    videos_dir = "/videos" if os.path.exists("/videos") else os.path.join(project_root, "videos")

    if not os.path.exists(videos_dir):
        return []
            
    video_files = []
    for root, dirs, files in os.walk(videos_dir):
        for file in files:
            if os.path.splitext(file)[1].lower() in VIDEO_EXTS:
                video_files.append(os.path.abspath(os.path.join(root, file)))
    return video_files

@mcp.tool()
def delete_videos(video_paths: List[str]):
    """
    根据绝对路径批量删除视频文件。
    仅限删除 /videos 或 /output 目录下的文件。
    
    参数：
    video_paths : List[str] - 要删除的文件路径列表
    
    返回：
    dict - 包含成功和失败信息的汇总
    """
    results = {"success": [], "failed": []}
    allowed_dirs = ["/videos", "/output", os.getcwd()]
    abs_allowed_dirs = [os.path.abspath(d) for d in allowed_dirs]

    for path in video_paths:
        try:
            abs_path = os.path.abspath(path)
            
            # 安全检查
            is_allowed = False
            for allowed in abs_allowed_dirs:
                if abs_path.startswith(allowed):
                    is_allowed = True
                    break
            
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
            
    return results

def main():
    import os
    from starlette.staticfiles import StaticFiles
    
    # 支持通过环境变量配置传输方式和端口
    transport = os.getenv('MCP_TRANSPORT', 'stdio')
    host = os.getenv('MCP_HOST', '0.0.0.0')
    port = int(os.getenv('MCP_PORT', '8032'))

    # 针对较新版本 MCP SDK 的安全配置 (DNS Rebinding Protection)
    # 必须在调用 mcp.sse_app() 之前配置，因为 middleware 在创建时就生成了
    if hasattr(mcp, "settings"):
        try:
            security = getattr(mcp.settings, "transport_security", None)
            if security:
                security.enable_dns_rebinding_protection = False
                security.allowed_hosts = ["*"]
                print("Configured security: DNS rebinding protection disabled, allowed_hosts=['*']")
        except Exception as e:
            print(f"Note: Could not configure transport security: {e}")

    # 针对 SSE 模式，我们需要手动处理 app 和挂载
    app = None
    if transport == 'sse':
        try:
            # FastMCP.sse_app 是一个方法，调用 it 返回 Starlette 实例
            app = mcp.sse_app()
            
            # 添加 Token 认证中间件
            auth_token = os.getenv('MCP_AUTH_TOKEN')
            if auth_token:
                app.add_middleware(TokenAuthMiddleware, token=auth_token)
                print("Token authentication enabled.")
            else:
                print("Warning: MCP_AUTH_TOKEN not set. Running without authentication.")

            # 确保目录存在
            output_abs = os.path.abspath("output")
            videos_abs = os.path.abspath("videos")
            os.makedirs(output_abs, exist_ok=True)
            os.makedirs(videos_abs, exist_ok=True)
            
            # 优先使用根目录下的目录 (Docker 卷挂载)，否则使用当前目录下的
            final_output = "/output" if os.path.exists("/output") else output_abs
            final_videos = "/videos" if os.path.exists("/videos") else videos_abs
            
            app.mount("/output", StaticFiles(directory=final_output), name="output")
            app.mount("/videos", StaticFiles(directory=final_videos), name="videos")
                
            print(f"Static files mounted: {final_output} -> /output, {final_videos} -> /videos")
        except Exception as e:
            print(f"Failed to setup SSE app or mount static files: {e}")
            # 如果创建失败，回退到让 mcp.run 自己去创建（虽然可能没挂载成功）
            app = None

    print(f"Server running on transport: {transport}")
    if transport == 'sse':
        import uvicorn
        if app:
            print(f"SSE server starting with modified app on http://{host}:{port}")
            uvicorn.run(app, host=host, port=port)
        else:
            print(f"SSE server fallback to mcp.run on http://{host}:{port}")
            mcp.run(transport='sse')
    else:
        print("STDIO mode")
        mcp.run(transport='stdio')

if __name__ == "__main__":
    main()