"""Export the public resource: our derived typed-graph structure, labels and tables, with no Competition Data.

The competition rules forbid redistributing Competition Data (graphs, snapshots, task texts) to non-participants.
So the export holds only what we derived:
  typed/<repo>_<commit>.json.gz   added nodes (id, kind, file, line; no source text) and added typed edges,
                                  plus kind/file/line for released node ids
  labels/, tables/                gold-site labels (paths + symbol ids), localization results, audit/repair tables
  code/                           the mtm package, which rebuilds the full repaired graphs from the competition data
A participant gets the full drop-in graphs with `python -m mtm.repair` on the competition data, or by merging
typed/ into the released graphs and filling new-node text from the snapshot (merge_typed below).

Run from app/: ../.venv/bin/python -m mtm.export_dataset  -> ../release/gemma4-swe-typed-graphs/
"""
import gzip
import json
import shutil
from pathlib import Path

from mtm.audit import DATA

OUT = Path("../release/gemma4-swe-typed-graphs")
TABLES = ["results/audit/table1.md", "results/audit/coverage.csv", "results/audit/edges.csv", "results/audit/reach.csv",
          "results/repair/table_g2.md", "results/repair/repair.csv", "results/repair/superset.csv",
          "results/repair/reach.csv", "results/localize/table2.md", "results/localize/loro_choice.csv",
          "results/localize/mcnemar.md", "results/validity.md", "results/validity_plus.md",
          "results/verifiable_tasks_plus.txt", "results/phase4_task_order.txt"]
LABELS = ["results/audit/gold_sites.csv", "results/repair/gold.csv", "results/localize/per_task.csv",
          "results/localize/hints.csv"]
CODE = ["mtm/__init__.py", "mtm/ast_index.py", "mtm/audit.py", "mtm/repair.py", "mtm/repair_report.py",
        "mtm/localize.py", "mtm/mcnemar.py", "mtm/hints.py", "mtm/export_dataset.py"]


def delta(released: dict, repaired: dict) -> dict:
    rel_ids = {n["id"] for n in released["nodes"]}
    rel_edges = {(e["source"], e["target"], e["type"], e.get("key")) for e in released["edges"]}
    attrs = lambda n: {k: n[k] for k in ("kind", "file", "line") if k in n}
    return {
        "added_nodes": [{"id": n["id"], **attrs(n)} for n in repaired["nodes"] if n["id"] not in rel_ids],
        "released_node_attrs": {n["id"]: attrs(n) for n in repaired["nodes"] if n["id"] in rel_ids and attrs(n)},
        "added_edges": [[e["type"], e["source"], e["target"], e["key"]] for e in repaired["edges"]
                        if (e["source"], e["target"], e["type"], e.get("key")) not in rel_edges],
    }


def merge_typed(released: dict, d: dict, text_of=lambda node: "") -> dict:
    """Released graph + typed delta -> repaired graph. `text_of(node)` supplies new-node text (from the snapshot)."""
    nodes = [dict(n, **d["released_node_attrs"].get(n["id"], {})) for n in released["nodes"]]
    nodes += [{"name": n["id"], "text": text_of(n), **n} for n in d["added_nodes"]]
    edges = [dict(e) for e in released["edges"]] + [{"type": t, "source": s, "target": v, "key": k}
                                                   for t, s, v, k in d["added_edges"]]
    return {**released, "nodes": nodes, "edges": edges}


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "typed").mkdir(parents=True)
    n_nodes = n_edges = 0
    for rep in sorted((DATA / "graphs_repaired").glob("*.json")):
        released = json.loads((DATA / "graphs" / rep.name).read_text())
        d = delta(released, json.loads(rep.read_text()))
        n_nodes += len(d["added_nodes"])
        n_edges += len(d["added_edges"])
        with gzip.open(OUT / "typed" / f"{rep.stem}.json.gz", "wt") as f:
            json.dump(d, f)
    for sub, files in (("tables", TABLES), ("labels", LABELS), ("code", CODE)):
        for f in files:
            dst = OUT / sub / (f if sub == "code" else Path(f).name)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, dst)
    print(f"typed deltas: {len(list((OUT / 'typed').glob('*.gz')))} commits, +{n_nodes} nodes, +{n_edges} edges")


if __name__ == "__main__":
    main()
