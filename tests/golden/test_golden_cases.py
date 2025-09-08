import json
from pathlib import Path

from app.deid.recognizers import detect_entities


def test_golden_small_dataset_counts():
    data_path = Path(__file__).resolve().parents[1] / "data" / "dataset_small.jsonl"
    texts = []
    with data_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                texts.append(json.loads(line))

    assert len(texts) >= 2

    expected_min = [
        {"EMAIL": 1, "URL": 1, "IP": 1, "MRN": 1},
        {"EMAIL": 1, "AMKA": 1},
    ]

    for idx, (rec, exp) in enumerate(zip(texts, expected_min)):
        ents = detect_entities(rec["text"], lang_hint=rec.get("lang"))
        counts = {}
        for e in ents:
            counts[e.label] = counts.get(e.label, 0) + 1
        for label, c in exp.items():
            assert counts.get(label, 0) >= c
        if idx == 1:
            # Greek sample should have either postal code or address (dedup may drop postal)
            assert counts.get("ADDRESS_GR", 0) >= 1 or counts.get("POSTAL_CODE_GR", 0) >= 1
