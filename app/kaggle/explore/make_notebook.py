"""Builds the public example notebook for the dataset (uses the dataset only, no Competition Data).

python make_notebook.py          -> mind-the-map-typed-graphs-quickstart.ipynb
python make_notebook.py --run    -> also runs every code cell locally against ../../../release/gemma4-swe-typed-graphs
Each section checks its numbers against the paper's tables, so a run that finishes reproduces them.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
NB = HERE / "mind-the-map-typed-graphs-quickstart.ipynb"

CELLS = [
("md", """# Mind the Map · typed graphs quickstart

This notebook uses only the **Gemma 4 SWE Typed Graphs** dataset; no competition data is needed.
It loads the typed additions to the 127 released code graphs and the task labels, and reproduces the paper's headline numbers.
Every section ends with an `assert` against the paper's tables.

- Code, paper and pre-registration: [github.com/saurin16/mind-the-map](https://github.com/saurin16/mind-the-map)
- Audit notebook (needs the competition data): [Mind the Map C1 Code Graph Audit](https://www.kaggle.com/code/saurinpatel16/mind-the-map-c1-code-graph-audit)"""),
("code", """import glob, gzip, json, os
from collections import Counter
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

hits = glob.glob("/kaggle/input/**/labels/gold.csv", recursive=True) or [os.environ.get("MTM_DS", ".") + "/labels/gold.csv"]
DS = Path(hits[0]).parents[1]
assert (DS / "labels/gold.csv").exists(), "attach the gemma4-swe-typed-graphs dataset"
print(DS, sorted(p.name for p in DS.iterdir()))"""),
("md", """## 1. What the repair adds

Each `typed/{repo}_{commit}.json` holds the nodes and typed edges that the repair adds to one released graph:
- `added_nodes`: id, kind, file, line;
- `added_edges`: `[type, source, target, key]`;
- `released_node_attrs`: kind, file, line for the released node ids.

Released nodes and edges are never changed, so released graph + delta is a strict superset."""),
("code", """def load(p):
    return json.load(gzip.open(p, "rt") if p.suffix == ".gz" else open(p))

deltas = {p.name.split(".json")[0]: load(p) for p in sorted((DS / "typed").glob("*.json*"))}
kinds, types = Counter(), Counter()
for d in deltas.values():
    kinds.update(n["kind"] for n in d["added_nodes"])
    types.update(e[0] for e in d["added_edges"])
print(len(deltas), "graphs |", sum(kinds.values()), "added nodes |", sum(types.values()), "added edges")
print(dict(kinds)); print(dict(types))

rep = pd.read_csv(DS / "tables/repair.csv")
assert len(deltas) == 127 and sum(kinds.values()) == rep.new_nodes.sum() == 161784
for t in ["contains", "calls", "imports", "inherits", "overrides", "tests"]:
    assert types[t] == rep[f"added_{t}"].sum(), t
assert sum(types.values()) == 804338

# the paper's "0 of 65,415 async functions" counts top-level ones; nested async defs are missing too
cov = pd.read_csv(DS / "tables/coverage.csv").groupby(["kind", "nested"])[["ast", "released"]].sum()
print(cov)
assert cov.loc[("async_function", False), "ast"] == 65415 and cov.loc["async_function", "released"].sum() == 0
assert kinds["async_function"] == cov.loc["async_function", "ast"].sum() == 70117
assert kinds["module"] == cov.loc[("module", False), "ast"] == 88857"""),
("code", """order = ["contains", "calls", "imports", "inherits", "overrides", "tests"]
fig, ax = plt.subplots(figsize=(7, 2.8))
ax.barh(order[::-1], [types[t] / 1e3 for t in order[::-1]], color="#2a78d6")
for i, t in enumerate(order[::-1]):
    ax.text(types[t] / 1e3 + 4, i, f"{types[t]:,}", va="center", fontsize=8)
ax.set_xlabel("added edges, thousands (127 graphs)")
ax.set_title("Edges the repair adds, by type", loc="left")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.show()"""),
("md", """## 2. Are the edited sites in the graph?

`labels/gold.csv` lists every symbol edited by each task's reference patch, and whether it is a node in the released and in the repaired graph."""),
("code", """gold = pd.read_csv(DS / "labels/gold.csv")
defs = gold[gold.kind != "module"]
cov = gold.groupby("kind")[["in_released", "in_repaired"]].agg(["sum", "count"])
print(cov)
print(f"definition sites: released {defs.in_released.sum()}/{len(defs)} -> repaired {defs.in_repaired.sum()}/{len(defs)}")
assert (defs.in_released.sum(), defs.in_repaired.sum(), len(defs)) == (468, 524, 524)
a = gold[gold.kind == "async_function"]
assert (a.in_released.sum(), a.in_repaired.sum(), len(a)) == (0, 56, 56)"""),
("md", """## 3. Can an agent reach them?

`tables/reach.csv` gives, for each task, the hop distance from the symbols named in the issue to the nearest edited symbol. A blank cell means unreachable."""),
("code", """reach = pd.read_csv(DS / "tables/reach.csv")
within2 = {c: int((reach[c] <= 2).sum()) for c in ["released", "repaired", "repaired_no_contains"]}
print({c: f"{v}/{len(reach)} ({100 * v / len(reach):.1f}%)" for c, v in within2.items()})
assert (within2["released"], within2["repaired"], within2["repaired_no_contains"], len(reach)) == (46, 93, 88, 129)"""),
("md", """## 4. Localization without a model

`labels/per_task.csv` has one row per task and method. C4 is Personalized PageRank on the repaired graph, seeded by BM25 and tuned leave-one-repo-out."""),
("code", """pt = pd.read_csv(DS / "labels/per_task.csv")
cols = ["file@1", "file@5", "file@10", "sym@1", "sym@5", "sym@10", "sym_2hop@5"]
hit = pt.groupby("method")[cols].mean().mul(100).round(1)
hit.insert(0, "n", pt.groupby("method").size())
order = ["grep", "bm25", "released_2hop", "repaired_2hop", "c4_released", "c4"]
display(hit.loc[order]) if "display" in globals() else print(hit.loc[order])
assert hit.loc["grep", "file@10"] == 57.0 and hit.loc["c4", "file@10"] == 75.0 and hit.loc["c4", "n"] == 128"""),
("md", """## 5. The hint a B2 agent sees

When C4 and BM25 agree on the top file, the hint is labelled high confidence. This label was found after looking at the results, so the paper treats it as exploratory only."""),
("code", """hints = pd.read_csv(DS / "labels/hints.csv")
h = hints.iloc[0]
print(h.instance_id, h.confidence); print("files:", json.loads(h.files)); print("symbols:", json.loads(h.symbols)[:5])

c4 = pt[pt.method == "c4"].merge(hints[["instance_id", "confidence"]], on="instance_id", suffixes=("", "_label"))
by = c4.groupby("confidence_label")["file@1"].agg(["sum", "count"])
by["Hit@1 %"] = (100 * by["sum"] / by["count"]).round(1)
print(by)
assert by.loc["high", "Hit@1 %"] == 47.6 and by.loc["low", "Hit@1 %"] == 22.1"""),
("md", """## 6. Walking the typed edges

The typed edges alone already answer structural questions. Here we use them to ask which symbols the test functions of one graph exercise."""),
("code", """name, d = next((k, v) for k, v in deltas.items() if k.startswith("rich_"))
tests = Counter(t for typ, s, t, k in d["added_edges"] if typ == "tests")
print(name, "-", len(tests), "symbols reached by tests edges; most tested:")
for sym, n in tests.most_common(8):
    print(f"  {n:4d}  {sym}")
inh = [(s, t) for typ, s, t, k in d["added_edges"] if typ == "inherits"][:5]
print("inherits:", inh)"""),
("md", """## 7. Rebuilding the full drop-in graphs

The full repaired graphs need the competition's released graphs and snapshots, which this dataset cannot redistribute. With the competition data attached:

```python
import sys; sys.path.insert(0, str(DS / "code"))
from mtm.export_dataset import merge_typed
graph = merge_typed(released_graph, delta, text_of)   # text_of(node) -> source text from the snapshot
```

or rebuild from source with `MTM_DATA=/path/to/competition/data python -m mtm.repair` (31 s on 10 cores).
The result loads unchanged in the competition harness, through `load_graph_from_json` and `get_code_neighbors(edge_type=...)`."""),
]


def build() -> dict:
    cells = []
    for kind, src in CELLS:
        c = {"cell_type": "markdown" if kind == "md" else "code", "metadata": {}, "source": src}
        if kind == "code":
            c.update(execution_count=None, outputs=[])
        cells.append(c)
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


if __name__ == "__main__":
    NB.write_text(json.dumps(build(), indent=1))
    print("wrote", NB.name)
    if "--run" in sys.argv:
        import matplotlib
        matplotlib.use("Agg")
        os_env = {"MTM_DS": str((HERE / "../../../release/gemma4-swe-typed-graphs").resolve())}
        import os
        os.environ.update(os_env)
        g = {}
        for kind, src in CELLS:
            if kind == "code":
                exec(compile(src, "cell", "exec"), g)
        print("all cells ran, all asserts passed")
