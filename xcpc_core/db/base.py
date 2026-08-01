from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """xcpc_core 全部 ORM 表的声明基类（纯 SQLAlchemy）。"""
