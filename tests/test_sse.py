"""
SSE 连接和基本功能集成测试（从原 test_sse.py 迁移）
"""
import pytest
import json


class TestSSEConnection:
    """SSE 连接基本测试"""

    def test_tool_list(self, mcp_client):
        """验证能获取工具列表"""
        import requests

        payload = {"jsonrpc": "2.0", "id": "list", "method": "tools/list", "params": {}}
        requests.post(
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
            if msg.get('id') == 'list':
                tools = msg.get('result', {}).get('tools', [])
                assert len(tools) > 0, "工具列表为空"
                return
        pytest.fail("未收到工具列表响应")

    def test_concat_videos_basic(self, mcp_client, test_video_url):
        """基本的 concat_videos 调用"""
        result = mcp_client.call_tool("concat_videos", {
            "input_files": [test_video_url, test_video_url],
            "output_path": "concat_test.mp4",
        })
        task_id = result.get('task_id')
        assert task_id, f"未获取到 task_id: {result}"

        info = mcp_client.poll_task(task_id)
        assert info.get('status') == 'COMPLETED', f"任务失败: {info}"
