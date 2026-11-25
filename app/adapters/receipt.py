"""小票 / 长截图识别适配层（第二周新增，契约 docs/api.md §2.3）。

与李语琛的分工边界
------------------
- 多模态能力与「长截图返回 JSON 数组」的 Prompt 在 Dify / 视觉模型侧（他负责）；
- 本模块负责把图片**送去**识别、把返回的数组**收敛**成槽位（我负责），
  并对识别不出金额的情况给出可读的 2002 文案。

三种 provider
-------------
- `api`  ：OpenAI 兼容的视觉模型（`image_url` + base64），一次可返回多笔；
- `dify` ：Dify 多模态工作流，图片以 base64 data URL 送入 `DIFY_IMAGE_KEY` 变量；
- `local`：不打包本地 OCR 模型（《防翻车指南》第 1 条：镜像体积优先），直接报不可用。

对外只暴露 `recognize(image, content_type) -> (raw_text, items)`，items 是未经校验的
原始槽位，归一化统一交给 `app.adapters.parser.normalize_many`。
"""
from __future__ import annotations

import base64
from typing import Any

from app.adapters import dify
from app.core.config import (
    DIFY_IMAGE_KEY,
    OCR_PROVIDER,
    VISION_API_KEY,
    VISION_BASE_URL,
    VISION_MODEL,
)

# 识别不出的统一文案（前端会直接展示给用户）
_NO_RESULT = "没识别出金额，请换一张更清晰的小票，或改用文本输入"

_PROMPT = (
    "你是小票识别器。请识别图片里的每一笔消费，只输出一个 JSON 对象，不要解释。\n"
    '格式：{"raw_text": "图片中识别到的文字", "items": [{"amount": 数字, "category": '
    "餐饮/交通/购物/居住/娱乐/医疗/教育/其他, \"merchant\": 商户或null, "
    '"occurred_at": "YYYY-MM-DD HH:MM 或 YYYY-MM-DD 或 null", "note": 备注或null}]}\n'
    "规则：一笔商品/一次支付 = 一条 item；识别不到金额的条目丢弃；金额用阿拉伯数字，"
    "不带单位；看不清的字段填 null，禁止编造；不要计入合计、优惠、找零行。"
)


class ReceiptError(RuntimeError):
    """小票识别失败（未配置 / 网络 / 云端返回异常 / 无有效条目）。"""


def engine_name() -> str:
    """当前生效的识别引擎，回显给前端做「真实 / 不可用」提示。"""
    if OCR_PROVIDER == "dify":
        return "dify" if dify.is_configured() else "none"
    if OCR_PROVIDER == "api":
        return "vision_api" if VISION_API_KEY.strip() else "none"
    return "none"


def is_available() -> bool:
    return engine_name() != "none"


def _data_url(image: bytes, content_type: str | None) -> str:
    """图片转 base64 data URL（两家的视觉接口都吃这个格式）。"""
    mime = content_type if content_type and content_type.startswith("image/") else "image/png"
    return f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"


def _parse_body(payload: Any) -> tuple[str, list[dict[str, Any]]]:
    """把模型 / 工作流输出收敛成 (raw_text, 原始 items)。"""
    if isinstance(payload, list):
        return "", [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return "", []

    raw_text = payload.get("raw_text") or payload.get("text") or ""
    items = payload.get("items")
    if items is None:
        # 工作流可能把数组放在别的键下，或者直接返回单笔
        nested = next((v for v in payload.values() if isinstance(v, list)), None)
        items = nested if nested is not None else [payload]
    return str(raw_text or ""), [item for item in items if isinstance(item, dict)]


def _recognize_vision(image: bytes, content_type: str | None) -> tuple[str, list[dict[str, Any]]]:
    """调视觉模型（OpenAI 兼容 chat/completions 的多模态消息格式）。"""
    import httpx

    response = httpx.post(
        f"{VISION_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {VISION_API_KEY}"},
        json={
            "model": VISION_MODEL,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": _data_url(image, content_type)},
                        },
                    ],
                }
            ],
        },
        timeout=60,
        trust_env=False,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    payload = dify.extract_json(content)
    if payload is None:
        raise ReceiptError("模型输出中没有可解析的 JSON")
    return _parse_body(payload)


def _recognize_dify(image: bytes, content_type: str | None) -> tuple[str, list[dict[str, Any]]]:
    """调 Dify 多模态工作流，图片以 data URL 写入约定变量。"""
    payload = dify.run_workflow(
        "请识别这张小票并把每一笔消费以 JSON 数组返回",
        inputs={DIFY_IMAGE_KEY: _data_url(image, content_type)},
    )
    raw_text, items = _parse_body(payload)
    if not items and isinstance(payload, list):
        items = [item for item in payload if isinstance(item, dict)]
    return raw_text, items


def recognize(image: bytes, content_type: str | None = None) -> tuple[str, list[dict[str, Any]]]:
    """识别小票 / 长截图，返回 (原文字, 原始槽位列表)。

    Raises:
        ReceiptError: 引擎未配置、调用失败或没有识别出任何带金额的条目。
    """
    if not image:
        raise ReceiptError("图片内容为空")

    engine = engine_name()
    if engine == "none":
        raise ReceiptError(
            "小票识别未启用（需设置 OCR_PROVIDER=api 与 VISION_API_KEY，"
            "或 OCR_PROVIDER=dify 与 DIFY_API_KEY）；可先用文本输入记账"
        )

    try:
        raw_text, items = (
            _recognize_dify(image, content_type)
            if engine == "dify"
            else _recognize_vision(image, content_type)
        )
    except ReceiptError:
        raise
    except Exception as exc:  # 网络 / 超时 / 非 2xx / 返回结构异常
        raise ReceiptError(f"小票识别调用失败：{exc}") from exc

    if not items:
        raise ReceiptError(_NO_RESULT)
    return raw_text, items
