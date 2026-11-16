"""系统健康检查。

契约路径：`GET /api/v1/health`（docs/api.md §8）。
同时在根路径暴露一份 `GET /health`，方便本地 curl 与容器探活，两者等价。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.response import ok

router = APIRouter(tags=["system"])


@router.get("/health", summary="健康检查")
def health() -> dict[str, Any]:
    """连通性探针：前端启动时先调它，失败则提示后端未启动。"""
    return ok("Backend is running")
