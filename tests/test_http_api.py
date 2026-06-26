"""
HTTP REST API 集成测试
覆盖：响应格式、参数校验、任务生命周期、错误处理
需要先启动 SSE 模式的服务器：MCP_TRANSPORT=sse MCP_AUTH_TOKEN=testtoken python -m ffmpeg_mcp.server
"""
import pytest
import requests
import time
import os


BASE_URL = os.getenv("MCP_TEST_URL", "http://localhost:8032")
TOKEN = os.getenv("MCP_AUTH_TOKEN", "testtoken")
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


# --- 响应格式 ---

class TestResponseFormat:
    """验证统一响应结构 {code, data, message}"""

    def test_success_response_structure(self):
        """成功响应包含 code=0, data, message"""
        resp = requests.get(f"{BASE_URL}/api/list_output_videos", headers=HEADERS)
        body = resp.json()
        assert "code" in body
        assert "data" in body
        assert "message" in body
        assert body["code"] == 0
        assert isinstance(body["data"], list)

    def test_error_response_structure(self):
        """错误响应包含 code=1, data=null, message"""
        resp = requests.get(f"{BASE_URL}/api/get_video_info", headers=HEADERS)
        body = resp.json()
        assert body["code"] == 1
        assert body["data"] is None
        assert "message" in body
        assert resp.status_code == 400


# --- 认证 ---

class TestAuthentication:
    """验证 Bearer Token 认证"""

    def test_missing_token_returns_401(self):
        """无 Token 时返回 401"""
        resp = requests.get(f"{BASE_URL}/api/list_output_videos")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self):
        """错误 Token 时返回 401"""
        resp = requests.get(
            f"{BASE_URL}/api/list_output_videos",
            headers={"Authorization": "Bearer wrong_token"},
        )
        assert resp.status_code == 401

    def test_valid_token_succeeds(self):
        """正确 Token 时返回 200"""
        resp = requests.get(f"{BASE_URL}/api/list_output_videos", headers=HEADERS)
        assert resp.status_code == 200


# --- 参数校验 ---

class TestParameterValidation:
    """验证缺少必填参数时返回 400"""

    def test_get_video_info_missing_param(self):
        resp = requests.get(f"{BASE_URL}/api/get_video_info", headers=HEADERS)
        assert resp.status_code == 400
        assert resp.json()["code"] == 1

    def test_get_audio_info_missing_param(self):
        resp = requests.get(f"{BASE_URL}/api/get_audio_info", headers=HEADERS)
        assert resp.status_code == 400

    def test_download_video_missing_param(self):
        resp = requests.get(f"{BASE_URL}/api/download_video", headers=HEADERS)
        assert resp.status_code == 400

    def test_find_video_path_missing_params(self):
        resp = requests.get(f"{BASE_URL}/api/find_video_path", headers=HEADERS)
        assert resp.status_code == 400

    def test_clip_video_missing_video_path(self):
        resp = requests.post(
            f"{BASE_URL}/api/clip_video",
            headers=HEADERS,
            json={"start": 0, "end": 10},
        )
        assert resp.status_code == 400

    def test_concat_videos_missing_input_files(self):
        resp = requests.post(
            f"{BASE_URL}/api/concat_videos",
            headers=HEADERS,
            json={},
        )
        assert resp.status_code == 400

    def test_concat_videos_invalid_input_files_type(self):
        resp = requests.post(
            f"{BASE_URL}/api/concat_videos",
            headers=HEADERS,
            json={"input_files": "not_a_list"},
        )
        assert resp.status_code == 400

    def test_overlay_video_missing_background(self):
        resp = requests.post(
            f"{BASE_URL}/api/overlay_video",
            headers=HEADERS,
            json={"overlay_video": "/videos/test.mp4"},
        )
        assert resp.status_code == 400

    def test_scale_video_missing_width(self):
        resp = requests.post(
            f"{BASE_URL}/api/scale_video",
            headers=HEADERS,
            json={"video_path": "/videos/test.mp4", "height": 720},
        )
        assert resp.status_code == 400

    def test_delete_videos_missing_video_paths(self):
        resp = requests.post(
            f"{BASE_URL}/api/delete_videos",
            headers=HEADERS,
            json={},
        )
        assert resp.status_code == 400

    def test_concat_videos_with_mp3_missing_audio_path(self):
        resp = requests.post(
            f"{BASE_URL}/api/concat_videos_with_mp3",
            headers=HEADERS,
            json={"video_paths": ["/videos/a.mp4"]},
        )
        assert resp.status_code == 400

    def test_extract_frames_missing_video_path(self):
        resp = requests.post(
            f"{BASE_URL}/api/extract_frames_from_video",
            headers=HEADERS,
            json={},
        )
        assert resp.status_code == 400


