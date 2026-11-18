# 数据库与规则设计文档（数据层 · 蔡适伶）

> 金额决策、接口字段、时间约定若变更，需在群内公告。

---

## 1. 核心约定

1. **金额存「分」整数**：存储层用 `amount_cents`（INTEGER，单位分），接口层仍用「元」。  
   换算由 DAO 完成，前端与 LLM 无感知，SQL 聚合全整数，杜绝浮点误差。
2. **LLM 不参与算术**：LLM 只输出槽位（金额原文、类别名、时间描述等），  
   单位换算（「3k」「三十二块」）、SUM/COUNT、预算比较全部由本层代码完成。
3. **时间统一 TEXT**：格式 `YYYY-MM-DD HH:MM:SS`，字符串比较即时间比较。
4. **时间区间左闭右开 `[start, end)`**：`end` 为次日 / 下月 1 日零点，  
   避免 DATETIME 含时分秒时右闭漏掉当天记录（队长 §5.2 示例里的 `06-30` 仅作示意）。

---

## 2. 表结构

SQLite，文件 `data/finance.db`（Docker 挂载卷持久化）。完整 DDL 见 `db/schema.sql`。

### records（消费记录，核心表）

| 字段           | 类型         | 说明                                           |
| ------------ | ---------- | -------------------------------------------- |
| id           | INTEGER PK | 自增                                           |
| user_id      | TEXT       | 默认 `demo_user`（单用户简化，留扩展口）                   |
| amount_cents | INTEGER    | 金额，单位「分」，CHECK > 0                           |
| category     | TEXT       | 类别名（8 类之一）                                   |
| merchant     | TEXT       | 商户                                           |
| occurred_at  | TEXT       | 消费时间（≠ 记账时间）                                 |
| source       | TEXT       | `text` / `ocr` / `voice` / `manual` / `demo` |
| raw_text     | TEXT       | 用户原始输入 / OCR 原文                              |
| note         | TEXT       | 备注                                           |
| confirmed    | INTEGER    | 0 草稿 / 1 已确认，默认 0                            |
| created_at   | TEXT       | 记账时间                                         |

索引：`(user_id, occurred_at)`、`(user_id, category)`。

### categories（类别，8 类）

| 字段       | 类型      | 说明                                    |
| -------- | ------- | ------------------------------------- |
| name     | TEXT PK | 餐饮 / 交通 / 购物 / 居住 / 娱乐 / 医疗 / 教育 / 其他 |
| keywords | TEXT    | 逗号分隔关键词，规则分类兜底用                       |

### budgets（预算）

| 字段           | 类型      | 说明             |
| ------------ | ------- | -------------- |
| user_id      | TEXT    | 默认 `demo_user` |
| category     | TEXT    | 空串 `''` 表示总预算  |
| month        | TEXT    | `YYYY-MM`      |
| amount_cents | INTEGER | 上限，单位「分」       |

联合唯一 `(user_id, category, month)`。

### sessions（会话上下文，供澄清反问）

| 字段         | 类型      | 说明            |
| ---------- | ------- | ------------- |
| session_id | TEXT PK |               |
| context    | TEXT    | JSON：待补全的草稿槽位 |
| updated_at | TEXT    |               |

---

## 3. 分类体系与规则词典

8 类：`餐饮 交通 购物 居住 娱乐 医疗 教育 其他`。完整词典在 `config/categories.json`，  
每类 ≥10 个关键词，初始化时写入 `categories` 表。

**分类流程（LLM 与规则的边界）**：

1. LLM 优先输出 `category`；
2. 本层 `normalize_category()` 校验是否落在 8 类内，非法 / 空 → 落「其他」；
3. LLM 失败时，`classify()` 用关键词词典兜底（命中数最多者胜，无命中 → 「其他」）。

`logic/classify.py` 提供：`known_categories()`、`is_valid_category()`、  
`normalize_category()`、`classify()`。

---

## 4. 金额处理

`logic/money.py`：

- `yuan_to_cents(amount)`：元 → 分，接受 int / float / str（`25` / `25.5` / `"25.50"`），负值抛错。
- `cents_to_yuan(cents)`：分 → 元字符串（`2550` → `"25.50"`）。

