"""Gate G2 harness check: the harness loads every repaired graph, and its neighbour tool answers on them.

Run from app/ with the harness venv: ../.venv-harness/bin/python -m runner.check_repaired
"""
import csv
import json
from pathlib import Path

from swegemma import graph as sg
from swegemma.graph import graph_utils

DATA = Path("data")
REPAIRED = DATA / "graphs_repaired"


def main() -> None:
    graphs = sorted(REPAIRED.glob("*.json"))
    for f in graphs:
        g = graph_utils.load_graph_from_json(str(f))
        assert g.number_of_nodes() > 0
    print(f"harness load_graph_from_json: {len(graphs)}/{len(graphs)} repaired graphs loaded")

    site = next(r for r in csv.DictReader(open("results/repair/gold.csv"))
                if r["kind"] == "async_function" and r["repo"] == "fastapi")
    task = next(t for t in map(json.loads, (DATA / "tasks.jsonl").open()) if t["instance_id"] == site["instance_id"])
    repo = f"fastapi_{task['base_commit']}"
    async_gold = site["symbol"]
    print("spot-check task:", site["instance_id"])
    checks = [(async_gold, None), (async_gold, "contains"), ("fastapi.routing.APIRoute", "inherits"),
              ("fastapi.security.http.HTTPBasic.__call__", "overrides"),
              ("fastapi.routing.run_endpoint_function", "calls"), ("fastapi.routing", "imports"),
              ("fastapi.routing.APIRouter.add_api_route", "calls")]
    for node, edge_type in checks:
        out = {}
        for label, gdir in (("released", DATA / "graphs"), ("repaired", REPAIRED)):
            graph_utils.clear_caches()
            try:
                res = sg.get_neighbor(node=f"{repo};{node}", max_neighbors=5, edge_type=edge_type,
                                      repo_name=repo, graph_dir=str(gdir), embeddings_dir=str(DATA / "embeddings"),
                                      use_local_storage=True)
                out[label] = list(res) if isinstance(res, list) else res
            except Exception as e:  # the harness raises on unknown nodes
                out[label] = f"{type(e).__name__}: {str(e)[:60]}"
        print(f"{node} [edge_type={edge_type}]\n  released: {out['released']}\n  repaired: {out['repaired']}")


if __name__ == "__main__":
    main()
