"""
视频工具集成测试：clip, concat, scale, overlay, extract_frames
"""
import pytest


class TestClipVideo:
    """clip_video 视频裁剪"""

    def test_clip_with_start_end(self, mcp_client, test_video_url):
        """按起止时间裁剪"""
        result = mcp_client.call_tool("clip_video", {
            "video_path": test_video_url,
            "start": 0,
            "end": 3,
        })
        task_id = result.get('task_id')
        assert task_id

        info = mcp_client.poll_task(task_id)
        assert info.get('status') == 'COMPLETED'
        assert info.get('result', {}).get('status') == 0


class TestConcatVideos:
    """concat_videos 视频拼接"""

    def test_concat_fast_mode(self, mcp_client, test_video_url):
        """快速模式拼接"""
        result = mcp_client.call_tool("concat_videos", {
            "input_files": [test_video_url, test_video_url],
            "fast": True,
        })
        task_id = result.get('task_id')
        assert task_id

        info = mcp_client.poll_task(task_id)
        assert info.get('status') == 'COMPLETED'


class TestScaleVideo:
    """scale_video 视频缩放"""

    def test_scale_down(self, mcp_client, test_video_url):
        """缩小分辨率"""
        result = mcp_client.call_tool("scale_video", {
            "video_path": test_video_url,
            "width": 320,
            "height": 240,
        })
        task_id = result.get('task_id')
        assert task_id

        info = mcp_client.poll_task(task_id)
        assert info.get('status') == 'COMPLETED'
        assert info.get('result', {}).get('status') == 0
