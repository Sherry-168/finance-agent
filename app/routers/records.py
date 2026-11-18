"""记账路由：解析草稿、确认入库、明细分页与增删改。

金额对外一律「元」（浮点），DAO 内部「分」；时间对外含首尾，传给 DAO 转右开。
解析只生成草稿，必须等前端确认卡提交才写入 records 表。
"""
from __future__ import annotations

import math
import sqlite3
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.config import DEFAULT_USER_ID
from app.core.response import NOT_FOUND, ApiError, ok
from app.core.validation import next_day, valid_date, yuan
from app.core.db import get_db
from app.services.nlp import parse_record_slots
from db import dao
from logic.classify import is_valid_category, known_categories, normalize_category
from logic.money import yuan_to_cents

router = APIRouter(prefix="/records", tags=["records"])

_REQUIRED_SLOTS = ("amount", "category", "occurred_at")
_OPTIONAL_SLOTS = ("merchant", "note")


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
    """修正记录：只更新显式传入的字段（金额单位：元）。"""

    amount: float | None = Field(None, gt=0)
    category: str | None = None
    merchant: str | None = None
    occurred_at: str | None = None
    note: str | None = None


def _record_out(row: dict[str, Any]) -> dict[str, Any]:
    """DAO 行（分）→ 契约记录对象（元）。"""
    return {
        "id": row["id"],
        "amount": yuan(row["amount_cents"]),
        "category": row["category"],
        "merchant": row["merchant"],
        "occurred_at": row["occurred_at"],
        "note": row["note"],
        "source": row["source"],
        "confirmed": row["confirmed"],
        "created_at": row["created_at"],
    }


def _clarify_question(missing: list[str]) -> str:
    if "amount" in missing:
        return "这笔大概花了多少钱？（例如：32 块、3k）"
    if "occurred_at" in missing:
        return "这是哪天花的呀？（例如：昨天、11 月 14 日）"
    return "这笔属于哪一类？（餐饮 / 交通 / 购物 / 居住 / 娱乐 / 医疗 / 教育 / 其他）"


def _merge_context(slots: dict[str, Any], context: dict[str, Any] | None) -> dict[str, Any]:
    """多轮澄清：新语句抽不到的槽位沿用同一会话上一轮的中间结果。"""
    if not context:
        return slots
    previous = context.get("fields") or {}
    for key in (*_REQUIRED_SLOTS, *_OPTIONAL_SLOTS):
        current = slots.get(key)
        prior = previous.get(key)
        # 规则兜底会把没识别出的类别落成「其他」，此时上一轮的明确类别更可信
        missing = current in (None, "") or (key == "category" and current == "其他" and prior not in (None, "", "其他"))
        if missing and prior not in (None, ""):
            slots[key] = prior
    return slots


