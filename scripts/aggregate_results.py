"""Aggregate scored runs (results/scored/main.jsonl) into pivot CSV/JSON.

Reads the rescored stream — never the raw stream — so there is exactly
one source of truth for paper numbers.  Provides both marginal Wilson
CIs and *matched* bootstrap CIs over (task, model, defense, seed)
tuples for the headline tables and figures.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd

from repoguard.utils.io import read_jsonl, write_json


SCORED_DEFAULT = REPO / "results" / "scored" / "main.jsonl"
RAW_DEFAULT = REPO / "results" / "raw" / "main.jsonl"


def wilson(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    denom = 1 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    margin = (z * math.sqrt((p_hat * (1 - p_hat) + z * z / (4 * n)) / n)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def to_dataframe(path: Path) -> pd.DataFrame:
    rows = list(read_jsonl(path))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    bool_cols = (
        "utility_pass",
        "proposed_attempt",
        "unsafe_action_blocked",
        "unsafe_action_landed",
        "attack_completed",
        "parser_failure",
        "environment_failure",
        "no_attack",
    )
    for c in bool_cols:
        if c in df.columns:
            df[c] = df[c].astype(bool)
    for c in ("tier", "model", "defense", "attack_carrier", "attack_goal"):
        if c in df.columns:
            df[c] = df[c].astype(str)
    return df


def summarize(df: pd.DataFrame) -> Dict[str, Any]:
    n = len(df)
    out: Dict[str, Any] = {"n": n}
    if n == 0:
        return out
    for col in ("utility_pass", "proposed_attempt", "unsafe_action_blocked",
                "unsafe_action_landed", "attack_completed",
                "parser_failure", "environment_failure"):
        if col in df.columns:
            p = float(df[col].mean())
            lo, hi = wilson(p, n)
            out[col] = p
            out[col + "_lo"] = lo
            out[col + "_hi"] = hi
    for col in ("wall_clock_s", "prompt_tokens", "completion_tokens",
                "defense_blocks", "turns_used"):
        if col in df.columns:
            out[col] = float(df[col].mean())
    return out


def pivot(df: pd.DataFrame, keys: List[str]) -> pd.DataFrame:
    out = []
    for kv, sub in df.groupby(keys):
        rec = dict(zip(keys, kv if isinstance(kv, tuple) else (kv,)))
        rec.update(summarize(sub))
        out.append(rec)
    return pd.DataFrame(out)


# ---------- matched analysis ---------------------------------------------

def _matched_one_group(sub: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> Dict[str, Any]:
    rec: Dict[str, Any] = {}
    clean = sub[sub["no_attack"]]
    attacked = sub[~sub["no_attack"]]
    match_keys = ["task_id", "model", "defense", "seed"]
    clean_per = clean.groupby(match_keys)["utility_pass"].mean()
    atk_per = attacked.groupby(match_keys).agg(
        util=("utility_pass", "mean"),
        attempt=("proposed_attempt", "mean"),
        blocked=("unsafe_action_blocked", "mean"),
        landed=("unsafe_action_landed", "mean"),
        complete=("attack_completed", "mean"),
    )
    joined = atk_per.join(clean_per.rename("util_clean"), how="inner")
    rec["n_matched"] = int(len(joined))
    for col in ("util", "util_clean", "attempt", "blocked", "landed", "complete"):
        if col in joined.columns:
            rec[col + "_mean"] = float(joined[col].mean()) if len(joined) else float("nan")
    if "util" in joined.columns and "util_clean" in joined.columns and len(joined):
        joined = joined.copy()
        joined["util_delta"] = joined["util"] - joined["util_clean"]
        rec["util_delta_mean"] = float(joined["util_delta"].mean())
        if len(joined) >= 2 and n_boot > 0:
            idx = np.arange(len(joined))
            samples = rng.choice(idx, size=(n_boot, len(joined)), replace=True)
            ds = joined["util_delta"].to_numpy()
            boot = ds[samples].mean(axis=1)
            rec["util_delta_lo"] = float(np.percentile(boot, 2.5))
            rec["util_delta_hi"] = float(np.percentile(boot, 97.5))
            for col in ("attempt", "landed", "complete"):
                if col in joined.columns:
                    xs = joined[col].to_numpy()
                    bs = xs[samples].mean(axis=1)
                    rec[col + "_lo"] = float(np.percentile(bs, 2.5))
                    rec[col + "_hi"] = float(np.percentile(bs, 97.5))
        else:
            rec["util_delta_lo"] = float("nan")
            rec["util_delta_hi"] = float("nan")
    return rec


def matched_table(df: pd.DataFrame, group_keys: List[str], n_boot: int = 1000,
                  rng_seed: int = 7) -> pd.DataFrame:
    """For each group, compute matched (clean vs attacked) utility delta and
    matched proposed-attempt / landed / completion rates with bootstrap CIs.

    A *match* is a triple ``(task_id, model, defense, seed)``.
    Clean runs are those with ``no_attack == True``; attacked runs share the
    same triple and any carrier/goal.  We average across the carriers/goals
    for each match so the unit of analysis is the (task, model, defense) tuple.
    """
    rng = np.random.default_rng(rng_seed)
    if not group_keys:
        rec = _matched_one_group(df, rng, n_boot)
        return pd.DataFrame([rec])
    rows: List[Dict[str, Any]] = []
    for kv, sub in df.groupby(group_keys):
        rec = dict(zip(group_keys, kv if isinstance(kv, tuple) else (kv,)))
        rec.update(_matched_one_group(sub, rng, n_boot))
        rows.append(rec)
    return pd.DataFrame(rows)


def matched_common_subset(df: pd.DataFrame, model: str, defenses: List[str],
                          n_boot: int = 1000, rng_seed: int = 7
                          ) -> Tuple[pd.DataFrame, List[str]]:
    """Matched-by-defense table restricted to the task subset that is attacked
    under EVERY defense in ``defenses`` for ``model``.

    This removes the cross-defense subset confound flagged in review: in the
    full grid each defense column lands on a different task subset (so the
    marginal clean-pass rate drifts across columns).  Here every defense is
    scored on the *same* shared tasks, so the comparison is apples-to-apples.
    Returns (table, sorted_common_task_ids).
    """
    sub = df[df["model"].astype(str) == model]
    if sub.empty:
        return pd.DataFrame(), []
    atk = sub[~sub["no_attack"]]
    task_sets = [set(atk[atk["defense"] == d]["task_id"].unique()) for d in defenses]
    task_sets = [s for s in task_sets if s]
    if not task_sets:
        return pd.DataFrame(), []
    common = set.intersection(*task_sets)
    if not common:
        return pd.DataFrame(), []
    sub_common = sub[sub["task_id"].isin(common) & sub["defense"].isin(defenses)]
    mt = matched_table(sub_common, ["defense"], n_boot=n_boot, rng_seed=rng_seed)
    mt["n_common_tasks"] = len(common)
    return mt, sorted(common)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", default=str(SCORED_DEFAULT))
    ap.add_argument("--raw", default=str(RAW_DEFAULT))
    ap.add_argument("--outdir", default=str(REPO / "results" / "aggregate"))
    args = ap.parse_args()

    scored_path = Path(args.scored)
    raw_path = Path(args.raw)
    if not scored_path.exists() and raw_path.exists():
        # Auto-rescore if scored is missing.
        import subprocess
        subprocess.run([sys.executable, str(REPO / "scripts" / "audit_scoring.py"),
                         "--raw", str(raw_path), "--out", str(scored_path)],
                        check=True)
    df = to_dataframe(scored_path)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    if df.empty:
        return

    df.to_csv(outdir / "all_runs.csv", index=False)

    # Marginal pivots
    baseline = df[df["no_attack"]]
    attacked = df[~df["no_attack"]]
    if not baseline.empty:
        pivot(baseline, ["tier", "model", "defense"]).to_csv(
            outdir / "baseline_utility.csv", index=False)
    if not attacked.empty:
        pivot(attacked, ["tier", "model", "defense", "attack_carrier"]).to_csv(
            outdir / "by_carrier_defense_model.csv", index=False)
        pivot(attacked, ["tier", "model", "defense"]).to_csv(
            outdir / "by_defense_model.csv", index=False)
        pivot(attacked, ["model", "attack_carrier"]).to_csv(
            outdir / "by_model_carrier.csv", index=False)
        pivot(attacked, ["defense", "attack_carrier"]).to_csv(
            outdir / "by_defense_carrier.csv", index=False)
        pivot(attacked, ["defense"]).to_csv(outdir / "by_defense.csv", index=False)
        pivot(attacked, ["attack_carrier"]).to_csv(outdir / "by_carrier.csv", index=False)
        pivot(attacked, ["model"]).to_csv(outdir / "by_model.csv", index=False)
        pivot(attacked, ["attack_goal"]).to_csv(outdir / "by_goal.csv", index=False)
        pivot(attacked, ["model", "defense", "attack_carrier"]).to_csv(
            outdir / "by_model_defense_carrier.csv", index=False)
        pivot(attacked, ["model", "defense"]).to_csv(
            outdir / "by_model_defense.csv", index=False)

    # Matched aggregates (the headline source)
    mt_md = matched_table(df, ["model", "defense"])
    mt_md.to_csv(outdir / "matched_model_defense.csv", index=False)
    mt_m = matched_table(df, ["model"])
    mt_m.to_csv(outdir / "matched_model.csv", index=False)
    mt_d = matched_table(df, ["defense"])
    mt_d.to_csv(outdir / "matched_defense.csv", index=False)
    mt_c = matched_table(df, ["model", "defense", "attack_carrier"]) if "attack_carrier" in df.columns else pd.DataFrame()
    mt_c.to_csv(outdir / "matched_model_defense_carrier.csv", index=False)
    mt_t = matched_table(df, ["tier", "model"]) if "tier" in df.columns else pd.DataFrame()
    mt_t.to_csv(outdir / "matched_tier_model.csv", index=False)

    # Common-subset matched comparison for the primary model: every defense
    # scored on the SAME shared tasks (removes the cross-defense subset
    # confound where each column otherwise lands on a different task set).
    PRIMARY_MODEL = "qwen2.5-coder:3b"
    PRIMARY_DEFENSES = ["D0_none", "D1_spotlight", "D2_strip",
                         "D3_action_gate", "D5_human_confirm"]
    mt_common, common_tasks = matched_common_subset(df, PRIMARY_MODEL, PRIMARY_DEFENSES)
    if not mt_common.empty:
        mt_common.to_csv(outdir / "matched_defense_common.csv", index=False)
        write_json(outdir / "matched_defense_common_meta.json",
                   {"model": PRIMARY_MODEL, "defenses": PRIMARY_DEFENSES,
                    "n_common_tasks": len(common_tasks),
                    "common_tasks": common_tasks})

    # Final headline (paired)
    matched_overall = matched_table(df, [])  # zero-key grouping -> single row
    if matched_overall.empty:
        matched_overall = pd.DataFrame([{}])
    h0 = matched_overall.iloc[0].to_dict() if not matched_overall.empty else {}

    overall_attempt = float(attacked["proposed_attempt"].mean()) if not attacked.empty else 0.0
    overall_blocked = float(attacked["unsafe_action_blocked"].mean()) if not attacked.empty else 0.0
    overall_landed = float(attacked["unsafe_action_landed"].mean()) if not attacked.empty else 0.0
    overall_complete = float(attacked["attack_completed"].mean()) if not attacked.empty else 0.0
    headline = {
        "n_runs": int(len(df)),
        "n_unique_tasks": int(df["task_id"].nunique()),
        "n_no_attack": int(df["no_attack"].sum()),
        "n_attacked": int((~df["no_attack"]).sum()),
        "models": sorted(df["model"].unique().tolist()),
        "defenses": sorted(df["defense"].unique().tolist()),
        "carriers": sorted([c for c in df["attack_carrier"].unique().tolist() if c != "none"]),
        "tiers": sorted(df["tier"].unique().tolist()),
        # Marginal
        "overall_utility_no_attack": float(baseline["utility_pass"].mean()) if not baseline.empty else None,
        "overall_utility_attacked": float(attacked["utility_pass"].mean()) if not attacked.empty else None,
        "overall_attempt_rate": overall_attempt,
        "overall_blocked_rate": overall_blocked,
        "overall_landed_rate": overall_landed,
        "overall_completion_rate": overall_complete,
        # Matched
        "matched_util_delta_mean": h0.get("util_delta_mean"),
        "matched_util_delta_lo": h0.get("util_delta_lo"),
        "matched_util_delta_hi": h0.get("util_delta_hi"),
        "matched_attempt_mean": h0.get("attempt_mean"),
        "matched_landed_mean": h0.get("landed_mean"),
        "matched_complete_mean": h0.get("complete_mean"),
        # Other
        "mean_wall_clock_s": float(df["wall_clock_s"].mean()) if "wall_clock_s" in df.columns else None,
        "parser_failure_rate": float(df["parser_failure"].mean()) if "parser_failure" in df.columns else None,
        "environment_failure_rate": float(df["environment_failure"].mean()) if "environment_failure" in df.columns else None,
    }
    write_json(outdir / "headline.json", headline)
    write_json(outdir / "headline_final.json", headline)
    print(json.dumps(headline, indent=2))


if __name__ == "__main__":
    main()
