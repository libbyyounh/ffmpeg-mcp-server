"""
音频工具集成测试：get_audio_info, get_video_info
"""
import pytest


class TestGetAudioInfo:
    """get_audio_info 音频信息获取"""

    def test_get_mp3_info(self, mcp_client, test_audio_medium):
        """获取 MP3 音频信息"""
        result = mcp_client.call_tool("get_audio_info", {
            "audio_path": test_audio_medium,
        })
        # 同步工具返回 ffprobe tuple (code, cmd, log)，MCP 序列化为 [code, cmd, log]
        # 或在某些 SDK 版本中只返回 code
        if isinstance(result, (list, tuple)):
            assert result[0] == 0, f"ffprobe 失败: {result}"
        else:
            # 返回值是 exit code，0 = 成功
            assert result == 0, f"ffprobe 失败: {result}"


class TestGetVideoInfo:
    """get_video_info 视频信息获取"""

    def test_get_video_info(self, mcp_client, test_video_url):
        """获取远程视频信息"""
        result = mcp_client.call_tool("get_video_info", {
            "video_path": test_video_url,
        })
        if isinstance(result, (list, tuple)):
            assert result[0] == 0, f"ffprobe 失败: {result}"
        else:
            assert result == 0, f"ffprobe 失败: {result}"


class TestListTools:
    """列出所有 MCP 工具"""

    def test_list_tools(self, mcp_client):
        """验证新工具出现在工具列表中"""
        # 通过 call_tool 调用一个不存在的工具来间接验证
        # 或者直接检查工具列表
        import requests
        import json

        payload = {"jsonrpc": "2.0", "id": "list-tools", "method": "tools/list", "params": {}}
        resp = requests.post(
            f"{mcp_client.base_url}{mcp_client.endpoint}",
            json=payload,
            headers=mcp_client.headers,
        )

        for line in mcp_client.stream_iterator:
            if not line:
                continue
            data = line.decode('utf-8').replace('data: ', '')
            if not data:
                continue
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get('id') == 'list-tools':
                tools = msg.get('result', {}).get('tools', [])
                tool_names = [t['name'] for t in tools]
                assert 'concat_videos_with_mp3' in tool_names
                assert 'concat_videos_with_mp3_video_first' in tool_names
                assert 'get_audio_info' in tool_names
                assert len(tools) >= 15, f"工具数量不足: {len(tools)}"
                return
        pytest.fail("未收到工具列表响应")
