# 前后端接口契约 (v1.1)

> 维护：史雅萱（后端）、林丹苗（前端）
> 冻结日期：2026-11-16
> 变更原则：本文件为**唯一契约来源**，任何字段变更必须先改本文件并在群内公告，再改代码。
> 实现状态标记：`【已实现】` / `【待修正】`（代码与本文不一致）/ `【待实现】`

## 0. 变更记录

| 版本 | 日期 | 变更内容 |
|---|---|---|
| v1.0 | 2026-11-15 | 初版：parse / records(POST) / query / health |
| v1.1 | 2026-11-16 | `/records/parse` 改为草稿包装结构（`draft_id`/`fields`/`confidence`/`missing_fields`/`clarify_question`），入参增加 `session_id`；`/query` 增加 `table`、`slots`；补全明细 CRUD、统计、预算、类别、演示数据接口定义 |

## 1. 基础规范

- Base URL：`http://localhost:8000/api/v1`（容器内可通过 `API_BASE_URL` 环境变量覆盖）
- 除 OCR 上传（`multipart/form-data`）外，均为 `application/json`
- 统一响应包装：

```json
{ "code": 0, "message": "ok", "data": { } }
```

- 错误码：

| code | 含义 |
|---|---|
| 0 | 成功 |
| 1001 | 参数错误 |
| 1002 | 资源不存在 |
| 2001 | LLM 调用失败 |
| 2002 | OCR 失败 |

- 前端统一解包：`code != 0` 时以提示气泡展示 `message`，不允许散落到各页面单独判断。
- 金额 `amount`：浮点数，**统一记正数支出**，前端展示加 `¥`；单位换算（「3k」「三十二块」）由后端完成。
- **金额单位（重要）**：对外接口统一使用**元**（浮点，保留两位小数）。后端/数据库内部可用「分」（整数）存储，但**必须在返回前转换为元**；入库接口（`POST /records`、`PUT /records/{id}`）接收的也是元。前端不做任何单位换算，只做 `¥` 与千分位格式化。
- 占比/使用率 `ratio`、`used_ratio`：0~1 小数（0.83 表示 83%），与金额单位无关。
- 时间 `occurred_at`：`YYYY-MM-DD`；需要时分的场景（小票）允许 `YYYY-MM-DD HH:MM`，前端按原样展示。
- 类别 `category`：必须是固定 8 类之一，映射失败落 `其他`。

## 2. 记账相关

### 2.1 自然语言解析为草稿 `【已实现·真实解析】`

**POST** `/records/parse`（**不入库**，只返回草稿）

```json
// 请求
{ "text": "昨天打车32块", "session_id": "s_abc123" }

// 响应
{ "code": 0, "message": "ok", "data": {
    "draft_id": "d_001",
    "fields": {
      "amount": 32.0,
      "category": "交通",
      "merchant": null,
      "occurred_at": "2026-11-14",
      "note": null
    },
    "confidence": 0.95,
    "missing_fields": [],
    "clarify_question": null
} }
```

约定：

- `clarify_question` 非空时，前端**只渲染 AI 反问气泡，不渲染确认卡**；用户补充后携带同一 `session_id` 继续请求，槽位齐全时该字段返回 `null` 并给出草稿。
- `missing_fields` 取值集合：`amount` / `category` / `occurred_at`（可扩展 `merchant`、`note`）。
- `confidence` 为 0~1 浮点数，前端展示为百分比。
- `draft_id` 用于确认入库时回溯草稿。

### 2.2 确认入库 `【已实现·真实落库】`

**POST** `/records`

```json
// 请求（可带用户在确认卡上的修正值）
{
  "amount": 32.0,
  "category": "交通",
  "merchant": null,
  "occurred_at": "2026-11-14",
  "note": null,
  "raw_text": "昨天打车32块"
}

// 响应
{ "code": 0, "message": "ok", "data": { "id": 101, "confirmed": 1 } }
```

- `amount` / `category` / `occurred_at` / `raw_text` **必填**；`merchant` / `note` 可空。
- 可选透传 `draft_id`、`source`（`text`/`ocr`/`manual`/`demo`），后端当前忽略，前端允许发送。

