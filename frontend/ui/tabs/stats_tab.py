"""Tab3 统计图表：月度指标卡 + 类别饼图 + 每日趋势折线。

Day 5 契约（docs/api.md §5，仅统计 confirmed=1）：
- GET /stats/summary?month=      → 指标卡（总额 / 笔数 / 日均，后端计算）
- GET /stats/by-category?month=  → ECharts 环形饼图
- GET /stats/trend?days=         → ECharts 折线面积图
前端只渲染聚合结果，不做任何统计计算（注意事项 3）。
"""

import re
from datetime import date

import gradio as gr

import api
import mock
from config import MOCK_FALLBACK  # noqa: F401  （保留给 demo_tab 提示等场景参考）
from ui import components as c

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
    """刷新三块统计内容；返回 (metrics_html, pie_html, trend_html)。"""
    month = (month or "").strip()
    days = int(days) if days else 30
    if not _MONTH_RE.match(month):
        return (
            c.tip("月份格式应为 YYYY-MM，例如 2026-11。", kind="error"),
            c.chart_placeholder("fa-pie-chart", "类别占比", "修正月份后刷新"),
            c.chart_placeholder("fa-trend-chart", "每日趋势", "修正月份后刷新"),
        )

    summary, notice_1 = _fetch_summary(month)
    by_cat, _notice_2 = _fetch_by_category(month)
    trend, _notice_3 = _fetch_trend(days)
    notice = notice_1 or ""
    if summary is None:
        metrics = c.tip(f"统计获取失败：{notice_1}", kind="error")
        return metrics, c.chart_placeholder("fa-pie-chart", "类别占比", "后端就绪后自动展示"), c.chart_placeholder("fa-trend-chart", "每日趋势", "后端就绪后自动展示")

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
    pie = (
        c.chart_iframe(c.pie_spec(cat_items, notice))
        if cat_items
        else c.empty_state("本月暂无分类数据", "先记几笔，或切换到其他月份。")
    )

    trend_items = (trend or {}).get("items") or []
    trend = (
        c.chart_iframe(c.trend_spec(trend_items, notice), height=300)
        if trend_items
        else c.empty_state("暂无趋势数据", "趋势取近 N 天已确认记录。")
    )
    return metrics, pie, trend


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
            gr.HTML(c.section_head("类别占比", "GET /stats/by-category"))
            pie_chart = gr.HTML(
                c.chart_placeholder("fa-pie-chart", "ECharts 饼图", "点击「刷新统计」或切到本页自动加载")
            )
        with gr.Column(scale=1):
            gr.HTML(c.section_head("每日趋势", "GET /stats/trend?days="))
            trend_chart = gr.HTML(
                c.chart_placeholder("fa-trend-chart", "ECharts 折线图", "点击「刷新统计」或切到本页自动加载")
            )

    gr.HTML(
        c.tip(
            "图表数据完全来自后端聚合结果，前端只做渲染；离线环境（无法加载 ECharts CDN）"
            "自动降级为简化条形视图，数值不变。查账回答也只展示后端返回的 answer_text 与 table。"
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
