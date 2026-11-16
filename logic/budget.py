"""预算设定与超支提醒（纯函数）。

阈值（对齐 /budgets/alerts 的 status 枚举）：已用 ≥80% 预警 warning，≥100% 超支 over。
"""
from __future__ import annotations

WARNING_THRESHOLD = 0.8


def used_ratio(limit_cents: int, spent_cents: int) -> float | None:
    """消费占比（0~1 以上）；预算上限非法时返回 None。"""
    if limit_cents <= 0:
        return None
    return round(spent_cents / limit_cents, 4)


def check_budget(limit_cents: int, spent_cents: int) -> dict:
    """返回 {status, used_ratio, remaining_cents}。

    status: normal / warning / over；预算上限非法时 used_ratio 与 remaining_cents 为 None。
    """
    if limit_cents <= 0:
        return {"status": "normal", "used_ratio": None, "remaining_cents": None}
    ratio = spent_cents / limit_cents
    if ratio >= 1:
        status = "over"
    elif ratio >= WARNING_THRESHOLD:
        status = "warning"
    else:
        status = "normal"
    return {
        "status": status,
        "used_ratio": round(ratio, 4),
        "remaining_cents": limit_cents - spent_cents,
    }


def remind_text(category: str | None, result: dict) -> str | None:
    """把检查结果转成用户可见的提醒文案；无需提醒返回 None。"""
    status = result["status"]
    if status == "over":
        name = f"「{category}」" if category else "本月总"
        over = -result["remaining_cents"]
        return f"{name}预算已超支 {_yuan(over)} 元，请注意控制。"
    if status == "warning":
        name = f"「{category}」" if category else "本月总"
        return f"{name}预算已使用 {int(result['used_ratio'] * 100)}%，接近上限，请留意。"
    return None


def _yuan(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"
