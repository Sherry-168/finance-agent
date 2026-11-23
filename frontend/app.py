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
from ui.tabs.demo_tab import load_demo_data as demo_load
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
    """拉取预警并渲染横幅；返回 (横幅 HTML, 预警列表, 跳转按钮可见性)。"""
    items, notice = _fetch_alerts()
    html = alerts.banner_html(items, dismissed, notice)
    return html, items, gr.update(visible=bool(html))


def refresh_dashboard():
    """仪表盘首屏（P1-3/B5）：本月支出 + 预算剩余 + 迷你环形进度。"""
    month = date.today().strftime("%Y-%m")
    notice = ""
    try:
        summary = api.stats_summary(month)
    except api.ApiError as exc:
        if api.should_fallback(exc):
            summary = mock.stats_summary(month)
            notice = mock.NOTICE
        else:
            summary = {"total": None, "count": 0, "daily_avg": None}

    try:
        items = api.budget_alerts(month).get("items") or []
    except api.ApiError as exc:
        if api.should_fallback(exc):
            items = mock.budget_alerts(month).get("items") or []
        else:
            items = []
    total = next((i for i in items if not i.get("category")), None)
    return c.dashboard_card(summary, total, notice)


GOTO_BUDGET_JS = (
    "() => {"
    "  const el = document.getElementById('tab-budget');"
    "  if (el) { el.click(); return; }"
    "  const btn = [...document.querySelectorAll('button')]"
    "    .find(b => b.textContent.includes('预算中心'));"
    "  if (btn) btn.click();"
    "}"
)

GOTO_STATS_JS = (
    "() => {"
    "  const el = document.getElementById('tab-stats');"
    "  if (el) { el.click(); return; }"
    "  const btn = [...document.querySelectorAll('button')]"
    "    .find(b => b.textContent.includes('统计图表'));"
    "  if (btn) btn.click();"
    "}"
)

# P2-2 / B7：演示态字号放大，兼顾投影可读性（按钮 ≥44px、正文 ≥14.5px）
DEMO_STYLE_CSS = """
.gradio-container { font-size: 15px !important; }
.tab-nav button { font-size: 15px !important; }
.fa-toolbar .btn, .fa-jump-btn { min-height: 44px !important; }
.fa-metric-value { font-size: clamp(22px, 2vw, 26px) !important; }
.fa-dash-big { font-size: clamp(21px, 2vw, 27px) !important; }
.fa-amount { font-size: 30px !important; }
.fa-banner { font-size: 15px !important; }
.fa-chat .message { font-size: 14.5px !important; }
.fa-draft { padding: 20px !important; }
.fa-budget-item { padding: 15px 16px !important; margin-bottom: 12px; }
"""


def demo_style_on():
    return f"<style>{DEMO_STYLE_CSS}</style>"


def demo_style_off():
    return ""


def notify_demo_ready():
    gr.Info("演示数据已就绪，已切到「统计图表」页")


def notify_demo_reset():
    gr.Info("演示数据已清空，页面回到空态")


def dismiss_banner(items: list, dismissed: set):
    """关闭按钮：把当前活跃提醒全部标记已读（本会话内不再弹同一条）。"""
    dismissed = set(dismissed or ()) | {alerts.alert_key(item) for item in items or []}
    html = alerts.banner_html(items, dismissed, "")
    return html, dismissed, gr.update(visible=bool(html))


def check_health():
    """启动自检（P0-1）：后端未连接时顶部出灰色提示条 + 重试按钮，页面不白屏。

    验收口径：手动停掉后端 → 页面仍可交互、出友好提示；重启后无需刷新即可恢复。
    """
    try:
        api.health()
        return gr.update(visible=False), ""
    except api.ApiError:
        tip = c.tip(
            "后端未连接：页面仍可交互，演示类功能将使用本地演示数据。"
            "点右侧「重试连接」重新检测，无需刷新页面。",
            kind="warn",
        )
        return gr.update(visible=True), tip


