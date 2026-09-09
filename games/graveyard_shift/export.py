"""Assemble immutable weighted books and independently replay the final files."""
import argparse
import contextlib
import csv
import hashlib
import io
import json
import os
import shutil
import warnings
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from fractions import Fraction as F
from itertools import zip_longest
from pathlib import Path
from types import SimpleNamespace

import zstandard as zstd

from games.graveyard_shift.audit import audit, contract, json_default, mode_spec, validate_rows
from games.graveyard_shift.engine import RULES, RULES_HASH
from games.graveyard_shift.optimize import read_candidates
from games.graveyard_shift.replay import verify
from games.graveyard_shift.simulate import digest, fingerprint


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=json_default) + "\n")
    os.replace(temporary, path)


def books(path):
    with path.open("rb") as raw, zstd.ZstdDecompressor().stream_reader(raw) as reader:
        with io.TextIOWrapper(reader, encoding="utf-8") as text:
            for line in text:
                if not line.strip():
                    raise ValueError("Empty event-book record")
                yield json.loads(line)


def replay_export(path, rows, candidates, mode, fixture_dir=None):
    """IDs, payouts, summary rows, tower events, ways and caps must all agree."""
    events, signatures, boards_seen, types, tiers = 0, set(), set(), Counter(), Counter()
    fixtures = {}
    for book, row, candidate in zip_longest(books(path), rows, candidates):
        if book is None or row is None or candidate is None:
            raise ValueError("Book / lookup / candidate lengths differ")
        if book["id"] != row[0] or book["id"] != candidate[0] or book["payoutMultiplier"] != row[2]:
            raise ValueError("Book ID or payout differs from lookup")
        result = verify(book, mode)
        expected = (book["id"], book["payoutMultiplier"], int(bool(result["features"])),
                    result["spins"], result["cascade_wins"], result["max_tower_level"])
        if tuple(candidate) != expected:
            raise ValueError("Candidate summary differs from independently replayed book")
        events += len(book["events"])
        canonical = [{k: v for k, v in e.items() if k != "variant"} for e in book["events"]]
        signatures.add(hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).digest())
        first_board = next((e["board"] for e in book["events"] if e["type"] == "reveal"), None)
        if first_board:
            boards_seen.add(hashlib.sha256(json.dumps(first_board).encode()).digest())
        for event in book["events"]:
            types[event["type"]] += 1
            if event["type"] == "tower":
                tiers[f"{event['ladder']}:{event['level']}:{event['multiplier']}"] += 1
        tags = []
        if not book["payoutMultiplier"]:
            tags.append("zero")
        if result["max_tower_level"] == 4:
            tags.append("tower_top")
        if any(e["type"] == "retrigger" for e in book["events"]):
            tags.append("retrigger")
        if book["payoutMultiplier"] == 2500000:
            tags.append("max_win")
        for tag in tags:
            if tag not in fixtures and fixture_dir:
                name = f"{mode}-{tag}.json"
                write_json(fixture_dir / name, book)
                fixtures[tag] = name
    if events > 10000000 or path.stat().st_size > 4200000000:
        raise ValueError("Mode exceeds documented event or compressed-file limit")
    return {"replayed_rounds": len(rows), "events": events,
            "compressed_bytes": path.stat().st_size,
            "unique_event_sequences_excluding_cosmetic_variant": len(signatures),
            "unique_first_boards": len(boards_seen), "event_types": dict(types),
            "tower_states_observed": dict(tiers), "fixtures": fixtures,
            "book_lookup_candidate_match": True,
            "size_and_event_limits_pass": True,
            "diversity_note": "Binary mode intentionally has only two mathematical outcomes; cosmetic variants are excluded from sequence diversity." if mode == "maxzero" else "Counts measure diversity; they are not a platform quality approval."}


def sdk_comparison(rows, cost):
    from utils.analysis.distribution_functions import get_etl_cvar_p5k_10k_vales
    from utils.rgs_verification import verify_mode_volatility
    distribution = defaultdict(int)
    for _, weight, payout in rows:
        distribution[payout / 100] += weight
    values = get_etl_cvar_p5k_10k_vales(distribution, cost)
    stats = SimpleNamespace(**dict(zip(["prob5k", "prob10k", "etl10k", "etl40b", "cvar"], values)), rtp=.962)
    with warnings.catch_warnings(record=True), contextlib.redirect_stdout(io.StringIO()):
        failures = verify_mode_volatility("graveyard_export", stats)
    return {"metrics": vars(stats), "violations": failures,
            "note": "Unmodified pinned SDK uses different thresholds, inclusive boundaries and ETL normalization. These warnings remain visible separately."}


