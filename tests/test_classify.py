"""规则分类单元测试。"""
from logic import classify


def test_rule_classify_hit():
    assert classify.classify("昨天打车32块") == "交通"
    assert classify.classify("午饭 火锅") == "餐饮"


def test_rule_classify_fallback():
    assert classify.classify("xyz123") == "其他"


def test_normalize_valid():
    assert classify.normalize_category("餐饮") == "餐饮"


def test_normalize_invalid():
    assert classify.normalize_category("不存在的") == "其他"
    assert classify.normalize_category(None) == "其他"


def test_known_categories():
    assert set(classify.known_categories()) == {"餐饮", "交通", "购物", "居住", "娱乐", "医疗", "教育", "其他"}
