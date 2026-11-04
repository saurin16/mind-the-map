"""Exact McNemar tests on paired per-task localization hits (Table 2, exploratory, unadjusted).

Also the C4/BM25 top-file agreement split used for B2's confidence label.
Run from app/: ../.venv/bin/python -m mtm.mcnemar   -> results/localize/mcnemar.md
"""
import csv
import json
from collections import defaultdict

from scipy.stats import binomtest

from mtm.localize import OUT

PAIRS = [("c4", "grep", "file@5"), ("c4", "grep", "file@10"),
         ("c4", "bm25", "file@5"), ("c4", "bm25", "file@10"),
         ("c4", "c4_released", "file@5"), ("c4", "c4_released", "file@10"),
         ("repaired_2hop", "released_2hop", "sym_2hop@5"), ("repaired_2hop", "released_2hop", "file@5")]


def mcnemar(a: list[bool], b: list[bool]) -> tuple[int, int, float]:
    only_a = sum(x and not y for x, y in zip(a, b))
    only_b = sum(y and not x for x, y in zip(a, b))
    n = only_a + only_b
    return only_a, only_b, binomtest(only_a, n).pvalue if n else 1.0


def main() -> None:
    rows = defaultdict(dict)
    for r in csv.DictReader(open(OUT / "per_task.csv")):
        rows[r["method"]][r["instance_id"]] = r
    lines = ["| A | B | metric | n | A only | B only | p (exact) |", "|---|---|---|---|---|---|---|"]
    for a, b, m in PAIRS:
        ids = sorted(set(rows[a]) & set(rows[b]))
        x = [rows[a][i][m] == "True" for i in ids]
        y = [rows[b][i][m] == "True" for i in ids]
        oa, ob, p = mcnemar(x, y)
        lines.append(f"| {a} | {b} | {m} | {len(ids)} | {oa} | {ob} | {p:.3f} |")
    agree = defaultdict(list)
    for i, r in rows["c4"].items():
        bm = rows["bm25"].get(i)
        if bm:
            same = json.loads(r["top_files"])[:1] == json.loads(bm["top_files"])[:1] and json.loads(r["top_files"])
            agree[bool(same)].append(r["file@1"] == "True")
    lines += ["", "| C4 top file == BM25 top file | n | C4 file Hit@1 |", "|---|---|---|"]
    for k in (True, False):
        lines.append(f"| {k} | {len(agree[k])} | {sum(agree[k])}/{len(agree[k])} ({100 * sum(agree[k]) / len(agree[k]):.1f}%) |")
    (OUT / "mcnemar.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
