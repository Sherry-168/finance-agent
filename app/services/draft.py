"""草稿服务：解析 → 草稿结构 → 确认入库，供 text / ocr / voice 三条链路复用。

为什么单独抽一层
----------------
第二周新增 `/voice` 与真正的 `/records/ocr` 后，三条链路都要回答同样的问题：
「槽位齐不齐？不齐该反问哪句？缺失字段是什么？确认卡怎么渲染？」
把这段契约拼装收在一处，路由只负责取输入与落库，避免三份实现慢慢跑偏。

结构对齐 docs/api.md §2.1（`draft_id` / `fields` / `confidence` / `missing_fields`
/ `clarify_question`），并保证**解析不入库**——入库只在用户确认（或语音演示显式
`auto_commit`）时发生。
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from app.adapters.parser import parse_text
from app.core.config import DEFAULT_USER_ID
from db import dao

# 槽位齐全的最低要求：缺任一项都不能直接入库，必须先反问
REQUIRED_FIELDS = ("amount", "category", "occurred_at")

# 反问文案按「最缺的那个」优先问，与前端确认卡的渲染顺序一致
_CLARIFY = {
    "amount": "这笔大概花了多少钱？",
    "occurred_at": "这是哪天花的呀？（例如：昨天、11 月 14 日）",
    "category": "这笔算哪个类别呢？（餐饮 / 交通 / 购物 / 居住 / 娱乐 / 医疗 / 教育 / 其他）",
}

REJECT_MESSAGE = "我只能帮你记一笔支出哦～比如「昨天打车 32 块」，换个说法试试？"


def next_draft_id() -> str:
    """草稿 id：只需在同一会话内可回溯，不做持久化。"""
    return f"d_{uuid.uuid4().hex[:8]}"


def empty_fields() -> dict[str, Any]:
    """五个槽位全空的标准结构。"""
    return {"amount": None, "category": None, "merchant": None, "occurred_at": None, "note": None}


def missing_fields(fields: dict[str, Any]) -> list[str]:
    """返回缺失的必填槽位（保持 REQUIRED_FIELDS 的固定顺序）。"""
    return [key for key in REQUIRED_FIELDS if not fields.get(key)]


def build_draft_from_fields(
    fields: dict[str, Any],
    *,
    confidence: float | None = None,
    draft_id: str | None = None,
) -> dict[str, Any]:
    """把归一化后的槽位包装成契约草稿（用于多笔拆单，每笔一张确认卡）。"""
    missing = missing_fields(fields)
    clarify = _CLARIFY[missing[0]] if missing else None
    return {
        "draft_id": draft_id or next_draft_id(),
        "fields": {key: fields.get(key) for key in empty_fields()},
        "confidence": confidence if confidence is not None else (0.62 if clarify else 0.9),
        "missing_fields": missing,
        "clarify_question": clarify,
    }


def build_draft(text: str) -> dict[str, Any]:
    """把一句话解析成草稿（**不入库**）。

    非记账输入（灌水 / 写诗 / 套现网贷等越界请求）不会生成空白确认卡，
    而是返回 `action=reject` 与一句引导文案，由前端直接渲染成 AI 气泡。
    """
    fields = parse_text(text)
    if fields.get("_rejected"):
        data = build_draft_from_fields(empty_fields(), confidence=0.0)
        data.update(
            {
                "missing_fields": [],
                "clarify_question": REJECT_MESSAGE,
                "action": "reject",
            }
        )
        return data
    return build_draft_from_fields(fields)


def commit_draft(
    conn: Any,
    fields: dict[str, Any],
    *,
    raw_text: str,
    source: str = "text",
    user_id: str | None = None,
) -> int:
    """把草稿槽位确认入库，返回记录 id。

    槽位不齐时抛 `ValueError`，由路由层转成 1001——绝不悄悄拿今天 / 其他 兜底，
    否则用户会得到一条自己没确认过的账。
    """
    missing = missing_fields(fields)
    if missing:
        raise ValueError(f"槽位不全，不能入库：{', '.join(missing)}")

    record = dao.from_slot_json(
        {
            "amount": fields["amount"],
            "category": fields["category"],
            "merchant": fields.get("merchant"),
            "occurred_at": fields["occurred_at"],
            "note": fields.get("note"),
            "source": source,
            "raw_text": raw_text,
        }
    )
    record_id = dao.add_record(conn, record, user_id=user_id or DEFAULT_USER_ID, confirmed=1)
    refresh_notifications(conn, fields["occurred_at"], user_id=user_id)
    return record_id


def refresh_notifications(conn: Any, occurred_at: str | None, *, user_id: str | None = None) -> None:
    """入库后事件驱动扫一遍预算警戒 + 异常巡检（db-design.md §5 口径）。

    刻意吞掉异常：提醒是加分项，不能因为它把「记账成功」变失败。
    月份取消费发生月——补记上个月的账单应该影响上个月的预算，而不是本月。
    """
    month = (occurred_at or "")[:7]
    if len(month) != 7:
        month = dt.date.today().strftime("%Y-%m")
    try:
        dao.scan_and_notify(conn, month=month, user_id=user_id or DEFAULT_USER_ID)
    except Exception:  # noqa: BLE001 —— 提醒失败不影响记账主链路
        return
