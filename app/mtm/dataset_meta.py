"""Kaggle metadata for the public dataset: full description, tags, file + column descriptions, sources, cover.

`kaggle datasets metadata --update` replaces every field, so this writes all of them.
The metadata dir is outside the dataset folder so the cover image is not uploaded as a data file.
Run from app/: ../.venv/bin/python -m mtm.dataset_meta
  -> ../notes/kmeta/dataset-metadata.json, then: kaggle datasets metadata --update -p ../notes/kmeta <id>
"""
import json
from pathlib import Path

DS = Path("../release/gemma4-swe-typed-graphs")
META = Path("../notes/kmeta")
ID = "saurinpatel16/gemma4-swe-typed-graphs"
REPO = "https://github.com/saurin16/mind-the-map"
KEYWORDS = ["programming", "computer science", "graph", "nlp", "benchmark"]

LABEL_COLS = {
    "gold.csv": ("Gold edit sites as graph symbols, and whether each is a node in the released and repaired graph.", {
        "instance_id": "Task id (repo_number).", "repo": "Repository: fastapi, rich, requests or httpx.",
        "symbol": "Qualified symbol id edited by the reference patch.",
        "kind": "module, class, function or async_function.",
        "in_released": "True if the symbol is a node in the released graph.",
        "in_repaired": "True if the symbol is a node in the repaired graph."}),
    "gold_sites.csv": ("Every site edited by each task's reference patch, located with the Python AST.", {
        "instance_id": "Task id (repo_number).", "repo": "Repository.", "path": "File path edited by the patch.",
        "symbol": "Innermost enclosing symbol id (empty for a new file).",
        "kind": "function, async_function, class, module or new_file.",
        "nested": "True if the symbol is defined inside a function or class body.",
        "flat_id": "The id the released graph builder gives this symbol (exact reconstruction).",
        "in_released": "True if flat_id is a node in the released graph."}),
    "hints.csv": ("The C4 localizer hint given to agent configuration B2 for each task.", {
        "instance_id": "Task id.", "repo": "Repository.",
        "confidence": "high if C4 and BM25 agree on the top file, else low (exploratory label).",
        "files": "JSON list of the top-5 files.", "symbols": "JSON list of the top-10 symbols."}),
    "per_task.csv": ("Model-free localization results: one row per task and method.", {
        "instance_id": "Task id.", "repo": "Repository.",
        "method": "grep, bm25, released_2hop, repaired_2hop, c4_released or c4 (C4 on the repaired graph).",
        "top_files": "JSON list of the method's top-ranked files.",
        "file@1": "Gold file ranked 1st.", "file@5": "Gold file in top 5.", "file@10": "Gold file in top 10.",
        "sym@1": "Gold symbol ranked 1st.", "sym@5": "Gold symbol in top 5.", "sym@10": "Gold symbol in top 10.",
        "sym_2hop@5": "A gold symbol within 2 hops of a top-5 symbol.",
        "confidence": "Top file score / sum of top-5 file scores."}),
}
TABLE_COLS = {
    "coverage.csv": ("Audit: AST symbols vs released graph nodes per commit and symbol type.", {
        "repo": "Repository.", "commit": "Base commit SHA.", "kind": "module, class, function or async_function.",
        "nested": "Defined inside a function or class body.", "is_test": "Defined in a test file.",
        "ast": "Symbols of this type found by the Python AST.", "released": "Of those, present in the released graph."}),
    "edges.csv": ("Audit: released graph structure and builder-reconstruction checks per commit.", {
        "repo": "Repository.", "commit": "Base commit SHA.", "nodes": "Released node count.",
        "unexplained_nodes": "Released nodes the reconstruction cannot explain (0 everywhere).",
        "parse_errors": "Files the AST could not parse.",
        "misqualified": "Top-level symbols whose released id differs from their qualified name.",
        "id_collisions": "Symbols sharing one released id.", "edges": "Released edge count.",
        "types": "JSON count of released edges by type.",
        "calls_that_are_containment": "calls edges that are really module/class containment."}),
    "loro_choice.csv": ("C4 hyperparameters chosen in each leave-one-repo-out fold.", {
        "held_out": "Repository held out.", "graph": "Graph used (released or repaired).",
        "train_file_hit5": "File Hit@5 on the training repos.", "alpha": "PageRank restart probability.",
        "mix": "Weight of the graph score vs lexical score.", "types": "Edge types used."}),
    "reach.csv": ("Hop distance from issue-named symbols to the nearest gold symbol (blank = unreachable).", {
        "instance_id": "Task id.", "repo": "Repository.", "released": "Hops on the released graph.",
        "repaired": "Hops on the repaired graph.", "repaired_no_contains": "Hops on the repaired graph without contains edges."}),
    "repair.csv": ("Repair: what the typed superset adds per commit.", {
        "repo": "Repository.", "commit": "Base commit SHA.", "released_nodes": "Released node count.",
        "nodes": "Repaired node count.", "new_nodes": "Nodes added.", "released_edges": "Released edge count.",
        "edges": "Repaired edge count.", "new_module": "Module nodes added.", "new_class": "Class nodes added.",
        "new_function": "Function nodes added.", "new_async_function": "Async function nodes added.",
        "added_contains": "contains edges added.", "added_calls": "calls edges added.",
        "added_imports": "imports edges added.", "added_inherits": "inherits edges added.",
        "added_overrides": "overrides edges added.", "added_tests": "tests edges added."}),
    "superset.csv": ("Superset check per commit: released nodes/edges missing or changed in the repaired graph (all 0 = pass).", {
        "repo": "Repository.", "commit": "Base commit SHA.", "missing_nodes": "Released nodes absent from the repair.",
        "changed_nodes": "Released nodes whose text or name changed.", "missing_edges": "Released edges absent from the repair."}),
}
OTHER = {
    "README.md": "Datasheet: contents, rebuild instructions, key numbers, limitations.",
    "tables/table1.md": "Paper Table 1: audit of the released graph.",
    "tables/table2.md": "Paper Table 2: localization benchmark.",
    "tables/table_g2.md": "Repair gate table: gold-site coverage and reachability, released vs repaired.",
    "tables/mcnemar.md": "Exact McNemar tests between localization methods.",
    "tables/validity.md": "Benchmark card: reference fixes verifiable with the official kit (39/129).",
    "tables/validity_plus.md": "Benchmark card: verifiable with the documented environment (98/129).",
    "tables/verifiable_tasks_plus.txt": "The 98 verifiable task ids.",
    "tables/phase4_task_order.txt": "Pre-registered task order for the agent evaluation.",
    "code/test_export.py": "Round-trip test: released graph + delta reproduces the repaired graph.",
    "code/mtm/__init__.py": "Package marker.",
    "code/mtm/ast_index.py": "Python AST index and exact reconstruction of the released builder's ids.",
    "code/mtm/audit.py": "C1 audit: coverage, reachability, edge checks.",
    "code/mtm/repair.py": "C2 repair: builds the typed superset graph.",
    "code/mtm/repair_report.py": "Repair gate: superset and reachability checks.",
    "code/mtm/localize.py": "C4 localizer (Personalized PageRank) and baselines.",
    "code/mtm/mcnemar.py": "Exact McNemar tests.",
    "code/mtm/hints.py": "Builds the B2 localizer hints.",
    "code/mtm/export_dataset.py": "Builds this dataset; merge_typed rebuilds the full graphs.",
}


