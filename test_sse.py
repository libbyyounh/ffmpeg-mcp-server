import requests
import json
import time
import os

def parse_mcp_result(msg):
    """助手函数：从 MCP 响应中提取并解析 tool 返回的 JSON 数据"""
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

def test_mcp():
    print("Testing FFmpeg MCP Server over SSE...")
    
    host = os.getenv('MCP_HOST', 'localhost')
    port = os.getenv('MCP_PORT', '8032')
    token = os.getenv('MCP_AUTH_TOKEN', 'testtoken')
    base_url = f"http://{host}:{port}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    try:
        print(f"Connecting to {base_url}/sse ...")
        sse_resp = requests.get(f'{base_url}/sse', stream=True, headers=headers)
        if sse_resp.status_code != 200:
            print(f"❌ SSE Connection failed: {sse_resp.status_code}")
            return

        endpoint = ''
        stream_iterator = sse_resp.iter_lines()
        for line in stream_iterator:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: /messages/'):
                endpoint = decoded_line.replace('data: ', '')
                break
        
        if not endpoint:
            print("❌ Failed to get message endpoint")
            return

        print(f"✅ Using endpoint: {endpoint}")

        # --- MCP INITIALIZATION SEQUENCE ---
        print("\n1. Sending 'initialize' request...")
        init_payload = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        requests.post(f"{base_url}{endpoint}", json=init_payload, headers=headers)
        
        for line in stream_iterator:
            if not line: continue
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                data = decoded_line.replace('data: ', '')
                msg = json.loads(data)
                if msg.get('id') == 'init-1':
                    print("✅ Received initialization result")
                    break

        print("\n2. Sending 'notifications/initialized'...")
        notif_payload = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        requests.post(f"{base_url}{endpoint}", json=notif_payload, headers=headers)

        # 3. Call SYNC tool: get_video_info
        print(f"\n3. Calling SYNC tool (get_video_info)...")
        info_payload = {
            "jsonrpc": "2.0",
            "id": "test-sync-info",
            "method": "tools/call",
            "params": {
                "name": "get_video_info",
                "arguments": {
                    "video_path": "https://www.w3schools.com/html/mov_bbb.mp4"
                }
            }
        }
        requests.post(f"{base_url}{endpoint}", json=info_payload, headers=headers)
        
        for line in stream_iterator:
            if not line: continue
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                data = decoded_line.replace('data: ', '')
                msg = json.loads(data)
                if msg.get('id') == 'test-sync-info':
                    print("✅ Received SYNC tool response (immediate)")
                    info = parse_mcp_result(msg)
                    print(json.dumps(info, indent=2, ensure_ascii=False))
                    break

        # 4. Call ASYNC tool: clip_video
        print(f"\n4. Submitting ASYNC task (clip_video)...")
        task_payload = {
            "jsonrpc": "2.0",
            "id": "test-async-clip",
            "method": "tools/call",
            "params": {
                "name": "clip_video",
                "arguments": {
                    "video_path": "https://www.w3schools.com/html/mov_bbb.mp4",
                    "start": 0,
                    "duration": 2
                }
            }
        }
        requests.post(f"{base_url}{endpoint}", json=task_payload, headers=headers)
        
        task_id = None
        for line in stream_iterator:
            if not line: continue
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                data = decoded_line.replace('data: ', '')
                msg = json.loads(data)
                if msg.get('id') == 'test-async-clip':
                    print("✅ Received ASYNC task initiation response")
                    result_data = parse_mcp_result(msg)
                    task_id = result_data.get('task_id')
                    print(f"Task ID: {task_id}")
                    break

        if not task_id:
            print("❌ Did not receive task_id")
            return

        # 5. Poll for task completion
        print(f"\n5. Polling for task {task_id} completion...")
        for i in range(20):
            status_payload = {
                "jsonrpc": "2.0",
                "id": f"poll-{i}",
                "method": "tools/call",
                "params": {
                    "name": "get_task_status",
                    "arguments": {"task_id": task_id}
                }
            }
            requests.post(f"{base_url}{endpoint}", json=status_payload, headers=headers)
            
            status_found = False
            for line in stream_iterator:
                if not line: continue
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    data = decoded_line.replace('data: ', '')
                    msg = json.loads(data)
                    if msg.get('id') == f"poll-{i}":
                        task_data = parse_mcp_result(msg)
                        status = task_data.get('status')
                        print(f"Attempt {i+1}: Status is {status}")
                        if status in ["COMPLETED", "FAILED"]:
                            print("\n🎉 Task Finished!")
                            print(json.dumps(task_data, indent=2, ensure_ascii=False))
                            status_found = True
                            break
                        else:
                            status_found = True
                            break
            
            if status_found and status in ["COMPLETED", "FAILED"]:
                break
            time.sleep(2)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_mcp()
