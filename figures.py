"""Paper figures from results/replay.json -> paper/figs/*.pdf + *.png (dataviz reference palette)."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

ROOT = Path(__file__).parent
R = json.load(open(ROOT / "results/replay.json"))
G, NAMES = R["E1b"], R["names"]
OUT = ROOT / "paper/figs"
OUT.mkdir(parents=True, exist_ok=True)

INK, INK2, MUTED, GRID, BASE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA, RED, MID = "#2a78d6", "#eb6834", "#1baf7a", "#e34948", "#f0efec"
M, N = (1, 2, 3, 5, 10), (25, 50, 100, 200, 525)
plt.rcParams.update({"font.size": 9, "axes.edgecolor": BASE, "axes.labelcolor": INK2,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "font.family": "serif"})


def save(fig, name):
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=220, bbox_inches="tight")
    plt.close(fig)


def fig_heatmap(p="P1", s="S2r"):
    z = np.array([[G[f"{p}|{m}|{n}"][s]["ratio"] for n in N] for m in M])
    cmap = LinearSegmentedColormap.from_list("div", [BLUE, MID, RED])
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    im = ax.imshow(np.log2(z), cmap=cmap, norm=TwoSlopeNorm(0, -3.5, 1.0), aspect="auto")
    for i in range(len(M)):
        for j in range(len(N)):
            ax.text(j, i, f"{z[i, j]:.2f}×", ha="center", va="center", fontsize=8,
                    color=INK, fontweight="bold" if z[i, j] > 1 else "normal")
    ax.set_xticks(range(len(N)), [str(n) for n in N])
    ax.set_yticks(range(len(M)), [str(m) for m in M])
    ax.set_xlabel("catalog size N (tools)")
    ax.set_ylabel("tasks per session m")
    ax.spines[:].set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.03)
    cb.set_ticks(np.log2([0.125, 0.25, 0.5, 1, 2]), labels=["0.125", "0.25", "0.5", "1", "2"])
    cb.set_label("cost relative to static-cached", color=INK2)
    cb.outline.set_visible(False)
    save(fig, f"fig1_heatmap_{s}_{p}")


def fig_bars(p="P1", n=100):
    strats = ["S1u", "S2", "S2r", "S2u", "S3", "S4", "S5"]
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    x, w = np.arange(len(strats)), 0.38
    for k, (m, col) in enumerate(((1, BLUE), (10, ORANGE))):
        v = [G[f"{p}|{m}|{n}"][s]["ratio"] for s in strats]
        lo = [G[f"{p}|{m}|{n}"][s]["lo"] for s in strats]
        hi = [G[f"{p}|{m}|{n}"][s]["hi"] for s in strats]
        err = [np.subtract(v, lo), np.subtract(hi, v)]
        ax.bar(x + (k - 0.5) * (w + 0.02), v, w, color=col, yerr=err, ecolor=INK2, capsize=2,
               error_kw={"lw": 0.8}, label=f"{m} task{'s' if m > 1 else ''} per session", zorder=3)
    ax.axhline(1, color=INK2, lw=1, ls="--", zorder=2)
    ax.text(-0.6, 1.04, "static-cached = 1", color=INK2, ha="left", va="bottom", fontsize=8)
    ax.set_xticks(x, strats)
    ax.set_ylabel("cost relative to static-cached")
    ax.set_yscale("log")
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_yticks([0.25, 0.5, 1, 2, 4], ["0.25", "0.5", "1", "2", "4"])
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
    ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(1, 1.18), ncol=2)
    save(fig, f"fig2_strategies_{p}_N{n}")


def fig_inversion(p="P1", n=100):
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.8), sharey=False)
    for ax, m, col in zip(axes, (1, 10), (BLUE, ORANGE)):
        c = G[f"{p}|{m}|{n}"]
        for s in ("S1", "S2", "S2r", "S2u", "S3", "S4", "S5"):
            ax.scatter(c[s]["raw"] / 1e3, c[s]["cost"] / 1e3, s=36, color=col,
                       edgecolor="#fcfcfb", linewidth=2, zorder=3)
            off = {(1, "S2"): (-4, -12), (1, "S2u"): (-18, 6), (1, "S2r"): (6, -4)}.get((m, s), (5, 3))
            ax.annotate(s, (c[s]["raw"] / 1e3, c[s]["cost"] / 1e3), xytext=off,
                        textcoords="offset points", fontsize=7.5, color=INK)
        ax.set_title(f"{m} task{'s' if m > 1 else ''} per session, N={n}", fontsize=9, color=INK)
        ax.set_xlabel("raw input tokens per session (k)")
        ax.grid(color=GRID, lw=0.6, zorder=0)
    axes[0].set_ylabel("normalized cost per session (k)")
    save(fig, f"fig3_inversion_{p}_N{n}")


def fig_serialization(p="P1"):
    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    for n, col, mk, dy in ((25, BLUE, "o", -7), (100, ORANGE, "s", 5), (525, AQUA, "^", 0)):
        y = [G[f"{p}|{m}|{n}"]["S1u"]["ratio"] for m in M]
        ax.plot(M, y, color=col, lw=2, marker=mk, ms=6, mec="#fcfcfb", mew=1.5, label=f"N={n}")
        ax.annotate(f"N={n}", (M[-1], y[-1]), xytext=(7, dy), textcoords="offset points",
                    va="center", fontsize=8, color=INK)
    ax.axhline(1, color=INK2, lw=1, ls="--")
    ax.set_xticks(M)
    ax.set_xlim(0.5, 12.5)
    ax.set_xlabel("tasks per session m")
    ax.set_ylabel("unstable / stable serialization cost")
    ax.grid(color=GRID, lw=0.6)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    save(fig, f"fig4_serialization_{p}")


if __name__ == "__main__":
    fig_heatmap()
    fig_bars()
    fig_inversion()
    fig_serialization()
    print(sorted(p.name for p in OUT.iterdir()))
