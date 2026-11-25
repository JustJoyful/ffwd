"""Build the four README figures from the result files under reports/.

Reproduce (matplotlib is NOT in the project environment and the lockfile is not changed; the --with run is ephemeral):

    uv run --frozen --with matplotlib==3.11.2 python docs/figures/make_figures.py

Inputs (all tracked in git):
  fig1  reports/2026-11-23-phase-1/results.json                      (k, n, Wilson 95% CI per system and split)
  fig2  reports/2026-11-23-phase-1-browser-row/report/results.json   (k, n, Wilson CIs; paired differences, guard)
  fig3  reports/2026-11-23-browser-gguf/*.parity.json                (browser dev counts, field this.k)
        reports/2026-11-23-mlc-parity/*.parity.json                  (cross-check of the MLC counts in data.json)
        docs/figures/data.json                                       (counts that exist only in markdown, source per value)
        Wilson intervals on fig3 are COMPUTED here with eval.stats.wilson_ci from the sourced counts.
  fig4  reports/2026-11-23-browser-gguf/M3-browser-q5km-{gpu,cpu}-bridge/turns.jsonl  (wall_ms per turn;
        first turn = n_messages == 2; median and IQR are COMPUTED here)

Nothing is hand-typed except the labels. Output: docs/figures/fig{1,2,3,4}-*.png (white background, dpi 150).
"""

import json
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from eval.stats import wilson_ci  # noqa: E402

OUT = Path(__file__).resolve().parent
R = ROOT / "reports"
# Okabe-Ito colour-blind-safe palette
C = {
    "B0": "#999999",
    "B2": "#000000",
    "M1": "#56B4E9",
    "M3": "#0072B2",
    "X1": "#E69F00",
    "browser": "#D55E00",
    "cpu": "#009E73",
}
plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#dddddd",
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
    }
)


def load(path: Path):
    return json.loads(path.read_text())


def save(fig, name: str) -> None:
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"{name}: {(OUT / name).stat().st_size / 1024:.0f} KB")


# ---------------------------------------------------------------- figure 1
def fig1() -> None:
    d = load(R / "2026-11-23-phase-1/results.json")["systems"]
    splits = ["test-iid", "test-compositional", "test-phrasing"]
    systems = ["B0", "B2", "M1", "M3", "X1"]
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    w = 0.16
    for i, s in enumerate(systems):
        for j, sp in enumerate(splits):
            r = d[s][sp]
            x = j + (i - 2) * w
            rate, lo, hi = r["rate"] * 100, r["ci95"][0] * 100, r["ci95"][1] * 100
            ax.bar(x, rate, w * 0.92, color=C[s], label=s if j == 0 else None)
            ax.errorbar(
                x,
                rate,
                yerr=[[max(0, rate - lo)], [max(0, hi - rate)]],
                color="#333333",
                lw=1,
                capsize=2,
            )
            ax.text(
                x, hi + 1.2, f"{r['k']}", ha="center", va="bottom", fontsize=6.5, color="#333333"
            )
    ax.set_xticks(range(3))
    ax.set_xticklabels([f"{sp}\n(n = {d['M3'][sp]['n']})" for sp in splits])
    ax.set_ylabel("task success (%)")
    ax.set_ylim(0, 112)
    ax.set_title("Phase 1 test run: success by split (native Q8_0, generated tasks)", fontsize=9.5)
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.2), frameon=False)
    fig.text(
        0.01,
        -0.02,
        "Bars: successes / n shown above each bar; whiskers: Wilson 95% interval (from results.json).",
        fontsize=7,
    )
    save(fig, "fig1-success-by-split.png")


