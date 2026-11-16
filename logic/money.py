"""金额工具：统一用「分」整数存储，与「元」互转。

红线：所有算账只使用 int（分）运算，禁止 float 参与金额计算，避免浮点误差。
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def yuan_to_cents(amount) -> int:
    """把「元」转成「分」。接受 int / float / str，如 25 -> 2500、25.5 -> 2550、'25.50' -> 2550。"""
    if isinstance(amount, bool):
        raise ValueError(f"金额不能是布尔值: {amount!r}")
    if isinstance(amount, int):
        if amount < 0:
            raise ValueError(f"金额不能为负: {amount!r}")
        return amount * 100
    try:
        d = Decimal(str(amount))
    except InvalidOperation:
        raise ValueError(f"无法解析金额: {amount!r}")
    if d < 0:
        raise ValueError(f"金额不能为负: {amount!r}")
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cents_to_yuan(cents: int) -> str:
    """把「分」转成「元」字符串，如 2550 -> '25.50'。"""
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return f"{sign}{cents // 100}.{cents % 100:02d}"
