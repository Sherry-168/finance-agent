"""记账小助手 · Gradio 前端入口。

布局对齐《记账小助手-UI优化方案-v2.md》v2.1：
左侧功能栏 / 顶部视图栏 / 中间对话区 / 右侧确认面板 / 底部提示条。

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
"""

import os
from concurrent.futures import ThreadPoolExecutor
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

# 左侧导航：(显示名, elem_id, 目标 tab id, 视图标题, 面包屑)
NAV_ITEMS = [
    ("💬 对话记账", "sidebar-chat", "tab-chat", "对话记账", "记账 / 对话记账"),
    ("📊 统计图表", "sidebar-stats", "tab-stats", "统计图表", "分析 / 统计图表"),
    ("💰 预算中心", "sidebar-budget", "tab-budget", "预算中心", "管理 / 预算中心"),
    ("📒 历史账目", "sidebar-records", "tab-records", "历史账目", "管理 / 历史账目"),
    ("🎬 演示入口", "sidebar-demo", "tab-demo", "演示入口", "管理 / 演示入口"),
]


_WIDGET_TIMEOUT = 3.0  # 辅助卡片统一超时，不能拖慢主流程


def _safe_load(future, fallback):
    """等待并发请求；返回 (数据, 完整原因, 状态)。

    状态："" 正常 / demo 演示数据 / error 真实接口失败。
    error 时不返回 Mock 数字，避免把演示数据当成真实账目展示。
    """
    try:
        return future.result(), "", ""
    except api.ApiError as exc:
        if api.should_fallback(exc):
            return fallback(), mock.NOTICE, "demo"
        return None, exc.message, "error"


def refresh_shell(dismissed):
    """首屏与定时刷新的唯一入口：一次并发拉取三块数据，只触发一次刷新。

    横幅、侧栏预算、今日概览共用同一批预算数据，避免重复请求和全局进度浮层。
    """
    month = date.today().strftime("%Y-%m")
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_budget = pool.submit(api.budget_alerts, month, timeout=_WIDGET_TIMEOUT)
        f_summary = pool.submit(api.stats_summary, month, timeout=_WIDGET_TIMEOUT)
        f_trend = pool.submit(api.stats_trend, 1, timeout=_WIDGET_TIMEOUT)
        budget, budget_msg, budget_kind = _safe_load(f_budget, lambda: mock.budget_alerts(month))
        summary, summary_msg, summary_kind = _safe_load(f_summary, lambda: mock.stats_summary(month))
        trend, trend_msg, trend_kind = _safe_load(f_trend, lambda: mock.stats_trend(1))

    kinds = {budget_kind, summary_kind, trend_kind}
    if "error" in kinds:
        # 接口在线但返回异常：宁可显示占位符，也不拿 Mock 数字冒充真实数据
        budget, summary, trend = {}, {}, {}
        notice, notice_kind = "数据更新失败 · 自动重试", "error"
        notice_tip = next((m for m in (budget_msg, summary_msg, trend_msg) if m), "服务暂时不可用")
    elif "demo" in kinds:
        notice, notice_kind, notice_tip = "演示数据 · 未连接后端", "demo", mock.NOTICE
    else:
        notice, notice_kind, notice_tip = "", "", ""

    items = (budget or {}).get("items") or []
    total = next((i for i in items if not i.get("category")), None)
    trend_items = (trend or {}).get("items") or []
    if trend_items:
        day = trend_items[-1]
    elif notice_kind == "error":
        day = {"date": date.today().isoformat(), "total": None, "count": None, "income": None}
    else:
        day = {"date": date.today().isoformat(), "total": 0, "count": 0, "income": 0}

    banner_notice = ""
    if notice_kind == "demo":
        banner_notice = mock.NOTICE
    elif notice_kind == "error":
        banner_notice = "预警数据加载失败，稍后自动重试"

    banner = alerts.banner_html(items, dismissed, banner_notice)
    visible = bool(banner)
    return (
        banner,
        items,
        gr.update(visible=visible),  # 💰 查看预算
        gr.update(visible=visible),  # ✕ 关闭横幅
        c.sidebar_budget(summary, total, notice, notice_kind, notice_tip),
        c.today_overview(day, total, notice, notice_kind, notice_tip),
    )


GOTO_BUDGET_JS = (
    "() => {"
    "  const el = document.getElementById('sidebar-budget');"
    "  if (el) { (el.querySelector('button') || el).click(); }"
    "}"
)

GOTO_STATS_JS = (
    "() => {"
    "  const el = document.getElementById('sidebar-stats');"
    "  if (el) { (el.querySelector('button') || el).click(); }"
    "}"
)

