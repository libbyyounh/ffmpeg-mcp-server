"""
concat_videos_with_mp3 系列工具集成测试
"""
import pytest


class TestConcatVideosWithMp3:
    """concat_videos_with_mp3 — 音频为准"""

    def test_trim_video_to_audio(self, mcp_client, test_video_url, test_audio_medium):
        """视频(10s) + 音频(5s) → 视频裁剪到 5s"""
        result = mcp_client.call_tool("concat_videos_with_mp3", {
            "video_paths": [test_video_url],
            "audio_path": test_audio_medium,
            "mute_video_audio": True,
            "order": "sequence",
        })
        task_id = result.get('task_id')
        assert task_id, f"未获取到 task_id: {result}"

        info = mcp_client.poll_task(task_id)
        assert info.get('status') == 'COMPLETED', f"任务失败: {info.get('error')}"

        res = info.get('result', {})
        assert res.get('status') == 0, f"处理失败: {res.get('log')}"
        assert res.get('path'), "缺少输出路径"

    def test_order_reverse(self, mcp_client, test_video_url, test_audio_medium):
        """order=reverse 倒序拼接"""
        result = mcp_client.call_tool("concat_videos_with_mp3", {
            "video_paths": [test_video_url, test_video_url],
            "audio_path": test_audio_medium,
            "mute_video_audio": True,
            "order": "reverse",
        })
        task_id = result.get('task_id')
        assert task_id

        info = mcp_client.poll_task(task_id)
        assert info.get('status') == 'COMPLETED'
        assert info.get('result', {}).get('status') == 0

    def test_mute_off(self, mcp_client, test_video_url, test_audio_medium):
        """mute_video_audio=False 混合音频"""
        result = mcp_client.call_tool("concat_videos_with_mp3", {
            "video_paths": [test_video_url],
            "audio_path": test_audio_medium,
            "mute_video_audio": False,
        })
        task_id = result.get('task_id')
        assert task_id

        info = mcp_client.poll_task(task_id)
        assert info.get('status') == 'COMPLETED'
        assert info.get('result', {}).get('status') == 0


class TestConcatVideosWithMp3VideoFirst:
    """concat_videos_with_mp3_video_first — 视频为准"""

    def test_audio_too_short_error(self, mcp_client, test_video_url, test_audio_short):
        """视频(10s) + 音频(1s) → 报错「音频长度不足」"""
        result = mcp_client.call_tool("concat_videos_with_mp3_video_first", {
            "video_paths": [test_video_url],
            "audio_path": test_audio_short,
            "mute_video_audio": True,
        })
        task_id = result.get('task_id')
        assert task_id

        info = mcp_client.poll_task(task_id)
        assert info.get('status') == 'COMPLETED'

        res = info.get('result', {})
        assert res.get('status') != 0, "预期失败但成功了"
        assert '音频长度不足' in res.get('log', ''), f"预期包含 '音频长度不足'，实际: {res.get('log')}"

    def test_audio_enough_success(self, mcp_client, test_video_url, test_audio_long):
        """视频(10s) + 音频(30s) → 拼接成功，音频裁剪到 ~10s"""
        result = mcp_client.call_tool("concat_videos_with_mp3_video_first", {
            "video_paths": [test_video_url],
            "audio_path": test_audio_long,
            "mute_video_audio": True,
        })
        task_id = result.get('task_id')
        assert task_id

        info = mcp_client.poll_task(task_id)
        assert info.get('status') == 'COMPLETED'
        assert info.get('result', {}).get('status') == 0
        assert info.get('result', {}).get('path'), "缺少输出路径"
