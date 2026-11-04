"""Phase 0 identity test: are the provided 256-d node vectors a known text encoder truncated to 256?

For a sample of nodes, embed node text with each candidate encoder, truncate to 256 (Matryoshka),
L2-normalise, and compare with the stored vector. Median cosine >= 0.95 => identity confirmed.
Also reports nearest-neighbour agreement (does the candidate rank the stored vector's own node first?),
which is robust to an unknown orthogonal rotation being absent but small numeric drift being present.
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parents[1] / "data"
N_SAMPLE = 1000

# (label, model id, prompt prefix applied to node text)
CANDIDATES = [
    ("embeddinggemma/raw", "google/embeddinggemma-300m", ""),
    ("embeddinggemma/doc", "google/embeddinggemma-300m", "title: none | text: "),
    ("embeddinggemma/code-query", "google/embeddinggemma-300m", "task: code retrieval | query: "),
]


def load_nodes(task: dict):
    stem = f"{task['instance_id'].rsplit('_', 1)[0]}_{task['base_commit']}"
    graph = json.loads((DATA / "graphs" / f"{stem}.json").read_text())
    emb = np.load(DATA / "embeddings" / f"{stem}.npz")
    keys = {k.removesuffix(".npy"): k for k in emb.files}
    rows = [(n["id"], n.get("text") or "", emb[keys[n["id"]]]) for n in graph["nodes"] if n["id"] in keys]
    return rows, len(graph["nodes"]), len(emb.files)


def unit(x: np.ndarray) -> np.ndarray:
    return x / np.clip(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12, None)


def main(task_id: str = "") -> None:
    from sentence_transformers import SentenceTransformer

    tasks = {t["instance_id"]: t for t in map(json.loads, (DATA / "tasks.jsonl").open())}
    task_id = task_id or next(iter(tasks))
    rows, n_nodes, n_vecs = load_nodes(tasks[task_id])
    print(f"task={task_id} graph_nodes={n_nodes} stored_vectors={n_vecs} matched={len(rows)}")
    dims = {r[2].shape for r in rows}
    print(f"stored vector shapes={dims} norm_median={np.median([np.linalg.norm(r[2]) for r in rows]):.4f}")

    random.seed(0)
    sample = random.sample(rows, min(N_SAMPLE, len(rows)))
    stored = unit(np.stack([r[2] for r in sample]).astype(np.float32))
    texts = [r[1] for r in sample]

    models = {}
    fulls = {}
    for label, model_id, prefix in CANDIDATES:
        model = models.setdefault(model_id, SentenceTransformer(model_id))
        full = model.encode([prefix + t for t in texts], normalize_embeddings=False, batch_size=16)
        fulls[label] = np.asarray(full)
        cand = unit(fulls[label][:, :256])
        cos = (cand * stored).sum(1)
        nn_hit = (np.argmax(cand @ stored.T, axis=1) == np.arange(len(sample))).mean()
        print(f"{label:28s} cos median={np.median(cos):.4f} p10={np.percentile(cos, 10):.4f} "
              f"p90={np.percentile(cos, 90):.4f}  nn@1={nn_hit:.3f}")

    raw_stored = np.stack([r[2] for r in sample]).astype(np.float32)
    for label, full in fulls.items():
        print(f"ridge {label:22s} " + linear_probe(full, raw_stored))



def linear_probe(full: np.ndarray, stored: np.ndarray, seed: int = 0) -> str:
    """Fallback bridge viability: ridge map encoder-768 -> stored-256, scored on a held-out 20%."""
    from sklearn.linear_model import Ridge

    idx = np.random.default_rng(seed).permutation(len(full))
    cut = int(0.8 * len(full))
    tr, te = idx[:cut], idx[cut:]
    pred = Ridge(alpha=1.0).fit(full[tr], stored[tr]).predict(full[te])
    p, t = unit(pred), unit(stored[te])
    cos = (p * t).sum(1)
    nn_hit = (np.argmax(p @ t.T, axis=1) == np.arange(len(te))).mean()
    hit10 = np.mean([i in np.argsort(-row)[:10] for i, row in enumerate(p @ t.T)])
    return (f"held-out n={len(te)} cos median={np.median(cos):.4f}  nn@1={nn_hit:.3f}  "
            f"hit@10={hit10:.3f}  (chance@10={10 / len(te):.3f})")


if __name__ == "__main__":
    main(*sys.argv[1:])
