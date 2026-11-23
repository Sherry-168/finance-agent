"""卡片与通用 HTML 原语（week2 文档 §2 分层：cards.py）。

Gradio 原生组件对卡片、进度条支持有限，
按《前端注意事项》第 7 条：复杂结构统一用 gr.HTML + 自定义 CSS（fa-* 类）承载。
"""

from config import APP_SUBTITLE, APP_TITLE

# ------------------------------------------------------------------ 页面骨架


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


# ------------------------------------------------------------------ 展示格式化


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


# ------------------------------------------------------------------ 草稿确认卡


def _field_row(label: str, value_html: str, unconf: bool = False) -> str:
    """字段行；unconf=True 时加虚线黄描边（P0-3 低置信度提示）。"""
    return (
        f'<div class="fa-field-row{" is-unconf" if unconf else ""}">'
        f'<span class="fa-field-label">{label}</span>'
        f'<span class="fa-field-value">{value_html}</span>'
        "</div>"
    )


def _conf_badge(show: bool) -> str:
    return ' <span class="fa-unconf">请确认</span>' if show else ""


def draft_card_placeholder() -> str:
    """无草稿时的占位卡。"""
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
      在左侧输入一句话生成草稿；解析只生成草稿，点击「确认入库」才会写入数据库。
    </div>
    """


def draft_card(draft: dict) -> str:
    """渲染归一化后的草稿确认卡（只读展示，修改走下方表单）。

    信息层级（week2 文档 B2）：金额最大字号 → 类别 chip → 商户/时间次要灰 → 置信度。
    """
    fields = draft.get("fields") or {}
    missing = draft.get("missing_fields") or []

    def missing_mark(key: str) -> str:
        return ' <span class="fa-missing">待补充</span>' if key in missing else ""

    # P0-3：置信度 < 0.8 时，金额/类别两个字段加黄色描边 + 「请确认」角标
    confidence = draft.get("confidence")
    low_conf = isinstance(confidence, (int, float)) and confidence < 0.8

    amount = fields.get("amount")
    amount_html = (
        f'<span class="fa-amount">{format_yuan(amount)}</span>'
        if amount is not None
        else "待补充"
    )
    rows = "".join(
        [
            _field_row(
                "金额",
                amount_html + missing_mark("amount") + _conf_badge(low_conf),
                unconf=low_conf,
            ),
            _field_row(
                "类别",
                f"{fields.get('category') or '待补充'}"
                + missing_mark("category")
                + _conf_badge(low_conf),
                unconf=low_conf,
            ),
            _field_row("商户", fields.get("merchant") or "—"),
            _field_row(
                "消费时间",
                f"{fields.get('occurred_at') or '待补充'}" + missing_mark("occurred_at"),
            ),
            _field_row("备注", fields.get("note") or "—"),
        ]
    )

    conf_html = format_ratio(confidence) if isinstance(confidence, (int, float)) else "--"
    rows += _field_row("置信度", conf_html)

    badge = "fa-badge is-ok" if not missing else "fa-badge is-warn"
    badge_text = "槽位齐全" if not missing else "待补充"
    draft_id = draft.get("draft_id")
    title = f"草稿确认卡{f' · {draft_id}' if draft_id else ''}"

    return f"""
    <div class="fa-draft">
      <div class="fa-draft-head">
        <span class="fa-draft-head-title">{title}</span>
        <span class="{badge}">{badge_text}</span>
      </div>
      {rows}
    </div>
    <div class="fa-tip" style="margin-top:10px">
      解析只生成草稿（不入库）。信息不全时继续在左侧对话补充；
      字段有误可直接在下方表单修改后确认。
    </div>
    """


def created_card(record_id, notice: str = "") -> str:
    """确认入库成功后的提示卡。"""
    text = f"已确认入库：记录 id {record_id}（confirmed=1），可到「明细管理」查看。"
    if notice:
        text += f"<br><br>{notice}"
    return tip(text, kind="ok")


def ocr_drafts_card(drafts: list, engine: str = "") -> str:
    """小票多草稿卡片：逐条展示，勾选动作由下方 CheckboxGroup 承载。"""
    if not drafts:
        return empty_state("未识别到消费条目", "请换一张更清晰的小票，或手动在左侧记一笔。")
    rows = []
    for index, draft in enumerate(drafts, start=1):
        fields = draft.get("fields") or {}
        missing = draft.get("missing_fields") or []
        meta = " / ".join(
            part for part in (
                fields.get("merchant") or "商户未识别",
                fields.get("occurred_at") or "时间未识别",
            ) if part
        )
        warn = f' <span class="fa-missing">待补充 {"、".join(missing)}</span>' if missing else ""
        rows.append(
            '<div class="fa-field-row">'
            f'<span class="fa-field-label">{index}. {fields.get("category") or "其他"}</span>'
            f'<span class="fa-field-value">{format_yuan(fields.get("amount"))} · {meta}{warn}</span>'
            "</div>"
        )
    engine_text = f" · 引擎 {engine}" if engine else ""
    return (
        '<div class="fa-draft">'
        f'<div class="fa-draft-head"><span class="fa-draft-head-title">小票草稿（{len(drafts)} 笔）</span>'
        '<span class="fa-badge is-ok">待勾选</span></div>'
        + "".join(rows)
        + "</div>"
        + f'<div class="fa-tip" style="margin-top:8px">仅勾选的条目会入库，金额由后端返回，前端不换算。{engine_text}</div>'
    )


# ------------------------------------------------------------------ 预算卡


def budget_progress(items: list, notice: str = "") -> str:
    """渲染预算预警列表：used_ratio / status 完全取后端（§6 契约）。

    状态 → 样式：normal 正常 / warning ≥80% 预警 / over ≥100% 超支。
    """
    rows = []
    for item in items:
        name = item.get("category") or "总预算"
        amount = item.get("amount")
        used = item.get("used")
        ratio = item.get("used_ratio")
        status = item.get("status")
        if status not in ("normal", "warning", "over"):
            if isinstance(ratio, (int, float)):
                status = "over" if ratio >= 1 else ("warning" if ratio >= 0.8 else "normal")
            else:
                status = "normal"

        meta = f"{format_yuan(used)} / {format_yuan(amount)}"
        pct = round(float(ratio) * 100, 1) if isinstance(ratio, (int, float)) else 0
        width = min(max(pct, 2.0), 100.0)
        numeric = isinstance(used, (int, float)) and isinstance(amount, (int, float))
        if status == "over":
            over = (float(used) - float(amount)) if numeric else None
            if over and over > 0:
                # P0-6：超 100% 的条目右侧显示超出金额（红）
                meta += f" · <b style='color:var(--fa-over)'>超 {format_yuan(over)}</b>"
            alert = "已超出预算，尽快控制消费"
        elif status == "warning":
            remaining = (float(amount) - float(used)) if numeric else None
            # P0-6：超 80% 的条目右侧显示剩余额度
            if remaining is not None:
                meta += f" · 剩 {format_yuan(remaining)}"
            alert = f"已用 {format_ratio(ratio)}，接近预算上限"
        else:
            alert = f"已用 {format_ratio(ratio)}，额度充足"
        rows.append(
            f"""
        <div class="fa-budget-item">
          <div class="fa-budget-top">
            <span>{name}　<span class="fa-badge{' is-ok' if status == 'normal' else (' is-warn' if status == 'warning' else ' is-over')}">{status}</span></span>
            <span class="fa-budget-meta">{meta}</span>
          </div>
          <div class="fa-bar"><div class="fa-bar-fill is-{status}" style="width:{width}%"></div></div>
          <div class="fa-budget-alert is-{status}">{alert}</div>
        </div>
        """
        )
    body = "".join(rows) or '<div class="fa-empty" style="padding:24px 0;text-align:center;opacity:.65">本月暂未设定预算</div>'
    notice_html = f"<br><i style='opacity:.7'>{notice}</i>" if notice else ""
    return body + f'<div class="fa-tip" style="margin-top:10px">已用 ≥80% 预警、≥100% 超支；使用率由后端聚合（仅已确认记录）。{notice_html}</div>'


def budget_list(items: list, notice: str = "") -> str:
    """GET /budgets 的已设预算清单（只读展示，不参与计算）。"""
    if not items:
        body = '<div class="fa-empty" style="padding:20px 0;text-align:center;opacity:.7">本月暂未设定预算</div>'
    else:
        rows = "".join(
            "<tr>"
            f"<td>{item.get('category') or '总预算'}</td>"
            f"<td style='text-align:right'>{format_yuan(item.get('amount'))}</td>"
            f"<td style='text-align:right;opacity:.65'>#{item.get('id', '—')}</td>"
            "</tr>"
            for item in items
        )
        body = (
            '<table class="fa-table" style="width:100%;border-collapse:collapse;font-size:13px">'
            '<thead><tr><th style="text-align:left">维度</th>'
            '<th style="text-align:right">预算上限</th><th style="text-align:right">ID</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )
    extra = f'<div class="fa-tip" style="margin-top:8px"><i>{notice}</i></div>' if notice else ""
    return (
        '<div class="fa-section-head"><span class="fa-section-title">已设预算</span>'
        '<span class="fa-section-desc">GET /budgets</span></div>'
        + body
        + extra
    )


# ------------------------------------------------------------------ 仪表盘首屏（P1-3 / B5）


def dashboard_card(summary: dict, total_budget: dict | None, notice: str = "") -> str:
    """左侧仪表盘：本月支出 / 预算剩余两个大数字 + 迷你环形进度。

    无论在哪个 Tab，预算压力始终可见（呼应「主动提醒」选题点）。
    数字全部来自后端 /stats/summary 与 /budgets/alerts，前端不计算。
    """
    spent = format_yuan(summary.get("total"))
    count = summary.get("count")
    daily = format_yuan(summary.get("daily_avg"))
    sub = f"{count} 笔 · 日均 {daily}" if isinstance(count, (int, float)) else f"日均 {daily}"

    amount = (total_budget or {}).get("amount")
    used = (total_budget or {}).get("used")
    ratio = (total_budget or {}).get("used_ratio")
    status = (total_budget or {}).get("status") or "normal"
    if isinstance(amount, (int, float)) and isinstance(used, (int, float)):
        remaining = float(amount) - float(used)
        remaining_text = format_yuan(abs(remaining))
        remaining_text = f"-{remaining_text}" if remaining < 0 else remaining_text
        remaining_label = "预算超出" if remaining < 0 else "预算剩余"
    else:
        remaining_text = "--"
        remaining_label = "预算剩余"
        amount = None
    pct = min(round(float(ratio) * 100), 100) if isinstance(ratio, (int, float)) else 0

    notice_html = f'<div class="fa-dash-notice">{notice}</div>' if notice else ""
    return f"""
    <div class="fa-dash">
      <div class="fa-dash-label">本月支出</div>
      <div class="fa-dash-big">{spent}</div>
      <div class="fa-dash-sub">{sub}</div>
      <div class="fa-ring is-{status}" style="--pct:{pct}"><div class="fa-ring-pct">{pct}%</div></div>
      <div class="fa-dash-row">
        <span>{remaining_label}</span>
        <b>{remaining_text}</b>
      </div>
      <div class="fa-dash-row is-muted">
        <span>总预算</span><b>{format_yuan(amount)}</b>
      </div>
      {notice_html}
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
