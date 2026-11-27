"""接口冒烟自检：以「前端客户端」的调用方式跑一遍全部接口，验证字段对齐。

用法（先启动后端 8000）：
    python scripts/smoke_api.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
os.environ["MOCK_FALLBACK"] = "0"
sys.path.insert(0, str(PROJECT_ROOT / "frontend"))

import api  # noqa: E402  前端客户端（与界面共用同一套调用）

# UI 层已从单一 components.py 拆分为 cards / charts 等模块（v2.2 设计系统改造），
# 渲染函数按职责迁移；冒烟脚本要跟着新的模块路径走，否则一运行就 ImportError。
# 用兼容别名保留脚本里原有的 components.xxx 调用，减少后续维护成本。
from ui import cards, charts  # noqa: E402

class _Components:  # noqa: D101 —— 仅用于聚合迁移后的渲染函数
    format_yuan = staticmethod(cards.format_yuan)
    format_ratio = staticmethod(cards.format_ratio)
    budget_progress = staticmethod(cards.budget_progress)
    pie_spec = staticmethod(charts.pie_spec)
    trend_spec = staticmethod(charts.trend_spec)


components = _Components()


def show(name: str, value) -> None:
    print(f"[ok] {name}: {value}")


def main() -> int:
    month = "2026-11"

    show("health", api.health())
    show("categories", api.list_categories())

    draft = api.parse_record("昨天打车 32 块", "smoke")
    show("parse_record", {k: draft.get(k) for k in ("draft_id", "fields", "confidence")})

    page = api.list_records(page=1, size=10)
    show("list_records", {"total": page.get("total"), "pages": page.get("pages")})

    summary = api.stats_summary(month)
    show("stats_summary", summary)
    show("render_metric", "ok" if components.format_yuan(summary["total"]) else "fail")

    by_category = api.stats_by_category(month=month)
    show("stats_by_category", by_category["items"][:2])
    spec = components.pie_spec(by_category["items"])
    slices = spec["option"]["series"][0]["data"]
    show("pie_spec_slices", len(slices))

    trend = api.stats_trend(7)
    trend_spec = components.trend_spec(trend["items"])
    show("stats_trend_items", len(trend["items"]))
    show("trend_spec_points", len(trend_spec["option"]["series"][0]["data"]))

    save = api.save_budget(month, "娱乐", 100)
    show("save_budget", save)
    budgets = api.list_budgets(month)
    show("list_budgets", len(budgets["items"]))
    alerts = api.budget_alerts(month)
    show("budget_alerts", [(i["category"], i["status"], components.format_ratio(i["used_ratio"])) for i in alerts["items"]])
    show("budget_progress_html", "ok" if components.budget_progress(alerts["items"]) else "fail")

    answer = api.query("这个月哪类花得最多？", "smoke")
    show("query", answer.get("answer_text"))

    # 第二周新增：主动提醒横幅数据源 + 语音能力探测
    alerts = api.request("GET", "/alerts", params={"month": month}) or {}
    show("alerts", [
        (item["level"], item["title"], item["is_read"]) for item in alerts.get("items", [])
    ])
    show("alerts_unread", alerts.get("unread_count"))
    voice = api.request("GET", "/voice/status") or {}
    show("voice_status", voice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
