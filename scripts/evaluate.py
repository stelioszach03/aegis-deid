#!/usr/bin/env python3
"""
Evaluate detector on a JSONL dataset of labeled spans.

Input record format (one JSON per line):
  {
    "text": "...",
    "lang": "el" | "en",
    "labels": [{"start": int, "end": int, "label": str}]
  }

Outputs:
  - Prints a tabular per-label report with TP/FP/FN, P/R/F1, and FNR
  - Writes a JSON summary with per-label, micro, and macro metrics
  - Optionally writes results to DB (MetricRun)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

# Ensure project root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.deid.recognizers import detect_entities  # noqa: E402
from app.db.session import session_scope  # noqa: E402
from app.db.crud import create_metric_run  # noqa: E402


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    label: str


def load_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                print(f"Skipping invalid JSON at line {i}")
                continue


def f1_score(p: float, r: float) -> float:
    return 0.0 if (p + r) == 0 else (2 * p * r) / (p + r)


def evaluate(dataset_path: Path, out_path: Optional[Path] = None, write_db: bool = False):
    tps: Dict[str, int] = defaultdict(int)
    fps: Dict[str, int] = defaultdict(int)
    fns: Dict[str, int] = defaultdict(int)

    labels_present: Set[str] = set()

    n_docs = 0
    t0 = time.perf_counter()
    for rec in load_jsonl(dataset_path):
        text = rec.get("text", "") or ""
        lang = rec.get("lang") or None
        gold_list = rec.get("labels", []) or []
        gold: Set[Tuple[int, int, str]] = set()
        for item in gold_list:
            try:
                s = int(item["start"])  # type: ignore[index]
                e = int(item["end"])  # type: ignore[index]
                lab = str(item["label"])  # type: ignore[index]
            except Exception:
                continue
            gold.add((s, e, lab))
            labels_present.add(lab)

        preds_ents = detect_entities(text, lang_hint=lang)
        preds: Set[Tuple[int, int, str]] = {
            (e.start, e.end, e.label) for e in preds_ents
        }
        for (_, _, lab) in preds:
            labels_present.add(lab)

        # Count
        matched = gold.intersection(preds)
        for (_, _, lab) in matched:
            tps[lab] += 1

        for (_, _, lab) in preds.difference(matched):
            fps[lab] += 1

        for (_, _, lab) in gold.difference(matched):
            fns[lab] += 1

        n_docs += 1

    elapsed = time.perf_counter() - t0
    docs_per_sec = (n_docs / elapsed) if elapsed > 0 else 0.0

    # Per-label metrics
    per_label: Dict[str, Dict[str, float]] = {}
    all_labels = sorted(labels_present)
    for lab in all_labels:
        tp, fp, fn = tps.get(lab, 0), fps.get(lab, 0), fns.get(lab, 0)
        p = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        r = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = f1_score(p, r)
        fnr = (fn / (tp + fn)) if (tp + fn) > 0 else 0.0
        per_label[lab] = {
            "precision": p,
            "recall": r,
            "f1": f1,
            "false_negative_rate": fnr,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }

    # Micro
    tp_sum = sum(tps.values())
    fp_sum = sum(fps.values())
    fn_sum = sum(fns.values())
    p_micro = (tp_sum / (tp_sum + fp_sum)) if (tp_sum + fp_sum) > 0 else 0.0
    r_micro = (tp_sum / (tp_sum + fn_sum)) if (tp_sum + fn_sum) > 0 else 0.0
    f1_micro = f1_score(p_micro, r_micro)
    fnr_overall = (fn_sum / (tp_sum + fn_sum)) if (tp_sum + fn_sum) > 0 else 0.0

    # Macro over labels with support in gold (tp+fn > 0)
    labels_with_support = [lab for lab in all_labels if (tps.get(lab, 0) + fns.get(lab, 0)) > 0]
    if labels_with_support:
        p_macro = sum(per_label[lab]["precision"] for lab in labels_with_support) / len(labels_with_support)
        r_macro = sum(per_label[lab]["recall"] for lab in labels_with_support) / len(labels_with_support)
        f1_macro = sum(per_label[lab]["f1"] for lab in labels_with_support) / len(labels_with_support)
    else:
        p_macro = r_macro = f1_macro = 0.0

    # Print table
    def fmt(x: float) -> str:
        return f"{x:.3f}"

    print("")
    print(f"Evaluated {n_docs} docs in {elapsed:.2f}s | {docs_per_sec:.1f} docs/sec")
    print("")
    header = f"{'LABEL':20} TP    FP    FN    P      R      F1     FNR"
    print(header)
    print("-" * len(header))
    for lab in all_labels:
        m = per_label[lab]
        print(
            f"{lab:20} {m['tp']:5d} {m['fp']:5d} {m['fn']:5d} "
            f"{fmt(m['precision']):>6} {fmt(m['recall']):>6} {fmt(m['f1']):>6} {fmt(m['false_negative_rate']):>6}"
        )
    print("-" * len(header))
    print(
        f"{'micro':20} {tp_sum:5d} {fp_sum:5d} {fn_sum:5d} "
        f"{fmt(p_micro):>6} {fmt(r_micro):>6} {fmt(f1_micro):>6} {fmt(fnr_overall):>6}"
    )
    print(
        f"{'macro':20} {'-':>5} {'-':>5} {'-':>5} "
        f"{fmt(p_macro):>6} {fmt(r_macro):>6} {fmt(f1_macro):>6} {'-':>6}"
    )

    # Write summary JSON
    summary = {
        "dataset": str(dataset_path),
        "docs": n_docs,
        "elapsed_sec": elapsed,
        "docs_per_sec": docs_per_sec,
        "per_label": per_label,
        "micro": {"precision": p_micro, "recall": r_micro, "f1": f1_micro},
        "macro": {"precision": p_macro, "recall": r_macro, "f1": f1_macro},
        "false_negative_rate": {**{k: v["false_negative_rate"] for k, v in per_label.items()}, "overall": fnr_overall},
    }

    if out_path is None:
        out_path = dataset_path.with_suffix(dataset_path.suffix + ".summary.json")
    with Path(out_path).open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nWrote summary to {out_path}")

    # Optionally write to DB
    if write_db:
        precision_j = {**{k: v["precision"] for k, v in per_label.items()}, "micro": p_micro, "macro": p_macro}
        recall_j = {**{k: v["recall"] for k, v in per_label.items()}, "micro": r_micro, "macro": r_macro}
        f1_j = {**{k: v["f1"] for k, v in per_label.items()}, "micro": f1_micro, "macro": f1_macro}
        fnr_j = {**{k: v["false_negative_rate"] for k, v in per_label.items()}, "overall": fnr_overall}
        with session_scope() as db:
            run = create_metric_run(
                db,
                dataset_name=str(dataset_path),
                precision=precision_j,
                recall=recall_j,
                f1=f1_j,
                docs_per_sec=docs_per_sec,
                false_negative_rate=fnr_j,
            )
            print(f"Saved MetricRun id={run.id}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate detector against JSONL dataset")
    parser.add_argument("--dataset", type=str, default=str(Path(__file__).resolve().parent / "dataset.jsonl"))
    parser.add_argument("--out", type=str, default=None, help="Path to write JSON summary")
    parser.add_argument("--write-db", action="store_true", help="Store metrics to DB")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    out_path = Path(args.out) if args.out else None
    evaluate(dataset_path, out_path=out_path, write_db=args.write_db)


if __name__ == "__main__":
    main()
