"""预算接口：设定 / 查询 / 预警。

category 为 null 或空串表示总额预算；状态判断（normal/warning/over）由
logic.budget + DAO 完成，前端只按状态渲染颜色。
"""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.config import DEFAULT_USER_ID
from app.core.db import get_db
from app.core.response import ApiError, ok
from app.core.validation import valid_month, yuan
from db import dao
from logic.classify import is_valid_category, known_categories
from logic.money import yuan_to_cents

router = APIRouter(tags=["budgets"])


class BudgetCreateRequest(BaseModel):
    month: str = Field(..., description="YYYY-MM")
    category: str | None = Field(None, description="8 类之一；null 表示总额预算")
    amount: float = Field(..., gt=0, description="预算上限（元）")


@router.post("/budgets", summary="设定月度预算")
def save_budget(
    payload: BudgetCreateRequest, conn: sqlite3.Connection = Depends(get_db)
) -> dict[str, Any]:
    month = valid_month(payload.month)
    category = payload.category if payload.category not in (None, "", "全部") else None
    if category and not is_valid_category(category):
        raise ApiError(1001, f"类别必须是 8 类之一：{'、'.join(known_categories())}")
    try:
        amount_cents = yuan_to_cents(payload.amount)
    except ValueError as exc:
        raise ApiError(1001, str(exc)) from exc

    dao.set_budget(conn, month, amount_cents, category, user_id=DEFAULT_USER_ID)
    row = dao.get_budget_row(conn, month, category, user_id=DEFAULT_USER_ID)
    return ok(
        {
            "id": row["id"],
            "month": row["month"],
            "category": row["category"],
            "amount": yuan(row["amount_cents"]),
        }
    )


@router.get("/budgets", summary="查询月度预算")
def list_budgets(
    month: str | None = Query(None, description="YYYY-MM，缺省为当前月"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    month = valid_month(month)
    items = [
        {
            "id": row["id"],
            "month": row["month"],
            "category": row["category"],
            "amount": yuan(row["amount_cents"]),
        }
        for row in dao.list_budgets(conn, month, user_id=DEFAULT_USER_ID)
    ]
    return ok({"items": items})


@router.get("/budgets/alerts", summary="预算预警")
def budget_alerts(
    month: str | None = Query(None, description="YYYY-MM，缺省为当前月"),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    month = valid_month(month)
    alerts = dao.budget_alerts(conn, month, user_id=DEFAULT_USER_ID)
    items = [
        {
            "category": alert["category"],
            "amount": yuan(alert["limit_cents"]),
            "used": yuan(alert["spent_cents"]),
            "used_ratio": alert["used_ratio"],
            "status": alert["status"],
        }
        for alert in alerts
    ]
    return ok({"items": items})
