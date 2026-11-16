"""Tab4 预算中心：月度预算设定 + 使用进度与提醒。

Day 1：设定表单与进度卡骨架（含 normal / warning / over 三种状态样式示意）。
Day 6：接 POST /budgets、GET /budgets、GET /budgets/alerts?month=、GET /categories。
"""

import gradio as gr

from config import CATEGORIES, TOTAL_BUDGET_LABEL
from ui import components as c


def build_budget_tab() -> dict:
    with gr.Row(equal_height=False):
        with gr.Column(scale=2, elem_classes=["fa-panel"]):
            gr.HTML(c.section_head("设定月度预算", "类别预算与总额预算双维度"))
            month_input = gr.Textbox(label="月份", placeholder="2026-11")
            category_input = gr.Dropdown(
                label="预算维度",
                choices=[TOTAL_BUDGET_LABEL] + CATEGORIES,
                value=TOTAL_BUDGET_LABEL,
            )
            amount_input = gr.Number(label="预算金额 (¥)", minimum=0.01, precision=2)
            with gr.Row(elem_classes=["fa-toolbar"]):
                save_btn = gr.Button("保存预算", variant="primary")
                refresh_btn = gr.Button("查看进度", variant="secondary")
            gr.HTML(
                c.tip(
                    "同一月份同一维度重复设定时按后端规则覆盖；使用率由后端计算，"
                    "前端只按 used_ratio 渲染颜色。"
                )
            )

        with gr.Column(scale=3):
            gr.HTML(c.section_head("预算进度与提醒", "已用 ≥80% 预警、≥100% 超支"))
            progress_area = gr.HTML(c.budget_placeholder())

    status_area = gr.HTML(
        c.empty_state(
            "预算状态",
            "设定后在此显示保存结果（当前为 Day 1 骨架，接口于 Day 6 接入）。",
        )
    )

    # ---------------- 骨架阶段的占位交互（Day 6 替换为真实调用） ----------------
    save_btn.click(
        lambda: c.todo_notice("预算设定 POST /budgets", "Day 6"), outputs=status_area
    )
    refresh_btn.click(
        lambda: c.todo_notice("预算预警 GET /budgets/alerts", "Day 6"),
        outputs=progress_area,
    )

    return {
        "month_input": month_input,
        "category_input": category_input,
        "amount_input": amount_input,
        "save_btn": save_btn,
        "refresh_btn": refresh_btn,
        "progress_area": progress_area,
        "status_area": status_area,
    }
