"""可复用 HTML 组件。

Gradio 原生组件对卡片、进度条、图表容器支持有限，
按《前端注意事项》第 7 条：复杂结构统一用 gr.HTML + 自定义 CSS（fa-* 类）承载。
"""

import html
import json

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

    return "已解析为草稿（**尚未入库**）：\n\n- " + "\n- ".join(lines) + "\n\n请在右侧确认卡核对，可直接修改字段后入库。"


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
        if status == "over":
            over = (float(used) - float(amount)) if isinstance(used, (int, float)) and isinstance(amount, (int, float)) else None
            alert = f"已超支 {format_yuan(over)}，尽快控制消费" if over and over > 0 else "已超出预算，尽快控制消费"
        elif status == "warning":
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


def chart_placeholder(chart_id: str, title: str, desc: str) -> str:
    """ECharts 挂载点：Day 5 用 gr.HTML 注入图表脚本填充该容器。"""
    return (
        f'<div class="fa-chart" id="{chart_id}">'
        f'<div class="fa-chart-placeholder-title">{title}</div>'
        f'<div class="fa-chart-placeholder-desc">{desc}</div>'
        "</div>"
    )


# ------------------------------------------------------------------ ECharts 图表
# Gradio 的 gr.HTML 通过 innerHTML 注入，<script> 不会执行，
# 因此图表统一放在 <iframe srcdoc> 里运行；ECharts 走 CDN，
# 加载失败（离线评审）时自动降级为纯 CSS 条形视图，数据不丢失。

_ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"

_FALLBACK_CSS = """
  html,body{margin:0;padding:0;background:#fff;}
  #app{width:100%;height:{height}px;}
  .fb{font:12px/1.7 -apple-system,'Segoe UI',sans-serif;color:#334;box-sizing:border-box;width:100%;padding:12px 14px;}
  .fb-title{font-weight:600;color:#1d3557;margin-bottom:8px;}
  .fb-row{display:flex;align-items:center;margin:5px 0;}
  .fb-name{width:58px;flex:none;white-space:nowrap;}
  .fb-track{flex:1;background:#eef3f2;border-radius:6px;height:15px;overflow:hidden;}
  .fb-fill{display:block;height:100%;background:linear-gradient(90deg,#2a9d8f,#4cc4b3);}
  .fb-val{width:88px;flex:none;text-align:right;color:#1d3557;font-variant-numeric:tabular-nums;}
"""

_IFRAME_JS = """
var spec = {spec};
var app = document.getElementById('app');
function fallback(){
  var rows = (spec.fallback || []).map(function(row){
    return '<div class="fb-row"><span class="fb-name">' + row.name + '</span>'
      + '<span class="fb-track"><span class="fb-fill" style="width:' + row.pct + '%"></span></span>'
      + '<span class="fb-val">' + row.value + '</span></div>';
  }).join('');
  app.innerHTML = '<div class="fb"><div class="fb-title">' + spec.fallbackTitle + '</div>' + rows + '</div>';
}
if (window.echarts) {
  var chart = echarts.init(app);
  chart.setOption(spec.option);
  window.addEventListener('resize', function(){ chart.resize(); });
} else {
  fallback();
}
"""


def pie_spec(items: list, notice: str = "") -> dict:
    """类别占比 → ECharts 环形饼图 option + 离线兜底条形数据。"""
    palette = ["#2a9d8f", "#e9c46a", "#f4a261", "#e76f51", "#457b9d", "#8ab17d", "#b5838d", "#6d6875"]
    data = [
        {"name": item.get("category") or "其他", "value": round(float(item.get("total") or 0), 2)}
        for item in items
    ]
    grand = sum(entry["value"] for entry in data)
    fallback = [
        {
            "name": entry["name"],
            "pct": round(entry["value"] / grand * 100, 1) if grand else 0,
            "value": f"¥{entry['value']:,.2f}",
        }
        for entry in data
    ]
    return {
        "option": {
            "tooltip": {"trigger": "item", "formatter": "{b}：¥{c}（{d}%）"},
            "color": palette,
            "legend": {"bottom": 0, "itemWidth": 10, "itemHeight": 10, "textStyle": {"fontSize": 11}},
            "series": [
                {
                    "type": "pie",
                    "radius": ["40%", "66%"],
                    "center": ["50%", "44%"],
                    "data": data,
                    "label": {"fontSize": 11, "formatter": "{b} {d}%"},
                    "itemStyle": {"borderRadius": 6, "borderColor": "#fff", "borderWidth": 2},
                }
            ],
        },
        "fallbackTitle": f"类别占比（离线简化视图）{' · ' + notice if notice else ''}",
        "fallback": fallback,
    }


