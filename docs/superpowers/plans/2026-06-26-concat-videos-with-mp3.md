# concat_videos_with_mp3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an MCP tool that concatenates videos to match an MP3's duration, with configurable ordering and audio mixing.

**Architecture:** Step-by-step FFmpeg processing — get durations, reorder videos, clip/loop each segment, concat, then replace/mix audio. Follows the existing async task pattern used by `overlay_video`, `clip_video`, etc.

**Tech Stack:** Python 3.10+, FFmpeg/FFprobe (via `ffmpeg.run_ffmpeg`/`run_ffprobe`), MCP FastMCP SDK

---

## File Structure

| File | Change |
|------|--------|
| `src/ffmpeg_mcp/cut_video.py` | Add `get_audio_duration()` and `concat_videos_with_mp3()` functions |
| `src/ffmpeg_mcp/server.py` | Add `concat_videos_with_mp3` MCP tool registration (async) |

No new files needed. Reuses existing `utils.ensure_local_path`, `utils.create_temp_file`, `utils.get_default_output_path`.

---

### Task 1: Add `get_audio_duration` helper to `cut_video.py`

**Files:**
- Modify: `src/ffmpeg_mcp/cut_video.py:154` (after `get_audio_info`)

- [ ] **Step 1: Add `get_audio_duration` function**

Add after the existing `get_audio_info` function at line 154:

```python
def get_audio_duration(audio_path: str) -> float:
    """
    获取音频文件时长（秒）

    参数:
        audio_path (str): 音频文件路径
    返回:
        float: 音频时长（秒）
    异常:
        ValueError: 无法获取音频时长
    """
    cmd = f' -v error -show_entries format=duration -of csv=p=0 -i "{audio_path}"'
    code, cmd_str, log = ffmpeg.run_ffprobe(cmd, timeout=60)
    if code != 0:
        raise ValueError(f"无法获取音频时长: {audio_path}. 错误: {log}")
    try:
        return float(log.strip())
    except (ValueError, TypeError) as e:
        raise ValueError(f"无法解析音频时长: {log}. 错误: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add src/ffmpeg_mcp/cut_video.py
git commit -m "feat: add get_audio_duration helper"
```

---

### Task 2: Add `concat_videos_with_mp3` core logic to `cut_video.py`

**Files:**
- Modify: `src/ffmpeg_mcp/cut_video.py` (after `get_audio_duration`)

- [ ] **Step 1: Add the import for `random` and `shutil` at the top of cut_video.py**

At line 1 of `src/ffmpeg_mcp/cut_video.py`, after the existing imports, add:

```python
import random
import shutil
import tempfile
```

- [ ] **Step 2: Add `concat_videos_with_mp3` function**

Add after the `get_audio_duration` function:

```python
def concat_videos_with_mp3(video_paths, audio_path, output_path=None,
                            mute_video_audio=True, order="sequence"):
    """
    根据音频时长拼接视频并替换音频

    参数:
        video_paths (list): 输入视频文件路径列表
        audio_path (str): MP3音频文件路径，决定输出时长
        output_path (str): 输出路径，可选
        mute_video_audio (bool): True=静音视频原声只保留MP3(默认), False=混合
        order (str): 拼接顺序 sequence(默认)|random|reverse

    返回:
        tuple: (status_code, log, output_path)
    """
    try:
        if output_path is None:
            output_path = utils.get_default_output_path(audio_path, "_with_mp3")

        # Step 1: 获取音频时长
        audio_duration = get_audio_duration(audio_path)
        if audio_duration <= 0:
            return (-1, "音频时长无效", "")

        # Step 2: 获取每个视频的时长和视频流信息
        video_infos = []
        for vp in video_paths:
            fmt_ctx = ffmpeg.media_format_ctx(vp)
            if fmt_ctx is None:
                print(f"跳过无法解析的视频: {vp}")
                continue
            if len(fmt_ctx.video_streams) == 0:
                print(f"跳过无视频流的文件: {vp}")
                continue
            v_duration = float(fmt_ctx.video_streams[0].duration or 0)
            if v_duration <= 0:
                # 尝试从 format 获取
                v_duration = float(fmt_ctx.audio_streams[0].duration) if fmt_ctx.audio_streams else 0
            if v_duration <= 0:
                print(f"跳过时长为0的视频: {vp}")
                continue
            video_infos.append({"path": vp, "duration": v_duration})

        if not video_infos:
            return (-1, "没有有效的视频文件", "")

        # Step 3: 按 order 参数排序
        if order == "random":
            random.shuffle(video_infos)
        elif order == "reverse":
            video_infos.reverse()
        # "sequence" 保持原序

        # Step 4: 构建裁剪/循环计划 — 生成 (path, duration) 片段列表
        segments = []
        remaining = audio_duration
        idx = 0
        while remaining > 0.01:  # 浮点精度容差
            vi = video_infos[idx % len(video_infos)]
            use_duration = min(vi["duration"], remaining)
            segments.append({"path": vi["path"], "duration": use_duration, "full_duration": vi["duration"]})
            remaining -= use_duration
            idx += 1

        # Step 5: 处理每个片段（裁剪或使用完整视频）
        temp_dir = tempfile.mkdtemp(prefix="ffmpeg_mcp_")
        try:
            segment_files = []
            for i, seg in enumerate(segments):
                seg_path = os.path.join(temp_dir, f"segment_{i:04d}.mp4")
                if seg["duration"] < seg["full_duration"] - 0.01:
                    # 需要裁剪
                    cmd = f'-i "{seg["path"]}" -t {seg["duration"]} -c copy -y "{seg_path}"'
                else:
                    # 使用完整视频
                    cmd = f'-i "{seg["path"]}" -c copy -y "{seg_path}"'
                code, log = ffmpeg.run_ffmpeg(cmd, timeout=300)
                if code != 0:
                    return (-1, f"处理片段 {i} 失败: {log}", "")
                segment_files.append(seg_path)

            # Step 6: 拼接所有片段
            merged_path = os.path.join(temp_dir, "merged.mp4")
            list_file = os.path.join(temp_dir, "filelist.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                for sf in segment_files:
                    f.write(f"file '{sf}'\n")

            cmd = f'-f concat -safe 0 -i "{list_file}" -c copy -y "{merged_path}"'
            code, log = ffmpeg.run_ffmpeg(cmd, timeout=600)
            if code != 0:
                # 回退到重编码模式
                print(f"快速拼接失败，回退到重编码模式: {log}")
                inputs_str = " ".join([f'-i "{sf}"' for sf in segment_files])
                filter_str = f"concat=n={len(segment_files)}:v=1:a=0[outv]"
                cmd = f'{inputs_str} -lavfi \'{filter_str}\' -map \'[outv]\' -y "{merged_path}"'
                code, log = ffmpeg.run_ffmpeg(cmd, timeout=600)
                if code != 0:
                    return (-1, f"拼接失败: {log}", "")

            # Step 7: 替换/混合音频
            if mute_video_audio:
                # 只保留MP3音频
                cmd = f'-i "{merged_path}" -i "{audio_path}" -map 0:v -map 1:a -shortest -y "{output_path}"'
            else:
                # 混合视频原声和MP3
                cmd = (f'-i "{merged_path}" -i "{audio_path}" '
                       f'-filter_complex "[0:a][1:a]amix=inputs=2:weights=\'1 3\'[outa]" '
                       f'-map 0:v -map "[outa]" -shortest -y "{output_path}"')

            code, log = ffmpeg.run_ffmpeg(cmd, timeout=600)
            if code != 0:
                return (-1, f"替换音频失败: {log}", "")

            return (0, f"成功，输出: {output_path}", output_path)

        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        return (-1, f"concat_videos_with_mp3 失败: {str(e)}", "")
```

