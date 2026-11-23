from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for the PostgreSQL control-plane tables (migrations in backend/migrations)."""
