import os
import pytest

from app.deid.recognizers import detect_entities


def _labels(ents):
    return {e.label for e in ents}


@pytest.mark.skipif(os.environ.get("SKIP_NER") == "1", reason="NER skipped")
def test_detect_entities_en_el(sample_texts):
    ents_en = detect_entities(sample_texts["en"], lang_hint="en")
    labs_en = _labels(ents_en)
    assert {"EMAIL", "URL", "IP"}.issubset(labs_en)
    assert any(l in labs_en for l in ("PHONE_GR", "PHONE_INTL"))

    ents_el = detect_entities(sample_texts["el"], lang_hint="el")
    labs_el = _labels(ents_el)
    assert "EMAIL" in labs_el
    assert any(l in labs_el for l in ("PHONE_GR", "PHONE_INTL"))
    assert "AMKA" in labs_el


def test_mrn_overdetection_guard(sample_texts):
    ents = detect_entities(sample_texts["en"], lang_hint="en")
    mrns = [e for e in ents if e.label == "MRN"]
    assert len(mrns) == 1
    assert mrns[0].text.upper() == "ABCD_778899"


def test_greek_address_heuristic(sample_texts):
    ents = detect_entities(sample_texts["el"], lang_hint="el")
    labs = _labels(ents)
    assert "ADDRESS_GR" in labs or "POSTAL_CODE_GR" in labs
