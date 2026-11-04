"""Tests for the C2 repairer. Run from app/: ../.venv/bin/python -m pytest tests/test_repair.py -q"""
import json
import textwrap

import pytest

from mtm.ast_index import RepoIndex, index_source
from mtm.audit import DATA
from mtm.repair import Resolver, node_ids, repair_commit, typed_edges

FILES = {
    "pkg/__init__.py": "from .models import Model\n",
    "pkg/models.py": textwrap.dedent('''\
        class Base:
            def save(self):
                return self.validate()

            def validate(self):
                return True


        class Model(Base):
            def save(self):
                return super().save()

            async def fetch(self, client):
                client.get()
                return helper()


        def helper():
            return Model()
    '''),
    "tests/test_models.py": textwrap.dedent('''\
        from pkg import Model
        from pkg.models import helper


        def make():
            return 1


        def test_save():
            m = Model()
            assert m.save()
            assert helper is not None
            make()
    '''),
}


@pytest.fixture(scope="module")
def repo():
    idx = RepoIndex()
    for path, src in FILES.items():
        index_source(path, src, idx)
    res = Resolver(idx)
    nid = node_ids(idx, set(), {})
    return idx, res, nid, typed_edges(idx, res, nid)


def test_async_and_module_nodes(repo):
    idx, _, nid, _ = repo
    assert nid["pkg.models.Model.fetch"] == "pkg.models.Model.fetch"
    assert idx.symbols["pkg.models.Model.fetch"].kind == "async_function"
    assert nid["pkg.models"] == "pkg.models" and nid["pkg"] == "pkg"


def test_resolution_through_reexport_self_and_super(repo):
    *_, edges = repo
    assert ("pkg.models.Model.fetch", "pkg.models.helper", "calls") in edges  # async caller
    assert ("pkg.models.Base.save", "pkg.models.Base.validate", "calls") in edges  # self.
    assert ("pkg.models.Model.save", "pkg.models.Base.save", "calls") in edges  # super()
    assert ("tests.test_models.test_save", "pkg.models.Model", "calls") in edges  # via pkg/__init__ re-export


def test_unknown_receivers_are_not_guessed(repo):
    *_, edges = repo
    assert not any(u == "pkg.models.Model.fetch" and v.endswith(".get") for u, v, _ in edges)
    assert not any(u == "tests.test_models.test_save" and v.endswith(".save") and k == "calls" for u, v, k in edges)


def test_structural_edges(repo):
    *_, edges = repo
    assert ("pkg.models.Model", "pkg.models.Base", "inherits") in edges
    assert ("pkg.models.Model.save", "pkg.models.Base.save", "overrides") in edges
    assert ("pkg.models.Model", "pkg.models.Model.fetch", "contains") in edges
    assert ("pkg.models", "pkg.models.Model", "contains") in edges
    assert ("pkg", "pkg.models.Model", "imports") in edges
    assert ("tests.test_models", "pkg.models.helper", "imports") in edges


def test_tests_edges_target_code_only(repo):
    *_, edges = repo
    tests = {(u, v) for u, v, k in edges if k == "tests"}
    assert ("tests.test_models.test_save", "pkg.models.Model") in tests
    assert ("tests.test_models.test_save", "pkg.models.helper") in tests  # referenced, not called
    assert not any(v.startswith("tests.") for _, v in tests)
    assert not any(u == "tests.test_models.make" for u, _ in tests)  # helper, not a test


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    path = DATA / "tasks.jsonl"
    if not path.exists():
        pytest.skip("competition data not downloaded")
    task = next(t for t in map(json.loads, path.open()) if t["instance_id"] == "fastapi_15661")
    name = f"fastapi_{task['base_commit']}.json"
    out = tmp_path_factory.mktemp("repaired")
    row = repair_commit((str(DATA / "graphs" / name), str(DATA / "snapshots" / "fastapi_15661.tgz"), str(out), "fastapi"))
    return json.loads((DATA / "graphs" / name).read_text()), json.loads((out / name).read_text()), row


def test_real_graph_is_superset(real):
    released, repaired, _ = real
    rel_nodes = {n["id"]: n for n in released["nodes"]}
    rep_nodes = {n["id"]: n for n in repaired["nodes"]}
    assert rel_nodes.keys() <= rep_nodes.keys()
    assert all(rep_nodes[i]["text"] == n["text"] and rep_nodes[i]["name"] == n["name"] for i, n in rel_nodes.items())
    key = lambda e: (e["source"], e["target"], e["type"], e["key"])
    assert {key(e) for e in released["edges"]} <= {key(e) for e in repaired["edges"]}
    assert len({key(e) for e in repaired["edges"]}) == len(repaired["edges"])  # multigraph keys unique


def test_real_graph_adds_async_and_types(real):
    _, repaired, row = real
    kinds = {n.get("kind") for n in repaired["nodes"]}
    types = {e["type"] for e in repaired["edges"]}
    assert "async_function" in kinds and row["new_async_function"] > 0
    assert types == {"calls", "contains", "imports", "inherits", "overrides", "tests"}
