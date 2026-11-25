"""FastAPI 应用装配：生命周期建库 + CORS + 全局异常处理 + 路由注册。

启动：
    uvicorn app.main:app --host 0.0.0.0 --port 8000
根目录 `main.py` 是兼容入口（`uvicorn main:app` 与 `python main.py` 同样可用）。

异常处理只覆盖契约已定义的错误码（1001 参数错误 / 1002 资源不存在 /
2001 LLM / 2002 OCR / 2003 ASR），未预期的 500 仍由框架兜底，
避免自造契约外的错误码（详见 docs/api.md §1）。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import API_PREFIX, APP_TITLE, CORS_ORIGINS
from app.core.db import init_database
from app.core.response import ApiError, NOT_FOUND, PARAM_ERROR, fail
from app.routers import (
    alerts,
    budgets,
    demo,
    health,
    meta,
    ocr,
    query,
    records,
    stats,
    voice,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """启动时建表（幂等），否则首次请求会因 `no such table` 直接 500。"""
    init_database()
    yield


app = FastAPI(
    title=APP_TITLE,
    description="个人记账与消费分析 AI 助手 · 后端接口",
    version="1.2",
    lifespan=lifespan,
)

# ---------------------------------------------------------------- 跨域（CORS）
# 前端现在是 Gradio 服务端调用，理论上不触发浏览器同源策略；但答辩时经常有人
# 直接用浏览器 / 前端调试工具打 8000 端口，没有 CORS 会被拦在预检请求上。
# 默认 `CORS_ORIGINS=*` 方便评审机器直连；生产可换成具体域名（逗号分隔）。
# 注意：星号通配与 Cookie 凭证互斥，全部放开时自动关闭 credentials。
_allow_all = "*" in CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=not _allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError):
    """把 FastAPI 默认的裸 422 收敛为 `{code: 1001}` 统一包装。"""
    details = [
        {"field": ".".join(str(part) for part in err["loc"][1:]) or "body", "message": err["msg"]}
        for err in exc.errors()
    ]
    return fail(PARAM_ERROR, "参数错误", {"errors": details})


@app.exception_handler(ApiError)
async def handle_api_error(_: Request, exc: ApiError):
    """业务异常同样走统一包装，前端只需按 code 判断。"""
    return fail(exc.code, exc.message, exc.data)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(_: Request, exc: StarletteHTTPException):
    """404 落 1002，其余（405 等）落 1001，杜绝前端拿到裸 HTTP 错误体。"""
    if exc.status_code == 404:
        return fail(NOT_FOUND, "资源不存在")
    return fail(PARAM_ERROR, str(exc.detail))


# ---------------------------------------------------------------- 路由注册
# 契约：Base URL = /api/v1（docs/api.md §1）
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(records.router, prefix=API_PREFIX)
app.include_router(query.router, prefix=API_PREFIX)
app.include_router(stats.router, prefix=API_PREFIX)
app.include_router(budgets.router, prefix=API_PREFIX)
app.include_router(meta.router, prefix=API_PREFIX)
app.include_router(alerts.router, prefix=API_PREFIX)
app.include_router(voice.router, prefix=API_PREFIX)
app.include_router(demo.router, prefix=API_PREFIX)
app.include_router(ocr.router, prefix=API_PREFIX)

# 根路径健康检查：本地 curl 与容器探活的便捷别名，与 /api/v1/health 等价
app.include_router(health.router, include_in_schema=False)
