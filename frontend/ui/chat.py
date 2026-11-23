"""聊天层渲染助手（week2 文档 §2 分层：chat.py）。

职责：聊天气泡文案与查账表格的 HTML/Markdown 生成。
气泡布局（用户右深色、AI 左白底阴影）由 style.css 覆盖 gr.Chatbot 实现；
新消息自动滚动由 gr.Chatbot(autoscroll=True) 原生承担。
"""

from datetime import datetime

from ui.cards import format_yuan

GREETING = (
    "你好，我是记账助手。说一句话就能记账，比如「昨天打车 32 块」；"
    "也能直接问我「上个月吃饭花了多少」。\n\n"
    "信息不全时我会反问你，补齐后在右侧确认卡核对入库。"
)


def stamp(text: str) -> str:
    """给气泡内容追加时间戳（P1-3：气泡带时间）。

    用 <sub> 而非内联 style——Gradio 的 Markdown 会剥离 style 属性，
    <sub> 默认更小字号，由 CSS 补透明度。
    """
    return f"{text}\n\n<sub>{datetime.now().strftime('%H:%M')}</sub>"


def draft_summary(draft: dict) -> str:
    """把归一化后的草稿整理成 AI 气泡文案（不参与任何计算）。"""
    fields = draft.get("fields") or {}
    lines = []

    amount_text = format_yuan(fields.get("amount")) if fields.get("amount") is not None else "未识别"
    lines.append(f"金额：{amount_text}")
    lines.append(f"类别：{fields.get('category') or '未识别'}")
    if fields.get("merchant"):
        lines.append(f"商户：{fields['merchant']}")
    if fields.get("occurred_at"):
        lines.append(f"时间：{fields['occurred_at']}")
    if fields.get("note"):
        lines.append(f"备注：{fields['note']}")

    confidence = draft.get("confidence")
    if isinstance(confidence, (int, float)):
        lines.append(f"置信度：{confidence * 100:.0f}%")

    missing = draft.get("missing_fields") or []
    if missing:
        lines.append(f"待补充字段：{'、'.join(missing)}")

    return "已解析为草稿（**尚未入库**）：\n\n- " + "\n- ".join(lines) + "\n\n请在右侧确认卡核对，可直接修改字段后入库。"


def query_table_markdown(table: list) -> str:
    """把后端 /query 的 table 渲染成 Markdown 表格（前端不做任何计算）。"""
    if not table:
        return ""
    lines = ["| 类别 | 金额 | 笔数 |", "|---|---:|---:|"]
    for item in table:
        category = str(item.get("category") or "—").replace("|", "\\|")
        lines.append(
            f"| {category} | {format_yuan(item.get('total'))} | {item.get('count', 0)} |"
        )
    return "\n".join(lines)