# P2-2 / B7：演示态字号放大，兼顾投影可读性（按钮 ≥44px、正文 ≥14.5px）
DEMO_STYLE_CSS = """
.gradio-container { font-size: 15px !important; }
.fa-sidebar button { font-size: 15px !important; }
.fa-toolbar .btn, .fa-jump-btn { min-height: 44px !important; }
.fa-side-budget-top b { font-size: 19px !important; }
.fa-amount { font-size: 30px !important; }
.fa-banner { font-size: 15px !important; }
.fa-chat .message { font-size: 14.5px !important; }
.fa-draft { padding: 20px !important; }
.fa-budget-item { padding: 15px 16px !important; margin-bottom: 12px !important; }
"""


def demo_style_on():
    return f"<style>{DEMO_STYLE_CSS}</style>"


def demo_style_off():
    return ""


def notify_demo_ready():
    gr.Info("演示数据已就绪，已切到「统计图表」页")


def notify_demo_reset():
    gr.Info("演示数据已清空，页面回到空态")


def dismiss_banner(items: list, dismissed):
    """关闭按钮：把当前活跃提醒全部标记已读，写入 BrowserState 持久化。

    BrowserState 只存 JSON 可序列化数据，故用 list 而非 set 承载已读指纹。
    """
    keys = set(dismissed or ()) | {alerts.alert_key(item) for item in items or []}
    html = alerts.banner_html(items, keys, "")
    visible = bool(html)
    return html, sorted(keys), gr.update(visible=visible), gr.update(visible=visible)


