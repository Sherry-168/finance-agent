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

from ui import components  # noqa: E402  前端渲染函数，用于校验字段是否被正确消费


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
