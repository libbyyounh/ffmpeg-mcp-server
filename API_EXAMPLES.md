# FFmpeg MCP API Usage Examples

This document provides examples of how to call the FFmpeg MCP server via HTTP when running in SSE (Server-Sent Events) mode.

## Prerequisites

- Server running in SSE mode (via Docker or with `MCP_TRANSPORT=sse`)
- Server accessible at `http://localhost:8032` (or your configured host/port)

## API Endpoint

The MCP server exposes its tools through the standard MCP protocol over HTTP.

Base URL: `http://localhost:8032`

## URL-based Inputs

The server now supports processing videos directly from remote URLs (HTTP/HTTPS). When using a URL and no `output_path` is specified, the result is automatically saved to the `/output` directory.


## Static File Serving

When running in **SSE mode**, the server acts as a web server and provides direct URL access to the video folders:
- `/output/` -> `http://localhost:8032/output/`
- `/videos/` -> `http://localhost:8032/videos/`

**Example:**
If you process a video and get the path `/output/my_clip.mp4`, you can access it directly at:
`http://localhost:8032/output/my_clip.mp4`

> [!TIP]
> **Real Environment Config**: In a production or remote environment, set the `MCP_EXTERNAL_URL` environment variable (e.g., `http://1.2.3.4:8032`) to ensure returned URLs use the correct public address instead of `localhost`.

### 1. Find Video Path

Search for a video file by name in a directory.

```bash
# Using MCP client
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "find_video_path",
      "arguments": {
        "root_path": "/videos",
        "video_name": "my_video.mp4"
      }
    }
  }'
```

### 2. Get Video Info

Get detailed information about a video file.

```bash
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "get_video_info",
      "arguments": {
        "video_path": "/videos/my_video.mp4"
      }
    }
  }'
  }'

# Get info from a remote URL
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "get_video_info",
      "arguments": {
        "video_path": "https://www.w3schools.com/html/mov_bbb.mp4"
      }
    }
  }'
```

**Response example:**
```json
{
  "duration": "120.5",
  "fps": "30.0",
  "codec": "h264",
  "width": 1920,
  "height": 1080
}
```

### 3. Clip Video

Extract a segment from a video.

```bash
# Clip from 00:01:30 to 00:02:30
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "clip_video",
      "arguments": {
        "video_path": "/videos/input.mp4",
        "start": "00:01:30",
        "end": "00:02:30",
        "output_path": "/output/clipped.mp4"
      }
    }
  }'

# Clip last 10 seconds using duration
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "clip_video",
      "arguments": {
        "video_path": "/videos/input.mp4",
        "start": -10,
        "duration": 10,
        "output_path": "/output/last_10s.mp4"
      }
    }
  }'
  }'

# Clip from a remote URL
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "clip_video",
      "arguments": {
        "video_path": "https://www.w3schools.com/html/mov_bbb.mp4",
        "start": "00:00:01",
        "duration": 5
      }
    }
  }'
```

### 4. Concatenate Videos

Merge multiple video files into one.

```bash
# Fast mode (requires same codec/resolution/fps)
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "concat_videos",
      "arguments": {
        "input_files": [
          "/videos/part1.mp4",
          "/videos/part2.mp4",
          "/videos/part3.mp4"
        ],
        "output_path": "/output/merged.mp4",
        "fast": true
      }
    }
  }'

# Safe mode (re-encodes if necessary)
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "concat_videos",
      "arguments": {
        "input_files": [
          "/videos/video1.mp4",
          "/videos/video2.avi"
        ],
        "output_path": "/output/merged.mp4",
        "fast": false
      }
    }
  }'

# Concatenate remote URLs
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "concat_videos",
      "arguments": {
        "input_files": [
          "https://www.w3schools.com/html/mov_bbb.mp4",
          "https://www.w3schools.com/html/movie.mp4"
        ],
        "fast": false
      }
    }
  }'
```

### 5. Overlay Video (Picture-in-Picture)

Overlay one video on top of another.

