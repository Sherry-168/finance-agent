"""自然语言查账。

链路：`logic.query_parser.extract_slots` 抽槽位（时间 / 类别 / 聚合方式）
→ `resolve_time_range` 换算绝对区间 → `dao` 取真实流水 → 后端模板拼 `answer_text`。
模型全程不参与算数，答案只来自已确认记录，草稿不计入。
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import DEFAULT_USER_ID
from app.core.db import get_db
from app.core.response import ok
from db import dao
from logic.classify import known_categories
from logic.money import cents_to_yuan
from logic.query_parser import extract_slots

router = APIRouter(tags=["query"])


class QuestionRequest(BaseModel):
    """查账入参。"""

    question: str = Field(..., min_length=1, description="自然语言问题，如「我上个月吃饭花了多少？」")
    session_id: str | None = None


def _money(cents: int) -> str:
    return f"¥{float(cents_to_yuan(cents)):,.2f}"


def _money_yuan(value: float) -> str:
    """已经是「元」的数值直接格式化，避免反复换算引入误差。"""
    return f"¥{float(value):,.2f}"


def _period_label(start: str, end_inclusive: str) -> str:
    """把闭区间转成口语化时间标签：整月 → 「10 月」，单日 → 日期，其余 → 区间。"""
    start_day = date.fromisoformat(start)
    end_day = date.fromisoformat(end_inclusive)
    next_year, next_month = (start_day.year + 1, 1) if start_day.month == 12 else (
        start_day.year,
        start_day.month + 1,
    )
    is_full_month = start_day.day == 1 and end_day + timedelta(days=1) == date(next_year, next_month, 1)
    if is_full_month:
        prefix = "" if start_day.year == date.today().year else f"{start_day.year} 年 "
        return f"{prefix}{start_day.month} 月"
    if start_day == end_day:
        return start_day.isoformat()
    return f"{start} 至 {end_inclusive}"


def _group_by_category(records: list[dict]) -> list[dict]:
    """按类别汇总（分 → 元），按金额降序。"""
    buckets: dict[str, dict[str, int]] = {}
    for record in records:
        bucket = buckets.setdefault(record["category"], {"total_cents": 0, "count": 0})
        bucket["total_cents"] += int(record["amount_cents"])
        bucket["count"] += 1
    rows = [
        {"category": name, "total": float(cents_to_yuan(v["total_cents"])), "count": v["count"]}
        for name, v in buckets.items()
    ]
    rows.sort(key=lambda row: -row["total"])
    return rows


def _empty_slots(slots: dict) -> dict[str, Any]:
    return {
        "time_range": [slots["start"], slots["end"]],
        "categories": slots["categories"],
        "agg": slots["agg"],
        "group_by": slots["group_by"],
    }


@router.post("/query", summary="自然语言查账")
def query_records(payload: QuestionRequest, conn: Any = Depends(get_db)) -> dict[str, Any]:
    """返回槽位、回答文案与明细表；数字全部由数据库聚合得出。"""
    slots = extract_slots(payload.question)
    start, end_exclusive = slots["start"], slots["end"]
    # 内部左闭右开，对外契约 time_range 为闭区间
    end_inclusive = (date.fromisoformat(end_exclusive) - timedelta(days=1)).isoformat()
    slots_out = _empty_slots(slots)
    slots_out["time_range"] = [start, end_inclusive]

    categories = slots["categories"]
    label = _period_label(start, end_inclusive)
    # 「近 7 天」这类相对区间直接沿用用户口语，比打印两个日期更自然
    relative = re.match(r"近(\d+)(天|个月)", slots.get("time_expr") or "")
    if relative:
        label = f"最近 {relative.group(1)} {relative.group(2)}"

    # ---------------- 趋势：按天汇总
    if slots["agg"] == "trend":
        records = dao.query_records(
            conn, start=start, end=end_exclusive, confirmed=1, user_id=DEFAULT_USER_ID
        )
        if not records:
            return ok(
                {
                    "slots": slots_out,
                    "answer_text": f"{label}，没有已确认的消费记录。",
                    "table": [],
                }
            )
        by_day: dict[str, dict[str, int]] = {}
        for record in records:
            day = record["occurred_at"][:10]
            bucket = by_day.setdefault(day, {"total_cents": 0, "count": 0})
            bucket["total_cents"] += int(record["amount_cents"])
            bucket["count"] += 1
        table = [
            {"date": day, "total": float(cents_to_yuan(v["total_cents"])), "count": v["count"]}
            for day, v in sorted(by_day.items())
        ]
        peak = max(table, key=lambda row: row["total"])
        total_cents = sum(v["total_cents"] for v in by_day.values())
        answer = (
            f"{label}，共支出 {_money(total_cents)}，共 {len(records)} 笔；"
            f"最高的一天是 {peak['date']}（{_money_yuan(peak['total'])}）。"
        )
        return ok({"slots": slots_out, "answer_text": answer, "table": table})

    # ---------------- 其余：先取区间内真实流水（按类别过滤）
    if categories:
        records = []
        for category in categories:
            records.extend(
                dao.query_records(
                    conn,
                    start=start,
                    end=end_exclusive,
                    category=category,
                    confirmed=1,
                    user_id=DEFAULT_USER_ID,
                )
            )
    else:
        records = dao.query_records(
            conn, start=start, end=end_exclusive, confirmed=1, user_id=DEFAULT_USER_ID
        )

    if not records:
        return ok(
            {
                "slots": slots_out,
                "answer_text": f"{label}，没有找到已确认的消费记录，先记几笔再问我吧。",
                "table": [],
            }
        )

    rows = _group_by_category(records)
    total_cents = sum(int(record["amount_cents"]) for record in records)

    # ---------------- 哪类花得最多
    if slots["agg"] == "top":
        top = rows[0]
        share = top["total"] / float(cents_to_yuan(total_cents)) if total_cents else 0.0
        answer = (
            f"{label}，花得最多的是「{top['category']}」，共 {_money_yuan(top['total'])}"
            f"（{share * 100:.0f}%），{top['count']} 笔。"
        )
        return ok({"slots": slots_out, "answer_text": answer, "table": rows})

    # ---------------- 汇总：指定类别或全部
    if categories:
        category_text = "、".join(f"「{name}」" for name in known_categories() if name in categories)
        answer = (
            f"{label}，{category_text}共支出 {_money(total_cents)}，共 {len(records)} 笔。"
        )
    else:
        answer = f"{label}，共支出 {_money(total_cents)}，共 {len(records)} 笔。"
        if len(rows) > 1:
            top = rows[0]
            answer += (
                f"其中「{top['category']}」花得最多，"
                f"{_money_yuan(top['total'])}。"
            )

    return ok({"slots": slots_out, "answer_text": answer, "table": rows})
