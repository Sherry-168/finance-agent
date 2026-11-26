# UI 页面优化进阶 · 设计系统（UI UX Pro Max 工作流产出）

> 生成方法：按 `nextlevelbuilder/ui-ux-pro-max-skill` 的工作流执行——
> **结构化输入 → 分层推理（产品/布局/风格/配色/字体/图表/UX）→ 输出可执行设计系统 → 反模式检查**。
> 仓库克隆时网络不可达，故依据其官方文档站与实战手册还原方法论后手工推理产出。
>
> 本项目不是 landing page，而是 **工具型仪表盘 + 对话工作台**，所以 skill 中的「Landing Pattern」域替换为「Dashboard / Workbench 布局域」。
> 现有 v2.2 色卡与布局是已验收基线，**本设计系统继承而非推翻它**，只补齐字体、动效、组件状态、图标策略、可访问性与反模式检查这些进阶维度。

---

## 0. 结构化输入（Skill Prompt 拆解）

| 维度 | 取值 | 依据 |
|---|---|---|
| Product | 个人记账 / 消费分析助手（Fintech-lite、数据工具） | `week2-plan.md` 选题 A，核心闭环「记账 → 查账 → 图表 → 提醒」 |
| Page | Dashboard + Chat 混合工作台（三栏：侧栏导航 / 对话主区 / 确认概览） | 当前 `app.py` 三段式布局 |
| Style | 克制专业（Neutral functional）+ 轻 Soft UI，数据清晰优先 | v2.2 色卡「单一主色系、高饱和 ≤5%」 |
| CTA | 确认入库、去记一笔、一键演示 | 草稿确认卡、空态跳转、演示按钮 |
| Tech stack | Gradio Blocks + 自定义 CSS（fa-* 类）+ Plotly | `theme.py`、`style.css`、`charts.py` |
| 约束 | 内网离线（系统字体，禁外链）、v2.2 令牌不改、900px 响应式、投影可读 | `theme.py:28` 注释、`week2-plan` 防翻车指南 |
| 目标用户 | 记账个人用户 + 评审/答辩场景（投影、评委机器无麦克风） | week2-plan 风险表 |

**BM25 风格 query（等价）**：`fintech personal-finance dashboard chat workbench neutral-functional soft-ui offline data-dense accessible`

---

## 1. 分层推理摘要

| 推理层 | 结论 | 理由 |
|---|---|---|
| 产业与目标 | Fintech-lite 工具；目标 = 快速记账 + 一眼看清预算压力 | 记账闭环是核心，提醒是加分项 |
| Layout pattern | Sidebar + Bento 数据卡 + 对话流（Workbench 三栏） | 高密度工具界面，侧栏常驻预算提醒；区别于营销 landing |
| Visual style | Neutral functional 为骨 + Soft UI 为皮（低对比柔和阴影、圆角 14/10） | 既有 v2.2 已落地该方向，保留可降风险 |
| Palette | 5 阶青绿主色 + 4 级中性 + 语义功能色（红/黄/绿只给数字与点） | v2.2 色卡，已验收 |
| Typography | 系统无衬线单一家族（SF Pro / PingFang / 微软雅黑），靠字号与字重分层 | 离线约束，禁 Google Fonts |
| Chart family | 饼图（分类占比）+ 折线（每日趋势）+ 环形（预算使用率） | 现有 `charts.py` 选型正确，保留 |
| Anti-pattern 过滤 | 见第 9 节清单 | 逐项可查 |

---

## 2. 设计系统 · 总览（Design System at a Glance）

```
Product    : 个人记账与消费分析助手（Fintech-lite）
Page       : Dashboard + Chat Workbench
Style      : Neutral functional + Soft UI Evolution（克制专业）
Layout     : 232px 侧栏 / flex:1 对话区 / 288px 确认栏；900px 折叠
Palette    : Deep teal → Teal 5 阶 + 中性 4 级 + 语义色点
Typography : 系统无衬线（离线），5 档字号 + 3 档字重
Spacing    : 4 的倍数（4/8/12/16/20/24）
Radius     : 14 卡片 / 10 控件 / 999 胶囊
Shadows    : 主色相低透明度两级
Charts     : Plotly 饼图 / 折线 / 环形（类别色与 chip 同源）
Motion     : 微交互 ≤200ms，尊重 prefers-reduced-motion
Icons      : 语义 emoji + 后续可替换 SVG，避免彩色 emoji 堆叠
A11y       : 对比度 ≥4.5:1、focus 可见、loading 骨架、hover 反馈
```

