"""Join the gold and empty-patch sweeps into the locally verifiable task set.

verifiable = gold patch resolves AND empty patch does not.
Writes results/verifiable_tasks{suffix}.txt and results/validity{suffix}.md.
Run from app/: ../.venv/bin/python -m mtm.validity [suffix]   (suffix "" = official wheels, "_plus" = wheels_plus)
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

RES = Path(__file__).resolve().parents[1] / "results"


def load(name: str) -> dict[str, dict]:
    rows = (json.loads(l) for l in (RES / name / "task_results.jsonl").open())
    return {r["instance_id"]: r for r in rows}


def failure_reason(r: dict, gold_dir: str = "gold") -> str:
    log = RES / gold_dir / "test_outputs" / f"{r['instance_id']}.log"
    out = log.read_text(errors="replace") if log.exists() else ""
    if m := re.search(r"No module named '([^']+)'", out):
        return f"env: missing wheel `{m.group(1)}`"
    if "fixture 'httpbin'" in out:
        return "env: missing wheel `pytest-httpbin`"
    if m := re.search(r"(AttributeError: module '[^']+' has no attribute '[^']+')", out):
        return f"env: {m.group(1)}"
    if r.get("error"):
        return "harness: " + r["error"].splitlines()[0][:70]
    return "tests fail with gold patch"


def main(suffix: str = "") -> None:
    gold, empty = load(f"gold{suffix}"), load(f"empty{suffix}")
    rows, ok = [], []
    for iid in sorted(gold):
        g, e = gold[iid], empty.get(iid)
        status = ("verifiable" if g["resolved"] and e is not None and not e["resolved"]
                  else "gold fails" if not g["resolved"]
                  else "empty passes" if e is not None else "no empty run")
        if status == "verifiable":
            ok.append(iid)
        rows.append((iid, iid.rsplit("_", 1)[0], status, "" if g["resolved"] else failure_reason(g, f"gold{suffix}")))

    (RES / f"verifiable_tasks{suffix}.txt").write_text("\n".join(ok) + "\n")
    by_repo = Counter((r[1], r[2]) for r in rows)
    repos = sorted({r[1] for r in rows})
    statuses = ["verifiable", "gold fails", "empty passes", "no empty run"]
    md = ["| repo | tasks | " + " | ".join(statuses) + " |", "|" + "---|" * (len(statuses) + 2)]
    for repo in repos + ["all"]:
        n = lambda s: sum(v for (rp, st), v in by_repo.items() if st == s and repo in (rp, "all"))
        md.append(f"| {repo} | {sum(n(s) for s in statuses)} | " + " | ".join(str(n(s)) for s in statuses) + " |")
    md += ["", "Gold-patch failure reasons:", ""]
    md += [f"- {reason}: {c}" for reason, c in Counter(r[3] for r in rows if r[3]).most_common()]
    (RES / f"validity{suffix}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nverifiable: {len(ok)}/{len(rows)}")


if __name__ == "__main__":
    main(*sys.argv[1:])
