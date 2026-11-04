"""Phase 4 driver (notes/prereg.md): run configs B0/B1/B2 × k runs on the first N tasks of the fixed order.

Order is task-major, then config, then run index (prereg §4). Each (config, run, task) gets its own results dir,
so the driver is resumable: finished units are skipped. A unit whose process fails or writes no result is
retried once; if the retry fails too it is recorded as unsolved with the error (prereg §3).

Needs llama-server serving the model alias at LOCAL_INFERENCE_URL (default http://127.0.0.1:8089/v1).
Run from app/ with the harness venv:
  ../.venv-harness/bin/python -m runner.phase4 --n 80                       # main runs
  ../.venv-harness/bin/python -m runner.phase4 --timing                     # B1, run 1, first 5 tasks
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ORDER = Path("results/phase4_task_order.txt")
CONFIGS = {
    "B0": dict(submission="submissions/b0", graph_dir="data/graphs", tasks="data/tasks.jsonl"),
    "B1": dict(submission="submissions/b1", graph_dir="data/graphs", tasks="data/tasks.jsonl"),
    "B2": dict(submission="submissions/b2", graph_dir="data/graphs_repaired", tasks="data/tasks_b2.jsonl"),
}


def result(out: Path, task: str) -> dict | None:
    f = out / "task_results.jsonl"
    if not f.exists():
        return None
    rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    return next((r for r in rows if r["instance_id"] == task), None)


def run_unit(cfg: str, run: int, task: str, root: Path, log) -> dict:
    out = root / cfg.lower() / f"r{run}" / task
    if (r := result(out, task)) is not None:
        return r
    c = CONFIGS[cfg]
    cmd = [sys.executable, "-m", "runner.run_eval", "--submission", c["submission"], "--results", str(out),
           "--task", task, "--tasks-path", c["tasks"], "--graph-dir", c["graph_dir"],
           "--wheels-dir", "data/wheels_plus", "--copy-wheels"]
    env = {**os.environ, "LOCAL_INFERENCE_URL": os.environ.get("LOCAL_INFERENCE_URL", "http://127.0.0.1:8089/v1")}
    for attempt in (1, 2):
        t0 = time.time()
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        (out / f"driver_attempt{attempt}.log").parent.mkdir(parents=True, exist_ok=True)
        (out / f"driver_attempt{attempt}.log").write_text(proc.stdout[-20000:] + "\n--- stderr ---\n" + proc.stderr[-20000:])
        r = result(out, task)
        print(json.dumps(dict(cfg=cfg, run=run, task=task, attempt=attempt, rc=proc.returncode,
                              wall=round(time.time() - t0, 1), resolved=r and r["resolved"])), file=log, flush=True)
        if r is not None and proc.returncode == 0:
            return r
    r = dict(instance_id=task, resolved=False, error=f"driver: failed twice (rc={proc.returncode})")
    (out / "task_results.jsonl").write_text(json.dumps(r) + "\n")
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, help="first N tasks of the prereg order")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--configs", nargs="+", default=list(CONFIGS))
    ap.add_argument("--timing", action="store_true", help="B1, run 1, first 5 tasks into results/phase4_timing")
    ap.add_argument("--root", default="results/phase4")
    ap.add_argument("--only", nargs="+", help="explicit task ids instead of the prereg order (smoke tests)")
    args = ap.parse_args()
    order = ORDER.read_text().split()
    if args.timing:
        tasks, configs, runs, root = order[:5], ["B1"], [1], Path("results/phase4_timing")
    else:
        tasks, configs, runs, root = args.only or order[: args.n], args.configs, range(1, args.k + 1), Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "driver.jsonl", "a") as log:
        for i, task in enumerate(tasks, 1):
            for cfg in configs:
                for run in runs:
                    r = run_unit(cfg, run, task, root, log)
                    print(f"[{i}/{len(tasks)}] {task} {cfg} r{run}: resolved={r['resolved']} "
                          f"dur={r.get('duration_seconds')} calls={r.get('tool_calls')}", flush=True)


if __name__ == "__main__":
    main()
