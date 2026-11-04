# Gate log (real terminal output only)

## G0 — Phase 0 (in progress, Nov 2 2026)

### 0.4a Local E4B tool-calling smoke (no competition data needed) — PASS
llama.cpp 0.8.0 (build 11960), gemma-4-E4B-it-Q4_K_M.gguf (4.6 GB), `--jinja -c 32768 -ngl 99`, Apple M5 24 GB.
Server healthy after 4 s. One request, 17k-token prompt, edit_file tool whose old_string contains a """ docstring:
```
wall=28.6s prompt_tokens=17330 completion_tokens=178
prefill_tok_s=774 decode_tok_s=28.7
tool_calls=1
name: edit_file | keys: ['filepath', 'new_string', 'old_string']
old_string applies verbatim: True
old_string: '"""Break *iterable* into lists of length *n*."""'
```
Notes:
- The """ arg-mangling reported for vLLM's gemma4 parser did not occur here (n=1; not a claim).
- Rough per-task estimate (to be replaced by a measured full-task run): ~45 calls × ~300 decode tokens / 28.7 tok/s ≈ 8 min,
  + incremental prefill (prompt cache on) ≈ 2 min → ~10 min/task. Phase 4 budget: 60 h / (3 configs × k=3 × 10 min) ≈ 40 tasks.

### Pending (blocked on user account steps)
- 0.1 data download + fix_links      — needs main-comp join + Kaggle token
- 0.2 HARNESS_README                 — needs data
- 0.3 identity test                  — needs data + HF EmbeddingGemma license/token
- 0.4b full-task agent smoke         — needs data + Docker running

### Nov 3 — account check after main-comp join
- Main competition joined (user, Nov 3).
- Docker Desktop started: `docker info` → server 29.6.2 ✅
- Kaggle CLI: `Authentication required` (no `~/.kaggle/access_token`) ❌, user runs `kaggle auth login`
- HF: `Not logged in` ❌, user accepts EmbeddingGemma license + runs `uvx hf auth login`

### Nov 3 — 0.1 data + 0.2 harness + partial 0.3
**0.1 Data** (`kaggle competitions download -c gemma-4-developer-agent`, 20.4 GB, unzipped):
```
graphs: files=127 empty=0
embeddings: files=127 empty=0
tasks 129 unique commits 127 missing graph []
repos Counter({'fastapi': 67, 'rich': 48, 'requests': 13, 'httpx': 1})
edge types Counter({'calls': 2490})        # first graph
node keys ['name', 'text', 'id']           # no kind / file / line fields
```
- ⚠️ The "129/256 files are 0 bytes" finding does NOT reproduce on this release: files are commit-named only, none empty. `fix_links.py` is not needed. **Drop that claim from the paper and brief.**
- Async gap reproduces (fastapi_15661, AST vs graph ids, naive module mapping):
```
sync defs 3609, in graph 3247; async defs 884, in graph 0
```
**0.2 Harness:** see `notes/harness.md`. `search_similar_code` takes a node key, not text (offline, no encoder); typed edges are drop-in via `edge_type`.

**0.3 Embedding profile (no encoder yet; HF login still missing):**
```
vectors 4263 = graph nodes 4263 (1:1)
shape (2000, 256) dtype float32 norm med 3.9373 mean |mean| 0.0704
pairwise cos median 0.8521 p99 0.999
```
- Norm ≈ 3.94, not 1 → not a plain normalized sentence-embedding output (a truncated unit 768-d vector would have norm < 1). Identity with EmbeddingGemma looks **less likely**; cosine test still needed (scale-invariant).
- Pairwise cosine median 0.85 = heavily anisotropic space: one shared direction dominates cosine ranking. Candidate audit finding + cheap fix (mean-centering) to test in Phase 1.

