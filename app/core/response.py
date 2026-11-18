"""统一响应包装与业务错误码（唯一来源：docs/api.md §1）。

约定：成功 `code=0`；失败走契约错误码，HTTP 状态码一律 200，
由前端按 `code` 统一解包提示，避免前端同时判断 HTTP 码与业务码。
"""
from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

SUCCESS_CODE = 0
PARAM_ERROR = 1001
NOT_FOUND = 1002
LLM_ERROR = 2001
OCR_ERROR = 2002

ERROR_MESSAGES: dict[int, str] = {
    SUCCESS_CODE: "ok",
    PARAM_ERROR: "参数错误",
    NOT_FOUND: "资源不存在",
    LLM_ERROR: "LLM 调用失败",
    OCR_ERROR: "OCR 识别失败",
}


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    """成功响应体。"""
    return {"code": SUCCESS_CODE, "message": message, "data": data}


class ApiError(Exception):
    """业务异常。路由/服务层抛出后由全局处理器转成统一包装，不再漏出裸 500。"""

    def __init__(self, code: int = PARAM_ERROR, message: str | None = None, data: Any = None):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "请求失败")
        self.data = data
        super().__init__(self.message)


def fail(code: int = PARAM_ERROR, message: str | None = None, data: Any = None) -> JSONResponse:
    """失败响应体（HTTP 200 + 业务码，见文件头约定）。"""
    return JSONResponse(
        status_code=200,
        content={
            "code": code,
            "message": message or ERROR_MESSAGES.get(code, "请求失败"),
            "data": data,
        },
    )