def trend_spec(items: list, notice: str = "") -> dict:
    """每日趋势 → ECharts 折线面积图 option + 离线兜底条形数据。"""
    dates = [item.get("date", "")[5:] for item in items]
    totals = [round(float(item.get("total") or 0), 2) for item in items]
    peak = max(totals) if totals else 0
    fallback = [
        {
            "name": date,
            "pct": round(total / peak * 100, 1) if peak else 0,
            "value": f"¥{total:,.2f}",
        }
        for date, total in zip(dates, totals)
    ]
    return {
        "option": {
            "tooltip": {"trigger": "axis", "valueFormatter": "function(v){return '¥' + Number(v).toLocaleString(undefined,{minimumFractionDigits:2});}"},
            "grid": {"left": 56, "right": 18, "top": 24, "bottom": 30},
            "xAxis": {"type": "category", "data": dates, "boundaryGap": False, "axisLabel": {"fontSize": 10, "interval": max(0, len(dates) // 10)}},
            "yAxis": {"type": "value", "axisLabel": {"fontSize": 10, "formatter": "¥{value}"}},
            "series": [
                {
                    "type": "line",
                    "data": totals,
                    "smooth": True,
                    "showSymbol": len(totals) <= 31,
                    "lineStyle": {"color": "#2a9d8f", "width": 2.4},
                    "areaStyle": {"color": "rgba(42,157,143,0.14)"},
                }
            ],
        },
        "fallbackTitle": f"每日趋势（离线简化视图）{' · ' + notice if notice else ''}",
        "fallback": fallback,
    }


def chart_iframe(spec: dict, height: int = 330) -> str:
    """把图表 spec 渲染成带 ECharts / 纯 CSS 兜底的 iframe。"""
    css = _FALLBACK_CSS.replace("{height}", str(height))
    js = _IFRAME_JS.replace("{spec}", json.dumps(spec, ensure_ascii=False))
    body = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<script src="{_ECHARTS_CDN}" onerror="window.__noEcharts=true"></script>
<style>{css}</style></head><body>
<div id="app" style="width:100%;height:{height}px"></div>
<script>{js}</script>
</body></html>"""
    return f'<iframe srcdoc="{html.escape(body, quote=True)}" style="width:100%;height:{height + 8}px;border:0;border-radius:12px;background:#fff"></iframe>'


# ------------------------------------------------------------------ 草稿确认卡


def _field_row(label: str, value_html: str) -> str:
    return (
        '<div class="fa-field-row">'
        f'<span class="fa-field-label">{label}</span>'
        f'<span class="fa-field-value">{value_html}</span>'
        "</div>"
    )


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
    """渲染归一化后的草稿确认卡（只读展示，修改走下方表单）。"""
    fields = draft.get("fields") or {}
    missing = draft.get("missing_fields") or []

    def missing_mark(key: str) -> str:
        return ' <span class="fa-missing">待补充</span>' if key in missing else ""

    amount = fields.get("amount")
    amount_html = f'<span class="fa-amount">{format_yuan(amount)}</span>' if amount is not None else "待补充"
    rows = "".join(
        [
            _field_row("金额", amount_html + missing_mark("amount")),
            _field_row("类别", f"{fields.get('category') or '待补充'}" + missing_mark("category")),
            _field_row("商户", fields.get("merchant") or "—"),
            _field_row("消费时间", f"{fields.get('occurred_at') or '待补充'}" + missing_mark("occurred_at")),
            _field_row("备注", fields.get("note") or "—"),
        ]
    )

    confidence = draft.get("confidence")
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
    text = f"已确认入库：记录 id {record_id}（confirmed=1）。明细页稍后可查看（Day 4 接入列表）。"
    if notice:
        text += f"<br><br>{notice}"
    return tip(text, kind="ok")


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
