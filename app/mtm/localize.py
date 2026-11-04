"""C4 Localizer and model-free localization benchmark (Table 2, Fig 3).

Methods, all given only the issue text (problem_statement) and the base snapshot:
  grep          files ranked by how many distinct code-like issue identifiers they contain (whole words)
  bm25          BM25 over file sources (files) and over graph nodes (symbols)
  released_2hop the Ali Hassan protocol on the released graph: identifier seeds, 2-hop expansion
  repaired_2hop the same protocol on the repaired graph
  c4_released   C4 (Personalized PageRank) restricted to the released graph's `calls` edges
  c4            C4 on the repaired typed graph

C4: restart distribution = identifier seeds (the audit's pre-registered seed rule) mixed with the BM25
top-k nodes; random walk over typed edges with per-type weights, both directions. Nodes are ranked by
PageRank score, files by their best node. Confidence = top file's share of the top-5 file scores.
Hyperparameters (alpha, BM25 mix, edge-type on/off) are chosen leave-one-repo-out on file Hit@5.

Labels: gold files = non-test `.py` files the gold patch edits that exist at the base commit; gold symbols =
the repaired-graph nodes enclosing the edited lines. Test files are never ranked.

Run from app/: ../.venv/bin/python -m mtm.localize
"""
import itertools
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from multiprocessing import Pool
from pathlib import Path

import networkx as nx
import numpy as np
from scipy import sparse

from mtm.ast_index import index_snapshot, is_test_path
from mtm.audit import DATA, gold_symbols, load_graph, repo_short, seed_nodes, write_csv
from mtm.repair import EDGE_TYPES

REPAIRED = DATA / "graphs_repaired"
OUT = DATA.parent / "results" / "localize"
KS = (1, 5, 10)
BM25_TOP = 20
PPR_ITERS = 40
GRID = dict(alpha=(0.3, 0.5, 0.7), mix=(0.0, 0.5, 1.0))  # mix = weight of BM25 seeds vs identifier seeds
TUNED_TYPES = ("contains", "imports", "inherits", "overrides", "tests")  # `calls` is always on

STOP = set("""a an and are as at be been but by can could did do does for from had has have how i if in into is it
its me my no not of on or our should so some such than that the their them then there these they this to too
us was we were what when where which while who why will with would you your also just like get set use used using
none true false self cls def class return import pass raise try except else elif lambda yield async await
python file line error example code issue bug fix""".split())
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def subtokens(text: str) -> list[str]:
    out = []
    for tok in IDENT.findall(text):
        for part in tok.split("_"):
            for sub in re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+", part):
                sub = sub.lower()
                if len(sub) >= 2 and sub not in STOP:
                    out.append(sub)
    return out


def code_identifiers(issue: str) -> set[str]:
    """Identifiers the issue writes as code: in backticks/fences, snake_case, camelCase, `x.y`, or `f(`."""
    spans = re.findall(r"```.*?```|`[^`\n]+`", issue, flags=re.S)
    found = {t for s in spans for t in IDENT.findall(s)}
    found |= set(re.findall(r"\b[A-Za-z]+_[A-Za-z0-9_]+\b", issue))
    found |= set(re.findall(r"\b[a-z]+[A-Z][A-Za-z0-9]*\b|\b[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*\b", issue))
    found |= set(re.findall(r"\.([A-Za-z_]\w*)", issue)) | set(re.findall(r"\b([A-Za-z_]\w*)\(", issue))
    return {t for t in found if len(t) >= 3 and t.lower() not in STOP}


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.2, b: float = 0.75):
        self.vocab = {t: i for i, t in enumerate(sorted({t for d in docs for t in d}))}
        rows, cols, vals = [], [], []
        for i, d in enumerate(docs):
            for t, c in Counter(d).items():
                rows.append(i), cols.append(self.vocab[t]), vals.append(c)
        tf = sparse.csr_matrix((vals, (rows, cols)), shape=(len(docs), len(self.vocab)), dtype=np.float32)
        lens = np.array([len(d) for d in docs], dtype=np.float32)
        df = np.bincount(tf.indices, minlength=len(self.vocab))
        self.idf = np.log(1 + (len(docs) - df + 0.5) / (df + 0.5)).astype(np.float32)
        norm = k1 * (1 - b + b * lens / max(lens.mean(), 1))
        tf = tf.tocoo()
        w = tf.data * (k1 + 1) / (tf.data + norm[tf.row])
        self.w = sparse.csc_matrix((w, (tf.row, tf.col)), shape=tf.shape)

    def score(self, query: list[str]) -> np.ndarray:
        q = Counter(t for t in query if t in self.vocab)
        out = np.zeros(self.w.shape[0], dtype=np.float32)
        for t, c in q.items():
            j = self.vocab[t]
            col = self.w[:, j]
            out[col.indices] += self.idf[j] * col.data  # query term multiplicity ignored (standard)
        return out


