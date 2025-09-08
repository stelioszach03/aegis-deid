from typing import Optional

from fastapi import Header, HTTPException

from app.main import app
from app.api.security import require_api_key


def test_401_invalid_api_key():
    # Override dependency to enforce a fixed API key for this test only
    async def require_fixed_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
        if x_api_key != "secret":
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    app.dependency_overrides[require_api_key] = require_fixed_key
    try:
        from fastapi.testclient import TestClient

        client = TestClient(app)
        # Missing header → 401
        r = client.get("/api/v1/config")
        assert r.status_code == 401
        # Wrong key → 401
        r = client.get("/api/v1/config", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401
        # Correct key → 200
        r = client.get("/api/v1/config", headers={"X-API-Key": "secret"})
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(require_api_key, None)


def test_429_rate_limit():
    from fastapi.testclient import TestClient

    client = TestClient(app)
    payload = {"text": "Email a@b.com", "lang_hint": "en"}
    status_codes = []
    # default limit is 30/min for /deid; send 35 requests
    for _ in range(35):
        r = client.post("/api/v1/deid", json=payload)
        status_codes.append(r.status_code)
    assert 429 in status_codes

