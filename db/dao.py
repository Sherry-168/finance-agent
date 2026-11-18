"""数据访问层（DAO）：封装 SQLite 读写，供后端（史雅萱）调用。

对外只暴露函数，不让调用方直接拼 SQL。
金额统一 int（分）；接口层（元）↔ 存储层（分）的换算在本层完成。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from logic.classify import normalize_category
from logic.money import yuan_to_cents

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "db" / "schema.sql"
CATEGORIES_PATH = ROOT / "config" / "categories.json"

DEFAULT_USER = "demo_user"


def connect(db_path: str = "data/finance.db") -> sqlite3.Connection:
    """建立连接。db_path 相对项目根目录。"""
    conn = sqlite3.connect(ROOT / db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """建表并写入分类体系。可重复调用（幂等）。"""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    seed_categories(conn)
    conn.commit()


def seed_categories(conn: sqlite3.Connection) -> None:
    """从 config/categories.json 导入 8 类分类词典。"""
    data = json.loads(CATEGORIES_PATH.read_text(encoding="utf-8"))
    for name, kws in data.items():
        conn.execute(
            "INSERT OR REPLACE INTO categories (name, keywords) VALUES (?, ?)",
            (name, ",".join(kws)),
        )
    conn.commit()


def list_categories(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """返回分类体系（供 Prompt 注入与前端渲染）。"""
    rows = conn.execute("SELECT name, keywords FROM categories ORDER BY name").fetchall()
    return [
        {"name": r["name"], "keywords": [k for k in (r["keywords"] or "").split(",") if k]}
        for r in rows
    ]


def _now() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def from_slot_json(fields: dict[str, Any]) -> dict[str, Any]:
    """把 LLM 输出的槽位 fields 转成可入库的 records 行（草稿 confirmed=0）。

    fields 字段与《项目方案设计文档》§5.1 一致：amount(元) / category / merchant / occurred_at / note。
    金额在此做「元 → 分」换算；category 归一化到 8 类（非法落「其他」）。
    """
    return {
        "amount_cents": yuan_to_cents(fields["amount"]),
        "category": normalize_category(fields.get("category")),
        "merchant": fields.get("merchant"),
        "occurred_at": fields.get("occurred_at") or _now(),
        "source": fields.get("source", "text"),
        "raw_text": fields.get("raw_text"),
        "note": fields.get("note"),
        "confirmed": 0,
    }


def add_record(
    conn: sqlite3.Connection,
    record: dict[str, Any],
    user_id: str = DEFAULT_USER,
    confirmed: int = 1,
) -> int:
    """入库一条记录，返回自增 id。confirmed 默认 1（确认入库），草稿传 0。"""
    cur = conn.execute(
        """INSERT INTO records
           (user_id, amount_cents, category, merchant, occurred_at, source, raw_text, note, confirmed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            int(record["amount_cents"]),
            record.get("category", "其他"),
            record.get("merchant"),
            record["occurred_at"],
            record.get("source", "text"),
            record.get("raw_text"),
            record.get("note"),
            int(confirmed),
        ),
    )
    conn.commit()
    return cur.lastrowid


def add_records(
    conn: sqlite3.Connection,
    records: list[dict[str, Any]],
    user_id: str = DEFAULT_USER,
    confirmed: int = 1,
) -> int:
    """批量入库，返回条数。"""
    return sum(1 for _ in (add_record(conn, r, user_id, confirmed) for r in records))


def get_record(conn: sqlite3.Connection, record_id: int, user_id: str = DEFAULT_USER) -> dict[str, Any] | None:
    """按 id 取单条记录（带 user_id 隔离），不存在返回 None。"""
    row = conn.execute(
        "SELECT * FROM records WHERE id = ? AND user_id = ?", (record_id, user_id)
    ).fetchone()
    return dict(row) if row else None