@dataclass
class Commit:
    """Everything the methods need for one base commit, precomputed once."""
    nodes: list[str]
    file_of: list[str | None]
    rankable: np.ndarray  # non-test nodes with a known file
    mats: dict[str, sparse.csr_matrix]  # edge type -> adjacency (row = source)
    rel_mat: sparse.csr_matrix  # released graph `calls` adjacency in repaired node order
    node_bm25: BM25
    files: list[str]
    file_bm25: BM25
    sources: dict[str, str]
    g_rel: nx.MultiDiGraph
    g_rep: nx.MultiDiGraph
    tasks: list[dict] = field(default_factory=list)


def prepare(args: tuple[str, list[dict]]) -> Commit:
    name, group = args
    g_rel, text = load_graph(DATA / "graphs", group[0])
    rep = json.loads((REPAIRED / name).read_text())
    g_rep = nx.node_link_graph(rep, edges="edges")
    nodes = list(g_rep.nodes)
    pos = {n: i for i, n in enumerate(nodes)}
    attrs = dict(g_rep.nodes(data=True))
    file_of = [attrs[n].get("file") for n in nodes]
    rankable = np.array([f is not None and not is_test_path(f) for f in file_of])

    def adj(edges) -> sparse.csr_matrix:
        e = [(pos[u], pos[v]) for u, v in edges]
        r, c = (zip(*e) if e else ((), ()))
        return sparse.csr_matrix((np.ones(len(e), dtype=np.float32), (r, c)), shape=(len(nodes), len(nodes)))

    by_type = defaultdict(list)
    for u, v, d in g_rep.edges(data=True):
        by_type[d["type"]].append((u, v))
    mats = {t: adj(by_type[t]) for t in EDGE_TYPES}
    rel_mat = adj([(u, v) for u, v, d in g_rel.edges(data=True)])

    docs = [subtokens(n.replace(".", " ")) * 3 + subtokens(attrs[n].get("text", "")) for n in nodes]
    idx = index_snapshot(DATA / "snapshots" / f"{group[0]['instance_id']}.tgz", set(g_rel.nodes))
    files = sorted(p for p in idx.sources if not is_test_path(p))
    file_bm25 = BM25([subtokens(p.replace("/", " ")) * 3 + subtokens(idx.sources[p]) for p in files])

    at = {(d.get("file"), d.get("line"), d.get("kind")): n for n, d in g_rep.nodes(data=True) if "file" in d}
    tasks = []
    for t in group:
        sites = gold_symbols(idx, t["patch"], text)
        gold_files = {s["path"] for s in sites if s["kind"] != "new_file" and not is_test_path(s["path"])}
        gold_nodes = set()
        for s in sites:
            if s["kind"] == "new_file" or is_test_path(s["path"]):
                continue
            sym = idx.symbols[s["symbol"]]
            node = at.get((sym.path, sym.def_line, sym.kind))
            if node is not None:
                gold_nodes.add(pos[node])
        tasks.append(dict(instance_id=t["instance_id"], repo=repo_short(t), issue=t["problem_statement"],
                          gold_files=gold_files, gold_nodes=gold_nodes))
    return Commit(nodes, file_of, rankable, mats, rel_mat, BM25(docs), files, file_bm25, idx.sources,
                  g_rel, g_rep, tasks)


# ---------------------------------------------------------------- methods: return (files, node indices, confidence)

