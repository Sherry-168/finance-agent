"""自检脚本：不依赖 pytest，用标准库跑一遍核心逻辑，输出结果。

运行：python scripts/selfcheck.py
"""
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import dao  # noqa: E402
from logic import budget, classify, money, stats  # noqa: E402
from logic.query_parser import resolve_time_range  # noqa: E402

checks = []


def check(name, fn):
    try:
        fn()
        checks.append((name, True, ""))
    except Exception as e:  # noqa: BLE001
        checks.append((name, False, f"{type(e).__name__}: {e}"))


def test_money():
    assert money.yuan_to_cents("25.50") == 2550
    assert money.yuan_to_cents(25.5) == 2550
    assert money.cents_to_yuan(2550) == "25.50"


def test_classify():
    assert classify.classify("昨天打车32块") == "交通"
    assert classify.classify("午饭 火锅") == "餐饮"
    assert classify.classify("无关键词输入") == "其他"
    assert classify.normalize_category("不存在的") == "其他"
    assert classify.normalize_category("餐饮") == "餐饮"
    assert len(classify.known_categories()) == 8


def test_query_parser():
    assert resolve_time_range("上月", today=date(2026, 11, 13)) == ("2026-10-01", "2026-11-01")
    assert resolve_time_range("近7天", today=date(2026, 11, 13))[0] == "2026-11-07"


def test_budget():
    assert budget.check_budget(10000, 5000)["status"] == "normal"
    assert budget.check_budget(10000, 8000)["status"] == "warning"
    assert budget.check_budget(10000, 12000)["status"] == "over"
    assert "超支" in budget.remind_text("餐饮", budget.check_budget(10000, 12000))


def test_stats():
    rs = [
        {"amount_cents": 2500, "category": "餐饮", "occurred_at": "2026-11-03 12:00"},
        {"amount_cents": 3200, "category": "交通", "occurred_at": "2026-11-05 08:00"},
    ]
    assert stats.total_expense(rs) == 5700
    assert stats.by_category(rs)[0]["category"] == "交通"
    assert abs(sum(s["share"] for s in stats.category_share(rs)) - 100.0) < 0.05


def test_dao_roundtrip():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    dao.init_db(conn)
    rec = dao.from_slot_json({"amount": 25, "category": "餐饮", "occurred_at": "2026-11-13 12:30"})
    dao.add_record(conn, rec)
    rows = dao.query_records(conn)
    assert len(rows) == 1 and rows[0]["amount_cents"] == 2500
    dao.set_budget(conn, "2026-11", 50000, category="餐饮")
    alerts = dao.budget_alerts(conn, "2026-11")
    assert alerts[0]["category"] == "餐饮"
    assert alerts[0]["status"] == "normal"
    conn.close()


def test_notify_dedupe():
    """提醒去重：重复扫描不能把「已关闭」的横幅刷回未读。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    dao.init_db(conn)
    dao.set_budget(conn, "2026-11", 10000, category="餐饮")
    dao.add_record(conn, {"amount_cents": 12000, "category": "餐饮", "occurred_at": "2026-11-10 12:00"})

    first = dao.scan_and_notify(conn, month="2026-11")
    assert first["inserted"] == 1
    row = dao.list_notifications(conn, unread_only=True)[0]
    dao.mark_notification_read(conn, row["id"])

    second = dao.scan_and_notify(conn, month="2026-11")
    assert second["inserted"] == 0 and second["updated"] == 1
    assert dao.count_unread_notifications(conn) == 0
    assert len(dao.list_notifications(conn)) == 1  # 不堆积重复行
    conn.close()


check("金额换算", test_money)
check("规则分类", test_classify)
check("查账时间解析", test_query_parser)
check("预算逻辑", test_budget)
check("统计逻辑", test_stats)
check("DAO 入库往返", test_dao_roundtrip)
check("主动提醒去重", test_notify_dedupe)

failed = [c for c in checks if not c[1]]
for name, ok, err in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  <- {err}" if err else ""))
print("-" * 40)
print(f"共 {len(checks)} 项，通过 {len(checks) - len(failed)} 项，失败 {len(failed)} 项")
sys.exit(1 if failed else 0)
