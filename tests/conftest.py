"""pytest 公共夹具（第二周新增）。

关键点：**测试绝不碰 data/finance.db**
--------------------------------------
接口测试会走真实的 `init_database()` 与请求生命周期，如果沿用默认库路径，
跑一次测试就会把开发者本地的演示数据写脏（甚至删掉别人导入的样例）。
所以在导入 `app.*` 之前把 `DB_PATH` 指向临时目录，`app.core.config` 读到的
就是隔离库；每个用例再清一遍业务表，保证用例之间互不影响。

`ASR_PROVIDER=mock`：语音用例不联网也能跑，转写结果固定为 `ASR_MOCK_TEXT`。
"""
from __future__ import annotations

import atexit
import os
import tempfile
import uuid

# 直接放在系统临时目录的**第一层**（不建子目录）：某些受限环境只给临时根目录
# 授予「建文件」权限，子目录里反而写不进去。
_DB_FILE = os.path.join(tempfile.gettempdir(), f"finance-agent-test-{uuid.uuid4().hex[:8]}.db")
os.environ["DB_PATH"] = _DB_FILE
os.environ["ASR_PROVIDER"] = "mock"
os.environ["ASR_MOCK_TEXT"] = "昨天打车 32 块"
os.environ["OCR_PROVIDER"] = "local"
os.environ["VISION_API_KEY"] = ""
os.environ.setdefault("DEFAULT_USER_ID", "demo_user")


def _cleanup() -> None:
    """跑完把临时库删掉，不在评审机器上留垃圾。"""
    for suffix in ("", "-journal", "-wal", "-shm"):
        try:
            os.unlink(_DB_FILE + suffix)
        except OSError:
            pass


atexit.register(_cleanup)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import get_connection, init_database  # noqa: E402
from app.main import app  # noqa: E402

_BUSINESS_TABLES = ("records", "budgets", "notifications")


@pytest.fixture(scope="session")
def client() -> TestClient:
    """整个会话共用一个 TestClient（含 lifespan，启动时建表）。"""
    init_database()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def api(client: TestClient) -> TestClient:
    """干净数据库上的 TestClient：每个用例前清空流水 / 预算 / 提醒。"""
    with get_connection() as conn:
        for table in _BUSINESS_TABLES:
            conn.execute(f"DELETE FROM {table}")  # noqa: S608 —— 表名来自固定白名单
        conn.commit()
    return client


@pytest.fixture()
def conn():
    """直连测试库，供需要预置数据的用例使用。"""
    with get_connection() as connection:
        yield connection
