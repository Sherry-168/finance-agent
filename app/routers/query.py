"""自然语言查账：LLM/规则只抽槽位，算数一律由 dao + logic.stats 完成。

前端只渲染 answer_text 与 table，因此这里负责把真实统计结果拼成回答文案，
不返回任何由模型口算出来的金额。
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import DEFAULT_USER_ID
from app.core.response import ok
from app.core.validation import next_day, yuan
from app.core.db import get_db
from app.services.nlp import parse_query_slots
from db import dao
from logic import stats

router = APIRouter(tags=["query"])


class QuestionRequest(BaseModel):
    """查账入参。"""

    question: str = Field(..., min_length=1, description="自然语言问题，如「我上个月吃饭花了多少？」")
    session_id: str | None = None


def _time_label(start: str, end: str) -> str:
    """把绝对区间还原成简短中文标签，仅用于回答文案。"""
    start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    next_month = (
        date(start_date.year + 1, 1, 1)
        if start_date.month == 12
        else date(start_date.year, start_date.month + 1, 1)
    )
    if start_date.day == 1 and end_date == next_month - timedelta(days=1):
        return f"{start_date.year} 年 {start_date.month} 月" if start_date.year != date.today().year else f"{start_date.month} 月"
    if start_date == end_date:
        return f"{start_date.month} 月 {start_date.day} 日"
    return f"{start} 至 {end}"


def _category_label(categories: list[str]) -> str:
    if not categories:
        return ""
    return "、".join(categories)


@router.post("/query", summary="自然语言查账")
def query_records(
    payload: QuestionRequest, conn: sqlite3.Connection = Depends(get_db)
) -> dict[str, Any]:
    """返回槽位、回答文案与按类别汇总的表格（仅 confirmed=1）。"""
    slots = parse_query_slots(payload.question)
    start, end = slots["start"], slots["end"]
    filters = {
        "start": start,
        "end": next_day(end),
        "confirmed": 1,
        "user_id": DEFAULT_USER_ID,
    }

    rows: list[dict[str, Any]] = []
    if slots["categories"]:
        for category in slots["categories"]:
            rows.extend(dao.query_records(conn, category=category, **filters))
    else:
        rows.extend(dao.query_records(conn, **filters))

    groups = stats.by_category(rows)
    total_cents = stats.total_expense(rows)
    table = [
        {"category": item["category"], "total": yuan(item["total_cents"]), "count": item["count"]}
        for item in groups
    ]

    label = _time_label(start, end)
    category_text = _category_label(slots["categories"])
    subject = f"{label}{category_text}"
    if slots["agg"] == "top" and groups:
        top = groups[0]
        answer = (
            f"你{subject}支出最多的是「{top['category']}」，"
            f"共 ¥{yuan(top['total_cents']):,.2f}，{top['count']} 笔。"
        )
    elif rows:
        answer = f"你{subject}共支出 ¥{yuan(total_cents):,.2f}，共 {len(rows)} 笔。"
    else:
        answer = f"你{subject}没有找到已确认的支出记录。"

    return ok(
        {
            "slots": {
                "time_range": [start, end],
                "categories": slots["categories"],
                "agg": slots["agg"],
                "group_by": slots["group_by"],
            },
            "answer_text": answer,
            "table": table,
        }
    )
