"""语音录入接口 `/api/v1/voice`（第二周新增，契约见 docs/api.md §11）。

链路：前端录音 → multipart 上传 → 云端 ASR 转文字 → 复用文本解析 → 返回草稿
→ 用户在确认卡上点「确认」调 `POST /records` 入库。

设计要点
--------
- **绝不做本地语音模型**：镜像体积是硬约束，转写全部走云端 API（或李语琛的 agent 函数）；
- **一定要能降级**：ASR 失败返回 2003 + 中文可读文案，前端提示「改用文本输入」，
  文本记账闭环不受影响（《防翻车指南》第 2、3 条）；
- **默认只出草稿**：语音识别有误差，直接入库等于替用户记账；`auto_commit=true`
  仅供演示 / 已确认的批量场景，且槽位不全时仍然拒绝入库。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.adapters import asr
from app.core.config import DEFAULT_USER_ID, MAX_UPLOAD_MB, max_upload_bytes
from app.core.db import get_db
from app.core.response import ASR_ERROR, PARAM_ERROR, ApiError, ok
from app.services.draft import build_draft, commit_draft

router = APIRouter(prefix="/voice", tags=["voice"])


def _check_size(size: int) -> None:
    """体积护栏：云端 ASR 按秒计费，超大文件既慢又贵，直接拒掉更清楚。"""
    if size <= 0:
        raise ApiError(PARAM_ERROR, "音频文件为空")
    if size > max_upload_bytes():
        raise ApiError(PARAM_ERROR, f"音频超过 {MAX_UPLOAD_MB:g} MB 上限，请压缩或改用文本输入")


@router.post("", summary="语音记账：音频 → 文字 → 草稿")
async def create_voice_draft(
    file: UploadFile = File(..., description="音频文件（wav / mp3 / m4a / webm 等）"),
    session_id: str | None = Form(None, description="澄清反问的会话上下文标识"),
    auto_commit: bool = Form(False, description="槽位齐全时是否直接入库（演示用）"),
    conn: Any = Depends(get_db),
) -> dict[str, Any]:
    """把一段录音转成记账草稿；识别失败返回 2003，不影响文本输入。"""
    audio = await file.read()
    _check_size(len(audio))

    try:
        transcript, engine = asr.speech_to_text(audio, file.filename)
    except asr.AsrError as exc:
        # 2003 + 可读文案：前端据此引导用户切回文本框，而不是弹一个技术栈错误
        raise ApiError(ASR_ERROR, str(exc))

    draft = build_draft(transcript)
    payload: dict[str, Any] = {
        "transcript": transcript,
        "asr_engine": engine,
        "session_id": session_id,
        "record_id": None,
        **draft,
    }

    if draft.get("action") == "reject":
        return ok(payload)

    if auto_commit:
        if draft["missing_fields"]:
            # 不替用户猜：缺金额 / 时间就老老实实回草稿让前端反问
            payload["action"] = "clarify"
            return ok(payload)
        payload["record_id"] = commit_draft(
            conn, draft["fields"], raw_text=transcript, source="voice", user_id=DEFAULT_USER_ID
        )
        payload["action"] = "committed"
        payload["confirmed"] = 1

    return ok(payload)


@router.get("/status", summary="语音能力探测")
def voice_status() -> dict[str, Any]:
    """前端据此决定录音按钮是否可用：`available=false` 时直接引导文本输入。"""
    return ok(
        {
            "available": asr.is_available(),
            "engine": asr.engine_name(),
            "max_upload_mb": MAX_UPLOAD_MB,
        }
    )
