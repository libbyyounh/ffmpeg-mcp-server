# FFmpeg-MCP
Using ffmpeg command line to achieve an mcp server, can be very convenient, through the dialogue to achieve the local video search, tailoring, stitching, playback and other functions

<a href="https://glama.ai/mcp/servers/@video-creator/ffmpeg-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@video-creator/ffmpeg-mcp/badge" alt="FFmpeg-Server MCP server" />
</a>

## Support Tools
The server implements the following tools: <br/>
- `find_video_path`
  The parameters are directory and file name, file name can be complete, or is not suffixed, recursive search in the directory, return the full path
- `get_video_info`
  The parameters are video path, return the video info, linkes duration/fps/codec/width/height.
- `clip_video`
  The parameter is the file path, start time, end time or duration, and returns the trimmed file path
- `concat_videos`
  The parameters are the list of files, the output path, and if the video elements in the list of files, such as width, height, frame rate, etc., are consistent, quick mode synthesis is automatically used
- `play_video`
  Play video/audio with ffplay, support many format, like mov/mp4/avi/mkv/3gp, video_path: video path speed: play rate loop: play count
- `overlay_video`
  Two video overlay. <br/>
  background_video: backgroud video path <br/>
  overlay_video: front video path <br/>
  output_path: output video path<br/>
  position: relative location<br/>
  dx: x offset<br/>
  dy: y offset<br/>
- `scale_video`
  Video scale. <br/>
  video_path: in video path <br/>
  width: out video width, -2 keep aspect <br/>
  height: out video height, -2 keep aspect <br/>
  output_path: output video path <br/>
- `extract_frames_from_video`
  Extract images from a video.<br/>
  Parameters: <br/>
  video_path (str): The path to the video.<br/>
  fps (int): Extract one frame every specified number of seconds. If set to 0, extract all frames; if set to 1, extract one frame per second.<br/>
  output_folder (str): The directory where the images will be saved.<br/>
  format (int): The format of the extracted images; 0: PNG, 1: JPG, 2: WEBP.<br/>
  total_frames (int): The maximum number of frames to extract. If set to 0, there is no limit<br/>
<br/>
More features are coming

## Installation procedure
1. Download project
```
git clone  https://github.com/video-creator/ffmpeg-mcp.git
cd ffmpeg-mcp
uv sync
```

2. Configuration in Cline
```
{
  "mcpServers": {
    "ffmpeg-mcp": {
      "autoApprove": [],
      "disabled": false,
      "timeout": 60,
      "command": "uv",
      "args": [
        "--directory",
        "/Users/xxx/Downloads/ffmpeg-mcp",
        "run",
        "ffmpeg-mcp"
      ],
      "transportType": "stdio"
    }
  }
}
```
Note: the value:`/Users/XXX/Downloads/ffmpeg` in args  need to replace the actual download ffmpeg-mcp directory

## Supported platforms
- macOS (ARM64 / x86_64)
- Linux (via Docker)
- Windows (via Docker)

## Docker Deployment (Recommended for HTTP/API Access)

### Quick Start with Docker Compose

1. Clone the repository
```bash
git clone https://github.com/video-creator/ffmpeg-mcp.git
cd ffmpeg-mcp
```

2. Create directories for videos
```bash
mkdir -p videos output
```

3. Start the server
```bash
docker-compose up -d
```

The server will be available at `http://localhost:8032`

### Manual Docker Build

```bash
# Build the image
docker build -t ffmpeg-mcp:latest .

# Run the container
docker run -d \
  --name ffmpeg-mcp-server \
  -p 8032:8032 \
  -v $(pwd)/videos:/videos \
  -v $(pwd)/output:/output \
  -e MCP_TRANSPORT=sse \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8032 \
  ffmpeg-mcp:latest
```

### Configuration

Copy `.env.example` to `.env` and modify settings:

```bash
cp .env.example .env
```

Available environment variables:
- `MCP_TRANSPORT`: `stdio` (default) or `sse` (for HTTP server)
- `MCP_HOST`: Server host (default: `0.0.0.0`)
- `MCP_PORT`: SSE 端口 (默认 8032)
- `MCP_AUTH_TOKEN`: 设置后启用 Token 认证，客户端需带上 `Authorization: Bearer <token>`
- `MCP_EXTERNAL_URL`: 服务器的基础公开 URL，用于工具返回文件地址

### Token 认证使用方法
如果您在 `.env` 中设置了 `MCP_AUTH_TOKEN`，所有请求（包括视频播放）都需要携带认证头。

**cURL 示例**:
```bash
curl -H "Authorization: Bearer your-token" http://localhost:8032/sse
```

**Claude Desktop 配置**:
MCP 目前的 SSE 规范尚未完全标准化认证字段，如果您的客户端不支持自定义 Header，建议通过前置代理（如 Nginx）处理或暂时留空此项。

### Using the HTTP API

When running in SSE mode (Docker), the MCP server exposes an HTTP endpoint that can be called by AI models and other clients. See `API_EXAMPLES.md` for detailed usage examples.

### Health Check

```bash
curl http://localhost:8032/
```

### View Logs

```bash
docker-compose logs -f
```

### Stop the Server

```bash
docker-compose down
```