"""SQLite 连接与初始化。

DAO 由数据负责人维护（db/dao.py），本模块只负责
「路径解析 + 连接生命周期 + 启动建表」，路由里不裸写 SQL。
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.config import database_file
from db import dao


def init_database() -> None:
    """建表并写入 8 类分类词典（幂等），应用启动时调用一次。"""
    conn = dao.connect(str(database_file()))
    try:
        dao.init_db(conn)
    finally:
        conn.close()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """每请求一条连接，用完即关，避免跨请求共享游标。"""
    conn = dao.connect(str(database_file()))
    try:
        yield conn
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI 依赖注入用：`conn: sqlite3.Connection = Depends(get_db)`。"""
    with get_connection() as conn:
        yield conn
