"""Tune whole-round integer weights; never edit a round's events or payout."""
import argparse
import csv
import json
import math
import os
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.special import ndtr

from games.graveyard_shift.audit import audit, contract, json_default, mode_spec
from games.graveyard_shift.simulate import digest, fingerprint

TOTAL_WEIGHT = 10**16
TARGETS = {
    "base": {"zero": .70, "std": 35, "feature": .0045},
    "ante": {"zero": .62, "std": 25, "feature": .0135},
    "boosted": {"zero": .55, "std": 15, "feature": .0045},
    "bonus": {"zero": .08, "std": 3},
    "super": {"zero": .06, "std": 3.5},
    "hidden": {"zero": .05, "std": 3.5},
}
EDGES = np.array([0, .25, .5, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 10000, 30000])


def read_candidates(root, mode):
    progress = json.loads((root / "progress.json").read_text())
    if not progress["complete"] or progress["model_hash"] != fingerprint()[0]:
        raise ValueError("Incomplete or different model checkpoint")
    batches = sorted((b for b in progress["completed_batches"] if b["mode"] == mode), key=lambda b: b["start"])
    rows = []
    for b in batches:
        file = root / mode / f"{b['start']:08d}-{b['count']}.csv"
        if digest(file) != b["sha256"][file.name]:
            raise ValueError("Candidate CSV checksum changed")
        with file.open(newline="") as handle:
            rows.extend([tuple(map(int, r)) for r in csv.reader(handle)])
    if [r[0] for r in rows] != list(range(progress["count_per_mode"])):
        raise ValueError("Candidate IDs are incomplete or overlapping")
    return rows


def spread_weight(weights, indices, amount):
    base, extra = divmod(int(amount), len(indices))
    for index in indices:
        weights[index] = base
    for index in indices[:extra]:
        weights[index] += 1


