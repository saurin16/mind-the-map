"""Python-AST ground truth for a repo snapshot, in the released graph's node-id format.

Node ids in the released graphs are dotted module paths from the repo root with a leading
`src/` dropped and `__init__` collapsed to the package, then `Class.method` qualifiers,
e.g. `requests.sessions.Session.request` for `src/requests/sessions.py`.
"""
import ast
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("module", "class", "function", "async_function")


@dataclass
class Symbol:
    id: str
    kind: str  # one of KINDS
    path: str  # repo-relative file path
    start: int
    end: int
    nested: bool = False  # defined inside a function body (not reachable as an attribute)
    is_test: bool = False
    flat_id: str = ""  # the id the released builder gives this symbol (see _walk)
    def_line: int = 0  # line of the `def`/`class` keyword (after decorators)


@dataclass
class RepoIndex:
    symbols: dict[str, Symbol] = field(default_factory=dict)
    by_path: dict[str, list[Symbol]] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    parse_errors: list[str] = field(default_factory=list)

    def enclosing(self, path: str, line: int) -> Symbol | None:
        """Innermost non-module symbol whose span contains `line`, else the module."""
        best = None
        for s in self.by_path.get(path, ()):
            if s.start <= line <= s.end and (best is None or s.end - s.start <= best.end - best.start):
                best = s
        return best


def released_match(idx: "RepoIndex", s: Symbol, node_text: dict[str, str]) -> bool:
    """True iff the released node with this symbol's id holds this symbol's own source,
    not another symbol's that collides with it after flattening."""
    text = node_text.get(s.flat_id)
    if text is None:
        return False
    lines = idx.sources[s.path].splitlines()
    head = _strip_comment(lines[s.def_line - 1]).strip() if 0 < s.def_line <= len(lines) else ""
    # Released class texts carry their decorator lines and drop trailing comments.
    body = text.lstrip().splitlines()
    while body and body[0].lstrip().startswith("@"):
        body.pop(0)
    return "\n".join(body).lstrip().startswith(head) if head else True


def _strip_comment(line: str) -> str:
    """Drop a trailing `# ...` comment that is outside string literals."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#":
            return line[:i]
    return line


def module_id(path: str, strip: int | None = None) -> str:
    """Dotted id; `strip` leading dirs are dropped (default: just a leading `src/`)."""
    parts = path.removesuffix(".py").split("/")
    if strip is None:
        strip = 1 if parts[0] == "src" else 0
    parts = parts[strip:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def is_test_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.startswith(("tests/", "test/")) or "/tests/" in path or name.startswith("test_") or name == "conftest.py"


def _walk(node: ast.AST, prefix: str, mod: str, path: str, in_func: bool, out: list[Symbol], test: bool,
          state: dict) -> None:
    """Emit symbols with their true qualified id and the id the released builder gives them.

    The released builder keeps a single `current_class`: a class sets it on entry and clears it to
    None on exit instead of restoring the outer class. Classes are always filed at module scope, and
    functions under `current_class` if set. So a class nested in a method makes the outer class's
    later methods module-level, and nested defs are flattened. `flat_id` reproduces that.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                (d.id if isinstance(d, ast.Name) else getattr(d, "attr", "")) == "overload"
                for d in child.decorator_list):
            continue  # typing stub; the implementation that follows is the real definition
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = ("class" if isinstance(child, ast.ClassDef)
                    else "async_function" if isinstance(child, ast.AsyncFunctionDef) else "function")
            start = min([d.lineno for d in child.decorator_list] + [child.lineno])
            sid = f"{prefix}.{child.name}"
            if kind == "class":
                flat = f"{mod}.{child.name}"
                state["cls"] = child.name
            else:
                flat = f"{mod}.{state['cls']}.{child.name}" if state["cls"] else f"{mod}.{child.name}"
            out.append(Symbol(sid, kind, path, start, child.end_lineno or start, in_func, test, flat, child.lineno))
            _walk(child, sid, mod, path, in_func or kind != "class", out, test, state)
            if kind == "class":
                state["cls"] = None
        else:
            _walk(child, prefix, mod, path, in_func, out, test, state)


def _file_symbols(path: str, tree: ast.AST, n_lines: int, strip: int | None) -> list[Symbol]:
    mid = module_id(path, strip)
    test = is_test_path(path)
    syms = [Symbol(mid, "module", path, 1, max(1, n_lines), False, test, mid, 1)]
    _walk(tree, mid, mid, path, False, syms, test, {"cls": None})
    return syms


def index_source(path: str, src: str, idx: RepoIndex, released: set[str] | None = None) -> None:
    """Index one file. With `released` ids, pick the leading-dir strip that best matches them:
    the released builder roots some trees below the repo root (e.g. `docs_src/x/y.py` -> `x.y`)."""
    idx.sources[path] = src
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        idx.parse_errors.append(path)
        return
    n = len(src.splitlines())
    syms = _file_symbols(path, tree, n, None)
    if released is not None:
        depth = path.count("/")
        cands = [_file_symbols(path, tree, n, k) for k in range(depth + 1)]
        best = max(cands, key=lambda c: sum(s.flat_id in released for s in c))
        if any(s.flat_id in released for s in best):
            syms = best
    idx.by_path[path] = syms
    for s in syms:
        idx.symbols.setdefault(s.id, s)  # first definition wins (e.g. if/else redefinitions)


def index_snapshot(tgz: Path, released: set[str] | None = None) -> RepoIndex:
    idx = RepoIndex()
    with tarfile.open(tgz) as tar:
        for m in tar:
            name = m.name.removeprefix("./")
            if not m.isfile() or not name.endswith(".py") or name.startswith(".git/"):
                continue
            f = tar.extractfile(m)
            if f is not None:
                index_source(name, f.read().decode("utf-8", errors="replace"), idx, released)
    return idx
