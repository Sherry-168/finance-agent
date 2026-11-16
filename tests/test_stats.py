"""统计逻辑单元测试。"""
from logic.stats import (
    by_category,
    category_share,
    filter_by_period,
    month_over_month,
    summary,
    top_category,
    total_expense,
    trend,
)


def _r(cents, category, t):
    return {"amount_cents": cents, "category": category, "occurred_at": t}


R = [
    _r(2500, "餐饮", "2026-11-03 12:15"),
    _r(3200, "交通", "2026-11-05 08:40"),
    _r(8990, "购物", "2026-11-07 20:10"),
    _r(1550, "餐饮", "2026-11-08 15:30"),
]


def test_total_expense():
    assert total_expense(R) == 2500 + 3200 + 8990 + 1550


def test_by_category_desc():
    result = by_category(R)
    assert result[0]["category"] == "购物"
    assert {r["category"] for r in result} == {"购物", "餐饮", "交通"}


def test_category_share_sum_to_100():
    assert abs(sum(s["share"] for s in category_share(R)) - 100.0) < 0.05


def test_filter_by_period_left_closed_right_open():
    got = filter_by_period(R, start="2026-11-05", end="2026-11-08")
    assert [r["occurred_at"] for r in got] == ["2026-11-05 08:40", "2026-11-07 20:10"]


def test_trend_day_aggregation():
    got = trend(R, granularity="day")
    assert got[0] == {"period": "2026-11-03", "total_cents": 2500}


def test_summary():
    s = summary(R)
    assert s["total_cents"] == 16240
    assert s["count"] == 4
    assert s["daily_avg_cents"] == round(16240 / 4)


def test_month_over_month_change():
    cur = [_r(10000, "餐饮", "2026-11-01 00:00")]
    prev = [_r(8000, "餐饮", "2026-10-01 00:00")]
    assert month_over_month(cur, prev)["change_pct"] == 25.0


def test_top_category():
    assert top_category(R, 1)[0]["category"] == "购物"
