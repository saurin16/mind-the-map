"""C2 Repairer: rebuild each released code graph as a typed superset.

Every released node and edge is kept unchanged (ids, `name`, `text`, and the `calls` edges, including the
ones that are really containment), so the released embeddings still line up. Added on top:

  nodes   every AST symbol the released graph lacks: async functions, modules, and nested or colliding
          definitions. New nodes use the symbol's true qualified id.
  attrs   `kind`, `file`, `line` on every node we can place in the source.
  edges   contains  module -> top-level def, class -> method, function -> nested def
          calls     resolved call sites inside function bodies (including async functions)
          imports   module -> imported repo module or symbol
          inherits  class -> resolved base class
          overrides method -> the base-class method it redefines
          tests     test function -> non-test symbol it calls or references

Name resolution is static and conservative: local defs, module namespaces, imports (including relative
imports and package re-exports), `self`/`cls`/`super()` members through resolved bases. Calls on objects of
unknown type are not guessed.

Run from app/: ../.venv/bin/python -m mtm.repair [out_dir]   (default data/graphs_repaired)
"""
import ast
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from mtm.ast_index import RepoIndex, Symbol, index_snapshot, module_id, released_match
from mtm.audit import DATA, repo_short

EDGE_TYPES = ("contains", "calls", "imports", "inherits", "overrides", "tests")
MODULE_TEXT_LINES = 40  # module nodes carry the file head (docstring + imports), not the whole file
MAX_REEXPORT_DEPTH = 6


class Resolver:
    """Static name resolution over one repo snapshot, in Python-import terms."""

    def __init__(self, idx: RepoIndex):
        self.idx = idx
        self.py: dict[str, Symbol] = {}  # python dotted name -> symbol
        self.pyname: dict[str, str] = {}  # symbol id -> python dotted name
        self.ns: dict[str, dict[str, str]] = {}  # module pyname -> local name -> target pyname
        self.trees: dict[str, ast.Module] = {}
        for path, syms in idx.by_path.items():
            mod = syms[0]
            mpy = module_id(path)
            for s in syms:
                name = mpy + s.id[len(mod.id):]
                self.pyname.setdefault(s.id, name)
                self.py.setdefault(name, idx.symbols[s.id])
            self.trees[path] = ast.parse(idx.sources[path])
            self.ns[mpy] = self._namespace(path, mpy, self.trees[path])
        self._bases: dict[str, list[Symbol]] = {}

    @staticmethod
    def _package(path: str, mpy: str) -> str:
        return mpy if path.endswith("__init__.py") else mpy.rpartition(".")[0]

    def _namespace(self, path: str, mpy: str, tree: ast.Module) -> dict[str, str]:
        ns = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                ns[node.name] = f"{mpy}.{node.name}"
        for node in ast.walk(tree):  # imports anywhere in the file (try/except, TYPE_CHECKING, functions)
            for local, target in self.import_bindings(node, path, mpy):
                ns.setdefault(local, target)
        return ns

    def import_bindings(self, node: ast.AST, path: str, mpy: str) -> list[tuple[str, str]]:
        if isinstance(node, ast.Import):
            return [(a.asname or a.name.split(".")[0], a.name if a.asname else a.name.split(".")[0]) for a in node.names]
        if isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                pkg = self._package(path, mpy).split(".")
                pkg = pkg[: len(pkg) - (node.level - 1)] if node.level > 1 else pkg
                base = ".".join(p for p in [*pkg, base] if p)
            return [(a.asname or a.name, f"{base}.{a.name}") for a in node.names if a.name != "*"]
        return []

    def lookup(self, name: str, depth: int = 0) -> Symbol | None:
        """Symbol for a python dotted name, following package re-exports (`from .x import y`)."""
        if name in self.py:
            return self.py[name]
        if depth >= MAX_REEXPORT_DEPTH:
            return None
        head, _, attr = name.rpartition(".")
        if not head:
            return None
        if head in self.ns and attr in self.ns[head] and self.ns[head][attr] != name:
            return self.lookup(self.ns[head][attr], depth + 1)
        owner = self.lookup(head, depth + 1)
        if owner is not None and owner.kind == "class":
            return self.member(owner, attr)
        if owner is not None and owner.kind == "module":
            return self.lookup(f"{self.pyname[owner.id]}.{attr}", depth + 1)
        return None

    def bases(self, cls: Symbol) -> list[Symbol]:
        if cls.id not in self._bases:
            self._bases[cls.id] = []
            node = self.node_of(cls)
            mpy = module_id(cls.path)
            for b in getattr(node, "bases", []):
                t = self.expr(b, mpy, None, {})
                if t is not None and t.kind == "class" and t.id != cls.id:
                    self._bases[cls.id].append(t)
        return self._bases[cls.id]

    def member(self, cls: Symbol, name: str, seen: frozenset = frozenset()) -> Symbol | None:
        if cls.id in seen:
            return None
        own = self.py.get(f"{self.pyname[cls.id]}.{name}")
        if own is not None:
            return own
        for b in self.bases(cls):
            hit = self.member(b, name, seen | {cls.id})
            if hit is not None:
                return hit
        return None

    def node_of(self, s: Symbol) -> ast.AST | None:
        for n in ast.walk(self.trees[s.path]):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.lineno == s.def_line:
                return n
        return None

    def expr(self, e: ast.AST, mpy: str, cls: Symbol | None, local: dict[str, str]) -> Symbol | None:
        """Resolve a Name/Attribute expression to a repo symbol, or None."""
        if isinstance(e, ast.Name):
            target = local.get(e.id) or self.ns.get(mpy, {}).get(e.id)
            return self.lookup(target) if target else None
        if not isinstance(e, ast.Attribute):
            return None
        v = e.value
        if isinstance(v, ast.Name) and v.id in ("self", "cls") and cls is not None:
            return self.member(cls, e.attr)
        if (isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "super"
                and cls is not None):
            for b in self.bases(cls):
                hit = self.member(b, e.attr)
                if hit is not None:
                    return hit
            return None
        owner = self.expr(v, mpy, cls, local)
        if owner is None:
            return None
        if owner.kind == "class":
            return self.member(owner, e.attr)
        if owner.kind == "module":
            return self.lookup(f"{self.pyname[owner.id]}.{e.attr}")
        return None


