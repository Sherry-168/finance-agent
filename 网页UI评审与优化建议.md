# 记账小助手 · 网页 UI 评审与优化建议

> 评审日期：2026-11-24
> 评审对象：`frontend/`（Gradio 6.32 + Plotly）
> 评审方式：本地启动前端（`MOCK_FALLBACK=1`），在 1440×1000 视口实际截图 + 通读 `app.py`、`style.css`、`ui/` 全部页面代码
> 结论一句话：**配色和设计令牌已经成型，当前主要短板不是“好不好看”，而是首屏加载态、纵向空间利用、空状态与产品文案。**

---

## 1. 总体评分

| 维度 | 分数 | 判断 |
|---|---:|---|
| 视觉一致性（配色 / 圆角 / 字体） | 8.0 / 10 | 单一青绿主色系执行得很彻底，像一套完整设计系统 |
| 布局与空间利用 | 5.5 / 10 | 首屏内容只占约 60% 高度，下方大面积空白；聊天区固定 380px 偏矮 |
| 信息架构 | 7.0 / 10 | 左侧导航 + 中间对话 + 右侧确认卡结构清晰，但缺少页面标题与层级 |
| 交互反馈 | 6.5 / 10 | 空态 / 错误态 / 降级提示齐全，但全局 processing 提示和残留加载文案破坏首屏 |
| 可访问性 | 5.0 / 10 | 大量 10–11.5px 小字；警示黄字对比度不足；图标按钮无可读名称 |
| 可维护性 | 5.5 / 10 | 48KB CSS 中重复规则与 `!important` 较多，存在未使用的顶栏 / ECharts 遗留代码 |

**综合：6.8 / 10。** 对内部工具来说底子不错，完成下面 4 个 P0 后，观感会有一次明显跃升。

---

## 2. 做得好的地方（建议保留）