def export_mode(task):
    source, weighted, output, mode = task
    source, weighted, output = Path(source), Path(weighted), Path(output)
    progress = json.loads((source / "progress.json").read_text())
    weighted_report = json.loads((weighted / "distribution-audit.json").read_text())
    model_hash = fingerprint()[0]
    if not weighted_report["all_modes_complete"] or weighted_report["model_hash"] != model_hash:
        raise ValueError("Incomplete or mismatched weighted checkpoint")
    candidate_rows = read_candidates(source, mode)
    lookup = weighted / f"lookUpTable_{mode}_0.csv"
    if digest(lookup) != weighted_report["modes"][mode]["lookup_sha256"]:
        raise ValueError("Weighted lookup checksum differs")
    with lookup.open(newline="") as handle:
        rows = validate_rows(csv.reader(handle))
    if [r[0] for r in rows] != list(range(len(candidate_rows))):
        raise ValueError("Weighted IDs are incomplete or out of order")
    report = audit(rows, mode)
    if report["metrics"]["rtp"] != F("0.962") or report["checks"]["critical_distribution_failures"]:
        raise ValueError("Weighted numerical gate failed")
    output.mkdir(parents=True, exist_ok=True)
    fixture_dir = output / "fixtures"
    fixture_dir.mkdir(exist_ok=True)
    path = output / f"books_{mode}.jsonl.zst"
    report_path = output / f"audit_{mode}.json"
    # Reuse only the same model, validator and exact weights/books/fixtures.
    identity = {"model_hash": model_hash, "validator_sha256": digest(Path(__file__)),
                "audit_sha256": digest(Path(__file__).with_name("audit.py")),
                "lookup_sha256": digest(lookup)}
    if report_path.exists():
        old = json.loads(report_path.read_text())
        if old.get("identity") == identity and all((output / p).exists() and digest(output / p) == sha for p, sha in old["files_sha256"].items()):
            return old
    batches = sorted((b for b in progress["completed_batches"] if b["mode"] == mode), key=lambda b: b["start"])
    temporary = path.with_suffix(".tmp")
    with temporary.open("wb") as target:
        for b in batches:
            part = source / mode / f"{b['start']:08d}-{b['count']}.jsonl.zst"
            if digest(part) != b["sha256"][part.name]:
                raise ValueError("Candidate event file checksum differs")
            with part.open("rb") as handle:
                shutil.copyfileobj(handle, target)
    os.replace(temporary, path)
    integrity = replay_export(path, rows, candidate_rows, mode, fixture_dir)
    if integrity["events"] != sum(b["events"] for b in batches):
        raise ValueError("Final event count differs from batch checkpoints")
    target_lookup = output / lookup.name
    shutil.copyfile(lookup, target_lookup.with_suffix(".tmp"))
    os.replace(target_lookup.with_suffix(".tmp"), target_lookup)
    report["exact_rtp"] = str(report["metrics"]["rtp"])
    report["identity"], report["integrity"] = identity, integrity
    total, cost = sum(w for _, w, _ in rows), mode_spec(mode)["cost"]
    report["play_statistics"] = {
        "probability_profit_over_mode_cost": F(sum(w for _, w, p in rows if p > cost * 100), total),
        "probability_break_even": F(sum(w for _, w, p in rows if p == cost * 100), total),
        "probability_return_below_mode_cost": F(sum(w for _, w, p in rows if p < cost * 100), total),
        "weighted_feature_probability": F(sum(w * c[2] for (_, w, _), c in zip(rows, candidate_rows)), total),
        "weighted_spins_per_round": F(sum(w * c[3] for (_, w, _), c in zip(rows, candidate_rows)), total),
        "unique_payout_values": len({p for _, w, p in rows if w})}
    report["pinned_sdk_comparison"] = sdk_comparison(rows, cost)
    paths = [path, target_lookup] + [fixture_dir / name for name in integrity["fixtures"].values()]
    report["files_sha256"] = {str(p.relative_to(output)): digest(p) for p in paths}
    report["checks"]["unverified"] = ["frontend_authoritative_playback", "ACP_statistics_parity", "viable_bet_template", "Stake_quality_review"]
    report["publish_ready"] = False
    write_json(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("weights", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    modes = contract()["modes"]
    results = {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(export_mode, (str(args.candidates), str(args.weights), str(args.output), m["id"])) for m in modes]
        for future in as_completed(jobs):
            report = future.result()
            mode = report["metrics"]["mode"]
            results[mode] = report
            write_json(args.output / "export-progress.json", {"complete": len(results) == len(modes), "modes": results, "publish_ready": False})
            print(f"{mode}: final file independently replayed; {report['integrity']['events']} events; exact RTP {report['exact_rtp']}", flush=True)
    rtps = [F(r["exact_rtp"]) for r in results.values()]
    if max(rtps) - min(rtps) > F("0.005"):
        raise ValueError("Cross-mode RTP spread failed")
    write_json(args.output / "index.json", {"modes": [{"name": m["id"], "cost": m["cost"], "events": f"books_{m['id']}.jsonl.zst", "weights": f"lookUpTable_{m['id']}_0.csv"} for m in modes]})
    write_json(args.output / "frontend-contract.json", {"contract": contract(), "rules": RULES, "rules_hash": RULES_HASH, "live_frontend_adapter_verified": False})
    write_json(args.output / "verification.json", {"model_hash": fingerprint()[0], "exact_cross_mode_rtp_spread": str(max(rtps) - min(rtps)),
               "modes": {m["id"]: results[m["id"]] for m in modes}, "complete": True, "publish_ready": False})
    files = sorted(p for p in args.output.rglob("*") if p.is_file() and p.name != "checksums.json")
    write_json(args.output / "checksums.json", {str(p.relative_to(args.output)): digest(p) for p in files})
    print(f"Verified export: {args.output}", flush=True)


if __name__ == "__main__":
    main()