### 2.3 小票 OCR（第二周接入）`【接口就绪·识别待接入】`

**POST** `/records/ocr`，`multipart/form-data`，字段名 `file`。

```json
{ "code": 0, "message": "ok", "data": {
    "drafts": [ { "draft_id": "d_002",
      "fields": { "amount": 45.5, "category": "餐饮", "merchant": "瑞幸咖啡",
                  "occurred_at": "2026-11-14 14:30", "note": null },
      "confidence": 0.88, "missing_fields": [], "clarify_question": null } ],
    "ocr_engine": "vision_api",
    "raw_text": "..."
} }
```

多商品小票返回多条 `drafts`，用户可勾选部分入库（逐条调 `POST /records`）。

### 2.4 明细列表 `【已实现】`

**GET** `/records?start=&end=&category=&page=&size=`

- `start` / `end`：`YYYY-MM-DD`，含首尾；省略表示不限
- `category`：省略表示全部
- `page`：默认 `1`；`size`：默认 `10`，可选 `10/20/50`

```json
{ "code": 0, "message": "ok", "data": {
    "items": [ { "id": 101, "amount": 32.0, "category": "交通", "merchant": null,
                 "occurred_at": "2026-11-14", "note": null, "source": "text",
                 "confirmed": 1, "created_at": "2026-11-14 20:11:03" } ],
    "total": 128, "page": 1, "size": 10, "pages": 13
} }
```

`confirmed`：`0` 草稿 / `1` 已确认，前端表格中区分展示。

### 2.5 修正记录 `【已实现】`

**PUT** `/records/{id}`

```json
// 请求（按需传需要修改的字段）
{ "amount": 30.0, "category": "交通", "merchant": "滴滴", "occurred_at": "2026-11-14", "note": "夜间加价" }
```

响应返回更新后的记录对象；id 不存在返回 `1002`。

### 2.6 删除记录 `【已实现】`

**DELETE** `/records/{id}`

```json
{ "code": 0, "message": "ok", "data": { "deleted": true } }
```

id 不存在返回 `1002`；前端删除前需二次确认。

## 3. 自然语言查账 `【已实现·真实聚合】`

**POST** `/query`

```json
// 请求
{ "question": "我上个月吃饭花了多少？", "session_id": "s_abc123" }

// 响应
{ "code": 0, "message": "ok", "data": {
    "slots": { "time_range": ["2026-10-01", "2026-10-31"],
               "categories": ["餐饮"], "agg": "sum", "group_by": null },
    "answer_text": "你 10 月餐饮共支出 ¥1,286.50，共 42 笔。",
    "table": [ { "category": "餐饮", "total": 1286.5, "count": 42 } ]
} }
```

- `slots` 由 LLM 解析，`answer_text` 由后端模板拼数字生成，**LLM 不参与算数**。
- 前端只渲染 `answer_text` 与 `table`，`table` 为空时隐藏表格。
- 实现进度（2026-11-18）：槽位解析支持 LLM + 规则兜底，金额 / 笔数均由 DAO + `logic.stats` 真实聚合，`answer_text` 为后端模板拼真实数字；前端展示无需改动。

## 4. 统计 `【已实现】`

### 4.1 月度概览

**GET** `/stats/summary?month=2026-11`

```json
{ "code": 0, "message": "ok", "data": {
    "month": "2026-11", "total": 3280.5, "count": 46, "daily_avg": 218.7 } }
```

`daily_avg` = 总额 ÷ 当月已过天数，由后端计算。

### 4.2 类别占比

**GET** `/stats/by-category?month=2026-11`（也支持 `start=&end=`）

```json
{ "code": 0, "message": "ok", "data": {
    "items": [ { "category": "餐饮", "total": 1286.5, "count": 42, "ratio": 0.39 } ] } }
```

### 4.3 每日趋势

**GET** `/stats/trend?days=30`

```json
{ "code": 0, "message": "ok", "data": {
    "items": [ { "date": "2026-11-01", "total": 128.0, "count": 3 } ] } }
```

