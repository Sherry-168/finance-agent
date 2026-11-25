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

# 解析后端的切换开关（第二周新增，验收项「LLM 调用可切 Dify」）：
#   openai → 直接调 OpenAI 兼容的 chat/completions（DeepSeek / Qwen / GLM）
#   dify   → 调李语琛交付的 Dify 工作流（多模态、拆单、拟人化 Prompt 都在 Dify 侧）
# 两种后端产出的槽位结构一致，路由 / DAO / 前端完全不感知差异。
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()

# ---------------------------------------------------------------- Dify 工作流
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
DIFY_BASE_URL = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1")
DIFY_TIMEOUT = float(os.getenv("DIFY_TIMEOUT", "30"))
# 工作流「开始节点」里接收用户输入的变量名，与 Dify 编排页保持一致即可
DIFY_INPUT_KEY = os.getenv("DIFY_INPUT_KEY", "user_input")
DIFY_USER = os.getenv("DIFY_USER", "demo_user")

# ---------------------------------------------------------------- 语音识别（ASR，云端 API，禁止本地模型）
#   auto    → 配了 Key 就走云端转写，没配 Key 明确报错（不静默造假）
#   agent   → 调用李语琛交付的 agent.speech_to_text(audio_path)
#   mock    → 离线演示：不联网，直接回 ASR_MOCK_TEXT（明确标注 asr_engine=mock）
ASR_PROVIDER = os.getenv("ASR_PROVIDER", "auto").strip().lower()
ASR_API_KEY = os.getenv("ASR_API_KEY", os.getenv("LLM_API_KEY", ""))
# OpenAI 兼容的 /audio/transcriptions 端点（智谱 open.bigmodel.cn / 阿里云百炼 compatible-mode 均可）
ASR_BASE_URL = os.getenv("ASR_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
ASR_MODEL = os.getenv("ASR_MODEL", "glm-asr")
ASR_TIMEOUT = float(os.getenv("ASR_TIMEOUT", "30"))
ASR_LANGUAGE = os.getenv("ASR_LANGUAGE", "zh")
ASR_MOCK_TEXT = os.getenv("ASR_MOCK_TEXT", "昨天打车 32 块")

# ---------------------------------------------------------------- OCR / 小票识别
# api  = 视觉模型（长截图可一次返回多笔）；dify = Dify 多模态工作流；local = 未打包本地模型
OCR_PROVIDER = os.getenv("OCR_PROVIDER", "local")
# 视觉模型单独一套凭据：解析用的 deepseek-chat 不具备读图能力，混用会静默失败
VISION_API_KEY = os.getenv("VISION_API_KEY", "")
VISION_BASE_URL = os.getenv("VISION_BASE_URL", os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"))
VISION_MODEL = os.getenv("VISION_MODEL", "glm-4v-flash")
# Dify 多模态工作流里接收图片（base64 data URL）的变量名
DIFY_IMAGE_KEY = os.getenv("DIFY_IMAGE_KEY", "receipt_image")

# ---------------------------------------------------------------- 跨域（CORS）
# 逗号分隔；默认 * 方便本地 / 答辩机器直连（凭证请求不支持 *，此时自动降级为无序白名单）
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

# ---------------------------------------------------------------- 上传限制
# 语音与图片都走云端 API，只做体积护栏，避免大文件把内存和超时拖垮
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "10"))

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


def has_dify() -> bool:
    """是否配置了 Dify 工作流 Key。"""
    return bool(DIFY_API_KEY.strip())


def parser_provider() -> str:
    """当前实际生效的解析后端：`dify` 或 `openai`。

    容错：选了 dify 却没配 Key 时自动回退 openai，避免答辩现场因漏配环境变量整条链路报错
    （回退只发生在「功能不可用」时，日志与 /health 的 llm.provider 会如实反映）。
    """
    if LLM_PROVIDER == "dify" and has_dify():
        return "dify"
    return "openai"


def llm_ready() -> bool:
    """解析链路是否具备真实模型能力（False 表示只会走规则兜底）。"""
    return has_dify() if parser_provider() == "dify" else has_llm_key()


def has_asr_key() -> bool:
    """是否配置了云端语音识别 Key。"""
    return bool(ASR_API_KEY.strip())


def max_upload_bytes() -> int:
    """上传体积上限（字节）。"""
    return int(MAX_UPLOAD_MB * 1024 * 1024)
