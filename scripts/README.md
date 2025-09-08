Synthetic dataset generation

This folder contains utilities to generate a mixed Greek/English synthetic dataset for de-identification.

Generator
- Script: `scripts/generate_synthetic.py`
- Dependencies: `faker`

Usage
- From repo root:
  - `python scripts/generate_synthetic.py --n 1000 --lang-mix 0.5`
- Output: `scripts/dataset.jsonl`

Record format (JSONL)
- Each line is a JSON object with fields:
  - `text` (string): the full note text
  - `lang` ("el" | "en"): language of the note
  - `labels` (array): list of labeled spans
    - items: `{ "start": number, "end": number, "label": string }`

Entities included
- PERSON, EMAIL, PHONE_GR, AMKA (Greek SSN), MRN, ADDRESS/ADDRESS_GR, DATE, GPE

Notes
- PHONE_GR follows Greek phone formats (optionally with `+30 ` prefix).
- AMKA is generated as 11 digits: `DDMMYY` + 5 digits.
- MRN is 6–12 characters alphanumeric with optional dashes/underscores.
- Greek addresses include tokens like `Οδός`, `Λεωφόρος`, `Πλ.`, `Οικ.`, with postal code `ΤΚ 12345`.
- English addresses are free-form (Faker) and labeled as `ADDRESS`.

