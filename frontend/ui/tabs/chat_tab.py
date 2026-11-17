"""Tab1 记账对话：聊天流 + 草稿确认卡 + 确认入库闭环。

Day 3 核心交互（前端注意事项 4/5 条）：
- /records/parse 只生成草稿，确认卡上「确认入库」才调 POST /records；
- clarify_question 非空时只出 AI 反问气泡，不渲染确认卡，多轮用同一 session_id；
- 确认卡下方表单可直接修改字段后提交（等价于「修改 → 重新提交」）。
第二周：/records/ocr 多笔草稿勾选。
"""

import re
import uuid

import gradio as gr

import api
import mock
from config import CATEGORIES, MOCK_FALLBACK
from ui import components as c

GREETING = (
    "你好，我是记账助手。直接说一句话就能记账，比如「昨天打车 32 块」。\n\n"
    "信息不全时我会反问你，补齐后在右侧确认卡核对入库。"
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def new_session_id() -> str:
    """后端会话标识，供澄清反问多轮拼接上下文使用。"""
    return f"s_{uuid.uuid4().hex[:8]}"


def _append(history: list, role: str, content: str) -> list:
    history = list(history or [])
    history.append({"role": role, "content": content})
    return history


def _parse_draft(text: str, session_id: str) -> tuple[dict | None, str]:
    """解析一句话为草稿；后端不可达时按开关降级本地 Mock。

    返回 (draft, notice)；draft 为 None 表示解析失败（notice 为错误信息）。
    """
    try:
        return api.parse_record(text, session_id), ""
    except api.ApiError as exc:
        # 只有网络层失败才降级 Mock；业务错误照实提示，避免掩盖后端问题
        if exc.is_network_error and MOCK_FALLBACK:
            return mock.parse_record(text, session_id), mock.NOTICE
        return None, exc.message


def _empty_form():
    return None, None, "", "", ""


def _form_values(draft: dict):
    fields = draft.get("fields") or {}
    return (
        fields.get("amount"),
        fields.get("category"),
        fields.get("merchant") or "",
        fields.get("occurred_at") or "",
        fields.get("note") or "",
    )


def respond(message: str, history: list, session_id: str, draft: dict | None):
    """发送一句话 → 用户气泡 → 调用解析 → AI 气泡（草稿摘要或反问）+ 确认卡。"""
    text = (message or "").strip()
    history = list(history or [])
    card = c.draft_card(draft) if draft else c.draft_card_placeholder()
    form_visible = gr.update(visible=draft is not None)

    if not text:
        return (history, "", session_id, draft, card, form_visible, *_empty_form())

    session_id = session_id or new_session_id()
    history = _append(history, "user", text)

    # 多轮澄清：把补充语句拼进原始输入，便于后端 / Mock 合并槽位
    prev_text = (draft or {}).get("raw_text") or ""
    raw_text = f"{prev_text} {text}".strip()

    parsed, notice = _parse_draft(raw_text, session_id)
    if parsed is None:
        history = _append(history, "assistant", f"解析失败：{notice}")
        return (history, "", session_id, draft, card, form_visible, *_empty_form())

    draft = dict(parsed)
    draft["raw_text"] = raw_text

    question = draft.get("clarify_question")
    if question:
        # 注意事项 5：只出反问气泡，不渲染确认卡
        history = _append(history, "assistant", question)
        if notice:
            history = _append(history, "assistant", f"_{notice}_")
        return (history, "", session_id, draft, c.draft_card_placeholder(), gr.update(visible=False), *_empty_form())

    content = c.draft_summary(draft)
    if notice:
        content = f"{content}\n\n_{notice}_"
    history = _append(history, "assistant", content)

    return (history, "", session_id, draft, c.draft_card(draft), gr.update(visible=True), *_form_values(draft))


def confirm_record(draft: dict | None, amount, category, merchant, occurred_at, note, history: list, session_id: str):
    """确认入库：前端只做格式校验，金额与统计口径以后端为准。"""
    history = list(history or [])
    if draft is None:
        return history, draft, c.tip("当前没有待确认的草稿，请先在左侧输入一句话。", kind="warn"), gr.update(visible=False)

    amount_value = float(amount) if amount is not None else None
    if amount_value is None or amount_value <= 0:
        return history, draft, c.tip("金额必须大于 0，请修改后重试。", kind="error"), gr.update(visible=True)
    if not category:
        return history, draft, c.tip("类别不能为空，请从 8 类固定枚举中选择。", kind="error"), gr.update(visible=True)
    occurred_at = (occurred_at or "").strip()
    if not _DATE_RE.match(occurred_at):
        return history, draft, c.tip("消费时间格式应为 YYYY-MM-DD，例如 2026-11-16。", kind="error"), gr.update(visible=True)

    payload = {
        "draft_id": draft.get("draft_id"),
        "amount": amount_value,
        "category": category,
        "merchant": (merchant or "").strip() or None,
        "occurred_at": occurred_at,
        "note": (note or "").strip() or None,
        "raw_text": draft.get("raw_text") or "",
        "source": "text",
    }

    notice = ""
    try:
        result = api.create_record(payload)
    except api.ApiError as exc:
        if exc.is_network_error and MOCK_FALLBACK:
            result = mock.create_record(payload)
            notice = mock.NOTICE
        else:
            return history, draft, c.tip(f"入库失败：{exc.message}", kind="error"), gr.update(visible=True)

    record_id = result.get("id")
    history = _append(history, "assistant", f"已确认入库（记录 id {record_id}）。可以继续记下一笔。")
    if notice:
        history = _append(history, "assistant", f"_{notice}_")
    return history, None, c.created_card(record_id, notice), gr.update(visible=False)


def discard_draft(draft: dict | None):
    """放弃当前草稿，回到占位卡。"""
    return None, c.draft_card_placeholder(), gr.update(visible=False)


def reset():
    """清空对话与草稿卡。"""
    return (
        [{"role": "assistant", "content": GREETING}],
        "",
        new_session_id(),
        None,
        c.draft_card_placeholder(),
        gr.update(visible=False),
        *_empty_form(),
    )


def build_chat_tab() -> dict:
    session_state = gr.State(new_session_id())
    draft_state = gr.State(None)

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
            with gr.Group(visible=False) as draft_form:
                amount_in = gr.Number(label="金额 (¥)", precision=2, minimum=0)
                category_in = gr.Dropdown(choices=CATEGORIES, label="类别", interactive=True)
                merchant_in = gr.Textbox(label="商户（可空）")
                occurred_in = gr.Textbox(label="消费时间（YYYY-MM-DD）", placeholder="2026-11-16")
                note_in = gr.Textbox(label="备注（可空）")
                with gr.Row(elem_classes=["fa-toolbar"]):
                    confirm_btn = gr.Button("确认入库", variant="primary", scale=2)
                    discard_btn = gr.Button("放弃草稿", variant="stop", scale=1)

    gr.HTML(
        c.tip(
            "交互约定：clarify_question 非空时以 AI 气泡继续反问，不渲染确认卡；"
            "多商品小票返回 drafts 数组，支持勾选部分入库（第二周）。"
        )
    )

    # ---------------- 事件绑定 ----------------
    respond_inputs = [text_input, chatbot, session_state, draft_state]
    respond_outputs = [
        chatbot,
        text_input,
        session_state,
        draft_state,
        draft_area,
        draft_form,
        amount_in,
        category_in,
        merchant_in,
        occurred_in,
        note_in,
    ]
    send_btn.click(respond, inputs=respond_inputs, outputs=respond_outputs)
    text_input.submit(respond, inputs=respond_inputs, outputs=respond_outputs)

    confirm_btn.click(
        confirm_record,
        inputs=[draft_state, amount_in, category_in, merchant_in, occurred_in, note_in, chatbot, session_state],
        outputs=[chatbot, draft_state, draft_area, draft_form],
    )
    discard_btn.click(discard_draft, inputs=[draft_state], outputs=[draft_state, draft_area, draft_form])
    clear_btn.click(reset, outputs=respond_outputs)
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
        "draft_form": draft_form,
        "confirm_btn": confirm_btn,
        "discard_btn": discard_btn,
        "session_state": session_state,
        "draft_state": draft_state,
    }
