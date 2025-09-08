import time
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.workers.celery_app import celery_app, log
from app.deid.engine import DeidEngine, POLICY_MAP as DEFAULT_POLICY_MAP
from app.core.config import get_settings
from app.db.session import session_scope
from app.db.crud import create_deid_log, create_metric_run


@celery_app.task(name="workers.deid_text_task")
def deid_text_task(text: str, lang_hint: Optional[str] = None):
    settings = get_settings()
    engine = DeidEngine(
        policy_map={**DEFAULT_POLICY_MAP},
        salt=settings.deid_salt,
        default_policy=settings.deid_default_policy,
    )

    req_id = uuid.uuid4()
    result = engine.deidentify(text or "", lang_hint=lang_hint)

    # Persist log
    try:
        with session_scope() as db:  # type: Session
            create_deid_log(
                db,
                request_id=req_id,
                num_entities=len(result.get("entities", [])),
                time_ms=float(result.get("time_ms", 0)),
                input_len=int(result.get("original_len", 0)),
                output_len=len(result.get("result_text", "")),
                policy_version=f"{settings.app_version}:{settings.deid_default_policy}",
                lang_hint=lang_hint or "",
                sample_preview=(result.get("result_text", "")[:200]),
            )
    except Exception as e:  # pragma: no cover - logging only
        log.warning(f"Failed to persist DeidLog: {e}")

    return {"request_id": str(req_id), **result}


@celery_app.task(name="workers.evaluate_dataset_task")
def evaluate_dataset_task(dataset_path: str):
    """Very lightweight placeholder evaluation: treat each non-empty line as a doc."""
    settings = get_settings()
    engine = DeidEngine(
        policy_map={**DEFAULT_POLICY_MAP},
        salt=settings.deid_salt,
        default_policy=settings.deid_default_policy,
    )

    started = time.perf_counter()
    n_docs = 0
    try:
        with open(dataset_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                text = line.strip()
                if not text:
                    continue
                engine.deidentify(text)
                n_docs += 1
    except FileNotFoundError:
        raise

    elapsed = time.perf_counter() - started
    docs_per_sec = (n_docs / elapsed) if elapsed > 0 else 0.0

    # Placeholder metrics
    precision = {"micro": 0.0}
    recall = {"micro": 0.0}
    f1 = {"micro": 0.0}
    fnr = {"overall": 0.0}

    # Persist metric run
    run = None
    with session_scope() as db:  # type: Session
        run = create_metric_run(
            db,
            dataset_name=str(dataset_path),
            precision=precision,
            recall=recall,
            f1=f1,
            docs_per_sec=docs_per_sec,
            false_negative_rate=fnr,
        )

    return {
        "id": run.id if run else None,
        "dataset_name": str(dataset_path),
        "docs": n_docs,
        "elapsed_sec": elapsed,
        "docs_per_sec": docs_per_sec,
    }