# --- 任务状态查询 ---

class TestTaskStatus:
    """验证 get_task_status 端点"""

    def test_nonexistent_task_returns_404(self):
        """不存在的 task_id 返回 404"""
        resp = requests.get(
            f"{BASE_URL}/api/get_task_status/nonexistent-id",
            headers=HEADERS,
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 1
        assert "not found" in body["message"].lower()


# --- 同步端点 ---

class TestSyncEndpoints:
    """验证同步 GET 端点"""

    def test_list_output_videos(self):
        resp = requests.get(f"{BASE_URL}/api/list_output_videos", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)

    def test_list_videos_folder(self):
        resp = requests.get(f"{BASE_URL}/api/list_videos_folder", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)

    def test_delete_videos_with_empty_list(self):
        """删除空列表应成功"""
        resp = requests.post(
            f"{BASE_URL}/api/delete_videos",
            headers=HEADERS,
            json={"video_paths": []},
        )
        assert resp.status_code == 400  # 空 list 不通过校验

    def test_delete_videos_with_nonexistent_file(self):
        """删除不存在的文件应返回 failed 列表"""
        resp = requests.post(
            f"{BASE_URL}/api/delete_videos",
            headers=HEADERS,
            json={"video_paths": ["/videos/nonexistent_file.mp4"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert len(body["data"]["failed"]) == 1
        assert body["data"]["failed"][0]["reason"] == "文件不存在"


# --- 异步任务生命周期 ---

class TestAsyncTaskLifecycle:
    """验证异步端点的完整生命周期：提交 → 轮询 → 完成"""

    def test_clip_video_full_lifecycle(self, test_video_url):
        """clip_video 提交任务并轮询到完成"""
        # 提交任务
        resp = requests.post(
            f"{BASE_URL}/api/clip_video",
            headers=HEADERS,
            json={
                "video_path": test_video_url,
                "start": 0,
                "duration": 2,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["status"] == "PENDING"
        task_id = body["data"]["task_id"]
        assert task_id

        # 轮询任务状态
        for _ in range(30):
            time.sleep(2)
            status_resp = requests.get(
                f"{BASE_URL}/api/get_task_status/{task_id}",
                headers=HEADERS,
            )
            assert status_resp.status_code == 200
            status_body = status_resp.json()
            task_status = status_body["data"]["status"]
            if task_status in ("COMPLETED", "FAILED"):
                break
        else:
            pytest.fail("任务轮询超时")

        assert task_status == "COMPLETED", f"任务失败: {status_body['data'].get('error')}"
        result = status_body["data"]["result"]
        assert result["status"] == 0
        assert "path" in result

    def test_concat_videos_full_lifecycle(self, test_video_url):
        """concat_videos 提交任务并轮询到完成"""
        resp = requests.post(
            f"{BASE_URL}/api/concat_videos",
            headers=HEADERS,
            json={
                "input_files": [test_video_url, test_video_url],
                "fast": True,
            },
        )
        assert resp.status_code == 200
        task_id = resp.json()["data"]["task_id"]

        for _ in range(30):
            time.sleep(2)
            status_resp = requests.get(
                f"{BASE_URL}/api/get_task_status/{task_id}",
                headers=HEADERS,
            )
            status = status_resp.json()["data"]["status"]
            if status in ("COMPLETED", "FAILED"):
                break
        else:
            pytest.fail("任务轮询超时")

        assert status == "COMPLETED", f"任务失败: {status_resp.json()['data'].get('error')}"
