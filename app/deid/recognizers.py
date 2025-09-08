from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import re

try:
    import spacy  # type: ignore
except Exception:  # pragma: no cover - spaCy optional at runtime
    spacy = None  # type: ignore

try:
    from .regex_rules import PATTERNS  # preferred: prioritized patterns
except Exception:  # fallback
    from .regex_rules import RULES as _RULES
    PATTERNS = [(k, v, 0) for k, v in _RULES.items()]


@dataclass
class Entity:
    start: int
    end: int
    text: str
    label: str
    detector: str  # "spacy" | "regex"


_NLP_EN = None
_NLP_EL = None


def _get_nlp(lang: str):
    global _NLP_EN, _NLP_EL
    if spacy is None:
        return None
    if lang == "en":
        if _NLP_EN is None:
            try:
                _NLP_EN = spacy.load(
                    "en_core_web_sm", disable=["tagger", "lemmatizer", "textcat", "parser"]
                )
            except Exception:
                _NLP_EN = None
        return _NLP_EN
    if lang == "el":
        if _NLP_EL is None:
            try:
                _NLP_EL = spacy.load(
                    "el_core_news_sm", disable=["tagger", "lemmatizer", "textcat", "parser"]
                )
            except Exception:
                _NLP_EL = None
        return _NLP_EL
    return None


def _spacy_entities(text: str, lang_hint: Optional[str]) -> List[Entity]:
    ents: List[Entity] = []
    labels = {"PERSON", "ORG", "GPE", "LOC", "DATE"}
    langs = [lang_hint] if lang_hint in {"en", "el"} else ["en", "el"]
    for lang in langs:
        nlp = _get_nlp(lang)
        if nlp is None:
            continue
        doc = nlp(text)
        for e in doc.ents:
            if e.label_ in labels:
                ents.append(Entity(start=e.start_char, end=e.end_char, text=e.text, label=e.label_, detector="spacy"))
    return ents


def _regex_entities(text: str) -> List[Entity]:
    ents: List[Entity] = []
    for name, pattern, _prio in sorted(PATTERNS, key=lambda t: t[2], reverse=True):
        for m in pattern.finditer(text):
            ents.append(Entity(start=m.start(), end=m.end(), text=m.group(0), label=name, detector="regex"))
    # Greek address heuristic
    greek_addr = _detect_greek_addresses(text)
    ents.extend(greek_addr)
    return ents


_GREEK_ADDR_RE = re.compile(r"\b(Οδός|Λεωφόρος|Πλ\.|Οικ\.|ΤΚ)\s+[^\n,;]{0,50}?\d+\b")


def _detect_greek_addresses(text: str) -> List[Entity]:
    res: List[Entity] = []
    for m in _GREEK_ADDR_RE.finditer(text):
        res.append(Entity(start=m.start(), end=m.end(), text=m.group(0), label="ADDRESS_GR", detector="regex"))
    return res


PRIORITY: Dict[str, int] = {
    # Prefer structured identifiers (like EMAIL) over generic NER spans on overlap
    "EMAIL": 110,
    "PERSON": 100,
    "AMKA": 95,
    "PHONE_GR": 90,
    "PHONE_INTL": 88,
    "URL": 85,
    "IP": 85,
    "DATE": 80,
    "GPE": 80,
    "LOC": 80,
    "ADDRESS": 78,
    "ADDRESS_GR": 78,
    "ORG": 75,
    "MRN": 70,
    "POSTAL_CODE_GR": 60,
    "GENERIC_ID": 50,
}


def _priority(label: str) -> int:
    return PRIORITY.get(label, 10)


def _filter_mrn_overdetections(text: str, entities: List[Entity]) -> List[Entity]:
    """
    Drop MRN candidates that:
    - have no digits (safety), OR
    - are purely alphabetic tokens, OR
    - lack nearby MRN context within the same line: one of ['MRN','Record','ID','ΑΜΚΑ','Αριθμός φακέλου'] within 12 chars to the left,
    - OR length < 6.
    Additionally, if there is no context AND the token doesn't contain '-' or '_' and doesn't mix letters+digits, reject.
    """
    out: List[Entity] = []
    lowered = text.lower()
    for e in entities:
        if e.label != "MRN":
            out.append(e)
            continue
        span_txt = e.text
        has_digit = any(ch.isdigit() for ch in span_txt)
        is_alpha_only = span_txt.isalpha()
        long_enough = len(span_txt) >= 6
        line_start = lowered.rfind("\n", 0, e.start) + 1
        left_ctx = lowered[max(line_start, e.start - 12):e.start]
        ctx_ok = any(k in left_ctx for k in ["mrn", "record", "id", "αμκα", "αριθμός φακέλου"])
        if (not has_digit) or is_alpha_only or (not long_enough and not ctx_ok):
            continue
        alnum_mix = any(c.isalpha() for c in span_txt) and any(c.isdigit() for c in span_txt)
        has_delim = ("-" in span_txt) or ("_" in span_txt)
        if not ctx_ok and not (alnum_mix and has_delim):
            continue
        out.append(e)
    return out


def _dedupe(entities: List[Entity]) -> List[Entity]:
    # Sort by priority desc, length desc, then start asc
    entities_sorted = sorted(
        entities, key=lambda e: (-_priority(e.label), -(e.end - e.start), e.start)
    )
    kept: List[Entity] = []
    for e in entities_sorted:
        overlap = False
        for k in kept:
            if not (e.end <= k.start or e.start >= k.end):
                overlap = True
                break
        if not overlap:
            kept.append(e)
    return sorted(kept, key=lambda e: e.start)


def detect_entities(text: str, lang_hint: Optional[str] = None) -> List[Entity]:
    sp = _spacy_entities(text, lang_hint)
    rx = _regex_entities(text)
    combined = sp + rx
    combined = _filter_mrn_overdetections(text, combined)
    return _dedupe(combined)


def recognize(text: str, lang: str = "en") -> List[Dict]:
    # Compatibility layer to return dicts expected by engine/apply_policies
    ents = detect_entities(text, lang_hint=lang)
    out: List[Dict] = []
    for e in ents:
        out.append({"type": e.label, "start": e.start, "end": e.end, "value": e.text})
    return out
