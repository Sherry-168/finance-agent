"""自然语言查账的「时间换算」落点（纯函数）。

约定（对齐《项目方案设计文档》§5.2 / §9）：
LLM 只负责把自然语言拆成槽位（时间表达、类别、聚合方式），
本模块负责把「上月」「近 7 天」这类相对时间换算成绝对区间，
SQL 执行与算数由 dao / stats 完成——LLM 全程不参与算术。

时间区间内部统一「左闭右开 [start, end)」：
end 为次日 / 下月 1 日零点，避免 DATETIME 含时分秒时右闭漏掉当天记录。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class QuerySpec:
    """一次查账的结构化参数。start/end 为 'YYYY-MM-DD'，区间左闭右开 [start, end)。"""
    start: str
    end: str
    categories: list[str] | None = None
    agg: str = "sum"      # sum / trend / share / top
    group_by: str | None = None


def _d(d: date) -> str:
    return d.isoformat()


def _next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _shift_month(d: date, months: int) -> date:
    y, m = d.year, d.month + months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return date(y, m, 1)


def resolve_time_range(expr: str, today: date | None = None) -> tuple[str, str]:
    """把时间表达解析成 (start, end)，左闭右开。无法识别时兜底为「本月」。"""
    today = today or date.today()
    e = (expr or "").strip()
    y, m = today.year, today.month

    if e in ("今天", "今日", "today"):
        return _d(today), _d(today + timedelta(days=1))
    if e in ("昨天", "昨日", "yesterday"):
        return _d(today - timedelta(days=1)), _d(today)
    if e in ("前天",):
        return _d(today - timedelta(days=2)), _d(today - timedelta(days=1))
    if e in ("大前天",):
        return _d(today - timedelta(days=3)), _d(today - timedelta(days=2))
    if e in ("本周", "这周", "this week"):
        monday = today - timedelta(days=today.weekday())
        return _d(monday), _d(today + timedelta(days=1))
    if e in ("上周", "last week"):
        monday = today - timedelta(days=today.weekday() + 7)
        return _d(monday), _d(monday + timedelta(days=7))
    if e in ("本月", "这个月", "this month"):
        start = date(y, m, 1)
        return _d(start), _d(_next_month(start))
    if e in ("上月", "上个月", "last month"):
        return _d(_shift_month(date(y, m, 1), -1)), _d(date(y, m, 1))
    if e in ("今年", "this year"):
        return _d(date(y, 1, 1)), _d(date(y + 1, 1, 1))
    if e in ("去年", "last year"):
        return _d(date(y - 1, 1, 1)), _d(date(y, 1, 1))

    mch = re.match(r"^(?:近|最近)(\d+)天$", e)
    if mch:
        n = int(mch.group(1))
        start = today - timedelta(days=n - 1)
        return _d(start), _d(today + timedelta(days=1))

    mch = re.match(r"^(?:近|最近)(\d+)个月$", e)
    if mch:
        n = int(mch.group(1))
        start = _shift_month(date(y, m, 1), -(n - 1))
        return _d(start), _d(today + timedelta(days=1))

    # 兜底：视为本月
    start = date(y, m, 1)
    return _d(start), _d(_next_month(start))


# ---------------------------------------------------------------- 槽位抽取

# 口语别名 → 8 类规范名（模型不可用时由本表兜底，模型可用时也用它校验）
CATEGORY_ALIASES: dict[str, str] = {
    "吃饭": "餐饮",
    "饮食": "餐饮",
    "餐饮": "餐饮",
    "外卖": "餐饮",
    "聚餐": "餐饮",
    "打车": "交通",
    "出行": "交通",
    "交通": "交通",
    "地铁": "交通",
    "加油": "交通",
    "购物": "购物",
    "网购": "购物",
    "买东西": "购物",
    "房租": "居住",
    "居住": "居住",
    "水电": "居住",
    "娱乐": "娱乐",
    "看电影": "娱乐",
    "看病": "医疗",
    "买药": "医疗",
    "医疗": "医疗",
    "学习": "教育",
    "培训": "教育",
    "教育": "教育",
}

# 时间表达：按「长词优先」排列，避免「上个月」被「个月」抢先命中
_TIME_PATTERNS: list[tuple[str, str]] = [
    (r"上个月|上月|上一个月", "上月"),
    (r"这个月|本月|这一个月", "本月"),
    (r"上个星期|上个礼拜|上周", "上周"),
    (r"这个星期|这个礼拜|这周|本周", "本周"),
    (r"去年", "去年"),
    (r"今年", "今年"),
    (r"大前天", "大前天"),
    (r"前天", "前天"),
    (r"昨天|昨日", "昨天"),
    (r"今天|今日", "今天"),
]

_TOP_HINTS = ("最多", "哪类", "哪一类", "哪个类别", "占比", "比重", "排行", "排名")
_TREND_HINTS = ("趋势", "每天", "每日", "走势", "按天")


def extract_slots(question: str, today: date | None = None) -> dict:
    """从自然语言问题抽取查账槽位（时间 / 类别 / 聚合方式）。

    返回 {time_expr, start, end, categories, agg, group_by}，其中 start/end 左闭右开。
    时间识别不到时兜底「本月」，并把兜底写进 time_expr，便于前端提示用户。
    """
    today = today or date.today()
    text = question or ""
    time_expr = "本月"
    for pattern, expr in _TIME_PATTERNS:
        if re.search(pattern, text):
            time_expr = expr
            break
    else:
        mch = re.search(r"(?:近|最近)\s*(\d+)\s*天", text)
        if mch:
            time_expr = f"近{int(mch.group(1))}天"
        else:
            mch = re.search(r"(?:近|最近)\s*(\d+)\s*个?月", text)
            if mch:
                time_expr = f"近{int(mch.group(1))}个月"

    categories = sorted({name for alias, name in CATEGORY_ALIASES.items() if alias in text})

    if any(hint in text for hint in _TREND_HINTS):
        agg, group_by = "trend", "date"
    elif any(hint in text for hint in _TOP_HINTS):
        agg, group_by = "top", "category"
    else:
        agg, group_by = "sum", None

    start, end = resolve_time_range(time_expr, today)
    return {
        "time_expr": time_expr,
        "start": start,
        "end": end,
        "categories": categories,
        "agg": agg,
        "group_by": group_by,
    }