**接口层金额单位说明**（供后端/前端对齐）：所有 API 的请求/响应金额字段用「元」，  
DAO 内部一律「分」。后端在出入参边界调用上述两个函数即可。

---

## 5. 统计与预算逻辑

`logic/stats.py`（纯函数，输入 records 列表，输出统计结果）：

| 函数                 | 说明              | 对应接口                 |
| ------------------ | --------------- | -------------------- |
| `filter_by_period` | [start, end) 过滤 | —                    |
| `total_expense`    | 总支出             | —                    |
| `summary`          | 总额 / 笔数 / 日均    | `/stats/summary`     |
| `by_category`      | 分类汇总（降序）        | `/stats/by-category` |
| `category_share`   | 分类占比 %          | `/stats/by-category` |
| `trend`            | 按 day/month 趋势  | `/stats/trend`       |
| `month_over_month` | 环比              | 可选加分项                |
| `top_category`     | 前 N 分类          | —                    |

`logic/budget.py`（纯函数）：

| 函数                              | 说明                                         |
| ------------------------------- | ------------------------------------------ |
| `check_budget(limit, spent)`    | 返回 `{status, used_ratio, remaining_cents}` |
| `remind_text(category, result)` | 提醒文案                                       |

**预算状态枚举（对齐 `/budgets/alerts`）**：`normal`（<80%）、`warning`（≥80%）、`over`（≥100%）。

---

## 6. 查账流程（对齐 §5.2 / §9）

「我上个月吃饭花了多少？」的处理链路：

1. LLM 只解析槽位：`{"time": "上月", "categories": ["餐饮"], "agg": "sum"}`
2. `resolve_time_range("上月")` → `("2026-10-01", "2026-11-01")`（左闭右开）
3. `query_records(start, end, category="餐饮", confirmed=1)` 取数
4. `total_expense(...)` 算数 → 后端模板拼接 `answer_text`

`logic/query_parser.py` 的 `resolve_time_range()` 支持：今天 / 昨天 / 本周 / 上周 /  
本月 / 上月 / 今年 / 去年 / 近 N 天 / 近 N 月，无法识别兜底「本月」。

---

## 7. 与队长 DDL 的差异说明（需在启动会同步）

| 项       | 队长 DDL          | 本设计                    | 理由                                 |
| ------- | --------------- | ---------------------- | ---------------------------------- |
| 金额      | `amount REAL`   | `amount_cents INTEGER` | 浮点误差是记账硬伤，存分整数更稳                   |
| 预算总预算标记 | `category NULL` | `category ''` 空串       | SQLite 的 UNIQUE 对 NULL 不生效，空串可保证唯一 |
| 时间区间    | 示例闭区间 `06-30`   | 左闭右开 `07-01`           | DATETIME 含时分秒，右闭会漏当天               |

> 建议在启动会上与队长确认这三点，达成一致后回写队长文档。

---

## 8. 与其他模块的接口契约

- **↔ 李语琛（AI）**：槽位 JSON 字段名必须与 records 表一致——`amount / category / merchant / occurred_at / note`；  
  8 类枚举由 `known_categories()` 注入 Prompt；缺金额/时间走他的 `clarify_question`，不落本层。
- **↔ 史雅萱（后端）**：只调 DAO 函数，不拼 SQL。函数清单见 `db/dao.py` 顶部 docstring。  
  金额出入参用元，内部用分；错误码 `2001/2002`（LLM/OCR 失败）触发时，分类兜底由 `classify()` 接管。
- **↔ 林丹苗（前端）**：`/stats/*` 与 `/budgets/alerts` 返回的金额单位——统计结果内部为分，  
  后端应在返回前转元，前端展示「元」。`status` 取值 `normal/warning/over`。
- **↔ 江为（测试）**：demo CSV 字段 `date,time,description,merchant,amount,payment_method`，  
  其中 `amount` 为元，`category` 由规则词典从 `description+merchant` 推断（`scripts/load_sample.py`）。

---

## 9. 测试

```bash
python scripts/selfcheck.py      # 自检，无需 pytest
pytest -q                        # 单元测试
```

覆盖：金额换算、规则分类、查账时间解析、统计、预算、DAO 入库往返。
