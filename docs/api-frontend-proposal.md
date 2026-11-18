# 前端接口对齐说明（v1.1 提议稿）

> 提出人：林丹苗（前端）
> 依据：`docs/api.md`（v1.0）+《项目方案设计文档》§5
> 状态：**待后端确认，确认后请更新 `docs/api.md` 并在群内公告冻结**
> 关联：`docs/api.md`、`frontend/config.py`

## 0. 结论摘要

前端核对现有契约后，需要处理两类问题，请在 Day 3（11/18）联调前定稿：

1. **既有接口返回结构偏简**：`/records/parse` 缺少草稿包装字段，`/query` 缺少分组表格，`POST /records` 在 `main.py` 中尚未实现。
2. **接口尚未纳入契约**：明细查询/修改/删除、统计、预算、类别、演示数据共 8 个接口缺失，影响 Day 4–6 开发。

前端已按本文件契约先行开发，后端接口就绪前用本地 Mock 数据自测，不阻塞进度。

## 1. 现状对照

| 接口 | `docs/api.md` v1.0 | 后端 `main.py` | 前端需要 |
|---|---|---|---|
| `POST /records/parse` | 扁平返回 `{amount, category, occurred_at}` | 已实现（Mock） | 草稿包装结构（§2.1） |
| `POST /records` | 已定义 | **未实现** | 确认入库（§2.2） |
| `POST /query` | `answer_text` + `total` | 已实现（Mock） | 增加 `slots`、`table`（§2.3） |
| `GET /health` | 已定义 | 已实现 | 无调整 |
| `GET/PUT/DELETE /records` | 未定义 | 未实现 | §3.1、§3.2 |
| `/stats/*`、`/budgets*`、`/categories`、`/demo/*` | 未定义 | 未实现 | §3.3–§3.6 |

## 2. 需要调整的既有接口

### 2.1 `POST /api/v1/records/parse`

补充草稿包装结构（前端确认卡与澄清反问的核心依赖）。

```json
// 请求
{ "text": "昨天打车32块", "session_id": "s_abc123" }

// 响应
{ "code": 0, "message": "ok", "data": {
    "draft_id": "d_001",
    "fields": { "amount": 32.0, "category": "交通", "merchant": null,
                "occurred_at": "2026-11-14", "note": null },
    "confidence": 0.92,
    "missing_fields": ["merchant"],
    "clarify_question": null
} }
```

约定：

- `clarify_question` 非空时，前端只渲染反问气泡，**不渲染确认卡**，并携带同一 `session_id` 继续下一轮；槽位补齐后该字段置 `null` 再返回草稿。
- `confidence` 用于确认卡展示可信度；`draft_id` 用于确认入库时回溯草稿。
- 入参增加 `session_id`，用于多轮澄清拼接上下文。
- 现有扁平结构 `{amount, category, occurred_at}` 无法支撑「反问澄清」与「确认/修改后入库」两条核心交互。

### 2.2 `POST /api/v1/records`

确认入库；文档已定义，`main.py` 尚未实现，当前调用会返回 404。

```json
// 请求（可带用户在确认卡上的修正值）
{ "draft_id": "d_001", "amount": 32.0, "category": "交通", "merchant": null,
  "occurred_at": "2026-11-14", "note": null, "raw_text": "昨天打车32块", "source": "text" }

// 响应
{ "code": 0, "message": "ok", "data": { "id": 101, "confirmed": 1 } }
```

### 2.3 `POST /api/v1/query`

建议保留分组表格数据，前端只展示 `answer_text` 与 `table`，不做任何计算。

```json
{ "code": 0, "message": "ok", "data": {
    "slots": { "time_range": ["2026-10-01", "2026-10-31"],
               "categories": ["餐饮"], "agg": "sum", "group_by": null },
    "answer_text": "你 10 月餐饮共支出 ¥1,286.50，共 42 笔。",
    "table": [ { "category": "餐饮", "total": 1286.5, "count": 42 } ]
} }
```

`table` 为空数组时前端自动隐藏表格区域。

## 3. 需要新增的接口

### 3.1 `GET /api/v1/records`

```
GET /api/v1/records?start=2026-11-01&end=2026-11-30&category=餐饮&page=1&size=10
```

```json
{ "code": 0, "message": "ok", "data": {
    "items": [ { "id": 101, "amount": 32.0, "category": "交通", "merchant": null,
                 "occurred_at": "2026-11-14", "note": null, "source": "text",
                 "confirmed": 1, "created_at": "2026-11-14 20:11:03" } ],
    "total": 128, "page": 1, "size": 10, "pages": 13
} }
```

