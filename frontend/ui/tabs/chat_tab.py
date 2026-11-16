"""Tab1 记账对话：聊天流 + 草稿确认卡 + OCR 上传占位入口。

Day 1：只搭界面结构（输入框、气泡流、确认卡容器）。
Day 2：接气泡渲染与消息流；Day 3：接 /records/parse 与确认入库；
Day 3+ 之后再换数据源即可接 /records/ocr（本周只留 UI 位）。
"""

import gradio as gr

from ui import components as c

GREETING = "你好，我是记账助手。直接说一句话就能记账，比如「昨天打车 32 块」。"


def build_chat_tab() -> dict:
    with gr.Row(equal_height=False):
        with gr.Column(scale=3, elem_classes=["fa-panel"]):
            gr.HTML(c.section_head("对话记账", "一句话 → 草稿 → 确认入库"))
            chatbot = gr.Chatbot(
                label="记账对话",
                value=[{"role": "assistant", "content": GREETING}],
                height=360,
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

    # ---------------- 骨架阶段的占位交互（Day 2/3 替换为真实调用） ----------------
    placeholder = lambda feature, day: (  # noqa: E731
        lambda: c.todo_notice(feature, day)
    )
    send_btn.click(
        placeholder("对话解析 POST /records/parse", "Day 3"),
        outputs=draft_area,
    )
    text_input.submit(
        placeholder("对话解析 POST /records/parse", "Day 3"),
        outputs=draft_area,
    )
    ocr_btn.click(
        placeholder("小票识别 POST /records/ocr", "第二周"),
        outputs=draft_area,
    )
    clear_btn.click(
        lambda: ([{"role": "assistant", "content": GREETING}], ""),
        outputs=[chatbot, text_input],
    )

    return {
        "chatbot": chatbot,
        "text_input": text_input,
        "send_btn": send_btn,
        "ocr_file": ocr_file,
        "ocr_btn": ocr_btn,
        "clear_btn": clear_btn,
        "draft_area": draft_area,
    }
