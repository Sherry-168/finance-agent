"""CORS 跨域配置测试（第二周新增验收项）。

前端是 Gradio 服务端调用，正常不触发浏览器同源策略；但答辩时经常有人直接用
浏览器 / 前端调试工具打 8000 端口，没有 CORS 会卡在预检请求上，所以这里是必测项。
"""
from __future__ import annotations


def test_preflight_allows_frontend_origin(api):
    response = api.options(
        "/api/v1/records/parse",
        headers={
            "Origin": "http://localhost:7860",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    headers = {key.lower(): value for key, value in response.headers.items()}
    assert headers.get("access-control-allow-origin") in ("*", "http://localhost:7860")
    assert "POST" in headers.get("access-control-allow-methods", "").upper()


def test_simple_request_carries_cors_header(api):
    response = api.get("/api/v1/health", headers={"Origin": "http://127.0.0.1:7860"})
    headers = {key.lower(): value for key, value in response.headers.items()}
    assert headers.get("access-control-allow-origin") in ("*", "http://127.0.0.1:7860")
