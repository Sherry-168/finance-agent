"""Dify 工作流适配层（第二周新增）。

与李语琛交付的根目录 `agent.py` 的关系
--------------------------------------
`agent.py` 验证了「Dify 工作流 → JSON 数组」这条路可行，但它把 URL、超时、
错误处理都写死在函数体里，且只返回字符串。本模块是它的**生产化版本**：
同样的 `/workflows/run` 契约，补上可配置地址、超时、统一异常与结构化返回，
并额外满足验收项「返回数组时后端自动取首条」与「数组 / 对象双兼容」。

职责边界
--------
- 只负责「把一批输入送进工作流、把 outputs 里的 JSON 抠出来」，不认识 8 类分类、
  不做金额换算、不拼文案——槽位归一化统一在 `app.adapters.parser` 完成；
- 任何网络 / 鉴权 / 格式异常都收敛成 `DifyError`，由上层决定降级到规则解析。
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import (
    DIFY_API_KEY,
    DIFY_BASE_URL,
    DIFY_INPUT_KEY,
    DIFY_TIMEOUT,
    DIFY_USER,
    has_dify,
)

# 模型偶尔把思考过程也吐出来（DeepSeek-R1 等），一律剥掉再找 JSON
_THINK_BLOCK = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.S | re.I)
# outputs 里可能出现的正文键名，按优先级尝试
_TEXT_KEYS = ("result", "text", "output", "answer", "json", "data")


class DifyError(RuntimeError):
    """Dify 调用失败（网络 / 鉴权 / 工作流状态异常 / 输出不是 JSON）。"""


def is_configured() -> bool:
    """是否配置了 Dify Key。"""
    return has_dify()


def extract_json(payload: Any) -> Any | None:
    """从字符串 / dict / list 里抠出 JSON 值，失败返回 None。

    依次尝试：本身就是 JSON 类型 → 直接 json.loads → 去掉 ``` 代码块后再试 →
    扫描首尾括号截取（模型爱在 JSON 前后加一句「以下是结果：」）。
    """
    if isinstance(payload, (dict, list)):
        return payload
    if not isinstance(payload, str):
        return None

    text = _THINK_BLOCK.sub(" ", payload).strip()
    if not text:
        return None

    for candidate in (text, _strip_code_fence(text)):
        try:
            return json.loads(candidate)
        except ValueError:
            pass

    # 截取第一个 [ 或 { 到对应的最后一个闭合符，兼容前后有解释性文字
    for opener, closer in (("[", "]"), ("{", "}")):
        start, end = candidate.find(opener), candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except ValueError:
                continue
    return None


def _strip_code_fence(text: str) -> str:
    """去掉模型包裹的 ```json 代码块。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _pick_output(outputs: Any) -> Any:
    """从工作流的 outputs 里取出正文；取不到就原样返回 outputs。"""
    if isinstance(outputs, str):
        return outputs
    if not isinstance(outputs, dict):
        return outputs
    for key in _TEXT_KEYS:
        value = outputs.get(key)
        if isinstance(value, (str, list, dict)) and value not in ("", None):
            return value
    # 单变量工作流：outputs 只有一个值时不必关心键名
    values = [v for v in outputs.values() if isinstance(v, (str, list, dict))]
    return values[0] if len(values) == 1 else outputs


def run_workflow(
    text: str,
    *,
    inputs: dict[str, Any] | None = None,
    user: str | None = None,
) -> Any:
    """调用 Dify 工作流（blocking 模式），返回抠出的 JSON 值。

    Args:
        text: 用户原始输入，写入 `DIFY_INPUT_KEY` 指定的开始节点变量。
        inputs: 额外输入变量（如多模态场景的图片 base64），与 text 合并。
        user: Dify 侧的用户标识，缺省读配置。

    Raises:
        DifyError: 未配置 Key、网络失败、工作流非 succeeded、输出里没有 JSON。
    """
    if not is_configured():
        raise DifyError("未配置 DIFY_API_KEY")

    import httpx

    variables: dict[str, Any] = dict(inputs or {})
    variables.setdefault(DIFY_INPUT_KEY, text)

    try:
        response = httpx.post(
            f"{DIFY_BASE_URL.rstrip('/')}/workflows/run",
            headers={
                "Authorization": f"Bearer {DIFY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "inputs": variables,
                "response_mode": "blocking",
                "user": user or DIFY_USER,
            },
            timeout=DIFY_TIMEOUT,
            # 后端多在本地 / 内网，禁用系统代理避免代理软件劫持请求
            trust_env=False,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:  # 网络、超时、非 2xx、非 JSON 统一收敛
        raise DifyError(f"Dify 请求失败：{exc}") from exc

    data = body.get("data") or {}
    status = data.get("status")
    if status and status != "succeeded":
        detail = data.get("error") or body.get("message") or status
        raise DifyError(f"Dify 工作流未成功：{detail}")

    payload = extract_json(_pick_output(data.get("outputs")))
    if payload is None:
        raise DifyError("Dify 输出中没有可解析的 JSON")
    return payload


def result_list(payload: Any) -> list[dict[str, Any]]:
    """把工作流输出统一成「槽位 dict 列表」。

    兼容三种形态（验收项要求「数组 / 对象双兼容」）：
    - `[{...}, {...}]`        多笔小票 / 长截图 → 原样返回
    - `{"records": [...]}`    工作流包了一层 → 取内层数组
    - `{...}`                 单笔 → 包成单元素列表
    """
    if isinstance(payload, list):
        items = [item for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        nested = next(
            (v for v in payload.values() if isinstance(v, list)),
            None,
        )
        items = [item for item in nested if isinstance(item, dict)] if nested else [payload]
    else:
        items = []
    return items
