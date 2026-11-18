"""固定 8 类分类枚举（契约 docs/api.md §6/§10）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.response import ok
from logic.classify import known_categories

router = APIRouter(tags=["categories"])


@router.get("/categories", summary="类别枚举")
def list_categories() -> dict[str, Any]:
    return ok({"items": known_categories()})
