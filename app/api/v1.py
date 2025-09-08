from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request
from pydantic import BaseModel, Field
from typing import Literal

from app.core.config import get_settings
from app.deid.engine import DeidEngine, POLICY_MAP as DEFAULT_POLICY_MAP
from app.core.limiter import limiter
from app.db.session import get_db
from app.db.models import MetricRun
from sqlalchemy.orm import Session
from app.workers.tasks import deid_text_task, evaluate_dataset_task
from app.workers.celery_app import celery_app


router = APIRouter()


# --- In-memory policy/config state for MVP ---
class PolicyConfig(BaseModel):
    policy_map: Dict[str, str]
    default_policy: Literal["mask", "hash", "redact"]


class PolicyUpdate(BaseModel):
    policy_map: Optional[Dict[str, str]] = None
    default_policy: Optional[Literal["mask", "hash", "redact"]] = None


_settings = get_settings()
_policy_state = PolicyConfig(
    policy_map={**DEFAULT_POLICY_MAP},
    default_policy=_settings.deid_default_policy,
)
_engine = DeidEngine(
    policy_map=_policy_state.policy_map,
    salt=_settings.deid_salt,
    default_policy=_policy_state.default_policy,
)


class DeidRequest(BaseModel):
    text: str
    lang_hint: Optional[Literal["en", "el"]] = None


class EngineEntity(BaseModel):
    label: str
    span: List[int] = Field(..., min_items=2, max_items=2)
    action: str


class DeidResult(BaseModel):
    original_len: int
    result_text: str
    entities: List[EngineEntity]
    time_ms: int


@limiter.exempt
@router.get("/health")
async def health():
    return {"status": "ok", "version": _settings.app_version}


@router.get("/config", response_model=PolicyConfig)
async def get_config():
    return _policy_state


@router.put("/config", response_model=PolicyConfig)
async def update_config(update: PolicyUpdate):
    global _engine, _policy_state
    changed = False
    if update.policy_map is not None:
        _policy_state.policy_map = update.policy_map
        changed = True
    if update.default_policy is not None:
        _policy_state.default_policy = update.default_policy
        changed = True
    if changed:
        _engine = DeidEngine(
            policy_map=_policy_state.policy_map,
            salt=_settings.deid_salt,
            default_policy=_policy_state.default_policy,
        )
    return _policy_state


@limiter.limit("30/minute")
@router.post("/deid", response_model=DeidResult)
async def deid(req: DeidRequest, request: Request):
    try:
        result = _engine.deidentify(req.text, lang_hint=req.lang_hint)
        return result
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))


@limiter.limit("30/minute")
@router.post("/deid/file", response_model=List[DeidResult])
async def deid_file(
    request: Request,
    files: List[UploadFile] = File(...),
    lang_hint: Optional[Literal["en", "el"]] = Form(None),
):
    results: List[DeidResult] = []  # type: ignore
    for f in files:
        try:
            content = (await f.read()).decode("utf-8", errors="ignore")
            res = _engine.deidentify(content, lang_hint=lang_hint)
            results.append(DeidResult(**res))
        except ValueError as e:
            raise HTTPException(status_code=413, detail=f"{f.filename}: {e}")
    return results


@router.get("/metrics/last")
async def metrics_last(db: Session = Depends(get_db)):
    run = db.query(MetricRun).order_by(MetricRun.created_at.desc()).first()
    if not run:
        return None
    return {
        "id": run.id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "dataset_name": run.dataset_name,
        "precision": run.precision,
        "recall": run.recall,
        "f1": run.f1,
        "docs_per_sec": run.docs_per_sec,
        "false_negative_rate": run.false_negative_rate,
    }


# --- Optional job queue endpoints ---
@router.post("/jobs/deid")
async def queue_deid(req: DeidRequest):
    task = deid_text_task.delay(req.text, req.lang_hint)
    return {"task_id": task.id, "status": "queued"}


class EvalRequest(BaseModel):
    dataset_path: str


@router.post("/jobs/evaluate")
async def queue_evaluate(req: EvalRequest):
    task = evaluate_dataset_task.delay(req.dataset_path)
    return {"task_id": task.id, "status": "queued"}


@router.get("/jobs/{task_id}")
async def job_status(task_id: str):
    res = celery_app.AsyncResult(task_id)
    payload = {"task_id": task_id, "status": res.status}
    if res.successful():
        payload["result"] = res.result
    elif res.failed():
        payload["error"] = str(res.result)
    return payload