- [ ] **Step 3: Commit**

```bash
git add src/ffmpeg_mcp/cut_video.py
git commit -m "feat: add concat_videos_with_mp3 core logic"
```

---

### Task 3: Register `concat_videos_with_mp3` MCP tool in `server.py`

**Files:**
- Modify: `src/ffmpeg_mcp/server.py:211` (after `get_audio_info` tool)

- [ ] **Step 1: Add the MCP tool registration**

Insert after the `get_audio_info` tool (after line 211, before `play_video`):

```python
@mcp.tool()
def concat_videos_with_mp3(video_paths: List[str], audio_path: str,
                            output_path: str = None, mute_video_audio: bool = True,
                            order: str = "sequence"):
    """
    根据音频时长拼接视频，视频过长则裁剪，过短则循环重复，最终输出以音频长度为准的视频。

    参数:
    video_paths (List[str]): 输入视频文件路径列表（支持远程URL）
    audio_path (str): MP3音频文件路径，决定输出视频的时长（支持远程URL）
    output_path (str): 输出路径，可选，不传则自动生成
    mute_video_audio (bool): 是否静音视频原声。True=只保留MP3音频(默认), False=视频原声与MP3混合
    order (str): 视频拼接顺序。sequence=按数组顺序(默认), random=随机抽取, reverse=倒序

    返回:
    异步任务，通过 get_task_status 查询结果
    """
    task_id = task_manager.create_task("concat_videos_with_mp3", {
        "video_paths": video_paths, "audio_path": audio_path,
        "output_path": output_path, "mute_video_audio": mute_video_audio, "order": order
    })

    def run_task():
        task_manager.update_task(task_id, "RUNNING")
        try:
            local_videos = [utils.ensure_local_path(v) for v in video_paths]
            local_audio = utils.ensure_local_path(audio_path)
            result = cut_video.concat_videos_with_mp3(
                local_videos, local_audio, output_path, mute_video_audio, order
            )
            if isinstance(result, (tuple, list)) and len(result) >= 3:
                status, log, path = result[0], result[1], result[2]
                task_manager.update_task(task_id, "COMPLETED",
                    result={"status": status, "log": log, "path": path, "url": get_file_url(path)})
            else:
                task_manager.update_task(task_id, "COMPLETED", result=result)
        except Exception as e:
            task_manager.update_task(task_id, "FAILED", error=str(e))

    threading.Thread(target=run_task).start()
    return {"task_id": task_id, "status": "PENDING", "message": "Task submitted successfully"}
```

- [ ] **Step 2: Commit**

```bash
git add src/ffmpeg_mcp/server.py
git commit -m "feat: register concat_videos_with_mp3 MCP tool"
```

---

### Task 4: Manual verification

- [ ] **Step 1: Start the MCP server in SSE mode**

```bash
cd /Users/findhappylee/workspace/github/ffmpeg-mcp-server
MCP_TRANSPORT=sse MCP_PORT=8032 python -m ffmpeg_mcp.server
```

Expected: Server starts with "Server running on transport: sse"

- [ ] **Step 2: Verify tool appears in tool list**

```bash
curl -s http://localhost:8032/sse &
# Or use the test client:
python test_client.py
```

Expected: `concat_videos_with_mp3` appears in the tools list.

- [ ] **Step 3: Test with sample videos**

Use `test_sse.py` as reference. Create a quick test that calls `concat_videos_with_mp3` with a short video and MP3, then polls `get_task_status` until COMPLETED or FAILED.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: concat_videos_with_mp3 tool complete"
```
