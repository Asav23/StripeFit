"""Database engine and session helpers."""

import json
import logging
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, inspect
from sqlmodel import Session, SQLModel, create_engine

from app.config import DB_PATH, UPLOAD_DIR

log = logging.getLogger("stripefit.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def init_db() -> None:
    from app import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)
    add_missing_columns()
    for sub in ("originals", "thumbs", "placeholders"):
        (UPLOAD_DIR / sub).mkdir(parents=True, exist_ok=True)
    with Session(engine) as session:
        if session.get(models.User, 1) is None:
            session.add(models.User(id=1))
            session.commit()


def add_missing_columns() -> None:
    """Tiny migration: add columns that exist on a model but not yet in the SQLite file.

    create_all() makes new tables but never alters existing ones, so without this a new model
    field would mean wiping the demo data with seed.py. Existing rows get the field's default.
    Renames and type changes are not handled; re-run scripts/seed.py for those.
    """
    models_by_table = {m.__tablename__: m for m in _table_models()}
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column.type.compile(engine.dialect)}'
                default = _default_sql(models_by_table.get(table.name), column)
                if default is not None:
                    ddl += f" DEFAULT {default}"
                conn.exec_driver_sql(ddl)
                log.info("Added column %s.%s to the database", table.name, column.name)
            for index in table.indexes:
                index.create(conn, checkfirst=True)  # e.g. an index on a column just added


def _table_models() -> list[type[SQLModel]]:
    found, todo = [], list(SQLModel.__subclasses__())
    while todo:
        model = todo.pop()
        todo += model.__subclasses__()
        if getattr(model, "__table__", None) is not None:
            found.append(model)
    return found


def _default_sql(model: Any, column: Any) -> str | None:
    """The model field's default as a SQL literal, or None if it has no usable default."""
    field = model.model_fields.get(column.name) if model else None
    if field is None:
        return None
    value = field.get_default(call_default_factory=True)
    if value is None:
        return None
    if isinstance(column.type, JSON):
        value = json.dumps(value)
    elif isinstance(value, bool):
        return "1" if value else "0"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, datetime):
        value = value.isoformat(sep=" ")
    return "'" + str(value).replace("'", "''") + "'"


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
