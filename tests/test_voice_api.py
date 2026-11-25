"""`/voice` 语音录入接口测试（第二周新增）。

不联网：`ASR_PROVIDER=mock`（conftest 已设置），转写固定为「昨天打车 32 块」，
用来验证「音频 → 文本 → 草稿 → 入库」整条链路与三种降级行为。
"""
from __future__ import annotations

import io

import pytest

from app.adapters.asr import AsrError
from app.core import config


def _upload(api, data=b"RIFF-fake-wav-bytes", filename="voice.wav", **form):
    return api.post(
        "/api/v1/voice",
        files={"file": (filename, io.BytesIO(data), "audio/wav")},
        data=form,
    )


def test_status_available_with_mock(api):
    body = api.get("/api/v1/voice/status").json()
    assert body["code"] == 0
    assert body["data"]["available"] is True
    assert body["data"]["engine"] == "mock"
    assert body["data"]["max_upload_mb"] > 0


def test_voice_returns_draft_only(api):
    body = _upload(api).json()
    assert body["code"] == 0
    data = body["data"]
    assert data["transcript"] == "昨天打车 32 块"
    assert data["asr_engine"] == "mock"
    assert data["fields"]["amount"] == 32.0
    assert data["fields"]["category"] == "交通"
    assert data["missing_fields"] == []
    assert data["clarify_question"] is None
    # 默认只出草稿，不替用户记账
    assert data["record_id"] is None
    assert api.get("/api/v1/records").json()["data"]["total"] == 0


def test_voice_auto_commit(api):
    body = _upload(api, auto_commit="true").json()
    data = body["data"]
    assert data["action"] == "committed"
    assert data["confirmed"] == 1
    assert isinstance(data["record_id"], int)

    page = api.get("/api/v1/records").json()["data"]
    assert page["total"] == 1
    record = page["items"][0]
    assert record["amount"] == 32.0
    assert record["category"] == "交通"
    assert record["source"] == "voice"


def test_voice_auto_commit_still_clarifies_when_incomplete(api, monkeypatch):
    """转写里有金额但没时间 → 即使 auto_commit 也不能猜日期入库。"""
    monkeypatch.setattr(
        "app.routers.voice.asr.speech_to_text", lambda audio, name=None: ("打车 32 块", "mock")
    )

    body = _upload(api, auto_commit="true").json()
    data = body["data"]
    assert data["action"] == "clarify"
    assert "occurred_at" in data["missing_fields"]
    assert data["clarify_question"]
    assert api.get("/api/v1/records").json()["data"]["total"] == 0


def test_voice_rejects_non_expense_speech(api, monkeypatch):
    """越界 / 灌水请求只回引导气泡，不生成空白确认卡。"""
    monkeypatch.setattr(
        "app.routers.voice.asr.speech_to_text",
        lambda audio, name=None: ("帮我写一首关于春天的诗", "mock"),
    )
    body = _upload(api).json()
    assert body["data"]["action"] == "reject"
    assert body["data"]["confidence"] == 0.0


def test_asr_error_returns_2003(api, monkeypatch):
    def boom(audio, name=None):
        raise AsrError("没听清，请靠近麦克风再说一遍")

    monkeypatch.setattr("app.routers.voice.asr.speech_to_text", boom)
    body = _upload(api).json()
    assert body["code"] == 2003
    assert "没听清" in body["message"]


def test_empty_audio_returns_1001(api):
    body = _upload(api, data=b"").json()
    assert body["code"] == 1001


def test_oversize_audio_returns_1001(api, monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0.001)
    body = _upload(api, data=b"x" * 2048).json()
    assert body["code"] == 1001
    assert "上限" in body["message"]


def test_missing_file_returns_1001(api):
    body = api.post("/api/v1/voice", data={}).json()
    assert body["code"] == 1001


def test_engine_none_blocks_voice(api, monkeypatch):
    """没配 ASR Key 时明确报 2003 并提示改用文本输入，而不是假装识别成功。"""
    monkeypatch.setattr("app.adapters.asr.ASR_PROVIDER", "auto")
    monkeypatch.setattr("app.adapters.asr.ASR_API_KEY", "")

    assert api.get("/api/v1/voice/status").json()["data"]["available"] is False
    body = _upload(api).json()
    assert body["code"] == 2003
    assert "文本输入" in body["message"]


def test_agent_mode_unavailable_until_function_delivered(api, monkeypatch):
    """`agent` 模式只在李语琛真的交付了 speech_to_text 后才对前端报可用。"""
    monkeypatch.setattr("app.adapters.asr.ASR_PROVIDER", "agent")
    monkeypatch.setattr("app.adapters.asr._agent_ready", lambda: False)

    data = api.get("/api/v1/voice/status").json()["data"]
    assert data["engine"] == "agent"
    assert data["available"] is False

    body = _upload(api).json()
    assert body["code"] == 2003
    # 具体原因可能是「函数没交付」或「agent.py 的依赖没装」，两者都指向 agent.py，
    # 关键是别再糊成一句「语音不可用」——联调时要一眼看出卡在哪。
    assert "agent.py" in body["message"]


def test_agent_mode_calls_delivered_function(api, monkeypatch):
    """李语琛按约定交付后，后端应把原始音频交给他并复用其返回文本。"""
    seen = {}

    def fake(audio, name=None):
        seen["size"] = len(audio)
        return "昨天打车 32 块"

    monkeypatch.setattr("app.adapters.asr.ASR_PROVIDER", "agent")
    monkeypatch.setattr("app.adapters.asr._agent_ready", lambda: True)
    monkeypatch.setattr("app.adapters.asr._transcribe_agent", fake)

    body = _upload(api, data=b"RIFF-payload").json()
    assert body["code"] == 0
    assert body["data"]["transcript"] == "昨天打车 32 块"
    assert body["data"]["asr_engine"] == "agent"
    assert body["data"]["fields"]["amount"] == 32.0
    assert seen["size"] == len(b"RIFF-payload")
