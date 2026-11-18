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
