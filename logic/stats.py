"""统计逻辑（纯函数）：按类别汇总、按日汇总、时间过滤、环比。

输入：records 字典列表，字段与 records 表一致（occurred_at / amount_cents / category）。
金额统一为 int（分）。
对应接口：/stats/summary、/stats/by-category、/stats/trend。
"""
from __future__ import annotations

from collections import defaultdict


def filter_by_period(records: list[dict], start: str | None = None, end: str | None = None) -> list[dict]:
    """按时间区间 [start, end) 过滤。ISO 字符串比较即时间比较。"""
    result = []
    for r in records:
        t = r["occurred_at"]
        if start and t < start:
            continue
        if end and t >= end:
            continue
        result.append(r)
    return result


def total_expense(records: list[dict]) -> int:
    """总支出（分）。"""
    return sum(int(r["amount_cents"]) for r in records)


def summary(records: list[dict]) -> dict:
    """月度概览：总额（分）、笔数、日均（分，按活跃天数计）。"""
    total = total_expense(records)
    cnt = len(records)
    days = len({r["occurred_at"][:10] for r in records}) or 1
    return {"total_cents": total, "count": cnt, "daily_avg_cents": round(total / days)}


def by_category(records: list[dict]) -> list[dict]:
    """按类别汇总，按金额降序。"""
    agg: dict[str, dict] = defaultdict(lambda: {"total_cents": 0, "count": 0})
    for r in records:
        cat = r.get("category") or "其他"
        agg[cat]["total_cents"] += int(r["amount_cents"])
        agg[cat]["count"] += 1
    result = [{"category": k, **v} for k, v in agg.items()]
    result.sort(key=lambda x: -x["total_cents"])
    return result


def category_share(records: list[dict]) -> list[dict]:
    """分类占比（百分比，保留两位小数）。"""
    total = total_expense(records)
    if total == 0:
        return []
    return [
        {
            "category": item["category"],
            "total_cents": item["total_cents"],
            "share": round(item["total_cents"] / total * 100, 2),
        }
        for item in by_category(records)
    ]


def trend(records: list[dict], granularity: str = "day") -> list[dict]:
    """按 day / month 汇总支出趋势，按时间升序。"""
    key_len = 10 if granularity == "day" else 7
    agg: dict[str, int] = defaultdict(int)
    for r in records:
        agg[r["occurred_at"][:key_len]] += int(r["amount_cents"])
    return [{"period": k, "total_cents": v} for k, v in sorted(agg.items())]


def month_over_month(current: list[dict], previous: list[dict]) -> dict:
    """环比：本月 vs 上月。change_pct 为百分比，上月为 0 时返回 None。"""
    cur = total_expense(current)
    prev = total_expense(previous)
    if prev == 0:
        return {"current_cents": cur, "previous_cents": prev, "change_pct": None}
    return {
        "current_cents": cur,
        "previous_cents": prev,
        "change_pct": round((cur - prev) / prev * 100, 2),
    }


def top_category(records: list[dict], n: int = 3) -> list[dict]:
    """支出最多的前 n 个分类。"""
    return by_category(records)[:n]