待确认项：

- 默认值：前端暂按 `page=1`、`size=10` 实现，`size` 可选 10 / 20 / 50，请与后端默认值对齐。
- `start` / `end` 含首尾，格式 `YYYY-MM-DD`；`category` 省略表示全部。
- 草稿（`confirmed=0`）与已确认记录是否需要默认过滤，请明确（前端需要在表格中区分展示）。

### 3.2 `PUT /api/v1/records/{id}` / `DELETE /api/v1/records/{id}`

- `PUT`：可修改 `amount / category / merchant / occurred_at / note`，返回更新后的记录对象。
- `DELETE`：返回 `data: {"deleted": true}`；id 不存在返回 `1002`。

### 3.3 统计接口

```
GET /stats/summary?month=2026-11
  data: { "month": "2026-11", "total": 3280.5, "count": 46, "daily_avg": 218.7 }
  // daily_avg = total ÷ 当月已过天数，由后端按服务器日期计算

GET /stats/by-category?month=2026-11      // 也支持 start=&end=
  data: { "items": [ { "category": "餐饮", "total": 1286.5, "count": 42, "ratio": 0.39 } ] }

GET /stats/trend?days=30
  data: { "items": [ { "date": "2026-11-01", "total": 128.0, "count": 3 } ] }
```

统计口径请明确：**仅统计 `confirmed=1`** 的记录，草稿不计入。

### 3.4 预算接口

```
POST /budgets   { "month": "2026-11", "category": "餐饮", "amount": 1500 }   // category 为 null 表示总额预算
                data: { "id": 7, "month": "2026-11", "category": "餐饮", "amount": 1500 }

GET  /budgets?month=2026-11
                data: { "items": [ { "id": 7, "month": "2026-11", "category": "餐饮", "amount": 1500 } ] }

GET  /budgets/alerts?month=2026-11
                data: { "items": [ { "category": "餐饮", "amount": 1500, "used": 1240,
                                     "used_ratio": 0.83, "status": "warning" } ] }
```

- `status` 固定枚举 `normal / warning / over`：`used_ratio` ≥ 0.8 为 `warning`，≥ 1.0 为 `over`。
- 前端仅按状态映射进度条颜色与提醒文案，不参与阈值判断。

### 3.5 类别枚举

```
GET /categories
  data: { "items": ["餐饮", "交通", "购物", "居住", "娱乐", "医疗", "教育", "其他"] }
```

### 3.6 演示数据

```
POST /demo/load
  data: { "records": 60, "months": 2, "receipts": 3 }

POST /demo/reset
  data: { "deleted_records": 60, "deleted_budgets": 3 }
```

## 4. 字段细节待确认

1. `occurred_at` 精度：文本记账只需日期，小票需时分（如 `2026-11-14 14:30`）。建议统一为 `YYYY-MM-DD HH:MM`，前端按原样展示；请确认是否接受纯日期入参。
2. 金额统一为正数支出，前端仅做 `¥` 展示；单位换算（「3k」「三十二块」）由后端完成。
3. 分类必须落在固定 8 类内，映射失败落 `其他`，不自造类别。

## 5. 错误码与响应约定（沿用现有）

| code | 含义 | 前端处理 |
|---|---|---|
| 0 | 成功 | 正常渲染 |
| 1001 | 参数错误 | 提示气泡展示 `message` |
| 1002 | 资源不存在 | 提示气泡 + 引导刷新 |
| 2001 | LLM 调用失败 | 提示气泡，允许重试 |
| 2002 | OCR 失败 | 提示气泡，引导换图 |

前端统一解包 `{code, message, data}`，`code != 0` 时以提示气泡展示 `message`，请勿返回裸 HTTP 错误体。

## 6. 联调时间点（与《前端一周任务清单》对齐）

| 接口 | 前端需要时间 |
|---|---|
| `/records/parse`（草稿结构）、`POST /records` | 周三 11/18 前 |
| `GET / PUT / DELETE /records` | 周四 11/19 前 |
| `/stats/summary`、`/stats/by-category`、`/stats/trend` | 周五 11/20 前 |
| `/budgets`、`/budgets/alerts`、`/categories`、`/demo/*` | 周六 11/21 前 |

## 7. 确认事项

- [ ] 同意按本文件补全 `docs/api.md`（升级至 v1.1）并冻结
- [ ] 确认 §2 三处既有接口的结构调整
- [ ] 确认 §3 新增接口字段与默认值（分页默认值、统计口径、预算状态枚举）
- [ ] 确认 §4 的 `occurred_at` 精度
- [ ] 确认 §6 联调时间点是否可满足
