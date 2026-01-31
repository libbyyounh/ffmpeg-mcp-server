import os
import requests
import hashlib
import tempfile
import zipfile

def convert_to_seconds(time_input):
    """
    将不同格式的时间表示转换为秒数。

    参数:
        time_input: 可以是以下格式之一：
            - str: 格式为 'HH:MM:SS', 'MM:SS' 或 'SS'.
            - tuple: 格式为 (HH, MM, SS).
            - int or float: 直接表示秒数.

    返回:
        float: 转换后的秒数表示。

    异常:
        ValueError: 如果输入格式不被识别。
    """
    if isinstance(time_input, (int, float)):
        return float(time_input)

    if isinstance(time_input, str):
        parts = time_input.split(':')
        parts = [float(p) for p in parts]
        if len(parts) == 3:
            hours, minutes, seconds = parts
        elif len(parts) == 2:
            hours = 0
            minutes, seconds = parts
        elif len(parts) == 1:
            hours = 0
            minutes = 0
            seconds = parts[0]
        else:
            raise ValueError(f"Unrecognized time string format: {time_input}")
        return hours * 3600 + minutes * 60 + seconds

    if isinstance(time_input, tuple):
        if len(time_input) == 3:
            hours, minutes, seconds = time_input
        elif len(time_input) == 2:
            hours = 0
            minutes, seconds = time_input
        elif len(time_input) == 1:
            hours = 0
            minutes = 0
            seconds = time_input[0]
        else:
            raise ValueError(f"Unrecognized time tuple format: {time_input}")
        return hours * 3600 + minutes * 60 + seconds

    raise ValueError(f"Unrecognized time input type: {type(time_input)}")

def create_temp_file() -> str:
    """
    创建临时文件并返回其路径。
    
    返回:
    str: 临时文件的路径
    """
    # 使用NamedTemporaryFile创建临时文件
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    # 获取临时文件的路径
    temp_file_path = temp_file.name
    # 关闭文件，以便其他进程或程序可以使用它
    temp_file.close()
    return temp_file_path

def unzip_to_current_directory(zip_file_path):
    # 获取当前目录路径
    current_directory = os.getcwd()

    # 打开ZIP文件
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        # 解压缩到当前目录
        zip_ref.extractall(current_directory)

def is_url(path: str) -> bool:
    """
    检查路径是否为 HTTP/HTTPS URL
    """
    if not isinstance(path, str):
        return False
    return path.lower().startswith(('http://', 'https://'))

def get_default_output_path(input_path: str, suffix: str = "_output") -> str:
    """
    为输入生成默认的输出路径。
    如果是 URL 或不在当前目录下的文件，默认保存到 /output 目录。
    """
    from urllib.parse import urlparse
    
    # 默认输出目录
    output_dir = "/output" if os.path.exists("/output") else os.getcwd()
    
    if is_url(input_path):
        # 从 URL 获取文件名
        parsed_url = urlparse(input_path)
        filename = os.path.basename(parsed_url.path)
        if not filename:
            filename = "downloaded_video.mp4"
    else:
        filename = os.path.basename(input_path)
    
    base, ext = os.path.splitext(filename)
    if not ext:
        ext = ".mp4"
        
    return os.path.join(output_dir, f"{base}{suffix}{ext}")

def ensure_local_path(path_or_url: str) -> str:
    """
    确保返回一个本地物理路径。
    如果是 HTTP URL，则下载到本地 /videos 目录并返回下载后的路径。
    """
    if not is_url(path_or_url):
        return os.path.abspath(path_or_url)
    
    # 远程 URL 下载逻辑
    # 确定下载目录
    videos_dir = "/videos" if os.path.exists("/videos") else os.path.join(os.getcwd(), "videos")
    os.makedirs(videos_dir, exist_ok=True)
    
    # 根据 URL 生成唯一文件名，避免冲突和重复下载
    url_hash = hashlib.md5(path_or_url.encode('utf-8')).hexdigest()
    # 尝试保留原始扩展名
    from urllib.parse import urlparse
    parsed = urlparse(path_or_url)
    # 提取扩展名
    ext = os.path.splitext(parsed.path)[1] or ".mp4"
    if '?' in ext:
        ext = ext.split('?')[0]
        
    local_filename = f"remote_{url_hash}{ext}"
    local_path = os.path.join(videos_dir, local_filename)
    
    # 如果已存在，直接返回
    if os.path.exists(local_path):
        print(f"Using cached remote video: {local_path}")
        return local_path
        
    # 下载
    print(f"Downloading remote video: {path_or_url} -> {local_path}")
    try:
        response = requests.get(path_or_url, stream=True, timeout=120)
        response.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"Download complete: {local_path}")
        return local_path
    except Exception as e:
        print(f"Download failed for {path_or_url}: {e}")
        # 如果下载失败，抛出异常以便上层捕获
        raise ValueError(f"无法下载远程视频: {path_or_url}. 错误: {str(e)}")