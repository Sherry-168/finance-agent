"""可复用 HTML 组件。

Gradio 原生组件对卡片、进度条、图表容器支持有限，
按《前端注意事项》第 7 条：复杂结构统一用 gr.HTML + 自定义 CSS（fa-* 类）承载。
"""

from config import APP_SUBTITLE, APP_TITLE

# ------------------------------------------------------------------ 顶部标题


def header() -> str:
    return f"""
    <div class="fa-header">
      <div>
        <h1 class="fa-header-title">{APP_TITLE}</h1>
        <p class="fa-header-sub">{APP_SUBTITLE}</p>
      </div>
      <div class="fa-header-tags">
        <span class="fa-tag">文本记账</span>
        <span class="fa-tag">自动分类统计</span>
        <span class="fa-tag">自然语言查账</span>
        <span class="fa-tag">预算提醒</span>
      </div>
    </div>
    """


def footer_note() -> str:
    return (
        '<div class="fa-tip" style="margin-top:12px">'
        "金额、统计与预算判断全部由后端计算，前端只负责渲染结果，不做任何算数。"
        "</div>"
    )


# ------------------------------------------------------------------ 区块标题


def section_head(title: str, desc: str = "") -> str:
    desc_html = f'<span class="fa-section-desc">{desc}</span>' if desc else ""
    return (
        '<div class="fa-section-head">'
        f'<span class="fa-section-title">{title}</span>{desc_html}'
        "</div>"
    )


def tip(text: str, kind: str = "info") -> str:
    """kind: info / ok / warn / error（对应 CSS 里的状态配色）。"""
    extra = "" if kind == "info" else f" is-{kind}"
    return f'<div class="fa-tip{extra}">{text}</div>'


def format_yuan(value) -> str:
    """金额展示格式化：¥1,286.50。

    约定（docs/api.md §1）：对外接口的金额单位统一为「元」，前端不做换算，
    只负责展示格式；value 非法时返回占位符。
    """
    if isinstance(value, (int, float)):
        return f"¥{value:,.2f}"
    return "¥ --"


def format_ratio(value) -> str:
    """占比 / 使用率展示：0.83 → 83%（约定为 0~1 小数）。"""
    if isinstance(value, (int, float)):
        return f"{value * 100:.0f}%"
    return "--%"


def draft_summary(draft: dict) -> str:
    """把归一化后的草稿整理成 AI 气泡文案（不参与任何计算）。"""
    fields = draft.get("fields") or {}
    lines = []

    amount_text = format_yuan(fields.get("amount")) if fields.get("amount") is not None else "未识别"
    lines.append(f"金额：{amount_text}")
    lines.append(f"类别：{fields.get('category') or '未识别'}")
    if fields.get("merchant"):
        lines.append(f"商户：{fields['merchant']}")
    if fields.get("occurred_at"):
        lines.append(f"时间：{fields['occurred_at']}")
    if fields.get("note"):
        lines.append(f"备注：{fields['note']}")

    confidence = draft.get("confidence")
    if isinstance(confidence, (int, float)):
        lines.append(f"置信度：{confidence * 100:.0f}%")

    missing = draft.get("missing_fields") or []
    if missing:
        lines.append(f"待补充字段：{'、'.join(missing)}")

    return "已解析为草稿（**尚未入库**）：\n\n- " + "\n- ".join(lines) + "\n\n确认卡交互即将开放，当前草稿不会写入数据库。"


def empty_state(title: str, desc: str) -> str:
    return (
        '<div class="fa-empty">'
        f'<div class="fa-empty-title">{title}</div>'
        f'<div class="fa-empty-desc">{desc}</div>'
        "</div>"
    )


def todo_notice(feature: str, day: str) -> str:
    """骨架阶段按钮的占位反馈，接口接入后替换为真实渲染。"""
    return (
        '<div class="fa-tip">'
        f"「{feature}」尚未接入，计划 {day} 联调后启用。当前为 Day 1 界面骨架。"
        "</div>"
    )


