"""演示入口区：一键灌入 / 清空演示数据，附后端连通性自检。

Day 2：接 GET /health 验证前后端连通。
Day 6：接 POST /demo/load、POST /demo/reset（评审无 Key 环境的演示通道）。
"""

import time

import gradio as gr

import api
import mock
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


def load_demo_data() -> str:
    """POST /demo/load：网络失败且允许时降级本地演示数据。"""
    notice = ""
    try:
        result = api.demo_load()
    except api.ApiError as exc:
        if exc.is_network_error and MOCK_FALLBACK:
            result = mock.demo_load()
            notice = mock.NOTICE
        else:
            return c.tip(f"演示数据加载失败：{exc.message}", kind="error")

    return c.tip(
        f"演示数据已灌入：{result.get('records', 0)} 笔明细（{result.get('months', 0)} 个月）"
        f" + {result.get('receipts', 0)} 张小票记录，并布置了含预警/超支演示点的预算。"
        f"<br>请到「明细管理」「统计图表」「预算中心」查看效果。"
        f"{f'<br>{notice}' if notice else ''}",
        kind="ok",
    )


def reset_demo_data(confirm: bool):
    """POST /demo/reset：清空演示数据（不可逆，需勾选确认）。"""
    if not confirm:
        return c.tip("清空不可恢复：请先勾选「我确认清空演示数据」。", kind="warn"), False

    notice = ""
    try:
        result = api.demo_reset()
    except api.ApiError as exc:
        if exc.is_network_error and MOCK_FALLBACK:
            result = mock.demo_reset()
            notice = mock.NOTICE
        else:
            return c.tip(f"清空失败：{exc.message}", kind="error"), False

    return (
        c.tip(
            f"已清空：{result.get('deleted_records', 0)} 笔演示明细、{result.get('deleted_budgets', 0)} 条演示预算。"
            f"{f'<br>{notice}' if notice else ''}",
            kind="ok",
        ),
        False,
    )


def build_demo_tab() -> dict:
    gr.HTML(c.demo_card())

    with gr.Row(elem_classes=["fa-toolbar"]):
        load_btn = gr.Button("一键灌入演示数据", variant="primary", scale=2)
        reset_btn = gr.Button("清空演示数据", variant="stop", scale=1)
        health_btn = gr.Button("检查后端连通性", variant="secondary", scale=1)

    confirm_reset = gr.Checkbox(label="我确认清空演示数据（不可恢复）", value=False)

    result_area = gr.HTML(
        c.empty_state(
            "尚未执行操作",
            "加载后到「明细」「统计」「预算」页查看效果；清空会删除演示数据与演示预算。",
        )
    )

    gr.HTML(
        c.tip(
            f"当前后端地址：{API_BASE_URL}　（环境变量 API_BASE_URL 可覆盖）"
            "　演示数据覆盖 8 类并埋设娱乐超支演示点，便于展示预算预警三态。"
        )
    )

    # ---------------- 事件绑定 ----------------
    health_btn.click(check_backend, outputs=result_area)
    load_btn.click(load_demo_data, inputs=None, outputs=result_area)
    reset_btn.click(
        reset_demo_data,
        inputs=[confirm_reset],
        outputs=[result_area, confirm_reset],
    )

    return {
        "load_btn": load_btn,
        "reset_btn": reset_btn,
        "health_btn": health_btn,
        "confirm_reset": confirm_reset,
        "result_area": result_area,
    }
