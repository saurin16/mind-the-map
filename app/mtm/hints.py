"""Build the B2 task file: each problem statement with the C4 localizer hint prepended (notes/prereg.md §2).

Hyperparameters per repo are the leave-one-repo-out picks for the repaired graph (results/localize/loro_choice.csv),
so a task's hint is never tuned on its own repo. Confidence is "high" when C4's top file equals BM25's top file.

Run from app/: ../.venv/bin/python -m mtm.hints   -> data/tasks_b2.jsonl, results/localize/hints.csv
"""
import csv
import json
from multiprocessing import Pool

from mtm.audit import DATA, write_csv
from mtm.localize import OUT, jobs, m_bm25, m_c4, prepare

TOP_FILES, TOP_SYMBOLS = 5, 10


def chosen() -> dict[str, dict]:
    out = {}
    for r in csv.DictReader(open(OUT / "loro_choice.csv")):
        if r["graph"] == "repaired":
            types = tuple(t for t in r["types"].split("+") if t != "calls")
            out[r["held_out"]] = dict(alpha=float(r["alpha"]), mix=float(r["mix"]), types=types)
    return out


def hint(files: list[str], symbols: list[str], high: bool) -> str:
    lines = [f"<localizer confidence=\"{'high' if high else 'low'}\">",
             "Candidate edit locations from a static code-graph localizer (it can be wrong).",
             "Files: " + ", ".join(files) if files else "Files: (none found)",
             "Symbols: " + ", ".join(symbols) if symbols else "Symbols: (none found)",
             "Confidence high: start by reading the first file." if high else
             "Confidence low: treat these as hints only and confirm with search before editing.",
             "</localizer>", ""]
    return "\n".join(lines)


def commit_hints(args: tuple[str, list[dict], dict]) -> list[dict]:
    name, group, cfgs = args
    c = prepare((name, group))
    raw = {t["instance_id"]: t for t in group}
    rows = []
    for t in c.tasks:  # c.tasks keeps every task, including ones without a localizable gold file
        files, nodes, _ = m_c4(c, t, cfgs[t["repo"]])
        bm_files = m_bm25(c, t)[0]
        high = bool(files) and bool(bm_files) and files[0] == bm_files[0]
        symbols = [c.nodes[i] for i in nodes[:TOP_SYMBOLS]]
        task = dict(raw[t["instance_id"]])
        task["problem_statement"] = hint(files[:TOP_FILES], symbols, high) + task["problem_statement"]
        rows.append(dict(instance_id=t["instance_id"], repo=t["repo"], confidence="high" if high else "low",
                         files=json.dumps(files[:TOP_FILES]), symbols=json.dumps(symbols), task=json.dumps(task)))
    return rows


def main() -> None:
    cfgs = chosen()
    with Pool() as pool:
        rows = [r for rs in pool.imap_unordered(commit_hints, [(n, g, cfgs) for n, g in jobs()]) for r in rs]
    order = [json.loads(l)["instance_id"] for l in (DATA / "tasks.jsonl").open()]
    rows.sort(key=lambda r: order.index(r["instance_id"]))
    (DATA / "tasks_b2.jsonl").write_text("".join(r.pop("task") + "\n" for r in rows))
    write_csv(OUT / "hints.csv", rows)
    print(f"wrote {len(rows)} tasks; high confidence: {sum(r['confidence'] == 'high' for r in rows)}")


if __name__ == "__main__":
    main()
