"""Restore damaged candidate batches only when original book hashes reproduce."""
import argparse
import csv
import json
import os
import shutil
import tempfile
from pathlib import Path

from games.graveyard_shift.simulate import batch, digest, fingerprint


def repair(root):
    progress = json.loads((root / "progress.json").read_text())
    if progress["model_hash"] != fingerprint()[0]:
        raise ValueError("Recovery requires the exact original model sources")
    repaired = []
    for index, old in enumerate(progress["completed_batches"]):
        stem = f"{old['start']:08d}-{old['count']}"
        folder = root / old["mode"]
        book, rows = folder / f"{stem}.jsonl.zst", folder / f"{stem}.csv"
        valid = all(p.exists() and digest(p) == old["sha256"][p.name] for p in (book, rows))
        if valid:
            with rows.open(newline="") as handle:
                contents = list(csv.reader(handle))
            try:
                valid = all(len(r) == 6 for r in contents) and [int(r[0]) for r in contents] == list(range(old["start"], old["start"] + old["count"]))
            except (ValueError, IndexError):
                valid = False
        if valid:
            continue
        with tempfile.TemporaryDirectory(prefix="graveyard-recovery-") as temporary:
            new = batch((temporary, old["mode"], old["start"], old["count"], old["seed"], old["model_hash"]))
            if new["sha256"][book.name] != old["sha256"][book.name]:
                raise ValueError("Seed did not reproduce original event bytes; refusing replacement")
            for name in [book.name, rows.name, f"{stem}.json"]:
                destination = folder / name
                recovered = destination.with_suffix(".recovered")
                shutil.copyfile(Path(temporary) / old["mode"] / name, recovered)
                os.replace(recovered, destination)
            progress["completed_batches"][index] = new
            note = {"mode": old["mode"], "start": old["start"], "same_seed_book_sha256_verified": True,
                    "reason": "batch checksum or summary row count mismatch"}
            progress.setdefault("recovery_notes", []).append(note)
            temporary_progress = root / "progress.recovered"
            temporary_progress.write_text(json.dumps(progress, indent=2) + "\n")
            os.replace(temporary_progress, root / "progress.json")
            repaired.append(note)
            print(f"Recovered {old['mode']}/{stem}: original event SHA256 matched", flush=True)
    return repaired


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    args = parser.parse_args()
    print(f"Recovered batches: {len(repair(args.candidates))}")
