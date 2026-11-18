"""自然语言槽位解析：LLM 只输出槽位，金额/时间/类别的归一化全部走规则。

未配置 LLM Key 时使用纯规则兜底，保证评审无 Key 环境也能跑通
「昨天打车 32 块」「我上个月吃饭花了多少」这两条核心链路。
LLM 调用失败不中断请求，降级到规则并降低 confidence；
所有算账仍由 dao / logic.stats 完成，这里不产生任何金额统计结果。
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT, has_llm_key
from logic.classify import classify, is_valid_category, known_categories, load_keywords
from logic.query_parser import resolve_time_range

log = logging.getLogger(__name__)

_CN_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}

# 带单位优先，避免把 11 月 14 日里的数字误判为金额
_AMOUNT_PATTERNS = (
    re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>千|万|k|K|w|W|块钱|块|元|rmb|RMB|￥|¥)"),
    re.compile(r"(?P<num>[零〇一二两三四五六七八九十百千万]+)\s*(?P<unit>块钱|块|元)"),
    re.compile(r"[￥¥]\s*(?P<num>\d+(?:\.\d+)?)"),
)
_UNIT_FACTOR = {"千": 1000, "k": 1000, "K": 1000, "万": 10000, "w": 10000, "W": 10000}

_ISO_DATE = re.compile(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})")
_CN_DATE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?")
_RELATIVE_DAYS = {"今天": 0, "今日": 0, "昨天": 1, "昨日": 1, "前天": 2, "大前天": 3}

_MERCHANT_HINTS = {
    "滴滴": "滴滴出行", "瑞幸": "瑞幸咖啡", "星巴克": "星巴克", "美团": "美团",
    "饿了么": "饿了么", "淘宝": "淘宝", "京东": "京东", "拼多多": "拼多多",
    "支付宝": "支付宝", "微信": "微信支付", "中石化": "中石化", "中石油": "中石油",
}

_CATEGORY_ALIASES = {
    "吃饭": "餐饮", "吃东西": "餐饮", "聚餐": "餐饮", "打的": "交通",
    "坐车": "交通", "搭车": "交通", "买东西": "购物", "网购": "购物",
    "看病": "医疗", "买药": "医疗", "上课": "教育", "看电影": "娱乐",
}

_QUERY_TIME_PATTERNS = (
    ("上个月", re.compile(r"上\s*个?月")),
    ("本月", re.compile(r"本\s*月|这个月|这个月里")),
    ("上月", re.compile(r"上月")),
    ("去年", re.compile(r"去年")),
    ("今年", re.compile(r"今年")),
    ("今天", re.compile(r"今天|今日")),
    ("昨天", re.compile(r"昨天|昨日")),
    ("近7天", re.compile(r"(?:近|最近)\s*7\s*天")),
    ("近30天", re.compile(r"(?:近|最近)\s*30\s*天")),
    ("近N天", re.compile(r"(?:近|最近)\s*(\d+)\s*天")),
    ("近3个月", re.compile(r"(?:近|最近)\s*3\s*个?月")),
    ("近6个月", re.compile(r"(?:近|最近)\s*6\s*个?月")),
)

_RECORD_PROMPT = (
    "你是记账解析器，只输出一个 JSON 对象，不要解释、不要 Markdown。"
    "字段：amount(数字，单位元，未知用 null)、category(严格取自这些类别："
    + "、".join(known_categories())
    + ")、merchant(字符串或 null)、occurred_at(YYYY-MM-DD 或「昨天」这类相对时间，未知用 null)、"
    "note(字符串或 null)。不要计算任何金额。"
)
_QUERY_PROMPT = (
    "你是查账槽位解析器，只输出一个 JSON 对象，不要解释、不要 Markdown。"
    "字段：time_expr(如 上个月/本月/近7天/2026年10月)、categories(字符串数组，"
    "严格取自：" + "、".join(known_categories()) + ")、agg(sum/trend/share/top)、"
    "group_by(null 或 category)。不要输出金额、笔数或任何统计结果。"
)


def _cn_to_int(text: str) -> int:
    """把简单中文数字（零~万）转成整数，如 三十二 → 32。"""
    total = section = number = 0
    for char in text:
        if char in _CN_DIGITS:
            number = _CN_DIGITS[char]
        elif char in _CN_UNITS:
            unit = _CN_UNITS[char]
            section += (number or 1) * unit
            number = 0
        elif char == "万":
            total += (section + number) * 10000
            section = number = 0
    return total + section + number


def extract_amount(text: str) -> float | None:
    """从一句话里抽金额（元），支持 32块 / 3k / 三十二块 / ￥45.5。"""
    raw = text or ""
    for pattern in _AMOUNT_PATTERNS:
        for match in pattern.finditer(raw):
            number = match.group("num")
            unit = (match.groupdict().get("unit") or "").lower()
            value = float(_cn_to_int(number)) if any(c in _CN_DIGITS for c in number) else float(number)
            if unit in _UNIT_FACTOR:
                value *= _UNIT_FACTOR[unit]
            if value > 0:
                return round(value, 2)
    return None


def extract_date(text: str, today: date | None = None) -> str | None:
    """抽消费日期；相对词优先于月日，避免「昨天 11 月 14 日」反复横跳。"""
    raw = text or ""
    today = today or date.today()
    for word, offset in _RELATIVE_DAYS.items():
        if word in raw:
            return (today - timedelta(days=offset)).isoformat()
    match = _ISO_DATE.search(raw)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except ValueError:
            return None
    match = _CN_DATE.search(raw)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        for year in (today.year, today.year - 1):
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                continue
    return None


def extract_merchant(text: str) -> str | None:
    for keyword, merchant in _MERCHANT_HINTS.items():
        if keyword in (text or ""):
            return merchant
    return None


def _normalize_amount(value: Any, text: str) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value > 0:
        return round(float(value), 2)
    if isinstance(value, str):
        extracted = extract_amount(value)
        if extracted is not None:
            return extracted
    return extract_amount(text)


def _normalize_category(value: Any, text: str) -> str:
    if is_valid_category(value):
        return str(value)
    if isinstance(value, str) and value:
        for alias, category in _CATEGORY_ALIASES.items():
            if alias in value:
                return category
    for alias, category in _CATEGORY_ALIASES.items():
        if alias in (text or ""):
            return category
    return classify(text)


def _normalize_date(value: Any, text: str) -> str | None:
    if isinstance(value, str) and value.strip():
        found = extract_date(value)
        if found:
            return found
    return extract_date(text)


def _llm_json(prompt: str, text: str) -> dict[str, Any] | None:
    """调用 OpenAI 兼容接口取槽位；失败返回 None，由规则兜底。"""
    if not has_llm_key():
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=LLM_TIMEOUT)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ]
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL, messages=messages, response_format={"type": "json_object"}
            )
        except Exception:  # 部分兼容接口不支持 response_format，退回普通 JSON 输出
            response = client.chat.completions.create(model=LLM_MODEL, messages=messages)
        content = response.choices[0].message.content or ""
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception as exc:  # 无网络 / 配额不足 / 模型违法输出都不应打死接口
        log.warning("LLM 槽位解析失败，降级规则兜底：%s", exc)
        return None


def parse_record_slots(text: str) -> dict[str, Any]:
    """解析一句话为归一化槽位（金额单位元，日期 YYYY-MM-DD）。"""
    llm = _llm_json(_RECORD_PROMPT, text)
    amount = _normalize_amount((llm or {}).get("amount"), text)
    category = _normalize_category((llm or {}).get("category"), text)
    occurred_at = _normalize_date((llm or {}).get("occurred_at"), text)
    merchant = (llm or {}).get("merchant") or extract_merchant(text)
    note = (llm or {}).get("note") or None

    confidence = 0.92 if llm else 0.78
    if amount is None or occurred_at is None:
        confidence = min(confidence, 0.55)
    if category == "其他" and not llm:
        confidence = min(confidence, 0.70)
    return {
        "amount": amount,
        "category": category,
        "merchant": merchant,
        "occurred_at": occurred_at,
        "note": note,
        "confidence": round(confidence, 2),
        "source": "llm" if llm else "rule",
    }


def _rule_time_expr(question: str) -> str:
    for expr, pattern in _QUERY_TIME_PATTERNS:
        match = pattern.search(question or "")
        if not match:
            continue
        if expr == "近N天":
            return f"近{match.group(1)}天"
        return expr
    year_month = re.search(r"(20\d{2})\s*[年-/]\s*(1[0-2]|0?[1-9])\s*月?", question or "")
    if year_month:
        return f"{year_month.group(1)}-{int(year_month.group(2)):02d}"
    month_day = re.search(r"(?<!\d)(1[0-2]|0?[1-9])\s*月", question or "")
    if month_day:
        return f"{int(month_day.group(1)):02d}月"
    return "本月"


def _resolve_time_range(time_expr: str) -> tuple[str, str]:
    """返回对外闭区间 [start, end]，内部复用 query_parser 的左闭右开。"""
    expr = (time_expr or "").strip()
    matched = re.fullmatch(r"(20\d{2})[-/年]\s*(\d{1,2})\s*月?", expr)
    if matched:
        year, month = int(matched.group(1)), int(matched.group(2))
        if 1 <= month <= 12:
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            return start.isoformat(), (end - timedelta(days=1)).isoformat()
    matched = re.fullmatch(r"(\d{1,2})\s*月", expr)
    if matched:
        today = date.today()
        year = today.year - 1 if int(matched.group(1)) > today.month else today.year
        start = date(year, int(matched.group(1)), 1)
        end = date(year + 1, 1, 1) if start.month == 12 else date(year, start.month + 1, 1)
        return start.isoformat(), (end - timedelta(days=1)).isoformat()
    start, end_exclusive = resolve_time_range(expr)
    return start, (date.fromisoformat(end_exclusive) - timedelta(days=1)).isoformat()


def _rule_categories(question: str) -> list[str]:
    found: list[str] = []
    for keyword, category in _CATEGORY_ALIASES.items():
        if keyword in (question or "") and category not in found:
            found.append(category)
    for category, keywords in load_keywords().items():
        if category == "其他" or category in found:
            continue
        if category in (question or "") or any(kw and kw in (question or "") for kw in keywords):
            found.append(category)
    return found


def _normalize_categories(value: Any, question: str) -> list[str]:
    candidates: list[str] = []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = [str(item) for item in value if item]
    result: list[str] = []
    for candidate in candidates:
        category = _normalize_category(candidate, question)
        if category != "其他" and category not in result:
            result.append(category)
    if not result:
        result = _rule_categories(question)
    return result


def _rule_agg(question: str) -> str:
    text = question or ""
    if any(word in text for word in ("最多", "最高", "排行", "排名", "哪种花")):
        return "top"
    if any(word in text for word in ("占比", "比例", "构成", "分布")):
        return "share"
    if any(word in text for word in ("趋势", "走势", "每天", "每日")):
        return "trend"
    return "sum"


def _rule_group_by(question: str) -> str | None:
    if any(word in (question or "") for word in ("分类", "各类", "分别", "哪个类别", "按类别")):
        return "category"
    return None


def parse_query_slots(question: str) -> dict[str, Any]:
    """把自然语言问题转成查账槽位；不返回任何金额或统计结果。"""
    llm = _llm_json(_QUERY_PROMPT, question)
    raw = llm or {}
    time_expr = str(raw.get("time_expr") or "").strip() or _rule_time_expr(question)
    start, end = _resolve_time_range(time_expr)
    agg = str(raw.get("agg") or "").strip().lower()
    if agg not in {"sum", "trend", "share", "top"}:
        agg = _rule_agg(question)
    group_by = raw.get("group_by")
    if group_by not in (None, "category"):
        group_by = _rule_group_by(question)
    return {
        "time_expr": time_expr,
        "start": start,
        "end": end,
        "categories": _normalize_categories(raw.get("categories"), question),
        "agg": agg,
        "group_by": group_by,
        "source": "llm" if llm else "rule",
    }
