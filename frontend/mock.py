"""本地 Mock 数据源。

仅在后端接口未就绪时驱动 UI 自测与演示（config.MOCK_FALLBACK 控制）。
真实解析、分类、算账一律由后端完成，本模块不参与生产链路。
"""

from __future__ import annotations

import datetime as dt
import re

NOTICE = "演示模式：后端接口未就绪，当前展示的是本地模拟数据"

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


_MOCK_RECORDS: list[dict] = []
_MOCK_NEXT_ID = 201
_MOCK_SEEDED = False


def _seed_records() -> None:
    """首次访问时生成确定性演示明细（金额/统计仍以后端为准）。

    每个进程只 seed 一次；demo_reset 清空后不再自动复活，保证清空语义真实。
    """
    global _MOCK_NEXT_ID, _MOCK_SEEDED
    if _MOCK_SEEDED:
        return
    _MOCK_SEEDED = True
    today = dt.date.today()
    samples = [
        (32.0, "交通", "滴滴出行", "市区通勤", "text"),
        (25.5, "餐饮", "兰州拉面", None, "text"),
        (128.0, "购物", "优衣库", "秋季外套", "manual"),
        (18.0, "餐饮", "瑞幸咖啡", None, "text"),
        (1200.0, "居住", "自如", "11 月房租", "manual"),
        (45.0, "娱乐", "万达影城", None, "text"),
        (66.5, "医疗", "海王星辰", "感冒药", "manual"),
        (320.0, "教育", "网易云课堂", None, "text"),
        (58.0, "餐饮", "美团外卖", "工作餐", "text"),
        (12.0, "交通", "地铁", None, "text"),
        (210.0, "购物", "京东", "洗衣液", "text"),
        (99.0, "娱乐", "腾讯视频", "季度会员", "manual"),
        (38.0, "餐饮", "沙县小吃", None, "text"),
        (156.0, "交通", "中石化", "加油", "manual"),
        (7.5, "餐饮", "蜜雪冰城", None, "text"),
        (880.0, "购物", "苹果官网", "AirPods", "manual"),
    ]
    for index, (amount, category, merchant, note, source) in enumerate(samples):
        day = today - dt.timedelta(days=index % 20)
        _MOCK_RECORDS.append(
            {
                "id": 100 + index,
                "amount": amount,
                "category": category,
                "merchant": merchant,
                "occurred_at": day.isoformat(),
                "note": note,
                "source": source,
                "confirmed": 1,
                "created_at": f"{day.isoformat()} 20:11:03",
            }
        )
    # 一条草稿示例，用于展示「草稿 / 已确认」状态区分
    _MOCK_RECORDS.append(
        {
            "id": _MOCK_NEXT_ID,
            "amount": 66.0,
            "category": "娱乐",
            "merchant": None,
            "occurred_at": today.isoformat(),
            "note": "待确认",
            "source": "text",
            "confirmed": 0,
            "created_at": f"{today.isoformat()} 21:00:00",
        }
    )
    _MOCK_NEXT_ID += 1