# ------------------------------------------------------------------ 指标卡


def metric_cards(items: list[tuple[str, str, str]]) -> str:
    """items: [(label, value, hint), ...]"""
    cards = "".join(
        f"""
        <div class="fa-metric">
          <div class="fa-metric-label">{label}</div>
          <div class="fa-metric-value">{value}</div>
          <div class="fa-metric-hint">{hint}</div>
        </div>
        """
        for label, value, hint in items
    )
    return f'<div class="fa-metric-grid">{cards}</div>'


# ------------------------------------------------------------------ 图表容器


def chart_placeholder(chart_id: str, title: str, desc: str) -> str:
    """ECharts 挂载点：Day 5 用 gr.HTML 注入图表脚本填充该容器。"""
    return (
        f'<div class="fa-chart" id="{chart_id}">'
        f'<div class="fa-chart-placeholder-title">{title}</div>'
        f'<div class="fa-chart-placeholder-desc">{desc}</div>'
        "</div>"
    )


# ------------------------------------------------------------------ 草稿确认卡


def _field_row(label: str, value_html: str) -> str:
    return (
        '<div class="fa-field-row">'
        f'<span class="fa-field-label">{label}</span>'
        f'<span class="fa-field-value">{value_html}</span>'
        "</div>"
    )


def draft_card_placeholder() -> str:
    """草稿确认卡骨架（Day 3 接入 /records/parse 后改为动态渲染）。"""
    fields = "".join(
        [
            _field_row("金额", '<span class="fa-amount">¥ --</span>'),
            _field_row("类别", "待解析"),
            _field_row("商户", "待解析"),
            _field_row("消费时间", "待解析"),
            _field_row("备注", "待解析"),
            _field_row("置信度", "待解析"),
        ]
    )
    return f"""
    <div class="fa-draft">
      <div class="fa-draft-head">
        <span class="fa-draft-head-title">草稿确认卡</span>
        <span class="fa-badge">未入库</span>
      </div>
      {fields}
    </div>
    <div class="fa-tip" style="margin-top:10px">
      解析只生成草稿，点击「确认入库」才会写入；信息不全时先以反问气泡继续对话。
      确认与修改按钮于 Day 3 接入。
    </div>
    """


# ------------------------------------------------------------------ 预算卡


def budget_placeholder() -> str:
    """预算进度卡骨架，示意外观与 normal / warning / over 三种状态样式。"""
    rows = [
        ("餐饮", "¥ 1,240 / ¥ 1,500", 83, "warning", "已用 83%，接近预算上限"),
        ("娱乐", "¥ 860 / ¥ 800", 100, "over", "已超支 ¥ 60"),
    ]
    items = ""
    for name, meta, ratio, state, alert in rows:
        width = min(ratio, 100)
        items += f"""
        <div class="fa-budget-item">
          <div class="fa-budget-top">
            <span>{name}</span>
            <span class="fa-budget-meta">{meta}</span>
          </div>
          <div class="fa-bar"><div class="fa-bar-fill is-{state}" style="width:{width}%"></div></div>
          <div class="fa-budget-alert is-{state}">{alert}</div>
        </div>
        """
    return f"""
    {items}
    <div class="fa-tip">
      以上为样式示意（示例数据）。真实进度取自 GET /budgets/alerts?month=，Day 6 接入。
    </div>
    """


# ------------------------------------------------------------------ 演示入口


def demo_card() -> str:
    return """
    <div class="fa-demo-card">
      <div class="fa-demo-title">演示数据一键灌入</div>
      <div class="fa-demo-desc">
        评审环境没有 LLM Key 时，用这里加载预置账单（约 60 笔 × 2 个月 + 3 张小票记录），
        立刻可以体验明细、统计与预算提醒；结束后可一键清空，不影响真实数据判断。
      </div>
    </div>
    """
