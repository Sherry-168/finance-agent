"""顶部提醒横幅渲染（week2 文档 §2 分层：alerts.py，对应 P1-2）。

规则（P1-2 契约）：
- 任一类别 >100% → 红色「超支」横幅；仅 >80% → 橙色「预警」；全部正常 → 返回空串不占位；
- 按 `category+status` 指纹去重，已读关闭的横幅本会话内不再弹出（gr.State 承载已读集合）；
- used_ratio / status 一律取后端 GET /budgets/alerts，前端不计算。
"""

_TOTAL_LABEL = "总预算"


def alert_key(item: dict) -> str:
    """去重指纹：category（None=总预算）+ status。"""
    category = item.get("category") or _TOTAL_LABEL
    return f"{category}:{item.get('status')}"


def active_alerts(items: list, dismissed=None) -> list[dict]:
    """过滤出需要展示的提醒（状态为 warning/over 且未被用户已读关闭）。"""
    dismissed = set(dismissed or ())
    return [
        item
        for item in items or []
        if item.get("status") in ("warning", "over") and alert_key(item) not in dismissed
    ]


def banner_html(items: list, dismissed=None, notice: str = "") -> str:
    """渲染顶部横幅；无活跃提醒时返回空串（不占位，P1-2 要求）。"""
    active = active_alerts(items, dismissed)
    if not active:
        return ""

    worst = "over" if any(item.get("status") == "over" for item in active) else "warning"
    level_text = "超支提醒" if worst == "over" else "预算预警"

    parts = []
    for item in active:
        name = item.get("category") or _TOTAL_LABEL
        ratio = item.get("used_ratio")
        if isinstance(ratio, (int, float)):
            parts.append(f"{name} 已用 {ratio * 100:.0f}%")
        else:
            parts.append(f"{name} 达到预警线")
    detail = "；".join(parts)

    notice_html = f'<span class="fa-banner-notice">{notice}</span>' if notice else ""
    return (
        f'<div class="fa-banner is-{worst}">'
        f'<span class="fa-banner-icon">{"⛔" if worst == "over" else "⚠️"}</span>'
        f"<b>{level_text}</b>"
        f'<span class="fa-banner-text">{detail}</span>'
        f"{notice_html}"
        "</div>"
    )