统计口径：**仅统计 `confirmed=1`** 的记录，草稿不计入。

## 5. 预算 `【已实现】`

### 5.1 设定预算

**POST** `/budgets`

```json
// 请求（category 为 null 表示总额预算）
{ "month": "2026-11", "category": "餐饮", "amount": 1500 }

// 响应
{ "code": 0, "message": "ok", "data": { "id": 7, "month": "2026-11", "category": "餐饮", "amount": 1500 } }
```

### 5.2 查询预算

**GET** `/budgets?month=2026-11`

```json
{ "code": 0, "message": "ok", "data": {
    "items": [ { "id": 7, "month": "2026-11", "category": "餐饮", "amount": 1500 } ] } }
```

### 5.3 预算预警

**GET** `/budgets/alerts?month=2026-11`

```json
{ "code": 0, "message": "ok", "data": {
    "items": [ { "category": "餐饮", "amount": 1500, "used": 1240,
                 "used_ratio": 0.83, "status": "warning" } ] } }
```

- `status`：`normal` / `warning`（`used_ratio` ≥ 0.8）/ `over`（`used_ratio` ≥ 1.0），判断由后端完成。
- `category` 为 `null` 表示总预算项。

## 6. 类别枚举 `【已实现】`

**GET** `/categories`

```json
{ "code": 0, "message": "ok", "data": { "items": ["餐饮", "交通", "购物", "居住", "娱乐", "医疗", "教育", "其他"] } }
```

## 7. 演示数据 `【已实现】`

**POST** `/demo/load`

```json
{ "code": 0, "message": "ok", "data": { "records": 60, "months": 2, "receipts": 3 } }
```

**POST** `/demo/reset`

```json
{ "code": 0, "message": "ok", "data": { "deleted_records": 60, "deleted_budgets": 3 } }
```

## 8. 健康检查 `【已实现】`

**GET** `/health`

```json
{ "code": 0, "message": "ok", "data": "Backend is running" }
```

## 9. 实现状态总览

| 接口 | 状态 | 备注 |
|---|---|---|
| `POST /records/parse` | 已实现 | 规则 + 可选 LLM 解析；缺槽位返回 `clarify_question` 并暂存会话 |
| `POST /records` | 已实现 | `raw_text` 必填；真实写入 records 表并返回自增 id |
| `POST /query` | 已实现 | 槽位解析 + DAO/stats 真实聚合；`answer_text` / `table` 均由后端生成 |
| `GET /records` | 已实现 | 时间 / 类别筛选 + 分页（金额单位为元） |
| `PUT /records/{id}` | 已实现 | 部分字段更新；不存在返回 1002 |
| `DELETE /records/{id}` | 已实现 | 不存在返回 1002 |
| `GET /stats/summary` | 已实现 | 仅 confirmed=1，日均按当月已过天数 |
| `GET /stats/by-category` | 已实现 | 支持 `month` 或 `start/end`，`ratio` 为 0~1 |
| `GET /stats/trend` | 已实现 | 近 N 天每日汇总，含 0 消费日 |
| `POST /budgets` | 已实现 | 同月同维度覆盖；`category=null` 表示总预算 |
| `GET /budgets` | 已实现 | 当月预算列表 |
| `GET /budgets/alerts` | 已实现 | 80% warning / 100% over 由后端判断 |
| `GET /categories` | 已实现 | 固定 8 类 |
| `POST /demo/load` | 已实现 | 两月共 60 条真实落库流水 + 三档预算，重复调用幂等 |
| `POST /demo/reset` | 已实现 | 清空当前用户的流水与预算 |
| `POST /records/ocr` | 接口就绪 | 当前返回 2002；第二周替换识别实现即可 |
| `GET /health` | 已实现 | 前后端连通性检查 |

> 2026-11-18 联调状态：上表除 OCR 识别算法（第二周范围）外全部接通，详见 `tests/test_api.py`。

## 10. 固定分类字典（严禁修改）

餐饮、交通、购物、居住、娱乐、医疗、教育、其他
