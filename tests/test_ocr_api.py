"""`/records/ocr` 小票识别接口测试（第二周新增）。

识别本身走云端视觉模型 / Dify，测试里用 monkeypatch 替换 `receipt.recognize`，
专注验证后端职责：多笔 → `drafts[]` 结构、逐条可入库、失败可降级。
"""
from __future__ import annotations

import io

import pytest

from app.adapters import receipt


def _upload(api, data=b"fake-png-bytes", content_type="image/png"):
    return api.post(
        "/api/v1/records/ocr",
        files={"file": ("receipt.png", io.BytesIO(data), content_type)},
    )


def test_ocr_multi_drafts(api, monkeypatch):
    monkeypatch.setattr(
        receipt,
        "recognize",
        lambda image, content_type=None: (
            "小票原文",
            [
                {"amount": 25.5, "category": "餐饮", "merchant": "瑞幸", "occurred_at": "2026-11-20 14:30"},
                {"amount": 8, "category": "交通"},
                {"category": "购物"},  # 缺金额：合计行，必须被丢弃
            ],
        ),
    )
    monkeypatch.setattr(receipt, "engine_name", lambda: "vision_api")

    body = _upload(api).json()
    assert body["code"] == 0
    data = body["data"]
    assert data["ocr_engine"] == "vision_api"
    assert data["raw_text"] == "小票原文"
    assert len(data["drafts"]) == 2

    first = data["drafts"][0]
    assert first["fields"]["amount"] == 25.5
    assert first["fields"]["merchant"] == "瑞幸"
    assert first["missing_fields"] == []
    assert first["clarify_question"] is None
    assert first["draft_id"].startswith("d_")

    # 第二笔缺日期 → 给出反问，前端只渲染反问气泡
    second = data["drafts"][1]
    assert second["missing_fields"] == ["occurred_at"]
    assert "哪天" in second["clarify_question"]


def test_ocr_drafts_can_be_committed_one_by_one(api, monkeypatch):
    monkeypatch.setattr(
        receipt,
        "recognize",
        lambda image, content_type=None: (
            "",
            [
                {"amount": 10, "category": "餐饮", "occurred_at": "2026-11-20"},
                {"amount": 20, "category": "交通", "occurred_at": "2026-11-21"},
            ],
        ),
    )
    monkeypatch.setattr(receipt, "engine_name", lambda: "vision_api")

    drafts = _upload(api).json()["data"]["drafts"]
    for draft in drafts:
        body = api.post(
            "/api/v1/records",
            json={**draft["fields"], "raw_text": "小票", "source": "ocr"},
        ).json()
        assert body["code"] == 0

    page = api.get("/api/v1/records").json()["data"]
    assert page["total"] == 2
    assert {item["source"] for item in page["items"]} == {"ocr"}


def test_ocr_unavailable_returns_2002_with_hint(api):
    body = _upload(api).json()
    assert body["code"] == 2002
    assert "文本输入" in body["message"]


def test_ocr_no_item_returns_2002_with_raw_text(api, monkeypatch):
    monkeypatch.setattr(receipt, "recognize", lambda image, content_type=None: ("只有合计", [{"category": "餐饮"}]))
    monkeypatch.setattr(receipt, "engine_name", lambda: "vision_api")

    body = _upload(api).json()
    assert body["code"] == 2002
    assert body["data"]["raw_text"] == "只有合计"


def test_ocr_receipt_error_returns_2002(api, monkeypatch):
    def boom(image, content_type=None):
        raise receipt.ReceiptError("图片太模糊")

    monkeypatch.setattr(receipt, "recognize", boom)
    body = _upload(api).json()
    assert body["code"] == 2002
    assert "模糊" in body["message"]


def test_ocr_empty_file_returns_1001(api):
    assert _upload(api, data=b"").json()["code"] == 1001


def test_ocr_non_image_returns_1001(api):
    assert _upload(api, content_type="application/pdf").json()["code"] == 1001


def test_ocr_oversize_returns_1001(api, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0.001)
    body = _upload(api, data=b"x" * 2048).json()
    assert body["code"] == 1001


def test_receipt_parse_body_shapes():
    assert receipt._parse_body([{"amount": 1}]) == ("", [{"amount": 1}])
    raw, items = receipt._parse_body({"raw_text": "原文", "items": [{"amount": 2}]})
    assert raw == "原文" and items == [{"amount": 2}]
    raw, items = receipt._parse_body({"amount": 3})
    assert raw == "" and items == [{"amount": 3}]