def rank_files_from_nodes(c: Commit, score: np.ndarray, k: int = 10) -> tuple[list[str], list[float]]:
    best: dict[str, float] = {}
    for i in np.argsort(-score):
        if score[i] <= 0 or len(best) >= k:
            break
        if c.rankable[i] and c.file_of[i] not in best:
            best[c.file_of[i]] = float(score[i])
    return list(best), list(best.values())


def top_nodes(c: Commit, score: np.ndarray, k: int = 10) -> list[int]:
    s = np.where(c.rankable & (score > 0), score, -np.inf)
    order = np.argsort(-s)[:k]
    return [int(i) for i in order if np.isfinite(s[i])]


def confidence(scores: list[float]) -> float:
    top = scores[:5]
    return top[0] / sum(top) if top and sum(top) > 0 else 0.0


def m_grep(c: Commit, t: dict) -> tuple:
    ids = code_identifiers(t["issue"])
    if not ids:
        return [], [], 0.0
    pat = re.compile(r"\b(" + "|".join(map(re.escape, sorted(ids))) + r")\b")
    scored = []
    for f in c.files:
        hits = Counter(pat.findall(c.sources[f]))
        if hits:
            scored.append((len(hits), sum(hits.values()), f))
    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return [f for *_, f in scored[:10]], [], confidence([float(x[0]) for x in scored])


def m_bm25(c: Commit, t: dict) -> tuple:
    q = subtokens(t["issue"])
    fs = c.file_bm25.score(q)
    order = [i for i in np.argsort(-fs)[:10] if fs[i] > 0]
    return [c.files[i] for i in order], top_nodes(c, c.node_bm25.score(q)), confidence([float(fs[i]) for i in order])


def m_2hop(c: Commit, t: dict, graph: str) -> tuple:
    g = c.g_rel if graph == "released" else c.g_rep
    seeds = seed_nodes(g, t["issue"])
    pos = {n: i for i, n in enumerate(c.nodes)}
    tie = c.node_bm25.score(subtokens(t["issue"]))
    tie = tie / (tie.max() or 1)
    score = np.zeros(len(c.nodes), dtype=np.float32)
    if seeds:
        hops = nx.multi_source_dijkstra_path_length(g.to_undirected(as_view=True), seeds, cutoff=2)
        for n, h in hops.items():
            if n in pos:
                score[pos[n]] = 0.5 ** h + 1e-3 * tie[pos[n]]
    files, fscores = rank_files_from_nodes(c, score)
    return files, top_nodes(c, score), confidence(fscores)


def ppr_matrix(c: Commit, types: tuple[str, ...], released: bool) -> sparse.csr_matrix:
    w = c.rel_mat if released else sum((c.mats[t] for t in ("calls", *types)), sparse.csr_matrix(c.rel_mat.shape))
    w = (w + w.T).tocsr()  # walk both directions
    deg = np.asarray(w.sum(axis=1)).ravel()
    inv = np.divide(1.0, deg, out=np.zeros_like(deg), where=deg > 0)
    return (sparse.diags(inv) @ w).T.tocsr(), deg == 0  # column-stochastic transpose, dangling mask


def restart(c: Commit, t: dict, mix: float, released: bool) -> np.ndarray:
    n = len(c.nodes)
    pos = {x: i for i, x in enumerate(c.nodes)}
    seeds = [pos[s] for s in seed_nodes(c.g_rel if released else c.g_rep, t["issue"]) if s in pos]
    sv = np.zeros(n, dtype=np.float64)
    if seeds:
        sv[seeds] = 1.0 / len(seeds)
    bm = c.node_bm25.score(subtokens(t["issue"])).astype(np.float64)
    if released:
        bm[[i for i, x in enumerate(c.nodes) if x not in c.g_rel]] = 0
    bv = np.zeros(n)
    top = [i for i in np.argsort(-bm)[:BM25_TOP] if bm[i] > 0]
    if top:
        bv[top] = bm[top] / bm[top].sum()
    if not seeds and not top:
        return np.zeros(n)
    if not seeds:
        return bv
    if not top:
        return sv
    return (1 - mix) * sv + mix * bv


