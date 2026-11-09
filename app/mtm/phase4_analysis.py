"""Registered Phase 4 analysis (notes/prereg.md §5, amendments 1-3).

Analysis set: tasks in prereg order whose 9 units (3 configs x 3 runs) all have a task_results.jsonl.
Primary: per-task solve rate; B2 vs B0 and B2 vs B1, mean paired difference with a task-level bootstrap
95% CI (10,000 resamples, seed 0), exact McNemar on (task, run) pairs, Holm over the two.
Secondary (descriptive): B1 vs B0, per-repo rates, tool calls / tokens / minutes (harness duration_seconds,
amendment 3), turns before the first gold-file read, B2 by hint confidence, failure taxonomy (amendment 1).
Run from app/: ../.venv/bin/python -m mtm.phase4_analysis   -> results/phase4_analysis/{table.md,summary.json,units.csv}
"""
import ast
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

from mtm.failures import CLASSES, classify
from mtm.mcnemar import mcnemar

ROOT = Path("results/phase4")
OUT = Path("results/phase4_analysis")
DS = Path("../release/gemma4-swe-typed-graphs")
CONFIGS, RUNS = ("B0", "B1", "B2"), ("r1", "r2", "r3")


def tool_calls(step: dict) -> list[dict]:
    tc = step.get("tool_calls") or []
    return ast.literal_eval(tc) if isinstance(tc, str) else tc


def first_gold_read(trace: dict, gold: set[str]) -> int | None:
    """Agent steps (main agent and sub-agent) up to and including the first read_file of a gold-patch file."""
    n = 0
    for s in trace["steps"]:
        if s["source"] != "agent":
            continue
        n += 1
        for c in tool_calls(s):
            if c.get("function_name") == "read_file" and str(c.get("arguments", {}).get("filepath", "")).lstrip("./") in gold:
                return n
    return None


def load_units() -> list[dict]:
    gold = defaultdict(set)
    for r in csv.DictReader(open(DS / "labels/gold_sites.csv")):
        gold[r["instance_id"]].add(r["path"])
    rows = []
    for c in CONFIGS:
        for run in RUNS:
            for d in sorted((ROOT / c.lower() / run).iterdir()):
                f = d / "task_results.jsonl"
                if not f.exists():
                    continue
                r = json.loads(f.read_text().splitlines()[0])
                log = d / "test_outputs" / f"{d.name}.log"
                tr = next(iter((d / "traces").glob("*.json")), None)
                trace = json.loads(tr.read_text()) if tr else None
                rows.append(dict(config=c, run=run, task=d.name, repo=d.name.split("_")[0],
                                 resolved=bool(r["resolved"]), tool_calls=r.get("tool_calls"),
                                 minutes=r["duration_seconds"] / 60 if r.get("duration_seconds") else None,
                                 tokens=trace["final_metrics"]["total_tokens"] if trace else None,
                                 gold_read_step=first_gold_read(trace, gold[d.name]) if trace else None,
                                 failure=classify(r, log.read_text(errors="replace") if log.exists() else "")))
    return rows


def boot_ci(diffs: list[float], n: int = 10_000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    ms = sorted(mean(rng.choices(diffs, k=len(diffs))) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n) - 1]


def holm(ps: dict[str, float]) -> dict[str, float]:
    out, prev = {}, 0.0
    for i, (k, p) in enumerate(sorted(ps.items(), key=lambda kv: kv[1])):
        prev = max(prev, min(1.0, (len(ps) - i) * p))
        out[k] = prev
    return out


