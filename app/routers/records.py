"""记账路由：解析草稿、确认入库、明细增删改查。

分层（详见 docs/backend-api-review.md 与 docs/api.md）：
- 解析走 `app.adapters.parser`（LLM 优先、规则兜底），路由不接触 Prompt；
- 落库走 `db.dao`（金额在 DAO 内「元 ↔ 分」换算），路由不裸写 SQL；
- 对外金额一律「元」浮点，`confirmed` 区分草稿(0)/已确认(1)。
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.adapters.parser import parse_text
from app.core.config import DEFAULT_USER_ID
from app.core.db import get_db
from app.core.response import ApiError, NOT_FOUND, PARAM_ERROR, ok
from db import dao
from logic.classify import normalize_category
from logic.money import cents_to_yuan, yuan_to_cents

router = APIRouter(prefix="/records", tags=["records"])


# ---------------------------------------------------------------- 入参模型


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


class RecordUpdateRequest(BaseModel):
    """修正记录入参：只传需要改的字段，全部可选。"""

    amount: float | None = Field(None, gt=0, description="金额（元）")
    category: str | None = None
    merchant: str | None = None
    occurred_at: str | None = None
    note: str | None = None


# ---------------------------------------------------------------- 内部工具


def _to_item(row: dict[str, Any]) -> dict[str, Any]:
    """DB 行 → 契约明细对象（金额分 → 元）。"""
    return {
        "id": row["id"],
        "amount": float(cents_to_yuan(row["amount_cents"])),
        "category": row["category"],
        "merchant": row["merchant"],
        "occurred_at": row["occurred_at"],
        "note": row["note"],
        "source": row["source"],
        "confirmed": row["confirmed"],
        "created_at": row["created_at"],
    }


def _exclusive_end(end: str | None) -> str | None:
    """契约为「含首尾」，DAO 为左闭右开：日期型 end 顺延一天。"""
    if not end:
        return None
    try:
        day = dt.date.fromisoformat(end)
    except ValueError:
        return end
    return (day + dt.timedelta(days=1)).isoformat()


def _next_draft_id() -> str:
    """草稿 id：只需在同一会话内可回溯，不做持久化。"""
    return f"d_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------- 解析


@router.post("/parse", summary="自然语言解析为草稿（不入库）")
def parse_record(payload: ParseRequest) -> dict[str, Any]:
    """把一句话解析成草稿，绝不入库；槽位不全时以 clarify_question 反问。"""
    fields = parse_text(payload.text)
    values: dict[str, Any] = {
        "amount": fields.get("amount"),
        "category": normalize_category(fields.get("category")),
        "merchant": fields.get("merchant"),
        "occurred_at": fields.get("occurred_at"),
        "note": fields.get("note"),
    }

    missing = [key for key in ("amount", "category", "occurred_at") if not values.get(key)]
    clarify = None
    if not values["amount"]:
        clarify = "这笔大概花了多少钱？"
    elif not values["occurred_at"]:
        clarify = "这是哪天花的呀？（例如：昨天、11 月 14 日）"
    elif not values["category"]:
        clarify = "这笔算哪个类别呢？（餐饮 / 交通 / 购物 / 居住 / 娱乐 / 医疗 / 教育 / 其他）"

    return ok(
        {
            "draft_id": _next_draft_id(),
            "fields": values,
            "confidence": 0.62 if clarify else 0.9,
            "missing_fields": missing,
            "clarify_question": clarify,
        }
    )


# ---------------------------------------------------------------- 入库


@router.post("", summary="确认入库（可带修正值）")
def create_record(payload: RecordCreateRequest, conn: Any = Depends(get_db)) -> dict[str, Any]:
    """确认后写入 records 表，返回自增 id。"""
    record = dao.from_slot_json(
        {
            "amount": payload.amount,
            "category": payload.category,
            "merchant": payload.merchant,
            "occurred_at": payload.occurred_at,
            "note": payload.note,
            "source": payload.source,
            "raw_text": payload.raw_text,
        }
    )
    record_id = dao.add_record(conn, record, user_id=DEFAULT_USER_ID, confirmed=1)
    return ok({"id": record_id, "confirmed": 1})


# ---------------------------------------------------------------- 明细查询


@router.get("", summary="明细列表（分页）")
def list_records(
    start: str | None = Query(None, description="开始日期 YYYY-MM-DD，含首"),
    end: str | None = Query(None, description="结束日期 YYYY-MM-DD，含尾"),
    category: str | None = Query(None, description="类别，省略表示全部"),
    page: int = Query(1, ge=1, description="页码，默认 1"),
    size: int = Query(10, ge=1, le=100, description="每页条数，默认 10"),
    conn: Any = Depends(get_db),
) -> dict[str, Any]:
    """按时间/类别筛选分页返回明细，时间倒序。"""
    end_exclusive = _exclusive_end(end)
    category = normalize_category(category) if category else None

    total = dao.count_records(
        conn, start=start, end=end_exclusive, category=category, user_id=DEFAULT_USER_ID
    )
    pages = max(1, (total + size - 1) // size)
    page = min(page, pages)

    rows = dao.query_records(
        conn,
        start=start,
        end=end_exclusive,
        category=category,
        page=page,
        size=size,
        user_id=DEFAULT_USER_ID,
    )
    # 同一天的多条记录按 id 兜底排序，保证翻页稳定
    rows.sort(key=lambda row: (row["occurred_at"], row["id"]), reverse=True)

    return ok(
        {
            "items": [_to_item(row) for row in rows],
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
        }
    )


# ---------------------------------------------------------------- 修正 / 删除


@router.put("/{record_id}", summary="修正记录")
def update_record(
    record_id: int, payload: RecordUpdateRequest, conn: Any = Depends(get_db)
) -> dict[str, Any]:
    """按需更新字段；金额由「元」换算为「分」后写入。"""
    if dao.get_record(conn, record_id, user_id=DEFAULT_USER_ID) is None:
        raise ApiError(NOT_FOUND, f"记录 {record_id} 不存在")

    updates: dict[str, Any] = {}
    if payload.amount is not None:
        updates["amount_cents"] = yuan_to_cents(payload.amount)
    if payload.category is not None:
        updates["category"] = normalize_category(payload.category)
    if payload.merchant is not None:
        updates["merchant"] = payload.merchant
    if payload.occurred_at is not None:
        updates["occurred_at"] = payload.occurred_at
    if payload.note is not None:
        updates["note"] = payload.note

    if not updates:
        raise ApiError(PARAM_ERROR, "没有需要更新的字段")

    dao.update_record(conn, record_id, updates)
    return ok(_to_item(dao.get_record(conn, record_id, user_id=DEFAULT_USER_ID)))


@router.delete("/{record_id}", summary="删除记录")
def delete_record(record_id: int, conn: Any = Depends(get_db)) -> dict[str, Any]:
    """物理删除一条记录；不存在返回 1002，便于前端提示。"""
    if dao.get_record(conn, record_id, user_id=DEFAULT_USER_ID) is None:
        raise ApiError(NOT_FOUND, f"记录 {record_id} 不存在")
    dao.delete_record(conn, record_id)
    return ok({"deleted": True})