def check_health():
    """启动自检：后端未连接时顶部出灰色提示条 + 重试按钮，页面不白屏。"""
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
    """构建 Gradio Blocks 应用（v2.1 三段式布局）。"""
    with gr.Blocks(title=APP_TITLE, analytics_enabled=False) as demo:
        demo_style_area = gr.HTML("", elem_classes=["fa-demo-style"])

        with gr.Row(equal_height=False, elem_classes=["fa-app-shell"]):
            # ---------------------------------------------------------- 左侧功能栏
            with gr.Column(scale=0, min_width=232, elem_classes=["fa-sidebar"]):
                gr.HTML(
                    '<div class="fa-sidebar-brand">'
                    '<div class="fa-sidebar-logo">记</div>'
                    '<div><div class="fa-sidebar-title">记账小助手</div>'
                    '<div class="fa-sidebar-sub">一句话，搞定记账</div></div>'
                    "</div>"
                )
                side_budget = gr.HTML(c.sidebar_budget_skeleton(), elem_classes=["fa-side-budget-slot"])

                gr.HTML('<div class="fa-nav-group">记账</div>')
                nav_chat = gr.Button(NAV_ITEMS[0][0], variant="primary", elem_id=NAV_ITEMS[0][1], elem_classes=["fa-sidebar-btn"])

                gr.HTML('<div class="fa-nav-group">分析</div>')
                nav_stats = gr.Button(NAV_ITEMS[1][0], variant="secondary", elem_id=NAV_ITEMS[1][1], elem_classes=["fa-sidebar-btn"])

                gr.HTML('<div class="fa-nav-group">管理</div>')
                nav_budget = gr.Button(NAV_ITEMS[2][0], variant="secondary", elem_id=NAV_ITEMS[2][1], elem_classes=["fa-sidebar-btn fa-nav-badge"])
                nav_records = gr.Button(NAV_ITEMS[3][0], variant="secondary", elem_id=NAV_ITEMS[3][1], elem_classes=["fa-sidebar-btn"])
                nav_demo = gr.Button(NAV_ITEMS[4][0], variant="secondary", elem_id=NAV_ITEMS[4][1], elem_classes=["fa-sidebar-btn"])

                gr.HTML(
                    '<div class="fa-side-account">'
                    '<div class="fa-account-avatar">A</div>'
                    '<div><div class="fa-account-name">我的账户</div>'
                    '<div class="fa-account-sub">管理员 · 演示</div></div>'
                    "</div>"
                )

            # ---------------------------------------------------------- 右侧内容区
            with gr.Column(scale=1, min_width=0, elem_classes=["fa-content-col"]):
                # 顶部提醒横幅与后端健康提示
                # B4/P1-2：BrowserState 存 localStorage，关闭后刷新页面不再重弹
                dismissed_state = gr.BrowserState([])
                alerts_state = gr.State([])
                with gr.Row(equal_height=True, visible=True):
                    banner = gr.HTML("", elem_classes=["fa-banner-wrap"])
                    quick_demo_btn = gr.Button(
                        "🎬 一键演示", variant="secondary", scale=0, size="sm",
                        elem_classes=["fa-jump-btn"],
                    )
                    goto_budget_btn = gr.Button(
                        "💰 查看预算", variant="secondary", scale=0, size="sm",
                        elem_classes=["fa-jump-btn"], visible=False,
                    )
                    dismiss_btn = gr.Button("✕", elem_classes=["fa-banner-close"], scale=0, visible=False)

                with gr.Row(equal_height=True, visible=False) as health_row:
                    health_html = gr.HTML("")
                    health_retry = gr.Button("🔄 重试连接", variant="secondary", scale=0, size="sm")

                with gr.Tabs(elem_classes=["fa-main-tabs"]) as tabs:
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

                with gr.Row(visible=True, elem_classes=["fa-bottom-tip"]) as bottom_tip:
                    gr.HTML(
                        c.tip(
                            '支持的例子：<b class="fa-tip-key">「午饭18」</b>'
                            '<b class="fa-tip-key">「打车32块」</b>'
                            '<b class="fa-tip-key">「菜50」</b>'
                            '<b class="fa-tip-key">「存钱500」</b>。'
                            "也支持「花」「收入」「存」等动词；问句可直接查账。"
                        )
                    )
                    tip_close_btn = gr.Button("✕", elem_classes=["fa-tip-close"], scale=0)

        # ---------------------------------------------------------- 视图切换
        nav_buttons = [nav_chat, nav_stats, nav_budget, nav_records, nav_demo]

        def select_view(tab_id: str, nav_index: int = -1):
            active_nav = nav_index if nav_index >= 0 else next(
                (i for i, item in enumerate(NAV_ITEMS) if item[2] == tab_id), -1
            )
            return [
                gr.update(selected=tab_id),
                *[
                    gr.update(variant="primary" if i == active_nav else "secondary")
                    for i in range(len(nav_buttons))
                ],
            ]

        view_outputs = [tabs, *nav_buttons]
        for index, (_, _, tab_id, _, _) in enumerate(NAV_ITEMS):
            nav_buttons[index].click(
                lambda t=tab_id, i=index: select_view(t, i),
                inputs=None,
                outputs=view_outputs,
            )

        goto_budget_btn.click(fn=None, inputs=None, outputs=None, js=GOTO_BUDGET_JS)
        tip_close_btn.click(lambda: gr.update(visible=False), inputs=None, outputs=[bottom_tip])

        # ---------------------------------------------------------- 页签自动加载
        records_tab_item.select(
            records_handles["initial_load"],
            inputs=None,
            outputs=records_handles["list_outputs"],
        )
        stats_tab_item.select(
            stats_handles["initial_load"],
            inputs=None,
            outputs=stats_handles["stats_outputs"],
        )
        budget_tab_item.select(
            budget_handles["initial_load"],
            inputs=None,
            outputs=budget_handles["initial_outputs"],
        )

        # ---------------------------------------------------------- 数据刷新
        banner_inputs = [dismissed_state]
        shell_outputs = [
            banner,
            alerts_state,
            goto_budget_btn,
            dismiss_btn,
            side_budget,
            chat_handles["today_overview"],
        ]

        # 首屏只发一个合并请求，且不展示全局进度条（P0-1）
        demo.load(refresh_shell, inputs=banner_inputs, outputs=shell_outputs, show_progress="hidden")
        demo.load(check_health, inputs=None, outputs=[health_row, health_html], show_progress="hidden")
        health_retry.click(check_health, inputs=None, outputs=[health_row, health_html], show_progress="hidden")

        budget_tab_item.select(refresh_shell, inputs=banner_inputs, outputs=shell_outputs, show_progress="hidden")
        for event in (
            chat_handles["confirm_event"],
            chat_handles["ocr_confirm_event"],
            budget_handles["save_event"],
            budget_handles["refresh_event"],
        ):
            event.then(refresh_shell, inputs=banner_inputs, outputs=shell_outputs, show_progress="hidden")

        # ---------------------------------------------------------- 一键演示编排
        style_outputs = [demo_style_area]

        def wire_demo_ready(event):
            event.then(refresh_shell, inputs=banner_inputs, outputs=shell_outputs, show_progress="hidden")
            event.then(demo_style_on, inputs=None, outputs=style_outputs)
            event.then(notify_demo_ready, inputs=None, outputs=None)
            event.then(fn=None, inputs=None, outputs=None, js=GOTO_STATS_JS)

        def wire_demo_reset(event):
            event.then(refresh_shell, inputs=banner_inputs, outputs=shell_outputs, show_progress="hidden")
            event.then(demo_style_off, inputs=None, outputs=style_outputs)
            event.then(notify_demo_reset, inputs=None, outputs=None)

        wire_demo_ready(demo_handles["load_event"])
        wire_demo_reset(demo_handles["reset_event"])

        quick_demo_event = quick_demo_btn.click(
            demo_load, inputs=None, outputs=[demo_handles["result_area"]],
        )
        wire_demo_ready(quick_demo_event)

        timer = gr.Timer(60)
        timer.tick(refresh_shell, inputs=banner_inputs, outputs=shell_outputs, show_progress="hidden")

        # ---------------------------------------------------------- 关闭横幅
        dismiss_btn.click(
            dismiss_banner,
            inputs=[alerts_state, dismissed_state],
            outputs=[banner, dismissed_state, goto_budget_btn, dismiss_btn],
        )

    return demo


def launch() -> None:
    """启动前端服务（Gradio 6 起 theme / css 需在 launch 时传入）。"""
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