1. **设计令牌完整**：主色 5 阶、中性 4 级、圆角 3 档、间距 4 的倍数，都在 [style.css](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/assets/style.css#L7-L69) 统一定义，没有散落魔法值。
2. **单一主色系**：深青绿侧栏 + 青绿行动色，红/黄只用于预算语义，视觉识别度高。
3. **业务状态覆盖全**：空态、错误、低置信度、预算三态、后端未连接、Mock 降级都有对应 UI，不是“只画 happy path”。
4. **金额与数字细节到位**：`font-variant-numeric: tabular-nums`、千分位、收入绿 / 支出红只给数字着色。
5. **聊天闭环清晰**：一句话 → AI 气泡 → 右侧草稿卡 → 修改 → 确认入库，路径短且可预期。
6. **动效克制**：`prefers-reduced-motion` 已做全局降级。

---

## 3. 问题清单（按优先级）

### P0 · 首屏观感，建议优先处理

#### P0-1 首屏被全局 «processing» 加载态污染

**现象（实测截图）**：页面顶部出现青绿色 loading 弧线 + 浏览器式进度文字 `processing | 7.1s`；右侧确认栏下方也残留一段加载文字；侧栏预算卡整体发灰半透明。

**原因**：
- [app.py](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/app.py#L320-L323) 首屏并发注册了 5 个 `demo.load`；
- [app.py](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/app.py#L364-L367) 又有一个 60 秒 `gr.Timer` 同时刷新 3 块数据；
- `refresh_banner` 未设置超时，其他部件用 3 秒超时，加载时间不一致；
- 所有事件都没有关闭 Gradio 的进度提示。

**建议**：
- 合并成一个 `refresh_shell()`，一次返回侧栏预算、今日概览、横幅与按钮可见性；
- 对 `demo.load` / `timer.tick` 统一加 `show_progress="hidden"`；
- 首屏先渲染静态骨架（Skeleton），不要让空组件参与 loading 降透明度；
- 定时刷新只刷新“横幅 + 预算”这类轻数据，不触发全页进度。

#### P0-2 页面没有撑满视口，下方大面积空白

**现象**：1440×1000 下，内容区在约 620px 处结束，剩余 380px 全是页面底色；侧栏却一直延伸到 1000px，左右高度不平衡。

**原因**：[style.css](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/assets/style.css#L1417-L1423) 的 `.fa-content-col` 没有最小高度；[chat_tab.py](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/ui/tabs/chat_tab.py#L432) 又把 Chatbot 固定为 `height=380`。

**建议**：
- 内容列设置 `min-height: calc(100vh - 40px)`；
- 对话页改成纵向 flex：对话卡 `flex:1`，Chatbot 高度跟随容器（`height:auto; min-height:340px`），而不是写死 380；
- 底部提示条固定在内容流末尾，而不是悬在中间。

#### P0-3 例句 chips 右侧被裁切

**现象**：第 5 个 chip「这个月花了多少」在卡片右边缘被截断，没有滚动提示。

**原因**：[style.css](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/assets/style.css#L1655-L1660) 使用 `flex-wrap: nowrap` + `overflow-x: auto`，但视觉上没有滚动条或渐隐提示。

**建议**：优先改成两行 `flex-wrap: wrap`；若坚持单行，至少在右侧加 24px 渐隐遮罩，并保留横向滚动。

#### P0-4 无预警时仍显示「✕」按钮，空横幅行占位

**现象**：首屏横幅为空，但右上角仍有一个孤立的「✕」，与「一键演示」并排，看起来像误触关闭按钮。

**原因**：[app.py](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/app.py#L231-L241) 中 `dismiss_btn` 默认可见，`refresh_banner` 的 outputs 只更新了横幅和「查看预算」，没有更新关闭按钮可见性。

**建议**：把 `dismiss_btn` 加入 `refresh_banner` 的 outputs，返回 `visible=bool(html)`；或者把横幅 + 关闭按钮包进同一个 Row，整体控制显隐。

#### P0-5 首屏预算卡始终显示「示范模式」提示

**现象**：即使后端正常，首帧仍显示 Mock 提示，用户会怀疑数据真实性。

**原因**：[app.py](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/app.py#L110-L121) 的 `initial_widgets()` 固定用 `mock.stats_summary` / `mock.budget_alerts` 并传入 `mock.NOTICE` 作为首帧内容。

**建议**：首帧只渲染「金额骨架 + 中性文字」，不显示 Mock 提示；待真实请求完成后再决定是否显示降级说明。

---

### P1 · 完成 P0 后继续优化

#### P1-1 预算状态直接显示英文 `normal / warning / over`

**证据**：[cards.py](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/ui/cards.py#L366) 直接把后端枚举值放进徽章。

**建议**：增加映射 `{"normal":"正常","warning":"预警","over":"超支"}`，颜色保持现有三态不变。

#### P1-2 用户界面暴露开发者文案

**现象**：统计页标题写「GET /stats/by-category · Plotly」，指标卡提示「GET /stats/summary」，预算清单写「GET /budgets」，演示页直接显示后端地址。

**建议**：面向用户改成人话（「按类别聚合」「仅统计已确认记录」）；接口信息放到调试面板或 `title` 属性里，默认不展示。

#### P1-3 聊天区白卡套白卡，层级偏弱

**现象**：外层对话卡是白底 + 阴影，AI 气泡又是白底 + 描边 + 阴影，边界靠双重阴影区分，略显“浮”。

**建议**：对话卡内部底色改为 `--fa-surface-2`（或极浅青灰），AI 气泡保持纯白；外层卡片去掉阴影只留 1px 边框，阴影留给真正需要抬升的元素（弹层、确认卡）。

#### P1-4 侧栏图标与角标不够“产品化”

- 导航图标使用 emoji（💬📊💰📒🎬），不同系统渲染差异大，且和文字同一行没有固定图标列；设计稿里要求的 20px 图标列并未真正实现。
- [style.css](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/assets/style.css#L1379-L1391) 中「预算中心」的红点角标写死 `content: "6"`，与实际预警数量无关。

**建议**：换成内联 SVG 图标（与加号/发送键同一套线性风格）；角标改成后端真实预警数，无数据时隐藏。

#### P1-5 表单与表格的可用性

- 统计月份、明细开始/结束日期都是裸 Textbox，用户必须记住 `YYYY-MM-DD` 格式；出错后才提示。
- 明细表格 `interactive=False`，点击整行载入编辑区，但行上没有 hover 指针 / 高亮，用户不知道可以点。
- 编辑区藏在默认收起的 Accordion 里，发现成本高。

**建议**：月份改 `Dropdown` 或月份选择器；日期加占位示例 + 失焦校验；给表格行加 `cursor:pointer` 与 hover 底色；载入行后自动展开编辑区并滚动到可见位置。

#### P1-6 无障碍与可读性

- 警示横幅文字 `#F5C26B` 压在 `#FEF3C7` 上，对比度约 1.9:1，远低于 4.5:1；超支横幅同理偏浅。
- 侧栏 Mock 提示、图表刻度、`fa-dash-notice` 等大量 10–11px 文字，投影场景下难读。
- 「＋」「🎤」「➤」「✕」按钮没有可读名称/提示。
- 除输入框外，大部分按钮没有自定义 `:focus-visible` 样式。

**建议**：警示文字改用 `#8A5A00` / `#B42323` 等深色墨水；正文不低于 12.5px，辅助文字不低于 11px；图标按钮补 `title` / `aria-label`；全局补 focus 环。

#### P1-7 图表细节与设计规范不一致

- [charts.py](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/ui/charts.py#L90) 趋势图填充色仍是旧蓝色 `rgba(47,107,255,0.10)`，与青绿主线冲突。
- 同一文件的调色板把暖黄 `#F5C26B`、红色 `#E05B5B` 分配给普通类别，违反“红黄只做语义”的既定规则。
- 空图表 `add_annotation` 未显式指定 `xref="paper" / yref="paper" / x=0.5 / y=0.5`，空态文案可能偏到左下角。
- 饼图外置标签在窄容器里容易互相挤压或被裁切。

**建议**：填充色改 `rgba(20,184,166,0.10)`；类别色只取青绿 + 中性灰；空态注解显式居中；窄屏饼图改图例或内置标签。

#### P1-8 HTML 拼接未转义，存在注入风险

**证据**：[cards.py](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/ui/cards.py#L213-L280) 将 `merchant`、`note` 等字段直接拼进 `gr.HTML`；[alerts.py](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/ui/alerts.py#L37-L54) 拼接类别名。OCR / 手工输入的内容可能包含 `<`、`>`。

**建议**：所有动态文本经 `html.escape()` 后再拼接，或改用 Gradio 原生组件承载用户内容。

---

### P2 · 工程与长期维护

#### P2-1 CSS 债务

- `.fa-section-title::before` 定义了两次（8px 与 6px），`.fa-banner`、`.fa-voice-panel` 也被重复覆盖；
- 大量 `!important` 用来对抗 Gradio 默认样式，升级 Gradio 时容易连锁失效；
- `.fa-topbar` / `.fa-segmented` / `.fa-bell-btn` / `.fa-header` 等规则已无组件使用。

**建议**：按“令牌 → 基础组件 → 页面区块 → 响应式”重排一次，删除确认无引用的规则；`!important` 只保留在跨 Gradio 内部结构的选择器上。

#### P2-2 响应式只在 900px 做了粗断点

900px 时侧栏收成 64px，但按钮仍渲染 11px 文字（[style.css](file:///c:/Users/Administrator/Desktop/智能体记账/frontend/assets/style.css#L1453-L1462)），图标 + 文字会拥挤。建议在 900px 以下真正切图标模式（隐藏文字或只留图标 + tooltip），并在 375 / 768 / 1024 / 1440 四档实测。

#### P2-3 未使用代码

`cards.header()`、`cards.footer_note()`、`charts.py` 尾部约 120 行 ECharts 遗留实现当前均未被引用。建议移到 `legacy/` 或删除，避免后来者误用。

#### P2-4 空状态与首次引导

首次进入只有一条欢迎气泡，用户不一定知道「右侧会出确认卡」。建议在空对话时提供 2–3 个带图标的操作卡（记一笔 / 拍小票 / 问本月花费），比纯文字 chips 更有引导性。

---

## 4. 建议的首屏目标布局

```text
┌──────────┬──────────────────────────────────────────────┬──────────────┐
│ 品牌      │  页面标题 / 面包屑            [一键演示] [🔔] │              │
│ 预算小卡  ├──────────────────────────────────────────────┤  草稿确认卡   │
│          │                                              │  ┌────────┐  │
│ 导航      │  对话卡（占满剩余高度）                        │  │ 金额    │  │
│          │   ┌──────────────────────────────┐           │  │ 字段    │  │
│          │   │ 气泡区 flex:1                │           │  │ 按钮    │  │
│          │   ├──────────────────────────────┤           │  └────────┘  │
│          │   │ 例句 chips（可换行）          │           │  今日概览     │
│          │   ├──────────────────────────────┤           │              │
│          │   │ 输入栏                        │           │              │
│          │   └──────────────────────────────┘           │              │
│ 账户      │  提示条（随内容流，不悬空）                    │              │
└──────────┴──────────────────────────────────────────────┴──────────────┘
```

关键点：
- 中间对话卡与右侧确认栏顶部对齐、底部对齐；
- 对话卡吃掉所有剩余高度，不再固定 380px；
- 顶部只保留一个真正的页面标题区，避免“侧栏品牌 + 顶栏 + 卡头”三套标题；
- 横幅出现时才占据高度，且关闭按钮与横幅同生共死。

---

## 5. 分阶段落地建议

| 阶段 | 目标 | 包含项 |
|---|---|---|
| 第一步 · 首屏修复 | 打开就“像一个成品” | P0-1 ~ P0-5 |
| 第二步 · 可读性 | 用户看得懂、点得到 | P1-1、P1-2、P1-4、P1-5、P1-6 |
| 第三步 · 视觉精修 | 统一质感与图表规范 | P1-3、P1-7、P2-4 |
| 第四步 · 工程清理 | 降低后续改版成本 | P1-8、P2-1、P2-2、P2-3 |

---

## 6. 可直接复制的修复片段

### 6.1 合并首屏刷新并隐藏进度条

```python
# app.py
def refresh_shell(dismissed: set):
    month = date.today().strftime("%Y-%m")
    banner_items, banner_notice = _fetch_alerts()
    banner = alerts.banner_html(banner_items, dismissed, banner_notice)
    side = refresh_dashboard()
    today = refresh_today()
    return (
        banner,
        banner_items,
        gr.update(visible=bool(banner)),   # dismiss_btn
        gr.update(visible=bool(banner)),   # goto_budget_btn
        side,
        today,
    )

demo.load(
    refresh_shell,
    inputs=[dismissed_state],
    outputs=[banner, alerts_state, dismiss_btn, goto_budget_btn, side_budget, chat_handles["today_overview"]],
    show_progress="hidden",
)
```

`refresh_banner` 里的 `api.budget_alerts(month)` 建议也加上 `timeout=_WIDGET_TIMEOUT`，与侧栏保持一致。

### 6.2 让内容区撑满视口

```css
.fa-content-col {
    min-height: calc(100vh - 40px);
}

.fa-chat-row {
    flex: 1 1 auto !important;
    min-height: 0 !important;
}

.fa-chat-row > .fa-panel {
    display: flex !important;
    flex-direction: column !important;
    min-height: 0 !important;
}

.fa-chat {
    flex: 1 1 auto !important;
    height: auto !important;
    min-height: 340px !important;
}
```

同时移除 `gr.Chatbot(height=380)`，避免内联高度和 CSS 打架。

### 6.3 例句 chips 改为可换行

```css
.fa-example-chips {
    flex-wrap: wrap !important;
    overflow-x: visible !important;
}
```

### 6.4 预算状态中文化

```python
_STATUS_TEXT = {"normal": "正常", "warning": "预警", "over": "超支"}

badge_text = _STATUS_TEXT.get(status, status)
```

### 6.5 警示色对比度

```css
.fa-banner.is-warning {
    color: #8A5A00 !important;
}

.fa-banner.is-over {
    color: #B42323 !important;
}
```

### 6.6 图表配色与空态

```python
fillcolor="rgba(20,184,166,0.10)"

fig.add_annotation(
    text=text,
    xref="paper", yref="paper", x=0.5, y=0.5,
    showarrow=False,
    font={"size": 14, "color": _TEXT_2},
)
```

### 6.7 动态文本转义

```python
from html import escape

f'<span class="fa-field-value">{escape(str(fields.get("merchant") or "—"))}</span>'
```

---

## 7. 验收清单

- [ ] 1440×1000 首屏不出现 `processing` 文字或全局进度条，60 秒定时刷新也不闪。
- [ ] 无预警时右上角没有孤立「✕」；有预警时「✕」与横幅同排且可点。
- [ ] 内容区底部与侧栏底部大致齐平，首屏无超过 100px 的无意义空白。
- [ ] 5 个例句 chip 完整可见，不被卡片边缘裁切。
- [ ] 首帧不出现「示范模式」提示（后端正常时）。
- [ ] 预算页徽章显示「正常 / 预警 / 超支」，不再出现英文枚举。
- [ ] 统计 / 预算 / 演示页不出现 `GET /...`、`Plotly` 等开发者文案。
- [ ] 警示横幅文字对比度 ≥ 4.5:1；辅助文字不小于 11px。
- [ ] 趋势图填充为青绿，不使用旧蓝色；空图表文案居中。
- [ ] 375 / 768 / 1024 / 1440 四档无横向滚动、无控件重叠。

---

## 8. 不建议做的

- 不要为了“丰富”再加一套顶栏或第二种主色；当前单色系是优势。
- 不要给每张卡片都加更大的阴影；层级应该靠底色、描边和留白，而不是阴影堆叠。
- 不要在首屏堆更多统计卡；用户来这里的第一目标是“记一笔”，预算是辅助信息。
- 不要继续用 `!important` 打补丁；后续每加一个组件都会更难维护。

---

## 9. 最后一句话

这套 UI 的“设计语言”已经完成了 80%，真正拖后腿的是**首屏那几秒的加载状态、纵向空间分配和工程化的产品文案**。先把 P0 四项修掉，页面质感会从“能用的 Demo”变成“可以交付的产品界面”。
