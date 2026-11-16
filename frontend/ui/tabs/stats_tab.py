"""Tab3 统计图表：月度指标卡 + 类别饼图 + 每日趋势折线。

Day 1：指标卡与 ECharts 容器占位。
Day 5：接 /stats/summary、/stats/by-category、/stats/trend，用 gr.HTML 注入 ECharts。
"""

import gradio as gr

from ui import components as c


def build_stats_tab() -> dict:
    with gr.Row(elem_classes=["fa-toolbar"]):
        month_input = gr.Textbox(label="统计月份", placeholder="2026-11", scale=2)
        days_input = gr.Dropdown(
            label="趋势天数", choices=[7, 14, 30], value=30, scale=1
        )
        refresh_btn = gr.Button("刷新统计", variant="primary", scale=1)

    metrics = gr.HTML(
        c.metric_cards(
            [
                ("本月支出总额", "¥ --", "GET /stats/summary"),
                ("本月笔数", "-- 笔", "仅统计已确认记录"),
                ("日均支出", "¥ --", "总额 ÷ 当月已过天数"),
            ]
        )
    )

    with gr.Row(equal_height=True):
        with gr.Column(scale=1):
            gr.HTML(c.section_head("类别占比", "GET /stats/by-category"))
            pie_chart = gr.HTML(
                c.chart_placeholder("fa-pie-chart", "ECharts 饼图", "Day 5 接入")
            )
        with gr.Column(scale=1):
            gr.HTML(c.section_head("每日趋势", "GET /stats/trend?days="))
            trend_chart = gr.HTML(
                c.chart_placeholder("fa-trend-chart", "ECharts 折线图", "Day 5 接入")
            )

    gr.HTML(
        c.tip(
            "图表数据完全来自后端聚合结果，前端只做渲染；查账回答也只展示后端返回的 "
            "answer_text 与 table。"
        )
    )

    # ---------------- 骨架阶段的占位交互（Day 5 替换为真实调用） ----------------
    refresh_btn.click(
        lambda: c.todo_notice("统计接口 /stats/*", "Day 5"),
        outputs=metrics,
    )

    return {
        "month_input": month_input,
        "days_input": days_input,
        "refresh_btn": refresh_btn,
        "metrics": metrics,
        "pie_chart": pie_chart,
        "trend_chart": trend_chart,
    }
