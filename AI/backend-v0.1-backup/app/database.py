import os
from contextlib import contextmanager
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def now_utc():
    return datetime.now(timezone.utc)


DATABASE_URL = os.getenv("IB_DATABASE_URL", "sqlite:////data/platform.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class NormativeAct(Base):
    __tablename__ = "normative_acts"
    __table_args__ = (UniqueConstraint("code", "revision", name="uq_act_code_revision"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(500))
    revision: Mapped[str] = mapped_column(String(100))
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    act_id: Mapped[int] = mapped_column(ForeignKey("normative_acts.id"), index=True)
    clause: Mapped[str] = mapped_column(String(160))
    text: Mapped[str] = mapped_column(Text)
    applicability: Mapped[str] = mapped_column(Text, default="Не определена")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class InfoObject(Base):
    __tablename__ = "info_objects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    type: Mapped[str] = mapped_column(String(100), default="other")
    stage: Mapped[str] = mapped_column(String(60), default="planning")
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Measure(Base):
    __tablename__ = "measures"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id"), index=True)
    info_object_id: Mapped[int] = mapped_column(ForeignKey("info_objects.id"), index=True)
    action: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="planned")
    evidence_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


def get_db():
    with SessionLocal() as db:
        yield db