### Nov 3 — 0.3 identity test (EmbeddingGemma-300m, fastapi_15661, n=1000 nodes)
`app/results/identity_fastapi_15661.txt`:
```
embeddinggemma/raw           cos median=-0.0088 p10=-0.0712 p90=0.0631  nn@1=0.000
embeddinggemma/doc           cos median=0.0052 p10=-0.0566 p90=0.0701  nn@1=0.002
embeddinggemma/code-query    cos median=0.0022 p10=-0.0631 p90=0.0692  nn@1=0.001
ridge embeddinggemma/raw     held-out n=200 cos median=0.9513  nn@1=0.040  hit@10=0.245  (chance@10=0.050)
ridge embeddinggemma/doc     held-out n=200 cos median=0.9522  nn@1=0.035  hit@10=0.265  (chance@10=0.050)
ridge embeddinggemma/code-query held-out n=200 cos median=0.9519  nn@1=0.035  hit@10=0.245  (chance@10=0.050)
```
**Verdict:**
- Identity hypothesis ❌ **rejected**: cosine ≈ 0, nn@1 ≈ 0. The stored vectors are not EmbeddingGemma@256 under any of three prompt formats.
- Learned projection ⚠️ **weak**: held-out hit@10 = 0.27 (5× chance, 1 repo, 800 train pairs). The 0.95 cosine is inflated by anisotropy (pairwise median 0.85), so it is not evidence of a good fit.
- Harness constraint (notes/harness.md): `search_similar_code` only accepts node keys, offline. **No text→vector bridge can run at eval time** whatever its quality.

**Decision (pivot rule from 03-concepts.md, applied):** demote C3.
- C3 shrinks to an audit finding: "the released vectors are not a public text encoder, are anisotropic, and the tool cannot embed text", plus this table. No more time on the projection.
- Effort moves to C2 (typed repair) + C4 (localizer over the repaired graph, seeded lexically from issue text), which work inside the harness through `get_code_neighbors(edge_type=...)`.
- Concept B pivot is **not** triggered: the audit (async 0/884) and repair are intact.

### Nov 3 — 0.4b full-task agent smoke (harness + local E4B + Docker)
Setup:
- Harness: `swegemma 0.2.11`, `adk_submission 0.2.13`, `adk_eval_core 0.1.0`, `google_adk 1.36.1` from Kaggle dataset `metric/gemma-4-developer-agent-wheelhouse` → `.venv-harness` (lock: `app/harness_wheels/requirements.lock`).
- Sandbox image `swebench-sandbox:latest` built from `docker/Dockerfile.public`, `--platform linux/amd64` (8 test wheels are x86-only).
- Model: llama-server E4B Q4_K_M, `-c 32768`, alias `gemma-4-e4b-it-qat-w4a16-ct`, via `LOCAL_INFERENCE_URL`.
- Submission `app/submissions/b0` = sample_submission, model → E4B, adapters removed, budgets 50 calls / 30 min.

Attempts (requests_7505):
1. `swegemma eval` → `ImportError: cannot import name 'CacheableResult' from 'mcp.types'` (litellm 1.106.6 vs mcp 1.30.0). Fix: `mcp` → 2.3.0.
2. `swegemma eval` → `ContextWindowExceededError ... (32858 tokens) exceeds ... (32768)` after 23 tool calls. Cause: the CLI does not configure ADK EventsCompaction/ContextCache; the scoring script + starter notebook do. Fix: `app/runner/run_eval.py` (notebook-identical EvalConfig).
3. `runner.run_eval` →
```
Evaluation complete: 0/1 resolved (0.00%)
resolved=False agent_patch_size=799 test_exit_code=1 duration_seconds=246.52 error=None tool_calls=11 total_llm_calls=15
tools: read_file 6, run_command 2, code_analyzer_agent 1, search_similar_code 1, get_code_neighbors 1, edit_file 1, submit_patch 1
pytest: 4 failed, 138 passed, 1 skipped, 1 xfailed, 4 warnings, 197 errors in 8.50s
E  recursive dependency involving fixture 'httpbin' detected
```
**Gate G0: ✅ PASS (pipeline).** Agent → patch → Phase 2 verification all run locally, with graph tools called and traces written.

