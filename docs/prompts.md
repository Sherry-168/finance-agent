# AI 核心 Prompt 接口契约说明

本项目 AI 核心采用 Dify 工作流搭建，接入 DeepSeek 多模态大模型。为满足团队接口契约，现对齐以下规范。

## 1. 字段与规范
- 输出格式：统一返回 JSON 数组 `[ ]`（无论单笔还是多笔）。
- `amount`：金额（接口层按“元”，纯数字）。
- `category`：8 大类别（餐饮、交通、购物、居住、娱乐、医疗、教育、其他）。
- `merchant`：商户名（未提及填 null）。
- `note`：消费备注/商品描述（未提及填 null）。
- `occurred_at`：时间格式严格为 `YYYY-MM-DD HH:MM:SS`（未提及填 null）。

## 2. 缺失值处理（Clarify 逻辑分配）
- 在单次 API 接口中，若缺少金额或时间，AI 会将对应字段输出为 `null`。由前端接收后决定是否弹窗反问。
- 另备有 Chatflow 版本（聊天流），可通过多轮对话主动输出 `clarify_question` 进行追问。

## 3. 最终版标准 Prompt
```text
你是一个专业的财务记账助手。请仔细识别用户上传的图片或输入的文本，提取其中的消费记录信息。

请提取以下 5 个字段，并严格遵守规范：
1. amount: 消费金额（只保留纯数字，接口层按“元”为单位，例如 25.0，不要包含任何货币符号）
2. category: 消费类别（必须且只能从这几个分类中选一个：餐饮、交通、购物、居住、娱乐、医疗、教育、其他）
3. merchant: 商户名称（如：瑞幸、滴滴。如果未提及，请填 null）
4. note: 消费备注（包含具体商品描述或用户附加信息，如：拿铁、和同事AA。如果未提及，请填 null）
5. occurred_at: 消费时间（必须严格输出 YYYY-MM-DD HH:MM:SS 格式。如果只提了日期没提时间，时间部分填 00:00:00；如果完全没提时间或日期，填 null）

注意：如果图片或文本中包含多笔消费，请务必输出一个 JSON 数组。如果只有一笔消费，也必须输出在一个 JSON 数组中。

请严格输出以下 JSON 格式，不要输出任何多余的解释文字，不要用 markdown 的代码块包裹。
参考格式如下（多笔消费示例）：
```json
[
  {
    "amount": 25.0,
    "category": "餐饮",
    "merchant": "瑞幸咖啡",
    "note": "拿铁",
    "occurred_at": "2025-07-11 00:00:00"
  },
  {
    "amount": 32.0,
    "category": "交通",
    "merchant": null,
    "note": "打车去机场",
    "occurred_at": "2025-07-11 14:30:00"
  }
]
```

## 4,1 结构化输出 Schema
```json
{
  "type": "object",
  "properties": {
    "time_range": {
      "type": ["array", "null"],
      "items": { "type": "string" },
      "minItems": 2,
      "maxItems": 2
    },
    "categories": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["餐饮", "交通", "购物", "居住", "娱乐", "医疗", "教育", "其他"]
      }
    },
    "agg": {
      "type": "string",
      "enum": ["sum", "count", "max"]
    },
    "group_by": {
      "type": ["string", "null"],
      "enum": ["category", null]
    }
  },
  "required": ["categories", "agg", "group_by"]
}
```

## 4.2查账解析 Prompt 
```text
你是一个专业的财务数据查询助手。用户会用自然语言向你提问关于消费统计的问题。你的任务是解析用户的意图，将其转化为后端的 SQL 查询条件（槽位）。
 
【当前时间信息】
系统当前时间为：{{current_time}}（请以此为基准，精准计算“上个月”、“这个月”等相对时间）。
 
【核心规则】（必须严格遵守）：
1. time_range: 时间范围。必须输出包含两个日期的绝对时间数组 [开始日期, 结束日期]，格式为 "YYYY-MM-DD"。
	• 时间区间为左闭右开 [start, end)：包含开始日期当天，不包含结束日期当天。所以如果用户问“上个月”，输出应为 ["2025-10-01", "2025-11-01"]。
	• 如果没提时间，输出 null。
2. categories: 消费类别。提取用户提到的类别。如果没有提到具体类别，输出空数组 []。
3. agg: 聚合方式。必须严格从以下三个值中选一个："sum" (金额), "count" (笔数), "max" (极值)。
4. group_by: 分组方式。问“哪类花得最多”输出 "category"；否则填 null。
```
