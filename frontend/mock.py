"""本地 Mock 数据源。

仅在后端接口未就绪时驱动 UI 自测与演示（config.MOCK_FALLBACK 控制）。
真实解析、分类、算账一律由后端完成，本模块不参与生产链路。
"""

from __future__ import annotations

import datetime as dt
import re

NOTICE = "演示模式：未连接后端，当前展示的是本地模拟数据"

_CATEGORY_KEYWORDS = {
    "餐饮": ["吃饭", "午饭", "晚饭", "早餐", "外卖", "奶茶", "咖啡", "火锅", "夜宵", "餐"],
    "交通": ["打车", "出租车", "滴滴", "地铁", "公交", "高铁", "火车", "加油", "停车", "机票"],
    "购物": ["买了", "购物", "衣服", "鞋", "淘宝", "京东", "超市", "日用品"],
    "居住": ["房租", "水电", "物业", "燃气", "宽带", "暖气"],
    "娱乐": ["电影", "游戏", "唱歌", "KTV", "演出", "健身", "旅游"],
    "医疗": ["医院", "买药", "挂号", "体检", "看病", "药店"],
    "教育": ["课程", "学费", "培训", "教材", "考试", "网课"],
}

_UNIT_FACTOR = {"k": 1000, "千": 1000, "w": 10000, "万": 10000}
_NUM = re.compile(r"(\d+(?:\.\d+)?)\s*(k|w|千|万|块|元|rmb|￥|¥)?", re.IGNORECASE)
_DAY_OFFSET = {"今天": 0, "昨天": 1, "前天": 2, "大前天": 3}
_MONTH_DAY = re.compile(r"(\d{1,2})\s*[月/-]\s*(\d{1,2})")


def _extract_amount(text: str) -> float | None:
    """优先取带货币单位的数字，其次取第一个数字。"""
    fallback = None
    for number, unit in _NUM.findall(text):
        value = float(number)
        unit = (unit or "").lower()
        if unit in _UNIT_FACTOR:
            return value * _UNIT_FACTOR[unit]
        if unit:
            return value
        if fallback is None:
            fallback = value
    return fallback


def _extract_category(text: str) -> str | None:
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(word.lower() in text.lower() for word in keywords):
            return category
    return None


def _extract_date(text: str) -> str | None:
    today = dt.date.today()
    for word, offset in _DAY_OFFSET.items():
        if word in text:
            return (today - dt.timedelta(days=offset)).isoformat()
    matched = _MONTH_DAY.search(text)
    if matched:
        month, day = int(matched.group(1)), int(matched.group(2))
        try:
            return dt.date(today.year, month, day).isoformat()
        except ValueError:
            return None
    return None


def parse_record(text: str, session_id: str) -> dict:
    """模拟 POST /records/parse：返回与后端一致的草稿结构。"""
    amount = _extract_amount(text)
    category = _extract_category(text)
    occurred_at = _extract_date(text)

    fields = {
        "amount": amount,
        "category": category or "其他",
        "merchant": None,
        "occurred_at": occurred_at,
        "note": None,
    }
    missing = [key for key in ("amount", "category", "occurred_at") if not fields.get(key)]

    clarify = None
    if amount is None:
        clarify = "这笔大概花了多少钱？"
    elif occurred_at is None:
        clarify = "这是哪天花的呀？（例如：昨天、11 月 14 日）"

    return {
        "draft_id": f"mock_{abs(hash(text)) % 10000:04d}",
        "fields": fields,
        "confidence": 0.62 if clarify else 0.88,
        "missing_fields": missing,
        "clarify_question": clarify,
    }


def health() -> str:
    return "Mock 模式（未连接后端）"


def query(question: str, session_id: str) -> dict:
    """模拟 POST /query：仅用于气泡流自测，数字不是真实统计。"""
    return {
        "slots": {},
        "answer_text": f"（演示模式）还没连接后端，无法统计「{question}」。"
        "启动后端后即可返回真实结果。",
        "table": [],
    }


def demo_load() -> dict:
    return {"records": 0, "months": 0, "receipts": 0}


def demo_reset() -> dict:
    return {"deleted_records": 0, "deleted_budgets": 0}
