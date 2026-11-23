"""Tab1 记账对话：记账草稿闭环 + 自然语言查账 + OCR 草稿勾选。

交互分流：
- 记账语句 → POST /records/parse → 草稿确认卡 → POST /records 入库；
- 查询问句 → POST /query → 只展示后端 answer_text 与 table（前端不算数）；
- 小票图片 → POST /records/ocr → 多笔 drafts 勾选后逐条入库。

clarify_question 非空时只出 AI 反问气泡，不渲染确认卡，多轮用同一 session_id。
"""

import os
import re
import uuid

import gradio as gr

import api
import mock
from config import CATEGORIES, MOCK_FALLBACK
from ui import cards as c
from ui import chat as chatui
from ui.chat import GREETING


def _category_choices() -> list[str]:
    """GET /categories 优先；未连通时用本地 8 类兜底。"""
    try:
        cats = api.list_categories()
        return cats if cats else list(CATEGORIES)
    except api.ApiError:
        return list(CATEGORIES)

# 契约允许纯日期或带时分（小票 OCR 草稿会带时间），见 docs/api.md §2.2
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?$")
# 命中这些词视为查账问句，交给后端 /query；其余输入仍走记账解析
_QUERY_KEYWORDS = (
    "多少", "几笔", "几元", "占比", "比例", "趋势", "走势", "最多", "排行",
    "排名", "哪类", "哪一类", "哪个类别", "哪种", "分别", "统计", "查询",
    "查一下", "查查", "总结一下",
)


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
        # 网络失败或接口未实现（1002）才降级 Mock；其他业务错误照实提示，避免掩盖后端问题
        if api.should_fallback(exc):
            return mock.parse_record(text, session_id), mock.NOTICE
        return None, exc.message


def _is_query_intent(text: str) -> bool:
    """区分查账问句与记账语句，避免把「花了 32 块」误判成提问。"""
    value = text or ""
    return any(keyword in value for keyword in _QUERY_KEYWORDS)


def _run_query(question: str, session_id: str) -> tuple[dict | None, str]:
    """调用 /query；后端不可达且允许时降级 Mock，业务错误照实返回。"""
    try:
        return api.query(question, session_id), ""
    except api.ApiError as exc:
        if api.should_fallback(exc):
            return mock.query(question, session_id), mock.NOTICE
        return None, exc.message


def _ocr_label(index: int, draft: dict) -> str:
    fields = draft.get("fields") or {}
    merchant = fields.get("merchant") or "商户未识别"
    return f"{index + 1}. {merchant} · {c.format_yuan(fields.get('amount'))}"


def recognize_receipt(file_path, history: list):
    """上传小票 → 识别为多笔草稿（后端 2002 时如实提示，不伪造结果）。"""
    history = list(history or [])
    if not file_path:
        return (
            history, [], "", c.tip("请先选择一张小票图片。", kind="warn"),
            gr.update(choices=[], value=[]), gr.update(visible=False),
        )

    history = _append(history, "user", f"[小票] {os.path.basename(file_path)}")
    try:
        result = api.ocr_receipt(file_path)
        notice = ""
    except api.ApiError as exc:
        if api.should_fallback(exc):
            result = mock.ocr_receipt()
            notice = mock.NOTICE
        else:
            history = _append(history, "assistant", f"小票识别失败：{exc.message}")
            return (
                history, [], "", c.tip(f"小票识别失败：{exc.message}", kind="error"),
                gr.update(choices=[], value=[]), gr.update(visible=False),
            )

    drafts = result.get("drafts") or []
    if not drafts:
        history = _append(history, "assistant", "未识别到消费条目，请换一张更清晰的小票。")
        return (
            history, [], "", c.empty_state("未识别到消费条目", "请换一张更清晰的小票。"),
            gr.update(choices=[], value=[]), gr.update(visible=False),
        )

    choices = [_ocr_label(index, draft) for index, draft in enumerate(drafts)]
    card = c.ocr_drafts_card(drafts, result.get("ocr_engine") or "")
    if notice:
        card += c.tip(notice, kind="warn")
    history = _append(history, "assistant", f"识别到 {len(drafts)} 笔草稿，请在右侧勾选后入库。")
    return (
        history, drafts, result.get("raw_text") or "", card,
        gr.update(choices=choices, value=choices), gr.update(visible=True),
    )


