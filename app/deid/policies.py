from hashlib import sha256
from typing import Dict, List, Tuple


# --- Policy action helpers ---
def mask_value(value: str) -> str:
    return "" if value is None else ("*" * len(value))


def redact_value(label: str) -> str:
    return f"[REDACTED:{label}]"


def hash_value(value: str, salt: str, label: str) -> str:
    digest = sha256((salt + (value or "")).encode("utf-8")).hexdigest()
    return f"{label}_HASH:{digest}"


def apply_policy_span(
    text: str,
    start: int,
    end: int,
    label: str,
    policy: str,
    *,
    salt: str = "",
) -> Tuple[str, str]:
    original = text[start:end]
    if policy == "mask":
        replacement = mask_value(original)
    elif policy == "redact":
        replacement = redact_value(label)
    elif policy == "hash":
        replacement = hash_value(original, salt, label)
    else:
        # Fallback: keep original to avoid data loss on unknown policy
        replacement = original

    new_text = text[:start] + replacement + text[end:]
    return new_text, replacement


def apply_policy_matches(
    text: str,
    matches: List[Dict],
    policy: str,
    *,
    salt: str = "",
) -> Tuple[str, List[Dict]]:
    if not matches:
        return text, []
    # Apply from left to right while adjusting indices due to replacement length diffs
    matches_sorted = sorted(matches, key=lambda m: m["start"]) if matches else []
    offset = 0
    out_matches: List[Dict] = []
    current_text = text
    for m in matches_sorted:
        start = m["start"] + offset
        end = m["end"] + offset
        label = m["type"]
        updated_text, replacement = apply_policy_span(current_text, start, end, label, policy, salt=salt)
        # compute new offset
        delta = len(replacement) - (end - start)
        offset += delta
        current_text = updated_text
        m2 = dict(m)
        m2["replacement"] = replacement
        out_matches.append(m2)
    return current_text, out_matches


# --- Backwards-compatible simple tag replacements (used by current API/tests) ---
REPLACEMENTS: Dict[str, str] = {
    "EMAIL": "<EMAIL>",
    "PHONE": "<PHONE>",
    "PHONE_GR": "<PHONE>",
    "PHONE_INTL": "<PHONE>",
    "SSN": "<SSN>",
    "CREDIT_CARD": "<CREDIT_CARD>",
    "IP": "<IP>",
    "URL": "<URL>",
    "AMKA": "<AMKA>",
    "MRN": "<MRN>",
    "POSTAL_CODE_GR": "<POSTAL_CODE>",
    "GENERIC_ID": "<ID>",
}


def apply_policies(text: str, matches: List[Dict]) -> Tuple[str, List[Dict]]:
    # Sort matches by start index to reconstruct text safely
    matches_sorted = sorted(matches, key=lambda m: m["start"]) if matches else []
    result: List[Dict] = []
    last = 0
    new_text_parts: List[str] = []

    for m in matches_sorted:
        start, end, ent_type = m["start"], m["end"], m["type"]
        replacement = REPLACEMENTS.get(ent_type, f"<{ent_type}>")
        new_text_parts.append(text[last:start])
        new_text_parts.append(replacement)
        last = end
        m_copy = dict(m)
        m_copy["replacement"] = replacement
        result.append(m_copy)

    new_text_parts.append(text[last:])
    sanitized = "".join(new_text_parts)
    return sanitized, result
