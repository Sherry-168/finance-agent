"""Tab2 明细管理：筛选 + 分页表格 + 点行载入编辑 + 二次确认删除。

Day 4 契约（docs/api.md §2.4）：
- GET /records?start=&end=&category=&page=&size=
- PUT /records/{id}（amount/category/merchant/occurred_at/note）
- DELETE /records/{id}，不可逆，必须勾选确认框
前端只渲染后端分页结果，金额展示统一 format_yuan（分→元转换在后端完成）。
"""

import re

import gradio as gr

import api
import mock
from config import (
    CATEGORIES,
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    PAGE_SIZE_CHOICES,
)
from ui import cards as c

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SOURCE_LABELS = {"text": "对话", "ocr": "小票", "manual": "手动"}
_ALL = "全部"


def _fmt_amount(value) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return "--"


def _rows(items: list) -> list:
    rows = []
    for item in items:
        source = item.get("source")
        rows.append(
            [
                str(item.get("id") or "--"),
                item.get("occurred_at") or "--",
                _fmt_amount(item.get("amount")),
                item.get("category") or "--",
                item.get("merchant") or "—",
                item.get("note") or "—",
                _SOURCE_LABELS.get(source, source or "—"),
                "已确认" if item.get("confirmed") in (1, True, "1") else "草稿",
            ]
        )
    return rows


def _fetch(start, end, category, page: int, size: int):
    """请求明细分页；网络失败且 MOCK_FALLBACK 开启时降级本地数据。"""
    category_arg = None if category in (None, "", _ALL) else category
    kwargs = dict(start=start or None, end=end or None, category=category_arg, page=page, size=size)
    try:
        return api.list_records(**kwargs), ""
    except api.ApiError as exc:
        if api.should_fallback(exc):
            return mock.list_records(**kwargs), mock.NOTICE
        return None, exc.message


def _page_info_html(result: dict | None, notice: str) -> str:
    if result is None:
        return '<div class="fa-section-desc">第 - 页 · 共 - 条</div>'
    text = f"第 {result.get('page')} / {result.get('pages')} 页 · 共 {result.get('total')} 条"
    if notice:
        text += f"　<i style='opacity:0.75'>({notice})</i>"
    return f'<div class="fa-section-desc">{text}</div>'


def _query(start, end, category, size: int, page: int):
    """统一查询入口：返回 (rows, page_info, status, page, items)。"""
    start = (start or "").strip()
    end = (end or "").strip()
    if start and not _DATE_RE.match(start) or end and not _DATE_RE.match(end):
        return [], _page_info_html(None, ""), c.tip("日期格式应为 YYYY-MM-DD，例如 2026-11-01。", kind="error"), page, []

    result, notice = _fetch(start, end, category, page, size)
    if result is None:
        return [], _page_info_html(None, ""), c.tip(f"查询失败：{notice}", kind="error"), page, []

    items = result.get("items") or []
    rows = _rows(items)
    status = c.tip(f"已加载 {len(items)} / {result.get('total')} 条明细。", kind="ok") if notice else c.empty_state(
        "本页已加载",
        "点击表格任意一行可载入下方编辑区进行修正或删除。",
    ) if items else c.empty_state("暂无数据", "换个筛选条件，或先在「记账对话」里记几笔。")
    return rows, _page_info_html(result, notice), status, int(result.get("page") or page), items


def search_records(start, end, category, size: int, _page: int):
    """查询按钮：回到第 1 页。"""
    return _query(start, end, category, int(size), DEFAULT_PAGE)


def prev_page(start, end, category, size: int, page: int):
    return _query(start, end, category, int(size), max(DEFAULT_PAGE, int(page or 1) - 1))


def next_page(start, end, category, size: int, page: int):
    # 越界页码由后端/ Mock 自动夹取合法页，无需前端判断
    return _query(start, end, category, int(size), int(page or 1) + 1)


def reset_filters():
    """重置筛选并重新加载。"""
    return (*_query("", "", _ALL, DEFAULT_PAGE_SIZE, DEFAULT_PAGE), "", "", _ALL, DEFAULT_PAGE_SIZE)