def confirm_ocr(selected, drafts: list, raw_text: str, history: list):
    """仅把勾选的小票草稿逐条入库；前端不修改后端返回的金额。"""
    history = list(history or [])
    if not selected or not drafts:
        history = _append(history, "assistant", "请先勾选至少要入库的小票条目。")
        return (
            history, [], "", gr.update(choices=[], value=[]), gr.update(visible=False),
        )

    saved: list[str] = []
    failed: list[str] = []
    notices: list[str] = []
    for label in selected:
        try:
            index = int(str(label).split(".", 1)[0]) - 1
        except (TypeError, ValueError):
            continue
        if not (0 <= index < len(drafts)):
            continue
        draft = drafts[index]
        fields = draft.get("fields") or {}
        amount = fields.get("amount")
        if not isinstance(amount, (int, float)) or amount <= 0:
            failed.append(f"{label}（金额缺失）")
            continue
        payload = {
            "draft_id": draft.get("draft_id"),
            "amount": amount,
            "category": fields.get("category") or "其他",
            "merchant": fields.get("merchant") or None,
            "occurred_at": fields.get("occurred_at") or "",
            "note": fields.get("note") or None,
            "raw_text": raw_text or f"小票：{fields.get('merchant') or fields.get('category') or ''}",
            "source": "ocr",
        }
        try:
            result = api.create_record(payload)
        except api.ApiError as exc:
            if api.should_fallback(exc):
                result = mock.create_record(payload)
                notices.append(mock.NOTICE)
            else:
                failed.append(f"{label}（{exc.message}）")
                continue
        saved.append(str(result.get("id") or "?"))

    if saved:
        history = _append(history, "assistant", f"小票已入库 {len(saved)} 笔（记录 id：{'、'.join(saved)}）。")
    if failed:
        history = _append(history, "assistant", "以下条目未入库：" + "；".join(failed))
    if notices:
        history = _append(history, "assistant", f"_{notices[0]}_")
    return (
        history, [], "", gr.update(choices=[], value=[]), gr.update(visible=False),
    )


def discard_ocr():
    """放弃整张小票草稿。"""
    return (
        [], "", c.tip("已放弃小票草稿。"),
        gr.update(choices=[], value=[]), gr.update(visible=False),
    )


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

    # 查账问句：只渲染后端算好的 answer_text / table，不在前端计算
    if _is_query_intent(text):
        result, notice = _run_query(text, session_id)
        if result is None:
            history = _append(history, "assistant", f"查账失败：{notice}")
        else:
            content = result.get("answer_text") or "（后端未返回回答文案）"
            table_md = chatui.query_table_markdown(result.get("table") or [])
            if table_md:
                content = f"{content}\n\n{table_md}"
            if notice:
                content = f"{content}\n\n_{notice}_"
            history = _append(history, "assistant", content)
        form_values = _form_values(draft) if draft else _empty_form()
        return (history, "", session_id, draft, card, form_visible, *form_values)

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

    content = chatui.draft_summary(draft)
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
        return history, draft, c.tip("消费时间格式应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM，例如 2026-11-16 09:30。", kind="error"), gr.update(visible=True)

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
        if api.should_fallback(exc):
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


def reset_all():
    """清空对话、记账草稿与 OCR 草稿。"""
    return (
        *reset(),
        [],
        "",
        c.tip("已放弃小票草稿。"),
        gr.update(choices=[], value=[]),
        gr.update(visible=False),
    )


def transcribe_voice(audio_path, history: list):
    """录音结束 → POST /voice → 转写文本回填输入框（不直接入库）。

    设计决策（week2 文档 A1，最高性价比）：转写结果必须让用户过目一遍再发送，
    可纠正 ASR 错字、可撤回；麦克风不可用时自然降级为键盘输入。
    """
    if not audio_path:
        return gr.update(), gr.update(), gr.update()

    try:
        result = api.voice_transcribe(audio_path)
        notice = ""
    except api.ApiError as exc:
        if api.should_fallback(exc):
            result = mock.voice_transcribe(audio_path)
            notice = mock.NOTICE
        else:
            text = f"语音识别失败：{exc.message}。请直接打字输入。"
            return (history or []) + [{"role": "assistant", "content": c.tip(text, kind="error")}], gr.update(), gr.update(value=None)

    text = (result.get("text") or "").strip()
    if not text:
        tip = c.tip("没有识别到内容，请离麦克风近一点重试，或直接打字。", kind="warn")
        return (history or []) + [{"role": "assistant", "content": tip}], gr.update(), gr.update(value=None)

    bubble = f"🎙 已转写：**{text}**\n\n请核对文字（可直接修改输入框），确认无误后点发送。"
    if notice:
        bubble += f"\n\n_{notice}_"
    return (history or []) + [{"role": "assistant", "content": bubble}], gr.update(value=text), gr.update(value=None)


