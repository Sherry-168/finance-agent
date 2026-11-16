"""预算逻辑单元测试。"""
from logic.budget import check_budget, remind_text, used_ratio


def test_normal():
    r = check_budget(10000, 5000)
    assert r["status"] == "normal"
    assert r["used_ratio"] == 0.5


def test_warning_at_80_percent():
    assert check_budget(10000, 8000)["status"] == "warning"


def test_over():
    r = check_budget(10000, 12000)
    assert r["status"] == "over"
    assert r["remaining_cents"] == -2000


def test_invalid_limit():
    r = check_budget(0, 5000)
    assert r["used_ratio"] is None


def test_used_ratio():
    assert used_ratio(10000, 2500) == 0.25
    assert used_ratio(0, 100) is None


def test_remind_over_text():
    text = remind_text("餐饮", check_budget(10000, 12000))
    assert "超支" in text
    assert "20.00" in text


def test_remind_warning_text():
    text = remind_text(None, check_budget(10000, 8000))
    assert "80%" in text


def test_remind_none():
    assert remind_text("餐饮", check_budget(10000, 1000)) is None
