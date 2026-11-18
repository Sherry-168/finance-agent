"""HTTP 接口端到端测试：统一包装、草稿链路、查账聚合、统计预算与演示数据。"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from db import dao


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    dao.init_db(conn)

    def override_get_db():
        yield conn

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        conn.close()


def _today() -> str:
    return date.today().isoformat()


def _create(client: TestClient, *, amount: float, category: str, note: str | None = None) -> int:
    response = client.post(
        "/api/v1/records",
        json={
            "amount": amount,
            "category": category,
            "occurred_at": _today(),
            "raw_text": f"{category}{amount}元",
            "note": note,
        },
    )
    assert response.json()["code"] == 0, response.text
    return response.json()["data"]["id"]


def test_parse_create_and_list(client: TestClient):
    parsed = client.post(
        "/api/v1/records/parse",
        json={"text": "昨天打车32块", "session_id": "s_parse"},
    ).json()
    assert parsed["code"] == 0
    draft = parsed["data"]
    assert draft["fields"]["amount"] == 32.0
    assert draft["fields"]["category"] == "交通"
    assert draft["fields"]["occurred_at"] == (date.today() - timedelta(days=1)).isoformat()
    assert draft["missing_fields"] == []
    assert draft["clarify_question"] is None

    fields = draft["fields"]
    record_id = _create(
        client,
        amount=fields["amount"],
        category=fields["category"],
        note=fields["note"],
    )
    assert isinstance(record_id, int) and record_id > 0

    page = client.get("/api/v1/records").json()
    assert page["code"] == 0
    assert page["data"]["total"] == 1
    item = page["data"]["items"][0]
    assert item["id"] == record_id
    assert item["amount"] == 32.0
    assert item["confirmed"] == 1


def test_parse_clarify_flow(client: TestClient):
    first = client.post(
        "/api/v1/records/parse",
        json={"text": "昨天打车", "session_id": "s_clarify"},
    ).json()["data"]
    assert "amount" in first["missing_fields"]
    assert first["clarify_question"]

    second = client.post(
        "/api/v1/records/parse",
        json={"text": "32块", "session_id": "s_clarify"},
    ).json()["data"]
    assert second["fields"]["amount"] == 32.0
    assert second["fields"]["category"] == "交通"
    assert second["fields"]["occurred_at"]
    assert second["clarify_question"] is None


def test_update_delete_and_error_codes(client: TestClient):
    record_id = _create(client, amount=10, category="餐饮")

    updated = client.put(
        f"/api/v1/records/{record_id}", json={"amount": 12.5, "note": "改过的"}
    ).json()
    assert updated["code"] == 0
    assert updated["data"]["amount"] == 12.5
    assert updated["data"]["note"] == "改过的"

    deleted = client.delete(f"/api/v1/records/{record_id}").json()
    assert deleted == {"code": 0, "message": "ok", "data": {"deleted": True}}
    missing = client.delete(f"/api/v1/records/{record_id}").json()
    assert missing["code"] == 1002

    bad_month = client.get("/api/v1/stats/summary?month=2026-13").json()
    assert bad_month["code"] == 1001
    ocr = client.post(
        "/api/v1/records/ocr", files={"file": ("receipt.png", b"x", "image/png")}
    ).json()
    assert ocr["code"] == 2002


def test_query_uses_real_aggregation(client: TestClient):
    _create(client, amount=10.5, category="餐饮")
    _create(client, amount=20.25, category="餐饮")
    _create(client, amount=99, category="购物")

    response = client.post(
        "/api/v1/query", json={"question": "我这个月吃饭花了多少？"}
    ).json()
    assert response["code"] == 0
    data = response["data"]
    assert data["slots"]["categories"] == ["餐饮"]
    assert "30.75" in data["answer_text"]
    assert data["table"] == [{"category": "餐饮", "total": 30.75, "count": 2}]


def test_stats_budget_alerts_and_categories(client: TestClient):
    month = date.today().strftime("%Y-%m")
    _create(client, amount=80, category="交通")

    summary = client.get(f"/api/v1/stats/summary?month={month}").json()["data"]
    assert summary == {"month": month, "total": 80.0, "count": 1, "daily_avg": round(80 / date.today().day, 2)}

    by_category = client.get(f"/api/v1/stats/by-category?month={month}").json()["data"]
    assert by_category["items"][0]["category"] == "交通"
    assert by_category["items"][0]["ratio"] == 1.0

    trend = client.get("/api/v1/stats/trend?days=2").json()["data"]["items"]
    assert len(trend) == 2
    assert trend[-1]["date"] == _today()
    assert trend[-1]["total"] == 80.0

    saved = client.post(
        "/api/v1/budgets", json={"month": month, "category": "交通", "amount": 100}
    ).json()
    assert saved["data"]["amount"] == 100.0
    alerts = client.get(f"/api/v1/budgets/alerts?month={month}").json()["data"]["items"]
    assert alerts[0]["used_ratio"] == 0.8
    assert alerts[0]["status"] == "warning"

    categories = client.get("/api/v1/categories").json()["data"]["items"]
    assert categories == ["餐饮", "交通", "购物", "居住", "娱乐", "医疗", "教育", "其他"]


def test_demo_load_and_reset(client: TestClient):
    loaded = client.post("/api/v1/demo/load").json()
    assert loaded["data"] == {"records": 60, "months": 2, "receipts": 3}
    assert client.get("/api/v1/records").json()["data"]["total"] == 60

    month = date.today().strftime("%Y-%m")
    statuses = {
        item["status"]
        for item in client.get(f"/api/v1/budgets/alerts?month={month}").json()["data"]["items"]
    }
    assert {"normal", "warning", "over"} <= statuses

    reset = client.post("/api/v1/demo/reset").json()["data"]
    assert reset == {"deleted_records": 60, "deleted_budgets": 3}
    assert client.get("/api/v1/records").json()["data"]["total"] == 0