def load_row(evt: gr.SelectData, items: list):
    """点击表格行 → 载入编辑区（等价于「修改」入口）。"""
    index = evt.index
    row = index[0] if isinstance(index, (list, tuple)) else index
    if not isinstance(row, int) or not (0 <= row < len(items)):
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), c.tip("请先查询出明细后，再点击行载入。")
    item = items[row]
    tip = c.tip(f"已载入记录 id {item.get('id')}，可修改后保存，或勾选确认后删除。")
    return (
        item.get("id"),
        item.get("amount"),
        item.get("category"),
        item.get("merchant") or "",
        item.get("occurred_at") or "",
        item.get("note") or "",
        tip,
    )


def _refresh_same_page(start, end, category, size: int, page: int):
    """增删改成功后刷新当前页。"""
    return _query(start, end, category, int(size), int(page or 1))


def _as_int(value) -> int | None:
    """record_id 兜底转换：组件可能传来 dict（gr.update）/ 空串等非法值。"""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def save_record(record_id, amount, category, merchant, occurred_at, note, start, end, category_filter, size, page):
    """PUT /records/{id}：前端只做格式校验，金额口径以后端为准。"""
    current = _refresh_same_page(start, end, category_filter, size, page)
    record_id = _as_int(record_id)
    if record_id is None:
        return (c.tip("请先点击表格某一行载入要修改的记录。", kind="warn"), *current)
    if amount is None or float(amount) <= 0:
        return (c.tip("金额必须大于 0。", kind="error"), *current)
    occurred_at = (occurred_at or "").strip()
    if occurred_at and not _DATE_RE.match(occurred_at):
        return (c.tip("消费时间格式应为 YYYY-MM-DD，留空表示不修改。", kind="error"), *current)

    payload = {
        "amount": float(amount),
        "category": category,
        "merchant": (merchant or "").strip() or None,
        "occurred_at": occurred_at or None,
        "note": (note or "").strip() or None,
    }
    notice = ""
    try:
        api.update_record(int(record_id), payload)
    except api.ApiError as exc:
        if api.should_fallback(exc):
            mock.update_record(int(record_id), payload)
            notice = mock.NOTICE
        else:
            return (c.tip(f"修改失败：{exc.message}", kind="error"), *current)

    return (
        c.tip(f"记录 id {int(record_id)} 已保存修改。{f'<br>{notice}' if notice else ''}", kind="ok"),
        *_refresh_same_page(start, end, category_filter, size, page),
    )


def remove_record(record_id, confirm_delete, start, end, category_filter, size, page):
    """DELETE /records/{id}：必须勾选确认框（注意事项：不可逆）。"""
    current = _refresh_same_page(start, end, category_filter, size, page)
    record_id = _as_int(record_id)
    if record_id is None:
        return (c.tip("请先点击表格某一行载入要删除的记录。", kind="warn"), False, *current)
    if not confirm_delete:
        return (c.tip("删除不可恢复：请先勾选「我确认删除该记录」。", kind="warn"), False, *current)

    notice = ""
    try:
        api.delete_record(int(record_id))
    except api.ApiError as exc:
        if api.should_fallback(exc):
            mock.delete_record(int(record_id))
            notice = mock.NOTICE
        else:
            return (c.tip(f"删除失败：{exc.message}", kind="error"), False, *current)

    return (
        c.tip(f"记录 id {int(record_id)} 已删除。{f'<br>{notice}' if notice else ''}", kind="ok"),
        False,
        *_refresh_same_page(start, end, category_filter, size, page),
    )