def open_attach_menu():
    """🎤 按钮展开附件面板（含录音组件）。"""
    return gr.update(visible=True), True


def toggle_ocr_menu(visible: bool):
    """加号按钮展开 / 收起上传入口菜单。"""
    next_visible = not bool(visible)
    return gr.update(visible=next_visible), next_visible


def reset_full():
    """清空对话与草稿，同时收起加号菜单。"""
    return (*reset_all(), gr.update(visible=False), False)


def build_chat_tab() -> dict:
    session_state = gr.State(new_session_id())
    draft_state = gr.State(None)
    ocr_drafts_state = gr.State([])
    ocr_raw_state = gr.State("")
    ocr_menu_state = gr.State(False)

    with gr.Row(equal_height=False):
        with gr.Column(scale=3, elem_classes=["fa-panel"]):
            gr.HTML(c.section_head("对话记账", "一句话 → 草稿 → 确认入库"))
            chatbot = gr.Chatbot(
                label="记账对话",
                value=[{"role": "assistant", "content": GREETING}],
                height=380,
                autoscroll=True,  # 新消息自动滚动到底部（week2 P0-2 / P1-3）
                elem_classes=["fa-chat"],
            )

            # 底部输入栏：＋ 展开附件面板 / 文本输入 / 语音输入占位 / 发送。
            # 图标统一用 CSS 数据 URI 绘制（见 style.css），避免系统字体把 ＋/➤/▣
            # 这类符号渲染成与文字重叠的图形。
            with gr.Group(elem_classes=["fa-composer-wrap"]):
                with gr.Row(elem_classes=["fa-composer"]):
                    plus_btn = gr.Button(
                        "＋",
                        elem_classes=["fa-icon-btn fa-plus-btn"],
                        min_width=42,
                        scale=0,
                    )
                    text_input = gr.Textbox(
                        show_label=False,
                        placeholder="说一句话记一笔…",
                        lines=1,
                        max_lines=3,
                        scale=1,
                        container=False,
                        elem_classes=["fa-composer-input"],
                    )
                    voice_btn = gr.Button(
                        "🎤",
                        elem_classes=["fa-icon-btn fa-voice-btn"],
                        min_width=36,
                        scale=0,
                    )
                    send_btn = gr.Button(
                        "➤",
                        elem_classes=["fa-icon-btn fa-send-btn"],
                        min_width=42,
                        scale=0,
                    )

                # 参考 DeepSeek 的「＋」弹出菜单：锚定在输入栏上方的小浮层，
                # 用「圆形图标 + 文案 + 右侧说明」的列表行，而不是大块方形磁贴。
                with gr.Group(visible=False, elem_classes=["fa-attach-panel"]) as ocr_menu:
                    gr.HTML('<div class="fa-attach-title">添加内容</div>')
                    with gr.Column(elem_classes=["fa-attach-list"]):
                        voice_audio = gr.Audio(
                            sources=["microphone"],
                            type="filepath",  # numpy 拿不到可上传的文件对象（week2 P1-1）
                            label="🎤 按住说话（建议 ≤60 秒，说完自动转写）",
                            interactive=True,
                            elem_classes=["fa-attach-item fa-item-voice"],
                        )
                        photo_file = gr.File(
                            label="拍照识别",
                            file_types=["image"],
                            interactive=True,
                            elem_classes=["fa-attach-item fa-item-photo"],
                        )
                        album_file = gr.File(
                            label="相册识别",
                            file_types=["image"],
                            interactive=True,
                            elem_classes=["fa-attach-item fa-item-album"],
                        )
                        gr.Button(
                            "Excel 导入",
                            interactive=False,
                            elem_classes=["fa-attach-item fa-item-excel"],
                        )
                    with gr.Row(elem_classes=["fa-attach-foot"]):
                        gr.HTML(
                            '<span class="fa-attach-note">Excel 导入为占位入口，暂未开放</span>'
                        )
                        clear_btn = gr.Button(
                            "清空对话与草稿",
                            elem_classes=["fa-text-btn"],
                            min_width=0,
                            scale=0,
                        )

        with gr.Column(scale=2):
            gr.HTML(c.section_head("草稿确认卡", "确认后才会入库"))
            draft_area = gr.HTML(c.draft_card_placeholder())
            with gr.Group(visible=False) as draft_form:
                amount_in = gr.Number(label="金额 (¥)", precision=2, minimum=0)
                category_in = gr.Dropdown(
                    choices=_category_choices(),  # GET /categories 优先（P0-2），未连通时本地枚举兜底
                    label="类别",
                    interactive=True,
                )
                merchant_in = gr.Textbox(label="商户（可空）")
                occurred_in = gr.Textbox(label="消费时间（YYYY-MM-DD）", placeholder="2026-11-16")
                note_in = gr.Textbox(label="备注（可空）")
                with gr.Row(elem_classes=["fa-toolbar"]):
                    confirm_btn = gr.Button("确认入库", variant="primary", scale=2)
                    discard_btn = gr.Button("放弃草稿", variant="stop", scale=1)

            with gr.Group(visible=False) as ocr_panel:
                gr.HTML(c.section_head("小票草稿", "勾选需要的条目后入库"))
                ocr_info = gr.HTML(c.empty_state("尚未识别小票", "上传图片后将自动识别。"))
                ocr_choices = gr.CheckboxGroup(
                    label="选择要入库的条目", choices=[], value=[]
                )
                with gr.Row(elem_classes=["fa-toolbar"]):
                    ocr_confirm_btn = gr.Button("入库所选", variant="primary", scale=2)
                    ocr_discard_btn = gr.Button("放弃小票草稿", variant="stop", scale=1)

    gr.HTML(
        c.tip(
            "交互约定：问句（含「多少 / 占比 / 趋势」等）走查账接口，只展示后端算好的回答与表格；"
            "记账语句生成草稿，确认后才入库；点「🎤」或「＋」可录音转写（回填文本框确认后发送）"
            "与拍照 / 相册小票识别，Excel 导入为占位入口。麦克风不可用时请直接打字。"
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

    confirm_event = confirm_btn.click(
        confirm_record,
        inputs=[draft_state, amount_in, category_in, merchant_in, occurred_in, note_in, chatbot, session_state],
        outputs=[chatbot, draft_state, draft_area, draft_form],
    )
    discard_btn.click(discard_draft, inputs=[draft_state], outputs=[draft_state, draft_area, draft_form])

    ocr_outputs = [ocr_drafts_state, ocr_raw_state, ocr_info, ocr_choices, ocr_panel]
    ocr_event_outputs = [chatbot, *ocr_outputs]
    photo_file.change(recognize_receipt, inputs=[photo_file, chatbot], outputs=ocr_event_outputs)
    album_file.change(recognize_receipt, inputs=[album_file, chatbot], outputs=ocr_event_outputs)
    voice_btn.click(
        open_attach_menu,
        inputs=None,
        outputs=[ocr_menu, ocr_menu_state],
    )
    # 录音结束自动转写：回填文本框 + 清空录音组件，等待用户确认发送
    voice_audio.change(
        transcribe_voice,
        inputs=[voice_audio, chatbot],
        outputs=[chatbot, text_input, voice_audio],
    )
    ocr_confirm_event = ocr_confirm_btn.click(
        confirm_ocr,
        inputs=[ocr_choices, ocr_drafts_state, ocr_raw_state, chatbot],
        outputs=ocr_event_outputs,
    )
    ocr_discard_btn.click(discard_ocr, outputs=ocr_outputs)

    plus_btn.click(
        toggle_ocr_menu,
        inputs=[ocr_menu_state],
        outputs=[ocr_menu, ocr_menu_state],
    )
    clear_btn.click(
        reset_full,
        outputs=[*respond_outputs, *ocr_outputs, ocr_menu, ocr_menu_state],
    )

    return {
        "chatbot": chatbot,
        "text_input": text_input,
        "send_btn": send_btn,
        "ocr_file": album_file,
        "photo_file": photo_file,
        "album_file": album_file,
        "ocr_menu": ocr_menu,
        "voice_btn": voice_btn,
        "voice_audio": voice_audio,
        "ocr_choices": ocr_choices,
        "ocr_confirm_btn": ocr_confirm_btn,
        "ocr_discard_btn": ocr_discard_btn,
        "clear_btn": clear_btn,
        "draft_area": draft_area,
        "draft_form": draft_form,
        "confirm_btn": confirm_btn,
        "confirm_event": confirm_event,
        "ocr_confirm_event": ocr_confirm_event,
        "discard_btn": discard_btn,
        "session_state": session_state,
        "draft_state": draft_state,
        "ocr_drafts_state": ocr_drafts_state,
        "ocr_raw_state": ocr_raw_state,
    }
