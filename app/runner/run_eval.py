"""Local evaluation runner that matches Kaggle scoring more closely than `swegemma eval`.

The CLI omits the ADK context compaction + caching that the scoring script and the official
starter notebook configure, so long local trajectories overflow 32k context where Kaggle's would not.
This runner builds the same EvalConfig as the starter notebook and lets each experiment config
(B0/B1/B2) swap the graph/embedding directories.

Run from app/ with the harness venv:
  LOCAL_INFERENCE_URL=http://127.0.0.1:8089/v1 ../.venv-harness/bin/python -m runner.run_eval \
      --submission submissions/b0 --results results/smoke_b0 --task requests_7505
"""
import argparse
import asyncio
import shlex
from pathlib import Path

import litellm
import yaml
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.cli import _build_cli_model_registry
from swegemma.config import EvalConfig, build_submission_limits
from swegemma.evaluate import Evaluator
from swegemma.warnings import _suppress_warnings

DATA = Path("data")
OPTIONAL_WHEELS = DATA / "wheels_optional"  # test-only extras, installed per repo by PIN_SCRIPT


def budgets(submission: Path) -> dict:
    """Read evaluation budgets from the submission's eval_config.yaml, as the starter notebook does."""
    path = submission / "eval_config.yaml"
    raw = (yaml.safe_load(path.read_text()) or {}) if path.is_file() else {}
    cfg = raw.get("evaluation", raw)
    turns = cfg.get("max_turns", cfg.get("max_llm_calls"))
    return dict(
        timeout_seconds=int(cfg.get("timeout_seconds", 300)),
        verification_timeout_seconds=int(cfg.get("verification_timeout_seconds", 300)),
        max_tool_calls=int(cfg.get("max_tool_calls", 100)),
        max_time_minutes=float(cfg.get("max_time_minutes", 60.0)),
        max_turns=int(turns) if turns is not None else None,
    )


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", required=True, type=Path)
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--tasks-path", default=str(DATA / "tasks.jsonl"),
                    help="data/tasks_b2.jsonl = problem statements with the C4 localizer hint (config B2)")
    ap.add_argument("--task", action="append", dest="tasks", help="instance_id (repeatable); default all")
    ap.add_argument("--graph-dir", default=str(DATA / "graphs"))
    ap.add_argument("--embeddings-dir", default=str(DATA / "embeddings"))
    ap.add_argument("--sandbox", default="docker", choices=["docker", "subprocess"])
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--copy-wheels", action="store_true",
                    help="copy wheels to /wheels and pip-install the repo's pinned dependency versions")
    ap.add_argument("--wheels-dir", default=str(DATA / "wheels"),
                    help="data/wheels_plus = official wheels + data/wheels_extra (see notes/gates.md)")
    return ap


def isolate_wheel_cache(wheels_dir: Path) -> None:
    """Key the harness's unpacked-wheel tar cache by wheel set.

    The harness caches `sp_base.tar` under tempfile.gettempdir() by name only, so switching wheel
    dirs silently reuses the old tar. Point tempdir at a per-wheel-set folder instead.
    """
    import hashlib
    import tempfile

    names = "\n".join(sorted(p.name for p in wheels_dir.glob("*.whl")))
    tmp = Path(tempfile.gettempdir()) / f"swegemma_wheels_{hashlib.sha256(names.encode()).hexdigest()[:12]}"
    tmp.mkdir(exist_ok=True)
    tempfile.tempdir = str(tmp)


def copy_wheels_into_sandbox() -> None:
    """Make /wheels available in Docker sandboxes.

    Under Docker the harness skips the /wheels copy and only unpacks one deduplicated version of
    each wheel into site-packages, so data/sandbox/setup.py's `pip install --find-links=/wheels`
    of the repo's pinned versions finds nothing (e.g. old fastapi tasks get Starlette 1.x).
    """
    from swegemma.harness import container_setup as cs
    from swegemma.harness import verification as vf

    def setup_container_wheels(docker, container_id, config):
        wheels_path = cs.resolve_wheels_dir(config)
        if wheels_path:
            docker.exec(container_id, "mkdir -p /wheels /wheels_opt")
            docker.copy_to(container_id, wheels_path, "/wheels")
        if OPTIONAL_WHEELS.is_dir():
            docker.copy_to(container_id, OPTIONAL_WHEELS, "/wheels_opt")

    cs.setup_container_wheels = vf.setup_container_wheels = setup_container_wheels

    original_install = cs.install_test_dependencies

    def install_test_dependencies(docker, container_id, repo="", **kwargs):
        original_install(docker, container_id, repo, **kwargs)
        docker.exec(container_id, f"python3 -c {shlex.quote(PIN_SCRIPT)}")

    cs.install_test_dependencies = vf.install_test_dependencies = install_test_dependencies


