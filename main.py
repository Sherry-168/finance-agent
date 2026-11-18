"""兼容入口。

真正的应用装配在 `app/main.py`，本文件只做两件事：
- 暴露 `app`，让 `uvicorn main:app` 继续可用；
- 支持 `python main.py` 直接启动，读取 BACKEND_HOST / BACKEND_PORT 环境变量。

推荐启动方式：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
"""
from __future__ import annotations

from app.main import app  # noqa: F401  uvicorn main:app 依赖此处导出

__all__ = ["app"]


def main() -> None:
    """本地开发启动（等价于 uvicorn app.main:app）。"""
    import uvicorn

    from app.core.config import SERVER_HOST, SERVER_PORT

    uvicorn.run("app.main:app", host=SERVER_HOST, port=SERVER_PORT, reload=False)


if __name__ == "__main__":
    main()