def list_records(
    *,
    start: str | None = None,
    end: str | None = None,
    category: str | None = None,
    page: int = 1,
    size: int = 10,
) -> dict:
    """模拟 GET /records：内存过滤 + 分页。"""
    _seed_records()
    items = list(_MOCK_RECORDS)
    if start:
        items = [item for item in items if item["occurred_at"] >= start]
    if end:
        items = [item for item in items if item["occurred_at"] <= end]
    if category:
        items = [item for item in items if item["category"] == category]
    items.sort(key=lambda item: (item["occurred_at"], item["id"]), reverse=True)

    total = len(items)
    pages = max(1, (total + size - 1) // size)
    page = min(max(1, page), pages)
    begin = (page - 1) * size
    return {
        "items": items[begin : begin + size],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


def update_record(record_id: int, payload: dict) -> dict:
    """模拟 PUT /records/{id}：返回更新后的记录。"""
    _seed_records()
    for item in _MOCK_RECORDS:
        if item["id"] == record_id:
            item.update({key: value for key, value in payload.items() if value is not None})
            return dict(item)
    return {"id": record_id}


def delete_record(record_id: int) -> dict:
    """模拟 DELETE /records/{id}。"""
    _seed_records()
    before = len(_MOCK_RECORDS)
    _MOCK_RECORDS[:] = [item for item in _MOCK_RECORDS if item["id"] != record_id]
    return {"deleted": len(_MOCK_RECORDS) < before}


def health() -> str:
    return "Mock 模式（未连接后端）"


def ocr_receipt() -> dict:
    """模拟 POST /records/ocr：多笔小票草稿，供勾选入库 UI 自测。"""
    today = dt.date.today().isoformat()
    return {
        "drafts": [
            {
                "draft_id": "mock_ocr_1",
                "fields": {
                    "amount": 45.5, "category": "餐饮", "merchant": "瑞幸咖啡",
                    "occurred_at": today, "note": None,
                },
                "confidence": 0.88, "missing_fields": [], "clarify_question": None,
            },
            {
                "draft_id": "mock_ocr_2",
                "fields": {
                    "amount": 12.0, "category": "交通", "merchant": "地铁",
                    "occurred_at": today, "note": None,
                },
                "confidence": 0.86, "missing_fields": [], "clarify_question": None,
            },
        ],
        "ocr_engine": "mock",
        "raw_text": "瑞幸咖啡 45.50\n地铁 12.00",
    }


def create_record(payload: dict) -> dict:
    """模拟 POST /records：写入内存明细表并返回成功结构。"""
    global _MOCK_NEXT_ID
    _seed_records()
    record = {
        "id": _MOCK_NEXT_ID,
        "amount": payload.get("amount") or 0.0,
        "category": payload.get("category") or "其他",
        "merchant": payload.get("merchant"),
        "occurred_at": payload.get("occurred_at") or dt.date.today().isoformat(),
        "note": payload.get("note"),
        "source": payload.get("source") or "text",
        "confirmed": 1,
        "created_at": f"{dt.date.today().isoformat()} {dt.datetime.now().strftime('%H:%M:%S')}",
    }
    _MOCK_NEXT_ID += 1
    _MOCK_RECORDS.append(record)
    return {"id": record["id"], "confirmed": 1}


def query(question: str, session_id: str) -> dict:
    """模拟 POST /query：仅用于气泡流自测，数字不是真实统计。"""
    return {
        "slots": {},
        "answer_text": f"（演示模式）还没连接后端，无法统计「{question}」。"
        "启动后端后即可返回真实结果。",
        "table": [],
    }


def _confirmed_between(start: str, end: str) -> list[dict]:
    """统计口径（api.md §5）：仅 confirmed=1 的记录。"""
    _seed_records()
    return [
        item
        for item in _MOCK_RECORDS
        if item["confirmed"] in (1, True, "1") and start <= item["occurred_at"] <= end
    ]


def _month_bounds(month: str) -> tuple[str, str]:
    year, mon = int(month[:4]), int(month[5:7])
    first = dt.date(year, mon, 1)
    if mon == 12:
        next_first = dt.date(year + 1, 1, 1)
    else:
        next_first = dt.date(year, mon + 1, 1)
    return first.isoformat(), (next_first - dt.timedelta(days=1)).isoformat()


def stats_summary(month: str) -> dict:
    """模拟 GET /stats/summary：总额 / 笔数 / 日均（当月已过天数）。"""
    start, end = _month_bounds(month)
    records = _confirmed_between(start, end)
    total = round(sum(item["amount"] for item in records), 2)
    year, mon = int(month[:4]), int(month[5:7])
    if mon == 12:
        days = (dt.date(year + 1, 1, 1) - dt.date(year, 12, 1)).days
    else:
        days = (dt.date(year, mon + 1, 1) - dt.date(year, mon, 1)).days
    today = dt.date.today()
    if month == today.strftime("%Y-%m"):
        days = min(days, today.day)
    return {
        "month": month,
        "total": total,
        "count": len(records),
        "daily_avg": round(total / days, 2) if days else 0.0,
    }


def stats_by_category(
    *, month: str | None = None, start: str | None = None, end: str | None = None
) -> dict:
    """模拟 GET /stats/by-category：分组总额、笔数、占比（降序）。"""
    if start and end:
        records = _confirmed_between(start, end)
    else:
        month = month or dt.date.today().strftime("%Y-%m")
        start, end = _month_bounds(month)
        records = _confirmed_between(start, end)

    groups: dict[str, dict] = {}
    grand = 0.0
    for item in records:
        bucket = groups.setdefault(item["category"], {"total": 0.0, "count": 0})
        bucket["total"] += item["amount"]
        bucket["count"] += 1
        grand += item["amount"]

    items = [
        {
            "category": name,
            "total": round(bucket["total"], 2),
            "count": bucket["count"],
            "ratio": round(bucket["total"] / grand, 2) if grand else 0.0,
        }
        for name, bucket in sorted(
            groups.items(), key=lambda pair: pair[1]["total"], reverse=True
        )
    ]
    return {"items": items}


def stats_trend(days: int = 30) -> dict:
    """模拟 GET /stats/trend：近 N 天每日总额与笔数（含 0 消费日）。"""
    days = max(1, min(int(days), 90))
    today = dt.date.today()
    start = (today - dt.timedelta(days=days - 1)).isoformat()
    records = _confirmed_between(start, today.isoformat())
    by_day: dict[str, dict] = {}
    for item in records:
        bucket = by_day.setdefault(item["occurred_at"], {"total": 0.0, "count": 0})
        bucket["total"] += item["amount"]
        bucket["count"] += 1
    items = []
    for offset in range(days - 1, -1, -1):
        day = (today - dt.timedelta(days=offset)).isoformat()
        bucket = by_day.get(day, {"total": 0.0, "count": 0})
        items.append(
            {"date": day, "total": round(bucket["total"], 2), "count": bucket["count"]}
        )
    return {"items": items}


# ---------------------------------------------------------------- 预算 / 类别 / 演示数据

_MOCK_BUDGETS: dict[tuple, float] = {}  # key: (month, category or "__total__")
_TOTAL_KEY = "__total__"
_BUDGETS_SEEDED = False


def _seed_budgets() -> None:
    """种子预算：刻意覆盖 normal / warning / over 三种状态，便于演示。

    与明细一样每个进程只 seed 一次，demo_reset 清空后不再复活。
    """
    global _BUDGETS_SEEDED
    if _BUDGETS_SEEDED:
        return
    _BUDGETS_SEEDED = True
    _seed_records()
    month = dt.date.today().strftime("%Y-%m")
    _MOCK_BUDGETS[(month, _TOTAL_KEY)] = 4000.0  # 总预算 → ~82% warning
    _MOCK_BUDGETS[(month, "餐饮")] = 1200.0      # → ~12% normal
    _MOCK_BUDGETS[(month, "交通")] = 500.0       # → ~40% normal
    _MOCK_BUDGETS[(month, "娱乐")] = 100.0       # → 144% over


def list_budgets(month: str) -> dict:
    """模拟 GET /budgets：当月预算列表（category 为 null 表示总预算）。"""
    _seed_budgets()
    items = []
    for (budget_month, category), amount in _MOCK_BUDGETS.items():
        if budget_month != month:
            continue
        items.append(
            {"month": month, "category": None if category == _TOTAL_KEY else category, "amount": amount}
        )
    return {"items": items}


def save_budget(month: str, category: str | None, amount: float) -> dict:
    """模拟 POST /budgets：同月同维度覆盖。"""
    _seed_budgets()
    key = (month, _TOTAL_KEY if category in (None, "", "全部") else category)
    _MOCK_BUDGETS[key] = float(amount)
    return {"month": month, "category": category, "amount": float(amount)}


def budget_alerts(month: str) -> dict:
    """模拟 GET /budgets/alerts：used_ratio 与状态由聚合计算（confirmed=1 口径）。"""
    _seed_budgets()
    start, end = _month_bounds(month)
    records = _confirmed_between(start, end)
    used_by_cat: dict[str | None, float] = {}
    for item in records:
        used_by_cat[item["category"]] = used_by_cat.get(item["category"], 0.0) + item["amount"]

    items = []
    for (budget_month, category), amount in sorted(_MOCK_BUDGETS.items()):
        if budget_month != month or amount <= 0:
            continue
        if category == _TOTAL_KEY:
            used = round(sum(used_by_cat.values()), 2)
        else:
            used = round(used_by_cat.get(category, 0.0), 2)
        ratio = round(used / amount, 2)
        status = "over" if ratio >= 1 else ("warning" if ratio >= 0.8 else "normal")
        items.append(
            {
                "month": month,
                "category": None if category == _TOTAL_KEY else category,
                "amount": amount,
                "used": used,
                "used_ratio": ratio,
                "status": status,
            }
        )
    return {"items": items}


def list_categories() -> list[str]:
    """模拟 GET /categories：固定 8 类。"""
    return [
        "餐饮", "交通", "购物", "居住", "娱乐", "医疗", "教育", "其他",
    ]


def demo_load() -> dict:
    """模拟 POST /demo/load：追加两个月的演示明细并布置预算。"""
    global _MOCK_NEXT_ID
    _seed_records()
    _seed_budgets()
    today = dt.date.today()
    added = 0
    # 上个月：铺底数据，保证趋势图跨月
    for offset, (amount, category, merchant) in enumerate(
        [
            (18.5, "餐饮", "瑞幸"), (42.0, "餐饮", "外卖"), (9.9, "交通", "公交"),
            (256.0, "购物", "天猫"), (13.0, "餐饮", "食堂"), (320.0, "娱乐", "剧本杀"),
        ]
    ):
        day = today.replace(day=1) - dt.timedelta(days=offset + 1)
        _MOCK_RECORDS.append(
            {
                "id": _MOCK_NEXT_ID,
                "amount": amount,
                "category": category,
                "merchant": merchant,
                "occurred_at": day.isoformat(),
                "note": None,
                "source": "manual",
                "confirmed": 1,
                "created_at": f"{day.isoformat()} 19:00:00",
            }
        )
        _MOCK_NEXT_ID += 1
        added += 1
    # 当月娱乐追加，放大超支演示点
    for amount, category, merchant in [(128.0, "娱乐", "KTV"), (56.0, "娱乐", "游戏充值")]:
        _MOCK_RECORDS.append(
            {
                "id": _MOCK_NEXT_ID,
                "amount": amount,
                "category": category,
                "merchant": merchant,
                "occurred_at": today.isoformat(),
                "note": "演示",
                "source": "text",
                "confirmed": 1,
                "created_at": f"{today.isoformat()} 20:00:00",
            }
        )
        _MOCK_NEXT_ID += 1
        added += 1
    return {"records": added, "months": 2, "receipts": 3}


def demo_reset() -> dict:
    """模拟 POST /demo/reset：清空演示明细与预算。"""
    records = len(_MOCK_RECORDS)
    budgets = len(_MOCK_BUDGETS)
    _MOCK_RECORDS.clear()
    _MOCK_BUDGETS.clear()
    global _MOCK_NEXT_ID
    _MOCK_NEXT_ID = 201
    return {"deleted_records": records, "deleted_budgets": budgets}
