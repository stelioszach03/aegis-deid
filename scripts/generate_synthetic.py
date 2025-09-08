#!/usr/bin/env python3
"""
Generate a mixed EL/EN synthetic dataset with labeled spans.

Outputs JSONL records like:
 {"text": ..., "lang": "el"|"en", "labels": [{"start": int, "end": int, "label": str}]}

Usage:
  python scripts/generate_synthetic.py --n 1000 --lang-mix 0.5
"""

from __future__ import annotations

import argparse
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from faker import Faker


@dataclass
class Span:
    start: int
    end: int
    label: str


def gen_phone_gr() -> str:
    # Either landline 2XXXXXXXXX (10 digits) or mobile 69XXXXXXXX (10 digits), optional +30 prefix
    if random.random() < 0.5:
        core = "2" + "".join(random.choice("0123456789") for _ in range(9))
    else:
        core = "69" + "".join(random.choice("0123456789") for _ in range(8))
    if random.random() < 0.3:
        return "+30 " + core
    return core


def gen_amka() -> str:
    # DDMMYY + 5 digits
    dd = random.randint(1, 28)
    mm = random.randint(1, 12)
    yy = random.randint(0, 99)
    tail = "".join(random.choice("0123456789") for _ in range(5))
    return f"{dd:02d}{mm:02d}{yy:02d}{tail}"


def gen_mrn() -> str:
    # 6-12 chars alnum with optional dashes/underscores
    length = random.randint(6, 12)
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    s = []
    for i in range(length):
        if 0 < i < length - 1 and random.random() < 0.15:
            s.append(random.choice("-_"))
        else:
            s.append(random.choice(chars))
    return "".join(s)


def gen_address_gr(fake_el: Faker) -> str:
    keyword = random.choice(["Οδός", "Λεωφόρος", "Πλ.", "Οικ."])
    street = fake_el.street_name()
    num = random.randint(1, 199)
    postal = "".join(random.choice("0123456789") for _ in range(5))
    city = fake_el.city()
    return f"{keyword} {street} {num}, ΤΚ {postal}, {city}"


def gen_address_en(fake_en: Faker) -> str:
    return fake_en.address().replace("\n", ", ")


def gen_date_el(fake_el: Faker) -> str:
    d = fake_el.date_object()
    return d.strftime("%d/%m/%Y")


def gen_date_en(fake_en: Faker) -> str:
    return fake_en.date().replace("-", "/")


def compose_note_el(fake_el: Faker) -> Tuple[str, List[Span]]:
    parts: List[str] = []
    spans: List[Span] = []
    offset = 0

    def add_text(s: str):
        nonlocal offset
        parts.append(s)
        offset += len(s)

    def add_ent(label: str, value: str):
        nonlocal offset
        start = offset
        parts.append(value)
        end = start + len(value)
        spans.append(Span(start, end, label))
        offset = end

    name = fake_el.name()
    email = fake_el.email()
    phone = gen_phone_gr()
    amka = gen_amka()
    mrn = gen_mrn()
    addr = gen_address_gr(fake_el)
    date = gen_date_el(fake_el)
    city = fake_el.city()

    add_text("Ο ασθενής ")
    add_ent("PERSON", name)
    add_text(" επικοινώνησε στο ")
    add_ent("PHONE_GR", phone)
    add_text(". ΑΜΚΑ: ")
    add_ent("AMKA", amka)
    add_text(". MRN: ")
    add_ent("MRN", mrn)
    add_text(". Email: ")
    add_ent("EMAIL", email)
    add_text(". Διεύθυνση: ")
    start_addr = offset
    add_text(addr)
    spans.append(Span(start_addr, start_addr + len(addr), "ADDRESS_GR"))
    add_text(". Ημερομηνία: ")
    add_ent("DATE", date)
    add_text(". Πόλη: ")
    add_ent("GPE", city)
    add_text(".")

    return "".join(parts), spans


def compose_note_en(fake_en: Faker) -> Tuple[str, List[Span]]:
    parts: List[str] = []
    spans: List[Span] = []
    offset = 0

    def add_text(s: str):
        nonlocal offset
        parts.append(s)
        offset += len(s)

    def add_ent(label: str, value: str):
        nonlocal offset
        start = offset
        parts.append(value)
        end = start + len(value)
        spans.append(Span(start, end, label))
        offset = end

    name = fake_en.name()
    email = fake_en.email()
    phone = gen_phone_gr()  # keep GR phones as target pattern
    amka = gen_amka()
    mrn = gen_mrn()
    addr = gen_address_en(fake_en)
    date = gen_date_en(fake_en)
    city = fake_en.city()

    add_text("Patient ")
    add_ent("PERSON", name)
    add_text(" contacted at ")
    add_ent("PHONE_GR", phone)
    add_text(". AMKA: ")
    add_ent("AMKA", amka)
    add_text(". MRN: ")
    add_ent("MRN", mrn)
    add_text(". Email: ")
    add_ent("EMAIL", email)
    add_text(". Address: ")
    start_addr = offset
    add_text(addr)
    spans.append(Span(start_addr, start_addr + len(addr), "ADDRESS"))
    add_text(". Date: ")
    add_ent("DATE", date)
    add_text(". City: ")
    add_ent("GPE", city)
    add_text(".")

    return "".join(parts), spans


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic EL/EN dataset with spans")
    parser.add_argument("--n", type=int, default=1000, help="Number of documents to generate")
    parser.add_argument("--lang-mix", type=float, default=0.5, help="Probability of Greek (el) samples [0..1]")
    args = parser.parse_args()

    fake_el = Faker("el_GR")
    fake_en = Faker("en_US")

    out_dir = Path(__file__).resolve().parent
    out_path = out_dir / "dataset.jsonl"

    rng = random.Random()
    rng.seed(1337)
    Faker.seed(1337)

    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for i in range(args.n):
            is_el = rng.random() < args.lang_mix
            if is_el:
                text, spans = compose_note_el(fake_el)
                lang = "el"
            else:
                text, spans = compose_note_en(fake_en)
                lang = "en"
            record = {
                "text": text,
                "lang": lang,
                "labels": [span.__dict__ for span in spans],
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    print(f"Wrote {count} records to {out_path}")


if __name__ == "__main__":
    main()
