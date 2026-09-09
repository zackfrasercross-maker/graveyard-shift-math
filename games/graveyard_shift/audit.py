"""Exact weighted-distribution analysis. This is not a game/outcome generator.

Uses integer lookup weights and Fraction arithmetic. Current risk checks follow
the live 2026-09-09 documentation, not the older SDK warning profile.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from fractions import Fraction as F
from math import sqrt
from pathlib import Path

CONTRACT_PATH = Path(__file__).with_name("contract.json")
UINT64_MAX = (1 << 64) - 1
PROFILE_URL = "https://stake-engine.com/docs/approval-guidelines/math-verification"


def contract():
    return json.loads(CONTRACT_PATH.read_text())


def mode_spec(mode):
    matches = [m for m in contract()["modes"] if m["id"] == mode]
    if not matches:
        raise ValueError(f"Unknown frontend mode: {mode}")
    return matches[0]


def validate_rows(rows):
    """Read exact CSV integers; never round malformed payout/weight values."""
    seen, validated, total = set(), [], 0
    cap = contract()["max_payout_base_bet"] * contract()["payout_multiplier_scale"]
    for row in rows:
        if len(row) != 3:
            raise ValueError("Lookup rows need id, weight, payoutMultiplier")
        values = []
        for value in row:
            if isinstance(value, str):
                if not value.isascii() or not value.isdecimal():
                    raise ValueError("Lookup fields must be unsigned decimal integers")
                value = int(value)
            if type(value) is not int or not 0 <= value <= UINT64_MAX:
                raise ValueError("Lookup fields must be uint64 integers")
            values.append(value)
        identifier, weight, payout = values
        if identifier in seen:
            raise ValueError(f"Duplicate simulation ID: {identifier}")
        if payout > cap:
            raise ValueError("Payout exceeds the locked 25,000x base-bet cap")
        if payout % 10:
            raise ValueError("Pinned SDK requires payoutMultiplier increments of 10")
        seen.add(identifier)
        total += weight
        if total > UINT64_MAX:
            raise ValueError("Total lookup weight exceeds uint64")
        validated.append((identifier, weight, payout))
    if not total:
        raise ValueError("Lookup needs positive total weight")
    return validated


def upper_tail_mean(distribution, tail=F(1, 1000)):
    """Mean of exactly the upper tail, splitting boundary-atom probability."""
    if not 0 < tail <= 1 or sum(distribution.values()) != 1:
        raise ValueError("Expected a probability distribution and valid tail")
    remaining, value = tail, F(0)
    for payout, probability in sorted(distribution.items(), reverse=True):
        used = min(remaining, probability)
        value += payout * used
        remaining -= used
        if not remaining:
            break
    return value / tail


def distribution_metrics(rows, mode):
    rows = validate_rows(rows)
    cost = F(mode_spec(mode)["cost"])
    if mode == "maxzero" and any(p not in (0, 2500000) for _, _, p in rows):
        raise ValueError("Max Win or Zero only allows zero or 25,000x base bet")
    total = sum(w for _, w, _ in rows)
    dist = defaultdict(F)
    for _, weight, payout in rows:
        if weight:
            dist[F(payout, 100)] += F(weight, total)
    mean = sum((x * p for x, p in dist.items()), F(0))
    variance = sum(((x - mean) ** 2 * p for x, p in dist.items()), F(0))
    cvar = upper_tail_mean(dist)
    etl40 = sum((x * p for x, p in dist.items() if x > 40 * cost), F(0)) / cost
    etl10k = sum((x * p for x, p in dist.items() if x > 10000), F(0)) / cost
    return {
        "mode": mode, "cost_base_bet": cost, "rtp": mean / cost,
        "expected_payout_base_bet": mean,
        "variance_base_bet": variance, "std_base_bet": sqrt(variance),
        "std_per_mode_cost": sqrt(variance) / float(cost),
        "nonzero_probability": 1 - dist.get(F(0), F(0)),
        "prob5k_raw": sum((p for x, p in dist.items() if x >= 5000), F(0)),
        "prob10k_raw": sum((p for x, p in dist.items() if x >= 10000), F(0)),
        "cvar_absolute": cvar, "cvar_per_mode_cost": cvar / cost,
        "etl40_cost_normalized": etl40, "etl10k_cost_normalized": etl10k,
        "etl_sum": etl40 + etl10k,
        "max_supported_payout_base_bet": max(dist),
        "max_win_probability": dist.get(F(contract()["max_payout_base_bet"]), F(0)),
        "rows": len(rows), "positive_weight_rows": sum(w > 0 for _, w, _ in rows),
        "positive_weight_paying_rows": sum(w > 0 and x > 0 for _, w, x in rows),
        "maximum_single_row_probability": F(max(w for _, w, _ in rows), total),
        "effective_row_count": F(total * total, sum(w * w for _, w, _ in rows)),
        "total_weight": total,
    }


def checks(metrics):
    """Distribution checks only. Event integrity/templates remain separate."""
    m, failures = metrics, []
    if not F("0.90") <= m["rtp"] <= F("0.967"):
        failures.append("rtp_band")
    if m["nonzero_probability"] < F(1, 50):
        failures.append("nonzero_probability")
    if m["mode"] == "base" and m["variance_base_bet"] < F("0.36"):
        failures.append("base_standard_deviation_minimum")
    if m["cost_base_bet"] > 2000:
        failures.append("maximum_cost")
    if m["max_supported_payout_base_bet"] > 500000:
        failures.append("maximum_payout")
    risks = {}
    groups = {
        "payout": [("max_supported_payout_base_bet", F(100000))],
        "cost": [("cost_base_bet", F(2000))],
        "cvar": [("cvar_absolute", F(50000)), ("cvar_per_mode_cost", F(700))],
        "tail_probability": [("prob5k_raw", F("0.05")), ("prob10k_raw", F("0.01"))],
        "tail_liability": [("etl40_cost_normalized", F("0.9")), ("etl10k_cost_normalized", F("0.8")), ("etl_sum", F("1.5"))],
    }
    if m["mode"] == "base":
        groups["base_volatility"] = [("variance_base_bet", F(3600))]
    for group, limits in groups.items():
        exceeded = {key: {"value": m[key], "limit": limit} for key, limit in limits if m[key] > limit}
        if exceeded:
            risks[group] = exceeded
    return {
        "critical_distribution_failures": failures,
        "target_rtp_matches": abs(m["rtp"] - F(contract()["target_rtp"])) <= F(contract()["internal_target_tolerance"]),
        "three_star_risk_classes": risks,
        "unverified": ["gameplay_rules", "book_event_integrity", "simulation_diversity", "book_size_and_event_count", "viable_bet_template", "frontend_playback", "Stake_review"],
    }


def suite_report(mode_rows):
    expected = {m["id"] for m in contract()["modes"]}
    if set(mode_rows) != expected:
        raise ValueError("A suite must include exactly all seven frontend modes")
    result = {mode: audit(rows, mode) for mode, rows in mode_rows.items()}
    rtps = [r["metrics"]["rtp"] for r in result.values()]
    return {"modes": result, "cross_mode_spread": max(rtps) - min(rtps),
            "cross_mode_pass": max(rtps) - min(rtps) <= F("0.005"), "publish_ready": False}


def audit(rows, mode):
    metrics = distribution_metrics(rows, mode)
    return {"metrics": metrics, "checks": checks(metrics), "publish_ready": False}


def maxzero_feasibility():
    cfg, mode = contract(), mode_spec("maxzero")
    hit = F(cfg["target_rtp"]) * mode["cost"] / cfg["max_payout_base_bet"]
    rows = [(0, hit.denominator - hit.numerator, 0),
            (1, hit.numerator, cfg["max_payout_base_bet"] * cfg["payout_multiplier_scale"])]
    result = audit(rows, "maxzero")
    result.update({
        "kind": "analytical_two_outcome_feasibility_NOT_publish_files",
        "frontend_commit": cfg["frontend_commit"], "profile_checked": "2026-09-09",
        "profile_source": PROFILE_URL,
        "exact_hit_probability": str(hit), "exact_rtp": str(result["metrics"]["rtp"]),
        "mean_bets_per_hit": 1 / hit,
        "all_mode_target_mean_payouts_base_bet": {m["id"]: F(cfg["target_rtp"]) * m["cost"] for m in cfg["modes"]},
        "rules_pending": cfg["rules_pending"],
        "other_six_modes_measured": False,
        "note": "Two payout values do not provide a production population of visually varied valid event books. No RNG or paytable is inferred from frontend QA fixtures.",
    })
    return result


def json_default(value):
    if isinstance(value, F):
        return float(value)
    raise TypeError(type(value).__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--maxzero-feasibility", action="store_true")
    source.add_argument("--lut", type=Path)
    parser.add_argument("--mode", choices=[m["id"] for m in contract()["modes"]])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.maxzero_feasibility:
        if args.mode:
            parser.error("--mode is only used with --lut")
        result = maxzero_feasibility()
    else:
        if not args.mode:
            parser.error("--lut requires --mode")
        with args.lut.open(newline="", encoding="utf-8") as handle:
            result = audit(csv.reader(handle), args.mode)
        result["exact_rtp"] = str(result["metrics"]["rtp"])
    output = json.dumps(result, indent=2, default=json_default) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    else:
        print(output, end="")
    return 2 if result["checks"]["critical_distribution_failures"] or not result["checks"]["target_rtp_matches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
