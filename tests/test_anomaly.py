"""异常巡检算法单元测试。"""
from logic.anomaly import average_per_category, detect_anomalies


def _r(cents, category, rid=None):
    d = {"amount_cents": cents, "category": category}
    if rid is not None:
        d["id"] = rid
    return d


def test_average_per_category():
    history = [_r(2000, "餐饮"), _r(3000, "餐饮"), _r(5000, "交通")]
    avg = average_per_category(history)
    assert avg["餐饮"] == 2500
    assert avg["交通"] == 5000


def test_detect_anomaly_above_threshold():
    history = [_r(2000, "餐饮"), _r(3000, "餐饮")]  # 平均 2500 分
    records = [
        _r(20000, "餐饮", rid=1),   # 200 元 > 3×25 且 > 100 元 → 异常
        _r(9000, "餐饮", rid=2),    # 90 元 > 75 元但 < 100 元下限 → 不算
        _r(4000, "餐饮", rid=3),    # 40 元 < 75 元 → 不算
    ]
    result = detect_anomalies(records, history)
    assert len(result) == 1
    assert result[0]["record_id"] == 1
    assert result[0]["ratio"] == 8.0


def test_detect_anomaly_no_history():
    assert detect_anomalies([_r(20000, "餐饮")], []) == []


def test_custom_thresholds():
    history = [_r(2000, "餐饮")]
    records = [_r(5000, "餐饮", rid=1)]
    result = detect_anomalies(records, history, multiplier=2.0, min_cents=0)
    assert len(result) == 1
