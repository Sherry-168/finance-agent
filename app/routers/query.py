"""自然语言查账。

Day 5 目标：LLM 只抽槽位 → `logic.query_parser` 换算绝对时间区间 →
`dao` / `logic.stats` 聚合算数 → 后端模板拼 `answer_text`。LLM 全程不参与算数。

Day 2 已修正的阻塞缺陷：入参此前用 `ParseRequest`（必填 `text`），
按契约传 `{question}` 会直接 422，导致查账链路完全跑不通。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import ok
from logic.query_parser import resolve_time_range

router = APIRouter(tags=["query"])


class QuestionRequest(BaseModel):
    """查账入参。"""

    question: str = Field(..., min_length=1, description="自然语言问题，如「我上个月吃饭花了多少？」")
    session_id: str | None = None


@router.post("/query", summary="自然语言查账")
def query_records(payload: QuestionRequest) -> dict[str, Any]:
    """返回槽位、回答文案与明细表。"""
    # TODO(Day 5)：槽位由 LLM 给出（时间表达 / 类别 / 聚合方式），再交给 dao/stats 算数。
    # 这里先只跑真实的时间换算，证明「自然语言 → 绝对区间」这一环已可用，
    # 不用编造金额冒充统计结果（评审会核对答案是否来自真实入库数据）。
    start, end_exclusive = resolve_time_range("本月")
    # 内部统一左闭右开；对外契约 time_range 为闭区间，故 end 回退一天
    end_inclusive = (date.fromisoformat(end_exclusive) - timedelta(days=1)).isoformat()
    return ok(
        {
            "slots": {
                "time_range": [start, end_inclusive],
                "categories": [],
                "agg": "sum",
                "group_by": None,
            },
            "answer_text": "查账接口已连通；槽位解析与聚合统计待接入（Day 5）。",
            "table": [],
        }
    )