```bash
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "overlay_video",
      "arguments": {
        "background_video": "/videos/background.mp4",
        "overlay_video": "/videos/overlay.mp4",
        "output_path": "/output/pip.mp4",
        "position": 1,
        "dx": 10,
        "dy": 10
      }
    }
  }'
```

**Position values:**
- 1: TopLeft (左上角)
- 2: TopCenter (上居中)
- 3: TopRight (右上角)
- 4: RightCenter (右居中)
- 5: BottomRight (右下角)
- 6: BottomCenter (下居中)
- 7: BottomLeft (左下角)
- 8: LeftCenter (左居中)
- 9: Center (居中)

### 6. Scale Video

Resize a video to specific dimensions.

```bash
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "scale_video",
      "arguments": {
        "video_path": "/videos/input.mp4",
        "width": "1280",
        "height": "720",
        "output_path": "/output/scaled.mp4"
      }
    }
  }'

# Keep aspect ratio (use -2 for auto calculation)
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "scale_video",
      "arguments": {
        "video_path": "/videos/input.mp4",
        "width": "1280",
        "height": "-2",
        "output_path": "/output/scaled_aspect.mp4"
      }
    }
  }'
```

### 7. Extract Frames from Video

Extract images from a video at specified intervals.

```bash
# Extract 1 frame per second as PNG
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "extract_frames_from_video",
      "arguments": {
        "video_path": "/videos/input.mp4",
        "fps": 1,
        "output_folder": "/output/frames",
        "format": 0,
        "total_frames": 0
      }
    }
  }'

# Extract first 10 frames as JPG
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "extract_frames_from_video",
      "arguments": {
        "video_path": "/videos/input.mp4",
        "fps": 0,
        "output_folder": "/output/frames",
        "format": 1,
        "total_frames": 10
      }
    }
  }'
```

**Format values:**
- 0: PNG
- 1: JPG
- 2: WEBP

### 8. Play Video

Play a video file (note: requires display, mainly for testing).

```bash
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "play_video",
      "arguments": {
        "video_path": "/videos/input.mp4",
        "speed": 1.0,
        "loop": 1
      }
    }
  }'
```

### 9. Retrieve Video (Download)

Retrieve processed video information. By default, it returns a URL for direct access. Use `base64: true` to get the binary content.

```bash
# Get URL only (default)
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "download_video",
      "arguments": {
        "video_path": "/output/result.mp4"
      }
    }
  }'

# Get Base64 binary data
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "download_video",
      "arguments": {
        "video_path": "/output/result.mp4",
        "base64": true
      }
    }
  }'
```

**How to decode Base64 back to a video file:**

**Python:**
```python
import base64

# Assume 'result' is the JSON response from the server
base64_data = result['result']['base64_data']
with open("downloaded_video.mp4", "wb") as f:
    f.write(base64.b64decode(base64_data))
```

**Node.js:**
```javascript
const Buffer = require('buffer').Buffer;
const base64Data = result.result.base64_data;
const buffer = Buffer.from(base64Data, 'base64');
fs.writeFileSync('downloaded_video.mp4', buffer);
```

### 10. List Output Videos

List all video files in the `/output` directory.

```bash
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "list_output_videos",
      "arguments": {}
    }
  }'
```

### 11. Delete Videos (Batch)

Batch delete video files from allowed directories (`/videos` or `/output`).

```bash
curl -X POST http://localhost:8032/message \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "delete_videos",
      "arguments": {
        "video_paths": [
          "/output/clip_1.mp4",
          "/output/test_video.mp4"
        ]
      }
    }
  }'
```

## Python Client Example

