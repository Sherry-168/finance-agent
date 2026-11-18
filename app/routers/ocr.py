"""小票 OCR 接口（契约 §2.3）。

第一周只留上传入口：接口存在且返回契约错误码 2002，
前端第二周接入视觉模型 / 本地 OCR 后直接替换这里的识别实现即可。
"""
from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.core.response import OCR_ERROR, ApiError

router = APIRouter(prefix="/records", tags=["ocr"])


@router.post("/ocr", summary="小票 OCR（第二周接入）")
async def recognize_receipt(file: UploadFile = File(..., description="小票图片")) -> None:
    """当前版本明确返回 2002，避免前端把 Mock 结果当成真实识别。"""
    raise ApiError(OCR_ERROR, "小票 OCR 第二周接入，当前暂不可用")
