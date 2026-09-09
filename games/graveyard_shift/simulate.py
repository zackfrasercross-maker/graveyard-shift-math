"""Resumable deterministic candidate books; every round is independently replayed."""
import argparse
import csv
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import zstandard as zstd
from games.graveyard_shift.engine import GenerationLimit, RULES_HASH, generate
from games.graveyard_shift.replay import verify
from games.graveyard_shift.audit import contract


def fingerprint():
    here = Path(__file__).parent
    sources = {name: hashlib.sha256((here / name).read_bytes()).hexdigest() for name in
               ("engine.py", "replay.py", "simulate.py", "rules.json", "contract.json")}
    return hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(), sources


def stratum(mode, identifier):
    slot = identifier % 1000
    if mode == "maxzero":
        return "normal", None
    if mode in ("base", "ante", "boosted"):
        if slot < 200:
            return "dry", None
        if slot < 300:
            return "normal", "bonus" if slot < 280 else "super" if slot < 295 else "hidden"
        if slot < 480:
            return "rich", None
        if slot < 482:
            return "cap", None
        return "normal", None
    if slot < 50:
        return "dry", None
    if slot < 350:
        return "rich", None
    if slot < 360:
        return "cap", None
    return "normal", None


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def batch(task):
    output, mode, start, count, seed, model_hash = task
    folder = Path(output) / mode
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{start:08d}-{count}"
    book_path = folder / f"{stem}.jsonl.zst"
    csv_path = folder / f"{stem}.csv"
    manifest_path = folder / f"{stem}.json"
    expected = {"mode": mode, "start": start, "count": count, "seed": seed, "model_hash": model_hash}
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        if all(old.get(k) == v for k, v in expected.items()) and all(p.exists() and digest(p) == old["sha256"][p.name] for p in (book_path, csv_path)):
            return {**old, "resumed": True}
        raise ValueError(f"Checkpoint mismatch: {manifest_path}")
    # Use distinct suffixes: neither temporary path can alias another output.
    tmp_books = folder / f"{stem}.books.tmp"
    tmp_csv = folder / f"{stem}.rows.tmp"
    event_count, rejected, total_payout, positive = 0, 0, 0, 0
    with tmp_books.open("wb") as raw, zstd.ZstdCompressor(level=6).stream_writer(raw, closefd=False) as writer, tmp_csv.open("w", newline="") as rows:
        csvwriter = csv.writer(rows, lineterminator="\n")
        for identifier in range(start, start + count):
            profile, feature = stratum(mode, identifier)
            for attempt in range(10):
                try:
                    book = generate(mode, identifier, seed=seed + attempt * 1000000007, profile=profile, force_feature=feature)
                    break
                except GenerationLimit:
                    rejected += 1
            else:
                raise RuntimeError(f"Generation failed for {mode}/{identifier}")
            replay = verify(book, mode)
            # Metadata is outside events and cannot affect presentation/payout.
            book["generation"] = {"profile": profile, "forceFeature": feature, "attempt": attempt}
            writer.write((json.dumps(book, separators=(",", ":")) + "\n").encode())
            csvwriter.writerow([identifier, book["payoutMultiplier"], int(bool(replay["features"])), replay["spins"], replay["cascade_wins"], replay["max_tower_level"]])
            event_count += len(book["events"])
            total_payout += book["payoutMultiplier"]
            positive += book["payoutMultiplier"] > 0
    os.replace(tmp_books, book_path)
    os.replace(tmp_csv, csv_path)
    result = {**expected, "events": event_count, "rejected_safety_candidates": rejected,
              "positive_payout_rows": positive, "unweighted_payout_sum_units": total_payout,
              "replayed_rounds": count, "sha256": {p.name: digest(p) for p in (book_path, csv_path)}}
    manifest_temp = folder / f"{stem}.manifest.tmp"
    manifest_temp.write_text(json.dumps(result, indent=2) + "\n")
    os.replace(manifest_temp, manifest_path)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=100000)
    parser.add_argument("--batch", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260909)
    parser.add_argument("--modes", nargs="+", choices=[m["id"] for m in contract()["modes"]], default=[m["id"] for m in contract()["modes"]])
    args = parser.parse_args()
    if min(args.count, args.batch, args.workers) < 1 or len(set(args.modes)) != len(args.modes):
        parser.error("Positive counts/workers and unique modes are required")
    model_hash, sources = fingerprint()
    output = args.output / model_hash[:16]
    output.mkdir(parents=True, exist_ok=True)
    tasks = [(str(output), mode, start, min(args.batch, args.count - start), args.seed, model_hash)
             for mode in args.modes for start in range(0, args.count, args.batch)]
    completed = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(batch, task) for task in tasks]
        for future in as_completed(jobs):
            result = future.result()
            completed.append(result)
            state = {"model_hash": model_hash, "source_sha256": sources, "rules_hash": RULES_HASH,
                     "seed": args.seed, "requested_modes": args.modes, "count_per_mode": args.count,
                     "completed_batches": completed, "complete": len(completed) == len(tasks),
                     "stage": "unweighted-candidates-not-a-published-distribution"}
            temp = output / "progress.tmp"
            temp.write_text(json.dumps(state, indent=2) + "\n")
            os.replace(temp, output / "progress.json")
            print(f"{len(completed)}/{len(tasks)} {result['mode']} ids {result['start']}..{result['start']+result['count']-1} replayed" + (" (resumed)" if result.get("resumed") else ""), flush=True)
    print(f"Candidate checkpoint: {output}", flush=True)


if __name__ == "__main__":
    main()
