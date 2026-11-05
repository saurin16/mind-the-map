"""Kaggle Writeup body from paper/writeup.md (the paper stays the single source).

v1 is posted before the pre-registered cutoff, so the PENDING PHASE 4 slots become an explicit
"not reported yet" status, never interim numbers. Title and subtitle go in Kaggle's own fields,
HTML comments are dropped, and figures point at the public GitHub copy.
Run from app/: ../.venv/bin/python -m mtm.build_writeup  -> ../paper/kaggle_writeup_v1.md
"""
import re
from pathlib import Path

SRC, OUT = Path("../paper/writeup.md"), Path("../paper/kaggle_writeup_v1.md")
FIG_URL = "https://raw.githubusercontent.com/saurin16/mind-the-map/main/paper/figures/"
V1 = {
    "[PENDING PHASE 4: one sentence of results.]":
        "Its results are added to this Writeup after the registered cutoff (Nov 10, 2026).",
    re.compile(r"\*\*Results\.\*\* \[PENDING PHASE 4:[^\]]*\]"):
        "**Results.** Not reported in this version. The runs are in progress, and the registration "
        "allows no analysis before the cutoff. This section will be updated with solve rate per "
        "configuration (95% CIs), the B2−B0 and B2−B1 effects with Holm-adjusted p, tool calls, turns "
        "until the first gold-file read and the failure taxonomy, with N as observed.",
    "[PENDING PHASE 4: 1–2 sentences.] ": "",
}


def build(text: str) -> str:
    text = re.sub(r"\s*<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"\A# .*\n+\*.*\*\n+", "", text)  # title + subtitle live in Kaggle's fields
    text = text.replace("](figures/", f"]({FIG_URL}")
    for old, new in V1.items():
        text, n = (old.subn(new, text) if isinstance(old, re.Pattern) else (text.replace(old, new), text.count(old)))
        assert n == 1, f"v1 slot not found exactly once: {old}"
    assert "PENDING" not in text and "GAP" not in text
    return text


if __name__ == "__main__":
    body = build(SRC.read_text())
    OUT.write_text(body)
    print(f"wrote {OUT}: {len(body.split())} words")
