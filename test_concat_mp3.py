"""
测试 concat_videos_with_mp3 和 concat_videos_with_mp3_video_first 工具
用法: MCP_TRANSPORT=sse MCP_PORT=8032 python test_concat_mp3.py
"""
import requests
import json
import time
import os


def parse_mcp_result(msg):
    """从 MCP 响应中提取 result"""
    try:
        content = msg.get('result', {}).get('content', [])
        if content and content[0].get('type') == 'text':
            text = content[0].get('text', '')
            try:
                return json.loads(text)
            except:
                return text
    except Exception as e:
        print(f"DEBUG: Error parsing result: {e}")
    return {}


class MCPTester:
    def __init__(self):
        host = os.getenv('MCP_HOST', 'localhost')
        port = os.getenv('MCP_PORT', '8032')
        token = os.getenv('MCP_AUTH_TOKEN', 'testtoken')
        self.base_url = f"http://{host}:{port}"
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.stream_iterator = None
        self.endpoint = None

    def connect(self):
        """建立 SSE 连接并完成握手"""
        print(f"连接到 {self.base_url}/sse ...")
        sse_resp = requests.get(f'{self.base_url}/sse', stream=True, headers=self.headers)
        if sse_resp.status_code != 200:
            raise Exception(f"SSE 连接失败: {sse_resp.status_code}")

        self.stream_iterator = sse_resp.iter_lines()
        for line in self.stream_iterator:
            decoded = line.decode('utf-8')
            if decoded.startswith('data: /messages/'):
                self.endpoint = decoded.replace('data: ', '')
                break

        if not self.endpoint:
            raise Exception("获取 endpoint 失败")
        print(f"✅ Endpoint: {self.endpoint}")

        # 握手
        init_payload = {
            "jsonrpc": "2.0", "id": "init-1", "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "test-client", "version": "1.0"}}
        }
        requests.post(f"{self.base_url}{self.endpoint}", json=init_payload, headers=self.headers)

        for line in self.stream_iterator:
            if not line: continue
            if line.decode('utf-8').startswith('data: '):
                msg = json.loads(line.decode('utf-8').replace('data: ', ''))
                if msg.get('id') == 'init-1':
                    break

        requests.post(f"{self.base_url}{self.endpoint}",
                      json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                      headers=self.headers)
        print("✅ 握手完成")

    def call_tool(self, tool_name, arguments, request_id="test-1"):
        """调用 MCP 工具并返回结果"""
        payload = {
            "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        }
        requests.post(f"{self.base_url}{self.endpoint}", json=payload, headers=self.headers)

        for line in self.stream_iterator:
            if not line: continue
            data = line.decode('utf-8').replace('data: ', '')
            if not data: continue
            try:
                msg = json.loads(data)
            except:
                continue
            if msg.get('id') == request_id:
                return parse_mcp_result(msg)
        return {}

    def poll_task(self, task_id, timeout=120):
        """轮询任务状态直到完成或超时"""
        for i in range(timeout // 2):
            info = self.call_tool("get_task_status", {"task_id": task_id}, f"poll-{task_id}-{i}")
            status = info.get('status')
            if status in ['COMPLETED', 'FAILED']:
                return info
            time.sleep(2)
        return {"status": "TIMEOUT", "error": "轮询超时"}


def test_concat_videos_with_mp3(tester):
    """测试 concat_videos_with_mp3 — 音频为准"""
    print("\n" + "=" * 60)
    print("测试 1: concat_videos_with_mp3 (音频为准)")
    print("=" * 60)

    video_url = "https://www.w3schools.com/html/mov_bbb.mp4"  # ~10秒
    # 用 ffmpeg 生成一个 5 秒的测试音频
    test_audio = "/tmp/test_bgm.mp3"
    os.system(f'ffmpeg -y -f lavfi -i "sine=frequency=440:duration=5" -q:a 2 "{test_audio}" 2>/dev/null')

    print(f"\n视频: {video_url} (约10秒)")
    print(f"音频: {test_audio} (5秒)")
    print("预期: 视频被裁剪到5秒")

    result = tester.call_tool("concat_videos_with_mp3", {
        "video_paths": [video_url],
        "audio_path": test_audio,
        "mute_video_audio": True,
        "order": "sequence"
    }, "test-mp3-1")

    task_id = result.get('task_id')
    if not task_id:
        print(f"❌ 未获取到 task_id: {result}")
        return False

    print(f"✅ Task ID: {task_id}")
    info = tester.poll_task(task_id)
    print(f"状态: {info.get('status')}")
    if info.get('status') == 'COMPLETED':
        res = info.get('result', {})
        print(f"输出: {res.get('path')}")
        print(f"URL: {res.get('url')}")
        return True
    else:
        print(f"❌ 失败: {info.get('error')}")
        return False


def test_concat_video_first_error(tester):
    """测试 concat_videos_with_mp3_video_first — 音频不足应报错"""
    print("\n" + "=" * 60)
    print("测试 2: concat_videos_with_mp3_video_first (音频不足应报错)")
    print("=" * 60)

    video_url = "https://www.w3schools.com/html/mov_bbb.mp4"  # ~10秒
    # 生成 1 秒的短音频
    test_audio = "/tmp/test_short.mp3"
    os.system(f'ffmpeg -y -f lavfi -i "sine=frequency=440:duration=1" -q:a 2 "{test_audio}" 2>/dev/null')

    print(f"\n视频: {video_url} (约10秒)")
    print(f"音频: {test_audio} (1秒)")
    print("预期: 报错 '音频长度不足'")

    result = tester.call_tool("concat_videos_with_mp3_video_first", {
        "video_paths": [video_url],
        "audio_path": test_audio,
        "mute_video_audio": True,
        "order": "sequence"
    }, "test-vf-1")

    task_id = result.get('task_id')
    if not task_id:
        print(f"❌ 未获取到 task_id: {result}")
        return False

    print(f"✅ Task ID: {task_id}")
    info = tester.poll_task(task_id)
    status = info.get('status')
    print(f"状态: {status}")

    if status == 'COMPLETED':
        res = info.get('result', {})
        task_status = res.get('status')
        log = res.get('log', '')
        if task_status != 0 and '音频长度不足' in log:
            print(f"✅ 正确报错: {log}")
            return True
        else:
            print(f"❌ 预期报错但得到: status={task_status}, log={log}")
            return False
    elif status == 'FAILED':
        print(f"✅ 任务失败（符合预期）: {info.get('error')}")
        return True
    else:
        print(f"❌ 意外状态: {status}")
        return False


def test_concat_video_first_success(tester):
    """测试 concat_videos_with_mp3_video_first — 音频足够时正常工作"""
    print("\n" + "=" * 60)
    print("测试 3: concat_videos_with_mp3_video_first (音频足够)")
    print("=" * 60)

    video_url = "https://www.w3schools.com/html/mov_bbb.mp4"  # ~10秒
    # 生成 30 秒的长音频
    test_audio = "/tmp/test_long.mp3"
    os.system(f'ffmpeg -y -f lavfi -i "sine=frequency=440:duration=30" -q:a 2 "{test_audio}" 2>/dev/null')

    print(f"\n视频: {video_url} (约10秒)")
    print(f"音频: {test_audio} (30秒)")
    print("预期: 拼接成功，音频被裁剪到约10秒")

    result = tester.call_tool("concat_videos_with_mp3_video_first", {
        "video_paths": [video_url],
        "audio_path": test_audio,
        "mute_video_audio": True,
        "order": "sequence"
    }, "test-vf-2")

    task_id = result.get('task_id')
    if not task_id:
        print(f"❌ 未获取到 task_id: {result}")
        return False

    print(f"✅ Task ID: {task_id}")
    info = tester.poll_task(task_id)
    print(f"状态: {info.get('status')}")
    if info.get('status') == 'COMPLETED':
        res = info.get('result', {})
        print(f"输出: {res.get('path')}")
        print(f"URL: {res.get('url')}")
        return True
    else:
        print(f"❌ 失败: {info.get('error')}")
        return False


def test_order_reverse(tester):
    """测试 order=reverse 排序"""
    print("\n" + "=" * 60)
    print("测试 4: concat_videos_with_mp3 (order=reverse)")
    print("=" * 60)

    video_url = "https://www.w3schools.com/html/mov_bbb.mp4"
    test_audio = "/tmp/test_bgm.mp3"  # 复用之前生成的

    print(f"\n视频: {video_url} x2 (倒序)")
    print(f"音频: {test_audio} (5秒)")

    result = tester.call_tool("concat_videos_with_mp3", {
        "video_paths": [video_url, video_url],
        "audio_path": test_audio,
        "mute_video_audio": True,
        "order": "reverse"
    }, "test-order-1")

    task_id = result.get('task_id')
    if not task_id:
        print(f"❌ 未获取到 task_id: {result}")
        return False

    info = tester.poll_task(task_id)
    print(f"状态: {info.get('status')}")
    if info.get('status') == 'COMPLETED':
        print("✅ 倒序拼接成功")
        return True
    else:
        print(f"❌ 失败: {info.get('error')}")
        return False


def main():
    print("=" * 60)
    print("concat_videos_with_mp3 系列工具测试")
    print("=" * 60)

    tester = MCPTester()
    tester.connect()

    results = {}
    results['音频为准'] = test_concat_videos_with_mp3(tester)
    results['音频不足报错'] = test_concat_video_first_error(tester)
    results['视频为准'] = test_concat_video_first_success(tester)
    results['倒序排序'] = test_order_reverse(tester)

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results.items():
        icon = "✅" if passed else "❌"
        print(f"  {icon} {name}")

    all_passed = all(results.values())
    print(f"\n{'✅ 全部通过!' if all_passed else '❌ 有测试失败'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
