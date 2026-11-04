# Pre-registration: Phase 4 agent evaluation (C5)

Status: **REGISTERED** at commit `cf3908bf09c36255d3cc37c2d53a08ed10add0e6` (Nov 3, 2026). No Phase 4 agent run may start before that commit. Any later change is logged at the bottom with its date and reason, and the paper reports it.

## 1. Question
Does giving a small local agent (Gemma 4 E4B) the repaired typed graph and the C4 localizer raise its per-task solve rate, compared with (a) no graph tools and (b) the graph tools as released?

## 2. Configurations
All three use the same model, prompts, sampling, budgets and harness. Only the graph-related tools differ.

| id | graph tools | graph dir | localizer |
|---|---|---|---|
| B0 | none: `get_code_neighbors`, `search_similar_code`, `get_code_subgraph` and the code-analyzer sub-agent are removed | – | – |
| B1 | as shipped in the starter submission | `data/graphs` (released) | – |
| B2 | as B1 | `data/graphs_repaired` | C4 hint at task start (below) |

- **B2 localizer hint.** A short block is prepended to the task. It lists C4's top-5 files and top-10 symbols, using the leave-one-repo-out hyperparameters for the task's repo (`results/localize/loro_choice.csv`, repaired-graph rows).
  - It also gives a confidence label. The label is **high** when C4's top file equals BM25's top file, otherwise **low**.
  - On high, the prompt says to start at that file. On low, it says to treat the list as hints and verify with search.
  - The label rule was chosen after seeing model-free results (Hit@1: 20/42 when the two agree, 19/86 when they don't). It is reported as exploratory, not tuned further.
- **Model:** `gemma-4-E4B-it` Q4_K_M via llama.cpp `llama-server`, `--jinja -c 32768`, served under the alias in `submissions/*/agent.yaml`.
- **Sampling:**
  - temperature 1.0, top-p 0.95;
  - thinking on, `thinking_budget` 4096, `max_output_tokens` 16384.
- **Budgets:** as in `submissions/b0/eval_config.yaml`: 50 tool calls, 30 min, 50 turns, 300 s verification timeout.
- **Harness:** `swegemma` 0.2.11 via `runner/run_eval.py`, with the starter notebook's compaction and caching, plus `--wheels-dir data/wheels_plus --copy-wheels`.

## 3. Tasks
- **Pool:** the 98 locally verifiable tasks (`results/verifiable_tasks_plus.txt`: gold resolves, empty patch does not, in the documented `wheels_plus` environment).
- **Order:** fixed in `results/phase4_task_order.txt`:
  - stratified by repo (fastapi 60, rich 38);
  - ordered by sha256(`mtm-prereg:<id>`);
  - interleaved so that any prefix keeps the ratio;
  - file sha256 `ec26f87af19d61574e75d3337f2c5103db8f2c98f16c840bdedadef1b694a871`.
- **N:** the first N tasks of that order, where N = floor(available machine-hours × 60 / (3 configs × k × minutes per task)).
  - Minutes per task is the median wall time of B1 on the first 5 tasks of the order, measured once before the main runs. Those 5 runs are discarded.
  - N is then fixed, written below, and committed before the main runs. ⚠️ GAP: timing not yet re-measured (one run took ~4 min). At about 5 min/task over 60 h, N ≈ 80.
- **Exclusion:** none after selection. Any harness crash is retried once; if the retry also fails, the run counts as unsolved and is reported.

## 4. Runs
- k = 3 runs per (config, task).
- Run order is interleaved: task-major, then config, then run index. This stops time-of-day or machine drift from aligning with a config.

## 5. Outcomes and analysis
- **Primary outcome:** per-task solve rate, the mean over k runs of the harness's `resolved` flag.
- **Primary comparisons:** B2 vs B0 and B2 vs B1. Holm correction over the two, family α = 0.05.
  - **Effect:** mean over tasks of (solve rate B2 − solve rate X). 95% CI from a paired task-level bootstrap (10,000 resamples, seed 0).
  - **Test:** exact McNemar on paired binary outcomes, pairing (task, run index) across configs.
- **Secondary, descriptive only (no test):**
  - B1 vs B0;
  - per-repo solve rates;
  - mean tool calls, tokens, wall minutes;
  - turns before the agent first reads a gold file;
  - B2 solve rate split by the high/low confidence label.
- **Model-free localization (already run; reported as is):** `results/localize/table2.md`. Exact McNemar on paired Hit@k, unadjusted, labelled exploratory.

## 6. What would count as a negative result
- If the B2 − B0 CI includes 0, we report "no detectable effect at this N". We do not add tasks, change k, change configs or re-pick the subset to change that.
- The model-free results (C4 vs BM25 not significant; C4 on released vs repaired graph p = 0.83) are reported whatever Phase 4 shows.

## N (fixed Nov 3, 22:47 UTC, before any main run)
- Timing run, B1, run 1, first 5 tasks of the order, wall time per unit from `results/phase4_timing/driver.jsonl`: 284.4, 426.3, 184.5, 137.3, 516.7 s. Median **4.74 min**. All 5 unresolved; these runs are discarded.
- Available machine-hours: 60, the budget from `05-build-plan.md`.
- **N = floor(60 × 60 / (3 × 3 × 4.74)) = 84**, the first 84 tasks of `results/phase4_task_order.txt`.

## Changes after registration
- **Amendment 1 (Nov 3, 23:40 UTC; main run started 23:29 UTC. Written before any main-run unit finished. Committed Nov 4, 03:40 UTC, by which time 13 units had finished: all 9 of fastapi_14605 and rich_3772 B0 r1–r3 and B1 r1, all unresolved. They were seen only as the driver's one-line progress output (resolved, duration, tool calls); their logs, patches and failure classes were not inspected before this commit).** Adds one secondary, descriptive outcome: a failure taxonomy of every unit, using `app/mtm/failures.py` as committed with this amendment. Classes, checked in order: resolved, harness_error, no_patch, broken_syntax, broken_import, hang, tests_fail. Reported per config as counts and shares, with no test. The primary outcome, comparisons, N, k, configs and tasks are unchanged.
  - *Why:* all 8 discarded smoke and timing runs were unresolved. On manual inspection, 5 of the 8 were the agent breaking its own edit (literal `\n`, indentation drift, or a test hang), not wrong logic. A near-zero solve rate would hide whether the localizer changes *how* the agent fails.
  - The classifier was written and checked on those 8 discarded runs only (B0 1 tests_fail; B1 2 broken_syntax, 1 broken_import, 2 hang, 1 tests_fail; B2 1 tests_fail).
- **Amendment 2 (Nov 4, ~03:50 UTC; drafted when 14 units had finished, all unresolved, seen only as progress lines): fixed stop date.**
  - *Why:* the timing run underestimated cost. N = 84 assumed 4.74 min per unit; the first 13 main-run units took ~4.15 h of wall time (~19 min per unit, including harness setup and one 30-min unit). At that pace 756 units need ~240 h, past the Nov 12 23:59 UTC deadline. The stop is set by date, decided before any outcome other than the progress lines was seen.
  - *Rule:* the driver is stopped at **Nov 10, 00:00 UTC** (or earlier only if all 756 units finish). The **primary analysis set** is the tasks, in prereg order, whose 9 units (3 configs × 3 runs) all have a `task_results.jsonl` at the cutoff. Units of a task left incomplete are excluded from the primary analysis and listed in the paper.
  - Because the order is task-major and repo-interleaved (§3, §4), any complete-task prefix keeps the fastapi:rich ratio and has every config on the same tasks.
  - Expected N at the cutoff: ~50 tasks at the current pace. The actual N is reported as observed; it is not a target.
  - Everything else is unchanged: configs, k, sampling, budgets, task order, primary outcome, tests, Holm correction, null-result rule (§6). We will not extend the cutoff, restart, or re-pick tasks to change a result.
