"""查账槽位抽取的回归用例（纯函数，固定基准日期避免随时间漂移）。"""
from datetime import date

from logic.query_parser import extract_slots

TODAY = date(2026, 11, 18)


def test_last_month_food_sum():
    slots = extract_slots("我上个月吃饭花了多少？", TODAY)
    assert slots["time_expr"] == "上月"
    assert (slots["start"], slots["end"]) == ("2026-10-01", "2026-11-01")
    assert slots["categories"] == ["餐饮"]
    assert slots["agg"] == "sum"
    assert slots["group_by"] is None


def test_top_category_this_month():
    slots = extract_slots("这个月哪类花得最多？", TODAY)
    assert (slots["start"], slots["end"]) == ("2026-11-01", "2026-12-01")
    assert slots["agg"] == "top"
    assert slots["group_by"] == "category"


def test_recent_days_range():
    slots = extract_slots("最近 7 天花了多少", TODAY)
    assert (slots["start"], slots["end"]) == ("2026-11-12", "2026-11-19")


def test_recent_months_range():
    slots = extract_slots("近 3 个月支出多少", TODAY)
    assert slots["start"] == "2026-09-01"
    assert slots["end"] == "2026-11-19"


def test_multi_category():
    slots = extract_slots("上个月吃饭和打车一共花了多少", TODAY)
    assert set(slots["categories"]) == {"餐饮", "交通"}


def test_trend_intent():
    slots = extract_slots("最近30天支出趋势", TODAY)
    assert slots["agg"] == "trend"
    assert slots["group_by"] == "date"


def test_day_before_yesterday_slots():
    slots = extract_slots("前天买咖啡花了多少", TODAY)
    assert slots["time_expr"] == "前天"
    assert (slots["start"], slots["end"]) == ("2026-11-16", "2026-11-17")


def test_unknown_time_falls_back_to_current_month():
    slots = extract_slots("我花了多少钱", TODAY)
    assert slots["time_expr"] == "本月"
    assert (slots["start"], slots["end"]) == ("2026-11-01", "2026-12-01")
