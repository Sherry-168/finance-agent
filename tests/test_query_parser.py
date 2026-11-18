"""查账时间解析单元测试。"""
from datetime import date

from logic.query_parser import resolve_time_range


def test_last_month():
    start, end = resolve_time_range("上月", today=date(2026, 11, 13))
    assert start == "2026-10-01"
    assert end == "2026-11-01"


def test_this_month():
    start, end = resolve_time_range("本月", today=date(2026, 11, 13))
    assert start == "2026-11-01"
    assert end == "2026-12-01"


def test_last_month_cross_year():
    start, end = resolve_time_range("上月", today=date(2026, 1, 15))
    assert start == "2025-12-01"
    assert end == "2026-01-01"


def test_recent_days():
    start, end = resolve_time_range("近7天", today=date(2026, 11, 13))
    assert start == "2026-11-07"
    assert end == "2026-11-14"


def test_this_week():
    start, end = resolve_time_range("本周", today=date(2026, 11, 13))  # 2026-11-13 是周五
    assert start == "2026-11-09"  # 周一
    assert end == "2026-11-14"


def test_unknown_falls_back_to_this_month():
    start, end = resolve_time_range("随便", today=date(2026, 11, 13))
    assert start == "2026-11-01"
