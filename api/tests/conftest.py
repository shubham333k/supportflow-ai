"""
Pytest configuration and shared fixtures for SupportFlow AI.
Registers SQLite compilers and adapters for PostgreSQL types (ARRAY, JSONB, UUID, Vector)
so all in-memory SQLite unit and integration tests work seamlessly.
"""

import json
import sqlite3

from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles

# Register SQLite adapters for Python list, dict, and UUID
sqlite3.register_adapter(list, json.dumps)
sqlite3.register_adapter(dict, json.dumps)
import uuid
sqlite3.register_adapter(uuid.UUID, lambda u: str(u))

# SQLite custom compilations for PostgreSQL types
@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(PG_UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_, compiler, **kw):
    return "BLOB"


import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from api.app.main import app
from api.app.models.base import Base
from api.app.models.database import get_db


@pytest.fixture
async def async_db():
    """Create in-memory SQLite async DB for tests and override get_db dependency."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    orig_override = app.dependency_overrides.get(get_db)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as db:
        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            yield db
        finally:
            if orig_override is not None:
                app.dependency_overrides[get_db] = orig_override
            else:
                app.dependency_overrides.pop(get_db, None)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
