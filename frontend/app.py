"""记账小助手 · Gradio 前端入口。

Day 1 目标：搭出五区骨架，接口在 Day 2~6 逐步接入。

启动方式（在 frontend 目录下）：
    pip install -r requirements.txt
    python app.py

分层（week2 文档 §2）：
    app.py   只做 Blocks 编排与事件绑定，不写业务逻辑
    api.py   所有 HTTP 调用的唯一出口
    ui/cards.py    卡片与通用 HTML 原语
    ui/charts.py   Plotly 图表工厂
    ui/chat.py     聊天气泡文案层
    ui/alerts.py   顶部提醒横幅渲染
    ui/tabs/*      五个页签的构建函数

分区：
    Tab1 记账对话（聊天流 + 草稿确认卡）
    Tab2 明细管理（表格 + 增删改）
    Tab3 统计图表（饼图 + 趋势）
    Tab4 预算中心（进度 + 提醒）
    Tab5 演示入口（一键灌入 / 清空演示数据）
"""

import os
from datetime import date

import gradio as gr

import api
import mock
from config import APP_TITLE, SERVER_NAME, SERVER_PORT
from ui import alerts
from ui import cards as c
from ui.tabs import (
    build_budget_tab,
    build_chat_tab,
    build_demo_tab,
    build_records_tab,
    build_stats_tab,
)
from ui.theme import APP_CSS, app_theme


def _fetch_alerts() -> tuple[list, str]:
    """GET /budgets/alerts；未连通且允许时降级 Mock（数据/状态仍由后端口径产出）。"""
    month = date.today().strftime("%Y-%m")
    try:
        return (api.budget_alerts(month).get("items") or []), ""
    except api.ApiError as exc:
        if api.should_fallback(exc):
            return (mock.budget_alerts(month).get("items") or []), mock.NOTICE
        return [], exc.message


def refresh_banner(dismissed: set):
    """拉取预警并渲染横幅；返回 (横幅 HTML, 当前预警列表)。"""
    items, notice = _fetch_alerts()
    return alerts.banner_html(items, dismissed, notice), items


def dismiss_banner(items: list, dismissed: set):
    """关闭按钮：把当前活跃提醒全部标记已读（本会话内不再弹同一条）。"""
    dismissed = set(dismissed or ()) | {alerts.alert_key(item) for item in items or []}
    return alerts.banner_html(items, dismissed, ""), dismissed


def create_app() -> gr.Blocks:
    """构建 Gradio Blocks 应用（五区骨架 + 顶部提醒横幅）。"""
    with gr.Blocks(title=APP_TITLE, analytics_enabled=False) as demo:
        gr.HTML(c.header())

        # 顶部提醒横幅（P1-2）：分级红/橙，可关闭，事件驱动刷新 + Timer 兜底
        dismissed_state = gr.State(set())
        alerts_state = gr.State([])
        with gr.Row(equal_height=True, visible=True):
            banner = gr.HTML("", elem_classes=["fa-banner-wrap"])
            dismiss_btn = gr.Button("✕", elem_classes=["fa-banner-close"], scale=0)

        with gr.Tabs():
            with gr.Tab("记账对话", id="tab-chat"):
                chat_handles = build_chat_tab()
            with gr.Tab("明细管理", id="tab-records") as records_tab_item:
                records_handles = build_records_tab()
            with gr.Tab("统计图表", id="tab-stats") as stats_tab_item:
                stats_handles = build_stats_tab()
            with gr.Tab("预算中心", id="tab-budget") as budget_tab_item:
                budget_handles = build_budget_tab()
            with gr.Tab("演示入口", id="tab-demo") as demo_tab_item:
                demo_handles = build_demo_tab()

        # 首次切到明细页时自动加载第一页（后端未启动时降级本地演示数据）
        records_tab_item.select(
            records_handles["initial_load"],
            inputs=None,
            outputs=records_handles["list_outputs"],
        )
        # 首次切到统计页时自动刷新三块统计
        stats_tab_item.select(
            stats_handles["initial_load"],
            inputs=None,
            outputs=stats_handles["stats_outputs"],
        )
        # 首次切到预算页时自动加载预警进度
        budget_tab_item.select(
            budget_handles["initial_load"],
            inputs=None,
            outputs=budget_handles["initial_outputs"],
        )

        # ---- 横幅刷新时机（P1-2）：页面加载 / 切预算页 / 入库成功 / 演示灌入，Timer(60) 兜底 ----
        banner_inputs = [dismissed_state]
        banner_outputs = [banner, alerts_state]
        demo.load(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        budget_tab_item.select(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        chat_handles["confirm_event"].then(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        chat_handles["ocr_confirm_event"].then(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        demo_handles["load_event"].then(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        demo_handles["reset_event"].then(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        timer = gr.Timer(60)
        timer.tick(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)

        # ---- 关闭横幅：按 category+status 指纹标记已读，本会话内不再弹同一条 ----
        dismiss_btn.click(
            dismiss_banner,
            inputs=[alerts_state, dismissed_state],
            outputs=[banner, dismissed_state],
        )

        gr.HTML(c.footer_note())

    return demo


def launch() -> None:
    """启动前端服务（Gradio 6 起 theme / css 需在 launch 时传入）。"""
    # 本机服务不走系统代理：代理软件开启时会把 localhost 自检请求劫持掉，
    # 导致 Gradio launch 报 404（httpx 默认信任环境代理，用 NO_PROXY 豁免）。
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
    os.environ.setdefault("no_proxy", "localhost,127.0.0.1")
    create_app().launch(
        server_name=SERVER_NAME,
        server_port=SERVER_PORT,
        show_error=True,
        theme=app_theme(),
        css=APP_CSS,
    )


if __name__ == "__main__":
    launch()
