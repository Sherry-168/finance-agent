"""统计路由：月度概览、类别占比、每日趋势。

口径（docs/api.md §4）：只统计 `confirmed=1` 的记录，草稿不计入。
金额统一以「元」返回；占比统一为 0~1 小数（前端 format_ratio 直接乘 100 展示）。
"""
from __future__ import annotations

import calendar
import datetime as dt
import re
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.config import DEFAULT_USER_ID
from app.core.db import get_db
from app.core.response import ApiError, PARAM_ERROR, ok
from db import dao
from logic.money import cents_to_yuan

router = APIRouter(prefix="/stats", tags=["stats"])

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _check_month(month: str | None) -> str:
    """校验并补全省略的月份（默认当前月）。"""
    month = month or dt.date.today().strftime("%Y-%m")
    if not _MONTH_RE.match(month):
        raise ApiError(PARAM_ERROR, "月份格式应为 YYYY-MM，例如 2026-11")
    return month


def _month_bounds(month: str) -> tuple[str, str]:
    """'YYYY-MM' → (当月 1 日, 下月 1 日)，左闭右开。"""
    year, mon = (int(part) for part in month.split("-"))
    start = dt.date(year, mon, 1)
    end = dt.date(year + 1, 1, 1) if mon == 12 else dt.date(year, mon + 1, 1)
    return start.isoformat(), end.isoformat()


def _days_elapsed(month: str) -> int:
    """日均分母：当月已过天数（历史月份取整月天数，未来月份取 1 避免除零）。"""
    year, mon = (int(part) for part in month.split("-"))
    today = dt.date.today()
    days_in_month = calendar.monthrange(year, mon)[1]
    if (year, mon) == (today.year, today.month):
        return max(today.day, 1)
    if (year, mon) > (today.year, today.month):
        return 1
    return days_in_month


def _yuan(cents: int) -> float:
    return float(cents_to_yuan(cents))


@router.get("/summary", summary="月度概览")
def summary(
    month: str | None = Query(None, description="YYYY-MM，默认当前月"),
    conn: Any = Depends(get_db),
) -> dict[str, Any]:
    """月度支出总额 / 笔数 / 日均（日均 = 总额 ÷ 当月已过天数）。"""
    month = _check_month(month)
    start, end = _month_bounds(month)

    records = dao.query_records(
        conn, start=start, end=end, confirmed=1, user_id=DEFAULT_USER_ID
    )
    total_cents = sum(int(r["amount_cents"]) for r in records)
    total = _yuan(total_cents)
    days = _days_elapsed(month)

    return ok(
        {
            "month": month,
            "total": total,
            "count": len(records),
            "daily_avg": round(total / days, 2),
        }
    )


@router.get("/by-category", summary="类别占比")
def by_category(
    month: str | None = Query(None, description="YYYY-MM，默认当前月"),
    start: str | None = Query(None, description="开始日期 YYYY-MM-DD，与 end 搭配使用"),
    end: str | None = Query(None, description="结束日期 YYYY-MM-DD（含当天）"),
    conn: Any = Depends(get_db),
) -> dict[str, Any]:
    """按类别汇总金额与笔数，ratio 为 0~1 小数，按金额降序。"""
    if start and end:
        start_day, end_day = start, end
        try:
            end_exclusive = (dt.date.fromisoformat(end_day) + dt.timedelta(days=1)).isoformat()
        except ValueError:
            raise ApiError(PARAM_ERROR, "日期格式应为 YYYY-MM-DD")
    else:
        month = _check_month(month)
        start_day, end_exclusive = _month_bounds(month)

    rows = dao.sum_by_category(conn, start=start_day, end=end_exclusive, user_id=DEFAULT_USER_ID)
    grand = sum(int(row["total_cents"]) for row in rows)
    items = [
        {
            "category": row["category"],
            "total": _yuan(row["total_cents"]),
            "count": int(row["count"]),
            "ratio": round(int(row["total_cents"]) / grand, 2) if grand else 0.0,
        }
        for row in rows
    ]
    return ok({"items": items})


@router.get("/trend", summary="每日趋势")
def trend(
    days: int = Query(30, ge=1, le=90, description="回溯天数，默认 30"),
    conn: Any = Depends(get_db),
) -> dict[str, Any]:
    """近 N 天每日支出与笔数，无消费的日期补 0，便于折线连续。"""
    today = dt.date.today()
    start = (today - dt.timedelta(days=days - 1)).isoformat()
    end_exclusive = (today + dt.timedelta(days=1)).isoformat()

    records = dao.query_records(
        conn, start=start, end=end_exclusive, confirmed=1, user_id=DEFAULT_USER_ID
    )
    buckets: dict[str, dict[str, int]] = {}
    for record in records:
        day = record["occurred_at"][:10]
        bucket = buckets.setdefault(day, {"total_cents": 0, "count": 0})
        bucket["total_cents"] += int(record["amount_cents"])
        bucket["count"] += 1

    items = []
    for offset in range(days - 1, -1, -1):
        day = (today - dt.timedelta(days=offset)).isoformat()
        bucket = buckets.get(day, {"total_cents": 0, "count": 0})
        items.append(
            {
                "date": day,
                "total": _yuan(bucket["total_cents"]),
                "count": bucket["count"],
            }
        )
    return ok({"items": items})