def ppr(pt: sparse.csr_matrix, dangling: np.ndarray, p: np.ndarray, alpha: float) -> np.ndarray:
    r = p.copy()
    for _ in range(PPR_ITERS):
        r = alpha * (pt @ r + r[dangling].sum() * p) + (1 - alpha) * p
    return r


def m_c4(c: Commit, t: dict, cfg: dict, released: bool = False, cache: dict | None = None) -> tuple:
    key = (cfg["types"], released)
    if cache is None or key not in cache:
        mat = ppr_matrix(c, cfg["types"], released)
        if cache is not None:
            cache[key] = mat
    else:
        mat = cache[key]
    p = restart(c, t, cfg["mix"], released)
    if not p.any():
        return [], [], 0.0
    score = ppr(*mat, p, cfg["alpha"]).astype(np.float32)
    files, fscores = rank_files_from_nodes(c, score)
    return files, top_nodes(c, score), confidence(fscores)


# ---------------------------------------------------------------- evaluation

def metrics(c: Commit, t: dict, out: tuple, rep_und: nx.Graph, symbols: bool = True) -> dict:
    files, nodes, conf = out
    row = {f"file@{k}": bool(set(files[:k]) & t["gold_files"]) for k in KS}
    if symbols:  # grep ranks files only
        row |= {f"sym@{k}": bool(set(nodes[:k]) & t["gold_nodes"]) for k in KS}
        near = (nx.multi_source_dijkstra_path_length(rep_und, {c.nodes[i] for i in nodes[:5]}, cutoff=2)
                if nodes else {})
        row["sym_2hop@5"] = any(c.nodes[g] in near for g in t["gold_nodes"])
    return row | {"confidence": conf}


def configs(released: bool) -> list[dict]:
    type_sets = [()] if released else [tuple(t for t, on in zip(TUNED_TYPES, bits) if on)
                                       for bits in itertools.product((0, 1), repeat=len(TUNED_TYPES))]
    return [dict(alpha=a, mix=m, types=ts) for a in GRID["alpha"] for m in GRID["mix"] for ts in type_sets]


def sweep(c: Commit) -> list[dict]:
    """file@5 of every C4 config on every task of this commit (both graphs)."""
    rows, cache = [], {}
    for released in (False, True):
        for i, cfg in enumerate(configs(released)):
            for t in c.tasks:
                if not t["gold_files"]:
                    continue
                files = m_c4(c, t, cfg, released, cache)[0]
                rows.append(dict(instance_id=t["instance_id"], repo=t["repo"], released=released, cfg=i,
                                 hit5=bool(set(files[:5]) & t["gold_files"])))
    return rows


def run_commit(args: tuple[str, list[dict], dict]) -> list[dict]:
    """Evaluate every method on this commit's tasks. `chosen` maps (repo, released) -> held-out config."""
    name, group, chosen = args
    c = prepare((name, group))
    und = c.g_rep.to_undirected(as_view=True)
    cache, rows = {}, []
    for t in c.tasks:
        if not t["gold_files"]:
            continue
        outs = {"grep": m_grep(c, t), "bm25": m_bm25(c, t), "released_2hop": m_2hop(c, t, "released"),
                "repaired_2hop": m_2hop(c, t, "repaired"),
                "c4_released": m_c4(c, t, chosen[(t["repo"], True)], True, cache),
                "c4": m_c4(c, t, chosen[(t["repo"], False)], False, cache)}
        for method, out in outs.items():
            rows.append(dict(instance_id=t["instance_id"], repo=t["repo"], method=method,
                             top_files=json.dumps(out[0][:5]), **metrics(c, t, out, und, method != "grep")))
    return rows


def sweep_commit(args: tuple[str, list[dict]]) -> list[dict]:
    return sweep(prepare(args))


