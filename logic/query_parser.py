"""自然语言查账的「时间换算」落点（纯函数）。

约定（对齐《项目方案设计文档》§5.2 / §9）：
LLM 只负责把自然语言拆成槽位（时间表达、类别、聚合方式），
本模块负责把「上月」「近 7 天」这类相对时间换算成绝对区间，
SQL 执行与算数由 dao / stats 完成——LLM 全程不参与算术。

时间区间内部统一「左闭右开 [start, end)」：
end 为次日 / 下月 1 日零点，避免 DATETIME 含时分秒时右闭漏掉当天记录。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class QuerySpec:
    """一次查账的结构化参数。start/end 为 'YYYY-MM-DD'，区间左闭右开 [start, end)。"""
    start: str
    end: str
    categories: list[str] | None = None
    agg: str = "sum"      # sum / trend / share / top
    group_by: str | None = None


def _d(d: date) -> str:
    return d.isoformat()


def _next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _shift_month(d: date, months: int) -> date:
    y, m = d.year, d.month + months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return date(y, m, 1)


def resolve_time_range(expr: str, today: date | None = None) -> tuple[str, str]:
    """把时间表达解析成 (start, end)，左闭右开。无法识别时兜底为「本月」。"""
    today = today or date.today()
    e = (expr or "").strip()
    y, m = today.year, today.month

    if e in ("今天", "今日", "today"):
        return _d(today), _d(today + timedelta(days=1))
    if e in ("昨天", "昨日", "yesterday"):
        return _d(today - timedelta(days=1)), _d(today)
    if e in ("本周", "这周", "this week"):
        monday = today - timedelta(days=today.weekday())
        return _d(monday), _d(today + timedelta(days=1))
    if e in ("上周", "last week"):
        monday = today - timedelta(days=today.weekday() + 7)
        return _d(monday), _d(monday + timedelta(days=7))
    if e in ("本月", "这个月", "this month"):
        start = date(y, m, 1)
        return _d(start), _d(_next_month(start))
    if e in ("上月", "上个月", "last month"):
        return _d(_shift_month(date(y, m, 1), -1)), _d(date(y, m, 1))
    if e in ("今年", "this year"):
        return _d(date(y, 1, 1)), _d(date(y + 1, 1, 1))
    if e in ("去年", "last year"):
        return _d(date(y - 1, 1, 1)), _d(date(y, 1, 1))

    mch = re.match(r"^(?:近|最近)(\d+)天$", e)
    if mch:
        n = int(mch.group(1))
        start = today - timedelta(days=n - 1)
        return _d(start), _d(today + timedelta(days=1))

    mch = re.match(r"^(?:近|最近)(\d+)个月$", e)
    if mch:
        n = int(mch.group(1))
        start = _shift_month(date(y, m, 1), -(n - 1))
        return _d(start), _d(today + timedelta(days=1))

    # 兜底：视为本月
    start = date(y, m, 1)
    return _d(start), _d(_next_month(start))
