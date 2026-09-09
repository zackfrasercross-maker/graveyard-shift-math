"""Resumable sampling tests of immutable final RGS integer lookup weights.

These are selections from independently replayed event books, not new outcome
generation or an optimizer run. The seed and statistical gates are fixed before
sampling. Failed tests are reported, never repaired by changing a seed/payout.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from fractions import Fraction as F
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from games.graveyard_shift.audit import audit, contract, json_default, mode_spec, validate_rows
from games.graveyard_shift.export import write_json
from games.graveyard_shift.optimize import read_candidates
from games.graveyard_shift.simulate import digest, fingerprint

SEED = 2026090902
FAMILY_ALPHA = .001
BIN_COUNT_BOUND = 12


def ticket_indices(cdf, tickets):
    """Exact half-open integer intervals, including zero-weight rows."""
    if cdf.dtype != np.uint64 or tickets.dtype != np.uint64:
        raise ValueError("CDF and tickets must retain uint64 precision")
    if len(cdf) == 0 or np.any(cdf[1:] < cdf[:-1]) or np.any(tickets >= cdf[-1]):
        raise ValueError("Invalid cumulative weights or ticket range")
    return np.searchsorted(cdf, tickets, side="right")


def batch_counts(folder, identity, cdf):
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{identity['start']:09d}-{identity['count']}"
    path, manifest = folder / f"{stem}.npz", folder / f"{stem}.json"
    if manifest.exists():
        saved = json.loads(manifest.read_text())
        if saved["identity"] != identity or not path.exists() or digest(path) != saved["counts_sha256"]:
            raise ValueError("Sampling checkpoint identity/checksum mismatch")
        with np.load(path, allow_pickle=False) as data:
            counts = data["counts"]
    else:
        seed = np.random.SeedSequence([identity["seed"], identity["mode_index"], identity["start"], identity["count"]])
        rng = np.random.Generator(np.random.PCG64DXSM(seed))
        tickets = rng.integers(0, int(cdf[-1]), size=identity["count"], dtype=np.uint64)
        selected = ticket_indices(cdf, tickets)
        counts = np.bincount(selected, minlength=len(cdf)).astype(np.uint64)
        temporary = path.with_suffix(".tmp")
        with temporary.open("wb") as handle:
            np.savez_compressed(handle, counts=counts)
        os.replace(temporary, path)
        write_json(manifest, {"identity": identity, "counts_sha256": digest(path)})
    if counts.dtype != np.uint64 or counts.shape != cdf.shape or sum(map(int, counts)) != identity["count"]:
        raise ValueError("Invalid sampling count checkpoint")
    return counts


def payout_band(payout, cost):
    if payout == 0:
        return "zero"
    if payout == 2500000:
        return "global_cap"
    if payout < cost * 100:
        return "return_below_cost"
    if payout == cost * 100:
        return "break_even"
    for upper in (5, 25, 100, 1000):
        if payout <= cost * 100 * upper:
            return f"profit_band_up_to_{upper}x_cost"
    return "profit_above_1000x_cost"


def summarize(rows, counts, mode, candidates):
    theory = audit(rows, mode)
    m = theory["metrics"]
    trials, total_weight = sum(map(int, counts)), sum(w for _, w, _ in rows)
    cost = mode_spec(mode)["cost"]
    payout_total = sum(int(n) * row[2] for row, n in zip(rows, counts))
    observed_rtp = F(payout_total, trials * cost * 100)
    observed_second = F(sum(int(n) * row[2] ** 2 for row, n in zip(rows, counts)), trials * (cost * 100) ** 2)
    observed_variance = observed_second - observed_rtp ** 2
    variance = float(m["variance_base_bet"]) / cost ** 2
    standard_error = math.sqrt(variance / trials)
    # Known-variance Bernstein bound for bounded IID sampling. Unlike a normal
    # approximation this accounts conservatively for rare capped payouts.
    # Split the family error budget between mean and frequency diagnostics.
    log_term = math.log(4 * 7 / FAMILY_ALPHA)
    radius_part = (25000 / cost) * log_term / (3 * trials)
    radius = radius_part + math.sqrt(radius_part ** 2 + 2 * variance * log_term / trials)
    masks = {}
    bands = sorted({payout_band(r[2], cost) for r in rows})
    for band in bands:
        masks[band] = [payout_band(r[2], cost) == band for r in rows]
    masks["feature_round"] = [bool(c[2]) for c in candidates]
    masks["tower_reached_level_4"] = [c[5] == 4 for c in candidates]
    if len(masks) > BIN_COUNT_BOUND:
        raise ValueError("Multiple-testing correction needs updating")
    frequency_tests = {}
    threshold = FAMILY_ALPHA / (2 * 7 * BIN_COUNT_BOUND)
    for name, mask in masks.items():
        weight = sum(r[1] for r, yes in zip(rows, mask) if yes)
        observed = sum(int(n) for n, yes in zip(counts, mask) if yes)
        expected_p = F(weight, total_weight)
        pvalue = float(binomtest(observed, trials, float(expected_p)).pvalue)
        frequency_tests[name] = {"observed_count": observed, "expected_count": float(expected_p * trials),
                                 "expected_probability_exact": str(expected_p), "observed_probability": observed / trials,
                                 "two_sided_binomial_pvalue": pvalue, "pass": pvalue >= threshold}
    failed = [name for name, value in frequency_tests.items() if not value["pass"]]
    mean_pass = abs(float(observed_rtp - m["rtp"])) <= radius
    return {"mode": mode, "trials": trials, "theoretical_rtp_exact": str(m["rtp"]),
            "observed_rtp_exact": str(observed_rtp), "observed_rtp": float(observed_rtp),
            "theoretical_standard_deviation_per_cost": m["std_per_mode_cost"],
            "observed_standard_deviation_per_cost": math.sqrt(float(observed_variance)),
            "normal_standard_error_of_rtp": standard_error,
            "normal_95_percent_half_width_approximate": 1.959963984540054 * standard_error,
            "bernstein_mean_bound": {"family_alpha": FAMILY_ALPHA, "modes": 7, "half_width": radius, "pass": mean_pass},
            "frequency_test_threshold": threshold, "frequency_tests": frequency_tests,
            "failed_frequency_tests": failed, "distinct_book_ids_selected": int(np.count_nonzero(counts)),
            "selected_underlying_spins_including_free_spins": sum(int(n) * c[3] for n, c in zip(counts, candidates)),
            "all_sampling_tests_pass": mean_pass and not failed,
            "note": "Finite observed RTP fluctuates; exact RTP belongs to immutable lookup weights. These trials do not create additional unique event books or constitute Stake RNG/platform certification."}


def test_mode(task):
    export, candidates, output, mode_index, mode, total_trials, batch_size = task
    export, candidates, output = Path(export), Path(candidates), Path(output)
    verification = json.loads((export / "verification.json").read_text())
    if not verification["complete"] or verification["model_hash"] != fingerprint()[0]:
        raise ValueError("Final event verification is incomplete or belongs to another model")
    original = verification["modes"][mode]
    for name, sha in original["files_sha256"].items():
        if digest(export / name) != sha:
            raise ValueError("Final verified export changed")
    path = export / f"lookUpTable_{mode}_0.csv"
    with path.open(newline="") as handle:
        rows = validate_rows(csv.reader(handle))
    candidate_rows = read_candidates(candidates, mode)
    if [(r[0], r[2]) for r in rows] != [(c[0], c[1]) for c in candidate_rows]:
        raise ValueError("Candidate statistics do not match final weighted books")
    theory = audit(rows, mode)
    if theory["metrics"]["rtp"] != F("0.962") or theory["checks"]["critical_distribution_failures"]:
        raise ValueError("Final theoretical distribution gate failed")
    cdf = np.cumsum(np.array([r[1] for r in rows], dtype=np.uint64), dtype=np.uint64)
    identity = {"seed": SEED, "mode": mode, "mode_index": mode_index, "lookup_sha256": digest(path),
                "book_sha256": digest(export / f"books_{mode}.jsonl.zst"), "test_code_sha256": digest(Path(__file__)),
                "model_hash": fingerprint()[0], "rng": "NumPy PCG64DXSM", "numpy_version": np.__version__}
    run_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    folder = output / mode / run_id
    counts = np.zeros(len(rows), dtype=np.uint64)
    for start in range(0, total_trials, batch_size):
        amount = min(batch_size, total_trials - start)
        counts += batch_counts(folder, {**identity, "start": start, "count": amount}, cdf)
        print(f"{mode}: {start + amount:,}/{total_trials:,} weighted test rounds checkpointed", flush=True)
    report = summarize(rows, counts, mode, candidate_rows)
    report["identity"] = identity
    with (folder / "final-counts.npz").open("wb") as handle:
        np.savez_compressed(handle, counts=counts)
    report["counts_sha256"] = digest(folder / "final-counts.npz")
    report["counts_path"] = str((folder / "final-counts.npz").relative_to(output))
    write_json(output / f"test_{mode}.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=10000000)
    parser.add_argument("--batch", type=int, default=1000000)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if min(args.trials, args.batch, args.workers) < 1 or args.trials > 1000000000:
        parser.error("Positive counts required; maximum one billion trials per mode")
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}
    modes = contract()["modes"]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(test_mode, (str(args.export), str(args.candidates), str(args.output), i, m["id"], args.trials, args.batch)) for i, m in enumerate(modes)]
        for future in as_completed(jobs):
            report = future.result()
            results[report["mode"]] = report
            write_json(args.output / "final-test.json", {"requested_trials_per_mode": args.trials,
                       "completed_trials": sum(r["trials"] for r in results.values()), "complete": len(results) == 7,
                       "all_sampling_tests_pass": len(results) == 7 and all(r["all_sampling_tests_pass"] for r in results.values()),
                       "modes": results, "publish_approval": False})
    if not all(r["all_sampling_tests_pass"] for r in results.values()):
        raise SystemExit("Statistical diagnostic failed; inspect the saved report without changing the seed.")


if __name__ == "__main__":
    main()
