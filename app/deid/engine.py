from time import perf_counter
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings
from .recognizers import detect_entities, recognize
from .policies import apply_policies, hash_value, mask_value, redact_value


# Default mapping for actions by label
POLICY_MAP: Dict[str, str] = {
    "PERSON": "redact",
    "EMAIL": "hash",
    "PHONE_GR": "mask",
    "AMKA": "hash",
    "MRN": "hash",
    "GPE": "redact",
    "ADDRESS": "redact",
    "URL": "redact",
    "IP": "redact",
}


def _canonical_label(label: str) -> str:
    # Normalize label for display/replacement
    if label.startswith("ADDRESS"):
        return "ADDRESS"
    if label.startswith("PHONE"):
        return "PHONE"
    if "_" in label:
        return label.split("_", 1)[0]
    return label


class DeidEngine:
    def __init__(self, policy_map: Dict[str, str], salt: str, default_policy: str) -> None:
        self.policy_map = dict(policy_map or {})
        self.salt = salt or ""
        self.default_policy = default_policy

    def _resolve_policy(self, label: str) -> str:
        # Exact match
        if label in self.policy_map:
            return self.policy_map[label]
        # Variant normalization
        base = _canonical_label(label)
        if base in self.policy_map:
            return self.policy_map[base]
        # Phone fallback to PHONE_GR policy if defined
        if base == "PHONE" and "PHONE_GR" in self.policy_map:
            return self.policy_map["PHONE_GR"]
        return self.default_policy

    def deidentify(self, text: str, lang_hint: Optional[str] = None) -> Dict:
        settings = get_settings()
        if text is None:
            text = ""
        if len(text) > settings.max_text_size:
            raise ValueError(
                f"Text too long: {len(text)} chars (max {settings.max_text_size})"
            )

        t0 = perf_counter()
        entities = detect_entities(text, lang_hint=lang_hint)

        # Ensure non-overlapping spans, sorted by start
        spans = sorted(((e.start, e.end, e.label, e.text) for e in entities), key=lambda x: x[0])
        merged: List[Tuple[int, int, str, str]] = []
        last_end = -1
        for s, e, label, txt in spans:
            if s >= last_end:
                merged.append((s, e, label, txt))
                last_end = e
            else:
                # Overlap: skip lower-priority span (detect_entities already resolves priority)
                continue

        # Build result text while applying per-entity policy
        result_parts: List[str] = []
        last = 0
        results_meta: List[Dict] = []
        for start, end, label, value in merged:
            result_parts.append(text[last:start])
            action = self._resolve_policy(label)
            canon = _canonical_label(label)
            if action == "mask":
                replacement = mask_value(value)
            elif action == "redact":
                replacement = redact_value(canon)
            elif action == "hash":
                replacement = hash_value(value, self.salt, canon)
            else:
                replacement = value  # unknown action -> passthrough

            result_parts.append(replacement)
            results_meta.append({
                "label": label,
                "span": [start, end],
                "action": action,
            })
            last = end

        result_parts.append(text[last:])
        result_text = "".join(result_parts)
        elapsed_ms = int((perf_counter() - t0) * 1000)

        return {
            "original_len": len(text),
            "result_text": result_text,
            "entities": results_meta,
            "time_ms": elapsed_ms,
        }


# Backward-compatible function kept for current API/tests
def deidentify(text: str, lang: str = "en") -> Tuple[str, List[Dict]]:
    matches = recognize(text, lang)
    sanitized, entities = apply_policies(text, matches)
    return sanitized, entities