---

## 3. 配色系统（继承 v2.2，不改动色值）

### 3.1 Token 表（与 `style.css :root` 一一对应）

| 类别 | Token | 色值 | 用途 |
|---|---|---|---|
| 主色 1 | `--fa-deep` | `#0B3D38` | 侧栏渐变起点 |
| 主色 2 | `--fa-deep-2` | `#104A44` | 侧栏渐变终点、环内圆 |
| 主色 3 | `--fa-primary-dark` | `#0F9D8A` | 主按钮渐变深端、强调文字 |
| 主色 4 | `--fa-primary` | `#14B8A6` | 行动色、进度填充、焦点边框 |
| 主色 5 | `--fa-accent` | `#2DD4BF` | 激活圆点、Logo、进度起点（面积 ≤40px²） |
| 浅底 1 | `--fa-primary-soft` | `#EEFAF8` | 分段容器、聚焦外发光、解析芯片、金额块、提示条 |
| 浅底 2 | `--fa-tag-bg` | `#D7F2EE` | 例句 chip、字段标签底 |
| 页面底 | `--fa-bg` | `#F4F7F6` | 绿灰底，托起白卡 |
| 卡面 | `--fa-surface` | `#FFFFFF` | 纯白卡片 |
| 描边 | `--fa-border` | `#E5E9E8` | 分隔线 / 1px 描边 |
| 正文 | `--fa-ink` | `#1F2937` | 正文与金额 |
| 次级 | `--fa-muted` | `#6B7280` | 次级标签（白底对比 4.8:1） |
| 占位 | `--fa-muted-2` | `#9CA3AF` | 占位符 / 未填字段 |
| 侧栏文字 | `--fa-side-ink` / `--fa-side-muted` / `--fa-side-group` | `#E6F4F1` / `#9DC9C2` / `#7FB2AB` | 深底三级文字 |
| 语义色 | `--fa-over` / `--fa-income` / `--fa-warning` | `#E05B5B` / `#16A34A` / `#F5C26B` | 支出/收入/预警，**只给数字与点** |
| 待确认 | `--fa-warning-soft` + `--fa-pending-ink` | `#FEF3C7` + `#B45309` | 状态胶囊（唯一允许的高饱和面） |

### 3.2 三条色彩纪律（沿用 v2.2，进阶补充量化）

1. 单一主色系：所有绿色只取自 5 阶，禁止第二种绿（收入绿 `#16A34A` 是唯一例外，仅数字）。
2. 高饱和色（红/黄）总面积 ≤5%，只做点（圆点、数字、胶囊），不做区块。
3. 对比靠明度不靠色相；深底浅字、浅底深字，避免中间明度大面积铺色。
4. **进阶**：类别 chip 8 色与 `charts.py CHART_PALETTE` 同源，保证「图例 ↔ 卡片标签」视觉记忆一致。

---

## 4. 字体系统（Typography）

### 4.1 字体栈（离线安全，已在 `theme.py` 落地）

```
font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text",
             "PingFang SC", "Microsoft YaHei", "Noto Sans SC",
             "Segoe UI", sans-serif;
```

- **不引入 Google Fonts / 外链字体**：内网与评委机器可能无外网，外链字体会回退造成闪烁与不一致。
- 单一家族靠字号/字重/颜色分层，避免多字体搭配带来的离线风险。

### 4.2 字号阶梯（5 档，来自 v2.2 token）

| 档位 | 字号 | 用途 | 示例 |
|---|---|---|---|
| XL | 26px / 700 | 确认卡金额（唯一视觉焦点） | `¥32.00` |
| LG | 20px / 700 | 侧栏本月支出、金额块 | `¥6,091.03` |
| MD | 16px / 600 | 站名、区块标题 | `记账小助手` |
| SM | 14 / 13.5px / 500-600 | 正文、导航项、字段值 | `对话记账` |
| XS | 12.5 / 11px / 500 | 副标题、chip、面包屑、提示条 | `确认后才会入库` |