def create_app() -> gr.Blocks:
    """构建 Gradio Blocks 应用（五区骨架 + 顶部提醒横幅）。"""
    with gr.Blocks(title=APP_TITLE, analytics_enabled=False) as demo:
        gr.HTML(c.header())

        # 顶部提醒横幅（P1-2）：分级红/橙，可关闭，事件驱动刷新 + Timer 兜底
        dismissed_state = gr.State(set())
        alerts_state = gr.State([])
        # P2-2：演示态样式注入点（<style> 由事件动态开/关）
        demo_style_area = gr.HTML("", elem_classes=["fa-demo-style"])

        with gr.Row(equal_height=True, visible=True):
            banner = gr.HTML("", elem_classes=["fa-banner-wrap"])
            quick_demo_btn = gr.Button(
                "🎬 一键演示", variant="primary", scale=0, size="sm",
                elem_classes=["fa-jump-btn"],
            )
            goto_budget_btn = gr.Button(
                "查看预算", variant="secondary", scale=0, size="sm",
                elem_classes=["fa-jump-btn"], visible=False,
            )
            dismiss_btn = gr.Button("✕", elem_classes=["fa-banner-close"], scale=0)

        # 后端健康提示条（P0-1）：默认隐藏，/health 失败时出现
        with gr.Row(equal_height=True, visible=False) as health_row:
            health_html = gr.HTML("")
            health_retry = gr.Button("重试连接", variant="secondary", scale=0, size="sm")

        # 仪表盘式首屏（P1-3 / B5）：左栏大数字 + 环形进度常驻，右侧 Tab 内容
        with gr.Row(equal_height=False):
            with gr.Column(scale=0, min_width=236, elem_classes=["fa-dash-col"]):
                dashboard = gr.HTML("", elem_classes=["fa-dash"])
            with gr.Column(scale=6, elem_classes=["fa-main-col"]):
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
        banner_outputs = [banner, alerts_state, goto_budget_btn]
        dash_outputs = [dashboard]
        demo.load(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        demo.load(refresh_dashboard, inputs=None, outputs=dash_outputs)

        # P0-1：启动自检 + 手动重试（后端重启后无需刷新即可恢复）
        demo.load(check_health, inputs=None, outputs=[health_row, health_html])
        health_retry.click(check_health, inputs=None, outputs=[health_row, health_html])
        budget_tab_item.select(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        budget_tab_item.select(refresh_dashboard, inputs=None, outputs=dash_outputs)
        chat_handles["confirm_event"].then(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        chat_handles["confirm_event"].then(refresh_dashboard, inputs=None, outputs=dash_outputs)
        chat_handles["ocr_confirm_event"].then(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        chat_handles["ocr_confirm_event"].then(refresh_dashboard, inputs=None, outputs=dash_outputs)
        demo_handles["load_event"].then(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        demo_handles["load_event"].then(refresh_dashboard, inputs=None, outputs=dash_outputs)
        demo_handles["reset_event"].then(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        demo_handles["reset_event"].then(refresh_dashboard, inputs=None, outputs=dash_outputs)

        # ---- P2-2 / A7 一键演示编排：灌数据 → 提示 + 切统计页（切页自动刷新图表）→ 演示态字号 ----
        style_outputs = [demo_style_area]

        def wire_demo_ready(event):
            event.then(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
            event.then(refresh_dashboard, inputs=None, outputs=dash_outputs)
            event.then(demo_style_on, inputs=None, outputs=style_outputs)
            event.then(notify_demo_ready, inputs=None, outputs=None)
            event.then(fn=None, inputs=None, outputs=None, js=GOTO_STATS_JS)

        def wire_demo_reset(event):
            event.then(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
            event.then(refresh_dashboard, inputs=None, outputs=dash_outputs)
            event.then(demo_style_off, inputs=None, outputs=style_outputs)
            event.then(notify_demo_reset, inputs=None, outputs=None)

        wire_demo_ready(demo_handles["load_event"])
        wire_demo_reset(demo_handles["reset_event"])

        # 顶部「一键演示」：与演示页按钮同一条编排链，不用翻到最后一个 Tab
        quick_demo_event = quick_demo_btn.click(
            demo_load, inputs=None, outputs=[demo_handles["result_area"]],
        )
        wire_demo_ready(quick_demo_event)
        timer = gr.Timer(60)
        timer.tick(refresh_banner, inputs=banner_inputs, outputs=banner_outputs)
        timer.tick(refresh_dashboard, inputs=None, outputs=dash_outputs)

        # P1-2 收尾：点「查看预算」跳到预算页（js 直点页签）
        goto_budget_btn.click(fn=None, inputs=None, outputs=None, js=GOTO_BUDGET_JS)

        # ---- 关闭横幅：按 category+status 指纹标记已读，本会话内不再弹同一条 ----
        dismiss_btn.click(
            dismiss_banner,
            inputs=[alerts_state, dismissed_state],
            outputs=[banner, dismissed_state, goto_budget_btn],
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
