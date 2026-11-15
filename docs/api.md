# 前后端接口契约 (v1.0)

## 1. 基础规范
- 所有接口以 `/api/v1/` 开头。
- 统一响应格式：`{"code": 0, "message": "ok", "data": {...}}`
- 字段名严格统一：金额=`amount` (浮点数)，类别=`category` (字符串)，时间=`occurred_at` (YYYY-MM-DD)。

## 2. 接口列表

### 2.1 自然语言记账解析
**POST** `/api/v1/records/parse`
- **请求**：`{"text": "昨天打车32块"}`
- **响应**：
  `{"code": 0, "data": {"amount": 32.0, "category": "交通", "occurred_at": "2026-11-14"}}`

### 2.2 确认入库
**POST** `/api/v1/records`
- **请求**：`{"amount": 32.0, "category": "交通", "occurred_at": "2026-11-14", "raw_text": "昨天打车32块"}`

### 2.3 自然语言查账
**POST** `/api/v1/query`
- **请求**：`{"question": "上个月吃饭花了多少？"}`
- **响应**：
  `{"code": 0, "data": {"answer_text": "你上个月餐饮共支出 ¥1286.50", "total": 1286.5}}`

### 2.4 健康检查
**GET** `/api/v1/health`
- **响应**：`{"code": 0, "message": "ok", "data": "Backend is running"}`

## 3. 固定分类字典（严禁修改）
餐饮、交通、购物、居住、娱乐、医疗、教育、其他