# ---------------------------------------------------------------- figure 2
def fig2() -> None:
    d = load(R / "2026-11-23-phase-1-browser-row/report/results.json")
    splits = ["test-iid", "test-phrasing", "test-compositional"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.2, 3.5), gridspec_kw={"width_ratios": [1.15, 1]})
    w = 0.34
    for i, (s, col, lab) in enumerate(
        [
            ("M3", C["M3"], "M3 native Q8_0"),
            ("M3-browser", C["browser"], "M3 browser Q5_K_M (wllama, WebGPU)"),
        ]
    ):
        for j, sp in enumerate(splits):
            r = d["systems"][s][sp]
            x = j + (i - 0.5) * w
            rate, lo, hi = r["rate"] * 100, r["ci95"][0] * 100, r["ci95"][1] * 100
            a.errorbar(
                x,
                rate,
                yerr=[[max(0, rate - lo)], [max(0, hi - rate)]],
                fmt="o",
                color=col,
                ms=6,
                capsize=3,
                lw=1.4,
                label=lab if j == 0 else None,
            )
    a.set_ylim(85, 100)
    a.set_xticks(range(3))
    a.set_xticklabels(
        [f"{sp.replace('test-', '')}\n(n = {d['systems']['M3'][sp]['n']})" for sp in splits]
    )
    a.set_ylabel("task success (%), points, not bars")
    a.set_title("Success by split, Wilson 95%", fontsize=9.5)
    a.legend(loc="lower left", frameon=False, fontsize=7)

    rows = [
        (
            sp.replace("test-", ""),
            d["per_split"][sp]["diff"],
            d["per_split"][sp]["ci95"],
            d["per_split"][sp]["n"],
        )
        for sp in splits
    ]
    pr = d["primary"]
    rows.append(("pooled", pr["diff"], pr["ci95"], pr["n"]))
    ys = [3, 2, 1, -0.4]
    for y, (lab, diff, ci, n) in zip(ys, rows, strict=True):
        col = "#000000" if lab == "pooled" else "#555555"
        b.errorbar(
            diff * 100,
            y,
            xerr=[[(diff - ci[0]) * 100], [(ci[1] - diff) * 100]],
            fmt="o",
            color=col,
            capsize=3,
            lw=1.4,
        )
        b.text(8.2, y, f"n = {n}", va="center", fontsize=7, ha="right")
    # the guard exists only for the pooled comparison: draw its margin and one-sided bound on that row only
    g = pr["guard"]
    y = ys[-1]
    b.plot([g["margin"] * -100] * 2, [y - 0.35, y + 0.35], color="#D55E00", lw=2)
    b.plot(
        g["lower_bound_975"] * 100,
        y - 0.0,
        marker="d",
        color="#D55E00",
        ms=6,
        ls="none",
        mfc="white",
    )
    b.annotate(
        "margin -2.0 pp",
        (-2.0, y + 0.35),
        (-6.6, y + 1.05),
        fontsize=7,
        color="#D55E00",
        arrowprops={"arrowstyle": "-", "color": "#D55E00", "lw": 0.7},
    )
    b.annotate(
        f"one-sided 97.5% bound {g['lower_bound_975'] * 100:.2f} pp",
        (g["lower_bound_975"] * 100, y - 0.05),
        (-7.6, y - 1.0),
        fontsize=7,
        color="#D55E00",
        arrowprops={"arrowstyle": "-", "color": "#D55E00", "lw": 0.7},
    )
    b.axvline(0, color="#333333", lw=0.8)
    b.set_yticks(ys)
    b.set_yticklabels([r[0] for r in rows])
    b.set_xlim(-8.2, 8.4)
    b.set_ylim(-1.7, 3.7)
    b.set_xlabel("browser minus native Q8_0 (percentage points)")
    b.set_title("Paired difference, bootstrap 95% CI", fontsize=9.5)
    fig.tight_layout()
    save(fig, "fig2-browser-vs-native.png")