⚠️ **Fidelity gap:** the public wheels have no `pytest-httpbin`, so every `requests` test that uses `httpbin` errors in the local sandbox. Resolution needs `errors == 0`, so **requests tasks (13/129) can't resolve locally** whatever the patch. Kaggle may use private wheels (`data/competition_data/secret/sandbox/wheels` path in `container_setup.py`).
→ **Phase 1 first job:** a gold-patch verification sweep (task `patch` as the agent patch) over all 129 tasks to define the locally verifiable task set. That's also a benchmark-card table for the paper.

Timing: 246 s for 11 tool calls (n=1). Phase 4 estimate revised from ~10 to ~5 min/task: N ≈ 60 h × 60 / (3 configs × 3 runs × 5 min) ≈ 80 tasks. Re-measure on 5 tasks before pre-registering.

---
## Phase 1 — C1 audit (Nov 3)
Code: `app/mtm/ast_index.py` (AST ground truth + released-builder id emulation), `app/mtm/audit.py`, `app/tests/test_audit.py`.
Run: `cd app && ../.venv/bin/python -m mtm.audit` (127 commits, 90 s CPU). Outputs in `app/results/audit/`.

**Builder reverse-engineered exactly.** The released ids are reproduced by: module path (a few trees rooted below the repo, e.g. `docs_src/`), classes always at module scope, functions under a single global `current_class` that is *cleared, not restored*, on leaving any class. With that rule **every one of 367,985 released nodes across 127 graphs is explained (0 unexplained)**. Side effects measured:
- 2,704 top-level methods filed under the wrong scope (e.g. `TestRequests.test_conflicting_post_params` → `tests.test_requests.test_conflicting_post_params`, after a class nested in an earlier method).
- 9,111 AST symbols collide on a flattened id with another symbol (node text belongs to only one of them). Presence is therefore checked by id **and** node text.

