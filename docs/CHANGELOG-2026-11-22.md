# 改动清单 · 2026-11-22

> 基线：`main` @ `ea6e53a`（origin/main）
> 范围：按方案设计文档 + `docs/api.md` v1.1 对齐的核心修复，以及「记账对话」UI 重做。
> 验证：`pytest tests -q` → **63 passed**；浏览器实测 7860 前端 0 控制台报错。

---

## 一、核心规则与接口修复（后端）

### `app/adapters/parser.py`（+80 行）
- 新增 5 个正则：`_DATE_WEEK`（上/本/下周几）、`_DATE_MONTH_DAY_LABEL`（这个月/上月 N 号）、`_CN_DECIMAL`（两块五）、`_EXPENSE_HINT`（记账动词）、`_WEEKDAY_NUM`。
- `_extract_amount`：中文小数金额（`两块五 → 2.5`）优先于整数匹配，避免丢掉 0.5。
- `_extract_date`：
  - 「上周五」按**自然周**算上星期的周五，而非「往回最近的周五」。
  - 「这个月 1 号 / 上月 15 号 / 下月 3 日」按月份标签解析，不存在的日期（如 2 月 30 日）收敛到当月最后一天。
  - 修正跨年注释口径：补记过去账单时「1 月说 11 月 5 日 → 去年 11 月」。
- 新增 `_is_rejected()`：`parse_text()` 给非记账输入（灌水、天气写诗）打 `_rejected` 标记；缺金额但命中类别的输入仍走 clarify。

### `app/routers/records.py`（+19 行）
- `/records/parse` 增加 `_rejected` 分支：返回 `action: "reject"` + 引导文案的空草稿，不再返回 `code=0` 的空白草稿。

### `logic/query_parser.py`（+5 行）
- `resolve_time_range` 新增「前天 / 大前天」闭区间；`_TIME_PATTERNS` 补对应模式，查账问句可识别。

### `app/routers/demo.py`（+13 行）
- 演示数据优先读根目录 `demo_bills.csv`（60 笔 / 2 个月），缺失时回退旧 `data/sample_transactions.csv`，兼容 Excel BOM。

### `config/categories.json`（+4 行）
- 餐饮补「中午 / 牛肉面」，居住补「话费」（冻结 8 类无「通讯」，话费归缴费类）。

### `demo_parse_cases.json`（N3 用例）
- 「11 月 5 日交了话费 39 元」期望类别 `通讯 → 居住`，与冻结 8 类一致。

---

## 二、UI 重做（前端）

### `frontend/ui/tabs/chat_tab.py`（+86 / -66 行）
- `_DATE_RE` 允许 `YYYY-MM-DD HH:MM`（小票 OCR 草稿带时间，对齐契约 §2.2）。
- 底部输入栏重做：`＋ / 文本输入 / 语音占位 / 发送` 四元素；原来挤在 330px 里的 6 个元素（语音/扫描/删除）精简。
- 右侧扫描按钮换成**语音输入占位**（麦克风图标），点击提示「语音输入即将上线」；OCR 仍走 `＋` 菜单里的拍照/相册。
- 删除死代码 `scan_receipt()`，新增 `voice_placeholder()`。
- `＋` 菜单改为 **DeepSeek 风格弹出浮层**：标题 + 三个列表行（拍照识别 / 相册识别 / Excel 导入占位）+ 底部「清空对话与草稿」。
- 底部交互提示同步更新。

### `frontend/assets/style.css`（+476 / -大量 行）
- 剪掉 Gradio Chatbot 自带浮动标题/工具条的灰色描边；隐藏 `.panel-full-width` 内嵌层的重复 padding，修复「文字显示不全」。
- 气泡改柔和阴影 + 大圆角，用户侧品牌色渐变、AI 侧白底。
- 修复按钮选择器旧写法（`.fa-plus-btn button` 从未命中，class 在 `<button>` 自身）；图标全部改为内联 SVG data-URI，避免字体符号重叠。
- 修复输入框被 `<label>` 隐藏的旧问题（`display:block` + `font-size:0` 只隐藏默认文字）。
- 附件面板改为 DeepSeek 风格浮层：绝对定位到输入栏上方、圆形图标行、hover 变色、Excel 占位标签。
- 关键修复：`.fa-composer-wrap` 默认 `overflow:hidden` 会把浮层整个裁掉 → 改为 `overflow:visible`，菜单才真正可见可点。
- 发送图标换成**纸飞机**，按用户要求整体逆时针旋转 90°（尖头朝上）。

---

## 三、回归测试

- `tests/test_parser_rules.py`（+39）：相对周、带标签月日、跨年、中文小数、reject、类别关键词。
- `tests/test_query_parser.py`（+12）：前天 / 大前天时间区间。
- `tests/test_query_slots.py`（+6）：前天槽位解析。

---

## 四、文档

- `README.md`：演示数据 15 → 60 条、测试数 50 → 63 passed。

---

## 验证汇总

| 项 | 结果 |
|---|---|
| `pytest tests -q` | 63 passed |
| `demo_parse_cases.json` 回放 | 20 / 20 通过 |
| `/demo/load` 端到端 | `records=60, months=2, receipts=0` |
| 浏览器（7860） | 输入框可聚焦、菜单浮层可见可点、0 控制台报错 |
