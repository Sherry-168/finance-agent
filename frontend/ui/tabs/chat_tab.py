"""Tab1 记账对话：聊天流 + 草稿确认卡 + OCR 上传占位入口。

Day 2：消息气泡流 + /records/parse 对接 + 澄清反问气泡（后端未起时自动走本地 Mock）。
Day 3：确认卡渲染与确认入库；第二周：/records/ocr 多笔草稿勾选。
"""

import uuid

import gradio as gr

import api
import mock
from config import MOCK_FALLBACK
from ui import components as c

GREETING = (
    "你好，我是记账助手。直接说一句话就能记账，比如「昨天打车 32 块」。\n\n"
    "信息不全时我会反问你，补齐后再生成草稿。"
)


def new_session_id() -> str:
    """后端会话标识，供澄清反问多轮拼接上下文使用。"""
    return f"s_{uuid.uuid4().hex[:8]}"


def _append(history: list, role: str, content: str) -> list:
    history = list(history or [])
    history.append({"role": role, "content": content})
    return history


def respond(message: str, history: list, session_id: str):
    """发送一句话 → 用户气泡 → 调用解析 → AI 气泡（草稿摘要或反问）。"""
    text = (message or "").strip()
    history = list(history or [])
    if not text:
        return history, "", session_id

    session_id = session_id or new_session_id()
    history = _append(history, "user", text)

    notice = ""
    try:
        draft = api.parse_record(text, session_id)
    except api.ApiError as exc:
        # 只有网络层失败才降级 Mock；业务错误照实提示，避免掩盖后端问题
        if exc.is_network_error and MOCK_FALLBACK:
            draft = mock.parse_record(text, session_id)
            notice = mock.NOTICE
        else:
            history = _append(history, "assistant", f"解析失败：{exc.message}")
            return history, "", session_id

    question = draft.get("clarify_question")
    if question:
        content = question
    else:
        content = c.draft_summary(draft)

    if notice:
        content = f"{content}\n\n_{notice}_"

    history = _append(history, "assistant", content)
    return history, "", session_id


def reset() -> tuple:
    return [{"role": "assistant", "content": GREETING}], "", new_session_id()


def build_chat_tab() -> dict:
    session_state = gr.State(new_session_id())

    with gr.Row(equal_height=False):
        with gr.Column(scale=3, elem_classes=["fa-panel"]):
            gr.HTML(c.section_head("对话记账", "一句话 → 草稿 → 确认入库"))
            chatbot = gr.Chatbot(
                label="记账对话",
                value=[{"role": "assistant", "content": GREETING}],
                height=380,
                elem_classes=["fa-chat"],
            )
            with gr.Row(elem_classes=["fa-toolbar"]):
                text_input = gr.Textbox(
                    show_label=False,
                    placeholder="例如：昨天打车 32 块",
                    lines=1,
                    max_lines=4,
                    scale=4,
                    container=False,
                )
                send_btn = gr.Button("发送", variant="primary", scale=1)
            with gr.Row(elem_classes=["fa-toolbar"]):
                ocr_file = gr.File(
                    label="小票 / 截图（OCR 第二周接入，暂不可用）",
                    file_types=["image"],
                    interactive=False,
                    height=110,
                    scale=3,
                )
                ocr_btn = gr.Button("识别小票", scale=1)
                clear_btn = gr.Button("清空对话", variant="secondary", scale=1)

        with gr.Column(scale=2):
            gr.HTML(c.section_head("草稿确认卡", "确认后才会入库"))
            draft_area = gr.HTML(c.draft_card_placeholder())

    gr.HTML(
        c.tip(
            "交互约定：clarify_question 非空时以 AI 气泡继续反问，不渲染草稿卡；"
            "多商品小票返回 drafts 数组，支持勾选部分入库。"
        )
    )

    # ---------------- 事件绑定 ----------------
    send_btn.click(
        respond,
        inputs=[text_input, chatbot, session_state],
        outputs=[chatbot, text_input, session_state],
    )
    text_input.submit(
        respond,
        inputs=[text_input, chatbot, session_state],
        outputs=[chatbot, text_input, session_state],
    )
    clear_btn.click(reset, outputs=[chatbot, text_input, session_state])
    ocr_btn.click(
        lambda: c.todo_notice("小票识别 POST /records/ocr", "第二周"),
        outputs=draft_area,
    )

    return {
        "chatbot": chatbot,
        "text_input": text_input,
        "send_btn": send_btn,
        "ocr_file": ocr_file,
        "ocr_btn": ocr_btn,
        "clear_btn": clear_btn,
        "draft_area": draft_area,
        "session_state": session_state,
    }
