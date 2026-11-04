"""C1 Auditor: measure the released code graphs against Python-AST ground truth.

Outputs (results/audit/):
  coverage.csv    one row per (commit, kind, nested, is_test): ast count, released count
  gold_sites.csv  one row per (task, gold edit site): enclosing symbol, kind, in released graph
  reach.csv       one row per task: seeds, gold symbols, hop distance to nearest gold symbol
  edges.csv       one row per commit: released edge types and how many `calls` edges are really containment
  table1.md       the per-repo summary

Run from app/: ../.venv/bin/python -m mtm.audit [graph_dir]
"""
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from mtm.ast_index import RepoIndex, index_snapshot, released_match

DATA = Path(os.environ.get("MTM_DATA", Path(__file__).resolve().parents[1] / "data"))
OUT = Path(os.environ.get("MTM_OUT", Path(__file__).resolve().parents[1] / "results" / "audit"))
MAX_HOPS = 3
# Pre-registered seed rule: an issue token seeds every node whose last id component equals it,
# ignoring tokens shorter than 3 chars and tokens that match more than MAX_SEED_FANOUT nodes.
MAX_SEED_FANOUT = 50
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def repo_short(task: dict) -> str:
    return task["instance_id"].rsplit("_", 1)[0]


def load_graph(graph_dir: Path, task: dict) -> tuple[nx.MultiDiGraph, dict[str, str]]:
    data = json.loads((graph_dir / f"{repo_short(task)}_{task['base_commit']}.json").read_text())
    return nx.node_link_graph(data, edges="edges"), {n["id"]: n.get("text") or "" for n in data["nodes"]}


def gold_lines(patch: str) -> dict[str, set[int]]:
    """Old-side line numbers each file's patch touches. Pure insertions map to the line above."""
    out: dict[str, set[int]] = defaultdict(set)
    path, old = None, 0
    for line in patch.splitlines():
        if line.startswith("--- "):
            src = line[4:].split("\t")[0].strip()
            path = None if src == "/dev/null" else src.removeprefix("a/")
        elif line.startswith("+++ "):
            if path is None:  # new file: no base symbol
                out[line[4:].split("\t")[0].strip().removeprefix("b/")].add(0)
        elif m := HUNK.match(line):
            old = int(m.group(1))
        elif path is None or line.startswith("\\"):
            continue
        elif line.startswith("-"):
            out[path].add(old)
            old += 1
        elif line.startswith("+"):
            out[path].add(max(1, old - 1))
        else:
            old += 1
    return out


def gold_symbols(idx: RepoIndex, patch: str, node_text: dict[str, str]) -> list[dict]:
    sites = {}
    for path, lines in gold_lines(patch).items():
        if not path.endswith(".py"):
            continue
        if path not in idx.by_path:
            sites[(path, None)] = dict(path=path, symbol="", kind="new_file", nested=False, flat_id="",
                                       in_released=False)
            continue
        for ln in sorted(lines):
            s = idx.enclosing(path, ln)
            if s is not None:
                sites[(path, s.id)] = dict(path=path, symbol=s.id, kind=s.kind, nested=s.nested, flat_id=s.flat_id,
                                           in_released=released_match(idx, s, node_text))
    return list(sites.values())


def seed_nodes(g: nx.MultiDiGraph, text: str) -> set[str]:
    by_name = defaultdict(set)
    for n in g.nodes:
        by_name[n.rsplit(".", 1)[-1]].add(n)
    seeds = set()
    for tok in set(IDENT.findall(text)):
        hits = by_name.get(tok, ())
        if 0 < len(hits) <= MAX_SEED_FANOUT:
            seeds |= hits
    return seeds


def hop_distance(g: nx.MultiDiGraph, seeds: set[str], targets: set[str]) -> int | None:
    """Undirected hops from any seed to any target, or None if not within MAX_HOPS."""
    if not seeds or not targets:
        return None
    dist = nx.multi_source_dijkstra_path_length(g.to_undirected(as_view=True), seeds, cutoff=MAX_HOPS)
    hits = [d for t, d in dist.items() if t in targets]
    return int(min(hits)) if hits else None