def files() -> list[dict]:
    out = []
    for sub, spec in (("labels", LABEL_COLS), ("tables", TABLE_COLS)):
        for name, (desc, cols) in spec.items():
            header = (DS / sub / name).read_text().splitlines()[0].split(",")
            assert header == list(cols), f"{sub}/{name}: columns changed"
            out.append({"name": f"{sub}/{name}", "description": desc,
                        "columns": [{"name": c, "description": d} for c, d in cols.items()]})
    for name, desc in OTHER.items():
        assert (DS / name).exists(), name
        out.append({"name": name, "description": desc})
    for p in sorted((DS / "typed").glob("*.json.gz")):
        repo, commit = p.name.removesuffix(".json.gz").rsplit("_", 1)
        out.append({"name": f"typed/{p.name.removesuffix('.gz')}", "description":
                    f"Typed delta for {repo} at {commit[:12]}: added_nodes, added_edges, released_node_attrs (no source text)."})
    return out


def main() -> None:
    readme = (DS / "README.md").read_text()
    META.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": ID,
        "title": "Gemma 4 SWE Typed Graphs (Mind the Map)",
        "subtitle": "Typed repair, audit and localization labels for the Gemma 4 agent code graphs",
        "description": readme,
        "licenses": [{"name": "apache-2.0"}],
        "keywords": KEYWORDS,
        "isPrivate": False,
        "expectedUpdateFrequency": "never",
        "userSpecifiedSources": f"Derived from the code graphs, repository snapshots and tasks released with the Kaggle "
                                f"Gemma 4 Developer Agent competition (not redistributed). Method and code: {REPO}",
        "image": "../../paper/figures/dataset_cover.png",
        "data": files(),
    }
    (META / "dataset-metadata.json").write_text(json.dumps(meta, indent=1))
    print(f"{len(meta['data'])} files described, description {len(readme)} chars")


if __name__ == "__main__":
    main()
