"""预算路由：设定预算、查询预算、超支预警。

口径（docs/api.md §5）：`used` 只累计已确认记录；`used_ratio` 为 0~1 小数；
`status` 由后端判定（normal / warning ≥80% / over ≥100%），前端只渲染颜色。
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.config import DEFAULT_USER_ID
from app.core.db import get_db
from app.core.response import ApiError, PARAM_ERROR, ok
from db import dao
from logic.classify import is_valid_category
from logic.money import cents_to_yuan, yuan_to_cents

router = APIRouter(prefix="/budgets", tags=["budgets"])

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_TOTAL_LABELS = {"", "全部", "总额", "总额（不限类别）"}


class BudgetRequest(BaseModel):
    """设定预算入参：category 为 None 表示总额预算。"""

    month: str = Field(..., description="YYYY-MM")
    category: str | None = Field(None, description="8 类之一；null/空串表示总额预算")
    amount: float = Field(..., gt=0, description="预算金额（元）")


def _check_month(month: str | None) -> str:
    month = month or dt.date.today().strftime("%Y-%m")
    if not _MONTH_RE.match(month):
        raise ApiError(PARAM_ERROR, "月份格式应为 YYYY-MM，例如 2026-11")
    return month


def _normalize_budget_category(category: str | None) -> str | None:
    """总额预算统一用 None，类别预算校验必须落在 8 类内。"""
    if category is None or category.strip() in _TOTAL_LABELS:
        return None
    if not is_valid_category(category):
        raise ApiError(PARAM_ERROR, f"类别必须是 8 类之一：{category}")
    return category


def _yuan(cents: int) -> float:
    return float(cents_to_yuan(cents))


@router.post("", summary="设定月度预算")
def save_budget(payload: BudgetRequest, conn: Any = Depends(get_db)) -> dict[str, Any]:
    """同月同维度覆盖写入，返回含 id 的预算对象。"""
    month = _check_month(payload.month)
    category = _normalize_budget_category(payload.category)

    dao.set_budget(
        conn,
        month=month,
        amount_cents=yuan_to_cents(payload.amount),
        category=category,
        user_id=DEFAULT_USER_ID,
    )
    row = dao.get_budget_row(conn, month=month, category=category, user_id=DEFAULT_USER_ID)
    return ok(
        {
            "id": row["id"] if row else None,
            "month": month,
            "category": category,
            "amount": _yuan(row["amount_cents"]) if row else payload.amount,
        }
    )


@router.get("", summary="查询当月预算")
def list_budgets(
    month: str | None = Query(None, description="YYYY-MM，默认当前月"),
    conn: Any = Depends(get_db),
) -> dict[str, Any]:
    """返回当月全部预算，category 为 null 的那条是总额预算。"""
    month = _check_month(month)
    rows = dao.list_budgets(conn, month=month, user_id=DEFAULT_USER_ID)
    return ok(
        {
            "items": [
                {
                    "id": row["id"],
                    "month": row["month"],
                    "category": row["category"] or None,
                    "amount": _yuan(row["amount_cents"]),
                }
                for row in rows
            ]
        }
    )


@router.get("/alerts", summary="预算预警")
def budget_alerts(
    month: str | None = Query(None, description="YYYY-MM，默认当前月"),
    conn: Any = Depends(get_db),
) -> dict[str, Any]:
    """返回各预算的额度、已用、使用率与状态，供前端进度条渲染。"""
    month = _check_month(month)
    rows = dao.budget_alerts(conn, month=month, user_id=DEFAULT_USER_ID)
    items = [
        {
            "category": row["category"],
            "amount": _yuan(row["limit_cents"]),
            "used": _yuan(row["spent_cents"]),
            "used_ratio": row["used_ratio"],
            "status": row["status"],
        }
        for row in rows
    ]
    return ok({"items": items})