def build_records_tab() -> dict:
    gr.HTML(c.section_head("消费明细", "按时间与类别筛选，支持修正与删除"))

    with gr.Row(elem_classes=["fa-toolbar"]):
        start_input = gr.Textbox(label="开始日期", placeholder="2026-11-01", scale=2)
        end_input = gr.Textbox(label="结束日期", placeholder="2026-11-30", scale=2)
        category_input = gr.Dropdown(label="类别", choices=[_ALL] + CATEGORIES, value=_ALL, scale=2)
        page_size_input = gr.Dropdown(label="每页", choices=PAGE_SIZE_CHOICES, value=DEFAULT_PAGE_SIZE, scale=1)
        search_btn = gr.Button("查询", variant="primary", scale=1)
        reset_btn = gr.Button("重置", variant="secondary", scale=1)

    table = gr.Dataframe(
        headers=["ID", "消费时间", "金额 (¥)", "类别", "商户", "备注", "来源", "状态"],
        datatype=["str"] * 8,
        value=[],
        interactive=False,
        wrap=True,
        row_count=(0, "dynamic"),
        elem_classes=["fa-table"],
    )

    page_state = gr.State(DEFAULT_PAGE)
    last_items = gr.State([])

    with gr.Row(elem_classes=["fa-toolbar"]):
        prev_btn = gr.Button("上一页", variant="secondary", scale=1)
        page_info = gr.HTML(_page_info_html(None, ""))
        next_btn = gr.Button("下一页", variant="secondary", scale=1)

    status_area = gr.HTML(
        c.empty_state("暂无数据", "点击「查询」加载明细；后端未启动时展示本地演示数据。")
    )

    # P0-4 空态跳转：gr.HTML 内按钮无法绑事件，用真实 Button + js 直点页签
    jump_chat_btn = gr.Button(
        "💬 去对话页记一笔",
        variant="secondary",
        size="sm",
        elem_classes=["fa-jump-btn"],
    )
    jump_chat_btn.click(
        fn=None,
        inputs=None,
        outputs=None,
        js=(
            "() => {"
            "  const el = document.getElementById('tab-chat');"
            "  if (el) { el.click(); return; }"
            "  const btn = [...document.querySelectorAll('button')]"
            "    .find(b => b.textContent.includes('记账对话'));"
            "  if (btn) btn.click();"
            "}"
        ),
    )

    with gr.Accordion("修改 / 删除记录（点击表格行自动载入）", open=False):
        gr.HTML(
            c.tip(
                "金额统一记正数支出，展示为 ¥；草稿（confirmed=0）与已确认记录在「状态」列区分。"
                "删除为不可逆操作，必须先勾选确认框。"
            )
        )
        with gr.Row(elem_classes=["fa-toolbar"]):
            record_id_input = gr.Number(label="记录 ID", precision=0, scale=1, minimum=1, interactive=False)
            amount_input = gr.Number(label="金额 (¥)", precision=2, minimum=0, scale=2)
            category_edit = gr.Dropdown(label="类别", choices=CATEGORIES, scale=2)
            occurred_edit = gr.Textbox(label="消费时间（YYYY-MM-DD）", placeholder="2026-11-16", scale=2)
        with gr.Row(elem_classes=["fa-toolbar"]):
            merchant_input = gr.Textbox(label="商户", scale=2)
            note_input = gr.Textbox(label="备注", scale=3)
        with gr.Row(elem_classes=["fa-toolbar"]):
            update_btn = gr.Button("保存修改", variant="primary", scale=1)
            confirm_delete = gr.Checkbox(label="我确认删除该记录（不可恢复）", value=False, scale=2)
            delete_btn = gr.Button("删除记录", variant="stop", scale=1)

    # ---------------- 事件绑定 ----------------
    list_outputs = [table, page_info, status_area, page_state, last_items]
    list_inputs = [start_input, end_input, category_input, page_size_input, page_state, last_items]

    search_btn.click(
        search_records,
        inputs=[start_input, end_input, category_input, page_size_input, page_state],
        outputs=list_outputs,
    )
    page_inputs = [start_input, end_input, category_input, page_size_input, page_state]
    prev_btn.click(prev_page, inputs=page_inputs, outputs=list_outputs)
    next_btn.click(next_page, inputs=page_inputs, outputs=list_outputs)
    reset_btn.click(reset_filters, outputs=[*list_outputs, start_input, end_input, category_input, page_size_input])

    table.select(
        load_row,
        inputs=[last_items],
        outputs=[record_id_input, amount_input, category_edit, merchant_input, occurred_edit, note_input, status_area],
    )

    update_btn.click(
        save_record,
        inputs=[record_id_input, amount_input, category_edit, merchant_input, occurred_edit, note_input, *page_inputs],
        outputs=[status_area, *list_outputs],
    )
    delete_btn.click(
        remove_record,
        inputs=[record_id_input, confirm_delete, *page_inputs],
        outputs=[status_area, confirm_delete, *list_outputs],
    )

    def initial_load():
        return _query("", "", _ALL, DEFAULT_PAGE_SIZE, DEFAULT_PAGE)

    return {
        "table": table,
        "page_info": page_info,
        "status_area": status_area,
        "page_state": page_state,
        "last_items": last_items,
        "start_input": start_input,
        "end_input": end_input,
        "category_input": category_input,
        "page_size_input": page_size_input,
        "initial_load": initial_load,
        "list_outputs": list_outputs,
    }
