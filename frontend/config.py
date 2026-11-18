"""前端全局配置。

以 docs/api.md 定稿的接口规范为准（Day 1 已冻结）：
- Base URL：http://localhost:8000/api/v1
- 全部 application/json（OCR 上传为 multipart/form-data）
- 统一响应包装 {"code": 0, "message": "ok", "data": {...}}
"""

import os

# ---------------------------------------------------------------- 接口基础配置
# 允许通过环境变量覆盖，便于 docker-compose 内改指向后端服务名
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
API_TIMEOUT = float(os.getenv("API_TIMEOUT", "15"))

# 统一响应包装：code == 0 才算成功，其余一律走前端统一报错提示
SUCCESS_CODE = 0
ERROR_MESSAGES = {
    1001: "参数有误，请检查输入内容",
    1002: "请求的数据不存在或已被删除",
    2001: "AI 解析失败，请稍后重试或换个说法",
    2002: "小票识别失败，请换一张清晰的图片",
}

# ---------------------------------------------------------------- 业务约定
# 单用户简化：前端不做登录 / 用户切换
USER_ID = "demo_user"

# 8 类固定枚举（与后端 categories 表一致，禁止前端自造类别）
CATEGORIES = ["餐饮", "交通", "购物", "居住", "娱乐", "医疗", "教育", "其他"]
TOTAL_BUDGET_LABEL = "总额（不限类别）"

# 明细列表默认分页参数（与后端默认值对齐）
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10
PAGE_SIZE_CHOICES = [10, 20, 50]

# ---------------------------------------------------------------- 联调兜底
# 默认关闭：后端接口已全部落地，评审看到的必须是数据库真实数据。
# 仅在纯前端自测时可显式设 MOCK_FALLBACK=1 打开本地演示数据。
MOCK_FALLBACK = os.getenv("MOCK_FALLBACK", "0").lower() not in ("0", "false", "no")

# ---------------------------------------------------------------- 启动参数
SERVER_NAME = os.getenv("FRONTEND_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("FRONTEND_PORT", "7860"))

APP_TITLE = "记账小助手"
APP_SUBTITLE = "说一句话、拍一张照，钱就记好了；问一句话，答案就出来了。"
