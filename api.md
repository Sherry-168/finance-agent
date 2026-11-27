# 前后端接口契约 (v1.2)

> 维护：史雅萱（后端）、林丹苗（前端）
> 冻结日期：2026-11-16（v1.2 增量：2026-11-25）
> 变更原则：本文件为**唯一契约来源**，任何字段变更必须先改本文件并在群内公告，再改代码。
> 实现状态标记：`【已实现】` / `【待修正】`（代码与本文不一致）/ `【待实现】`

## 0. 变更记录

| 版本 | 日期 | 变更内容 |
|---|---|---|
| v1.0 | 2026-11-15 | 初版：parse / records(POST) / query / health |
| v1.1 | 2026-11-16 | `/records/parse` 改为草稿包装结构（`draft_id`/`fields`/`confidence`/`missing_fields`/`clarify_question`），入参增加 `session_id`；`/query` 增加 `table`、`slots`；补全明细 CRUD、统计、预算、类别、演示数据接口定义 |
| v1.2 | 2026-11-25 | 第二周增量：新增 `POST /voice`（语音录入，§12）与 `GET /alerts`（主动提醒横幅，§11）；`POST /records/ocr` 由占位升级为多笔 `drafts[]` 实现；错误码新增 `2003`；`POST /records` 响应新增 `unread_alerts`；`/alerts` 支持已读关闭 |

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
| 2003 | 语音识别失败（ASR 未配置 / 云端异常 / 没听清，提示改用文本输入） |

- 前端统一解包：`code != 0` 时以提示气泡展示 `message`，不允许散落到各页面单独判断。
- 金额 `amount`：浮点数，**统一记正数支出**，前端展示加 `¥`；单位换算（「3k」「三十二块」）由后端完成。
- **金额单位（重要）**：对外接口统一使用**元**（浮点，保留两位小数）。后端/数据库内部可用「分」（整数）存储，但**必须在返回前转换为元**；入库接口（`POST /records`、`PUT /records/{id}`）接收的也是元。前端不做任何单位换算，只做 `¥` 与千分位格式化。
- 占比/使用率 `ratio`、`used_ratio`：0~1 小数（0.83 表示 83%），与金额单位无关。
- 时间 `occurred_at`：`YYYY-MM-DD`；需要时分的场景（小票）允许 `YYYY-MM-DD HH:MM`，前端按原样展示。
- 类别 `category`：必须是固定 8 类之一，映射失败落 `其他`。

## 2. 记账相关

### 2.1 自然语言解析为草稿 `【已实现】`

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

### 2.2 确认入库 `【已实现】`

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
{ "code": 0, "message": "ok", "data": { "id": 101, "confirmed": 1, "unread_alerts": 1 } }
```

- `amount` / `category` / `occurred_at` / `raw_text` **必填**；`merchant` / `note` 可空。
- 可选透传 `draft_id`、`source`（`text`/`ocr`/`voice`/`manual`/`demo`），`source` 会写入 `records.source`。
- `unread_alerts`（v1.2 新增）：入库后后端自动扫过预算 / 异常巡检，这里直接回最新未读数，
  前端确认成功后即可点亮顶部横幅，不必等下一次轮询。

### 2.3 小票 OCR（多笔拆单）`【已实现】`

**POST** `/records/ocr`，`multipart/form-data`，字段名 `file`（png / jpg / webp，≤ `MAX_UPLOAD_MB`）。

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

- 长截图 / 多商品小票返回多条 `drafts`，每笔一张确认卡，用户可勾选部分逐条调 `POST /records`。
- 识别不到金额的行（合计 / 优惠 / 找零）会被丢弃，不会生成空确认卡。
- `ocr_engine`：`vision_api`（视觉模型）/ `dify`（Dify 多模态工作流）。
- 引擎未配置或识别失败返回 `2002`；失败时 `data.raw_text` 尽可能带回原文，前端可引导用户复制到文本框继续记账。

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

## 3. 自然语言查账 `【已实现】`

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
- 实现进度（2026-11-18）：槽位抽取（`logic/query_parser.extract_slots`）+ 真实聚合已接入，`answer_text` 与 `table` 均由数据库计算得出；LLM 不参与算数，仅在有 Key 时辅助解析。

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
{ "code": 0, "message": "ok", "data": { "deleted_records": 60, "deleted_budgets": 3, "deleted_notifications": 2 } }
```

> `deleted_notifications` 为本轮新增：重置会连同提醒横幅一起清空，避免旧「已读」记录让重新演示时同 key 提醒无法再次弹出。

## 8. 健康检查 `【已实现】`

**GET** `/health`

```json
{ "code": 0, "message": "ok", "data": "Backend is running" }
```

## 9. 实现状态总览

