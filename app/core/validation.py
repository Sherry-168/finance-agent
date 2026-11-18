"""接口层通用校验与换算工具。

对外金额统一「元」，内部 DAO / logic 统一「分」，换算只在接口层完成；
日期参数对外含首尾，传给 DAO 时统一转成左闭右开。
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from app.core.response import ApiError

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?: [0-2]\d:[0-5]\d(?::[0-5]\d)?)?$")


def valid_month(value: str | None, *, default_today: date | None = None) -> str:
    """校验 YYYY-MM；空值时取当前月。"""
    if value is None or not value.strip():
        return (default_today or date.today()).strftime("%Y-%m")
    month = value.strip()
    if not _MONTH_RE.match(month):
        raise ApiError(1001, "月份格式应为 YYYY-MM，例如 2026-11")
    return month


def valid_date(value: str | None, *, allow_time: bool = False, field: str = "日期") -> str | None:
    """校验 YYYY-MM-DD（可选带时分秒），空值返回 None。"""
    if value is None or not value.strip():
        return None
    text = value.strip()
    pattern = _DATETIME_RE if allow_time else _DATE_RE
    if not pattern.match(text):
        hint = "YYYY-MM-DD HH:MM" if allow_time else "YYYY-MM-DD"
        raise ApiError(1001, f"{field}格式应为 {hint}")
    try:
        datetime.strptime(text[:10], "%Y-%m-%d")
    except ValueError as exc:
        raise ApiError(1001, f"{field}不是有效日期：{text}") from exc
    return text


def month_bounds(month: str) -> tuple[str, str]:
    """'YYYY-MM' → 左闭右开 [YYYY-MM-01, 下月-01)。"""
    year, mon = (int(part) for part in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
    return start.isoformat(), end.isoformat()


def next_day(value: str | None) -> str | None:
    """对外 end 含首尾，DAO 用右开区间，故整体后移一天。"""
    if not value:
        return None
    return (date.fromisoformat(value[:10]) + timedelta(days=1)).isoformat()


def elapsed_days(month: str, *, today: date | None = None) -> int:
    """日均分母：当月已过天数（历史月份取整月天数）。"""
    start, end_exclusive = month_bounds(month)
    total_days = (date.fromisoformat(end_exclusive) - date.fromisoformat(start)).days
    today = today or date.today()
    if month == today.strftime("%Y-%m"):
        return max(1, min(today.day, total_days))
    return total_days


def yuan(cents: int) -> float:
    """分 → 元（浮点，保留两位），仅在响应序列化时使用。"""
    return round(int(cents) / 100, 2)


def ratio(numerator: int, denominator: int) -> float:
    """占比 0~1，保留两位小数；分母为 0 时返回 0。"""
    if not denominator:
        return 0.0
    return round(numerator / denominator, 2)
