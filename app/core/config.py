"""运行配置：所有可变项一律由环境变量注入，仓库内不出现真实密钥。

优先级：真实环境变量 > 项目根目录 `.env` > 本文件默认值。
`.env` 已被 .gitignore 忽略，提交前请核对 `git status`。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录：app/core/config.py -> app/core -> app -> 根
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 允许没有 .env：本地缺省值可跑通，容器内由 compose 注入
load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------- 应用
APP_TITLE = "记账助手后端 API"
API_PREFIX = os.getenv("API_PREFIX", "/api/v1")

# ---------------------------------------------------------------- 存储
# 相对路径按项目根目录解析；容器内传绝对路径 /app/data/finance.db
DB_PATH = os.getenv("DB_PATH", "data/finance.db")
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "demo_user")

# ---------------------------------------------------------------- LLM（OpenAI 兼容：DeepSeek / Qwen / GLM 任一）
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))

# ---------------------------------------------------------------- OCR：api = 视觉模型优先，local = 本地兜底
OCR_PROVIDER = os.getenv("OCR_PROVIDER", "local")

# ---------------------------------------------------------------- 服务
SERVER_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("BACKEND_PORT", "8000"))


def database_file() -> Path:
    """返回数据库文件绝对路径，并保证父目录存在。

    sqlite3 不会自动建目录，父目录不存在会直接报 `unable to open database file`，
    所以这里统一兜住（容器首次挂载空卷时尤其需要）。
    """
    path = Path(DB_PATH)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def has_llm_key() -> bool:
    """是否配置了真实 LLM Key（决定走模型还是走规则兜底）。"""
    return bool(LLM_API_KEY.strip())