Table 1 (`results/audit/table1.md`, all repos):
- top-level sync functions 288,588/289,266 (99.8%) · **async functions 0/65,415 (0.0%)** · classes 94.2% · modules 0/88,857 · nested defs 72.7%
- edge types: `calls` only (452,588); 13.1% of `calls` edges are really class→method containment
- gold edit sites (enclosing symbol of each changed line, 573 sites): 449 in graph (78.4%); **async 0/56**; 122 module-level, 49 new files. 20/129 tasks touch an async function.
- issue-seeded reachability (seed = issue token equal to a node's last name, fan-out ≤ 50; undirected): gold within ≤1 hop 30.2%, ≤2 34.9%, **≤3 48.1%** — independently matches Ali Hassan's 47.9%.

vs. the external audit: Jason Wold reported 0/305 async vs 4,739/4,740 sync. We get 0/65,415 async defs over all 127 graphs and 0/56 async gold sites over 129 tasks. Same conclusion, different denominator (his was a subset; his exact counting isn't published). We report ours.

`pytest tests/test_audit.py` → `8 passed in 0.39s`

---
## Phase 1 — gold-patch validity sweep (Nov 3)
Code: `app/runner/gold_sweep.py` (harness Phase 2 verifier, no model: `gold` = task `patch` as agent patch, `empty` = no patch), `app/mtm/validity.py`. ~11 s/task, concurrency 3.
```
gold: 43/129 resolved (33.33%)
empty: 4/129 resolved (3.10%)
| repo | tasks | verifiable | gold fails | empty passes |
| fastapi | 67 | 1 | 66 | 0 |
| httpx | 1 | 0 | 1 | 0 |
| requests | 13 | 0 | 10 | 3 |
| rich | 48 | 38 | 9 | 1 |
| all | 129 | 39 | 86 | 4 |
Gold-patch failure reasons:
- env: missing wheel `typing_inspection`: 62
- tests fail with gold patch: 9
- env: missing wheel `pytest-httpbin`: 8
- env: missing wheel `dirty_equals`: 4
- env: AttributeError: module 'httpx' has no attribute 'Stream': 1
- env: missing wheel `attr`: 1
- harness: Required test node did not pass: test_traceback_finely_grained_missing: 1
```
**Only 39/129 tasks are locally verifiable with the public wheelhouse.** 75 of the 86 gold failures are 4 missing wheels (`typing_inspection`, `pytest-httpbin`, `dirty_equals`, `attrs`). The empty-patch control passes on 4 tasks (3 requests, 1 rich), which are invalid as benchmarks regardless.
⚠️ GAP: whether Kaggle's private scoring wheelhouse includes these is unknown. Fix proposed: a supplemental wheelhouse (`data/wheels_extra/`, linux x86_64/py3-none wheels from PyPI) and a re-sweep. Expected ~110 verifiable tasks. This needs the user's OK (downloads from PyPI).
Paper value: a "benchmark card" table. The public eval environment silently fails 2/3 of the reference fixes, so local numbers from the public kit are not comparable to leaderboard numbers.

---
## Phase 1 — supplemental environment ("wheels_plus") + re-sweep (Nov 3)
User approved adding missing wheels from PyPI. Pinned linux_x86_64 / cp313 wheels, sha256 in `app/harness_wheels/wheels_extra.sha256`.
- `data/wheels_extra/` (auto-injected): typing_inspection, dirty_equals, attrs, pytest_httpbin + httpbin, blinker, decorator, six, brotlicffi, cffi, pycparser, greenlet. `data/wheels_plus/` = official + extras.
- `data/wheels_optional/` (NOT auto-injected; installed per repo only if its own test deps list it): inline_snapshot, asttokens, executing, python_multipart, ujson, orjson.

Runner options (`runner/run_eval.py`, all opt-in, default = official behaviour):
- `--wheels-dir data/wheels_plus` → also unpacks `pytest_httpbin`, which the harness excludes from injection.
- `--copy-wheels` → copies wheels to `/wheels` + `/wheels_opt`, then `PIN_SCRIPT` (a) reinstalls any `[project]` dependency whose injected version violates the repo's spec, choosing the highest `/wheels` version that satisfies it, and (b) installs the repo's own test extras from `/wheels_opt`.
- Always: the harness's unpacked-wheel tar cache is keyed by wheel set (`isolate_wheel_cache`).

Harness behaviours found on the way (paper "benchmark card" material):
1. **Stale wheel cache:** `sp_base.tar` is cached by name in `$TMPDIR` and never invalidated. A changed wheel set silently reuses the old tar. Our first sweep ran on a stale tar. Re-run with a clean, wheel-set-keyed cache: **identical result, `gold: 43/129, empty: 4/129, verifiable 39/129`**, so the official-kit baseline stands.
2. **Pins ignored under Docker:** only one deduplicated (newest) version of each wheel is injected. The `/wheels` copy is skipped, and `setup.py` maps names to a single file, ignoring version specifiers. Old fastapi tasks get Starlette 1.6 → `Router.__init__() got an unexpected keyword argument 'on_startup'` (48 tasks in an intermediate run).
3. **No `RECORD` files:** injected packages lack them, so pip can't uninstall them (`--ignore-installed` needed).
4. **Plugin shadowing:** a pytest-plugin wheel that imports the repo's own package (inline_snapshot → rich) makes the tests import the *installed* `rich` instead of the workspace. The empty patch "resolved" 32/48 rich tasks in that run. That's why test extras are per-repo and not injected.

Final wheels_plus sweep:
```
gold: 104/129 resolved (80.62%)
empty: 6/129 resolved (4.65%)
| repo | tasks | verifiable | gold fails | empty passes |
| fastapi | 67 | 60 | 5 | 2 |
| httpx | 1 | 0 | 1 | 0 |
| requests | 13 | 0 | 10 | 3 |
| rich | 48 | 38 | 9 | 1 |
| all | 129 | 98 | 25 | 6 |
```
Remaining gold failures: requests 8 × `Network is unreachable` (offline sandbox; timeout tests need network), rich 9 × output-golden mismatches (pygments/terminal version), fastapi 5, httpx 1 (`httpx.Stream` missing). No further fixes attempted: diminishing returns.
**Verifiable set: `app/results/verifiable_tasks_plus.txt` (98 tasks: fastapi 60, rich 38).** Every later agent experiment uses `--wheels-dir data/wheels_plus --copy-wheels` on this set.
⚠️ GAP: Kaggle's scoring environment may differ in either direction. The paper will state that local numbers come from this documented environment, not from the leaderboard one.

**Benchmark card (official public kit → documented wheels_plus env):** verifiable 39 → 98 / 129 · gold resolves 43 → 104 · empty-patch resolves 4 → 6.

### Nov 3 — Gate G1: Kaggle notebook v0 (private) ✅
- Built by `app/kaggle/build_notebook.py` from the repo's own `mtm/ast_index.py` + `mtm/audit.py` (verbatim `%%writefile`); `audit.py` now reads `MTM_DATA` / `MTM_OUT` env vars (defaults unchanged, 8/8 tests still pass).
- Pushed private: https://www.kaggle.com/code/saurinpatel16/mind-the-map-c1-code-graph-audit (v1, CPU, internet off, competition source `gemma-4-developer-agent`, mounted at `/kaggle/input/competitions/gemma-4-developer-agent`).
- Kaggle run status `KernelWorkerStatus.COMPLETE`; output downloaded to `app/kaggle/output_v1/`:
```
identical to local run: True                 (in-notebook assert on table1.md)
kaggle table1 identical to local             (cmp)
coverage.csv / gold_sites.csv / reach.csv / edges.csv identical
```
- Validity tables (official 39/129, wheels_plus 98/129) are embedded as static markdown, labelled "local Docker sweep, not rerun here" — notebooks have no Docker.
**Gate G1 closed.**

### Nov 3 — C1 audit correction (found while building C2)
`released_match` under-counted presence: released **class** texts start with their decorator lines (`@dataclass`) and drop trailing comments (`# type: ignore`), so the def-line check failed for those. Also `@overload` typing stubs were taken as the canonical definition instead of the implementation. Fixed in `mtm/ast_index.py` (+2 tests, 10/10 pass), audit rerun:
```
                         before        after
classes in graph         94.2%    ->   63810/63831 (100.0%)
nested defs              72.7%    ->   19856/26877 (73.9%)
top-level sync fn        288588   ->   288796/289266 (99.8%)
gold sites in graph      78.4%    ->   468/573 (81.7%)
gold ≤1/≤2/≤3 hops       30.2/34.9/48.1%  ->  31.0/35.7/49.6%
async fn 0/65415, modules 0/88857, edge types calls:452588, unexplained released nodes 0   (unchanged)
```
⚠️ Kaggle notebook v1 still shows the old Table 1 (it asserts equality with the old local file). Needs a v2 push (user OK).

### Nov 3 — Phase 2: C2 typed repair — Gate G2 ✅
`mtm/repair.py` (all 127 graphs in 31 s, 10 processes) → `data/graphs_repaired/`; report `mtm/repair_report.py` → `results/repair/`.
Totals: nodes 367,985 → 529,769 (+88,857 modules, +70,117 async functions, +2,417 functions, +393 classes; new = symbols the released graph lacks); edges 452,588 → 1,256,926.
```
| repo | superset violations | gold def sites: released → repaired | module-level gold sites | async gold sites | gold ≤2 hops: released → repaired → repaired w/o `contains` | contains | calls | imports | inherits | overrides | tests |
| fastapi | 0 | 324/375 → 375/375 | 0/85 → 85/85 | 0/51 → 51/51 | 17/67 → 46/67 → 43/67 | 340572 | 242555 | 121109 | 8378 | 2216 | 16691 |
| httpx | 0 | 14/19 → 19/19 | – | 0/5 → 5/5 | 1/1 → 1/1 → 1/1 | 840 | 1812 | 112 | 32 | 82 | 118 |
| requests | 0 | 13/13 → 13/13 | 0/6 → 6/6 | – | 6/13 → 9/13 → 9/13 | 8984 | 24111 | 2381 | 433 | 134 | 8416 |
| rich | 0 | 117/117 → 117/117 | 0/31 → 31/31 | – | 22/48 → 37/48 → 35/48 | 94561 | 276805 | 40993 | 3572 | 3008 | 59011 |
| all | 0 | 468/524 (89.3%) → 524/524 (100%) | 0/122 → 122/122 | 0/56 → 56/56 (100%) | 46/129 (35.7%) → 93/129 (72.1%) → 88/129 (68.2%) | 444957 | 545283 | 164595 | 12415 | 5440 | 84236 |
```
(Table 1's 573 = these 524 def sites + 49 edits in brand-new files, which no base graph can hold.)
- [x] Async coverage of edited symbols ≥ 95% → **56/56 (100%)**
- [x] Superset: every released node id, `name`, `text` and every released edge (incl. key) present → **0 violations over 127 graphs**
- [x] Harness `load_graph_from_json`: **127/127** (graph files are per commit; 129 tasks share 127 commits). Neighbour tool on repaired vs released graph (`results/repair/harness_check.txt`), task fastapi_15745:
```
async gold site ...tutorial002_py310.read_items   released: []  repaired: [its module]  (also via edge_type=contains)
fastapi.routing.APIRoute  inherits                released: []  repaired: [GzipRoute, ..., TimedRoute]
HTTPBasic.__call__        overrides               released: []  repaired: [fastapi.security.http.HTTPBase.__call__]
fastapi.routing.run_endpoint_function (async) calls  released: []  repaired: [fastapi.routing.get_request_handler.app]   # matches the source comment "Only called by get_request_handler"
fastapi.routing           imports                 released: []  repaired: [lenient_issubclass, ModelField, fastapi.applications, ...]
APIRouter.add_api_route   calls                   released: 3   repaired: 5
```
- [x] `pytest tests/` → **17 passed** (test_repair.py 7: re-export / self / super() resolution, async callers, no guessing on unknown receivers, structural edges, tests→code only, real-graph superset + types)

Honest limits (for the paper): resolution is static and conservative (no type inference: `obj.method()` on unknown receivers is skipped), so our `calls` recall vs the released name-matched `calls` is partial (requests_7505: 487/1495 released non-containment calls reproduced; 207 new). Released edges are all kept, so B2 sees a superset of B1. Module nodes carry the first 40 lines of the file. New nodes have no stored embedding → the harness gives them a zero vector (search_similar_code can't rank them; C3/C4 handle retrieval).

### Nov 3 — Kaggle notebook v2 (Table 1 correction) ✅
Rebuilt with the fixed `ast_index.py` (decorator/comment matcher, `@overload` stubs) and pushed as version 2 (private). Kaggle status `COMPLETE`; output in `app/kaggle/output_v2/`:
```
identical to local run: True
table1.md / coverage.csv / gold_sites.csv / reach.csv / edges.csv identical
```
The notebook now reproduces the corrected Table 1 (classes 100.0%, gold sites in graph 81.7%, ≤3 hops 49.6%).

### Nov 3 — Phase 3: C4 localizer + model-free benchmark — Gate G3 ✅
`mtm/localize.py` (59 s, all 129 tasks; 128 have a localizable gold file, 1 edits only a new file). Methods: grep (code-like issue identifiers), BM25 (files / nodes), released-graph 2-hop (Ali Hassan protocol), repaired-graph 2-hop, C4 = Personalized PageRank over typed edges seeded by identifiers + BM25 top-20 nodes, on released (`calls`) and repaired graphs. C4 hyperparameters (alpha × BM25 mix × 32 edge-type subsets = 288 configs repaired, 9 released; 38,016 sweep runs) chosen **leave-one-repo-out** on file Hit@5. C3 bridge dropped (Phase 0).
Table 2 (all folds; full per-fold + verifiable-98 tables in `results/localize/table2.md`):
```
| method        | n   | file@1 | file@5 | file@10 | sym@1 | sym@5 | sym@10 | sym_2hop@5 |
| grep          | 128 | 27.3 | 49.2 | 57.0 | –    | –    | –    | –    |
| bm25          | 128 | 27.3 | 56.2 | 71.1 | 18.0 | 39.8 | 48.4 | 75.8 |
| released_2hop | 128 | 29.7 | 43.8 | 47.7 | 15.6 | 26.6 | 30.5 | 51.6 |
| repaired_2hop | 128 | 31.2 | 50.0 | 56.2 | 17.2 | 31.2 | 35.9 | 66.4 |
| c4_released   | 128 | 32.0 | 63.3 | 79.7 |  9.4 | 27.3 | 41.4 | 82.8 |
| c4            | 128 | 30.5 | 61.7 | 75.0 | 10.2 | 32.8 | 44.5 | 79.7 |
```
Paired exact McNemar (exploratory, unadjusted):
```
c4 vs grep file@5: 31 vs 15, p=0.026 | file@10: 33 vs 10, p=0.001
c4 vs bm25 file@5: 18 vs 11, p=0.265 | file@10: 16 vs 11, p=0.442
c4 vs c4_released file@5: 10 vs 12, p=0.832 | file@10: 6 vs 12, p=0.238
repaired_2hop vs released_2hop sym_2hop@5: 22 vs 3, p<0.001 | file@5: 14 vs 6, p=0.115
```
LORO picks: repaired graph → calls+contains every fold (alpha 0.7, or 0.3 when rich is held out; mix 1.0 = BM25 seeds only); released → calls, alpha 0.7.
Calibration (C4 top-file share): **not calibrated**: 0.2–0.4 → 32.3% Hit@1 (n=99), 0.4–0.6 → 22.2% (n=27), 0.6–0.8 → 50% (n=2). Post-hoc signal that does separate: C4 top file == BM25 top file → Hit@1 20/42 (48%) vs 19/86 (22%). Adopted as B2's confidence label and pre-registered as exploratory.
**Honest reading:** graph-PPR localization beats grep significantly and BM25 numerically (not significantly). The repair does not improve C4's file ranking; it does significantly improve 2-hop symbol reachability (the agent-facing tool metric). `tests`/`imports`/`inherits`/`overrides` edges were never selected by LORO for file ranking; their value, if any, has to show in the agent runs.
- [x] Table 2 per LORO fold (+ verifiable subset)
- [x] Calibration bins (negative result, plus the agreement signal)
- [x] `notes/prereg.md` committed before any Phase 4 run: **`cf3908bf09c36255d3cc37c2d53a08ed10add0e6`** (first commit, 1,432 files). Task order `results/phase4_task_order.txt` sha256 ec26f87a… is in that commit.
Tests: `pytest tests/` → 23 passed (test_localize.py 6: tokenizer, code identifiers, BM25, PPR distribution, confidence, LORO never tunes on the held-out repo).

### Nov 3 — Phase 4 setup
- `submissions/b0|b1|b2`: same system prompt (one line made tool-neutral: it named `search_similar_code`, which B0 lacks), sampling per prereg (temperature 1.0, top-p 0.95, thinking 4096, max output 16384; the starter's temperature was 0.2). B0 drops the 3 graph tools and the code-analyzer sub-agent; B1 = B2 files.
- `mtm/hints.py` → `data/tasks_b2.jsonl`: only `problem_statement` differs (hint prepended, original kept verbatim, checked); 42/129 high confidence (= the C4/BM25 agreement count from Phase 3).
- `runner/phase4.py`: task-major → config → run order, one results dir per unit, resumable, one retry then recorded as unsolved. `runner/run_eval.py` gained `--tasks-path`.
- llama-server E4B Q4_K_M `--jinja -c 32768 -ngl 99`, alias `gemma-4-e4b-it-qat-w4a16-ct`, :8089.
Smoke (rich_3676, last task in the order, so outside the first N; discarded):
```
B0 resolved=False 167 s, tools {read_file 1, edit_file 1, run_command 2, submit_patch 1}, no graph tools in prompt, no hint
B1 resolved=False 590 s, tools {read_file 6, edit_file 6, run_command 5, submit_patch 1}, graph tools offered
B2 resolved=False 290 s, tools {read_file 3, code_analyzer_agent 1, edit_file 1, run_command 2, submit_patch 1}, <localizer> block present
```
Timing run (prereg §3; B1, run 1, first 5 tasks; discarded): wall 284.4 / 426.3 / 184.5 / 137.3 / 516.7 s → median 4.74 min; 0/5 resolved. **N = floor(60·60 / (3·3·4.74)) = 84** (fastapi 52, rich 32), written to `notes/prereg.md` (not yet committed). 84 × 3 configs × 3 runs = 756 units ≈ 60 h.
⚠️ Floor-effect risk: E4B resolved 0/8 units so far (smoke 0/3, timing 0/5). If the true solve rate is a few %, the paired B2−B0 CI will likely include 0 → reported as "no detectable effect at this N" (prereg §6). Secondary metrics (turns to first gold-file read, tool calls) still carry the localization signal.
**Launched Nov 3 23:29 UTC** after commit `88228376126e97c4602dca370ddb396b55bf35b9` (N = 84 in prereg). `caffeinate -ims runner.phase4 --n 84` → `app/results/phase4/`, progress in `app/results/phase4.log` and `app/results/phase4/driver.jsonl`.

**Nov 4 03:40 UTC — amendment 1 committed** (`d72c26a`); 13 units finished by then, all unresolved, seen as progress lines only.
**Nov 4 03:50 UTC — pace problem.** ~19 min/unit observed vs 4.74 planned → 756 units ≈ 240 h > deadline. Amendment 2 drafted in `notes/prereg.md`: stop driver Nov 10 00:00 UTC; primary analysis = tasks with all 9 units complete at cutoff (~50 expected).

## Phase 5 — paper draft v0.1 (Nov 4)
- `paper/writeup.md`: all sections except §6 results, abstract's last sentence and conclusion (marked PENDING PHASE 4).
- `sed -e 's/<!--.*-->//' paper/writeup.md | wc -w` → 2682 (incl. title, tables, references; limit 3,000).
- New `app/mtm/mcnemar.py` → `app/results/localize/mcnemar.md`; reproduces the Phase 3 McNemar numbers and the 20/42 vs 19/86 agreement split exactly.
- `notes/claims.md`: every number → source file. Two untraced numbers dropped from the paper (calls recall 487/1,495; empty patch 32/48 rich).
- Open: Figures 1–2; verify reference venues/ids (L1, C1, R1, O1, C2, B1); Kaggle Writeup submit + screenshot (Gate G5).
- Nov 4: Figures 1 (pipeline) and 2 (coverage/edges) from `app/mtm/figures.py`, numbers parsed from result files. References verified by web search: LocAgent arXiv 2503.09089; CodexGraph NAACL 2025 / 2408.03910; RepoGraph ICLR 2025 / 2410.14684; OrcaLoca ICML 2025 / 2502.00350; CoSIL ASE 2025 / 2503.22424; Bjarnason, Silva, Monperrus arXiv 2602.07150 (no ICLR venue found → removed). Word count 2,760.
- Nov 4: v0.2 reframe (user: "remove what didn't work"). Cut: ridge projection, norm stats, calibration bins, "edges never helped" line, confidence-label limitation (still flagged exploratory in §5). Kept in one line each, as prereg §6 requires: C4 vs BM25 n.s., C4 released vs repaired p = 0.83. Title/abstract lead with audit, repair (2× reachability), benchmark card. Words 2,679.

## Phase 6 — resource release (Nov 4)
- Rules check (competition Rules §2.4b): "You agree not to transmit, duplicate, publish, redistribute ... the Competition Data to any party not participating". Repaired graphs embed every released node/edge + snapshot text → **not published**.
- `app/mtm/export_dataset.py` → `release/gemma4-swe-typed-graphs/`: typed deltas only (127 commits, +161,784 nodes without text, +804,338 edges; 367,985+161,784 = 529,769 and 452,588+804,338 = 1,256,926 match Gate G2), labels, tables, code, README/datasheet. No `problem_statement` in labels/tables (grep).
- `tests/test_export.py`: released graph + delta (+ snapshot text) reproduces every repaired graph exactly, all 127 → `pytest tests/` 24 passed.
- Kaggle Dataset created **private**: https://www.kaggle.com/datasets/saurinpatel16/gemma4-swe-typed-graphs (status ready, files listed). Public flip pending user OK.
- Nov 4: dataset made **public** (user OK) via `kaggle datasets metadata --update` (license `apache-2.0`, `isPrivate: false`). Logged-out check: `GET /api/v1/datasets/view/...` → 200, `isPrivate: False`, `licenseName: Apache 2.0`; logged-out file list returns files (README.md, code/mtm/...). Paper Resources line now links it.
