"""统一 API 请求层。

职责（《前端注意事项》第 2 条）：
- 统一拼接 Base URL，统一解包 {"code", "message", "data"}；
- code != 0 时抛 ApiError，页面层只负责把 message 显示成提示气泡；
- 网络异常、超时、非 JSON 响应也收敛成 ApiError，页面层无需区分。
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from config import API_BASE_URL, API_TIMEOUT, ERROR_MESSAGES, MOCK_FALLBACK, SUCCESS_CODE

DRAFT_FIELDS = ("amount", "category", "merchant", "occurred_at", "note")
MISSING_REQUIRED = ("amount", "category", "occurred_at")


class ApiError(Exception):
    """接口异常。code 为业务错误码；为 None 表示网络层失败（后端未启动 / 超时等）。"""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code

    @property
    def is_network_error(self) -> bool:
        return self.code is None


def should_fallback(exc: "ApiError") -> bool:
    """是否降级到本地 Mock 演示。

    三种情况降级（MOCK_FALLBACK 开启时）：
    - 网络层失败（后端未启动 / 超时）；
    - 1002 资源不存在（后端在线但该接口尚未实现）；
    - 1001 且 message 含 Method Not Allowed（GET/PUT/DELETE 与已实现的 POST 同路径
      时，后端把 405 包装成 1001，同样属于"接口未就绪"）。
    其他业务错误（参数错误、LLM 失败等）照常报错，不掩盖真实问题。
    """
    if not MOCK_FALLBACK:
        return False
    if exc.is_network_error or exc.code == 1002:
        return True
    return exc.code == 1001 and "method not allowed" in exc.message.lower()


# ---------------------------------------------------------------- 底层请求


def _friendly_message(code: int, server_message: str) -> str:
    base = ERROR_MESSAGES.get(code, "请求失败，请稍后重试")
    detail = (server_message or "").strip()
    if not detail or detail in ("ok", "success"):
        return base
    return f"{base}（{detail}）"


def request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    files: dict | None = None,
    timeout: float | None = None,
) -> Any:
    """发起请求并返回统一包装里的 data；失败抛 ApiError。"""
    url = f"{API_BASE_URL}{path}"
    try:
        response = httpx.request(
            method,
            url,
            params=params,
            json=json_body,
            files=files,
            timeout=timeout or API_TIMEOUT,
            follow_redirects=True,
            # 后端在本地 / 内网，禁用系统代理，避免代理软件劫持 127.0.0.1 请求
            trust_env=False,
        )
    except httpx.TimeoutException as exc:
        raise ApiError("后端响应超时，请稍后重试") from exc
    except httpx.HTTPError as exc:
        raise ApiError("无法连接后端服务，请确认后端已启动") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ApiError(f"接口返回格式异常（HTTP {response.status_code}）") from exc

    # 兜底：未套统一包装的裸数据也允许渲染，避免后端临时实现直接崩页面
    if not isinstance(payload, dict) or "code" not in payload:
        if response.status_code >= 400:
            raise ApiError(f"接口异常（HTTP {response.status_code}）")
        return payload

    code = payload.get("code")
    if code != SUCCESS_CODE:
        raise ApiError(_friendly_message(code, payload.get("message", "")), code)
    return payload.get("data")


# ---------------------------------------------------------------- 数据结构归一化


def _first(mapping: dict, *keys: str, default=None):
    for key in keys:
        if mapping.get(key) is not None:
            return mapping[key]
    return default


def normalize_draft(data: dict | None) -> dict:
    """把后端草稿归一化为确认卡需要的结构。

    兼容两种形态：
    - 完整版（api.md v1.1 提议稿）：{draft_id, fields, confidence, missing_fields, clarify_question}
    - 简版（api.md v1.0 现状）：{amount, category, occurred_at}
    """
    data = data or {}
    raw_fields = data.get("fields")
    if isinstance(raw_fields, dict):
        fields = {key: raw_fields.get(key) for key in DRAFT_FIELDS}
    else:
        fields = {key: data.get(key) for key in DRAFT_FIELDS}

    missing = data.get("missing_fields")
    if not isinstance(missing, list):
        missing = [key for key in MISSING_REQUIRED if fields.get(key) in (None, "")]

    return {
        "draft_id": data.get("draft_id"),
        "fields": fields,
        "confidence": data.get("confidence"),
        "missing_fields": missing,
        "clarify_question": (data.get("clarify_question") or None),
    }


def normalize_records_page(data: Any, page: int, size: int) -> dict:
    """归一化分页结果；后端返回裸列表时也兜住。"""
    if isinstance(data, list):
        return {"items": data, "total": len(data), "page": page, "size": size, "pages": 1}

    data = data or {}
    items = _first(data, "items", "records", default=[]) or []
    total = _first(data, "total", "count", default=len(items))
    return {
        "items": items,
        "total": total,
        "page": _first(data, "page", default=page),
        "size": _first(data, "size", "page_size", default=size),
        "pages": _first(data, "pages", "total_pages", default=1),
    }


# ---------------------------------------------------------------- 业务接口


def health() -> Any:
    """GET /health —— 前后端连通性检查。"""
    return request("GET", "/health", timeout=5)


def parse_record(text: str, session_id: str) -> dict:
    """POST /records/parse —— 自然语言解析为草稿（不入库）。"""
    data = request(
        "POST",
        "/records/parse",
        json_body={"text": text, "session_id": session_id},
    )
    return normalize_draft(data)


def ocr_receipt(file_path: str) -> dict:
    """POST /records/ocr —— 上传小票，返回可勾选的多笔草稿。"""
    with open(file_path, "rb") as stream:
        data = request(
            "POST",
            "/records/ocr",
            files={"file": (os.path.basename(file_path), stream, "image/*")},
        ) or {}
    drafts = data.get("drafts") or []
    return {
        "drafts": [normalize_draft(draft) for draft in drafts],
        "ocr_engine": data.get("ocr_engine"),
        "raw_text": data.get("raw_text") or "",
    }


def create_record(payload: dict) -> dict:
    """POST /records —— 确认入库。"""
    return request("POST", "/records", json_body=payload) or {}


def list_records(
    *,
    start: str | None = None,
    end: str | None = None,
    category: str | None = None,
    page: int = 1,
    size: int = 10,
) -> dict:
    """GET /records —— 分页明细。"""
    params = {"page": page, "size": size}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    if category:
        params["category"] = category
    return normalize_records_page(request("GET", "/records", params=params), page, size)


def update_record(record_id: int, payload: dict) -> dict:
    """PUT /records/{id} —— 修正记录。"""
    return request("PUT", f"/records/{record_id}", json_body=payload) or {}


def delete_record(record_id: int) -> dict:
    """DELETE /records/{id} —— 删除记录。"""
    return request("DELETE", f"/records/{record_id}") or {}


def query(question: str, session_id: str) -> dict:
    """POST /query —— 自然语言查账（前端只渲染 answer_text / table）。"""
    data = request(
        "POST", "/query", json_body={"question": question, "session_id": session_id}
    )
    data = data or {}
    return {
        "slots": data.get("slots") or {},
        "answer_text": data.get("answer_text") or "",
        "table": data.get("table") or [],
    }


def stats_summary(month: str) -> dict:
    """GET /stats/summary —— 月度总额、笔数、日均。"""
    return request("GET", "/stats/summary", params={"month": month}) or {}


def stats_by_category(
    *, month: str | None = None, start: str | None = None, end: str | None = None
) -> dict:
    """GET /stats/by-category —— 类别占比。"""
    params = {}
    if month:
        params["month"] = month
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    data = request("GET", "/stats/by-category", params=params) or {}
    return {"items": _first(data, "items", "list", default=[]) or []}


def stats_trend(days: int = 30) -> dict:
    """GET /stats/trend —— 每日趋势。"""
    data = request("GET", "/stats/trend", params={"days": days}) or {}
    return {"items": _first(data, "items", "list", default=[]) or []}


def list_budgets(month: str) -> dict:
    """GET /budgets —— 当月预算列表。"""
    data = request("GET", "/budgets", params={"month": month}) or {}
    return {"items": _first(data, "items", "budgets", default=[]) or []}


def save_budget(month: str, category: str | None, amount: float) -> dict:
    """POST /budgets —— 设定月度预算（category 为 None 表示总预算）。"""
    return (
        request(
            "POST",
            "/budgets",
            json_body={"month": month, "category": category, "amount": amount},
        )
        or {}
    )


def budget_alerts(month: str) -> dict:
    """GET /budgets/alerts —— 各预算使用率与状态。"""
    data = request("GET", "/budgets/alerts", params={"month": month}) or {}
    return {"items": _first(data, "items", "alerts", default=[]) or []}


def list_categories() -> list[str]:
    """GET /categories —— 固定 8 类枚举。"""
    data = request("GET", "/categories") or {}
    items = data if isinstance(data, list) else (_first(data, "items", default=[]) or [])
    return [str(item) for item in items]


def demo_load() -> dict:
    """POST /demo/load —— 一键灌入演示数据。"""
    return request("POST", "/demo/load") or {}


def demo_reset() -> dict:
    """POST /demo/reset —— 清空演示数据。"""
    return request("POST", "/demo/reset") or {}
