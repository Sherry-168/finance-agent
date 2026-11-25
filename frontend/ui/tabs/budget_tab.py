"""Tab4 预算中心：月度预算设定（类别 / 总额双维度）+ 三态进度预警。

Day 6 契约（docs/api.md §6，仅统计 confirmed=1）：
- POST /budgets {month, category|null, amount}   同月同维度覆盖
- GET /budgets/alerts?month= → [{category, amount, used, used_ratio, status}]
- GET /categories → 8 类枚举（下拉框选项）
前端只按后端 used_ratio / status 渲染颜色与文案，不做任何计算（注意事项 3）。
"""

import re
from datetime import date

import gradio as gr

import api
import mock
from config import CATEGORIES, TOTAL_BUDGET_LABEL
from ui import cards as c

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _save_budget(month: str, category: str, amount):
    """保存预算；返回 (status_html, progress_html)。"""
    category_arg = None if category in (None, "", TOTAL_BUDGET_LABEL) else category
    if amount is None or float(amount) <= 0:
        return c.tip("预算金额必须大于 0。", kind="error"), None
    payload_month = (month or "").strip()
    if not _MONTH_RE.match(payload_month):
        return c.tip("月份格式应为 YYYY-MM，例如 2026-11。", kind="error"), None

    notice = ""
    try:
        result = api.save_budget(payload_month, category_arg, float(amount))
    except api.ApiError as exc:
        if api.should_fallback(exc):
            result = mock.save_budget(payload_month, category_arg, float(amount))
            notice = mock.NOTICE
        else:
            return c.tip(f"预算保存失败：{exc.message}", kind="error"), None

    label = category_arg or TOTAL_BUDGET_LABEL
    status = c.tip(
        f"{payload_month} 的「{label}」预算已保存为 {c.format_yuan(result.get('amount'))}。"
        f"{f'<br>{notice}' if notice else ''}",
        kind="ok",
    )
    return status, result.get("month") or payload_month


def load_alerts(month: str):
    """加载预警进度卡；返回 (progress_html,)。"""
    month = (month or "").strip()
    if not _MONTH_RE.match(month):
        return (c.tip("月份格式应为 YYYY-MM，例如 2026-11。", kind="error"),)

    try:
        data = api.budget_alerts(month)
        notice = ""
    except api.ApiError as exc:
        if api.should_fallback(exc):
            data = mock.budget_alerts(month)
            notice = mock.NOTICE
        else:
            return (c.tip(f"预算预警获取失败：{exc.message}", kind="error"),)

    items = (data or {}).get("items") or []
    return (c.budget_progress(items, notice),)


def load_budgets(month: str):
    """GET /budgets：展示当月已设预算清单。"""
    month = (month or "").strip()
    if not _MONTH_RE.match(month):
        return (c.tip("月份格式应为 YYYY-MM，例如 2026-11。", kind="error"),)
    try:
        data = api.list_budgets(month)
        notice = ""
    except api.ApiError as exc:
        if api.should_fallback(exc):
            data = mock.list_budgets(month)
            notice = mock.NOTICE
        else:
            return (c.tip(f"预算列表获取失败：{exc.message}", kind="error"),)
    return (c.budget_list((data or {}).get("items") or [], notice),)


def load_budget_data(month: str):
    """刷新进度 + 已设预算列表。"""
    return load_alerts(month)[0], load_budgets(month)[0]


def save_and_refresh(month, category, amount):
    """保存成功后立即刷新进度卡与预算清单。"""
    status, refresh_month = _save_budget(month, category, amount)
    target_month = refresh_month or month
    progress, listing = load_budget_data(target_month)
    return status, progress, listing


def _category_choices() -> list[str]:
    """GET /categories：优先取后端枚举；未连通时用本地 8 类兜底。"""
    try:
        cats = api.list_categories()
        return cats if cats else list(CATEGORIES)
    except api.ApiError:
        return list(CATEGORIES)


def build_budget_tab() -> dict:
    today = date.today().strftime("%Y-%m")
    categories = _category_choices()
    with gr.Row(equal_height=False):
        with gr.Column(scale=2, elem_classes=["fa-panel"]):
            gr.HTML(c.section_head("设定月度预算", "类别预算与总额预算双维度"))
            month_input = gr.Textbox(label="月份", value=today, placeholder="2026-11")
            category_input = gr.Dropdown(
                label="预算维度",
                choices=[TOTAL_BUDGET_LABEL] + categories,
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
            progress_area = gr.HTML(c.empty_state(
                "尚未加载预警", "切到本页或点「加载预警」自动刷新。",
                action=("💬 先去记一笔", "sidebar-chat"),
            ))
            budget_list_area = gr.HTML(c.budget_list([]))

    status_area = gr.HTML(
        c.empty_state("预算状态", "保存预算后在此显示结果；右侧进度与清单随保存自动刷新。")
    )

    stats_outputs = [status_area, progress_area, budget_list_area]
    save_event = save_btn.click(
        save_and_refresh,
        inputs=[month_input, category_input, amount_input],
        outputs=stats_outputs,
    )
    refresh_event = refresh_btn.click(
        load_budget_data, inputs=[month_input], outputs=[progress_area, budget_list_area]
    )

    def initial_load():
        return load_budget_data(today)

    return {
        "month_input": month_input,
        "category_input": category_input,
        "amount_input": amount_input,
        "save_btn": save_btn,
        "save_event": save_event,
        "refresh_btn": refresh_btn,
        "refresh_event": refresh_event,
        "progress_area": progress_area,
        "budget_list_area": budget_list_area,
        "status_area": status_area,
        "initial_load": initial_load,
        "initial_outputs": [progress_area, budget_list_area],
    }
