"""Kaggle Writeup body from paper/writeup.md (the paper stays the single source).

v1 (Nov 5) was posted before the Phase 4 analysis and turned the PENDING slots into a "not reported yet"
status (git history). v2 carries the registered results, so the paper must have no PENDING slot left.
Title and subtitle go in Kaggle's own fields, HTML comments are dropped, figures point at the public GitHub copy.
Run from app/: ../.venv/bin/python -m mtm.build_writeup  -> ../paper/kaggle_writeup_v2.md
"""
import re
from pathlib import Path

SRC, OUT = Path("../paper/writeup.md"), Path("../paper/kaggle_writeup_v2.md")
FIG_URL = "https://raw.githubusercontent.com/saurin16/mind-the-map/main/paper/figures/"


def build(text: str) -> str:
    text = re.sub(r"\s*<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"\A# .*\n+\*.*\*\n+", "", text)  # title + subtitle live in Kaggle's fields
    text = text.replace("](figures/", f"]({FIG_URL}")
    assert "PENDING" not in text and "GAP" not in text
    return text


if __name__ == "__main__":
    body = build(SRC.read_text())
    OUT.write_text(body)
    print(f"wrote {OUT}: {len(body.split())} words")
