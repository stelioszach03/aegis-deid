import re

from app.deid.regex_rules import EMAIL, PHONE_GR, AMKA, MRN, URL, IP


def test_email_varieties():
    cases = [
        "john@example.com",
        "john.doe@example.com",
        "john_doe+tag@example.co.uk",
        "x@y.z"
    ]
    for c in cases:
        assert EMAIL.search(c)
    assert EMAIL.search("not-an-email") is None


def test_phone_gr_variants_and_rejects():
    positives = [
        "+30 2101234567",
        "+30 210 123 4567",
        "210 123 4567",
        "6912345678",
        "+30 69 1234 5678",
    ]
    for p in positives:
        assert PHONE_GR.search(p), p
    negatives = ["12345", "+30 123 45", "+3069"]
    for n in negatives:
        assert PHONE_GR.search(n) is None


def test_amka_restrictions():
    assert AMKA.search("ΑΜΚΑ 12039912345")
    assert AMKA.search("1203991234") is None  # 10 digits


def test_mrn_strict_accept_reject():
    accepts = ["ZXCV-778899", "ABCD_778899", "AB123456"]
    for a in accepts:
        assert MRN.search(a)
    rejects = ["Athens", "Patient", "ABC", "123456"]
    for r in rejects:
        assert MRN.search(r) is None


def test_url_and_ip():
    assert URL.search("https://example.org/path?q=1")
    assert IP.search("Client 192.168.1.10 end")
    assert URL.search("no url here") is None
    assert IP.search("999.999.999.999")  # regex allows but not validated semantically

