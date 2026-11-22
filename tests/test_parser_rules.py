"""解析接缝的单元测试：无 LLM Key 时的规则兜底行为。

覆盖考核要求的两个红线：
- 金额换算（「3k」「三十二块」）由代码完成；
- 时间缺失返回 None 交给反问，绝不默认今天。
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.adapters import parser


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """强制走规则分支，避免测试环境存在 Key 时产生真实网络请求。"""
    monkeypatch.setattr(parser, "has_llm_key", lambda: False)


def test_parse_yesterday_taxi():
    fields = parser.parse_text("昨天打车32块")
    assert fields["amount"] == 32.0
    assert fields["category"] == "交通"
    assert fields["occurred_at"] == (dt.date.today() - dt.timedelta(days=1)).isoformat()


def test_parse_chinese_numeral():
    fields = parser.parse_text("三十二块吃火锅")
    assert fields["amount"] == 32.0
    assert fields["category"] == "餐饮"
    assert fields["occurred_at"] is None  # 没说时间就不能猜


def test_parse_k_unit():
    fields = parser.parse_text("1.5k 交房租")
    assert fields["amount"] == 1500.0
    assert fields["category"] == "居住"


def test_parse_missing_amount():
    fields = parser.parse_text("奶茶")
    assert fields["amount"] is None


def test_parse_date_not_treated_as_amount():
    """「11月14日」里的 11 不能被当成金额。"""
    fields = parser.parse_text("11月14日买了一双鞋 199")
    today = dt.date.today()
    year = today.year if 11 <= today.month else today.year - 1
    assert fields["amount"] == 199.0
    assert fields["category"] == "购物"
    assert fields["occurred_at"] == dt.date(year, 11, 14).isoformat()


def test_relative_week_is_last_calendar_week():
    """「上周五」必须是上周的周五，不是从今天往回最近的周五。"""
    fixed = dt.date(2026, 11, 22)  # 周日
    assert parser._extract_date("上周五和同事聚餐", fixed) == "2026-11-13"
    assert parser._extract_date("上周六唱 KTV", fixed) == "2026-11-14"
    assert parser._extract_date("本周一开会", fixed) == "2026-11-16"


def test_labeled_month_day():
    fixed = dt.date(2026, 11, 22)
    assert parser._extract_date("这个月 1 号付房租", fixed) == "2026-11-01"
    assert parser._extract_date("上月 15 号交电费", fixed) == "2026-10-15"
    assert parser._extract_date("下月 3 日", fixed) == "2026-12-03"


def test_cross_year_month_day():
    """补记过去账单：当前月份小于所说月份时按去年处理。"""
    assert parser._extract_date("11 月 5 日交话费", dt.date(2026, 1, 10)) == "2025-11-05"
    assert parser._extract_date("1 月 5 日交话费", dt.date(2026, 12, 10)) == "2026-01-05"


def test_chinese_decimal_amount():
    fields = parser.parse_text("昨天坐公交两块五")
    assert fields["amount"] == 2.5
    assert fields["category"] == "交通"


def test_meaningless_input_is_rejected():
    assert parser.parse_text("哈哈哈哈哈哈哈哈")["_rejected"] is True
    assert parser.parse_text("今天天气怎么样？帮我写一首诗")["_rejected"] is True
    # 缺金额但说了「水果」仍走澄清，不是拒绝
    assert "_rejected" not in parser.parse_text("昨天买了个杯子和一些水果")


def test_meal_keyword_from_demo_case():
    assert parser.parse_text("今天中午吃了碗牛肉面 28 块")["category"] == "餐饮"
    assert parser.parse_text("11 月 5 日交了话费 39 元")["category"] == "居住"
