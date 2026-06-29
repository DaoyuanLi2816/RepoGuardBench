"""Generate paper figures from the scored aggregate CSVs.

R3 redesign: shorter labels, no overlapping captions, n in axis
labels, two-panel safety-utility plot, legends placed below plots.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


plt.rcParams.update({
    "font.size": 8.5,
    "axes.titlesize": 9.5,
    "axes.labelsize": 8.5,
    "legend.fontsize": 7.5,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "figure.dpi": 150,
})

CARRIER_SHORT = {
    "readme": "README", "issue": "Issue", "code_comment": "Comment",
    "test_log": "Test log", "rule_file": "Rule file",
}
DEFENSE_SHORT = {
    "D0_none": "D0",
    "D1_spotlight": "D1",
    "D2_strip": "D2",
    "D3_action_gate": "D3",
    "D4_task_align": "D4",
    "D5_human_confirm": "D5",
    "D3np_action_gate_silent": "D3np",
    "D5np_confirm_silent": "D5np",
}
MODEL_SHORT = {
    "qwen2.5-coder:1.5b": "1.5B",
    "qwen2.5-coder:3b": "3B",
    "qwen2.5-coder:7b": "7B",
    "qwen2.5-coder:14b": "14B",
    "llama3.1:8b": "Llama 8B",
    "starcoder2:3b": "SC2 3B",
    "deepseek-coder:6.7b-instruct": "DS 6.7B",
}
# Primary Qwen2.5-Coder family in size order (for the scaling figure).
QWEN_FAMILY = ["qwen2.5-coder:1.5b", "qwen2.5-coder:3b",
               "qwen2.5-coder:7b", "qwen2.5-coder:14b"]


def _safe_clip(arr):
    return np.clip(np.asarray(arr, dtype=float), 0, None)


# -------- fig 1: pipeline --------

def fig1_pipeline(outpath: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 2.8))
    ax.set_axis_off()
    cols = [
        ("Inputs", [
            "README / docs", "Issue body",
            "Code comments", "Build / test log",
            "Rule / config file",
        ], 0.02, "#fdf2e9", "Attacker writes"),
        ("Defenses", [
            "D1 spotlight",
            "D2 strip",
            "D3 action gate",
            "D4 task align",
            "D5 human confirm",
        ], 0.28, "#eafaf1", "Local-only filters"),
        ("Agent", [
            "Qwen2.5-Coder",
            "JSON ReAct loop",
            "4-turn budget",
            "Local sandbox",
            "No network",
        ], 0.54, "#eaf2f8", "Single GPU"),
        ("Scorer", [
            "target test",
            "proposed attempt",
            "blocked / landed",
            "completed",
            "audit log",
        ], 0.80, "#f4ecf7", "Seven metrics"),
    ]
    bx_w, bx_y, bx_h = 0.18, 0.30, 0.58
    for title, items, x0, color, sub in cols:
        ax.add_patch(plt.Rectangle((x0, bx_y), bx_w, bx_h,
                                     facecolor=color, edgecolor="black", lw=0.8))
        ax.text(x0 + bx_w / 2, bx_y + bx_h - 0.04, title,
                ha="center", va="top", fontsize=9.5, fontweight="bold")
        for i, item in enumerate(items):
            ax.text(x0 + bx_w / 2, bx_y + bx_h - 0.13 - i * 0.075,
                    "- " + item, ha="center", va="top", fontsize=7.4)
        ax.text(x0 + bx_w / 2, bx_y - 0.035, sub, ha="center", va="top",
                fontsize=7.0, style="italic")
    for x_from, x_to in ((0.20, 0.28), (0.46, 0.54), (0.72, 0.80)):
        ax.annotate("", xy=(x_to, bx_y + bx_h / 2),
                     xytext=(x_from, bx_y + bx_h / 2),
                     arrowprops=dict(arrowstyle="->", lw=0.9))
    goals = ["canary read", "canary exfil", "test delete",
             "unauth shell", "backdoor"]
    for i, g in enumerate(goals):
        x = 0.04 + i * 0.19
        ax.add_patch(plt.Rectangle((x, 0.02), 0.16, 0.06,
                                     facecolor="#fef9e7",
                                     edgecolor="#7d6608", lw=0.6))
        ax.text(x + 0.08, 0.05, g, ha="center", va="center", fontsize=7.0)
    ax.text(0.5, 0.13, "Safe synthetic attack goals (inert, workspace-only)",
            ha="center", va="bottom", fontsize=7.4, fontweight="bold")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


# -------- fig 2: safety-utility (vertical stacked panels) --------

def fig2_safety_utility(matched_md: pd.DataFrame, outpath: Path) -> None:
    primary = "qwen2.5-coder:3b"
    df = matched_md[matched_md["model"] == primary].copy()
    if df.empty:
        return
    df = df.sort_values("defense").reset_index(drop=True)
    labels = [DEFENSE_SHORT.get(d, d) for d in df["defense"]]
    y = np.arange(len(df))

    fig, (axT, axB) = plt.subplots(2, 1, figsize=(3.4, 3.6),
                                     gridspec_kw={"hspace": 0.55})
    # Top: attempt rate
    xs = df["attempt_mean"].to_numpy(dtype=float)
    los = _safe_clip(xs - df.get("attempt_lo", xs).to_numpy(dtype=float))
    his = _safe_clip(df.get("attempt_hi", xs).to_numpy(dtype=float) - xs)
    axT.errorbar(xs, y, xerr=[los, his], fmt="o", capsize=2,
                  markersize=5, color="#34495e", ecolor="#95a5a6")
    axT.set_yticks(y); axT.set_yticklabels(labels)
    axT.invert_yaxis()
    axT.set_xlabel("Matched attempt rate (lower is safer)")
    axT.grid(axis="x", alpha=0.25)
    axT.set_xlim(left=-0.005)
    axT.set_title("Attempt rate")

    # Bottom: utility delta
    ys = df["util_delta_mean"].to_numpy(dtype=float)
    los = _safe_clip(ys - df.get("util_delta_lo", ys).to_numpy(dtype=float))
    his = _safe_clip(df.get("util_delta_hi", ys).to_numpy(dtype=float) - ys)
    axB.errorbar(ys, y, xerr=[los, his], fmt="o", capsize=2,
                  markersize=5, color="#34495e", ecolor="#95a5a6")
    axB.axvline(0.0, color="grey", lw=0.6, linestyle="--")
    axB.set_yticks(y); axB.set_yticklabels(labels)
    axB.invert_yaxis()
    axB.set_xlabel(r"Matched utility delta ($\geq 0$ better)")
    axB.grid(axis="x", alpha=0.25)
    axB.set_title("Utility delta")
    fig.suptitle(f"Defenses on {MODEL_SHORT.get(primary, primary)} "
                 "(95% bootstrap CI)", y=1.0, fontsize=9.5)
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


# -------- fig 3: carrier risk --------

def fig3_carriers(byc: pd.DataFrame, outpath: Path) -> None:
    df = byc.copy()
    if "attack_carrier" not in df.columns:
        return
    df = df[df["attack_carrier"] != "none"].sort_values("proposed_attempt").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    y = np.arange(len(df))
    xs = df["proposed_attempt"].to_numpy(dtype=float)
    los = _safe_clip(xs - df.get("proposed_attempt_lo", xs).to_numpy(dtype=float))
    his = _safe_clip(df.get("proposed_attempt_hi", xs).to_numpy(dtype=float) - xs)
    ax.errorbar(xs, y, xerr=[los, his], fmt="o", capsize=2,
                color="#2c3e50", ecolor="#7f8c8d", markersize=5)
    ns = df.get("n", [0] * len(df)).astype(int)
    ylabels = [f"{CARRIER_SHORT.get(c,c)} (n={n})" for c, n in zip(df["attack_carrier"], ns)]
    ax.set_yticks(y); ax.set_yticklabels(ylabels)
    ax.set_xlabel("Proposed attempt rate (95% Wilson CI)")
    ax.set_xlim(left=-0.005)
    ax.grid(axis="x", alpha=0.25)
    ax.set_title("Attempt rate by carrier")
    fig.tight_layout()
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


# -------- fig 4: model scaling --------

def fig4_model_scaling(matched_m: pd.DataFrame, outpath: Path) -> None:
    df = matched_m.copy()
    if df.empty:
        return
    # Keep only Qwen2.5-Coder family for main plot, ordered by size.
    df = df[df["model"].isin(QWEN_FAMILY)].copy()
    df["_o"] = df["model"].map({m: i for i, m in enumerate(QWEN_FAMILY)})
    df = df.sort_values("_o").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    xs = np.arange(len(df))
    ys = df["attempt_mean"].to_numpy(dtype=float)
    los = _safe_clip(ys - df.get("attempt_lo", ys).to_numpy(dtype=float))
    his = _safe_clip(df.get("attempt_hi", ys).to_numpy(dtype=float) - ys)
    ax.errorbar(xs, ys, yerr=[los, his], fmt="o-", capsize=3,
                markersize=6, color="#34495e", ecolor="#34495e")
    ns = df.get("n_matched", [0] * len(df)).astype(int).tolist()
    short_labels = [f"{MODEL_SHORT.get(m, m)}\n(n={n})"
                     for m, n in zip(df["model"], ns)]
    ax.set_xticks(xs); ax.set_xticklabels(short_labels)
    ax.set_ylabel("Attempt rate")
    ax.set_xlabel("Qwen2.5-Coder size")
    ax.grid(axis="y", alpha=0.25)
    ymax = max(0.2, float(np.nanmax(ys) if len(ys) else 0.2))
    ax.set_ylim(-0.01, ymax + max(his) + 0.02 if len(his) else ymax + 0.05)
    ax.set_title("Attempt rate vs model size")
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


# -------- fig 5: top defense x carrier risk cells (compact bar) --------

def fig5_top_cells(bycd: pd.DataFrame, outpath: Path, k: int = 10) -> None:
    if bycd.empty or "defense" not in bycd.columns or "attack_carrier" not in bycd.columns:
        return
    df = bycd[bycd["attack_carrier"] != "none"].copy()
    df = df[(df["n"] >= 18) & (df["proposed_attempt"] > 0)].copy()
    df = df.sort_values("proposed_attempt", ascending=False).head(k)
    if df.empty:
        return
    df = df[::-1].reset_index(drop=True)  # so largest is at top of bar chart
    labels = [f"{DEFENSE_SHORT.get(r['defense'], r['defense'])}"
              f" × {CARRIER_SHORT.get(r['attack_carrier'], r['attack_carrier'])}"
              f" (n={int(r['n'])})" for _, r in df.iterrows()]
    fig, ax = plt.subplots(figsize=(3.4, 0.32 * len(df) + 0.6))
    y = np.arange(len(df))
    xs = df["proposed_attempt"].to_numpy(dtype=float)
    los = _safe_clip(xs - df.get("proposed_attempt_lo", xs).to_numpy(dtype=float))
    his = _safe_clip(df.get("proposed_attempt_hi", xs).to_numpy(dtype=float) - xs)
    ax.barh(y, xs, color="#34495e", height=0.6, edgecolor="white")
    ax.errorbar(xs, y, xerr=[los, his], fmt="none", ecolor="#7f8c8d", capsize=2)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.set_xlabel("Proposed attempt rate (Wilson 95% CI)")
    ax.set_xlim(left=0)
    ax.grid(axis="x", alpha=0.25)
    ax.set_title("Highest-risk defense x carrier cells")
    fig.tight_layout()
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


def fig5_defense_matrix_full(bycd: pd.DataFrame, outpath: Path) -> None:
    """Full heatmap retained for the supplementary."""
    if bycd.empty or "defense" not in bycd.columns or "attack_carrier" not in bycd.columns:
        return
    df = bycd[bycd["attack_carrier"] != "none"].copy()
    pv = df.pivot_table(index="defense", columns="attack_carrier",
                          values="proposed_attempt", aggfunc="mean")
    nv = df.pivot_table(index="defense", columns="attack_carrier",
                          values="n", aggfunc="sum")
    if pv.empty:
        return
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    im = ax.imshow(pv.values, aspect="auto", cmap="Greys",
                    vmin=0, vmax=max(0.1, float(np.nanmax(pv.values))))
    ax.set_xticks(range(len(pv.columns)))
    ax.set_xticklabels([CARRIER_SHORT.get(c, c) for c in pv.columns])
    ax.set_yticks(range(len(pv.index)))
    ax.set_yticklabels([DEFENSE_SHORT.get(d, d) for d in pv.index])
    for i in range(pv.shape[0]):
        for j in range(pv.shape[1]):
            v = pv.values[i, j]
            n = nv.values[i, j] if not np.isnan(nv.values[i, j]) else 0
            if math.isnan(v) or n == 0:
                ax.text(j, i, "—", ha="center", va="center", fontsize=8,
                        color="#aaaaaa")
            else:
                ax.text(j, i, f"{100*v:.0f}%", ha="center", va="center",
                        fontsize=7.5,
                        color=("white" if v > 0.5 else "black"))
    ax.set_title("Attempt rate by defense x carrier")
    plt.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    fig.tight_layout()
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


# -------- fig 6: outcome taxonomy (replaces old fig 6, with muted palette) --------

def fig6_action_taxonomy(all_runs: pd.DataFrame, outpath: Path) -> None:
    if all_runs.empty:
        return
    df = all_runs[~all_runs["no_attack"]].copy()
    df = df[df["model"].isin(QWEN_FAMILY)]
    if df.empty:
        return
    def classify(r):
        if r.get("environment_failure"):
            return "env failure"
        if r.get("attack_completed"):
            return "completed"
        if r.get("unsafe_action_landed"):
            return "landed"
        if r.get("unsafe_action_blocked"):
            return "blocked"
        if r.get("parser_failure"):
            return "parser fail"
        if r.get("utility_pass"):
            return "clean fix"
        return "no fix"
    df["cat"] = df.apply(classify, axis=1)
    cats = ["clean fix", "no fix", "parser fail", "blocked",
            "landed", "completed", "env failure"]
    # muted, colorblind-aware palette
    colors = ["#4c72b0", "#cccccc", "#dbd35c", "#d99554",
              "#8b5a3c", "#882e2e", "#7f8c8d"]
    counts = pd.crosstab(df["model"], df["cat"]).reindex(columns=cats, fill_value=0)
    # Force model (x-axis) order by size, not alphabetical (1.5B,3B,7B,14B).
    counts = counts.reindex(index=[m for m in QWEN_FAMILY if m in counts.index])
    totals = counts.sum(axis=1)
    pct = counts.div(totals, axis=0) * 100
    fig, ax = plt.subplots(figsize=(4.0, 3.0))
    bottom = np.zeros(len(pct))
    xs = np.arange(len(pct))
    for cat, color in zip(cats, colors):
        vals = pct[cat].to_numpy()
        ax.bar(xs, vals, bottom=bottom, label=cat, color=color, width=0.6,
               edgecolor="white", linewidth=0.5)
        bottom += vals
    short = [MODEL_SHORT.get(m, m) for m in pct.index]
    ax.set_xticks(xs)
    ax.set_xticklabels(short)
    ax.set_ylabel("Share of attacked runs (%)")
    ax.set_xlabel("Qwen2.5-Coder size")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.2)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20),
              ncol=4, frameon=False, fontsize=7)
    ax.set_title("Per-run outcome taxonomy")
    plt.subplots_adjust(bottom=0.32)
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


# -------- fig 6 (was fig 7): sandbox ablation (vertical two-panel) --

def fig7_sandbox_ablation(all_runs: pd.DataFrame, outpath: Path) -> None:
    if all_runs.empty or "sandbox_mode" not in all_runs.columns:
        return
    df = all_runs[~all_runs["no_attack"]].copy()
    df = df[df["model"].isin(["qwen2.5-coder:3b", "qwen2.5-coder:7b"])]
    if df.empty:
        return
    grp = df.groupby(["sandbox_mode", "model"])[
        ["proposed_attempt", "unsafe_action_landed", "attack_completed"]
    ].mean().reset_index()
    if grp.empty:
        return

    metrics = ["proposed_attempt", "unsafe_action_landed", "attack_completed"]
    metric_labels = ["Attempt", "Landed", "Completed"]
    modes = ["strict", "ide_like_marker"]
    models = ["qwen2.5-coder:3b", "qwen2.5-coder:7b"]
    fig, axes = plt.subplots(2, 1, figsize=(3.4, 3.4),
                              gridspec_kw={"hspace": 0.55})
    for ax, mode in zip(axes, modes):
        sub = grp[grp["sandbox_mode"] == mode].set_index("model").reindex(models)
        xs = np.arange(len(metrics))
        w = 0.34
        for i, m in enumerate(models):
            vals = sub.loc[m, metrics].to_numpy(dtype=float) if m in sub.index else np.zeros(len(metrics))
            ax.bar(xs + (i - 0.5) * w, vals, width=w,
                   color=("#34495e" if i == 0 else "#7f8c8d"),
                   label=MODEL_SHORT.get(m, m))
        ax.set_xticks(xs); ax.set_xticklabels(metric_labels)
        ax.set_ylabel("Rate")
        title = "Strict sandbox" if mode == "strict" else "IDE-like marker sandbox"
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
        ax.set_ylim(0, max(0.05, ax.get_ylim()[1]))
    axes[0].legend(loc="upper right", frameon=False, fontsize=7, ncol=2)
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


# -------- fig 7 (was fig 8): cross-family pilot -----------------

def fig8_cross_family(all_runs: pd.DataFrame, outpath: Path) -> None:
    """Compact horizontal-bar pilot summary; muted palette."""
    if all_runs.empty:
        return
    df = all_runs[~all_runs["no_attack"]].copy()
    if df.empty:
        return
    df = df.groupby("model")[
        ["proposed_attempt", "unsafe_action_landed", "attack_completed", "utility_pass"]
    ].mean().reset_index()
    if df.empty:
        return
    df = df.sort_values("model")
    metrics = ["utility_pass", "proposed_attempt", "unsafe_action_landed",
               "attack_completed"]
    labels = ["clean pass", "attempt", "landed", "completed"]
    colors = ["#4c72b0", "#34495e", "#8b5a3c", "#882e2e"]
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    y = np.arange(len(df))
    w = 0.22
    for i, (m, lab, c) in enumerate(zip(metrics, labels, colors)):
        ax.barh(y + (i - 1.5) * w, df[m].to_numpy(), height=w,
                color=c, label=lab, edgecolor="white", linewidth=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels([MODEL_SHORT.get(m, m) for m in df["model"]])
    ax.set_xlim(0, max(0.7, float(df[metrics].values.max()) * 1.2))
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="upper right", frameon=False, fontsize=7, ncol=2)
    ax.set_title("Cross-family pilot (attacked runs)")
    fig.tight_layout()
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agg", default=str(REPO / "results" / "aggregate"))
    ap.add_argument("--out", default=str(REPO / "paper" / "figures"))
    args = ap.parse_args()
    agg = Path(args.agg); out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    fig1_pipeline(out / "fig1_pipeline.pdf")
    fig1_pipeline(out / "fig1_pipeline.png")

    def _read(name):
        p = agg / name
        return pd.read_csv(p) if p.exists() else pd.DataFrame()

    matched_md = _read("matched_model_defense.csv")
    matched_m = _read("matched_model.csv")
    byc = _read("by_carrier.csv")
    bycd = _read("by_defense_carrier.csv")
    all_runs = _read("all_runs.csv")
    if not matched_md.empty:
        fig2_safety_utility(matched_md, out / "fig2_safety_utility.pdf")
        fig2_safety_utility(matched_md, out / "fig2_safety_utility.png")
    if not byc.empty:
        fig3_carriers(byc, out / "fig3_carriers.pdf")
        fig3_carriers(byc, out / "fig3_carriers.png")
    if not matched_m.empty:
        fig4_model_scaling(matched_m, out / "fig4_model_scaling.pdf")
        fig4_model_scaling(matched_m, out / "fig4_model_scaling.png")
    if not bycd.empty:
        fig5_top_cells(bycd, out / "fig5_top_cells.pdf")
        fig5_top_cells(bycd, out / "fig5_top_cells.png")
        fig5_defense_matrix_full(bycd, out / "fig5_defense_matrix.pdf")
        fig5_defense_matrix_full(bycd, out / "fig5_defense_matrix.png")
    if not all_runs.empty:
        fig6_action_taxonomy(all_runs, out / "fig6_action_taxonomy.pdf")
        fig6_action_taxonomy(all_runs, out / "fig6_action_taxonomy.png")
        fig7_sandbox_ablation(all_runs, out / "fig7_sandbox_ablation.pdf")
        fig7_sandbox_ablation(all_runs, out / "fig7_sandbox_ablation.png")
        # Cross-family figure restricted to non-Qwen models
        cf = all_runs[~all_runs["model"].astype(str).str.startswith(
            "qwen2.5-coder")]
        if not cf.empty:
            fig8_cross_family(cf, out / "fig8_cross_family.pdf")
            fig8_cross_family(cf, out / "fig8_cross_family.png")
        else:
            _placeholder(out / "fig8_cross_family.pdf",
                          "Cross-family pilot results pending.")
            _placeholder(out / "fig8_cross_family.png",
                          "Cross-family pilot results pending.")
    print(f"[figures] wrote to {out}")


def _placeholder(outpath: Path, msg: str) -> None:
    """Render a small placeholder image so the paper still compiles."""
    fig, ax = plt.subplots(figsize=(3.5, 2.0))
    ax.set_axis_off()
    ax.text(0.5, 0.5, msg, ha="center", va="center", fontsize=8)
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
