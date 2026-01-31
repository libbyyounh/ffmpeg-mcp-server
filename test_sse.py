import requests
import json
import time

def test_mcp():
    print("Testing FFmpeg MCP Server over SSE...")
    try:
        sse_resp = requests.get('http://localhost:8032/sse', stream=True)
        endpoint = ''
        for line in sse_resp.iter_lines():
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('event: endpoint'):
                # The data line is usually the next line
                continue
            if decoded_line.startswith('data: /messages/'):
                endpoint = decoded_line.replace('data: ', '')
                break
        
        if not endpoint:
            print("Failed to get message endpoint")
            return

        print(f"Using endpoint: {endpoint}")

        # 2. Call get_video_info with a remote URL
        payload = {
            "jsonrpc": "2.0",
            "id": "test-info",
            "method": "tools/call",
            "params": {
                "name": "get_video_info",
                "arguments": {
                    "video_path": "https://www.w3schools.com/html/mov_bbb.mp4"
                }
            }
        }
        
        print("\nCalling get_video_info for remote URL...")
        post_resp = requests.post(f"http://localhost:8032{endpoint}", json=payload)
        print(f"POST Status Code: {post_resp.status_code}") # Should be 202

        print("\nWaiting for response on SSE stream...")
        for line in sse_resp.iter_lines():
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                data = decoded_line.replace('data: ', '')
                try:
                    msg = json.loads(data)
                    if msg.get('id') == 'test-info':
                        print("✅ Received tool result:")
                        print(json.dumps(msg, indent=2, ensure_ascii=False))
                        break
                except:
                    pass

        # 3. Test static file access
        print("\nTesting static file access...")
        static_resp = requests.get("http://localhost:8032/videos/", allow_redirects=True)
        print(f"GET /videos/: {static_resp.status_code}")
        if static_resp.status_code == 200:
            print("✅ Static file serving is WORKING")
        else:
            print(f"❌ Static file serving FAILED (Status: {static_resp.status_code})")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_mcp()
