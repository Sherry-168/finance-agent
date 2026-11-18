"""基础字典路由：固定 8 类类别枚举。

类别字典是冻结项（docs/api.md §10，严禁修改），因此直接读词典文件，
不查库、不受数据库状态影响，前端下拉框可稳定渲染。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.response import ok
from logic.classify import known_categories

router = APIRouter(tags=["meta"])


@router.get("/categories", summary="8 类类别枚举")
def categories() -> dict[str, Any]:
    """返回固定 8 类，顺序与词典文件一致。"""
    return ok({"items": known_categories()})
