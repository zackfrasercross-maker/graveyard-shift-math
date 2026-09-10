"""Package only verified, tested final math files in the Stake upload layout."""
import argparse
import csv
import hashlib
import json
import os
from fractions import Fraction as F
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import numpy as np

from games.graveyard_shift.audit import audit, contract, mode_spec, validate_rows
from games.graveyard_shift.simulate import digest, fingerprint
from games.graveyard_shift.export import write_json


def package(export, trials, output):
    verification = json.loads((export / "verification.json").read_text())
    sampled = json.loads((trials / "final-test.json").read_text())
    expected_modes = [m["id"] for m in contract()["modes"]]
    if not verification["complete"] or verification["model_hash"] != fingerprint()[0]:
        raise ValueError("Event verification is incomplete or model changed")
    if not sampled["complete"] or not sampled["all_sampling_tests_pass"]:
        raise ValueError("Final sampling diagnostics have not passed")
    if set(sampled["modes"]) != set(expected_modes) or sampled["completed_trials"] != sum(r["trials"] for r in sampled["modes"].values()):
        raise ValueError("Final sampling mode/count mismatch")
    if any(r["trials"] < 10000000 for r in sampled["modes"].values()):
        raise ValueError("At least 10 million test rounds per mode required")
    checksums = json.loads((export / "checksums.json").read_text())
    for name, sha in checksums.items():
        if Path(name).is_absolute() or ".." in Path(name).parts or digest(export / name) != sha:
            raise ValueError(f"Export checksum/path mismatch: {name}")
    expected_index = {"modes": [{"name": m["id"], "cost": m["cost"],
                     "events": f"books_{m['id']}.jsonl.zst", "weights": f"lookUpTable_{m['id']}_0.csv"} for m in contract()["modes"]]}
    if json.loads((export / "index.json").read_text()) != expected_index:
        raise ValueError("Index does not match the current game's seven modes")
    names = ["index.json"]
    for mode in expected_modes:
        r = sampled["modes"][mode]
        if r["identity"]["model_hash"] != fingerprint()[0] or not r["all_sampling_tests_pass"]:
            raise ValueError("Sampling used a different model or failed diagnostics")
        if r["identity"]["test_code_sha256"] != digest(Path(__file__).with_name("final_trials.py")):
            raise ValueError("Final trial code changed after the recorded run")
        count_path = Path(r["counts_path"])
        if count_path.is_absolute() or ".." in count_path.parts or digest(trials / count_path) != r["counts_sha256"]:
            raise ValueError("Final sampled counts checksum/path mismatch")
        lookup_name, book_name = f"lookUpTable_{mode}_0.csv", f"books_{mode}.jsonl.zst"
        if digest(export / lookup_name) != r["identity"]["lookup_sha256"] or digest(export / book_name) != r["identity"]["book_sha256"]:
            raise ValueError("Files differ from those used for the final trials")
        with (export / lookup_name).open(newline="") as handle:
            rows = validate_rows(csv.reader(handle))
        with np.load(trials / count_path, allow_pickle=False) as data:
            counts = data["counts"]
        if counts.dtype != np.uint64 or counts.shape != (len(rows),) or sum(map(int, counts)) != r["trials"]:
            raise ValueError("Final trial count vector is invalid")
        observed = F(sum(int(n) * row[2] for n, row in zip(counts, rows)), r["trials"] * 100 * mode_spec(mode)["cost"])
        if str(observed) != r["observed_rtp_exact"]:
            raise ValueError("Observed RTP does not match saved trial counts")
        numerical = audit(rows, mode)
        integrity = verification["modes"][mode]["integrity"]
        if numerical["metrics"]["rtp"] != F(481, 500) or numerical["checks"]["critical_distribution_failures"]:
            raise ValueError("Final numerical gate failed")
        if integrity["replayed_rounds"] != len(rows) or not integrity["book_lookup_candidate_match"] or not integrity["size_and_event_limits_pass"]:
            raise ValueError("Final book integrity gate failed")
        names.extend([book_name, lookup_name])
    if len(set(names)) != 15:
        raise ValueError("Expected exactly one index plus seven book/lookup pairs")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    with ZipFile(temporary, "w", allowZip64=True) as archive:
        for name in names:
            archive.write(export / name, name, compress_type=ZIP_STORED if name.endswith(".zst") else ZIP_DEFLATED, compresslevel=None if name.endswith(".zst") else 9)
    with ZipFile(temporary) as archive:
        if archive.namelist() != names:
            raise ValueError("ZIP member layout differs")
        # Read all archived bytes, validating CRC and exact source SHA256.
        for name in names:
            h = hashlib.sha256()
            with archive.open(name) as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != digest(export / name):
                raise ValueError(f"ZIP bytes differ from tested export: {name}")
    os.replace(temporary, output)
    result = {"archive": output.name, "archive_sha256": digest(output), "archive_bytes": output.stat().st_size,
              "members": {n: digest(export / n) for n in names}, "math_upload_schema_verified": True,
              "offline_math_validation_passed": True, "tested_round_selections": sampled["completed_trials"],
              "model_hash": fingerprint()[0], "stake_approval": False, "frontend_live_integration_verified": False,
              "risk_classes": {m: list(verification["modes"][m]["checks"]["three_star_risk_classes"]) for m in expected_modes}}
    write_json(output.with_suffix(".manifest.json"), result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("trials", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.export, args.trials, args.output), indent=2))
