"""Model-free task validity sweep: which tasks can be resolved in this local harness at all?

For each task, run the harness's own Phase 2 verifier twice, with no agent:
  gold  - the task's reference `patch` as the agent patch  -> should resolve
  empty - no patch                                         -> should NOT resolve
A task is locally verifiable iff gold resolves and empty does not.

Run from app/ with the harness venv:
  ../.venv-harness/bin/python -m runner.gold_sweep --submission submissions/b0 --results results/gold --concurrency 3
  ../.venv-harness/bin/python -m runner.gold_sweep ... --mode empty --results results/empty
"""
import asyncio

from adk_eval_core.tracing import SessionTrace
from swegemma.evaluate import Evaluator

from runner.run_eval import build_config, parser


class GoldEvaluator(Evaluator):
    """Skips Phase 1 (agent) and hands the reference patch straight to verification."""

    async def _run_agent_sandbox(self, task, snapshot_path, *args, **kwargs):
        return task.patch, None, SessionTrace()


def main() -> None:
    ap = parser()
    ap.add_argument("--mode", choices=["gold", "empty"], default="gold")
    args = ap.parse_args()
    if args.mode == "gold":
        result = asyncio.run(GoldEvaluator(build_config(args)).run())
    else:
        result = asyncio.run(Evaluator(build_config(args, skip_agent_patch=True)).run())
    print(f"{args.mode}: {result.resolved}/{result.total} resolved ({result.resolution_rate:.2%})")


if __name__ == "__main__":
    main()
