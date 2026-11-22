"""自然语言 / 小票文本 → 结构化槽位（fields）。

职责边界（对齐 docs/api.md §2.1 与《项目方案设计文档》§9）：
- 本模块只产出槽位，不写库、不统计、不拼提示文案；
- LLM 优先：有 Key 且输出合法就用；无 Key / 超时 / 输出不合法时退回规则解析；
- 金额换算（「3k」「三十二块」）由代码完成，不让模型算数；
- 时间缺失一律返回 None，由路由层反问，**绝不默认今天**。

换实现只改本文件：李语琛的 Dify 工作流交付后，替换 `_llm_parse()` 的内部实现，
`parse_text()` 的签名与返回结构保持不变，路由 / DAO / 前端无需改动。
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
import re
from typing import Any

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT, has_llm_key
from logic.classify import classify, normalize_category

FIELDS = ("amount", "category", "merchant", "occurred_at", "note")

# ---------------------------------------------------------------- 文本识别规则

_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}

# 带货币单位的数字：「32块」「1.5k」「20 元」
_NUM_WITH_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(k|K|千|w|W|万|块钱|块|元)")
_UNIT_FACTOR = {"k": 1000, "K": 1000, "千": 1000, "w": 10000, "W": 10000, "万": 10000}
# 中文数字 + 货币单位：「三十二块」「一百五」
_CN_WITH_UNIT = re.compile(r"([零一二三四五六七八九十百两]+)\s*(?:块钱|块|元)")
# 去掉日期片段后再找裸数字，避免把「11月14日」的 11 当成金额
_DATE_NOISE = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日号]?|\d{1,2}\s*月\s*\d{1,2}\s*[日号]?|\d{1,2}\s*[-/]\s*\d{1,2}|\d{1,2}\s*[日号]|\d{1,2}:\d{2}")
_DAY_WORDS = {"大前天": 3, "前天": 2, "昨天": 1, "昨日": 1, "今天": 0, "今日": 0}
_DATE_FULL = re.compile(r"(\d{4})\s*[年/-]\s*(\d{1,2})\s*[月/-]\s*(\d{1,2})")
_DATE_MONTH_DAY = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?")
_DATE_SHORT = re.compile(r"(?<!\d)(\d{1,2})\s*[-/]\s*(\d{1,2})(?!\d)")
# 「上周五 / 本周六 / 下周一」：周几按自然周（周一~周日）计算
_DATE_WEEK = re.compile(r"(上|本|这|下)\s*(?:周|星期|礼拜)\s*([一二三四五六日天1-7])")
# 「这个月 1 号 / 上个月 15 号 / 下月 3 日」
_DATE_MONTH_DAY_LABEL = re.compile(r"(这个月|本月|当月|上个月|上月|下个月|下月)\s*(\d{1,2})\s*[日号]")
# 中文小数金额：「两块五」→ 2.5（尾数按「角」处理，可带「毛/角」）
_CN_DECIMAL = re.compile(r"([零一二三四五六七八九十百两]+)\s*(?:块钱|块|元)\s*([零一二三四五六七八九])\s*[毛角]?")
# 记账意图提示：用于区分「缺金额待澄清」与「完全非记账输入」
_EXPENSE_HINT = re.compile(r"买|花|付|交|吃|喝|坐|打|充|消费|开销|支出|付款|缴费|记一笔")
_WEEKDAY_NUM = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
}


def _cn_to_number(text: str) -> float | None:
    """中文数字转阿拉伯数字，覆盖「三十二」「一百零五」「两千」等常见口语表述。"""
    total, section, number, matched = 0, 0, 0, False
    for ch in text:
        if ch in _CN_DIGIT:
            number = _CN_DIGIT[ch]
            matched = True
        elif ch in _CN_UNIT:
            unit = _CN_UNIT[ch]
            section += (number or 1) * unit
            number, matched = 0, True
        elif ch == "万":
            section = (section + number) * 10000
            total, section, number, matched = total + section, 0, 0, True
        else:
            return None
    return float(total + section + number) if matched else None


def _extract_amount(text: str) -> float | None:
    """抽取金额（元）。优先带单位，其次中文数字，最后在去掉日期后的文本里找裸数字。"""
    for number, unit in _NUM_WITH_UNIT.findall(text):
        value = float(number)
        if unit in _UNIT_FACTOR:
            value *= _UNIT_FACTOR[unit]
        return round(value, 2)

    # 「两块五」这类中文小数要先于「两块」匹配，否则 0.5 会被丢掉
    dec = _CN_DECIMAL.search(text)
    if dec:
        whole = _cn_to_number(dec.group(1))
        frac = _CN_DIGIT.get(dec.group(2))
        if whole is not None and frac is not None:
            return round(whole + frac / 10, 2)

    cn = _CN_WITH_UNIT.search(text)
    if cn:
        value = _cn_to_number(cn.group(1))
        if value:
            return round(value, 2)

    cleaned = _DATE_NOISE.sub(" ", text)
    bare = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if bare:
        return round(float(bare.group(1)), 2)
    return None


def _extract_date(text: str, today: dt.date | None = None) -> str | None:
    """抽取消费日期，返回 YYYY-MM-DD；无法识别或日期非法时返回 None（不猜）。"""
    today = today or dt.date.today()

    for word, offset in _DAY_WORDS.items():
        if word in text:
            return (today - dt.timedelta(days=offset)).isoformat()

    # 「上周五」指上周（周一~周日）的周五，不是从今天往回最近的一个周五
    week = _DATE_WEEK.search(text)
    if week:
        prefix, token = week.group(1), week.group(2)
        weekday = _WEEKDAY_NUM.get(token)
        if weekday:
            monday = today - dt.timedelta(days=today.weekday())
            if prefix == "上":
                monday -= dt.timedelta(days=7)
            elif prefix == "下":
                monday += dt.timedelta(days=7)
            try:
                return (monday + dt.timedelta(days=weekday - 1)).isoformat()
            except OverflowError:
                return None

    # 「这个月 1 号」「上个月 15 号」「下月 3 日」
    labeled = _DATE_MONTH_DAY_LABEL.search(text)
    if labeled:
        label, day_text = labeled.group(1), labeled.group(2)
        if label in ("这个月", "本月", "当月"):
            year, month = today.year, today.month
        elif label in ("上个月", "上月"):
            first = today.replace(day=1)
            prev = first - dt.timedelta(days=1)
            year, month = prev.year, prev.month
        else:
            year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        # 遇到「2 月 30 号」这类不存在的日期，收敛到当月最后一天而不是静默丢掉
        day = min(int(day_text), calendar.monthrange(year, month)[1])
        try:
            return dt.date(year, month, day).isoformat()
        except ValueError:
            return None

    for pattern, groups in ((_DATE_FULL, 3), (_DATE_MONTH_DAY, 2), (_DATE_SHORT, 2)):
        match = pattern.search(text)
        if not match:
            continue
        parts = [int(match.group(i)) for i in range(1, groups + 1)]
        if groups == 3:
            year, month, day = parts
        else:
            month, day = parts
            year = today.year
            # 记账多为补记过去的账单：所说月份晚于当前月份时按去年处理
            # （如 1 月说「11 月 5 日」→ 去年 11 月；12 月说「1 月 5 日」→ 今年 1 月）
            if month > today.month:
                year -= 1
        try:
            return dt.date(year, month, day).isoformat()
        except ValueError:
            return None
    return None


def _rule_parse(text: str) -> dict[str, Any]:
    """无 LLM 时的兜底解析：关键词分类 + 规则抽金额与日期。"""
    amount = _extract_amount(text)
    category = classify(text)
    return {
        "amount": amount,
        "category": normalize_category(category),
        "merchant": None,
        "occurred_at": _extract_date(text),
        "note": "AA 分摊" if "aa" in text.lower() else None,
    }


# ---------------------------------------------------------------- LLM 实现


def _build_messages(text: str) -> list[dict[str, str]]:
    """构造抽取 Prompt：只允许输出单笔槽位 JSON，缺字段用 null。"""
    today = dt.date.today().isoformat()
    system = (
        "你是记账助手的信息抽取器。只做一件事：把用户的一句话提取成 JSON 对象，不要解释、不要计算、不要编造。\n"
        f"今天是 {today}。相对时间（昨天/前天/上周五）请换算成具体日期。\n"
        "字段：amount(数字，元，正数)、category(餐饮/交通/购物/居住/娱乐/医疗/教育/其他)、"
        "merchant(商户名或 null)、occurred_at(YYYY-MM-DD 或 null)、note(补充说明或 null)。\n"
        "用户没说的字段一律填 null，禁止猜测；金额用阿拉伯数字，不要带单位。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]


def _strip_code_fence(content: str) -> str:
    """去掉模型偶尔包裹的 ```json 代码块。"""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z]*\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return content.strip()


def _normalize_llm_fields(payload: dict[str, Any]) -> dict[str, Any] | None:
    """把模型输出收敛到契约槽位；金额无法解析或为负则视为不合法。"""
    amount = payload.get("amount")
    if isinstance(amount, str):
        amount = _extract_amount(amount)
    if amount is not None:
        try:
            amount = round(float(amount), 2)
        except (TypeError, ValueError):
            return None
        if amount <= 0:
            return None

    occurred_at = payload.get("occurred_at") or payload.get("date")
    if occurred_at and not re.match(r"^\d{4}-\d{2}-\d{2}", str(occurred_at)):
        occurred_at = _extract_date(str(occurred_at))

    return {
        "amount": amount,
        "category": normalize_category(payload.get("category")),
        "merchant": payload.get("merchant"),
        "occurred_at": str(occurred_at) if occurred_at else None,
        "note": payload.get("note") or payload.get("description"),
    }


def _llm_parse(text: str) -> dict[str, Any] | None:
    """调 OpenAI 兼容接口（DeepSeek / Qwen / Dify 均可）。

    任何异常都返回 None，由 `parse_text` 降级到规则解析——外部能力不可用时，
    应用仍能记账，而不是整条链路报错。
    """
    if not has_llm_key():
        return None

    import httpx

    try:
        response = httpx.post(
            f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "temperature": 0,
                "messages": _build_messages(text),
            },
            timeout=LLM_TIMEOUT,
            trust_env=False,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except Exception:
        return None

    try:
        payload = json.loads(_strip_code_fence(content))
    except ValueError:
        return None
    # 多笔小票模型可能直接给数组，单笔解析取第一条
    if isinstance(payload, list):
        payload = payload[0] if payload else None
    if not isinstance(payload, dict):
        return None
    return _normalize_llm_fields(payload)


# ---------------------------------------------------------------- 对外入口


def _is_rejected(text: str) -> bool:
    """识别非记账输入（纯灌水 / 天气写诗等），避免返回 code=0 的空白草稿。

    判定保持一致口径：既没有金额、也没有命中任何类别关键词、且不含记账动词时，
    视为非记账意图。缺金额但说了「水果 / 电影 / 买杯子」的仍走 clarify。
    """
    content = (text or "").strip()
    if not content:
        return True
    if _extract_amount(content) is not None or classify(content) != "其他":
        return False
    return not _EXPENSE_HINT.search(content)


def parse_text(text: str) -> dict[str, Any]:
    """把一句话解析成槽位。LLM 失败时静默降级到规则，返回结构始终一致。"""
    result = _llm_parse(text)
    if result is None:
        result = _rule_parse(text)
    if _is_rejected(text):
        result = dict(result)
        result["_rejected"] = True
    return result
