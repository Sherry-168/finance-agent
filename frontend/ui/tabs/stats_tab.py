"""Tab3 统计图表：月度指标卡 + 类别饼图 + 每日趋势折线。

第二周口径（week2-plan P0-5）：图表库统一 **Plotly + gr.Plot**（开工对齐第①项），
替换第一周的 ECharts iframe（ECharts 方案仍保留在 ui/charts.py 尾部作降级参考）。

契约（docs/api.md §5，仅统计 confirmed=1）：
- GET /stats/summary?month=      → 指标卡（总额 / 笔数 / 日均，后端计算）
- GET /stats/by-category?month=  → 环形饼图（占比 <3% 合并为「其他」）
- GET /stats/trend?days=         → 折线图（hover：日期 · ¥金额 · N 笔）
前端只渲染聚合结果，不做任何统计计算（注意事项 3）。
"""

import re
from datetime import date

import gradio as gr

import api
import mock
from config import MOCK_FALLBACK
from ui import cards as c
from ui import charts

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _fetch_summary(month: str):
    try:
        return api.stats_summary(month), ""
    except api.ApiError as exc:
        if api.should_fallback(exc):
            return mock.stats_summary(month), mock.NOTICE
        return None, exc.message


def _fetch_by_category(month: str):
    try:
        return api.stats_by_category(month=month), ""
    except api.ApiError as exc:
        if api.should_fallback(exc):
            return mock.stats_by_category(month=month), mock.NOTICE
        return None, exc.message


def _fetch_trend(days: int):
    try:
        return api.stats_trend(days=days), ""
    except api.ApiError as exc:
        if api.should_fallback(exc):
            return mock.stats_trend(days=days), mock.NOTICE
        return None, exc.message


def load_stats(month: str, days):
    """刷新三块统计内容；返回 (metrics_html, pie_fig, trend_fig)。"""
    month = (month or "").strip()
    days = int(days) if days else 30
    invalid = charts.empty_figure("月份格式应为 YYYY-MM（例如 2026-11），修正后刷新")
    if not _MONTH_RE.match(month):
        return (
            c.tip("月份格式应为 YYYY-MM，例如 2026-11。", kind="error"),
            invalid,
            invalid,
        )

    summary, notice_1 = _fetch_summary(month)
    by_cat, _notice_2 = _fetch_by_category(month)
    trend, _notice_3 = _fetch_trend(days)
    notice = notice_1 or ""

    if summary is None:
        err = charts.empty_figure("统计获取失败，请检查后端后点击「刷新统计」")
        return c.tip(f"统计获取失败：{notice_1}", kind="error"), err, err

    metrics = c.metric_cards(
        [
            (f"{month} 支出总额", c.format_yuan(summary.get("total")), "GET /stats/summary · 仅已确认记录"),
            ("笔数", f"{summary.get('count', 0)} 笔", "confirmed=1 口径"),
            ("日均支出", c.format_yuan(summary.get("daily_avg")), "总额 ÷ 当月已过天数（后端计算）"),
        ]
    )
    if notice:
        metrics += c.tip(notice, kind="warn")

    cat_items = (by_cat or {}).get("items") or []
    pie = charts.pie_figure(cat_items) if cat_items else charts.empty_figure("本月暂无分类数据，先去记几笔")

    trend_items = (trend or {}).get("items") or []
    trend_fig = charts.trend_figure(trend_items) if trend_items else charts.empty_figure("暂无趋势数据")

    return metrics, pie, trend_fig


def build_stats_tab() -> dict:
    today = date.today().strftime("%Y-%m")
    with gr.Row(elem_classes=["fa-toolbar"]):
        month_input = gr.Textbox(label="统计月份", value=today, placeholder="2026-11", scale=2)
        days_input = gr.Dropdown(label="趋势天数", choices=[7, 14, 30], value=30, scale=1)
        refresh_btn = gr.Button("刷新统计", variant="primary", scale=1)

    metrics = gr.HTML(
        c.metric_cards(
            [
                (f"{today} 支出总额", "¥ --", "GET /stats/summary"),
                ("本月笔数", "-- 笔", "仅统计已确认记录"),
                ("日均支出", "¥ --", "总额 ÷ 当月已过天数"),
            ]
        )
    )

    with gr.Row(equal_height=True):
        with gr.Column(scale=1):
            gr.HTML(c.section_head("类别占比", "GET /stats/by-category · Plotly"))
            pie_chart = gr.Plot(
                value=charts.empty_figure("点击「刷新统计」或切到本页自动加载"),
                elem_id="chart-pie",
            )
            gr.HTML('<p class="fa-sr-only" id="chart-pie-desc">类别占比饼图，展示本月各消费类别的支出比例。</p>')
        with gr.Column(scale=1):
            gr.HTML(c.section_head("每日趋势", "GET /stats/trend?days= · Plotly"))
            trend_chart = gr.Plot(
                value=charts.empty_figure("点击「刷新统计」或切到本页自动加载"),
                elem_id="chart-trend",
            )
            gr.HTML('<p class="fa-sr-only" id="chart-trend-desc">每日趋势折线图，展示近期每日支出金额与笔数。</p>')

    gr.HTML(
        c.tip(
            "图表数据完全来自后端聚合结果，前端只做渲染（Plotly + gr.Plot）；"
            "查账回答也只展示后端返回的 answer_text 与 table。"
        )
    )

    stats_outputs = [metrics, pie_chart, trend_chart]
    stats_inputs = [month_input, days_input]
    refresh_btn.click(load_stats, inputs=stats_inputs, outputs=stats_outputs)

    def initial_load():
        return load_stats(today, 30)

    return {
        "month_input": month_input,
        "days_input": days_input,
        "refresh_btn": refresh_btn,
        "metrics": metrics,
        "pie_chart": pie_chart,
        "trend_chart": trend_chart,
        "initial_load": initial_load,
        "stats_outputs": stats_outputs,
    }
