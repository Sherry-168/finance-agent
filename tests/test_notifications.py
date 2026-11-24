"""notifications 表与主动提醒 DAO 单元测试（内存数据库）。"""
import sqlite3

import pytest

from db.dao import (
    add_record,
    clear_notifications,
    count_unread_notifications,
    init_db,
    insert_notifications,
    list_notifications,
    mark_notification_read,
    scan_and_notify,
    set_budget,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def test_insert_and_list(conn):
    insert_notifications(conn, [{
        "type": "anomaly", "category": "购物", "level": "danger",
        "title": "大额", "message": "异常", "data": {"ratio": 6.0},
    }])
    assert count_unread_notifications(conn) == 1
    items = list_notifications(conn)
    assert items[0]["type"] == "anomaly"
    assert items[0]["data"]["ratio"] == 6.0


def test_mark_read(conn):
    insert_notifications(conn, [{
        "type": "budget_warning", "category": None, "level": "warning",
        "title": "t", "message": "m",
    }])
    items = list_notifications(conn)
    mark_notification_read(conn, items[0]["id"])
    assert count_unread_notifications(conn) == 0
    assert list_notifications(conn, unread_only=True) == []


def test_clear(conn):
    insert_notifications(conn, [{
        "type": "budget_warning", "level": "warning", "title": "t", "message": "m",
    }])
    assert clear_notifications(conn) == 1
    assert count_unread_notifications(conn) == 0


def test_scan_and_notify_budget_over(conn):
    set_budget(conn, "2026-11", 10000, category="餐饮")
    add_record(conn, {"amount_cents": 12000, "category": "餐饮", "occurred_at": "2026-11-10 12:00"})
    result = scan_and_notify(conn, month="2026-11")
    assert result["budget"] == 1
    items = list_notifications(conn, unread_only=True)
    assert any(i["type"] == "budget_over" for i in items)


def test_scan_and_notify_anomaly(conn):
    # 历史：餐饮平均单笔 20 元；本月一笔 200 元 → 异常（>3 倍且 >100 元）
    add_record(conn, {"amount_cents": 2000, "category": "餐饮", "occurred_at": "2026-09-10 12:00"})
    add_record(conn, {"amount_cents": 2000, "category": "餐饮", "occurred_at": "2026-09-20 12:00"})
    add_record(conn, {"amount_cents": 20000, "category": "餐饮", "occurred_at": "2026-11-10 12:00"})
    result = scan_and_notify(conn, month="2026-11")
    assert result["anomaly"] == 1
    items = list_notifications(conn, unread_only=True)
    assert any(i["type"] == "anomaly" for i in items)


def test_scan_and_notify_idempotent(conn):
    set_budget(conn, "2026-11", 10000, category="餐饮")
    add_record(conn, {"amount_cents": 12000, "category": "餐饮", "occurred_at": "2026-11-10 12:00"})
    scan_and_notify(conn, month="2026-11")
    scan_and_notify(conn, month="2026-11")  # 第二次扫描：未读被清掉重写，不堆积
    assert count_unread_notifications(conn) == 1
