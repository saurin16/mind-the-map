# HARNESS_README: what matters for Mind the Map (read Nov 3)

| Fact | Section | Consequence for the paper |
|---|---|---|
| `search_similar_code(query)` resolves `query` to an **existing node key** and returns its cosine neighbours; multi-word text falls back to **lexical token overlap**. No embedding model in the sandbox (offline). | §6.3 #8 | Explains the 21/21 empty searches: issue text can never be embedded. The C3 bridge must precompute vectors **outside** the tool, or be exposed as a node-id list via a sub-agent prompt. |
| Graph tools load `data/graphs/<repo>.json` + `data/embeddings/<repo>.npz` into a NetworkX `CustomMultiDiGraph`; `edge_type` filter is free text. | §6.3 | A repaired graph with the same schema and new typed edges (`imports`, `contains`, `tests`, ...) is drop-in. `get_code_neighbors(node, edge_type="tests")` works with no harness change. |
| Every tool output capped at 5,000 chars. | §6.3 | Typed edges + ranking matter more than more edges (truncation). |
| Scoring: vLLM `:8000`, `tool_call_parser=gemma4`, `max_model_len=32768`, models via `LiteLlm(openai/<alias>, api_base=…)`. Falls back to attaching to an already-active endpoint. | §3.3 | Local runs: llama-server on an OpenAI `/v1` endpoint + `--models-yaml` mapping the alias. ⚠️ GAP: exact models.yaml schema, read from the installed `swegemma` package. |
| `swegemma eval --tasks --snapshots-dir --submission-dir --results-dir --sandbox docker --task-ids ...` | §9.1 | Our C5 runner = this CLI. Traces (`traces/trace_<id>.json`) give tool-call counts and turns-to-first-correct-read for free. |
| `--sandbox subprocess` exists. | §9.1 | Fallback if Docker-on-Mac (arm64) image build fails. |
| Thinking: use `include_thoughts: true` + `thinking_budget: 4096`, `max_output_tokens: 16384`. | §2.4, §10 | Fix these in all configs B0/B1/B2 (pre-register). |
| Read-only `AgentTool` sub-agent with `skip_summarization: true` is the recommended context isolator. | §10 #4 | The C4 localizer ships as exactly this. |
