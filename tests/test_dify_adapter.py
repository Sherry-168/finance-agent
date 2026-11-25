"""Dify 适配层与解析后端切换的单元测试（第二周新增）。

验收口径对应关系：
- 「Dify 接入：LLM 调用可切 Dify」→ `_llm_parse` 按 `LLM_PROVIDER` 选后端
- 「返回数组时后端自动取首条」→ `_dify_parse` 取 `result_list()[0]`
- 「数组 / 对象双兼容适配层」→ `extract_json` + `result_list`
"""
from __future__ import annotations

import json

import pytest

from app.adapters import dify, parser


# ---------------------------------------------------------------- extract_json


@pytest.mark.parametrize(
    "raw",
    [
        '{"amount": 32}',
        '```json\n{"amount": 32}\n```',
        '好的，结果如下：\n```json\n{"amount": 32}\n```\n以上。',
        '这里是结果 {"amount": 32} 请查收',
    ],
)
def test_extract_json_accepts_object_and_fence(raw):
    assert dify.extract_json(raw) == {"amount": 32}


def test_extract_json_strips_thinking_block():
    raw = '<think>先想一想</think>[{"amount": 1}, {"amount": 2}]'
    assert dify.extract_json(raw) == [{"amount": 1}, {"amount": 2}]


def test_extract_json_survives_surrounding_prose():
    raw = "识别到两笔：\n[{\"amount\": 1}, {\"amount\": 2}]\n请确认。"
    assert dify.extract_json(raw) == [{"amount": 1}, {"amount": 2}]


def test_extract_json_returns_none_for_garbage():
    assert dify.extract_json("完全没有 JSON") is None
    assert dify.extract_json(None) is None


def test_extract_json_passthrough_structured():
    assert dify.extract_json({"a": 1}) == {"a": 1}
    assert dify.extract_json([1, 2]) == [1, 2]


# ---------------------------------------------------------------- result_list


def test_result_list_three_shapes():
    assert dify.result_list([{"a": 1}, {"a": 2}]) == [{"a": 1}, {"a": 2}]
    assert dify.result_list({"records": [{"a": 1}]}) == [{"a": 1}]
    assert dify.result_list({"amount": 5}) == [{"amount": 5}]
    # 非 dict 元素被丢弃，避免下游 normalize 崩在类型上
    assert dify.result_list([{"a": 1}, "junk", 3]) == [{"a": 1}]


def test_result_list_empty_payload():
    assert dify.result_list([]) == []
    assert dify.result_list("text") == []


# ---------------------------------------------------------------- run_workflow


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _patch_post(monkeypatch, payload: dict, captured: dict | None = None):
    monkeypatch.setattr("app.adapters.dify.is_configured", lambda: True)

    def fake_post(url, **kwargs):
        if captured is not None:
            captured.update(url=url, **kwargs)
        return _FakeResponse(payload)

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)


def test_run_workflow_success(monkeypatch):
    captured: dict = {}
    _patch_post(
        monkeypatch,
        {
            "data": {
                "status": "succeeded",
                "outputs": {"result": '```json\n[{"amount": 25}]\n```'},
            }
        },
        captured,
    )

    assert dify.run_workflow("瑞幸 25 块") == [{"amount": 25}]
    assert captured["url"].endswith("/workflows/run")
    assert captured["json"]["inputs"]["user_input"] == "瑞幸 25 块"
    assert captured["json"]["response_mode"] == "blocking"


def test_run_workflow_extra_inputs(monkeypatch):
    captured: dict = {}
    _patch_post(
        monkeypatch,
        {"data": {"status": "succeeded", "outputs": {"result": "[]"}}},
        captured,
    )
    dify.run_workflow("识别小票", inputs={"receipt_image": "data:image/png;base64,xx"})
    assert captured["json"]["inputs"]["receipt_image"].startswith("data:image/png")


