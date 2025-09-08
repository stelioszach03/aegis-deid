import json
import subprocess
from pathlib import Path

import pytest


def _db_available() -> bool:
    try:
        from sqlalchemy import create_engine
        from app.core.config import get_settings

        eng = create_engine(get_settings().postgres_dsn, future=True)
        with eng.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False


def test_generate_synthetic_creates_jsonl(tmp_path):
    out_dir = Path("scripts")
    cmd = ["python", "scripts/generate_synthetic.py", "--n", "20", "--lang-mix", "0.5"]
    subprocess.run(cmd, check=True)
    out = out_dir / "dataset.jsonl"
    assert out.exists()
    # Check first few lines have required fields
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 10
    rec = json.loads(lines[0])
    assert "text" in rec and "lang" in rec and "labels" in rec


@pytest.mark.usefixtures("db_setup")
def test_evaluate_script_summary_and_optional_db(tmp_path):
    # Ensure dataset exists
    subprocess.run(["python", "scripts/generate_synthetic.py", "--n", "10", "--lang-mix", "0.5"], check=True)
    out_summary = Path("scripts") / "summary.json"
    cmd = ["python", "scripts/evaluate.py", "--dataset", "scripts/dataset.jsonl", "--out", str(out_summary)]
    if _db_available():
        cmd.append("--write-db")
    subprocess.run(cmd, check=True)
    assert out_summary.exists()
    summary = json.loads(out_summary.read_text(encoding="utf-8"))
    assert "docs" in summary and summary["docs"] > 0
    assert "per_label" in summary

