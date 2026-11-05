# Mind the Map

Code and results for *Mind the Map: Auditing and Repairing the Released Gemma 4 Code Graphs*, a paper for the Kaggle Gemma 4 Developer Agent paper track.

- **Paper draft:** [`paper/writeup.md`](paper/writeup.md). Every number in it traces to a file through [`notes/claims.md`](notes/claims.md).
- **Dataset** (typed-graph additions, labels, tables; no Competition Data): [kaggle.com/datasets/saurinpatel16/gemma4-swe-typed-graphs](https://www.kaggle.com/datasets/saurinpatel16/gemma4-swe-typed-graphs)
- **Notebook** (reproduces audit Table 1 from the competition data): [kaggle.com/code/saurinpatel16/mind-the-map-c1-code-graph-audit](https://www.kaggle.com/code/saurinpatel16/mind-the-map-c1-code-graph-audit)
- **Pre-registration:** [`notes/prereg.md`](notes/prereg.md), with commit provenance in [`notes/provenance.md`](notes/provenance.md). Every gate's terminal output is in [`notes/gates.md`](notes/gates.md).

## What's here

| Path | Contents |
|---|---|
| `app/mtm/ast_index.py`, `audit.py` | C1 audit: an exact reconstruction of the released graph builder, plus coverage and reachability |
| `app/mtm/repair.py`, `repair_report.py` | C2 repair: the typed superset graph (`contains`, `calls`, `imports`, `inherits`, `overrides`, `tests`) |
| `app/mtm/localize.py`, `mcnemar.py`, `hints.py` | C4 localizer: Personalized PageRank tuned leave-one-repo-out, the model-free benchmark, and the B2 hints |
| `app/mtm/export_dataset.py` | Builds the public dataset and `merge_typed` |
| `app/mtm/failures.py` | Failure taxonomy (prereg amendment 1) |
| `app/runner/` | Harness runner, gold and empty-patch validity sweep, and the Phase 4 driver |
| `app/tests/` | 24 tests |
| `app/results/` | Audit, repair and localization outputs; validity tables; the pre-registered task order |

## Reproduce

You need the competition data. Join the competition at https://www.kaggle.com/competitions/gemma-4-developer-agent and download it to `app/data/`. Then:

```
cd app
python -m mtm.audit          # Table 1          (~90 s CPU)
python -m mtm.repair         # repaired graphs  (~31 s, 10 cores)
python -m mtm.repair_report  # repair gate table
python -m mtm.localize       # Table 2          (~60 s)
python -m mtm.mcnemar
python -m pytest tests/
```

The agent runs (`runner/phase4.py`) also need:
- the competition harness wheels;
- Docker;
- llama.cpp serving Gemma 4 E4B;
- the B0/B1/B2 submission configs, which are edits of the competition's sample submission (described in `notes/prereg.md` §2 and `notes/gates.md`).

The competition data, harness wheels and sample submission are not redistributed here, as the competition rules require.

## License

Apache 2.0.