def main() -> None:
    order = [l.strip() for l in open("results/phase4_task_order.txt") if l.strip()]
    units = load_units()
    have = Counter(u["task"] for u in units)
    analysis = []
    for t in order:  # prereg-order prefix of complete tasks
        if have[t] != 9:
            break
        analysis.append(t)
    incomplete = sorted(t for t in have if t not in analysis)
    A = set(analysis)
    U = [u for u in units if u["task"] in A]
    res = {(u["config"], u["run"], u["task"]): u["resolved"] for u in U}
    rate = {c: {t: mean(res[(c, r, t)] for r in RUNS) for t in analysis} for c in CONFIGS}

    def compare(a: str, b: str) -> dict:
        diffs = [rate[a][t] - rate[b][t] for t in analysis]
        pairs = [(t, r) for t in analysis for r in RUNS]
        oa, ob, p = mcnemar([res[(a, r, t)] for t, r in pairs], [res[(b, r, t)] for t, r in pairs])
        lo, hi = boot_ci(diffs)
        return dict(effect=mean(diffs), ci=[lo, hi], only_a=oa, only_b=ob, p=p)

    prim = {"B2-B0": compare("B2", "B0"), "B2-B1": compare("B2", "B1")}
    for k, p in holm({k: v["p"] for k, v in prim.items()}).items():
        prim[k]["p_holm"] = p
    sec = {"B1-B0": compare("B1", "B0")}

    def desc(rows: list[dict]) -> dict:
        g = [u["gold_read_step"] for u in rows if u["gold_read_step"] is not None]
        return dict(units=len(rows), solved=sum(u["resolved"] for u in rows),
                    tool_calls=mean(u["tool_calls"] for u in rows if u["tool_calls"] is not None),
                    tokens=mean(u["tokens"] for u in rows if u["tokens"] is not None),
                    minutes=mean(u["minutes"] for u in rows if u["minutes"] is not None),
                    read_gold=len(g), steps_to_gold_median=median(g) if g else None)

    per_cfg = {c: desc([u for u in U if u["config"] == c]) for c in CONFIGS}
    per_repo = {c: {repo: desc([u for u in U if u["config"] == c and u["repo"] == repo])["solved"]
                    for repo in ("fastapi", "rich")} for c in CONFIGS}
    repo_n = Counter(t.split("_")[0] for t in analysis)
    conf = {r["instance_id"]: r["confidence"] for r in csv.DictReader(open(DS / "labels/hints.csv"))}
    b2_conf = {lab: dict(tasks=sum(conf[t] == lab for t in analysis),
                         solved=sum(u["resolved"] for u in U if u["config"] == "B2" and conf[u["task"]] == lab))
               for lab in ("high", "low")}
    fail = {c: Counter(u["failure"] for u in U if u["config"] == c) for c in CONFIGS}

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "units.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(units[0]))
        w.writeheader()
        w.writerows(sorted(units, key=lambda u: (order.index(u["task"]), u["config"], u["run"])))
    summary = dict(n_tasks=len(analysis), repos=dict(repo_n), incomplete=incomplete,
                   incomplete_units={t: have[t] for t in incomplete}, primary=prim, secondary=sec,
                   per_config=per_cfg, per_repo_solved=per_repo, b2_by_confidence=b2_conf,
                   failures={c: {k: fail[c][k] for k in CLASSES} for c in CONFIGS})
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))

    n = len(analysis)
    L = [f"Analysis set: first {n} tasks of the prereg order ({repo_n['fastapi']} fastapi, {repo_n['rich']} rich), "
         f"{3 * n} units per config. Excluded (incomplete at stop): "
         + ", ".join(f"{t} ({have[t]}/9)" for t in incomplete), "",
         "| config | solved units | solve rate | tool calls | tokens (k) | minutes | units reading a gold file | agent steps to first gold read (median) |",
         "|---|---|---|---|---|---|---|---|"]
    for c in CONFIGS:
        d = per_cfg[c]
        L.append(f"| {c} | {d['solved']}/{d['units']} | {100 * d['solved'] / d['units']:.1f}% | {d['tool_calls']:.1f} | "
                 f"{d['tokens'] / 1e3:.0f} | {d['minutes']:.1f} | {d['read_gold']}/{d['units']} | {d['steps_to_gold_median']:g} |")
    L += ["", "| comparison | effect (pp) | 95% CI (pp) | discordant (a only / b only) | McNemar p | Holm p |", "|---|---|---|---|---|---|"]
    for k, v in {**prim, **sec}.items():
        L.append(f"| {k}{'' if k in prim else ' (secondary)'} | {100 * v['effect']:+.1f} | [{100 * v['ci'][0]:+.1f}, {100 * v['ci'][1]:+.1f}] | "
                 f"{v['only_a']} / {v['only_b']} | {v['p']:.3f} | {v.get('p_holm', float('nan')):.3f} |".replace("| nan |", "| – |"))
    L += ["", "| failure | " + " | ".join(CONFIGS) + " |", "|---|---|---|---|"]
    for k in CLASSES:
        L.append(f"| {k} | " + " | ".join(str(fail[c][k]) for c in CONFIGS) + " |")
    L += ["", f"Per-repo solved units: " + "; ".join(f"{c} fastapi {per_repo[c]['fastapi']}/{3 * repo_n['fastapi']}, rich {per_repo[c]['rich']}/{3 * repo_n['rich']}" for c in CONFIGS),
          f"B2 by hint confidence: high {b2_conf['high']['solved']}/{3 * b2_conf['high']['tasks']} units, low {b2_conf['low']['solved']}/{3 * b2_conf['low']['tasks']} units"]
    (OUT / "table.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