| 接口 | 状态 | 备注 |
|---|---|---|
| `POST /records/parse` | 已实现 | 解析接缝：`LLM_PROVIDER` 可切 `openai` / `dify`，无 Key 走规则兜底；缺金额/时间返回 `clarify_question` |
| `POST /records` | 已实现 | 真正落库，返回自增 id（`raw_text` 必填）；入库后自动扫描提醒并回 `unread_alerts` |
| `POST /query` | 已实现 | 槽位抽取 + 真实聚合；时间/类别解析不到时兜底「本月」并回显 `slots` |
| `GET /records` | 已实现 | 分页 + 时间/类别筛选，金额按「元」返回 |
| `PUT /records/{id}` | 已实现 | 只更新传入字段；不存在返回 1002 |
| `DELETE /records/{id}` | 已实现 | 物理删除；不存在返回 1002 |
| `GET /stats/summary` | 已实现 | 日均分母按当月已过天数计算（历史月取整月） |
| `GET /stats/by-category` | 已实现 | ratio 0~1 两位小数，按金额降序 |
| `GET /stats/trend` | 已实现 | days 1~90，无消费日期补 0 |
| `POST /budgets` | 已实现 | 同月同维度覆盖；非法月份/类别返回 1001 |
| `GET /budgets` | 已实现 | `category=null` 为总额预算 |
| `GET /budgets/alerts` | 已实现 | **算**出来的实时使用率（进度条用），状态由后端判定（0.8 预警 / 1.0 超支） |
| `GET /categories` | 已实现 | 直接读词典文件，不受库状态影响 |
| `POST /demo/load` | 已实现 | 幂等：已有演示数据不重复导入；同时布置 4 条演示预算 |
| `POST /demo/reset` | 已实现 | 清空该用户流水与预算，返回删除条数 |
| `POST /records/ocr` | 已实现 | 视觉模型 / Dify 多模态 → 多笔 `drafts[]`；未配置返回 2002 |
| `GET /alerts` | 已实现 | **读** notifications 表（横幅数据源），拉取时事件驱动补扫 |
| `POST /alerts/{id}/read` | 已实现 | 关闭单条横幅；重复扫描不会把它刷回未读 |
| `POST /alerts/read-all` | 已实现 | 全部关闭 |
| `POST /voice` | 已实现 | 音频 → 云端 ASR → 文本 → 草稿（可选 `auto_commit`） |
| `GET /voice/status` | 已实现 | 语音能力探测：`available` / `engine` |
| `GET /health` | 已实现 | 前后端连通性检查 |

## 10. 固定分类字典（严禁修改）

餐饮、交通、购物、居住、娱乐、医疗、教育、其他

## 11. 语音录入 `【已实现】`（第二周新增）

**POST** `/voice`，`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | 文件 | 是 | 音频（wav / mp3 / m4a / aac / ogg / webm / amr / flac），≤ `MAX_UPLOAD_MB` |
| `session_id` | 文本 | 否 | 澄清反问的会话标识，原样回显 |
| `auto_commit` | 布尔 | 否 | 默认 `false`。`true` 且槽位齐全时直接入库（演示用） |

```json
// 响应（默认只出草稿，不入库）
{ "code": 0, "message": "ok", "data": {
    "transcript": "昨天打车 32 块",
    "asr_engine": "cloud",
    "session_id": "s_abc123",
    "record_id": null,
    "draft_id": "d_f61b7f8e",
    "fields": { "amount": 32.0, "category": "交通", "merchant": null,
                "occurred_at": "2026-11-24", "note": null },
    "confidence": 0.9,
    "missing_fields": [],
    "clarify_question": null
} }
```

约定：

- `fields` / `missing_fields` / `clarify_question` 与 §2.1 **完全同构**，前端复用同一套确认卡渲染。
- `asr_engine`：`cloud`（云端转写）/ `agent`（李语琛的 `speech_to_text`）/ `mock`（离线演示）。
  `mock` 是明确的演示态，答辩时如实说明「当前未接真实 ASR」。
- `action` 字段（前端可按需读取）：
  - 不返回 / 缺省 → 正常草稿，渲染确认卡；
  - `"reject"` → 非记账 / 越界请求，只渲染 `clarify_question` 气泡；
  - `"clarify"` → `auto_commit=true` 但槽位不全，仍按反问处理；
  - `"committed"` → 已入库，此时 `record_id` 与 `confirmed=1` 有值。
- 识别失败返回 `2003`，`message` 是可直接展示的中文；前端据此提示「改用文本输入」。

**GET** `/voice/status`

```json
{ "code": 0, "message": "ok", "data": { "available": true, "engine": "cloud", "max_upload_mb": 10.0 } }
```

`available=false` 表示没配 `ASR_API_KEY`，前端应禁用录音按钮并保留文本输入作为降级方案。

## 12. 主动提醒 `【已实现】`（第二周新增）

数据来自 `notifications` 表：后端在「确认入库后」与「前端拉取时」各扫一次，
把预算警戒（≥80% 橙 / ≥100% 红）与异常巡检（单笔远超历史均值）写进去。

**GET** `/alerts?month=2026-11&unread_only=true&refresh=true`

```json
{ "code": 0, "message": "ok", "data": {
    "items": [ { "id": 1, "type": "budget_over", "category": "餐饮", "level": "danger",
                 "title": "餐饮已超支",
                 "message": "餐饮已支出 ¥120.00，超出预算 ¥100.00，请注意控制。",
                 "data": { "category": "餐饮", "limit_cents": 10000, "spent_cents": 12000,
                           "used_ratio": 1.2, "limit": 100.0, "used": 120.0, "month": "2026-11" },
                 "is_read": 0, "created_at": "2026-11-25 18:23:26" } ],
    "unread_count": 1,
    "month": "2026-11"
} }
```

- `level`：`warning`（橙）/ `danger`（红），前端只按它选颜色，不自己算阈值。
- `type`：`budget_warning` / `budget_over` / `anomaly`。
- `data` 同时提供「分」（`*_cents`）与「元」（`limit`/`used`/`amount`/`avg`）两种视图，
  前端无需换算；`data.month` 标明这条提醒属于哪个月。
- `refresh=true`（默认）会先补扫一次再返回；`refresh=false` 只读库，适合前端轮询。

**POST** `/alerts/{id}/read` → `{ "id": 1, "is_read": 1, "unread_count": 0 }`，id 不存在返回 `1002`。

**POST** `/alerts/read-all` → `{ "updated": 1, "unread_count": 0 }`。

去重口径（重要，避免「关掉又冒出来」）：同一个月里同一 `(type, category)` 只保留一行，
重复扫描只刷新文案与数字、**保留 `is_read`**；条件已消失的未读提醒会被清掉，
已读历史保留。换月后新提醒重新出现为未读。
