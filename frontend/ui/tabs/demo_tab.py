"""演示入口区：一键灌入 / 清空演示数据，附后端连通性自检。

Day 1：界面与按钮骨架。
Day 2：接后端健康检查；Day 6：接 POST /demo/load、POST /demo/reset。
"""

import gradio as gr

from config import API_BASE_URL
from ui import components as c


def build_demo_tab() -> dict:
    gr.HTML(c.demo_card())

    with gr.Row(elem_classes=["fa-toolbar"]):
        load_btn = gr.Button("一键灌入演示数据", variant="primary", scale=2)
        reset_btn = gr.Button("清空演示数据", variant="stop", scale=1)
        health_btn = gr.Button("检查后端连通性", variant="secondary", scale=1)

    result_area = gr.HTML(
        c.empty_state(
            "尚未执行操作",
            "加载后到「明细」「统计」「预算」页查看效果；清空会删除演示数据与演示预算。",
        )
    )

    gr.HTML(
        c.tip(
            f"当前后端地址：{API_BASE_URL}　（环境变量 API_BASE_URL 可覆盖）"
            "　演示数据约 60 笔 × 2 个月 + 3 张小票记录，覆盖 8 类并埋设娱乐超支演示点。"
        )
    )

    # ---------------- 骨架阶段的占位交互（Day 2/6 替换为真实调用） ----------------
    load_btn.click(
        lambda: c.todo_notice("演示数据 POST /demo/load", "Day 6"), outputs=result_area
    )
    reset_btn.click(
        lambda: c.todo_notice("清空演示数据 POST /demo/reset", "Day 6"),
        outputs=result_area,
    )
    health_btn.click(
        lambda: c.todo_notice("后端健康检查", "Day 2"), outputs=result_area
    )

    return {
        "load_btn": load_btn,
        "reset_btn": reset_btn,
        "health_btn": health_btn,
        "result_area": result_area,
    }