def loro_choice(sweep_rows: list[dict]) -> tuple[dict, list[dict]]:
    """For each held-out repo, the config with the best file@5 on the other repos (task-weighted)."""
    repos = sorted({r["repo"] for r in sweep_rows})
    chosen, log = {}, []
    for released in (False, True):
        cfgs = configs(released)
        for held in repos:
            train = defaultdict(list)
            for r in sweep_rows:
                if r["released"] == released and r["repo"] != held:
                    train[r["cfg"]].append(r["hit5"])
            best = max(train, key=lambda i: (np.mean(train[i]), -i))
            chosen[(held, released)] = cfgs[best]
            log.append(dict(held_out=held, graph="released" if released else "repaired",
                            train_file_hit5=round(float(np.mean(train[best])), 4), **{**cfgs[best],
                            "types": "+".join(("calls", *cfgs[best]["types"]))}))
    return chosen, log


def jobs() -> list[tuple[str, list[dict]]]:
    by = defaultdict(list)
    for t in map(json.loads, (DATA / "tasks.jsonl").open()):
        by[f"{repo_short(t)}_{t['base_commit']}.json"].append(t)
    return sorted(by.items())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    js = jobs()
    with Pool() as pool:
        sweep_rows = [r for rows in pool.imap_unordered(sweep_commit, js) for r in rows]
        print(f"sweep: {len(sweep_rows)} (config, task) runs", flush=True)
        chosen, log = loro_choice(sweep_rows)
        write_csv(OUT / "loro_choice.csv", log)
        rows = [r for rs in pool.imap_unordered(run_commit, [(n, g, chosen) for n, g in js]) for r in rs]
    rows.sort(key=lambda r: (r["repo"], r["instance_id"], r["method"]))
    cols = ["instance_id", "repo", "method", "top_files", *(f"file@{k}" for k in KS), *(f"sym@{k}" for k in KS),
            "sym_2hop@5", "confidence"]
    write_csv(OUT / "per_task.csv", [{k: r.get(k, "") for k in cols} for r in rows])
    verifiable = set((DATA.parent / "results" / "verifiable_tasks_plus.txt").read_text().split())
    md = ["# Table 2: model-free localization (leave-one-repo-out for C4)", "",
          table2(rows, None), "", "## Verifiable subset (98 tasks)", "", table2(rows, verifiable), "",
          "## LORO choices", "", *(f"- held out {x['held_out']} ({x['graph']}): alpha={x['alpha']} mix={x['mix']} "
                                   f"types={x['types']} (train file@5 {x['train_file_hit5']})" for x in log),
          "", "## Calibration (C4, held-out predictions): confidence bin → file Hit@1", "", calibration(rows)]
    (OUT / "table2.md").write_text("\n".join(md) + "\n")
    print((OUT / "table2.md").read_text())


METHODS = ("grep", "bm25", "released_2hop", "repaired_2hop", "c4_released", "c4")


def table2(rows: list[dict], only: set[str] | None) -> str:
    rows = [r for r in rows if only is None or r["instance_id"] in only]
    repos = sorted({r["repo"] for r in rows})
    cols = ["file@1", "file@5", "file@10", "sym@1", "sym@5", "sym@10", "sym_2hop@5"]
    out = ["| method | fold | n | " + " | ".join(cols) + " |", "|" + "---|" * (3 + len(cols))]
    for m in METHODS:
        for fold in [*repos, "all"]:
            sel = [r for r in rows if r["method"] == m and fold in (r["repo"], "all")]
            cell = lambda k: f"{100 * np.mean([r[k] for r in sel]):.1f}" if sel and k in sel[0] else "–"  # noqa: E731
            out.append(f"| {m} | {fold} | {len(sel)} | " + " | ".join(cell(k) for k in cols) + " |")
    return "\n".join(out)


def calibration(rows: list[dict]) -> str:
    sel = [r for r in rows if r["method"] == "c4"]
    edges = [0, 0.2, 0.4, 0.6, 0.8, 1.0001]
    out = ["| confidence | n | file Hit@1 |", "|---|---|---|"]
    for lo, hi in zip(edges, edges[1:]):
        b = [r for r in sel if lo <= r["confidence"] < hi]
        out.append(f"| {lo:.1f}–{min(hi, 1):.1f} | {len(b)} | " + (f"{100 * np.mean([r['file@1'] for r in b]):.1f}" if b else "–") + " |")
    return "\n".join(out)


if __name__ == "__main__":
    main()
