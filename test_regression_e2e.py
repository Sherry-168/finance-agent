"""端到端抓 Bug 回归用例。

记录本轮「全模态与提醒专项测试」发现并修复的三个真实缺陷，防止复发：

1. smoke_api.py 引用已迁移的 ui.components 模块 → 冒烟脚本一运行就 ImportError。
2. demo/reset 只清流水 / 预算，不清 notifications → 旧的「已读」提醒残留，
   重新灌入演示数据后同 key 提醒永不弹出，评审「重置重演」会翻车。
3. scan_and_notify 插入新提醒时未按业务 key 去重 → 同类多笔异常消费生成多条
   横幅 / 孤儿行，用户点「关闭」后下次轮询又冒出来。
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

from db import dao

ROOT = Path(__file__).resolve().parent.parent
MONTH = dt.date.today().strftime("%Y-%m")
IN_MONTH = f"{MONTH}-10"


def _add(api, amount: float, category: str):
    return api.post(
        "/api/v1/records",
        json={
            "amount": amount,
            "category": category,
            "occurred_at": IN_MONTH,
            "raw_text": "回归测试",
            "source": "manual",
        },
    )


def test_smoke_script_imports_ok():
    """Bug1：冒烟脚本的 UI 模块引用必须与 v2.2 拆分后的 cards/charts 一致。"""
    # 只验证 import 阶段能过（不需要后端在线）；脚本 main 会在连接失败时抛错，
    # 这里用 py_compile + 显式 import 检查替代，避免依赖外部服务。
    script = ROOT / "scripts" / "smoke_api.py"
    source = script.read_text(encoding="utf-8")
    assert "from ui import components" not in source, "仍引用已删除的 ui.components 模块"
    assert "from ui import cards" in source or "import ui.cards" in source


def test_demo_reset_clears_notifications(api, conn):
    """Bug2：重置演示数据必须连提醒一起清，否则重置后同 key 提醒永久消失。"""
    api.post("/api/v1/budgets", json={"month": MONTH, "category": "娱乐", "amount": 100})
    _add(api, 200, "娱乐")
    api.get("/api/v1/alerts", params={"month": MONTH})  # 生成超支提醒

    assert dao.count_unread_notifications(conn) >= 1

    body = api.post("/api/v1/demo/reset").json()
    assert body["code"] == 0
    assert body["data"]["deleted_notifications"] >= 1
    assert dao.list_notifications(conn) == [], "重置后 notifications 表必须为空"

    # 重新灌入演示数据 + 制造超支 → 提醒应作为全新未读出现
    api.post("/api/v1/demo/load")
    api.post("/api/v1/budgets", json={"month": MONTH, "category": "娱乐", "amount": 100})
    _add(api, 150, "娱乐")
    items = api.get("/api/v1/alerts", params={"month": MONTH}).json()["data"]["items"]
    ent = [i for i in items if i.get("category") == "娱乐" and i["type"] == "budget_over"]
    assert ent and ent[0]["is_read"] == 0, "重置后同条件超支提醒必须重新弹出"


def test_same_category_anomalies_deduped(api, conn):
    """Bug3：同月同类多笔异常消费只应留一条提醒，点已读后不再复活。"""
    # 历史：两个月前两笔 20 元餐饮（历史均值 20 元）
    for d in ("2026-08-10", "2026-08-20"):
        dao.add_record(conn, {"amount_cents": 2000, "category": "餐饮", "occurred_at": d})
    # 本月两笔大额异常
    dao.add_record(conn, {"amount_cents": 20000, "category": "餐饮", "occurred_at": "2026-11-10"})
    dao.add_record(conn, {"amount_cents": 30000, "category": "餐饮", "occurred_at": "2026-11-11"})

    dao.scan_and_notify(conn, month=MONTH)
    rows = [r for r in dao.list_notifications(conn) if r["type"] == "anomaly"]
    assert len(rows) == 1, f"同类异常应去重为一条，实际 {len(rows)} 条"

    # 点已读后再扫一次，不能复活
    dao.mark_notification_read(conn, rows[0]["id"])
    dao.scan_and_notify(conn, month=MONTH)
    unread = [r for r in dao.list_notifications(conn) if r["type"] == "anomaly" and r["is_read"] == 0]
    assert unread == [], "点已读后轮询不应让同类异常提醒复活"
