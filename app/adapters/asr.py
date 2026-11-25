"""语音转文字（ASR）适配层（第二周新增）。

硬约束（《第二周防翻车指南》第 1 条）
------------------------------------
**禁止在镜像里跑本地语音模型**——那会把镜像撑到几个 GB，评审机器拉不动。
所以这里只有三个云端 / 离线选项，没有 whisper / funasr：

- `auto`（默认）：配了 Key 就调 OpenAI 兼容的 `/audio/transcriptions`；没配就抛
  `AsrError`，明确告诉前端「语音不可用，请用文本框」，绝不伪造转写结果。
- `agent`：调用李语琛交付的 `agent.speech_to_text(audio_path)`，把 AI 同学的
  实现接进来（这是他分工里「写一个 speech_to_text(audio_file) 函数交给后端」的落点）。
- `mock`：离线演示用，不联网直接返回 `ASR_MOCK_TEXT`，响应里 `asr_engine="mock"`
  会如实标注，答辩时不会被当成真实识别结果。

降级原则：任何异常都收敛成 `AsrError`，由路由转成 2003 + 可读文案，
前端据此提示「改用文本输入」，文本记账闭环永远可用。
"""
from __future__ import annotations

import importlib
import os
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import (
    ASR_API_KEY,
    ASR_BASE_URL,
    ASR_LANGUAGE,
    ASR_MODEL,
    ASR_MOCK_TEXT,
    ASR_PROVIDER,
    ASR_TIMEOUT,
    has_asr_key,
)

# 微信 / 手机录音常见后缀；ASR 云端只认后缀判断容器格式，没有后缀会被拒
DEFAULT_SUFFIX = ".wav"
_ALLOWED_SUFFIX = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".webm", ".amr", ".flac"}


class AsrError(RuntimeError):
    """语音识别失败（未配置 / 网络 / 云端返回异常 / 空结果）。"""


def engine_name() -> str:
    """当前生效的转写引擎名，回显给前端做「真实 / 演示」提示。"""
    if ASR_PROVIDER == "mock":
        return "mock"
    if ASR_PROVIDER == "agent":
        return "agent"
    return "cloud" if has_asr_key() else "none"


def is_available() -> bool:
    """语音链路是否可用（mock 也算可用，前端据此决定是否禁用录音按钮）。"""
    return engine_name() != "none"


def _safe_suffix(filename: str | None) -> str:
    """从上传文件名里取后缀，非法后缀回落到 .wav。"""
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in _ALLOWED_SUFFIX else DEFAULT_SUFFIX


def _transcribe_cloud(audio: bytes, filename: str | None) -> str:
    """调 OpenAI 兼容的 `/audio/transcriptions`（智谱 glm-asr / 百炼 compatible-mode）。"""
    import httpx

    response = httpx.post(
        f"{ASR_BASE_URL.rstrip('/')}/audio/transcriptions",
        headers={"Authorization": f"Bearer {ASR_API_KEY}"},
        data={
            "model": ASR_MODEL,
            "language": ASR_LANGUAGE,
            "response_format": "json",
        },
        files={"file": (f"audio{_safe_suffix(filename)}", audio, "application/octet-stream")},
        timeout=ASR_TIMEOUT,
        trust_env=False,
    )
    response.raise_for_status()
    body: Any = response.json()
    # 兼容三种常见返回：{"text": ...} / {"result": ...} / {"data": {"text": ...}}
    if isinstance(body, dict):
        for key in ("text", "result", "transcript"):
            if isinstance(body.get(key), str):
                return body[key].strip()
        inner = body.get("data")
        if isinstance(inner, dict) and isinstance(inner.get("text"), str):
            return inner["text"].strip()
    raise AsrError("语音识别服务返回格式无法解析")


def _transcribe_agent(audio: bytes, filename: str | None) -> str:
    """调用李语琛交付的 `agent.speech_to_text(audio_path)`。

    约定：函数接收一个音频**文件路径**，返回识别文本。
    签名不一致 / 模块缺失时抛 AsrError 并带上原始异常，便于联调时快速定位。
    """
    try:
        module = importlib.import_module("agent")
    except ImportError as exc:
        raise AsrError("未找到 agent.py，无法调用李语琛的 ASR 函数") from exc

    func = getattr(module, "speech_to_text", None)
    if not callable(func):
        raise AsrError("agent.py 中没有 speech_to_text(audio_file) 函数")

    suffix = _safe_suffix(filename)
    handle, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(audio)
        text = func(path)
    except Exception as exc:  # noqa: BLE001 —— 统一收敛成 AsrError 给路由转 2003
        raise AsrError(f"调用 agent.speech_to_text 失败：{exc}") from exc
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    if not isinstance(text, str) or not text.strip():
        raise AsrError("agent.speech_to_text 没有返回文本")
    return text.strip()


def speech_to_text(audio: bytes, filename: str | None = None) -> tuple[str, str]:
    """音频字节 → (转写文本, 引擎名)。

    Raises:
        AsrError: 未配置云端服务、网络失败、云端返回异常或空文本。
    """
    if not audio:
        raise AsrError("音频内容为空")

    engine = engine_name()
    if engine == "mock":
        text = (ASR_MOCK_TEXT or "").strip()
        if not text:
            raise AsrError("ASR_MOCK_TEXT 为空，无法进行离线演示")
        return text, "mock"

    if engine == "agent":
        return _transcribe_agent(audio, filename), "agent"

    if engine == "none":
        raise AsrError(
            "未配置语音识别服务（ASR_API_KEY），语音输入暂不可用；"
            "请改用文本输入，或设置 ASR_PROVIDER=mock 做离线演示"
        )

    try:
        text = _transcribe_cloud(audio, filename)
    except AsrError:
        raise
    except Exception as exc:  # 网络 / 超时 / 非 2xx
        raise AsrError(f"语音识别服务调用失败：{exc}") from exc

    if not text:
        # 静音 / 噪声太大的典型表现，给一句能指导用户的中文
        raise AsrError("没听清，请靠近麦克风再说一遍，或改用文本输入")
    return text, "cloud"
