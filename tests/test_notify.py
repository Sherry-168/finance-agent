"""通知生成单元测试。"""
from logic.notify import build_anomaly_notifications, build_budget_notifications


def test_build_budget_warning():
    alerts = [
        {"category": "餐饮", "limit_cents": 10000, "spent_cents": 8300,
         "used_ratio": 0.83, "status": "warning"}
    ]
    items = build_budget_notifications(alerts)
    assert len(items) == 1
    assert items[0]["type"] == "budget_warning"
    assert items[0]["level"] == "warning"
    assert "83%" in items[0]["message"]


def test_build_budget_over():
    alerts = [
        {"category": None, "limit_cents": 50000, "spent_cents": 60000,
         "used_ratio": 1.2, "status": "over"}
    ]
    items = build_budget_notifications(alerts)
    assert items[0]["type"] == "budget_over"
    assert items[0]["level"] == "danger"
    assert "总预算" in items[0]["title"]


def test_build_budget_skips_normal():
    alerts = [
        {"category": "餐饮", "limit_cents": 10000, "spent_cents": 5000,
         "used_ratio": 0.5, "status": "normal"}
    ]
    assert build_budget_notifications(alerts) == []


def test_build_anomaly():
    anomalies = [
        {"record_id": 1, "category": "购物", "amount_cents": 30000,
         "avg_cents": 5000, "ratio": 6.0}
    ]
    items = build_anomaly_notifications(anomalies)
    assert items[0]["type"] == "anomaly"
    assert items[0]["level"] == "danger"
    assert "300.00" in items[0]["message"]
