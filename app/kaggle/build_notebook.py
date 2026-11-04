"""Build the Kaggle notebook v0 (C1 audit) from the repo's own mtm/ sources.

The notebook writes mtm/ast_index.py and mtm/audit.py verbatim, reruns the audit on the competition
data, and checks its Table 1 against the one computed locally (results/audit/table1.md).
The validity sweep needs Docker, which Kaggle notebooks lack, so its tables are embedded and labelled.

Run from app/: python3 kaggle/build_notebook.py   -> kaggle/notebook/mind-the-map-audit.ipynb
"""
import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP / "kaggle" / "notebook"
SLUG = "mind-the-map-c1-code-graph-audit"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")}


def code(text: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text.strip("\n")}


def writefile(rel: str) -> dict:
    return code(f"%%writefile {rel}\n" + (APP / rel).read_text())


def main() -> None:
    expected = (APP / "results" / "audit" / "table1.md").read_text()
    cells = [
        md("""
# Mind the Map · C1: auditing the released code graphs (v0)

This notebook reruns our audit of the competition's released code graphs against Python-AST ground truth
from the task snapshots. It uses the same `mtm/` source files as our repository.

- **Table 1** below is recomputed here from `/kaggle/input`, then checked against our local run.
- **The validity tables** at the end come from a local Docker sweep. They are copied in, not rerun,
  because notebooks have no Docker.
"""),
        code("""
import os, glob
from pathlib import Path
hits = glob.glob("/kaggle/input/**/tasks.jsonl", recursive=True)
assert hits, "attach the gemma-4-developer-agent competition data"
DATA = Path(hits[0]).parent
os.environ["MTM_DATA"] = str(DATA)
os.environ["MTM_OUT"] = "/kaggle/working/audit"
os.makedirs("mtm", exist_ok=True)
open("mtm/__init__.py", "w").close()
print(DATA, sorted(p.name for p in DATA.iterdir()))
"""),
        writefile("mtm/ast_index.py"),
        writefile("mtm/audit.py"),
        md("## Run the audit (~2 min)"),
        code("""
from mtm import audit
audit.main(str(DATA / "graphs"))
"""),
        md("## Table 1 matches the local run"),
        code(f"""
from IPython.display import Markdown, display
EXPECTED = {expected!r}
got = Path("/kaggle/working/audit/table1.md").read_text()
display(Markdown(got))
print("identical to local run:", got == EXPECTED)
assert got == EXPECTED
"""),
        md("""
## Gold-patch validity (local Docker sweep, copied in, not rerun here)

A task is *verifiable* when the reference (gold) patch resolves and an empty patch does not.

**Official public kit**

""" + (APP / "results" / "validity.md").read_text() + """

**Documented `wheels_plus` setup:** the official wheels, 12 extra wheels, and a step that installs each repo's
pinned dependency versions. Hashes and harness findings are in our repository.

""" + (APP / "results" / "validity_plus.md").read_text() + """

⚠️ Kaggle's scoring environment may differ from both local setups.
"""),
    ]
    nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 5}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mind-the-map-audit.ipynb").write_text(json.dumps(nb, indent=1))
    (OUT / "kernel-metadata.json").write_text(json.dumps({
        "id": f"saurinpatel16/{SLUG}",
        "title": "Mind the Map C1 Code Graph Audit",
        "code_file": "mind-the-map-audit.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": False,
        "enable_internet": False,
        "competition_sources": ["gemma-4-developer-agent"],
        "dataset_sources": [], "kernel_sources": [], "model_sources": [],
    }, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
