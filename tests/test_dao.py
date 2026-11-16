"""DAO 层与金额工具单元测试（使用内存数据库）。"""
import sqlite3

import pytest

from db.dao import (
    add_record,
    add_records,
    budget_alerts,
    from_slot_json,
    get_budget,
    init_db,
    list_categories,
    query_records,
    set_budget,
    sum_by_category,
    update_record,
)
from logic.money import cents_to_yuan, yuan_to_cents


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def test_categories_seeded(conn):
    assert {c["name"] for c in list_categories(conn)} == {
        "餐饮", "交通", "购物", "居住", "娱乐", "医疗", "教育", "其他",
    }


def test_yuan_to_cents_variants():
    assert yuan_to_cents(25) == 2500
    assert yuan_to_cents(25.5) == 2550
    assert yuan_to_cents("25.50") == 2550
    assert yuan_to_cents("0.01") == 1


def test_cents_to_yuan():
    assert cents_to_yuan(2550) == "25.50"
    assert cents_to_yuan(2500) == "25.00"


def test_yuan_to_cents_rejects_negative():
    with pytest.raises(ValueError):
        yuan_to_cents(-1)


def test_from_slot_json_normalizes_category():
    rec = from_slot_json({"amount": 25, "category": "不存在的", "occurred_at": "2026-11-13 12:30"})
    assert rec["amount_cents"] == 2500
    assert rec["category"] == "其他"


def test_add_and_query(conn):
    rec = from_slot_json({"amount": 25, "category": "餐饮", "occurred_at": "2026-11-13 12:30"})
    add_record(conn, rec)
    rows = query_records(conn)
    assert len(rows) == 1
    assert rows[0]["amount_cents"] == 2500
    assert rows[0]["confirmed"] == 1


def test_batch_and_filter(conn):
    txs = [
        {"amount_cents": 2500, "category": "餐饮", "occurred_at": "2026-11-03 12:00"},
        {"amount_cents": 3200, "category": "交通", "occurred_at": "2026-11-05 08:00"},
        {"amount_cents": 4000, "category": "交通", "occurred_at": "2026-10-18 10:00"},
    ]
    assert add_records(conn, txs) == 3
    assert len(query_records(conn, category="交通")) == 2
    assert len(query_records(conn, start="2026-11-01")) == 2


def test_update_record(conn):
    rec = from_slot_json({"amount": 25, "category": "餐饮", "occurred_at": "2026-11-13 12:30"})
    rid = add_record(conn, rec, confirmed=0)
    update_record(conn, rid, {"confirmed": 1, "amount_cents": 3000})
    row = query_records(conn)[0]
    assert row["confirmed"] == 1
    assert row["amount_cents"] == 3000


def test_sum_by_category_sql(conn):
    txs = [
        {"amount_cents": 2500, "category": "餐饮", "occurred_at": "2026-11-03 12:00"},
        {"amount_cents": 1550, "category": "餐饮", "occurred_at": "2026-11-08 12:00"},
        {"amount_cents": 3200, "category": "交通", "occurred_at": "2026-11-05 08:00"},
    ]
    add_records(conn, txs)
    result = {r["category"]: r["total_cents"] for r in sum_by_category(conn)}
    assert result["餐饮"] == 4050
    assert result["交通"] == 3200


def test_budget_upsert(conn):
    set_budget(conn, "2026-11", 50000)
    assert get_budget(conn, "2026-11") == 50000
    set_budget(conn, "2026-11", 60000)
    assert get_budget(conn, "2026-11") == 60000
    assert get_budget(conn, "2026-10") is None


def test_budget_alerts_over(conn):
    add_record(conn, {"amount_cents": 12000, "category": "餐饮", "occurred_at": "2026-11-03 12:00"})
    set_budget(conn, "2026-11", 10000, category="餐饮")
    alerts = budget_alerts(conn, "2026-11")
    assert alerts[0]["category"] == "餐饮"
    assert alerts[0]["status"] == "over"
    assert alerts[0]["spent_cents"] == 12000
