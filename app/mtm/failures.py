"""Failure taxonomy for agent runs (prereg amendment 1): why each unresolved run failed.

Classes, checked in this order on each (config, run, task) unit:
  resolved        the harness marked it resolved
  harness_error   the driver or harness recorded an error, or no test output exists
  no_patch        the agent submitted an empty patch
  broken_syntax   tests could not import the edited code: SyntaxError / IndentationError in the test log
  broken_import   tests errored at collection on an ImportError / NameError / AttributeError from the edit
  hang            the test run was killed (exit 137) or timed out
  tests_fail      tests ran and at least one failed or errored at run time

Run from app/: ../.venv/bin/python -m mtm.failures results/phase4 [more roots...]
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

CLASSES = ("resolved", "harness_error", "no_patch", "broken_syntax", "broken_import", "hang", "tests_fail")


def classify(r: dict, log: str) -> str:
    if r.get("resolved"):
        return "resolved"
    if r.get("error") or not log:
        return "harness_error"
    if not r.get("agent_patch_size"):
        return "no_patch"
    if re.search(r"\b(SyntaxError|IndentationError|TabError)\b", log):
        return "broken_syntax"
    if r.get("test_exit_code") in (2, 4) and re.search(r"\b(ImportError|ModuleNotFoundError|NameError|AttributeError)\b", log):
        return "broken_import"
    if r.get("test_exit_code") in (124, 137) or re.search(r"\bTimeout(Error|Expired)?\b", log):
        return "hang"
    return "tests_fail"


def units(root: Path):
    """Yield (config, run, task, result, test log) for every finished unit under a phase-4 style root."""
    for f in sorted(root.glob("*/r*/*/task_results.jsonl")):
        unit = f.parent
        task = unit.name
        r = json.loads(f.read_text().splitlines()[0])
        log = unit / "test_outputs" / f"{task}.log"
        yield unit.parts[-3].upper(), unit.parts[-2], task, r, log.read_text(errors="replace") if log.exists() else ""


def main(*roots: str) -> None:
    rows = [dict(config=c, run=run, task=t, failure=classify(r, log)) for root in roots
            for c, run, t, r, log in units(Path(root))]
    by = Counter((r["config"], r["failure"]) for r in rows)
    configs = sorted({r["config"] for r in rows})
    print("| failure | " + " | ".join(configs) + " |")
    print("|" + "---|" * (len(configs) + 1))
    for k in CLASSES:
        print(f"| {k} | " + " | ".join(str(by[(c, k)]) for c in configs) + " |")
    print(f"| total | " + " | ".join(str(sum(by[(c, k)] for k in CLASSES)) for c in configs) + " |")
    for r in rows:
        print(json.dumps(r), file=sys.stderr)


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["results/phase4"]))
