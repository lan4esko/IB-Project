"""Безопасный разовый перенос строк из SQLite v0.1 в чистую PostgreSQL v0.2.
Запуск только вручную, требует IB_DATABASE_URL=postgresql+psycopg://... .
"""
from pathlib import Path
import os
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from app import database as dbm

TABLES = [dbm.NormativeAct, dbm.InfoObject, dbm.Requirement, dbm.Measure, dbm.AuditEvent]

def migrate():
    if dbm.engine.dialect.name != "postgresql":
        raise RuntimeError("Источник назначения должен быть PostgreSQL")
    source_file = Path(os.getenv("IB_SQLITE_SOURCE", "/data/platform.db"))
    if not source_file.is_file():
        raise RuntimeError("Исходный SQLite-файл отсутствует, импорт не выполнялся")
    source = create_engine(f"sqlite:///{source_file}")
    with Session(source) as source_session, Session(dbm.engine) as target:
        # Никаких частичных повторных импортов в непустую БД.
        for model in TABLES:
            count = target.scalar(select(model.id).limit(1))
            if count is not None:
                raise RuntimeError(f"Таблица назначения {model.__tablename__} уже содержит данные")
        counters = {}
        for model in TABLES:
            source_items = source_session.scalars(select(model).order_by(model.id)).all()
            counters[model.__tablename__] = len(source_items)
            columns = [column.key for column in model.__table__.columns]
            for item in source_items:
                target.add(model(**{name: getattr(item, name) for name in columns}))
            target.flush()
        for model in TABLES:
            table = model.__tablename__
            if counters[table]:
                target.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"(SELECT MAX(id) FROM {table}), true)"
                ))
        target.commit()
        print("SQLite -> PostgreSQL OK:", counters)

if __name__ == "__main__":
    migrate()
