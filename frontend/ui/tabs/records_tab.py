"""Tab2 明细管理：筛选 + 分页表格 + 增删改。

Day 1：搭筛选条、表格、分页与操作区骨架（数据为空态）。
Day 4：接 GET /records?start=&end=&category=&page=&size=、PUT /records/{id}、DELETE /records/{id}。
"""

import gradio as gr

from config import CATEGORIES, DEFAULT_PAGE, DEFAULT_PAGE_SIZE, PAGE_SIZE_CHOICES
from ui import components as c


def build_records_tab() -> dict:
    gr.HTML(c.section_head("消费明细", "按时间与类别筛选，支持修正与删除"))

    with gr.Row(elem_classes=["fa-toolbar"]):
        start_input = gr.Textbox(
            label="开始日期", placeholder="2026-11-01", scale=2
        )
        end_input = gr.Textbox(
            label="结束日期", placeholder="2026-11-30", scale=2
        )
        category_input = gr.Dropdown(
            label="类别",
            choices=["全部"] + CATEGORIES,
            value="全部",
            scale=2,
        )
        page_size_input = gr.Dropdown(
            label="每页",
            choices=PAGE_SIZE_CHOICES,
            value=DEFAULT_PAGE_SIZE,
            scale=1,
        )
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

    with gr.Row(elem_classes=["fa-toolbar"]):
        prev_btn = gr.Button("上一页", variant="secondary", scale=1)
        page_info = gr.HTML(
            f'<div class="fa-section-desc">第 {DEFAULT_PAGE} 页 · 共 0 条</div>'
        )
        next_btn = gr.Button("下一页", variant="secondary", scale=1)

    with gr.Accordion("修改 / 删除记录", open=False):
        gr.HTML(
            c.tip(
                "金额统一记正数支出，展示为 ¥；草稿（confirmed=0）与已确认记录在表格「状态」列区分。"
                "删除为不可逆操作，需先勾选确认。"
            )
        )
        with gr.Row(elem_classes=["fa-toolbar"]):
            record_id_input = gr.Number(
                label="记录 ID", precision=0, scale=1, minimum=1
            )
            amount_input = gr.Number(label="金额 (¥)", scale=2)
            category_edit = gr.Dropdown(
                label="类别", choices=CATEGORIES, scale=2
            )
            merchant_input = gr.Textbox(label="商户", scale=2)
            note_input = gr.Textbox(label="备注", scale=2)
        with gr.Row(elem_classes=["fa-toolbar"]):
            update_btn = gr.Button("保存修改", variant="primary", scale=1)
            confirm_delete = gr.Checkbox(label="我确认删除该记录", value=False, scale=1)
            delete_btn = gr.Button("删除记录", variant="stop", scale=1)

    status_area = gr.HTML(
        c.empty_state(
            "暂无数据",
            "查询后在此展示明细（当前为 Day 1 骨架，接口于 Day 4 接入）。",
        )
    )

    # ---------------- 骨架阶段的占位交互（Day 4 替换为真实调用） ----------------
    search_btn.click(
        lambda: c.todo_notice("明细查询 GET /records", "Day 4"), outputs=status_area
    )
    reset_btn.click(
        lambda: (
            "",
            "",
            "全部",
            DEFAULT_PAGE_SIZE,
            c.empty_state("暂无数据", "筛选条件已重置。"),
        ),
        outputs=[
            start_input,
            end_input,
            category_input,
            page_size_input,
            status_area,
        ],
    )
    update_btn.click(
        lambda: c.todo_notice("记录修改 PUT /records/{id}", "Day 4"),
        outputs=status_area,
    )
    delete_btn.click(
        lambda: c.todo_notice("记录删除 DELETE /records/{id}", "Day 4"),
        outputs=status_area,
    )

    return {
        "start_input": start_input,
        "end_input": end_input,
        "category_input": category_input,
        "page_size_input": page_size_input,
        "search_btn": search_btn,
        "reset_btn": reset_btn,
        "table": table,
        "prev_btn": prev_btn,
        "next_btn": next_btn,
        "page_info": page_info,
        "record_id_input": record_id_input,
        "amount_input": amount_input,
        "category_edit": category_edit,
        "merchant_input": merchant_input,
        "note_input": note_input,
        "update_btn": update_btn,
        "confirm_delete": confirm_delete,
        "delete_btn": delete_btn,
        "status_area": status_area,
    }
