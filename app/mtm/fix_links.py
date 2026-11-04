"""Restore the hard-linked graph/embedding files that the Kaggle zip ships as 0-byte copies.

Each commit has one readable file; task-named and commit-named siblings point to it.
Group files by base_commit (from tasks.jsonl) and copy the non-empty member over empty ones.
"""
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path


def main(data_dir: str = "app/data") -> None:
    data = Path(data_dir)
    tasks = [json.loads(line) for line in (data / "tasks.jsonl").open()]
    for sub, ext in (("graphs", ".json"), ("embeddings", ".npz")):
        groups = defaultdict(set)
        for t in tasks:
            short = t["instance_id"].rsplit("_", 1)[0]
            commit_name = f"{short}_{t['base_commit']}{ext}"
            groups[t["base_commit"]] |= {f"{t['instance_id']}{ext}", commit_name}
        fixed = missing = 0
        for commit, names in groups.items():
            paths = [data / sub / n for n in names]
            good = [p for p in paths if p.exists() and p.stat().st_size > 0]
            if not good:
                missing += 1
                print(f"[{sub}] no readable file for {commit}: {sorted(names)}")
                continue
            for p in paths:
                if not p.exists() or p.stat().st_size == 0:
                    shutil.copyfile(good[0], p)
                    fixed += 1
        empty = sum(1 for p in (data / sub).iterdir() if p.stat().st_size == 0)
        total = sum(1 for _ in (data / sub).iterdir())
        print(f"{sub}: groups={len(groups)} fixed={fixed} unrecoverable={missing} files={total} empty_after={empty}")


if __name__ == "__main__":
    main(*sys.argv[1:])
