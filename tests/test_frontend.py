"""前端交互逻辑测试：查账分流、表格渲染、预算清单与 OCR 勾选入库。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))

import api  # noqa: E402
from ui import components as c  # noqa: E402
from ui.tabs import budget_tab, chat_tab  # noqa: E402


def test_query_intent_routes_to_answer_text(monkeypatch):
    assert chat_tab._is_query_intent("昨天打车32块") is False
    assert chat_tab._is_query_intent("我上个月吃饭花了多少？") is True

    def fake_query(question, session_id):
        assert "多少" in question
        return {
            "slots": {},
            "answer_text": "你 11 月餐饮共支出 ¥128.50，共 3 笔。",
            "table": [{"category": "餐饮", "total": 128.5, "count": 3}],
        }

    monkeypatch.setattr(api, "query", fake_query)
    result = chat_tab.respond("我这个月吃饭花了多少？", [], "s_test", None)
    history = result[0]
    assert history[-1]["role"] == "assistant"
    assert "¥128.50" in history[-1]["content"]
    assert "| 类别 | 金额 | 笔数 |" in history[-1]["content"]
    assert result[3] is None  # 查账不应改动记账草稿


def test_query_table_markdown_uses_backend_numbers():
    markdown = c.query_table_markdown(
        [{"category": "餐饮", "total": 1286.5, "count": 42}]
    )
    assert "| 餐饮 | ¥1,286.50 | 42 |" in markdown


def test_budget_list_uses_get_budgets(monkeypatch):
    monkeypatch.setattr(
        api,
        "list_budgets",
        lambda month: {"items": [{"id": 7, "month": month, "category": "餐饮", "amount": 1500.0}]},
    )
    html = budget_tab.load_budgets("2026-11")[0]
    assert "GET /budgets" in html
    assert "¥1,500.00" in html
    assert "餐饮" in html


def test_ocr_multi_draft_selection(monkeypatch):
    drafts = [
        {
            "draft_id": "d_1",
            "fields": {
                "amount": 45.5, "category": "餐饮", "merchant": "瑞幸咖啡",
                "occurred_at": "2026-11-18", "note": None,
            },
            "confidence": 0.88, "missing_fields": [], "clarify_question": None,
        },
        {
            "draft_id": "d_2",
            "fields": {
                "amount": 12.0, "category": "交通", "merchant": "地铁",
                "occurred_at": "2026-11-18", "note": None,
            },
            "confidence": 0.86, "missing_fields": [], "clarify_question": None,
        },
    ]
    monkeypatch.setattr(
        api,
        "ocr_receipt",
        lambda path: {"drafts": drafts, "ocr_engine": "mock", "raw_text": "瑞幸 45.5 / 地铁 12"},
    )
    history, parsed, raw_text, card, choices, panel = chat_tab.recognize_receipt("receipt.png", [])
    assert len(parsed) == 2
    assert "瑞幸咖啡" in card
    assert len(choices["value"]) == 2
    assert panel["visible"] is True

    created: list[dict] = []

    def fake_create(payload):
        created.append(payload)
        return {"id": 100 + len(created)}

    monkeypatch.setattr(api, "create_record", fake_create)
    result = chat_tab.confirm_ocr(choices["value"][:1], parsed, raw_text, history)
    assert len(created) == 1
    assert created[0]["source"] == "ocr"
    assert created[0]["amount"] == 45.5
    assert "小票已入库 1 笔" in result[0][-1]["content"]
    assert result[4]["visible"] is False
