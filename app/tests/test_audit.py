"""Tests for the C1 auditor. Run from app/: ../.venv/bin/python -m pytest tests/test_audit.py -q"""
import json
import textwrap
from pathlib import Path

import pytest

from mtm.ast_index import RepoIndex, index_snapshot, index_source, module_id, released_match
from mtm.audit import DATA, gold_lines, gold_symbols, load_graph, seed_nodes

SRC = textwrap.dedent('''\
    import x

    class Outer:
        def a(self):
            class Inner:
                def m(self):
                    pass
            return Inner

        def b(self):
            pass

    async def fetch():
        def helper():
            pass
        return helper

    def top():
        return 1
''')


def ids(src: str = SRC, path: str = "pkg/mod.py") -> dict:
    idx = RepoIndex()
    index_source(path, src, idx)
    return {s.id: s for s in idx.symbols.values()}, idx


def test_module_id_rules():
    assert module_id("src/requests/sessions.py") == "requests.sessions"
    assert module_id("fastapi/__init__.py") == "fastapi"
    assert module_id("docs_src/body/tutorial001.py", strip=1) == "body.tutorial001"


def test_kinds_and_nesting():
    syms, _ = ids()
    assert syms["pkg.mod.fetch"].kind == "async_function"
    assert syms["pkg.mod.fetch.helper"].nested
    assert syms["pkg.mod.Outer.a.Inner"].nested and syms["pkg.mod.Outer.a.Inner"].kind == "class"
    assert not syms["pkg.mod.Outer.b"].nested


def test_released_builder_scope_emulation():
    """Classes go to module scope; leaving any class clears current_class, so Outer.b loses its class."""
    syms, _ = ids()
    flat = {k: v.flat_id for k, v in syms.items()}
    assert flat["pkg.mod.Outer.a"] == "pkg.mod.Outer.a"
    assert flat["pkg.mod.Outer.a.Inner"] == "pkg.mod.Inner"
    assert flat["pkg.mod.Outer.a.Inner.m"] == "pkg.mod.Inner.m"
    assert flat["pkg.mod.Outer.b"] == "pkg.mod.b"  # the mis-qualification bug
    assert flat["pkg.mod.fetch.helper"] == "pkg.mod.helper"


def test_released_match_rejects_collisions():
    syms, idx = ids()
    s = syms["pkg.mod.top"]
    assert released_match(idx, s, {"pkg.mod.top": "def top():\n    return 1"})
    assert not released_match(idx, s, {"pkg.mod.top": "async def top():\n    ..."})
    assert not released_match(idx, s, {})


def test_overload_stubs_are_not_symbols():
    src = "@overload\ndef f(x: int) -> int: ...\n@typing.overload\ndef f(x: str) -> str: ...\ndef f(x):\n    return x\n"
    syms, _ = ids(src)
    assert syms["pkg.mod.f"].def_line == 5


def test_released_match_skips_decorators_and_comments():
    """Released class texts keep decorator lines and drop trailing comments."""
    src = "@dataclass\nclass Jar(dict):  # type: ignore[misc]\n    x: int = 0\n"
    syms, idx = ids(src)
    s = syms["pkg.mod.Jar"]
    assert released_match(idx, s, {"pkg.mod.Jar": "@dataclass\nclass Jar(dict):\n    None"})
    assert not released_match(idx, s, {"pkg.mod.Jar": "@dataclass\nclass Jar(list):\n    None"})


def test_gold_lines_and_enclosing_symbol():
    patch = textwrap.dedent('''\
        --- a/pkg/mod.py
        +++ b/pkg/mod.py
        @@ -10,2 +10,2 @@
             def b(self):
        -        pass
        +        return 2
        --- /dev/null
        +++ b/pkg/new.py
        @@ -0,0 +1 @@
        +x = 1
    ''')
    assert gold_lines(patch) == {"pkg/mod.py": {11}, "pkg/new.py": {0}}
    _, idx = ids()
    sites = {(s["kind"], s["symbol"]) for s in gold_symbols(idx, patch, {})}
    assert sites == {("function", "pkg.mod.Outer.b"), ("new_file", "")}


def test_pure_insertion_maps_to_line_above():
    patch = "--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -19,1 +19,2 @@\n     return 1\n+    # note\n"
    assert gold_lines(patch) == {"pkg/mod.py": {19}}


@pytest.fixture(scope="module")
def real_task():
    path = DATA / "tasks.jsonl"
    if not path.exists():
        pytest.skip("competition data not downloaded")
    return next(t for t in map(json.loads, path.open()) if t["instance_id"] == "requests_7505")


def test_emulation_explains_every_released_node(real_task):
    g, text = load_graph(DATA / "graphs", real_task)
    idx = index_snapshot(DATA / "snapshots" / "requests_7505.tgz", set(g.nodes))
    assert set(g.nodes) <= {s.flat_id for s in idx.symbols.values()}
    assert not any(s.kind == "async_function" and released_match(idx, s, text) for s in idx.symbols.values())
    assert {d["type"] for _, _, d in g.edges(data=True)} == {"calls"}


def test_seed_fanout_cap(real_task):
    g, _ = load_graph(DATA / "graphs", real_task)
    assert "requests.sessions.Session.request" in seed_nodes(g, "Session.request drops the header")
    assert not seed_nodes(g, "xx self")  # too short / too common