# Runs in the sandbox. (1) For each [project] dependency whose injected version violates the repo's
# spec, install the highest /wheels version that satisfies it. (2) Install the repo's own test
# extras (dependency-groups `tests`, optional `standard`/`all`, requirements-tests*.txt) when their
# wheel is in /wheels_opt, which the harness never auto-injects (e.g. inline_snapshot, whose pytest
# plugin would import the installed `rich` ahead of rich's own workspace).
# No deps, failures ignored. --ignore-installed because the harness unpacks wheels without RECORD
# files, so pip can't uninstall them.
PIN_SCRIPT = """
import re, subprocess, sys, tomllib, pathlib
from importlib.metadata import version, PackageNotFoundError
from pip._vendor.packaging.requirements import Requirement, InvalidRequirement
norm = lambda n: re.sub(r'[-_.]+', '-', n).lower()
links = sorted({str(w.parent) for w in pathlib.Path('/wheels').rglob('*.whl')})  # docker cp may nest the dir
opt = {norm(w.name.split('-')[0]): w.parent for w in pathlib.Path('/wheels_opt').rglob('*.whl')}
links += sorted({str(d) for d in opt.values()})
ws = pathlib.Path('/workspace')
cfg = tomllib.loads((ws / 'pyproject.toml').read_text()) if (ws / 'pyproject.toml').exists() else {}
groups = cfg.get('dependency-groups', {})
def group(name, seen=()):
    for item in groups.get(name, []):
        if isinstance(item, dict):
            if item.get('include-group') not in seen:
                yield from group(item['include-group'], seen + (name,))
        else:
            yield item
extras = list(group('tests'))
for key in ('standard', 'all'):
    extras += cfg.get('project', {}).get('optional-dependencies', {}).get(key, [])
for f in ws.glob('requirements-tests*.txt'):
    extras += [l.split('#')[0].strip() for l in f.read_text().splitlines() if l.strip() and not l.startswith(('-', '#'))]

def install(spec_list, only_opt):
    for d in spec_list:
        try:
            req = Requirement(d)
        except InvalidRequirement:
            continue
        if req.marker and not req.marker.evaluate():
            continue
        if only_opt and norm(req.name) not in opt:
            continue
        try:
            if version(req.name) in req.specifier:
                continue
        except PackageNotFoundError:
            pass
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-index',
                        *[f'--find-links={l}' for l in links], '--no-deps', '--no-build-isolation',
                        '--ignore-installed', f'{req.name}{req.specifier}'], check=False)

install(cfg.get('project', {}).get('dependencies', []), only_opt=False)
install(extras, only_opt=True)
from importlib.metadata import requires
for name in list(opt):  # requirements of installed extras that are themselves in /wheels_opt
    try:
        install(requires(name) or [], only_opt=True)
    except PackageNotFoundError:
        pass
"""


def inject_test_plugins() -> None:
    """Also unpack `pytest_httpbin` into the sandbox when it is in the wheels dir.

    The harness excludes test plugins from its auto-injected base wheels and leaves them to
    data/sandbox/setup.py, whose `pip --find-links=/wheels` has nothing to find under Docker
    (the /wheels copy is skipped). Without the plugin every `httpbin`-fixture test errors.
    """
    from swegemma.harness import container_setup as cs

    original = cs._inspect_wheels_dir

    def patched(wheels_dir):
        base, large, mod_to_pkg, requires = original(wheels_dir)
        extra = [w for w in Path(wheels_dir).glob("pytest_httpbin-*.whl") if w not in base]
        return base + extra, large, mod_to_pkg, requires

    cs._inspect_wheels_dir = patched


def build_config(args: argparse.Namespace, **overrides) -> EvalConfig:
    """EvalConfig with the starter notebook's compaction/caching settings."""
    _suppress_warnings()
    if Path(args.wheels_dir) != DATA / "wheels":
        inject_test_plugins()
    isolate_wheel_cache(Path(args.wheels_dir))
    if args.copy_wheels:
        copy_wheels_into_sandbox()
    litellm.drop_params = True
    limits, gen_constraints = build_submission_limits()
    config = EvalConfig(
        tasks_path=Path(args.tasks_path),
        snapshots_dir=DATA / "snapshots",
        results_dir=args.results,
        submission_dir=args.submission,
        models=_build_cli_model_registry(submission_dir=args.submission),
        sandbox=args.sandbox,
        task_ids=args.tasks,
        concurrency=args.concurrency,
        limits=limits,
        generation_constraints=gen_constraints,
        context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
        events_compaction_config=EventsCompactionConfig(
            compaction_interval=15, overlap_size=2, token_threshold=14336, event_retention_size=5,
        ),
        graph_dir=args.graph_dir,
        embeddings_dir=args.embeddings_dir,
        wheels_dir=Path(args.wheels_dir),
        display_mode="quiet",
        **{**budgets(args.submission), **overrides},
    )
    return config


def main() -> None:
    config = build_config(parser().parse_args())
    result = asyncio.run(Evaluator(config).run())
    print(f"Evaluation complete: {result.resolved}/{result.total} resolved ({result.resolution_rate:.2%})")


if __name__ == "__main__":
    main()
