import re
from hashlib import sha256

import pytest

from app.deid.policies import mask_value, redact_value, hash_value
from app.deid.regex_rules import AMKA, PHONE_GR
from app.deid.recognizers import detect_entities
from app.core.config import get_settings


def test_policy_mask_preserves_length():
    original = "Sensitive123"
    masked = mask_value(original)
    assert masked == "*" * len(original)


def test_policy_redact_uses_label():
    assert redact_value("EMAIL") == "[REDACTED:EMAIL]"


def test_policy_hash_uses_salt_and_value():
    salt = "salt-xyz"
    value = "john@example.com"
    expected = sha256((salt + value).encode("utf-8")).hexdigest()
    hashed = hash_value(value, salt, "EMAIL")
    assert hashed.endswith(expected)
    assert hashed.startswith("EMAIL_HASH:")


def test_regex_amka_matches_valid_format():
    text = "ΑΜΚΑ: 13059912345"
    m = AMKA.search(text)
    assert m is not None
    assert m.group(1) == "13059912345"


def test_regex_phone_gr_matches_mobile_and_landline():
    cases = [
        "+30 2101234567",
        "2101234567",
        "6912345678",
    ]
    for c in cases:
        assert PHONE_GR.search(c) is not None
    assert PHONE_GR.search("12345") is None


def test_dedup_overlapping_phone_prefers_gr():
    # This should match both PHONE_GR and PHONE_INTL, dedupe keeps PHONE_GR
    text = "Call me at +30 2101234567 today"
    ents = detect_entities(text, lang_hint="el")
    # Ensure only one entity covers that span
    phones = [e for e in ents if e.label.startswith("PHONE")]
    assert len(phones) == 1
    assert phones[0].label == "PHONE_GR"


def test_mrn_no_overdetects_simple_english():
    txt = (
        "Patient John Papadopoulos was admitted on 2024-03-12 in Athens.\n"
        "Contact: +30 694 123 4567, john_doe+test@example.co.uk\n"
        "Record: MRN=ABCD_778899\n"
        "Refer to: https://hospital.example.org/cases/7788\n"
        "Client IP noted: 192.168.10.25\n"
    )
    ents = detect_entities(txt, lang_hint="en")
    mrns = [e for e in ents if e.label == "MRN"]
    assert len(mrns) == 1
    assert mrns[0].text.upper() == "ABCD_778899"
    assert any(e.label == "EMAIL" for e in ents)
    assert any(e.label == "URL" for e in ents)
    assert any(e.label in ("PHONE_GR", "PHONE_INTL") for e in ents)
    assert any(e.label == "IP" for e in ents)


def test_engine_changes_text_and_actions(api_client):
    txt = "Email me at alice@example.com and call +30 210 123 4567"
    r = api_client.post("/api/v1/deid", json={"text": txt, "lang_hint": "en"})
    assert r.status_code == 200
    body = r.json()
    assert body["result_text"] != txt
    actions = {e["label"]: e["action"] for e in body["entities"]}
    # Defaults: EMAIL->hash, PHONE_GR->mask
    assert actions.get("EMAIL") == "hash"
    assert actions.get("PHONE_GR") == "mask"


def test_max_text_size_guard(api_client):
    settings = get_settings()
    too_long = "A" * (settings.max_text_size + 1)
    r = api_client.post("/api/v1/deid", json={"text": too_long, "lang_hint": "en"})
    assert r.status_code == 413


def test_hash_deterministic(api_client):
    settings = get_settings()
    email = "bob@example.com"
    r = api_client.post("/api/v1/deid", json={"text": email, "lang_hint": "en"})
    assert r.status_code == 200
    body = r.json()
    from hashlib import sha256 as _sha256

    exp = _sha256((settings.deid_salt + email).encode("utf-8")).hexdigest()
    assert f"EMAIL_HASH:{exp}" in body["result_text"]