```python
import requests
import json

class FFmpegMCPClient:
    def __init__(self, base_url="http://localhost:8032"):
        self.base_url = base_url
        self.endpoint = f"{base_url}/message"

    def call_tool(self, tool_name, arguments):
        payload = {
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        response = requests.post(
            self.endpoint,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )

        return response.json()

    def get_video_info(self, video_path):
        return self.call_tool("get_video_info", {
            "video_path": video_path
        })

    def clip_video(self, video_path, start, end=None, duration=None, output_path=None):
        args = {
            "video_path": video_path,
            "start": start
        }
        if end:
            args["end"] = end
        if duration:
            args["duration"] = duration
        if output_path:
            args["output_path"] = output_path

        return self.call_tool("clip_video", args)

    def concat_videos(self, input_files, output_path=None, fast=True):
        return self.call_tool("concat_videos", {
            "input_files": input_files,
            "output_path": output_path,
            "fast": fast
        })

# Usage
client = FFmpegMCPClient()

# Get video info
info = client.get_video_info("/videos/my_video.mp4")
print(info)

# Clip video
result = client.clip_video(
    video_path="/videos/input.mp4",
    start="00:01:00",
    duration=30,
    output_path="/output/clip.mp4"
)
print(result)

# Merge videos
result = client.concat_videos(
    input_files=["/videos/part1.mp4", "/videos/part2.mp4"],
    output_path="/output/merged.mp4"
)
print(result)
```

## Node.js Client Example

```javascript
const axios = require('axios');

class FFmpegMCPClient {
  constructor(baseUrl = 'http://localhost:8032') {
    this.baseUrl = baseUrl;
    this.endpoint = `${baseUrl}/message`;
  }

  async callTool(toolName, arguments) {
    const payload = {
      method: 'tools/call',
      params: {
        name: toolName,
        arguments: arguments
      }
    };

    const response = await axios.post(this.endpoint, payload, {
      headers: { 'Content-Type': 'application/json' }
    });

    return response.data;
  }

  async getVideoInfo(videoPath) {
    return this.callTool('get_video_info', {
      video_path: videoPath
    });
  }

  async clipVideo(videoPath, start, options = {}) {
    const args = {
      video_path: videoPath,
      start: start,
      ...options
    };

    return this.callTool('clip_video', args);
  }

  async concatVideos(inputFiles, outputPath = null, fast = true) {
    return this.callTool('concat_videos', {
      input_files: inputFiles,
      output_path: outputPath,
      fast: fast
    });
  }
}

// Usage
(async () => {
  const client = new FFmpegMCPClient();

  // Get video info
  const info = await client.getVideoInfo('/videos/my_video.mp4');
  console.log(info);

  // Clip video
  const result = await client.clipVideo('/videos/input.mp4', '00:01:00', {
    duration: 30,
    output_path: '/output/clip.mp4'
  });
  console.log(result);

  // Merge videos
  const merged = await client.concatVideos(
    ['/videos/part1.mp4', '/videos/part2.mp4'],
    '/output/merged.mp4'
  );
  console.log(merged);
})();
```

## Integration with AI Models

AI models can call these tools by making HTTP requests to the MCP server. The model should:

1. Understand the available tools and their parameters
2. Construct proper JSON payloads
3. Handle responses and errors
4. Use absolute paths within the Docker container (e.g., `/videos/`, `/output/`)

Example prompt for AI model:

```
You have access to an FFmpeg MCP server at http://localhost:8032 with the following tools:
- find_video_path: Find video files
- get_video_info: Get video metadata
- clip_video: Extract video segments
- concat_videos: Merge videos
- overlay_video: Create picture-in-picture
- scale_video: Resize videos
- extract_frames_from_video: Export frames as images
- play_video: Play videos
- download_video: Retrieve video content as Base64
- list_output_videos: List files in the output directory
- delete_videos: Batch delete video files

Videos are located in /videos/ and outputs should go to /output/
```

## Error Handling

Always check the response for errors:

```python
response = client.call_tool("clip_video", {...})
if "error" in response:
    print(f"Error: {response['error']}")
else:
    print(f"Success: {response}")
```

## Notes

- All file paths should be absolute paths within the Docker container
- Use `/videos/` for input files (mapped to `./videos` on host)
- Use `/output/` for output files (mapped to `./output` on host)
- Large video operations may take time; consider implementing timeout handling
- The server runs as a single instance; concurrent requests are handled sequentially
