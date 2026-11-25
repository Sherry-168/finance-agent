"""主动提醒生成：把预算警戒、异常巡检的结构化结果转成 notifications。

纯函数，不依赖数据库；落库由 db.dao 完成。
事件驱动：后端在「入库后」或「前端拉取 /alerts 时」调用 dao.scan_and_notify，
本模块负责产出结构化通知项。
"""
from __future__ import annotations

from logic.money import cents_to_yuan


def build_budget_notifications(alerts: list[dict]) -> list[dict]:
    """把 dao.budget_alerts 的结果转成通知。

    alerts 每项含 category / limit_cents / spent_cents / used_ratio / status。
    仅对 warning / over 生成通知，normal 不生成。
    """
    items = []
    for a in alerts:
        status = a["status"]
        if status not in ("warning", "over"):
            continue
        category = a.get("category")
        name = category if category else "总预算"
        used = cents_to_yuan(a["spent_cents"])
        limit = cents_to_yuan(a["limit_cents"])
        if status == "over":
            item = {
                "type": "budget_over",
                "category": category,
                "level": "danger",
                "title": f"{name}已超支",
                "message": f"{name}已支出 ¥{used}，超出预算 ¥{limit}，请注意控制。",
            }
        else:
            ratio = int(a["used_ratio"] * 100)
            item = {
                "type": "budget_warning",
                "category": category,
                "level": "warning",
                "title": f"{name}接近上限",
                "message": f"{name}已使用 {ratio}%（¥{used} / ¥{limit}），请留意。",
            }
        item["data"] = {
            "category": category,
            "limit_cents": a["limit_cents"],
            "spent_cents": a["spent_cents"],
            "used_ratio": a["used_ratio"],
        }
        items.append(item)
    return items


def build_anomaly_notifications(anomalies: list[dict]) -> list[dict]:
    """把异常巡检结果转成通知。"""
    items = []
    for a in anomalies:
        amount = cents_to_yuan(a["amount_cents"])
        avg = cents_to_yuan(a["avg_cents"])
        items.append(
            {
                "type": "anomaly",
                "category": a["category"],
                "level": "danger",
                "title": f"「{a['category']}」出现大额消费",
                "message": (
                    f"这笔 {a['category']} 消费 ¥{amount}，是历史平均单笔 ¥{avg} 的 "
                    f"{a['ratio']} 倍，超出常规，请留意。"
                ),
                "data": {
                    "record_id": a["record_id"],
                    "category": a["category"],
                    "amount_cents": a["amount_cents"],
                    "avg_cents": a["avg_cents"],
                    "ratio": a["ratio"],
                },
            }
        )
    return items
