"""
共享 fixtures：MCP SSE 客户端、测试音频/视频生成
"""
import pytest
import requests
import json
import time
import os
import subprocess


class MCPClient:
    """MCP SSE 客户端，封装连接、握手、调用、轮询"""

    def __init__(self, base_url="http://localhost:8032", token="testtoken"):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.stream_iterator = None
        self.endpoint = None

    def connect(self):
        """建立 SSE 连接并完成 MCP 握手"""
        sse_resp = requests.get(f'{self.base_url}/sse', stream=True, headers=self.headers)
        assert sse_resp.status_code == 200, f"SSE 连接失败: {sse_resp.status_code}"

        self.stream_iterator = sse_resp.iter_lines()
        for line in self.stream_iterator:
            decoded = line.decode('utf-8')
            if decoded.startswith('data: /messages/'):
                self.endpoint = decoded.replace('data: ', '')
                break
        assert self.endpoint, "获取 endpoint 失败"

        # 握手
        init_payload = {
            "jsonrpc": "2.0", "id": "init-1", "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }
        requests.post(f"{self.base_url}{self.endpoint}", json=init_payload, headers=self.headers)

        for line in self.stream_iterator:
            if not line:
                continue
            if line.decode('utf-8').startswith('data: '):
                msg = json.loads(line.decode('utf-8').replace('data: ', ''))
                if msg.get('id') == 'init-1':
                    break

        requests.post(
            f"{self.base_url}{self.endpoint}",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=self.headers,
        )

    def call_tool(self, tool_name, arguments, request_id=None):
        """调用 MCP 工具并返回解析后的结果"""
        if request_id is None:
            request_id = f"call-{tool_name}-{id(arguments)}"
        payload = {
            "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        requests.post(f"{self.base_url}{self.endpoint}", json=payload, headers=self.headers)

        for line in self.stream_iterator:
            if not line:
                continue
            data = line.decode('utf-8').replace('data: ', '')
            if not data:
                continue
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get('id') == request_id:
                return self._parse_result(msg)
        return {}

    def poll_task(self, task_id, timeout=120, interval=2):
        """轮询异步任务直到 COMPLETED/FAILED 或超时"""
        for i in range(timeout // interval):
            info = self.call_tool("get_task_status", {"task_id": task_id}, f"poll-{task_id}-{i}")
            status = info.get('status')
            if status in ('COMPLETED', 'FAILED'):
                return info
            time.sleep(interval)
        return {"status": "TIMEOUT", "error": "轮询超时"}

    @staticmethod
    def _parse_result(msg):
        """从 MCP 响应中提取 result"""
        try:
            content = msg.get('result', {}).get('content', [])
            if content and content[0].get('type') == 'text':
                text = content[0].get('text', '')
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text
        except Exception:
            pass
        return {}


@pytest.fixture(scope="session")
def mcp_client():
    """Session 级别的 MCP 客户端，所有测试共享同一个连接"""
    host = os.getenv('MCP_HOST', 'localhost')
    port = os.getenv('MCP_PORT', '8032')
    token = os.getenv('MCP_AUTH_TOKEN', 'testtoken')
    client = MCPClient(base_url=f"http://{host}:{port}", token=token)
    client.connect()
    return client


@pytest.fixture(scope="session")
def test_video_url():
    """测试视频 URL（约 10 秒）"""
    return "https://www.w3schools.com/html/mov_bbb.mp4"


@pytest.fixture(scope="session")
def test_audio_short(tmp_path_factory):
    """生成 1 秒测试 MP3"""
    path = tmp_path_factory.mktemp("audio") / "short.mp3"
    subprocess.run(
        ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
         '-q:a', '2', str(path)],
        capture_output=True,
    )
    return str(path)


@pytest.fixture(scope="session")
def test_audio_medium(tmp_path_factory):
    """生成 5 秒测试 MP3"""
    path = tmp_path_factory.mktemp("audio") / "medium.mp3"
    subprocess.run(
        ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=5',
         '-q:a', '2', str(path)],
        capture_output=True,
    )
    return str(path)


@pytest.fixture(scope="session")
def test_audio_long(tmp_path_factory):
    """生成 30 秒测试 MP3"""
    path = tmp_path_factory.mktemp("audio") / "long.mp3"
    subprocess.run(
        ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=30',
         '-q:a', '2', str(path)],
        capture_output=True,
    )
    return str(path)
