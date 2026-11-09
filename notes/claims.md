# Claims → source (paper/writeup.md)

Every number in the paper, one line each. Paths are relative to `app/` unless noted. External claims are cited, not re-measured.

## Data / benchmark card (§2)
- 129 tasks, 4 repos (fastapi 67, rich 48, requests 13, httpx 1), 127 commits → `results/audit/table1.md` (tasks, commits columns)
- Official kit: verifiable 39/129, gold resolves 43, empty resolves 4 → `results/validity.md`, `results/gold_sweep.log`
- Four missing test deps (typing_inspection, pytest-httpbin, dirty_equals, attrs) → `results/gold_sweep.log` (failure reasons), `notes/gates.md` Phase 1 sweep
- Four harness behaviours; empty patch "resolved" 32/48 rich in an intermediate run → `notes/gates.md` "wheels_plus" section (32/48 dropped from the paper: log not kept; qualitative only)
- wheels_plus: verifiable 98/129 (fastapi 60, rich 38), gold 104, empty 6 → `results/validity_plus.md`, `results/gold_sweep_plus.log`
- Audit tables reproduced byte for byte on Kaggle → `kaggle/output_v2/` + `cmp` in `notes/gates.md` (notebook v2)

## Audit (§3, Table 1)
- 367,985 released nodes, 0 unexplained → `results/audit.log`, `notes/gates.md` Phase 1
- 2,704 mis-qualified; 9,111 id collisions → `results/audit/table1.md` (all row)
- sync 288,796/289,266 (99.8%); classes 63,810/63,831; nested 19,856/26,877 (73.9%); async 0/65,415; modules 0/88,857 → `results/audit/table1.md`
- `calls` only, 452,588 edges, 13.1% containment → `results/audit/table1.md`
- 573 def-level gold sites = 524 defs + 49 new-file; 122 module-level; 468/573 (81.7%) in graph; 105/573 = 18% missing → `results/audit/table1.md`, `results/audit/gold_sites.csv` (kinds: function 388, class 80, async_function 56, module 122, new_file 49)
- async gold 0/56; 20/129 tasks touch async → `results/audit/gold_sites.csv` (count printed Nov 4)
- reach ≤1/2/3 hops 31.0/35.7/49.6% → `results/audit/table1.md`, `results/audit/reach.csv`
- Community 47.9% → [A1]
- Embeddings: 4,263 nodes, cos median ≈ 0 (−0.0088 / 0.0052 / 0.0022), nn@1 ≤ 0.2%, norm median 3.89, ridge hit@10 0.245–0.265 vs chance 0.05 → `results/identity_fastapi_15661.txt`
- `search_similar_code` takes a node id only → `notes/harness.md`

## Repair (§4, Table 2)
- 0 superset violations; def sites 468/524 → 524/524; module 0/122 → 122/122; async 0/56 → 56/56; ≤2 hops 46/129 → 93/129 → 88/129 w/o contains → `results/repair/table_g2.md`, `results/repair/superset.csv`, `results/repair/gold.csv`, `results/repair/reach.csv`
- nodes 367,985 → 529,769; edges 452,588 → 1,256,926 → `results/repair.log`, `results/repair/repair.csv`
- 127/127 graphs load; typed-neighbour examples → `results/repair/harness_check.txt`
- calls recall 487/1,495, 207 new (requests_7505) → `notes/gates.md` G2 limits (numbers dropped from the paper: not in a results file; qualitative only)
- Module text = first 40 lines → `mtm/repair.py` MODULE_TEXT_LINES

## Localization (§5, Table 3)
- Table 3 values (128 tasks) → `results/localize/table2.md`
- LORO grid: α {0.3,0.5,0.7} × mix {0,0.5,1} × 32 edge subsets; picks calls+contains every repaired fold → `mtm/localize.py` `configs`, `results/localize/loro_choice.csv`
- McNemar: c4 vs grep 31/15 p=0.026, 33/10 p=0.001; vs bm25 18/11 p=0.265, 16/11 p=0.442; vs c4_released 10/12 p=0.832; repaired vs released 2-hop sym 22/3 p<0.001 → `results/localize/mcnemar.md` (`mtm/mcnemar.py`)
- Calibration 32.3% (n=99), 22.2% (n=27) → `results/localize/table2.md`
- Agreement 20/42 (47.6%) vs 19/86 (22.1%) → `results/localize/mcnemar.md`

## Agent study (§6)
- Design, sampling, budgets, k=3, prereg commit cf3908b → `notes/prereg.md`, `git log`
- Amendment 1 (8 discarded runs, 5 self-broken edits) → `notes/prereg.md`, commit d72c26a
- Amendment 2 (~19 min/unit vs 4.7, cutoff Nov 10 00:00 UTC, N=84 registered) → `notes/prereg.md`, commit df14b7e
- Results → PENDING (`mtm.stats` over `results/phase4/` after cutoff)

## External (cited, not measured)
- −5 tasks, 21/21 empty searches, 0/31 gold pre-edit → [T1]
- No async functions → [W1]; won't fix → [H1]
- grep first hit 30%, 35/128 no identifier → [J1]
- 15% flip → [Z1]; several-point single-run swings → [B1]

## Word count
- `sed -e 's/<!--.*-->//' paper/writeup.md | wc -w` → 2,696 (Nov 4, includes title, tables and references; ~300 words left for Phase 4 results)

## Figures (Nov 4)
- Fig 1 pipeline: labels only, no numbers → `app/mtm/figures.py` `pipeline_fig`
- Fig 2 coverage + edges: parsed at render time from `results/repair/table_g2.md` (all row) and `results/audit/table1.md` (released `calls` 452,588); repaired per-type totals sum to 1,256,926 (= repair.csv `edges`; `calls` 545,283 = 452,588 released + 92,695 added) → `app/mtm/figures.py` `coverage_fig`
- Palette: categorical slots 1–2 (#2a78d6, #eb6834), validator ALL PASS on light surface
- Word count after figures: 2,760

## Phase 4 results (Nov 9, prereg amendment 3) → `app/results/phase4_analysis/summary.json`, `table.md`
- 61 tasks (37 fastapi, 24 rich), 549 runs; excluded fastapi_14448 (1/9) → `incomplete_units`
- Solved B0 13/183 (7.1%), B1 12/183 (6.6%), B2 16/183 (8.7%) → `per_config.solved`
- B2−B0 +1.6 pp [−4.4, +8.2], discordant 11/8, Holm 0.848; B2−B1 +2.2 pp [−3.3, +8.2], 9/5, Holm 0.848 → `primary`
- Tool calls 9.3/11.6/11.7; tokens 102k/127k/129k; minutes (harness duration) 6.7/7.5/8.1; gold-file read 116/126/133 of 183 → `per_config`
- Mean agent steps to first gold read B0 2.1, B1 3.2, B2 1.8 → mean of `units.csv` gold_read_step (analysis set)
- Failures: tests_fail 94/107/93; syntax+import 44/40/46; no_patch 26/15/23 → `failures`
- B2 high 11/54, low 5/129 solved runs → `b2_by_confidence`
- Stop Nov 9 04:13:55 UTC (19.8 h before cutoff) → `notes/prereg.md` amendment 3
- Body word count (whitespace) 2,987 → `mtm.build_writeup`
