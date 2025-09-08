import re
from typing import List, Tuple

# RFC-lite email pattern
EMAIL = re.compile(
    r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b"
)

# Phones
# Ensure escaped plus and flexible spacing after country code
PHONE_GR = re.compile(r"\b(?:\+30\s*)?(?:2(?:\s*\d){9}|69(?:\s*\d){8})\b")
PHONE_INTL = re.compile(r"\b\+\d{7,15}\b")

# Greek SSN (AMKA): DDMMYY + 5 digits
AMKA = re.compile(r"\b((?:0[1-9]|[12]\d|3[01])(?:0[1-9]|1[0-2])\d{2}\d{5})\b")

# Medical Record Number (stricter; requires letters+digits and structure)
MRN = re.compile(
    r"\b(?:[A-Z]{2,6}[A-Z0-9]{0,4}[-_][0-9]{4,8}|[A-Z]{2,6}[-_][0-9]{4,10}|[A-Z]{2,6}[0-9]{4,10})\b",
    re.IGNORECASE,
)

# URLs and IPs
URL = re.compile(r"\bhttps?://[^\s<>\"]+\b")
IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# Greek postal code
POSTAL_CODE_GR = re.compile(r"\b\d{5}\b")

# Generic ID like "ID: ABC-12345"
GENERIC_ID = re.compile(r"\bID:\s*[A-Za-z0-9][A-Za-z0-9\-]{3,}\b")


# Expose a prioritized list of (label, pattern, priority)
PATTERNS: List[Tuple[str, re.Pattern, int]] = [
    ("EMAIL", EMAIL, 100),
    ("PHONE_GR", PHONE_GR, 95),
    ("PHONE_INTL", PHONE_INTL, 90),
    ("AMKA", AMKA, 85),
    ("MRN", MRN, 80),
    ("URL", URL, 70),
    ("IP", IP, 60),
    ("POSTAL_CODE_GR", POSTAL_CODE_GR, 50),
    ("GENERIC_ID", GENERIC_ID, 40),
]

# Backwards-compatible dict form (label -> pattern)
RULES = {label: pattern for label, pattern, _ in PATTERNS}
