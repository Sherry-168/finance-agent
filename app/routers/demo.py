"""演示数据路由：一键灌入示例账单与预算、清空演示数据。

面向评审场景：无需自造数据即可跑通「明细 / 统计 / 预算」三条主链路。
示例账单优先使用 `demo_bills.csv`（60 笔 / 2 个月，对齐方案文档 §8 与 docs/api.md），
缺失时回退到旧的 `data/sample_transactions.csv`。两者均按 utf-8-sig 读取以兼容 Excel BOM。
"""
from __future__ import annotations

import csv
import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends

from app.core.config import DEFAULT_USER_ID, PROJECT_ROOT
from app.core.db import get_db
from app.core.response import ApiError, NOT_FOUND, ok
from db import dao
from logic.classify import classify
from logic.money import yuan_to_cents

router = APIRouter(prefix="/demo", tags=["demo"])

SAMPLE_CSV = PROJECT_ROOT / "demo_bills.csv"
LEGACY_SAMPLE_CSV = PROJECT_ROOT / "data" / "sample_transactions.csv"

# 演示预算：刻意覆盖 normal / warning / over 三态，方便答辩展示预警效果
_DEMO_BUDGETS: list[tuple[str | None, int]] = [
    (None, 4000),
    ("餐饮", 1200),
    ("交通", 500),
    ("娱乐", 100),
]


def _read_sample_rows() -> list[dict[str, Any]]:
    """读取示例账单 CSV，返回可直接入库的记录列表（金额已转「分」）。"""
    csv_path = SAMPLE_CSV if SAMPLE_CSV.exists() else LEGACY_SAMPLE_CSV
    if not csv_path.exists():
        raise ApiError(NOT_FOUND, "示例账单缺失：demo_bills.csv / data/sample_transactions.csv")

    records: list[dict[str, Any]] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("date") or not row.get("amount"):
                continue
            occurred_at = f"{row['date']} {row.get('time') or '00:00'}:00"
            description = row.get("description") or ""
            merchant = row.get("merchant") or None
            records.append(
                {
                    "amount_cents": yuan_to_cents(row["amount"]),
                    "category": classify(f"{description} {merchant or ''}"),
                    "merchant": merchant,
                    "occurred_at": occurred_at,
                    "source": "demo",
                    "raw_text": description,
                    "note": None,
                }
            )
    return records


def _seed_budgets(conn, month: str) -> None:
    """布置演示预算（同月同维度覆盖），制造预警与超支两种状态。"""
    for category, amount in _DEMO_BUDGETS:
        dao.set_budget(
            conn,
            month=month,
            amount_cents=amount * 100,
            category=category,
            user_id=DEFAULT_USER_ID,
        )


@router.post("/load", summary="灌入演示数据")
def load_demo(conn: Any = Depends(get_db)) -> dict[str, Any]:
    """导入示例账单并布置预算；已导入过则幂等返回，不重复堆数据。"""
    existing = [
        record
        for record in dao.query_records(conn, user_id=DEFAULT_USER_ID)
        if record["source"] == "demo"
    ]
    if existing:
        return ok(
            {
                "records": len(existing),
                "months": len({record["occurred_at"][:7] for record in existing}),
                "receipts": 0,
            }
        )

    records = _read_sample_rows()
    dao.add_records(conn, records, user_id=DEFAULT_USER_ID, confirmed=1)
    _seed_budgets(conn, dt.date.today().strftime("%Y-%m"))

    return ok(
        {
            "records": len(records),
            "months": len({record["occurred_at"][:7] for record in records}),
            "receipts": 0,  # 小票 OCR 第二周接入，此处如实返回 0
        }
    )


@router.post("/reset", summary="清空演示数据")
def reset_demo(conn: Any = Depends(get_db)) -> dict[str, Any]:
    """删除该用户全部流水与预算，返回删除条数（前端需二次确认）。"""
    deleted_records = dao.delete_all_records(conn, user_id=DEFAULT_USER_ID)
    deleted_budgets = dao.delete_all_budgets(conn, user_id=DEFAULT_USER_ID)
    return ok({"deleted_records": deleted_records, "deleted_budgets": deleted_budgets})
