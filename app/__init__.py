"""后端应用包。

分层约定：
- `app/core/`    基础设施（配置、响应包装、数据库连接、异常）
- `app/routers/` HTTP 路由，只做参数校验与响应组装
- `app/adapters/` 外部能力接缝（LLM / OCR 解析），便于无 Key 时降级
- `db/` `logic/`  数据与规则（蔡适伶维护），纯函数、可单测，不依赖 FastAPI
"""
