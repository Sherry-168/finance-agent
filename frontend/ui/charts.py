"""Plotly 图表工厂（week2 文档 §2 分层：charts.py）。

第二周统一口径（week2-plan P0-5）：Plotly + gr.Plot。
主题三要素：透明背景 / 统一色板 / 中文显式字体（否则容器里变方块）。

文件尾部保留第一周的 ECharts iframe 方案作为离线降级参考，统计页已不再引用。
"""

import html
import json

import plotly.graph_objects as go

PLOTLY_FONT = "-apple-system, PingFang SC, Microsoft YaHei, Noto Sans SC, sans-serif"
# v2.2 色板：统一取自深青绿 5 阶 + 中性灰，红/黄只作末位语义点缀
CHART_PALETTE = [
    "#0F9D8A", "#14B8A6", "#2DD4BF", "#104A44",
    "#6B7280", "#9CA3AF", "#F5C26B", "#E05B5B",
]
_TEXT, _TEXT_2 = "#1F2937", "#6B7280"


def _chart_layout(fig: "go.Figure", legend: bool = False) -> "go.Figure":
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": PLOTLY_FONT, "size": 12, "color": _TEXT},
        margin={"l": 10, "r": 10, "t": 14, "b": 10},
        showlegend=legend,
    )
    return fig


def empty_figure(text: str) -> "go.Figure":
    """空数据占位：只显示文案，不渲染空白坐标轴（P0-5 要求）。"""
    fig = go.Figure()
    fig.add_annotation(
        text=text, showarrow=False, font={"size": 14, "color": _TEXT_2}
    )
    fig.update_layout(xaxis={"visible": False}, yaxis={"visible": False})
    return _chart_layout(fig)


def pie_figure(items: list) -> "go.Figure":
    """类别占比环图；占比 <3% 的类别合并为「其他」（B6），标签「类别 12.3%」。"""
    threshold = 0.03
    labels, values, other_total = [], [], 0.0
    for item in sorted(items, key=lambda x: float(x.get("total") or 0), reverse=True):
        total = float(item.get("total") or 0)
        ratio = float(item.get("ratio") or 0)
        if ratio and ratio < threshold:
            other_total += total
        else:
            labels.append(item.get("category") or "其他")
            values.append(round(total, 2))
    if other_total > 0:
        labels.append("其他")
        values.append(round(other_total, 2))

    fig = go.Figure(
        go.Pie(
            name="消费类别占比",
            labels=labels,
            values=values,
            hole=0.42,
            sort=False,
            marker={"colors": CHART_PALETTE, "line": {"color": "#fff", "width": 2}},
            texttemplate="%{label} %{percent:.1%}",
            textposition="outside",
            hovertemplate="%{label}：¥%{value:,.2f}（%{percent:.1%}）<extra></extra>",
        )
    )
    return _chart_layout(fig)


def trend_figure(items: list) -> "go.Figure":
    """每日趋势折线；hover 显示「日期 · ¥金额 · N 笔」，Y 轴金额（P0-5）。"""
    dates = [item.get("date", "") for item in items]
    totals = [round(float(item.get("total") or 0), 2) for item in items]
    counts = [int(item.get("count") or 0) for item in items]

    fig = go.Figure(
        go.Scatter(
            name="每日支出趋势",
            x=dates,
            y=totals,
            customdata=counts,
            mode="lines+markers" if len(dates) <= 31 else "lines",
            line={"color": CHART_PALETTE[0], "width": 2.4, "shape": "spline"},
            marker={"size": 6},
            fill="tozeroy",
            fillcolor="rgba(47,107,255,0.10)",
            hovertemplate="%{x} · ¥%{y:,.2f} · %{customdata} 笔<extra></extra>",
        )
    )
    fig.update_xaxes(showgrid=False, tickformat="%m-%d", tickfont={"size": 10, "color": _TEXT_2})
    fig.update_yaxes(
        tickprefix="¥", gridcolor="#EEF1F5", tickfont={"size": 10, "color": _TEXT_2}
    )
    return _chart_layout(fig)


# ------------------------------------------------------------------ ECharts 遗留方案（离线降级参考，统计页未引用）
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


def chart_placeholder(chart_id: str, title: str, desc: str) -> str:
    """ECharts 挂载点：Day 5 曾用 gr.HTML 注入图表脚本填充该容器。"""
    return (
        f'<div class="fa-chart" id="{chart_id}">'
        f'<div class="fa-chart-placeholder-title">{title}</div>'
        f'<div class="fa-chart-placeholder-desc">{desc}</div>'
        "</div>"
    )


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