def test_run_workflow_failed_status(monkeypatch):
    _patch_post(monkeypatch, {"data": {"status": "failed", "error": "quota exceeded"}})
    with pytest.raises(dify.DifyError, match="quota exceeded"):
        dify.run_workflow("x")


def test_run_workflow_without_json(monkeypatch):
    _patch_post(monkeypatch, {"data": {"status": "succeeded", "outputs": {"result": "纯文字"}}})
    with pytest.raises(dify.DifyError):
        dify.run_workflow("x")


def test_run_workflow_without_key(monkeypatch):
    monkeypatch.setattr("app.adapters.dify.is_configured", lambda: False)
    with pytest.raises(dify.DifyError, match="DIFY_API_KEY"):
        dify.run_workflow("x")


def test_run_workflow_network_error(monkeypatch):
    import httpx

    monkeypatch.setattr("app.adapters.dify.is_configured", lambda: True)

    def boom(url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(dify.DifyError, match="Dify 请求失败"):
        dify.run_workflow("x")


# ---------------------------------------------------------------- 解析后端切换


def test_parser_uses_dify_and_takes_first(monkeypatch):
    """Dify 返回数组时只取首条（验收口径），且槽位被归一化。"""
    monkeypatch.setattr(parser, "parser_provider", lambda: "dify")
    monkeypatch.setattr(
        dify,
        "run_workflow",
        lambda text, **kwargs: [
            {"amount": "25.5", "category": "餐饮", "merchant": "瑞幸", "occurred_at": "2026-11-20"},
            {"amount": 8, "category": "交通"},
        ],
    )

    fields = parser.parse_text("瑞幸 25.5")
    assert fields["amount"] == 25.5
    assert fields["category"] == "餐饮"
    assert fields["merchant"] == "瑞幸"


def test_parser_falls_back_to_rules_when_dify_breaks(monkeypatch):
    """Dify 挂掉不能让记账链路挂掉：静默降级到规则解析。"""
    monkeypatch.setattr(parser, "parser_provider", lambda: "dify")

    def boom(text, **kwargs):
        raise dify.DifyError("timeout")

    monkeypatch.setattr(dify, "run_workflow", boom)

    fields = parser.parse_text("昨天打车32块")
    assert fields["amount"] == 32.0
    assert fields["category"] == "交通"


def test_parse_text_many_with_dify_array(monkeypatch):
    monkeypatch.setattr(parser, "parser_provider", lambda: "dify")
    monkeypatch.setattr(
        dify,
        "run_workflow",
        lambda text, **kwargs: [
            {"amount": 25, "category": "餐饮", "occurred_at": "2026-11-20"},
            {"amount": 8, "category": "交通", "occurred_at": "2026-11-20"},
            {"category": "购物"},  # 缺金额 → 归一化后丢弃
        ],
    )

    items = parser.parse_text_many("长截图")
    assert [item["amount"] for item in items] == [25.0, 8.0]


def test_parse_text_many_falls_back_to_single(monkeypatch):
    monkeypatch.setattr(parser, "parser_provider", lambda: "openai")
    items = parser.parse_text_many("昨天打车32块")
    assert len(items) == 1
    assert items[0]["amount"] == 32.0


def test_normalize_many_drops_invalid():
    assert parser.normalize_many([{"amount": 0}, {"amount": -1}, {"amount": 5}]) == [
        {"amount": 5.0, "category": "其他", "merchant": None, "occurred_at": None, "note": None}
    ]


def test_provider_switch_reads_config(monkeypatch):
    """选了 dify 但没配 Key 时回退 openai，避免现场漏配环境变量就整条链路失效。"""
    from app.core import config

    monkeypatch.setattr(config, "LLM_PROVIDER", "dify")
    monkeypatch.setattr(config, "DIFY_API_KEY", "")
    assert config.parser_provider() == "openai"

    monkeypatch.setattr(config, "DIFY_API_KEY", "app-xxx")
    assert config.parser_provider() == "dify"
    assert config.llm_ready() is True