@router.post("/parse", summary="自然语言解析为草稿（不入库）")
def parse_record(payload: ParseRequest, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    """把一句话解析成草稿；槽位不全时以 clarify_question 反问并暂存上下文。"""
    context = dao.load_session(conn, payload.session_id) if payload.session_id else None
    slots = _merge_context(parse_record_slots(payload.text), context)
    raw_text = " ".join(
        part for part in ((context or {}).get("raw_text"), payload.text) if part
    )

    missing = [key for key in _REQUIRED_SLOTS if slots.get(key) in (None, "")]
    fields = {key: slots.get(key) for key in (*_REQUIRED_SLOTS, *_OPTIONAL_SLOTS)}
    draft = {
        "draft_id": f"d_{uuid.uuid4().hex[:8]}",
        "fields": fields,
        "confidence": slots.get("confidence", 0.7),
        "missing_fields": missing,
        "clarify_question": None,
    }

    if missing:
        draft["clarify_question"] = _clarify_question(missing)
        if payload.session_id:
            dao.save_session(
                conn,
                payload.session_id,
                {
                    "fields": {key: fields.get(key) for key in (*_REQUIRED_SLOTS, *_OPTIONAL_SLOTS)},
                    "raw_text": raw_text,
                },
            )
        return ok(draft)

    if payload.session_id:
        dao.delete_session(conn, payload.session_id)
    return ok(draft)


@router.post("", summary="确认入库（可带修正值）")
def create_record(
    payload: RecordCreateRequest, conn: sqlite3.Connection = Depends(get_db)
) -> dict[str, Any]:
    """确认卡提交后写入 records 表，返回真实自增 id。"""
    occurred_at = valid_date(payload.occurred_at, allow_time=True, field="消费时间")
    if not occurred_at:
        raise ApiError(1001, "消费时间不能为空")
    record = dao.from_slot_json(
        {
            "amount": payload.amount,
            "category": normalize_category(payload.category),
            "merchant": payload.merchant,
            "occurred_at": occurred_at,
            "note": payload.note,
            "source": payload.source,
            "raw_text": payload.raw_text,
        }
    )
    record_id = dao.add_record(conn, record, user_id=DEFAULT_USER_ID, confirmed=1)
    return ok({"id": record_id, "confirmed": 1})


@router.get("", summary="明细分页列表（start/end 含首尾）")
def list_records(
    start: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end: str | None = Query(None, description="结束日期 YYYY-MM-DD（含当天）"),
    category: str | None = Query(None, description="8 类之一，省略表示全部"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """按时间 / 类别筛选并分页；草稿与已确认记录都会返回。"""
    start_date = valid_date(start, field="开始日期")
    end_date = valid_date(end, field="结束日期")
    if start_date and end_date and start_date > end_date:
        raise ApiError(1001, "开始日期不能晚于结束日期")
    if category and not is_valid_category(category):
        raise ApiError(1001, f"类别必须是 8 类之一：{'、'.join(known_categories())}")

    filters = {
        "start": start_date,
        "end": next_day(end_date),
        "category": category,
        "user_id": DEFAULT_USER_ID,
    }
    total = dao.count_records(conn, **filters)
    rows = dao.query_records(conn, page=page, size=size, **filters)
    pages = max(1, math.ceil(total / size))
    return ok({"items": [_record_out(row) for row in rows], "total": total, "page": page, "size": size, "pages": pages})


@router.put("/{record_id}", summary="修正记录")
def update_record(
    record_id: int,
    payload: RecordUpdateRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """按需更新字段；id 不存在返回 1002。"""
    if not dao.get_record(conn, record_id, user_id=DEFAULT_USER_ID):
        raise ApiError(NOT_FOUND, f"记录 {record_id} 不存在")

    fields: dict[str, Any] = {}
    supplied = payload.model_fields_set
    if "amount" in supplied and payload.amount is not None:
        try:
            fields["amount_cents"] = yuan_to_cents(payload.amount)
        except ValueError as exc:
            raise ApiError(1001, str(exc)) from exc
    if "category" in supplied and payload.category is not None:
        fields["category"] = normalize_category(payload.category)
    if "occurred_at" in supplied and payload.occurred_at is not None:
        occurred = valid_date(payload.occurred_at, allow_time=True, field="消费时间")
        if not occurred:
            raise ApiError(1001, "消费时间不能为空")
        fields["occurred_at"] = occurred
    if "merchant" in supplied:
        fields["merchant"] = payload.merchant or None
    if "note" in supplied:
        fields["note"] = payload.note or None

    dao.update_record(conn, record_id, fields)
    return ok(_record_out(dao.get_record(conn, record_id, user_id=DEFAULT_USER_ID)))


@router.delete("/{record_id}", summary="删除记录")
def delete_record(
    record_id: int, conn: sqlite3.Connection = Depends(get_db)
) -> dict[str, Any]:
    """删除单条记录；id 不存在返回 1002。"""
    if not dao.get_record(conn, record_id, user_id=DEFAULT_USER_ID):
        raise ApiError(NOT_FOUND, f"记录 {record_id} 不存在")
    dao.delete_record(conn, record_id)
    return ok({"deleted": True})
