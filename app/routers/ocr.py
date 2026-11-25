"""小票 OCR 接口（契约 docs/api.md §2.3）。

第二周从「占位报 2002」升级为真实链路：图片 → 视觉模型 / Dify 多模态 → 多笔槽位
→ `drafts[]`，前端可勾选部分逐条调 `POST /records` 入库。

识别与归一化的分工：`app.adapters.receipt` 只管把图送出去并拿回原始数组，
槽位校验与契约结构统一走 `parser.normalize_many` + `services.draft`，
保证 OCR / 语音 / 文本三条链路的草稿长得一模一样。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, UploadFile

from app.adapters import receipt
from app.adapters.parser import normalize_many
from app.core.config import MAX_UPLOAD_MB, max_upload_bytes
from app.core.response import OCR_ERROR, PARAM_ERROR, ApiError, ok
from app.services.draft import build_draft_from_fields, next_draft_id

router = APIRouter(prefix="/records", tags=["ocr"])


@router.post("/ocr", summary="小票 / 长截图识别为多笔草稿")
async def recognize_receipt(
    file: UploadFile = File(..., description="小票或长截图，支持一次识别多笔"),
) -> dict[str, Any]:
    """返回 `drafts[]`，每笔一张确认卡；识别失败返回 2002 并附带原文供降级。"""
    image = await file.read()
    if not image:
        raise ApiError(PARAM_ERROR, "图片文件为空")
    if len(image) > max_upload_bytes():
        raise ApiError(PARAM_ERROR, f"图片超过 {MAX_UPLOAD_MB:g} MB 上限，请压缩后重试")
    content_type = file.content_type or ""
    if content_type and not content_type.startswith("image/"):
        raise ApiError(PARAM_ERROR, "只支持图片格式（png / jpg / webp）")

    try:
        raw_text, items = receipt.recognize(image, content_type)
    except receipt.ReceiptError as exc:
        raise ApiError(OCR_ERROR, str(exc))

    drafts = [
        build_draft_from_fields(fields, draft_id=next_draft_id())
        for fields in normalize_many(items)
    ]
    if not drafts:
        # 原文一并返回：前端可让用户复制粘贴到文本框继续记账，不至于彻底走不通
        raise ApiError(OCR_ERROR, "图片里没有识别出可记账的金额", {"raw_text": raw_text})

    return ok(
        {
            "drafts": drafts,
            "ocr_engine": receipt.engine_name(),
            "raw_text": raw_text,
        }
    )