**进阶规则**：
- 正文不低于 12px；提示条正文 11.5px 是 v2.2 明确的特例（单行密集信息）。
- 行高：正文 1.6–1.75，标题 1.3–1.4；演示态投影正文放大到 ≥14.5px（`DEMO_STYLE_CSS`）。
- 数字统一 `font-variant-numeric: tabular-nums`，保证金额列对齐。

---

## 5. 间距与圆角（Spacing & Radius）

| 维度 | 取值 |
|---|---|
| 间距 | 仅 4 的倍数：4 / 8 / 12 / 16 / 20 / 24（`--s-1` ~ `--s-6`） |
| 圆角 | 14 卡片 / 10 控件 / 999 胶囊 |
| 三栏宽度 | 侧栏 232px（`flex:0 0 232px`）、确认栏 288px、主区 `flex:1` |
| 栏间距 | 16px |
| 内容区内边距 | 上 16 / 下 20 / 左右 24 |

**对齐规则**：
- 所有卡片内边距统一（确认卡、今日概览 16px）。
- 字段行 33px 高（9px 上下 padding + 13px 字），数据行 28px。
- 按钮高度 36px（控件档），演示态 ≥44px（投影档）。

---

## 6. 布局系统（Layout）

### 6.1 桌面三栏（>=900px）

```
┌──────────┬─────────────────────────────┬──────────┐
│ 侧栏 232 │ 主对话区 flex:1              │ 确认 288 │
│ 品牌      │ 区块头(12/18)                │ 草稿确认卡│
│ 预算+环   │ 气泡区(flex:1, pad20)        │ (gap12)  │
│ 导航三组  │ 快捷pills / 输入框            │ 今日概览  │
│ 账户(auto)│                             │          │
└──────────┴─────────────────────────────┴──────────┘
```

### 6.2 响应式

- 1280px 以下：先压缩中间对话区，确认栏保持 288px。
- 900px 以下：侧栏收 64px 图标栏、确认栏下移到对话区下方、栏间距 12px。

**进阶建议（未实施，仅记录）**：900px 侧栏图标栏建议用 `title`/`aria-label` 提供文字说明，避免纯图标无标签。

---

## 7. 组件系统（Components）

| 组件 | 规格 | 状态样式 |
|---|---|---|
| 按钮 | 高 36 / 圆角 10 / 主渐变 `#0F9D8A→#14B8A6` | hover 抬升 1px + 阴影加深；active 下沉；disabled 降透明 0.5 |
| 导航项 | 36px 高 / 9-12 padding / 激活右侧 6px `#2DD4BF` 圆点 | hover 半透明白 10%；激活半透明白 14% |
| 草稿确认卡 | 白底 / 14 圆角 / 16 padding / 金额 26px | 金额块浅底 `--fa-primary-soft`；类别彩色 chip；置信度小圆点 |
| 聊天气泡 | 最大宽 76% / 12-15 padding / 14 圆角单角 4px | 用户右深色渐变；AI 左白底描边 |
| 输入区 | 外边距 0/16/16 / 1.5px 边框 / 14 圆角 | focus 主色边框 + 3px `--fa-primary-soft` 外发光 |
| 类别 chip | 24px 高 / 999 圆角 / 8px 色点 + 类别名 | 8 类各自浅底，颜色同源图表 |
| 预算环 | 42px / conic-gradient / 环心百分比 | normal 青绿 / warning 暖黄 / over 红 |
| 横幅 | 顶部醒目 / 红(over) 橙(warning) | 已读关闭 + localStorage 持久化 |
| 空态 | 引导文案 + 可选跳转按钮 | 按钮渐变青绿，点击回对话页 |
| 图表容器 | Plotly / 白卡 / 14 圆角 | 空数据用 `empty_figure()` 文案占位 |

---

## 8. 动效与交互（Motion）