def edge_stats(g: nx.MultiDiGraph) -> dict:
    types = Counter(d.get("type", "") for _, _, d in g.edges(data=True))
    containment = sum(1 for u, v, d in g.edges(data=True)
                      if d.get("type") == "calls" and v.startswith(u + ".") and "." not in v[len(u) + 1:])
    return dict(edges=g.number_of_edges(), types=dict(types), calls_that_are_containment=containment)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main(graph_dir: str = str(DATA / "graphs")) -> None:
    gdir = Path(graph_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(l) for l in (DATA / "tasks.jsonl").open()]
    by_commit = defaultdict(list)
    for t in tasks:
        by_commit[(repo_short(t), t["base_commit"])].append(t)

    cov, gold, reach, edges = [], [], [], []
    for n, ((repo, commit), group) in enumerate(sorted(by_commit.items()), 1):
        g, node_text = load_graph(gdir, group[0])
        released = set(g.nodes)
        idx = index_snapshot(DATA / "snapshots" / f"{group[0]['instance_id']}.tgz", released)
        explained = {s.flat_id for s in idx.symbols.values()}
        flat_counts = Counter(s.flat_id for s in idx.symbols.values() if s.kind != "module")

        c = Counter()
        for s in idx.symbols.values():
            c[(s.kind, s.nested, s.is_test, "ast")] += 1
            c[(s.kind, s.nested, s.is_test, "released")] += released_match(idx, s, node_text)
        for (kind, nested, test, col), v in c.items():
            if col == "ast":
                cov.append(dict(repo=repo, commit=commit, kind=kind, nested=nested, is_test=test,
                                ast=v, released=c[(kind, nested, test, "released")]))
        edges.append(dict(repo=repo, commit=commit, nodes=len(released),
                          unexplained_nodes=len(released - explained), parse_errors=len(idx.parse_errors),
                          misqualified=sum(1 for s in idx.symbols.values()
                                           if s.kind != "module" and not s.nested and s.flat_id != s.id),
                          id_collisions=sum(v - 1 for v in flat_counts.values() if v > 1),
                          **{k: json.dumps(v) if isinstance(v, dict) else v for k, v in edge_stats(g).items()}))

        for t in group:
            sites = gold_symbols(idx, t["patch"], node_text)
            for s in sites:
                gold.append(dict(instance_id=t["instance_id"], repo=repo, **s))
            targets = {s["flat_id"] for s in sites if s["in_released"]}
            seeds = seed_nodes(g, t["problem_statement"])
            reach.append(dict(instance_id=t["instance_id"], repo=repo, n_seeds=len(seeds),
                              n_gold=len(sites), n_gold_in_graph=len(targets),
                              hops=hop_distance(g, seeds, targets)))
        print(f"[{n}/{len(by_commit)}] {repo} {commit[:8]} nodes={len(released)} tasks={len(group)}", flush=True)

    write_csv(OUT / "coverage.csv", cov)
    write_csv(OUT / "gold_sites.csv", gold)
    write_csv(OUT / "reach.csv", reach)
    write_csv(OUT / "edges.csv", edges)
    (OUT / "table1.md").write_text(table1(cov, gold, reach, edges))
    print((OUT / "table1.md").read_text())


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / b:.1f}%)" if b else "–"


def table1(cov, gold, reach, edges) -> str:
    repos = sorted({r["repo"] for r in reach}) + ["all"]
    pick = lambda rows, r: [x for x in rows if r == "all" or x["repo"] == r]
    lines = ["| repo | tasks | commits | top-level sync fn | top-level async fn | classes | modules | nested defs | "
             "edge types | `calls` that are containment | top-level defs mis-qualified | id collisions | gold sites in graph | async gold sites in graph | "
             "gold reachable ≤1 hop | ≤2 hops | ≤3 hops |", "|" + "---|" * 17]
    for r in repos:
        cv, gd, rc, ed = pick(cov, r), pick(gold, r), pick(reach, r), pick(edges, r)
        s = lambda kind, nested: (sum(x["released"] for x in cv if x["kind"] == kind and x["nested"] == nested),
                                  sum(x["ast"] for x in cv if x["kind"] == kind and x["nested"] == nested))
        nested = [s(k, True) for k in ("function", "async_function", "class")]
        types = Counter()
        for e in ed:
            types.update(json.loads(e["types"]))
        n_edges = sum(e["edges"] for e in ed)
        sites = [x for x in gd if x["kind"] != "module"]
        asy = [x for x in sites if x["kind"] == "async_function"]
        reach_k = lambda k: pct(sum(1 for x in rc if x["hops"] is not None and x["hops"] <= k), len(rc))
        lines.append("| " + " | ".join([
            r, str(len(rc)), str(len(ed)),
            pct(*s("function", False)), pct(*s("async_function", False)), pct(*s("class", False)),
            pct(*s("module", False)), pct(sum(a for a, _ in nested), sum(b for _, b in nested)),
            ", ".join(f"{k}:{v}" for k, v in types.items()),
            pct(sum(e["calls_that_are_containment"] for e in ed), n_edges),
            str(sum(e["misqualified"] for e in ed)), str(sum(e["id_collisions"] for e in ed)),
            pct(sum(x["in_released"] for x in sites), len(sites)),
            pct(sum(x["in_released"] for x in asy), len(asy)),
            reach_k(1), reach_k(2), reach_k(3)]) + " |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main(*sys.argv[1:])
