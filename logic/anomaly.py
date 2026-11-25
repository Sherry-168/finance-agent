"""异常巡检算法：对比单笔支出与历史均值，找出「畸形消费」。

算法（可解释、可测试）：
1. 按类别计算「历史平均单笔金额」（历史 = 历史区间内的已确认记录，不含本月）。
2. 对待检查的记录，若单笔金额 > 平均单笔 × 阈值倍数 且 > 绝对下限，判定为「异常大额消费」。

默认阈值：3 倍均值 + 100 元（10000 分）下限，可由调用方覆盖。
"""
from __future__ import annotations

from collections import defaultdict

DEFAULT_MULTIPLIER = 3.0
DEFAULT_MIN_CENTS = 10000  # 100 元


def average_per_category(records: list[dict]) -> dict[str, float]:
    """按类别计算平均单笔金额（分）；无记录的类别不出现。"""
    sums: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    for r in records:
        cat = r.get("category") or "其他"
        sums[cat] += int(r["amount_cents"])
        counts[cat] += 1
    return {cat: sums[cat] / counts[cat] for cat in sums}


def detect_anomalies(
    records: list[dict],
    history: list[dict],
    multiplier: float = DEFAULT_MULTIPLIER,
    min_cents: int = DEFAULT_MIN_CENTS,
) -> list[dict]:
    """找出畸形大额消费。

    records：待检查的记录（通常为本月已确认记录）。
    history：用于计算历史均值的记录（通常为近 N 天 / 上月已确认记录）。
    返回 list[dict]：record_id / category / amount_cents / avg_cents / ratio。
    """
    avg = average_per_category(history)
    anomalies = []
    for r in records:
        cat = r.get("category") or "其他"
        base = avg.get(cat)
        if base is None:
            continue
        cents = int(r["amount_cents"])
        if cents > base * multiplier and cents > min_cents:
            anomalies.append(
                {
                    "record_id": r.get("id"),
                    "category": cat,
                    "amount_cents": cents,
                    "avg_cents": round(base),
                    "ratio": round(cents / base, 2),
                }
            )
    return anomalies
