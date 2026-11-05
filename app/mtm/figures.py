"""Paper figures from committed result files (no hand-typed numbers).

Fig 2: gold edit sites present / reachable, released vs repaired (results/repair/table_g2.md, all row),
       and edges by type (released graph has `calls` only; repaired totals from the same row).
Fig 1: pipeline diagram, labels only.
Cover: Kaggle card/thumbnail (560x280), headline two-hop number from the same row as Fig 2.
Run from app/: ../.venv/bin/python -m mtm.figures   -> ../paper/figures/fig{1,2}.png
"""
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path("../paper/figures")
RELEASED, REPAIRED = "#eb6834", "#2a78d6"  # categorical slots 2, 1 (validated light)
INK, MUTED, GRID, SURFACE = "#1f1f1e", "#6b6a64", "#e4e3de", "#fcfcfb"
FRAC = re.compile(r"(\d+)/(\d+)")


def g2_all_row() -> dict[str, str]:
    lines = [l for l in Path("results/repair/table_g2.md").read_text().splitlines() if l.startswith("|")]
    head = [c.strip() for c in lines[0].strip("|").split("|")]
    row = next(l for l in lines if l.startswith("| all "))
    return dict(zip(head, [c.strip() for c in row.strip("|").split("|")]))


def fracs(cell: str) -> list[tuple[int, int]]:
    return [(int(a), int(b)) for a, b in FRAC.findall(cell)]


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)
    ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", labelcolor=INK)


def coverage_fig() -> None:
    r = g2_all_row()
    rows = [("definition sites in graph", fracs(r["gold def sites: released → repaired"])),
            ("module-level sites in graph", fracs(r["module-level gold sites"])),
            ("async sites in graph", fracs(r["async gold sites: released → repaired"])),
            ("tasks with gold ≤2 hops from issue", fracs(r["gold ≤2 hops: released → repaired → repaired w/o `contains`"])[:2])]
    types = ["contains", "calls", "imports", "inherits", "overrides", "tests"]
    repaired_edges = {t: int(r[t]) for t in types}
    released_edges = {t: 0 for t in types}
    released_edges["calls"] = int(re.search(r"calls:(\d+)", Path("results/audit/table1.md").read_text()).group(1))

    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw=dict(width_ratios=[1.15, 1]), facecolor=SURFACE)
    h = 0.36
    for i, (label, ((n0, d0), (n1, d1))) in enumerate(rows):
        y = len(rows) - 1 - i
        for off, (n, d), c in ((h / 2 + 0.02, (n0, d0), RELEASED), (-h / 2 - 0.02, (n1, d1), REPAIRED)):
            v = 100 * n / d
            a.barh(y + off, max(v, 0.6), h, color=c, edgecolor=SURFACE, lw=0)
            a.text(v + 1.5, y + off, f"{n}/{d}", va="center", fontsize=8, color=INK)
    a.set_yticks(range(len(rows)), [l for l, _ in reversed(rows)], fontsize=9)
    a.set_xlim(0, 118)
    a.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    a.set_title("A  Gold edit sites (129 tasks)", loc="left", fontsize=10, color=INK)
    style(a)

    y = range(len(types))
    a2 = b
    a2.barh([i - 0.2 for i in y], [released_edges[t] / 1e3 for t in types], 0.38, color=RELEASED, lw=0)  # y inverted
    a2.barh([i + 0.2 for i in y], [repaired_edges[t] / 1e3 for t in types], 0.38, color=REPAIRED, lw=0)
    a2.set_yticks(list(y), types, fontsize=9)
    a2.invert_yaxis()
    a2.set_xlabel("edges, thousands (127 graphs)", fontsize=8, color=MUTED)
    a2.set_title("B  Edges by type", loc="left", fontsize=10, color=INK)
    style(a2)
    handles = [plt.Rectangle((0, 0), 1, 1, color=RELEASED), plt.Rectangle((0, 0), 1, 1, color=REPAIRED)]
    fig.legend(handles, ["released graph", "repaired graph (C2)"], loc="upper right", ncol=2, frameon=False,
               fontsize=9, labelcolor=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(OUT / "fig2.png", dpi=200, facecolor=SURFACE)


def cover_fig() -> None:
    """Kaggle card + thumbnail (min 560x280, saved at 2x): the headline two-hop number, from the same row as Fig 2."""
    (n0, d0), (n1, d1) = fracs(g2_all_row()["gold ≤2 hops: released → repaired → repaired w/o `contains`"])[:2]
    fig = plt.figure(figsize=(5.6, 2.8), dpi=100, facecolor=SURFACE)
    fig.text(0.06, 0.80, "Mind the Map", fontsize=20, weight="bold", color=INK)
    fig.text(0.06, 0.68, "Gemma 4 code graphs: audit + typed repair", fontsize=10, color=MUTED)
    fig.text(0.06, 0.50, "tasks with an edit site ≤2 hops from the issue", fontsize=9, color=MUTED)
    a = fig.add_axes((0.06, 0.12, 0.88, 0.32), facecolor=SURFACE)
    for y, (n, d), c, lab in ((1, (n0, d0), RELEASED, "released"), (0, (n1, d1), REPAIRED, "repaired")):
        v = 100 * n / d
        a.barh(y, v, 0.62, color=c, lw=0)
        a.text(v + 1.5, y, f"{v:.1f}%  {lab}", va="center", fontsize=10, color=INK, weight="bold")
    a.set_xlim(0, 100)
    a.axis("off")
    fig.savefig(OUT / "cover.png", dpi=200, facecolor=SURFACE)  # 1120x560: 2x the 560x280 minimum


def dataset_cover_fig() -> None:
    """Kaggle dataset cover, 560x280. The CLI crops the thumbnail from x=140..420, so the title sits in that square."""
    fig = plt.figure(figsize=(5.6, 2.8), dpi=100, facecolor=SURFACE)
    fig.text(0.5, 0.62, "Mind the Map", ha="center", fontsize=22, weight="bold", color=INK)
    fig.text(0.5, 0.47, "Gemma 4 typed code graphs", ha="center", fontsize=10, color=MUTED)
    types = ["contains", "calls", "imports", "inherits", "overrides", "tests"]
    for i, t in enumerate(types):
        fig.text(0.09 + i * 0.165, 0.2, t, ha="center", fontsize=8.5, color=REPAIRED if t != "calls" else RELEASED,
                 bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=GRID))
    fig.savefig(OUT / "dataset_cover.png", dpi=100, facecolor=SURFACE)


