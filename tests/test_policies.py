from hashlib import sha256

from app.deid.policies import mask_value, redact_value, hash_value


def test_mask_preserves_length_and_unicode():
    s = "Γιάννης123"
    masked = mask_value(s)
    assert len(masked) == len(s)
    assert set(masked) == {"*"}


def test_redact_format():
    assert redact_value("EMAIL") == "[REDACTED:EMAIL]"


def test_hash_value_stability():
    salt = "salty"
    value = "john@example.com"
    exp = sha256((salt + value).encode("utf-8")).hexdigest()
    hv = hash_value(value, salt, "EMAIL")
    assert hv == f"EMAIL_HASH:{exp}"

