"""演示数据接口：一键灌入 / 清空。

无 LLM Key 的评审环境靠这里拿到两个月流水与三档预算（normal / warning / over），
数据全部走 DAO 落库，统计页与查账页读到的都是真实记录。
"""
from __future__ import annotations

import calendar
import sqlite3
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends

from app.core.config import DEFAULT_USER_ID
from app.core.db import get_db
from app.core.response import ok
from db import dao
from logic.classify import classify
from logic.money import yuan_to_cents

router = APIRouter(prefix="/demo", tags=["demo"])

_RECORD_COUNT = 60
_MONTHS = 2
_RECEIPTS = 3

_SAMPLES = (
    ("餐饮", "瑞幸咖啡", 18.5), ("交通", "滴滴出行", 32.0),
    ("购物", "京东", 128.0), ("居住", "自如", 1200.0),
    ("娱乐", "万达影城", 45.0), ("医疗", "海王星辰", 66.5),
    ("教育", "网易云课堂", 320.0), ("餐饮", "美团外卖", 58.0),
    ("交通", "中石化", 156.0), ("购物", "优衣库", 210.0),
)


def _day_in_month(year: int, month: int, index: int, limit: int) -> str:
    max_day = min(calendar.monthrange(year, month)[1], limit)
    return date(year, month, min(index, max_day)).isoformat()


def _build_records() -> list[dict[str, Any]]:
    today = date.today()
    first = today.replace(day=1)
    prev_year, prev_month = (first.year - 1, 12) if first.month == 1 else (first.year, first.month - 1)
    records: list[dict[str, Any]] = []
    for offset in range(_RECORD_COUNT // 2):
        category, merchant, base_amount = _SAMPLES[offset % len(_SAMPLES)]
        amount = round(base_amount + (offset % 5) * 7.5, 2)
        # 第二个半年月份把金额略做区分，趋势图跨月更直观
        for year, month, factor, limit in (
            (prev_year, prev_month, 0.9, calendar.monthrange(prev_year, prev_month)[1]),
            (first.year, first.month, 1.0, today.day),
        ):
            day = _day_in_month(year, month, offset + 1, limit)
            description = f"{category}{merchant}消费"
            records.append(
                {
                    "amount_cents": yuan_to_cents(round(amount * factor, 2)),
                    "category": classify(description) if category == "其他" else category,
                    "merchant": merchant,
                    "occurred_at": day,
                    "source": "demo",
                    "raw_text": description,
                    "note": "演示数据",
                }
            )
    return records


def _setup_budgets(conn: sqlite3.Connection, records: list[dict[str, Any]]) -> None:
    today = date.today()
    month = today.strftime("%Y-%m")
    start = today.replace(day=1).isoformat()
    end = (
        date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)
    ).isoformat()
    current = [
        record
        for record in records
        if start <= record["occurred_at"] < end
    ]
    total = sum(int(record["amount_cents"]) for record in current)
    dining = sum(
        int(record["amount_cents"])
        for record in current
        if record["category"] == "餐饮"
    )
    fun = sum(
        int(record["amount_cents"])
        for record in current
        if record["category"] == "娱乐"
    )
    dao.set_budget(conn, month, round(total * 1.18), user_id=DEFAULT_USER_ID)
    dao.set_budget(conn, month, round(dining * 1.5), "餐饮", user_id=DEFAULT_USER_ID)
    dao.set_budget(conn, month, max(100, round(fun * 0.8)), "娱乐", user_id=DEFAULT_USER_ID)


@router.post("/load", summary="一键灌入演示数据")
def load_demo(conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    existing = dao.count_records(conn, source="demo", user_id=DEFAULT_USER_ID)
    if existing < _RECORD_COUNT:
        records = _build_records()
        dao.add_records(conn, records, user_id=DEFAULT_USER_ID, confirmed=1)
        _setup_budgets(conn, records)
    return ok({"records": _RECORD_COUNT, "months": _MONTHS, "receipts": _RECEIPTS})


@router.post("/reset", summary="清空演示数据")
def reset_demo(conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    return ok(dao.clear_user_data(conn, user_id=DEFAULT_USER_ID))
