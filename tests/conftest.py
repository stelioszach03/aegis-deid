import os
import json
import subprocess
from pathlib import Path
from typing import Dict

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def env() -> None:
    # Load .env if present; otherwise set sane defaults for tests
    if Path(".env").exists():
        load_dotenv(".env")
    # Ensure API key is disabled during tests (open endpoints by default)
    os.environ["API_KEY"] = ""
    # Clear cached settings so API sees updated env
    try:
        from app.core.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        _ = get_settings()
    except Exception:
        pass
    os.environ.setdefault("APP_ENV", "dev")
    # Force localhost services for tests, regardless of .env compose values
    os.environ["POSTGRES_DSN"] = "postgresql+psycopg://deid:deidpass@localhost:5432/deid"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    # Celery eager mode for unit tests
    os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")
    os.environ.setdefault("CELERY_TASK_EAGER_PROPAGATES", "1")


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


@pytest.fixture(scope="session")
def db_setup() -> None:
    if not _db_available():
        pytest.skip("Database not available; skipping DB migrations")
    # Run alembic upgrade head once per session
    subprocess.run(["alembic", "upgrade", "head"], check=True)


@pytest.fixture()
def api_client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


@pytest.fixture()
def sample_texts() -> Dict[str, str]:
    en = (
        "Patient John Papadopoulos was admitted on 2024-03-12 in Athens.\n"
        "Contact: +30 694 123 4567, john_doe+tag@example.co.uk\n"
        "Record: MRN=ABCD_778899\n"
        "Refer: https://hospital.example.org/cases/7788\n"
        "IP: 192.168.10.25\n"
    )
    el = (
        "Ο ασθενής Γιάννης Παπαδόπουλος, ΑΜΚΑ 12039912345, τηλ 210 123 4567, "
        "email giannis@example.com, διεύθυνση Οδός Σοφοκλέους 10, ΤΚ 10559, Αθήνα."
    )
    return {"en": en, "el": el}


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory) -> Path:
    root = Path(__file__).resolve().parent / "data"
    return root
