#!/usr/bin/env python3
"""
FFmpeg MCP Server - Test Client
简单的测试客户端，用于验证 MCP 服务器是否正常工作
"""

import requests
import json
import sys


class FFmpegMCPClient:
    def __init__(self, base_url="http://localhost:8032"):
        self.base_url = base_url
        self.endpoint = f"{base_url}/message"

    def call_tool(self, tool_name, arguments):
        """调用 MCP 工具"""
        payload = {
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        try:
            response = requests.post(
                self.endpoint,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"error": "无法连接到服务器。请确保服务器正在运行。"}
        except requests.exceptions.Timeout:
            return {"error": "请求超时"}
        except Exception as e:
            return {"error": str(e)}

    def list_tools(self):
        """列出所有可用工具"""
        payload = {
            "method": "tools/list",
            "params": {}
        }

        try:
            response = requests.post(
                self.endpoint,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def health_check(self):
        """健康检查"""
        try:
            response = requests.get(self.base_url, timeout=5)
            return response.status_code == 200
        except:
            return False


def main():
    print("=" * 60)
    print("FFmpeg MCP Server - Test Client")
    print("=" * 60)

    # 初始化客户端
    client = FFmpegMCPClient()

    # 1. 健康检查
    print("\n1️⃣  Health Check...")
    if client.health_check():
        print("✅ Server is running!")
    else:
        print("❌ Server is not responding. Please start the server first.")
        print("   Run: ./start.sh or docker-compose up -d")
        sys.exit(1)

    # 2. 列出可用工具
    print("\n2️⃣  Listing available tools...")
    tools_response = client.list_tools()
    if "error" in tools_response:
        print(f"❌ Error: {tools_response['error']}")
    else:
        print("✅ Available tools:")
        if "result" in tools_response and "tools" in tools_response["result"]:
            for tool in tools_response["result"]["tools"]:
                print(f"   - {tool['name']}")
        else:
            print(f"   Response: {json.dumps(tools_response, indent=2)}")

    # 3. 测试 get_video_info (如果有测试视频)
    print("\n3️⃣  Testing get_video_info tool...")
    print("   Note: This requires a video file at /videos/test.mp4")
    print("   You can skip this test if you don't have a test video yet.")

    test_video = "/videos/test.mp4"
    response = client.call_tool("get_video_info", {"video_path": test_video})

    if "error" in response:
        print(f"   ⚠️  Expected error (no test video): {response.get('error', 'Unknown error')}")
    else:
        print("   ✅ Video info retrieved successfully!")
        print(f"   Response: {json.dumps(response, indent=2)}")

    print("\n" + "=" * 60)
    print("✅ Test completed!")
    print("\n📚 Next steps:")
    print("   1. Place video files in ./videos/ directory")
    print("   2. Check API_EXAMPLES.md for usage examples")
    print("   3. Start using the API!")
    print("=" * 60)


if __name__ == "__main__":
    main()
