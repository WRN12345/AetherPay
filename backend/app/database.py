"""
数据库连接
使用同步 SQLAlchemy；FastAPI 中调用它的接口应写成普通 def
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类，Alembic 从 Base.metadata 生成迁移"""


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：每个请求一个数据库会话"""
    with SessionLocal() as session:
        yield session
