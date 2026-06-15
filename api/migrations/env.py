"""Alembic environment (async). Adapted from boilerplate v0.15.0.

Migrations are HAND-WRITTEN (鐵律 2): ``target_metadata`` is wired only so
``alembic check``/history works and offline rendering is possible — we never run
``--autogenerate``. DB URL is built from ``app.core.config`` (localhost only).
"""

import asyncio
import importlib
import pkgutil
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.core.db.database import Base

config = context.config

config.set_main_option(
    "sqlalchemy.url",
    f"{settings.POSTGRES_ASYNC_PREFIX}{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}",
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def import_models(package_name: str) -> None:
    package = importlib.import_module(package_name)
    for _, module_name, _ in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        importlib.import_module(module_name)


import_models("app.models")
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
