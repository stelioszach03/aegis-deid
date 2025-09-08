import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .models import Document, DeidLog, MetricRun


def create_document(db: Session, original_text: str, deidentified_text: str, lang: str = "en") -> Document:
    doc = Document(
        original_text=original_text,
        deidentified_text=deidentified_text,
        lang=lang,
    )
    db.add(doc)
    db.flush()
    return doc


def create_deid_log(
    db: Session,
    *,
    request_id: uuid.UUID,
    num_entities: int,
    time_ms: float,
    input_len: int,
    output_len: int,
    policy_version: str,
    lang_hint: Optional[str] = None,
    sample_preview: Optional[str] = None,
) -> DeidLog:
    log = DeidLog(
        request_id=request_id,
        num_entities=num_entities,
        time_ms=time_ms,
        input_len=input_len,
        output_len=output_len,
        policy_version=policy_version,
        lang_hint=lang_hint,
        sample_preview=sample_preview,
    )
    db.add(log)
    db.flush()
    return log


def create_metric_run(
    db: Session,
    *,
    dataset_name: str,
    precision: Dict[str, Any],
    recall: Dict[str, Any],
    f1: Dict[str, Any],
    docs_per_sec: Optional[float] = None,
    false_negative_rate: Optional[Dict[str, Any]] = None,
) -> MetricRun:
    run = MetricRun(
        dataset_name=dataset_name,
        precision=precision,
        recall=recall,
        f1=f1,
        docs_per_sec=docs_per_sec,
        false_negative_rate=false_negative_rate,
    )
    db.add(run)
    db.flush()
    return run
