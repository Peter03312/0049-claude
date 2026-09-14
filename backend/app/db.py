"""SQLite / SQLAlchemy 初始化。"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 容器内工作目录为 /data 并挂卷；本地运行则落在当前目录。
# 可用 DB_PATH 环境变量覆盖。
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.getcwd(), "leafcards.db"))

# 允许测试用内存或临时路径通过环境变量覆盖
connect_args = {"check_same_thread": False} if DB_PATH.endswith(".db") else {}
if DB_PATH.endswith(".db"):
    _dir = os.path.dirname(DB_PATH)
    if _dir:
        os.makedirs(_dir, exist_ok=True)
engine = create_engine(
    f"sqlite:///{DB_PATH}", echo=False, future=True, connect_args=connect_args
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401  确保模型已注册

    Base.metadata.create_all(engine)
