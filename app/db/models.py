import uuid
from datetime import datetime

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Integer, Float, func
from sqlalchemy.dialects.postgresql import UUID, JSONB


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    original_text: Mapped[str] = mapped_column(Text)
    deidentified_text: Mapped[str] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(String(8), default="en")


class DeidLog(Base):
    __tablename__ = "deid_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    num_entities: Mapped[int] = mapped_column(Integer, nullable=False)
    time_ms: Mapped[float] = mapped_column(Float, nullable=False)
    input_len: Mapped[int] = mapped_column(Integer, nullable=False)
    output_len: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    lang_hint: Mapped[str] = mapped_column(String(8), nullable=True)
    sample_preview: Mapped[str] = mapped_column(Text, nullable=True)


class MetricRun(Base):
    __tablename__ = "metric_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    precision: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recall: Mapped[dict] = mapped_column(JSONB, nullable=False)
    f1: Mapped[dict] = mapped_column(JSONB, nullable=False)
    docs_per_sec: Mapped[float] = mapped_column(Float, nullable=True)
    false_negative_rate: Mapped[dict] = mapped_column(JSONB, nullable=True)
