"""Tests for the C4 localizer. Run from app/: ../.venv/bin/python -m pytest tests/test_localize.py -q"""
import numpy as np
from scipy import sparse

from mtm.localize import BM25, code_identifiers, confidence, configs, loro_choice, ppr, subtokens


def test_subtokens_split_snake_and_camel():
    assert subtokens("get_HTTPResponse parseURL the") == ["http", "response", "parse", "url"]


def test_code_identifiers_need_code_form():
    issue = "The session drops headers.\n`Session.request` fails, see merge_setting() and maxRetries.\n```\nfoo = bar\n```"
    ids = code_identifiers(issue)
    assert {"Session", "request", "merge_setting", "maxRetries", "foo", "bar"} <= ids
    assert "headers" not in ids and "drops" not in ids


def test_bm25_prefers_rare_matching_terms():
    bm = BM25([["cookie", "jar", "the"], ["session", "the"], ["cookie", "cookie", "session"]])
    s = bm.score(["jar"])
    assert s.argmax() == 0 and s[1] == 0 and s[2] == 0


def test_ppr_is_a_distribution_and_ranks_seed_neighbourhood():
    # path 0-1-2-3 plus isolated (dangling) node 4; restart on node 0
    w = sparse.csr_matrix(([1, 1, 1, 1, 1, 1], ([0, 1, 1, 2, 2, 3], [1, 0, 2, 1, 3, 2])), shape=(5, 5), dtype=float)
    deg = np.asarray(w.sum(axis=1)).ravel()
    pt = (sparse.diags(np.divide(1, deg, out=np.zeros(5), where=deg > 0)) @ w).T.tocsr()
    p = np.array([1.0, 0, 0, 0, 0])
    r = ppr(pt, deg == 0, p, 0.5)
    assert abs(r.sum() - 1) < 1e-6
    assert r[0] > r[1] > r[2] > r[3] and r[4] == 0


def test_confidence_is_top_share():
    assert confidence([3.0, 1.0]) == 0.75
    assert confidence([]) == 0.0


def test_loro_never_tunes_on_held_out_repo():
    n = len(configs(False))
    rows = []
    for cfg in range(n):  # config 0 is perfect on repo A only, config 1 perfect on repo B only
        rows += [dict(repo="A", released=False, cfg=cfg, hit5=cfg == 0, instance_id="a"),
                 dict(repo="B", released=False, cfg=cfg, hit5=cfg == 1, instance_id="b")]
    rows += [dict(repo=r, released=True, cfg=0, hit5=True, instance_id=r) for r in "AB"]
    chosen, _ = loro_choice(rows)
    assert chosen[("A", False)] == configs(False)[1]  # tuned on B only
    assert chosen[("B", False)] == configs(False)[0]