def integer_weights(probabilities, groups, payouts, cost):
    if len(probabilities) != len(groups) or not all(groups):
        raise ValueError("Every probability needs a nonempty outcome group")
    if sorted(i for group in groups for i in group) != list(range(len(payouts))):
        raise ValueError("Outcome groups must partition all rows exactly once")
    if any(not math.isfinite(float(p)) or p < 0 for p in probabilities):
        raise ValueError("Invalid selection probabilities")
    weights = [0] * len(payouts)
    for probability, indices in zip(probabilities, groups):
        spread_weight(weights, indices, round(float(probability) * TOTAL_WEIGHT))
    zero = next(i for i, p in enumerate(payouts) if p == 0)
    weights[zero] += TOTAL_WEIGHT - sum(weights)
    target = F(contract()["target_rtp"]) * cost * 100 * TOTAL_WEIGHT
    if target.denominator != 1:
        raise ValueError("Weight scale cannot express target payout")
    error = int(target) - sum(w * int(p) for w, p in zip(weights, payouts))
    if error:
        # Use existing smallest prize classes to correct rounding exactly.
        values = sorted(set(int(p) for p in payouts if p))
        a = values[0]
        b = next((p for p in values if math.gcd(a, p) < a), a)
        def egcd(x, y):
            if not y:
                return x, 1, 0
            g, u, v = egcd(y, x % y)
            return g, v, u - (x // y) * v
        g, u, v = egcd(a, b)
        if error % g:
            raise ValueError("Available payouts cannot express exact rounding repair")
        for prize, change in [(a, u * (error // g)), (b, v * (error // g))]:
            if not change:
                continue
            index = max((i for i, p in enumerate(payouts) if p == prize), key=lambda i: weights[i])
            weights[index] += change
            weights[zero] -= change
    if min(weights) < 0 or sum(weights) != TOTAL_WEIGHT:
        raise ValueError("Unsafe integer rounding repair")
    if sum(w * int(p) for w, p in zip(weights, payouts)) != target:
        raise ValueError("RTP repair not exact")
    return weights


def fit(rows, mode):
    cost = mode_spec(mode)["cost"]
    payouts = np.array([r[1] for r in rows], dtype=np.int64)
    if mode == "maxzero":
        groups = [[i for i, p in enumerate(payouts) if p == value] for value in [0, 2500000]]
        if sum(map(len, groups)) != len(rows) or not all(groups):
            raise ValueError("Binary feature candidate mismatch")
        return integer_weights([1 - .03848, .03848], groups, payouts, cost), {"method": "exact-binary-weights"}
    x = payouts.astype(float) / 100 / cost
    feature = np.array([r[2] for r in rows])
    buckets = defaultdict(list)
    for i, value in enumerate(x):
        band = -1 if value == 0 else 999 if payouts[i] == 2500000 else int(np.searchsorted(EDGES, value, side="left") - 1)
        buckets[(band, int(feature[i]) if mode in ("base", "ante", "boosted") else 1)].append(i)
    keys = sorted(buckets)
    groups = [buckets[k] for k in keys]
    count = len(groups)
    mean = np.array([np.mean(x[g]) for g in groups])
    moment = np.array([np.mean(x[g] ** 2) for g in groups])
    iszero = np.array([k[0] == -1 for k in keys], dtype=float)
    iscap = np.array([k[0] == 999 for k in keys], dtype=float)
    isfeature = np.array([k[1] for k in keys], dtype=float)
    target = TARGETS[mode]
    prior = []
    for band, has_feature in keys:
        if band == -1:
            p = target["zero"]
        elif band == 999:
            p = 1e-6
        else:
            mu = math.log(40 / cost) if has_feature and mode in ("base", "ante", "boosted") else -.8
            sigma = 1.5
            lo, hi = EDGES[band], EDGES[band + 1]
            p = (float(ndtr((math.log(hi) - mu) / sigma)) - (float(ndtr((math.log(lo) - mu) / sigma)) if lo else 0)) * (1 - target["zero"])
        if "feature" in target:
            p *= target["feature"] if has_feature else 1 - target["feature"]
        prior.append(max(p, 1e-10))
    prior = np.array(prior)
    prior /= prior.sum()
    rtp = float(F(contract()["target_rtp"]))
    second = target["std"] ** 2 + rtp ** 2
    equal = [np.ones(count), mean, moment / second, iszero, iscap]
    rhs = [1, rtp, 1, target["zero"], 1e-6]
    if "feature" in target:
        equal.append(isfeature)
        rhs.append(target["feature"])
    # Current non-critical risk constraints. Binary mode is reported separately.
    risk = [np.array([np.mean((payouts[g] >= 500000).astype(float)) for g in groups]),
            np.array([np.mean((payouts[g] >= 1000000).astype(float)) for g in groups]),
            np.array([np.mean(x[g] * (x[g] > 40)) for g in groups]),
            np.array([np.mean(x[g] * (payouts[g] > 1000000)) for g in groups]),
            np.array([np.mean(x[g] * ((x[g] > 40).astype(float) + (payouts[g] > 1000000).astype(float))) for g in groups]),
            np.array([np.mean(np.maximum(x[g] - 40, 0)) for g in groups])]
    # Keep a margin so exact integer rounding cannot cross a risk boundary.
    bounds_rhs = [.0499, .0099, .899, .799, 1.499, (699 - 40) * .001]
    objective = np.r_[np.zeros(count), 1 / np.maximum(prior, .001)]
    identity = np.eye(count)
    ub = np.vstack([np.c_[identity, -identity], np.c_[-identity, -identity], np.c_[np.array(risk), np.zeros((len(risk), count))]])
    result = linprog(objective, A_ub=ub, b_ub=np.r_[prior, -prior, bounds_rhs],
                     A_eq=np.c_[equal, np.zeros((len(equal), count))], b_eq=rhs,
                     bounds=[(1e-10, None)] * count + [(0, None)] * count, method="highs")
    if not result.success:
        raise ValueError(f"{mode}: whole-round weight fit failed: {result.message}")
    weights = integer_weights(result.x[:count], groups, payouts, cost)
    return weights, {"method": "whole-round-bucket-linear-program-with-exact-integer-repair",
                     "internal_shape_targets": target, "buckets": count,
                     "maxwin_probability_target": "1/1000000", "events_modified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}
    for spec in contract()["modes"]:
        mode = spec["id"]
        rows = read_candidates(args.candidates, mode)
        weights, tuning = fit(rows, mode)
        lut = [(r[0], w, r[1]) for r, w in zip(rows, weights)]
        report = audit(lut, mode)
        report["exact_rtp"] = str(report["metrics"]["rtp"])
        report["tuning"] = tuning
        report["weighted_feature_probability"] = F(sum(w * r[2] for r, w in zip(rows, weights)), TOTAL_WEIGHT)
        report["weighted_average_spins"] = F(sum(w * r[3] for r, w in zip(rows, weights)), TOTAL_WEIGHT)
        if report["metrics"]["rtp"] != F(contract()["target_rtp"]):
            raise ValueError("RTP is not exact after integer export")
        if report["checks"]["critical_distribution_failures"]:
            raise ValueError(f"Critical failures: {mode}: {report['checks']}")
        if mode != "maxzero" and report["checks"]["three_star_risk_classes"]:
            raise ValueError(f"Unexpected risk classes: {mode}: {report['checks']}")
        path = args.output / f"lookUpTable_{mode}_0.csv"
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", newline="") as handle:
            csv.writer(handle, lineterminator="\n").writerows(lut)
        os.replace(temporary, path)
        report["lookup_sha256"] = digest(path)
        results[mode] = report
        print(f"{mode}: exact RTP {report['exact_rtp']}, SD/cost {report['metrics']['std_per_mode_cost']:.3f}, risk classes {list(report['checks']['three_star_risk_classes'])}", flush=True)
        temporary = args.output / "distribution-audit.tmp"
        temporary.write_text(json.dumps({"stage": "weighted-distributions-event-assembly-pending", "model_hash": fingerprint()[0], "modes": results, "all_modes_complete": len(results) == 7, "publish_ready": False}, indent=2, default=json_default) + "\n")
        os.replace(temporary, args.output / "distribution-audit.json")


if __name__ == "__main__":
    main()
