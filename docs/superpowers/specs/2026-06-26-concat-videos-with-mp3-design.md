# Design: concat_videos_with_mp3 MCP Tool

## Overview

Add a new MCP tool `concat_videos_with_mp3` that concatenates one or more videos to match the duration of a given MP3 audio file, then outputs the merged video with the MP3 as the audio track. Videos that are too short are looped from the source list; videos that exceed the target duration are trimmed.

## Tool Interface

```python
@mcp.tool()
def concat_videos_with_mp3(
    video_paths: List[str],        # Input video paths (supports remote URLs)
    audio_path: str,               # MP3 audio path (determines output duration)
    output_path: str = None,       # Output path (auto-generated if omitted)
    mute_video_audio: bool = True, # True = mute video audio, keep MP3 only (default)
    order: str = "sequence"        # sequence (default) | random | reverse
) -> dict
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `video_paths` | `List[str]` | required | One or more video file paths. Supports HTTP/HTTPS URLs. |
| `audio_path` | `str` | required | MP3 audio file path. Determines the output video duration. |
| `output_path` | `str` | `None` | Output file path. Auto-generated via `utils.get_default_output_path` if omitted. |
| `mute_video_audio` | `bool` | `True` | `True` = only keep MP3 audio (video original audio is muted). `False` = mix video audio with MP3. |
| `order` | `str` | `"sequence"` | Video concatenation order: `sequence` (array order), `random` (shuffle), `reverse` (reverse array). |

### Return

Async task pattern (same as `overlay_video`, `clip_video`, etc.):

```json
{"task_id": "xxx", "status": "PENDING", "message": "Task submitted successfully"}
```

Poll via `get_task_status(task_id)` for final result.

## Processing Flow (Approach A: Step-by-Step)

```
Step 1: Get durations
  - ffprobe audio_path → audio_duration (target duration)
  - ffprobe each video → video_durations[]

Step 2: Reorder videos by `order` parameter
  - sequence: keep original array order
  - random:   shuffle with random.sample
  - reverse:  reverse the array

Step 3: Build clip/loop plan
  Loop through reordered videos, accumulating total duration:
  - If video remaining ≤ needed duration: use entire video, accumulate
  - If video remaining > needed duration: trim to needed duration
  - When a video is exhausted but total < audio_duration:
    restart from the beginning of the video list (source list loop)

  Produces a list of (video_path, start, duration) segments.

Step 4: Process each segment with FFmpeg
  For each segment:
  - If trimming needed: ffmpeg -i video -ss start -t duration -c copy segment.mp4
  - If full video used: symlink or copy to temp
  - If loop needed: ffmpeg -stream_loop N -i video -t duration segment.mp4

Step 5: Concatenate all segments
  ffmpeg -f concat -safe 0 -i filelist.txt -c copy merged.mp4

Step 6: Replace audio
  - mute_video_audio=True:
    ffmpeg -i merged.mp4 -i bgm.mp3 -map 0:v -map 1:a -shortest output.mp4
  - mute_video_audio=False:
    ffmpeg -i merged.mp4 -i bgm.mp3
    -filter_complex "[0:a][1:a]amix=inputs=2:weights='1 3'[outa]"
    -map 0:v -map "[outa]" -shortest output.mp4

Step 7: Cleanup temp files
```

## Code Changes

### `cut_video.py`

Add two functions:

1. `get_audio_duration(audio_path: str) -> float`
   - Uses `ffprobe -v error -show_entries format=duration -of csv=p=0` to get audio duration in seconds.

2. `concat_videos_with_mp3(video_paths, audio_path, output_path, mute_video_audio, order) -> tuple`
   - Core logic implementing the processing flow above.
   - Returns `(status_code, log, output_path)` matching existing convention.

### `server.py`

Add new tool registration:

```python
@mcp.tool()
def concat_videos_with_mp3(video_paths: List[str], audio_path: str,
                            output_path: str = None, mute_video_audio: bool = True,
                            order: str = "sequence"):
    """..."""
    task_id = task_manager.create_task("concat_videos_with_mp3", {...})

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_videos = [utils.ensure_local_path(v) for v in video_paths]
            local_audio = utils.ensure_local_path(audio_path)
            status, log, path = cut_video.concat_videos_with_mp3(
                local_videos, local_audio, output_path, mute_video_audio, order
            )
            task_manager.update_task(task_id, "COMPLETED",
                result={"status": status, "log": log, "path": path, "url": get_file_url(path)})
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return {"task_id": task_id, "status": "PENDING", "message": "Task submitted successfully"}
```

### `utils.py`

No changes needed. Reuse existing `ensure_local_path`, `create_temp_file`, `get_default_output_path`.

## Error Handling

| Scenario | Handling |
|----------|----------|
| Audio file not found | Raise `FileNotFoundError` |
| All video files not found | Raise `FileNotFoundError` |
| ffprobe fails to get duration | Task FAILED with ffprobe error message |
| Video has no video stream (audio-only) | Skip that video, continue with next |
| Concat fails (codec mismatch) | Retry with re-encode mode (`-c:v libx264 -c:a aac`) |
| Temp file cleanup | `finally` block removes all temp files |

## Temporary File Strategy

- All temp files go to `tempfile.mkdtemp()` directory
- Naming: `segment_000.mp4`, `segment_001.mp4`, ..., `filelist.txt`
- `finally` block: `shutil.rmtree(temp_dir)` to clean up regardless of success/failure

## Example Usage

```
Agent: concat_videos_with_mp3(
  video_paths=["intro.mp4", "main.mp4", "outro.mp4"],
  audio_path="background_music.mp3",
  order="sequence",
  mute_video_audio=True
)
→ Processes: intro(10s) + main(60s) + outro(15s) = 85s
→ If music is 120s: loops back to use intro again (trimmed to 35s)
→ Output: merged video with MP3 audio, 120s total
```
