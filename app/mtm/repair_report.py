"""Gate G2 report: check the repaired graphs against the released ones and the gold edit sites.

Outputs (results/repair/):
  superset.csv  one row per commit: released nodes/edges missing or changed in the repaired graph (all 0 = pass)
  gold.csv      one row per (task, gold edit site): node present in released / repaired graph
  reach.csv     one row per task: hop distance from issue seeds to gold, released vs repaired graph
  table_g2.md   the per-repo summary

Run from app/: ../.venv/bin/python -m mtm.repair_report
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from mtm.ast_index import index_snapshot
from mtm.audit import DATA, gold_symbols, hop_distance, load_graph, pct, repo_short, seed_nodes, write_csv
from mtm.repair import EDGE_TYPES

REPAIRED = DATA / "graphs_repaired"
OUT = DATA.parent / "results" / "repair"


def superset_row(released: dict, repaired: dict) -> dict:
    rep = {n["id"]: n for n in repaired["nodes"]}
    key = lambda e: (e["source"], e["target"], e["type"], e["key"])
    rep_edges = {key(e) for e in repaired["edges"]}
    return dict(missing_nodes=sum(n["id"] not in rep for n in released["nodes"]),
                changed_nodes=sum(n["id"] in rep and (rep[n["id"]]["text"], rep[n["id"]]["name"]) != (n["text"], n["name"])
                                  for n in released["nodes"]),
                missing_edges=sum(key(e) not in rep_edges for e in released["edges"]))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(l) for l in (DATA / "tasks.jsonl").open()]
    by_commit = defaultdict(list)
    for t in tasks:
        by_commit[(repo_short(t), t["base_commit"])].append(t)

    sup, gold, reach, types = [], [], [], defaultdict(Counter)
    for n, ((repo, commit), group) in enumerate(sorted(by_commit.items()), 1):
        name = f"{repo}_{commit}.json"
        released, repaired = (json.loads((d / name).read_text()) for d in (DATA / "graphs", REPAIRED))
        sup.append(dict(repo=repo, commit=commit, **superset_row(released, repaired)))
        types[repo].update(e["type"] for e in repaired["edges"])
        g_rel, text = load_graph(DATA / "graphs", group[0])
        g_rep = nx.node_link_graph(repaired, edges="edges")
        g_nocontains = nx.MultiDiGraph()
        g_nocontains.add_nodes_from(g_rep.nodes)
        g_nocontains.add_edges_from((u, v) for u, v, d in g_rep.edges(data=True) if d["type"] != "contains")
        at = {(d.get("file"), d.get("line")): node for node, d in g_rep.nodes(data=True) if "file" in d}
        idx = index_snapshot(DATA / "snapshots" / f"{group[0]['instance_id']}.tgz", set(g_rel.nodes))

        for t in group:
            sites = [s for s in gold_symbols(idx, t["patch"], text) if s["kind"] != "new_file"]
            targets = set()
            for s in sites:
                node = at.get((s["path"], idx.symbols[s["symbol"]].def_line))
                targets.add(node)
                gold.append(dict(instance_id=t["instance_id"], repo=repo, symbol=s["symbol"], kind=s["kind"],
                                 in_released=s["in_released"], in_repaired=node is not None))
            targets.discard(None)
            rel_targets = {s["flat_id"] for s in sites if s["in_released"]}
            reach.append(dict(instance_id=t["instance_id"], repo=repo,
                              released=hop_distance(g_rel, seed_nodes(g_rel, t["problem_statement"]), rel_targets),
                              repaired=hop_distance(g_rep, seed_nodes(g_rep, t["problem_statement"]), targets),
                              repaired_no_contains=hop_distance(g_nocontains, seed_nodes(g_rep, t["problem_statement"]),
                                                                targets)))
        print(f"[{n}/{len(by_commit)}] {repo} {commit[:8]}", flush=True)

    write_csv(OUT / "superset.csv", sup)
    write_csv(OUT / "gold.csv", gold)
    write_csv(OUT / "reach.csv", reach)
    (OUT / "table_g2.md").write_text(table(sup, gold, reach, types))
    print((OUT / "table_g2.md").read_text())


def table(sup, gold, reach, types) -> str:
    repos = sorted(types) + ["all"]
    pick = lambda rows, r: [x for x in rows if r == "all" or x["repo"] == r]
    within = lambda rows, col, k: pct(sum(1 for x in rows if x[col] is not None and x[col] <= k), len(rows))
    lines = ["| repo | superset violations | gold def sites: released → repaired | module-level gold sites | async gold sites: released → repaired | "
             "gold ≤2 hops: released → repaired → repaired w/o `contains` | " + " | ".join(EDGE_TYPES) + " |",
             "|" + "---|" * (6 + len(EDGE_TYPES))]
    for r in repos:
        sp, rc = pick(sup, r), pick(reach, r)
        gd = [x for x in pick(gold, r) if x["kind"] != "module"]  # same denominator as Table 1
        md = [x for x in pick(gold, r) if x["kind"] == "module"]
        asy = [x for x in gd if x["kind"] == "async_function"]
        tc = sum((types[x] for x in (sorted(types) if r == "all" else [r])), Counter())
        lines.append("| " + " | ".join([
            r, str(sum(x["missing_nodes"] + x["changed_nodes"] + x["missing_edges"] for x in sp)),
            f"{pct(sum(x['in_released'] for x in gd), len(gd))} → {pct(sum(x['in_repaired'] for x in gd), len(gd))}",
            f"{pct(sum(x['in_released'] for x in md), len(md))} → {pct(sum(x['in_repaired'] for x in md), len(md))}",
            f"{pct(sum(x['in_released'] for x in asy), len(asy))} → {pct(sum(x['in_repaired'] for x in asy), len(asy))}",
            f"{within(rc, 'released', 2)} → {within(rc, 'repaired', 2)} → {within(rc, 'repaired_no_contains', 2)}",
            *[str(tc[k]) for k in EDGE_TYPES]]) + " |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