def pipeline_fig() -> None:
    fig, ax = plt.subplots(figsize=(11, 2.7), facecolor=SURFACE)
    ax.set_xlim(0, 11)
    ax.set_ylim(0.75, 3.25)
    ax.axis("off")

    def box(x, y, w, txt, sub, accent=False):
        ax.add_patch(FancyBboxPatch((x, y), w, 0.8, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc="#eaf2fc" if accent else "white", ec=REPAIRED if accent else MUTED, lw=1.2))
        ax.text(x + w / 2, y + 0.52, txt, ha="center", va="center", fontsize=10, color=INK, weight="bold")
        ax.text(x + w / 2, y + 0.24, sub, ha="center", va="center", fontsize=8, color=MUTED)

    def arrow(x0, y0, x1, y1):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=12, color=MUTED, lw=1.1))

    box(0.1, 2.3, 2.0, "Repo snapshot", "base commit")
    box(0.1, 0.9, 2.0, "Released graph", "calls only")
    box(2.9, 2.3, 2.1, "C2 Repairer", "AST · typed superset", True)
    box(2.9, 0.9, 2.1, "C1 Auditor", "coverage · reachability", True)
    box(5.8, 2.3, 2.1, "C4 Localizer", "BM25 seeds · PPR → hint", True)
    box(5.8, 0.9, 2.1, "Issue text", "problem statement")
    box(8.7, 2.3, 2.2, "E4B agent", "graph tools · B0 / B1 / B2", True)
    box(8.7, 0.9, 2.2, "C5 Evaluation", "k=3 · paired · prereg", True)
    arrow(2.1, 2.7, 2.9, 2.7)
    arrow(2.1, 1.3, 2.9, 1.3)
    arrow(2.1, 2.5, 2.9, 1.5)
    arrow(5.0, 2.7, 5.8, 2.7)
    arrow(6.85, 1.7, 6.85, 2.3)
    arrow(7.9, 2.7, 8.7, 2.7)
    arrow(9.8, 2.3, 9.8, 1.7)
    fig.tight_layout()
    fig.savefig(OUT / "fig1.png", dpi=200, facecolor=SURFACE)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    pipeline_fig()
    coverage_fig()
    cover_fig()
    dataset_cover_fig()
    print("wrote", *sorted(p.name for p in OUT.glob("fig*.png")))
