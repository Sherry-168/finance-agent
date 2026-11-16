# 后端接口实现核对（2026-11-16）

> 核对人：林丹苗（前端）
> 核对对象：`origin/main` @ `2718ba1`（PR #2 ```2e26ce5 feat: 按照 v1.1 契约补全后端接口```）
> 核对方式：逐行阅读 `main.py` 静态核对，未启动服务实测（下文标「未实测」处为静态推断）
> 对照文档：`docs/api.md`（本次已同步至 v1.1）、`docs/api-frontend-proposal.md`

## 1. 结论摘要

后端这次确实按 v1.1 补了 `/records/parse` 与 `POST /records`，方向正确。但仍有 **1 个阻塞性缺陷、2 个契约漂移、10 个接口未实现**，Day 3 联调前需处理。

| 类别 | 数量 | 影响 |
|---|---|---|
| 阻塞（P0） | 1 | `/query` 调用必失败，查账功能跑不通 |
| 契约漂移（P0） | 1 | `docs/api.md` 未随代码更新，接口冻结原则失效 |
| 数据未接通（P1） | 2 | `parse` 返回硬编码假数据；`POST /records` 未真正入库 |
| 接口缺失（P1） | 10 | Day 4–6 的明细 / 统计 / 预算 / 演示全部无法联调 |

## 2. 问题清单

### P0-1 `POST /query` 入参字段不匹配，调用必然 422（未实测，静态确认）

现状：

```python
class ParseRequest(BaseModel):
    text: str
    session_id: Optional[str] = None

@app.post("/api/v1/query")
def query_records(request: ParseRequest):
    ...
```

契约（`docs/api.md` §3）与前端实际发送：

```json
{ "question": "我上个月吃饭花了多少？", "session_id": "s_abc123" }
```

`ParseRequest` 要求 `text` 必填，因此请求会被 FastAPI 直接判 422（且是裸 HTTP 错误体，不是统一包装），前端只能显示「接口返回格式异常」。

修复建议：

```python
class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

@app.post("/api/v1/query")
def query_records(request: QuestionRequest):
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "slots": {"time_range": [], "categories": [], "agg": "sum", "group_by": None},
            "answer_text": "...",
            "table": [],
        },
    }
```

### P0-2 `docs/api.md` 未随代码更新

`2e26ce5` 只改了 `main.py`，`docs/api.md` 仍是 v1.0 扁平版（`{"amount": 32.0, "category": "交通", "occurred_at": "..."}`）。

后果：前端若以文档为准开发，会拿不到 `draft_id` / `confidence` / `clarify_question`；新人按文档写会直接报错。

处理：本次已由前端**代拟更新为 v1.1**（`docs/api.md`，含实现状态标记），请后端确认后视为冻结；后续任何字段调整必须先改文档再改代码。

### P1-1 `POST /records/parse` 仍是硬编码假数据

```python
return {"code": 0, "data": {"draft_id": "d_001", "fields": {"amount": 32.0, "category": "交通", ...}, "confidence": 0.95, "missing_fields": [], "clarify_question": None}}
```

- 无论输入什么（哪怕「看电影 88 块」），都返回打车 32 元；
- `clarify_question` 恒为 `null`，`missing_fields` 恒为空 —— **澄清反问链路无法联调**；
- `confidence` 恒为 0.95，确认卡的可信度展示没有意义。

建议：Day 3 前接入李语琛的解析模块，至少有「缺金额 / 缺时间 → 返回反问句」的最小可用版本。

### P1-2 `POST /records` 未真正入库

```python
@app.post("/api/v1/records")
def save_record(item: RecordItem):
    return {"code": 0, "data": {"id": 101, "confirmed": 1}}   # 固定 id，不落库
```

- 返回固定 `id: 101`，`GET /records` 也还没有，所以「确认入库 → 明细可见」这条验收链路仍不成立；
- `RecordItem.raw_text: str` 为**必填**，确认卡提交时必须带上原始输入（前端已知悉，会带）；
- `draft_id`、`source` 未在模型中，pydantic 会静默丢弃（无害，但建议显式声明 `Optional` 以便后续溯源）。

### P1-3 缺失接口（10 个）

| 接口 | 前端使用时间 |
|---|---|
| `GET /records`（分页/筛选） | Day 4 |
| `PUT /records/{id}` | Day 4 |
| `DELETE /records/{id}` | Day 4 |
| `GET /stats/summary` | Day 5 |
| `GET /stats/by-category` | Day 5 |
| `GET /stats/trend` | Day 5 |
| `POST /budgets`、`GET /budgets`、`GET /budgets/alerts` | Day 6 |
| `GET /categories`、`POST /demo/load`、`POST /demo/reset` | Day 6 |
| `POST /records/ocr`（multipart） | 第二周 |

字段与示例均已写入 `docs/api.md` §2.4–§7，可直接照此实现。

### P2-1 错误码没有真正生效

目前所有接口恒返回 `code: 0`，参数错误由 FastAPI 直接抛 422 裸体（如 `/query` 的必填缺失、`amount` 类型错误）。

建议加统一异常处理器，保证任何失败也走 `{code, message, data}` 包装：

```python
from fastapi import Request
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
def on_validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=200, content={
        "code": 1001, "message": "参数错误", "data": {"detail": exc.errors()},
    })
```

### P2-2 目录结构

`main.py` 已从骨架长到 60+ 行但仍单文件。补完 §P1-3 会明显膨胀，建议尽早拆分：

```
app/
├── main.py          # FastAPI 实例 + 路由注册
├── schemas.py       # Pydantic 模型
├── routers/records.py, query.py, stats.py, budgets.py, demo.py
└── db.py            # SQLite 连接与建表
```

## 3. 前端应对（已完成，不需后端配合）

- `frontend/api.py` 的 `normalize_draft()` 同时兼容 v1.0 扁平结构与 v1.1 草稿结构，后端切换期间前端不需要改代码；
- 后端未启动时，对话解析自动降级本地 Mock（`config.MOCK_FALLBACK`），界面可持续自测；
- 业务错误（`code != 0`）不降级，如实提示，避免掩盖真实问题。

## 4. 待办（请后端认领）

- [ ] 修 `POST /query`：改用 `{question, session_id}`，补 `slots`
- [ ] 确认 `docs/api.md` v1.1（本次前端代拟），确认后群内公告冻结
- [ ] `POST /records/parse` 接入真实解析，至少支持「缺金额 / 缺时间」返回 `clarify_question`
- [ ] `POST /records` 真正落库（联调蔡适伶的插入逻辑）
- [ ] Day 4 前：`GET /records`、`PUT /records/{id}`、`DELETE /records/{id}`
- [ ] Day 5 前：`/stats/summary`、`/stats/by-category`、`/stats/trend`
- [ ] Day 6 前：`/budgets*`、`/categories`、`/demo/load`、`/demo/reset`
- [ ] 加统一异常处理器，保证错误响应也是 `{code, message, data}`
