import requests
import json
import time
import os

def parse_mcp_result(msg):
    """Refined helper to extract result from MCP tool response"""
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
    print("Testing FFmpeg MCP Server over SSE: Concat Videos...")
    
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

        # --- MCP INITIALIZATION ---
        print("\n1. Handshaking (initialize)...")
        init_payload = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0"}}
        }
        requests.post(f"{base_url}{endpoint}", json=init_payload, headers=headers)
        
        # Wait for initialize response
        for line in stream_iterator:
            if not line: continue
            if line.decode('utf-8').startswith('data: '):
                msg = json.loads(line.decode('utf-8').replace('data: ', ''))
                if msg.get('id') == 'init-1':
                    break
        
        requests.post(f"{base_url}{endpoint}", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=headers)
        print("✅ Handshake complete")

        # --- TEST CONCAT VIDEOS ---
        print("\n2. Submitting concat_videos task (2 remote videos)...")
        # We'll use the same video twice for demonstration
        video_url = "https://www.w3schools.com/html/mov_bbb.mp4"
        task_payload = {
            "jsonrpc": "2.0",
            "id": "test-concat",
            "method": "tools/call",
            "params": {
                "name": "concat_videos",
                "arguments": {
                    "input_files": [video_url, video_url],
                    "output_path": "concat_result.mp4"
                }
            }
        }
        requests.post(f"{base_url}{endpoint}", json=task_payload, headers=headers)
        
        task_id = None
        for line in stream_iterator:
            if not line: continue
            data = line.decode('utf-8').replace('data: ', '')
            if not data: continue
            
            # DEBUG
            print(f"DEBUG raw SSE data: {data}")

            try:
                msg = json.loads(data)
            except Exception as e:
                print(f"DEBUG: JSON parse error for data: {data} -> {e}")
                continue
            
            if msg.get('id') == 'test-concat':
                print("✅ Received task submission response")
                res = parse_mcp_result(msg)
                task_id = res.get('task_id')
                print(f"Task ID: {task_id}")
                break

        if not task_id:
            print("❌ Failed to get task_id")
            return

        # Poll status
        print(f"\n3. Polling task {task_id}...")
        for i in range(30): # Wait up to 60s
            status_req = {
                "jsonrpc": "2.0",
                "id": f"poll-{i}",
                "method": "tools/call",
                "params": {"name": "get_task_status", "arguments": {"task_id": task_id}}
            }
            requests.post(f"{base_url}{endpoint}", json=status_req, headers=headers)
            
            found = False
            for line in stream_iterator:
                if not line: continue
                val = line.decode('utf-8').replace('data: ', '')
                if not val: continue
                try:
                    m = json.loads(val)
                except:
                    continue
                
                if m.get('id') == f"poll-{i}":
                    info = parse_mcp_result(m)
                    status = info.get('status')
                    print(f"Poll {i+1}: {status}")
                    if status in ['COMPLETED', 'FAILED']:
                        print("\n🎉 Final Result:")
                        print(json.dumps(info, indent=2, ensure_ascii=False))
                        found = True
                    break
            
            if found: break
            time.sleep(2)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_mcp()