# ---------------------------------------------------------------- figure 3
def fig3() -> None:
    data = load(OUT / "data.json")["quant_curve_dev_n100"]
    nat = {q: v["k"] for q, v in data["native_gguf_llamacpp_b12032"].items()}
    br = {}
    for q, f in [("Q4_K_M", "q4km-gpu"), ("Q5_K_M", "q5km-gpu"), ("Q6_K", "q6k-gpu")]:
        br[q] = load(R / f"2026-11-23-browser-gguf/M3-browser-{f}.parity.json")["this"]["k"]
    br_kv = load(R / "2026-11-23-browser-gguf/M3-browser-q5km-gpu-kvq80.parity.json")["this"]["k"]
    mlc = {
        q: load(R / f"2026-11-23-mlc-parity/{f}.parity.json")["this"]["k"]
        for q, f in [("q4f16_1", "M3-mlc-q4f16_1"), ("q0f16", "M3-mlc-q0f16-control")]
    }
    # the MLC counts in data.json must agree with the result files
    assert mlc["q4f16_1"] == data["mlc_stored_weights_read_back_through_hf_fp16_M3"]["q4f16_1"]["k"]
    assert mlc["q0f16"] == data["mlc_stored_weights_read_back_through_hf_fp16_M3"]["q0f16"]["k"]
    n = data["n"]

    def pt(ax, x, k, **kw):
        _, lo, hi = wilson_ci(k, n)
        ax.errorbar(x, k, yerr=[[k - lo * n], [hi * n - k]], capsize=2.5, lw=1, **kw)

    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    cats = ["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0", "MLC\nq4f16_1", "MLC\nq0f16 (fp16)"]
    xs = {c: i for i, c in enumerate(cats)}
    for q in ["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"]:
        pt(
            ax,
            xs[q] - 0.12,
            nat[q],
            fmt="o",
            color=C["M3"],
            ms=6,
            label="native GGUF (llama.cpp b12032)" if q == "Q4_K_M" else None,
        )
    for q in ["Q4_K_M", "Q5_K_M", "Q6_K"]:
        pt(
            ax,
            xs[q] + 0.12,
            br[q],
            fmt="s",
            color=C["browser"],
            ms=6,
            label="browser GGUF, WebGPU (wllama, f16 KV)" if q == "Q4_K_M" else None,
        )
    pt(
        ax,
        xs["Q5_K_M"] + 0.28,
        br_kv,
        fmt="s",
        color=C["browser"],
        mfc="white",
        ms=6,
        label="browser, q8_0 KV (the shipped setting)",
    )
    pt(
        ax,
        xs["MLC\nq4f16_1"],
        mlc["q4f16_1"],
        fmt="^",
        color=C["cpu"],
        ms=6,
        label="MLC weights read back through HF fp16 (not a browser run)",
    )
    pt(ax, xs["MLC\nq0f16 (fp16)"], mlc["q0f16"], fmt="^", color=C["cpu"], ms=6)
    for c in ["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"]:
        ax.text(
            xs[c] - 0.2, nat[c], str(nat[c]), ha="right", va="center", fontsize=7.5, color=C["M3"]
        )
    for c in ["Q4_K_M", "Q5_K_M", "Q6_K"]:
        ax.text(
            xs[c] + 0.12,
            br[c] - 13,
            str(br[c]),
            ha="center",
            va="center",
            fontsize=7.5,
            color=C["browser"],
        )
    ax.text(
        xs["Q5_K_M"] + 0.28,
        br_kv - 13,
        str(br_kv),
        ha="center",
        va="center",
        fontsize=7.5,
        color=C["browser"],
    )
    ax.text(
        xs["MLC\nq4f16_1"] + 0.12,
        mlc["q4f16_1"],
        str(mlc["q4f16_1"]),
        ha="left",
        va="center",
        fontsize=7.5,
        color=C["cpu"],
    )
    ax.text(
        xs["MLC\nq0f16 (fp16)"] - 0.12,
        mlc["q0f16"],
        str(mlc["q0f16"]),
        ha="right",
        va="center",
        fontsize=7.5,
        color=C["cpu"],
    )
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels(cats)
    ax.set_ylabel(f"dev tasks passed, of {n}")
    ax.set_ylim(-3, 112)
    ax.set_title("M3 quantisation curve on one seeded 100-task dev sample", fontsize=9.5)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.52), ncol=2, frameon=False, fontsize=7)
    fig.text(
        0.01,
        -0.12,
        "Whiskers: Wilson 95% interval computed by make_figures.py from the counts (eval.stats.wilson_ci).",
        fontsize=7,
    )
    save(fig, "fig3-quantisation-curve.png")


# ---------------------------------------------------------------- figure 4
def quartiles(v):
    q = statistics.quantiles(v, n=4, method="inclusive")
    return q[0], statistics.median(v), q[2]


def fig4() -> None:
    paths = {
        "WebGPU (RTX 3050)": "M3-browser-q5km-gpu-bridge",
        "processor only (6 threads)": "M3-browser-q5km-cpu-bridge",
    }
    fig, ax = plt.subplots(figsize=(7.0, 3.5))
    w = 0.34
    notes = []
    for i, (lab, d) in enumerate(paths.items()):
        rows = [
            json.loads(line)
            for line in (R / "2026-11-23-browser-gguf" / d / "turns.jsonl").read_text().splitlines()
            if line.strip()
        ]
        first = [r["wall_ms"] / 1000 for r in rows if r["n_messages"] == 2]
        later = [r["wall_ms"] / 1000 for r in rows if r["n_messages"] > 2]
        for j, (v, name) in enumerate([(first, "first turn"), (later, "later turns")]):
            q1, med, q3 = quartiles(v)
            x = i + (j - 0.5) * w
            col = C["browser"] if i == 0 else C["cpu"]
            ax.bar(x, med, w * 0.92, color=col, alpha=1.0 if j == 0 else 0.55)
            ax.errorbar(x, med, yerr=[[med - q1], [q3 - med]], color="#333333", lw=1, capsize=3)
            ax.text(x, q3 + 0.35, f"{med:.2f} s", ha="center", fontsize=7.5)
            ax.text(x, -1.3, f"{name}\nn = {len(v)}", ha="center", va="top", fontsize=7)
        notes.append(f"{lab}: {len(first)} first + {len(later)} later turns")
    ax.set_xticks([0, 1])
    ax.set_xticklabels(list(paths), fontsize=8.5)
    ax.tick_params(axis="x", pad=34, length=0)
    ax.set_ylabel("wall time per model turn (s)")
    ax.set_ylim(0, 16)
    ax.set_title("Time per model turn, M3 Q5_K_M in the browser, dev spike", fontsize=9.5)
    fig.text(
        0.01,
        -0.1,
        "Bars: median; whiskers: interquartile range (computed here from turns.jsonl). One laptop, one seed, 100 dev tasks per path.",
        fontsize=7,
    )
    save(fig, "fig4-latency-per-turn.png")
    print("; ".join(notes))


if __name__ == "__main__":
    for f in (fig1, fig2, fig3, fig4):
        f()
