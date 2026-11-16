"""记账路由：自然语言解析为草稿、确认入库。

当前状态（Day 2）：
- `parse` 仍返回契约示例，解析模块（李语琛）的接入点见函数内 TODO；
- `create` 尚未落库，Day 3 接 `dao.from_slot_json` + `dao.add_record`。
两个缺陷已在 docs/backend-api-review.md 登记，这里只做结构收敛，不改语义。
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import ok

router = APIRouter(prefix="/records", tags=["records"])


class ParseRequest(BaseModel):
    """记账解析入参。"""

    text: str = Field(..., min_length=1, description="用户原始输入，如「昨天打车32块」")
    session_id: str | None = Field(None, description="澄清反问的会话上下文标识")


class RecordCreateRequest(BaseModel):
    """确认入库入参（金额单位：元）。"""

    amount: float = Field(..., gt=0, description="金额（元），统一记正数支出")
    category: str = Field(..., description="8 类之一，后端负责归一化")
    occurred_at: str = Field(..., description="消费时间，YYYY-MM-DD 或 YYYY-MM-DD HH:MM")
    raw_text: str = Field(..., description="用户原始输入 / OCR 原文，用于溯源")
    merchant: str | None = None
    note: str | None = None
    draft_id: str | None = Field(None, description="草稿 id，便于回溯来源")
    source: Literal["text", "ocr", "voice", "manual", "demo"] = Field(
        "text", description="录入来源，落库时写入 records.source"
    )


@router.post("/parse", summary="自然语言解析为草稿（不入库）")
def parse_record(payload: ParseRequest) -> dict[str, Any]:
    """把一句话解析成草稿，绝不入库；槽位不全时以 clarify_question 反问。"""
    # TODO(Day 3)：替换为 parse_text(payload.text, payload.session_id)
    #   LLM 只输出槽位 JSON → logic.classify.normalize_category 校验类别
    #   → logic.money 换算金额 → 缺金额/缺时间返回 clarify_question（不猜数）
    draft = {
        "draft_id": "d_001",
        "fields": {
            "amount": 32.0,
            "category": "交通",
            "merchant": None,
            "occurred_at": "2026-11-14",
            "note": None,
        },
        "confidence": 0.95,
        "missing_fields": [],
        "clarify_question": None,
    }
    return ok(draft)


@router.post("", summary="确认入库（可带修正值）")
def create_record(payload: RecordCreateRequest) -> dict[str, Any]:
    """确认后写入 records 表。Day 3 接 DAO，当前仍返回固定 id。"""
    # TODO(Day 3)：落库
    #   record = dao.from_slot_json(payload.model_dump())
    #   record_id = dao.add_record(conn, record, confirmed=1)
    return ok({"id": 101, "confirmed": 1})
