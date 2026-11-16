"""演示入口区：一键灌入 / 清空演示数据，附后端连通性自检。

Day 2：接 GET /health 验证前后端连通。
Day 6：接 POST /demo/load、POST /demo/reset。
"""

import time

import gradio as gr

import api
from config import API_BASE_URL, MOCK_FALLBACK
from ui import components as c


def check_backend() -> str:
    """调用健康检查，成功/失败都以提示卡展示（不抛异常）。"""
    started = time.perf_counter()
    try:
        detail = api.health()
    except api.ApiError as exc:
        elapsed = (time.perf_counter() - started) * 1000
        hint = (
            "　提示：对话解析已启用本地 Mock 兜底，仍可体验界面；入库与统计需后端启动。"
            if MOCK_FALLBACK
            else ""
        )
        return c.tip(
            f"后端未连通：{exc.message}<br>"
            f"请求地址：{API_BASE_URL}　耗时 {elapsed:.0f} ms。{hint}",
            kind="error",
        )

    elapsed = (time.perf_counter() - started) * 1000
    return c.tip(
        f"后端连通正常：{detail}<br>"
        f"请求地址：{API_BASE_URL}　耗时 {elapsed:.0f} ms。",
        kind="ok",
    )


def build_demo_tab() -> dict:
    gr.HTML(c.demo_card())

    with gr.Row(elem_classes=["fa-toolbar"]):
        load_btn = gr.Button("一键灌入演示数据", variant="primary", scale=2)
        reset_btn = gr.Button("清空演示数据", variant="stop", scale=1)
        health_btn = gr.Button("检查后端连通性", variant="secondary", scale=1)

    result_area = gr.HTML(
        c.empty_state(
            "尚未执行操作",
            "加载后到「明细」「统计」「预算」页查看效果；清空会删除演示数据与演示预算。",
        )
    )

    gr.HTML(
        c.tip(
            f"当前后端地址：{API_BASE_URL}　（环境变量 API_BASE_URL 可覆盖）"
            "　演示数据约 60 笔 × 2 个月 + 3 张小票记录，覆盖 8 类并埋设娱乐超支演示点。"
        )
    )

    # ---------------- 事件绑定 ----------------
    health_btn.click(check_backend, outputs=result_area)

    # 演示数据接口随后端排期（Day 6）接入
    load_btn.click(
        lambda: c.todo_notice("演示数据 POST /demo/load", "Day 6"), outputs=result_area
    )
    reset_btn.click(
        lambda: c.todo_notice("清空演示数据 POST /demo/reset", "Day 6"),
        outputs=result_area,
    )

    return {
        "load_btn": load_btn,
        "reset_btn": reset_btn,
        "health_btn": health_btn,
        "result_area": result_area,
    }
