"""主动提醒接口（第二周新增，契约见 docs/api.md §12）。

与 `/budgets/alerts` 的区别（容易混，答辩会被问）
-----------------------------------------------
- `/budgets/alerts`：**算**出来给进度条用的实时使用率，无状态、不落库；
- `/alerts`：**读**notifications 表里已经生成的提醒，带已读状态，是前端顶部横幅的数据源。

数据由蔡适伶的 `dao.scan_and_notify()` 生成（预算警戒 + 异常巡检），
本路由负责三件事：拉取时触发一次扫描（事件驱动）、把金额从「分」转「元」、
提供「关闭单条 / 全部已读」两个动作。
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.config import DEFAULT_USER_ID
from app.core.db import get_db
from app.core.response import ApiError, NOT_FOUND, PARAM_ERROR, ok
from db import dao
from logic.money import cents_to_yuan

router = APIRouter(prefix="/alerts", tags=["alerts"])

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# notifications.data 里以「分」存储的键 → 对外暴露的「元」键（前端只做 ¥ 格式化）
_MONEY_KEYS = {
    "limit_cents": "limit",
    "spent_cents": "used",
    "amount_cents": "amount",
    "avg_cents": "avg",
}


def _check_month(month: str | None) -> str:
    """校验月份；省略时按当前月扫描。"""
    month = month or dt.date.today().strftime("%Y-%m")
    if not _MONTH_RE.match(month):
        raise ApiError(PARAM_ERROR, "月份格式应为 YYYY-MM，例如 2026-11")
    return month


def _money_view(data: Any) -> Any:
    """把 data 里的「分」补一份「元」别名，同时保留原键（老前端不受影响）。

    只加不删：`amount_cents` 仍在，新增 `amount`（元浮点），避免出现「同一字段
    一会儿是分一会儿是元」的静默错误。
    """
    if not isinstance(data, dict):
        return data
    view = dict(data)
    for src, dst in _MONEY_KEYS.items():
        if src in view:
            try:
                view[dst] = float(cents_to_yuan(int(view[src])))
            except (TypeError, ValueError):
                continue
    return view


def _to_item(row: dict[str, Any]) -> dict[str, Any]:
    """DB 行 → 契约提醒对象。"""
    return {
        "id": row["id"],
        "type": row["type"],
        "category": row["category"],
        "level": row["level"],
        "title": row["title"],
        "message": row["message"],
        "data": _money_view(row.get("data")),
        "is_read": int(row.get("is_read") or 0),
        "created_at": row["created_at"],
    }


def _scan(conn: Any, month: str) -> None:
    """触发一次扫描；失败只降级为「读到旧提醒」，不让横幅接口整条报错。"""
    try:
        dao.scan_and_notify(conn, month=month, user_id=DEFAULT_USER_ID)
    except Exception:  # noqa: BLE001 —— 提醒是加分项，不能拖垮前端首页
        return


@router.get("", summary="未读主动提醒（前端横幅数据源）")
def list_alerts(
    month: str | None = Query(None, description="YYYY-MM，默认当前月；决定扫描哪个月的预算"),
    unread_only: bool = Query(True, description="是否只返回未读，默认 true"),
    refresh: bool = Query(True, description="拉取前是否重扫一次，默认 true"),
    conn: Any = Depends(get_db),
) -> dict[str, Any]:
    """返回提醒列表与未读数，`level` 决定横幅颜色（warning 橙 / danger 红）。"""
    month = _check_month(month)
    if refresh:
        _scan(conn, month)

    rows = dao.list_notifications(conn, unread_only=unread_only, user_id=DEFAULT_USER_ID)
    return ok(
        {
            "items": [_to_item(row) for row in rows],
            "unread_count": dao.count_unread_notifications(conn, user_id=DEFAULT_USER_ID),
            "month": month,
        }
    )


@router.post("/{notification_id}/read", summary="标记单条提醒已读")
def read_alert(notification_id: int, conn: Any = Depends(get_db)) -> dict[str, Any]:
    """前端点横幅上的「×」时调用；id 不存在返回 1002。"""
    exists = any(
        row["id"] == notification_id
        for row in dao.list_notifications(conn, user_id=DEFAULT_USER_ID)
    )
    if not exists:
        raise ApiError(NOT_FOUND, f"提醒 {notification_id} 不存在")
    dao.mark_notification_read(conn, notification_id, user_id=DEFAULT_USER_ID)
    return ok(
        {
            "id": notification_id,
            "is_read": 1,
            "unread_count": dao.count_unread_notifications(conn, user_id=DEFAULT_USER_ID),
        }
    )


@router.post("/read-all", summary="全部标记已读")
def read_all_alerts(conn: Any = Depends(get_db)) -> dict[str, Any]:
    """「全部关闭」按钮用：把当前未读一次性置为已读。"""
    rows = dao.list_notifications(conn, unread_only=True, user_id=DEFAULT_USER_ID)
    for row in rows:
        dao.mark_notification_read(conn, row["id"], user_id=DEFAULT_USER_ID)
    return ok({"updated": len(rows), "unread_count": 0})