def _body_nodes(fn: ast.AST):
    """AST nodes of a function body, not descending into nested defs/classes (they are their own sources)."""
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) and n is not fn:
            if not isinstance(n, ast.Lambda):
                stack.extend(n.decorator_list)  # decorators run in the enclosing scope
                continue
        yield n
        stack.extend(ast.iter_child_nodes(n))


def node_ids(idx: RepoIndex, released: set[str], node_text: dict[str, str]) -> dict[str, str]:
    """Symbol id -> graph node id: the released node when it holds this symbol, else a new unique id."""
    out, taken = {}, set(released)
    for s in sorted(idx.symbols.values(), key=lambda s: (s.path, s.start)):
        if s.kind != "module" and released_match(idx, s, node_text):
            out[s.id] = s.flat_id
            continue
        nid = s.id if s.id not in taken else f"{s.id}@{s.path}:{s.def_line}"
        taken.add(nid)
        out[s.id] = nid
    return out


def symbol_text(idx: RepoIndex, s: Symbol) -> str:
    lines = idx.sources[s.path].splitlines()
    if s.kind == "module":
        return "\n".join(lines[:MODULE_TEXT_LINES])
    seg = lines[s.def_line - 1: s.end]
    return "\n".join([seg[0].lstrip(), *seg[1:]]) if seg else ""


