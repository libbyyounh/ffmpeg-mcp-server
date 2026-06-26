# Design: concat_videos_with_mp3_video_first MCP Tool

## Overview

Add a new MCP tool `concat_videos_with_mp3_video_first` — the reverse of `concat_videos_with_mp3`. Video total duration is the authority. If total video exceeds audio duration, return an error. Otherwise, trim the audio to match the video total duration.

## Difference from `concat_videos_with_mp3`

| Aspect | `concat_videos_with_mp3` | `concat_videos_with_mp3_video_first` |
|--------|--------------------------|--------------------------------------|
| Authority duration | Audio | Video |
| Video > Audio | Trim/loop videos to match audio | **Error: "音频长度不足"** |
| Video < Audio | Loop videos to match audio | Trim audio to match video total |
| Output duration | = audio duration | = total video duration |

## Tool Interface

```python
@mcp.tool()
def concat_videos_with_mp3_video_first(
    video_paths: List[str],        # Input video paths (supports remote URLs)
    audio_path: str,               # MP3 audio path
    output_path: str = None,       # Output path (auto-generated if omitted)
    mute_video_audio: bool = True, # True = mute video audio, keep MP3 only (default)
    order: str = "sequence"        # sequence (default) | random | reverse
) -> dict
```

Parameters are identical to `concat_videos_with_mp3`.

## Processing Flow

```
Step 1: Get durations
  - ffprobe audio_path → audio_duration
  - ffprobe each video → video_durations[]

Step 2: Reorder videos by `order` parameter

Step 3: Calculate total video duration
  - Sum all video durations
  - If total_video_duration > audio_duration → return (-1, "音频长度不足：视频总时长 X.XXs > 音频时长 Y.YYs", "")

Step 4: Concatenate all videos (no trim/loop needed)
  - ffmpeg -f concat -safe 0 -i filelist.txt -c copy merged.mp4

Step 5: Replace/mix audio, trimmed to video total duration
  - mute_video_audio=True:
    ffmpeg -i merged.mp4 -i bgm.mp3 -map 0:v -map 1:a -t {total_video_duration} -y output.mp4
  - mute_video_audio=False:
    ffmpeg -i merged.mp4 -i bgm.mp3
    -filter_complex "[0:a][1:a]amix=inputs=2:weights='1 3'[outa]"
    -map 0:v -map "[outa]" -t {total_video_duration} -y output.mp4

Step 6: Cleanup temp files
```

## Code Changes

### `cut_video.py`

Add `concat_videos_with_mp3_video_first()` function — similar to `concat_videos_with_mp3` but with video-first semantics.

### `server.py`

Add `concat_videos_with_mp3_video_first` MCP tool registration (async pattern).
