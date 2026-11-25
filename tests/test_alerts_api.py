"""`/alerts` 主动提醒接口测试（第二周新增）。

覆盖验收口径：超 80% 橙色（warning）、超 100% 红色（danger）、可已读关闭，
以及「入库后自动扫描」这条事件驱动链路是否真的通。
"""
from __future__ import annotations

import datetime as dt

import pytest

THIS_MONTH = dt.date.today().strftime("%Y-%m")
IN_MONTH = f"{THIS_MONTH}-10"


def _set_budget(api, amount: float, category: str | None = "餐饮"):
    return api.post(
        "/api/v1/budgets",
        json={"month": THIS_MONTH, "category": category, "amount": amount},
    )


def _add_record(api, amount: float, category: str = "餐饮"):
    return api.post(
        "/api/v1/records",
        json={
            "amount": amount,
            "category": category,
            "occurred_at": IN_MONTH,
            "raw_text": f"测试记录 {amount}",
        },
    )


def test_empty_alerts(api):
    body = api.get("/api/v1/alerts").json()
    assert body["code"] == 0
    assert body["data"]["items"] == []
    assert body["data"]["unread_count"] == 0


def test_warning_at_80_percent(api):
    """用 90 元 / 100 元预算 = 90%，落在 warning（橙色）区间。"""
    _set_budget(api, 100)
    _add_record(api, 90)

    items = api.get("/api/v1/alerts").json()["data"]["items"]
    assert len(items) == 1
    item = items[0]
    assert item["type"] == "budget_warning"
    assert item["level"] == "warning"
    assert item["category"] == "餐饮"
    assert item["is_read"] == 0
    # 金额同时提供「分」原值与「元」别名，前端只做 ¥ 格式化
    assert item["data"]["limit_cents"] == 10000
    assert item["data"]["limit"] == 100.0
    assert item["data"]["used"] == 90.0
    assert item["data"]["used_ratio"] == pytest.approx(0.9)


def test_danger_over_budget(api):
    _set_budget(api, 100)
    _add_record(api, 120)

    items = api.get("/api/v1/alerts").json()["data"]["items"]
    assert [item["type"] for item in items] == ["budget_over"]
    assert items[0]["level"] == "danger"
    assert "超支" in items[0]["title"]
    assert items[0]["data"]["used"] == 120.0


def test_normal_budget_has_no_alert(api):
    """没到 80% 不该打扰用户——横幅只在需要时出现。"""
    _set_budget(api, 100)
    _add_record(api, 50)
    assert api.get("/api/v1/alerts").json()["data"]["items"] == []


def test_total_budget_category_is_none(api):
    """总额预算（category=null）的提醒也应有，且 name 显示为「总预算」。"""
    _set_budget(api, 100, category=None)
    _add_record(api, 120)
    items = api.get("/api/v1/alerts").json()["data"]["items"]
    assert items[0]["category"] is None
    assert "总预算" in items[0]["title"]


def test_anomaly_alert(api, conn):
    """历史平均 20 元，本月一笔 200 元 → 异常巡检要抓到。"""
    from db import dao

    dao.add_record(conn, {"amount_cents": 2000, "category": "餐饮", "occurred_at": "2026-09-10 12:00"})
    dao.add_record(conn, {"amount_cents": 2000, "category": "餐饮", "occurred_at": "2026-09-20 12:00"})

    _add_record(api, 200)
    items = api.get("/api/v1/alerts").json()["data"]["items"]
    assert any(item["type"] == "anomaly" for item in items)


def test_mark_single_read(api):
    _set_budget(api, 100)
    _add_record(api, 120)

    alert_id = api.get("/api/v1/alerts").json()["data"]["items"][0]["id"]
    body = api.post(f"/api/v1/alerts/{alert_id}/read").json()
    assert body["data"]["is_read"] == 1
    assert body["data"]["unread_count"] == 0

    # 默认只返回未读；显式查全部时仍能看到这条已读历史
    assert api.get("/api/v1/alerts").json()["data"]["items"] == []
    all_items = api.get("/api/v1/alerts", params={"unread_only": False, "refresh": False}).json()
    assert all_items["data"]["items"][0]["is_read"] == 1


def test_read_all(api):
    _set_budget(api, 100)
    _add_record(api, 120)
    api.get("/api/v1/alerts")  # 先生成提醒

    body = api.post("/api/v1/alerts/read-all").json()
    assert body["data"]["updated"] == 1
    assert api.get("/api/v1/alerts").json()["data"]["unread_count"] == 0


def test_read_unknown_alert_returns_1002(api):
    body = api.post("/api/v1/alerts/999999/read").json()
    assert body["code"] == 1002


def test_invalid_month_returns_1001(api):
    body = api.get("/api/v1/alerts", params={"month": "2026-13"}).json()
    assert body["code"] == 1001


def test_refresh_false_does_not_scan(api, conn):
    """`refresh=false` 时只读不扫，用于前端轮询时不重复打库。"""
    from db import dao

    _set_budget(api, 100)
    _add_record(api, 120)  # 入库时已经自动扫描过一次
    dao.clear_notifications(conn)

    body = api.get("/api/v1/alerts", params={"refresh": False}).json()
    assert body["data"]["items"] == []

    # 默认 refresh=true 会补扫，提醒重新出现
    assert api.get("/api/v1/alerts").json()["data"]["items"]


def test_record_create_response_carries_unread_count(api):
    """确认入库后立即回未读数，聊天页可直接点亮横幅，无需再等轮询。"""
    _set_budget(api, 100)
    body = _add_record(api, 120).json()
    assert body["code"] == 0
    assert body["data"]["unread_alerts"] == 1