def typed_edges(idx: RepoIndex, res: Resolver, nid: dict[str, str]) -> set[tuple[str, str, str]]:
    edges: set[tuple[str, str, str]] = set()

    def add(src: Symbol | None, dst: Symbol | None, kind: str) -> None:
        if src is not None and dst is not None and src.id != dst.id and src.id in nid and dst.id in nid:
            edges.add((nid[src.id], nid[dst.id], kind))

    for path, syms in idx.by_path.items():
        mod, mpy, tree = syms[0], module_id(path), res.trees[path]
        by_line = {s.def_line: idx.symbols[s.id] for s in syms if s.kind != "module"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):  # `import a.b` binds `a` but imports module a.b
                targets = [a.name for a in node.names]
            else:
                targets = [t for _, t in res.import_bindings(node, path, mpy)]
            for target in targets:
                add(mod, res.lookup(target), "imports")

        def visit(parent_ast: ast.AST, parent: Symbol, cls: Symbol | None, local: dict[str, str]) -> None:
            for child in ast.iter_child_nodes(parent_ast):
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visit(child, parent, cls, local)
                    continue
                s = by_line.get(child.lineno)
                if s is None:
                    continue
                add(parent, s, "contains")
                if isinstance(child, ast.ClassDef):
                    for b in res.bases(s):
                        add(s, b, "inherits")
                    visit(child, s, s, local)
                    continue
                if cls is not None and parent.id == cls.id:
                    for b in res.bases(cls):
                        add(s, res.member(b, child.name), "overrides")
                inner = dict(local)
                inner.update({n.name: res.pyname[by_line[n.lineno].id] for n in ast.iter_child_nodes(child)
                              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                              and n.lineno in by_line})
                is_test = s.is_test and (child.name.startswith("test") or (cls is not None and cls.id.rsplit(".", 1)[-1].startswith("Test")))
                for n in _body_nodes(child):
                    if isinstance(n, ast.Call):
                        add(s, res.expr(n.func, mpy, cls, inner), "calls")
                    if is_test and isinstance(n, (ast.Name, ast.Attribute)):
                        t = res.expr(n, mpy, cls, inner)
                        if t is not None and not t.is_test:
                            add(s, t, "tests")
                visit(child, s, cls, inner)

        visit(tree, mod, None, {})
    return edges


def repair_commit(args: tuple[str, str, str, str]) -> dict:
    graph_path, tgz, out_dir, repo = args
    data = json.loads(Path(graph_path).read_text())
    released = {n["id"] for n in data["nodes"]}
    node_text = {n["id"]: n.get("text") or "" for n in data["nodes"]}
    idx = index_snapshot(Path(tgz), released)
    res = Resolver(idx)
    nid = node_ids(idx, released, node_text)

    nodes = {n["id"]: dict(n) for n in data["nodes"]}
    for sid, node in nid.items():
        s = idx.symbols[sid]
        if node not in nodes:
            nodes[node] = {"name": node, "text": symbol_text(idx, s), "id": node}
        nodes[node].setdefault("kind", s.kind)
        nodes[node].setdefault("file", s.path)
        nodes[node].setdefault("line", s.def_line)

    seen = {(e["source"], e["target"], e["type"]) for e in data["edges"]}
    edges = [dict(e) for e in data["edges"]]
    keys = Counter((e["source"], e["target"]) for e in edges)
    added = Counter()
    for u, v, kind in sorted(typed_edges(idx, res, nid)):
        if (u, v, kind) in seen:
            continue
        edges.append({"type": kind, "source": u, "target": v, "key": keys[(u, v)]})
        keys[(u, v)] += 1
        added[kind] += 1

    out = {**data, "nodes": list(nodes.values()), "edges": edges}
    Path(out_dir, Path(graph_path).name).write_text(json.dumps(out))
    kinds = Counter(nodes[n].get("kind", "unplaced") for n in nodes if n not in released)
    return dict(repo=repo, commit=Path(graph_path).stem.rsplit("_", 1)[1], released_nodes=len(released),
                nodes=len(nodes), new_nodes=len(nodes) - len(released), released_edges=len(data["edges"]),
                edges=len(edges), **{f"new_{k}": kinds[k] for k in ("module", "class", "function", "async_function")},
                **{f"added_{k}": added[k] for k in EDGE_TYPES})


def main(out_dir: str = str(DATA / "graphs_repaired")) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(l) for l in (DATA / "tasks.jsonl").open()]
    jobs = {}
    for t in tasks:
        name = f"{repo_short(t)}_{t['base_commit']}.json"
        jobs.setdefault(name, (str(DATA / "graphs" / name), str(DATA / "snapshots" / f"{t['instance_id']}.tgz"),
                               str(out), repo_short(t)))
    with Pool() as pool:
        rows = []
        for n, row in enumerate(pool.imap_unordered(repair_commit, jobs.values()), 1):
            rows.append(row)
            print(f"[{n}/{len(jobs)}] {row['repo']} {row['commit'][:8]} +{row['new_nodes']} nodes "
                  f"+{row['edges'] - row['released_edges']} edges", flush=True)
    report = Path(DATA.parent / "results" / "repair")
    report.mkdir(parents=True, exist_ok=True)
    from mtm.audit import write_csv
    write_csv(report / "repair.csv", sorted(rows, key=lambda r: (r["repo"], r["commit"])))
    print("wrote", out, "and", report / "repair.csv")


if __name__ == "__main__":
    main(*sys.argv[1:])