def count_records(
    conn: sqlite3.Connection,
    start: str | None = None,
    end: str | None = None,
    category: str | None = None,
    confirmed: int | None = None,
    source: str | None = None,
    user_id: str = DEFAULT_USER,
) -> int:
    """与 query_records 同口径的计数（供分页 total 与演示数据幂等判断）。"""
    sql = "SELECT COUNT(*) AS n FROM records WHERE user_id = ?"
    args: list[Any] = [user_id]
    if start:
        sql += " AND occurred_at >= ?"
        args.append(start)
    if end:
        sql += " AND occurred_at < ?"
        args.append(end)
    if category:
        sql += " AND category = ?"
        args.append(category)
    if confirmed is not None:
        sql += " AND confirmed = ?"
        args.append(int(confirmed))
    if source:
        sql += " AND source = ?"
        args.append(source)
    return int(conn.execute(sql, args).fetchone()["n"])


def update_record(conn: sqlite3.Connection, record_id: int, fields: dict[str, Any]) -> None:
    """按 id 更新指定字段（确认草稿、修正金额/类别等）。"""
    allowed = {"amount_cents", "category", "merchant", "occurred_at", "note", "confirmed"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if "category" in updates:
        updates["category"] = normalize_category(updates["category"])
    if not updates:
        return
    sets = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(f"UPDATE records SET {sets} WHERE id = ?", (*updates.values(), record_id))
    conn.commit()


def delete_record(conn: sqlite3.Connection, record_id: int) -> None:
    conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()


def query_records(
    conn: sqlite3.Connection,
    start: str | None = None,
    end: str | None = None,
    category: str | None = None,
    confirmed: int | None = None,
    page: int | None = None,
    size: int | None = None,
    user_id: str = DEFAULT_USER,
) -> list[dict[str, Any]]:
    """按条件查询流水，时间区间左闭右开 [start, end)，按时间倒序，可选分页。"""
    sql = "SELECT * FROM records WHERE user_id = ?"
    args: list[Any] = [user_id]
    if start:
        sql += " AND occurred_at >= ?"
        args.append(start)
    if end:
        sql += " AND occurred_at < ?"
        args.append(end)
    if category:
        sql += " AND category = ?"
        args.append(category)
    if confirmed is not None:
        sql += " AND confirmed = ?"
        args.append(int(confirmed))
    sql += " ORDER BY occurred_at DESC"
    if page is not None and size:
        sql += " LIMIT ? OFFSET ?"
        args.extend([int(size), (int(page) - 1) * int(size)])
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def sum_by_category(
    conn: sqlite3.Connection,
    start: str | None = None,
    end: str | None = None,
    user_id: str = DEFAULT_USER,
) -> list[dict[str, Any]]:
    """数据库层按类别汇总已确认支出（供后端直接取数）。"""
    sql = (
        "SELECT category, SUM(amount_cents) AS total_cents, COUNT(*) AS count "
        "FROM records WHERE user_id = ? AND confirmed = 1"
    )
    args: list[Any] = [user_id]
    if start:
        sql += " AND occurred_at >= ?"
        args.append(start)
    if end:
        sql += " AND occurred_at < ?"
        args.append(end)
    sql += " GROUP BY category ORDER BY total_cents DESC"
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def set_budget(
    conn: sqlite3.Connection,
    month: str,
    amount_cents: int,
    category: str | None = None,
    user_id: str = DEFAULT_USER,
) -> None:
    """设定月度预算。category=None（或空串）表示总额预算。"""
    conn.execute(
        """INSERT INTO budgets (user_id, category, month, amount_cents) VALUES (?, ?, ?, ?)
           ON CONFLICT(user_id, category, month) DO UPDATE SET amount_cents=excluded.amount_cents""",
        (user_id, category or "", month, int(amount_cents)),
    )
    conn.commit()


def get_budget(
    conn: sqlite3.Connection,
    month: str,
    category: str | None = None,
    user_id: str = DEFAULT_USER,
) -> int | None:
    """查询月度预算上限（分），未设置返回 None。"""
    row = conn.execute(
        "SELECT amount_cents FROM budgets WHERE user_id = ? AND month = ? AND category = ?",
        (user_id, month, category or ""),
    ).fetchone()
    return row["amount_cents"] if row else None


def get_budget_row(
    conn: sqlite3.Connection,
    month: str,
    category: str | None = None,
    user_id: str = DEFAULT_USER,
) -> dict[str, Any] | None:
    """返回完整预算行（含 id），供 POST /budgets 回显。"""
    row = conn.execute(
        "SELECT id, month, category, amount_cents FROM budgets "
        "WHERE user_id = ? AND month = ? AND category = ?",
        (user_id, month, category or ""),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "month": row["month"],
        "category": row["category"] or None,
        "amount_cents": row["amount_cents"],
    }


def list_budgets(conn: sqlite3.Connection, month: str, user_id: str = DEFAULT_USER) -> list[dict[str, Any]]:
    """查询某月全部预算；总预算（category=''）排在最前。"""
    rows = conn.execute(
        "SELECT id, month, category, amount_cents FROM budgets "
        "WHERE user_id = ? AND month = ? "
        "ORDER BY CASE WHEN category = '' THEN 0 ELSE 1 END, category",
        (user_id, month),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "month": row["month"],
            "category": row["category"] or None,
            "amount_cents": row["amount_cents"],
        }
        for row in rows
    ]


