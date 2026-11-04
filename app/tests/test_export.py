"""The public typed delta round-trips to the repaired graph and carries no source text."""
import gzip
import json

from mtm.audit import DATA
from mtm.export_dataset import OUT, merge_typed


def test_roundtrip_all_commits_and_no_text():
    files = sorted((OUT / "typed").glob("*.json.gz"))
    assert len(files) == 127
    for f in files:
        name = f.name.removesuffix(".gz")
        d = json.load(gzip.open(f, "rt"))
        assert all(set(n) <= {"id", "kind", "file", "line"} for n in d["added_nodes"])
        assert all(set(a) <= {"kind", "file", "line"} for a in d["released_node_attrs"].values())
        repaired = json.loads((DATA / "graphs_repaired" / name).read_text())
        text = {n["id"]: n["text"] for n in repaired["nodes"]}
        merged = merge_typed(json.loads((DATA / "graphs" / name).read_text()), d, lambda n: text[n["id"]])
        key = lambda n: n["id"]
        assert sorted(merged["nodes"], key=key) == sorted(repaired["nodes"], key=key), name
        ekey = lambda e: (e["source"], e["target"], e["type"], e["key"])
        assert sorted(map(ekey, merged["edges"])) == sorted(map(ekey, repaired["edges"])), name