| 项 | 规则 |
|---|---|
| 时长 | 微交互 ≤200ms（hover 120ms、环渲染 400ms ease-out） |
| 反馈 | 所有可点击元素有 hover/active 反馈 |
| 转写回填 | 录音结束 → 回填输入框，不直接入库，用户可改后发送 |
| 预算刷新 | 保存预算后联动刷新侧栏环、横幅、今日概览（event.then） |
| Reduced motion | 进阶项：`@media (prefers-reduced-motion: reduce)` 关闭过渡动画（**待实施**） |
| 骨架屏 | 首帧用 `sidebar_budget_skeleton` / `today_overview_skeleton`，不用转圈 |

---

## 9. 图表与数据可视化（Charts）

| 图表 | 类型 | 库 | 选型理由 |
|---|---|---|---|
| 分类占比 | 饼图 | Plotly `go.Pie` | 类别少、看比例，<3% 合并「其他」 |
| 每日趋势 | 折线图 | Plotly `go.Scatter` | 时间序列，hover 显示金额+笔数 |
| 预算使用率 | 环形（侧栏 42px） | CSS conic-gradient | 常驻侧栏，一眼看压力 |

- 类别色与 chip 同源（skill 的「图表视觉记忆一致」规则）。
- hover 统一显示金额 + 笔数，避免只有数字无语义。
- 进阶：图表应补 `aria-label` / 文本替代（**待实施**，当前靠空态文案兜底）。

---

## 10. UX 规则与反模式检查（Anti-pattern Check）

### 10.1 已通过

| 检查项 | 状态 |
|---|---|
| 单一主色系，无第二种绿 | ✅ 收入绿仅数字例外 |
| 高饱和色只做点，面积 ≤5% | ✅ |
| 对比度 ≥4.5:1（主要文字） | ✅ `#1F2937`/`#6B7280` 白底达标 |
| 间距 4 的倍数、圆角三档 | ✅ |
| 按钮/卡片 hover 反馈 | ✅ |
| 加载态用骨架屏 | ✅ |
| 响应式 900px 折叠 | ✅ |
| 文本输入框始终可用（语音降级） | ✅ |
| 离线字体（无外链） | ✅ |

### 10.2 待实施 → 已实施（2026-11-26 落地）

| 缺口 | skill 规则依据 | 落地情况 |
|---|---|---|
| 图标策略混用 emoji | UX 指南「SVG icons, no emoji」 | ✅ 导航 5 项 + 顶部演示/预算/重试 + 空态跳转按钮全部改为 CSS mask 内联 SVG（`--nav-icon` / `--btn-icon`），图标随 `currentColor` 变化，无外链；分类色点保留 |
| `prefers-reduced-motion` | UX 指南「Respect reduced-motion」 | ✅ 媒体查询已存在（style.css），关闭所有 animation/transition |
| 图表无障碍 | Chart accessibility notes | ✅ 两个 `gr.Plot` 加 `elem_id`，配套 sr-only 文本摘要；饼图/折线 trace 加 `name` 元数据 |
| 焦点态可见性 | UX 指南「focus」 | ✅ 全局 `:focus-visible` 主色 2px outline（输入框除外，沿用专属外发光） |
| 空态跳转按钮文字 | 反模式「CTA 动词太弱」 | ✅ 保持「去记一笔 / 先去记一笔」强动词 |
| 暗色模式对比 | UX 指南「dark mode contrast」 | — 本项目为浅色工具，明确排除暗色模式（不实施） |

---

## 11. 与 v2.2 的关系

- **继承**：本设计系统完全保留 v2.2 的色卡、圆角、间距、三栏布局，不改动 `style.css` 既有令牌。
- **补充**：新增字体系统、动效规范、组件状态、图标策略、可访问性与反模式检查——这些是 skill 的进阶维度。
- **约束**：内网离线优先，字体不外链；评审投影可读性优先（演示态放大）。

---

## 12. 一句话总结

> 用 UI UX Pro Max 的推理框架重新审视后，本项目设计系统的判断是：
> **这是一款 Fintech-lite 工具型工作台，不是营销页——所以「数据清晰 > 视觉炫技」，
> 保持 v2.2 的青绿单一主色与三栏密度，把进阶投入放在字体层级、组件状态、动效克制与可访问性上。**