def budget_alerts(
    conn: sqlite3.Connection,
    month: str,
    user_id: str = DEFAULT_USER,
) -> list[dict[str, Any]]:
    """返回该月各预算的已用 / 上限 / 占比 / 状态（对齐 /budgets/alerts）。"""
    from logic.budget import check_budget
    from logic.stats import total_expense

    rows = conn.execute(
        "SELECT category, amount_cents FROM budgets WHERE user_id = ? AND month = ?",
        (user_id, month),
    ).fetchall()
    start, end = _month_range(month)
    alerts = []
    for r in rows:
        limit = r["amount_cents"]
        if r["category"]:
            spent = total_expense(
                query_records(conn, start, end, category=r["category"], confirmed=1, user_id=user_id)
            )
        else:
            spent = total_expense(query_records(conn, start, end, confirmed=1, user_id=user_id))
        info = check_budget(limit, spent)
        alerts.append({"category": r["category"] or None, "limit_cents": limit, "spent_cents": spent, **info})
    return alerts


def _month_range(month: str) -> tuple[str, str]:
    """'YYYY-MM' → ('YYYY-MM-01', '下月-01')，左闭右开。"""
    y, m = (int(x) for x in month.split("-"))
    if m == 12:
        end = f"{y + 1}-01-01"
    else:
        end = f"{y}-{m + 1:02d}-01"
    return f"{month}-01", end


# ---------------------------------------------------------------- 解析会话（澄清反问多轮上下文）


def load_session(conn: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    """读取会话中暂存的草稿槽位；无记录返回 None。"""
    row = conn.execute(
        "SELECT context FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if not row or not row["context"]:
        return None
    try:
        context = json.loads(row["context"])
    except (TypeError, ValueError):
        return None
    return context if isinstance(context, dict) else None


def save_session(conn: sqlite3.Connection, session_id: str, context: dict[str, Any]) -> None:
    """写入 / 覆盖会话上下文。"""
    conn.execute(
        """INSERT INTO sessions (session_id, context, updated_at)
           VALUES (?, ?, datetime('now', 'localtime'))
           ON CONFLICT(session_id) DO UPDATE SET
             context = excluded.context, updated_at = excluded.updated_at""",
        (session_id, json.dumps(context, ensure_ascii=False)),
    )
    conn.commit()


def delete_session(conn: sqlite3.Connection, session_id: str) -> None:
    """槽位齐全后清理会话，避免下一笔账被旧上下文污染。"""
    conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    conn.commit()


# ---------------------------------------------------------------- 演示数据


def clear_user_data(conn: sqlite3.Connection, user_id: str = DEFAULT_USER) -> dict[str, int]:
    """清空单用户流水与预算（演示重置），返回删除条数。"""
    records = conn.execute("DELETE FROM records WHERE user_id = ?", (user_id,)).rowcount
    budgets = conn.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,)).rowcount
    conn.commit()
    return {"deleted_records": records, "deleted_budgets": budgets}
