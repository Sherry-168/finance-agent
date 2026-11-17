"""记账小助手 · Gradio 前端入口。

Day 1 目标：搭出五区骨架，接口在 Day 2~6 逐步接入。

启动方式（在 frontend 目录下）：
    pip install -r requirements.txt
    python app.py

分区：
    Tab1 记账对话（聊天流 + 草稿确认卡）
    Tab2 明细管理（表格 + 增删改）
    Tab3 统计图表（饼图 + 趋势）
    Tab4 预算中心（进度 + 提醒）
    Tab5 演示入口（一键灌入 / 清空演示数据）
"""

import os

import gradio as gr

from config import APP_TITLE, SERVER_NAME, SERVER_PORT
from ui import components as c
from ui.tabs import (
    build_budget_tab,
    build_chat_tab,
    build_demo_tab,
    build_records_tab,
    build_stats_tab,
)
from ui.theme import APP_CSS, app_theme


def create_app() -> gr.Blocks:
    """构建 Gradio Blocks 应用（五区骨架）。"""
    with gr.Blocks(title=APP_TITLE, analytics_enabled=False) as demo:
        gr.HTML(c.header())

        with gr.Tabs():
            with gr.Tab("记账对话", id="tab-chat"):
                build_chat_tab()
            with gr.Tab("明细管理", id="tab-records") as records_tab_item:
                records_handles = build_records_tab()
            with gr.Tab("统计图表", id="tab-stats") as stats_tab_item:
                stats_handles = build_stats_tab()
            with gr.Tab("预算中心", id="tab-budget") as budget_tab_item:
                budget_handles = build_budget_tab()
            with gr.Tab("演示入口", id="tab-demo"):
                build_demo_tab()

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
            outputs=budget_handles["progress_output"],
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
