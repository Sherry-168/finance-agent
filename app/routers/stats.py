"""统计接口：月度概览 / 类别占比 / 每日趋势。

统计口径统一为 confirmed=1，草稿不参与；聚合由 DAO + logic.stats 完成，
接口层只做「分 → 元」和 0~1 占比换算。
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.config import DEFAULT_USER_ID
from app.core.db import get_db
from app.core.response import ApiError, ok
from app.core.validation import elapsed_days, month_bounds, next_day, ratio, valid_date, valid_month, yuan
from db import dao
from logic import stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary", summary="月度概览")
def stats_summary(
    month: str | None = Query(None, description="YYYY-MM，缺省为当前月"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    month = valid_month(month)
    start, end = month_bounds(month)
    rows = dao.query_records(conn, start, end, confirmed=1, user_id=DEFAULT_USER_ID)
    total_cents = stats.total_expense(rows)
    return ok(
        {
            "month": month,
            "total": yuan(total_cents),
            "count": len(rows),
            "daily_avg": round(total_cents / 100 / elapsed_days(month), 2),
        }
    )


@router.get("/by-category", summary="类别占比")
def stats_by_category(
    month: str | None = Query(None, description="YYYY-MM，与 start/end 二选一"),
    start: str | None = Query(None, description="开始日期 YYYY-MM-DD（含）"),
    end: str | None = Query(None, description="结束日期 YYYY-MM-DD（含）"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    start_date = valid_date(start, field="开始日期")
    end_date = valid_date(end, field="结束日期")
    if not (start_date or end_date):
        month = valid_month(month)
        start_date, end_exclusive = month_bounds(month)
    else:
        end_exclusive = next_day(end_date)
        if start_date and end_date and start_date > end_date:
            raise ApiError(1001, "开始日期不能晚于结束日期")

    rows = dao.sum_by_category(conn, start_date, end_exclusive, user_id=DEFAULT_USER_ID)
    grand_total = sum(int(row["total_cents"]) for row in rows)
    items = [
        {
            "category": row["category"],
            "total": yuan(row["total_cents"]),
            "count": row["count"],
            "ratio": ratio(row["total_cents"], grand_total),
        }
        for row in rows
    ]
    return ok({"items": items})


@router.get("/trend", summary="每日趋势")
def stats_trend(
    days: int = Query(30, ge=1, le=90),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    today = date.today()
    start = (today - timedelta(days=days - 1)).isoformat()
    end_exclusive = (today + timedelta(days=1)).isoformat()
    rows = dao.query_records(
        conn, start, end_exclusive, confirmed=1, user_id=DEFAULT_USER_ID
    )

    by_day: dict[str, dict[str, int]] = {}
    for row in rows:
        day = row["occurred_at"][:10]
        bucket = by_day.setdefault(day, {"total_cents": 0, "count": 0})
        bucket["total_cents"] += int(row["amount_cents"])
        bucket["count"] += 1

    items = []
    for offset in range(days - 1, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        bucket = by_day.get(day, {"total_cents": 0, "count": 0})
        items.append(
            {"date": day, "total": yuan(bucket["total_cents"]), "count": bucket["count"]}
        )
    return ok({"items": items})
