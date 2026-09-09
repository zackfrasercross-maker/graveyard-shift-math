import csv
import json
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

import zstandard as zstd

from games.graveyard_shift.engine import generate
from games.graveyard_shift.export import books, replay_export
from games.graveyard_shift.optimize import TOTAL_WEIGHT, integer_weights, read_candidates
from games.graveyard_shift.replay import verify
from games.graveyard_shift.simulate import batch, digest, fingerprint


class PipelineTests(unittest.TestCase):
    def test_binary_integer_weights_preserve_exact_cost_adjusted_rtp(self):
        weights = integer_weights([.96152, .03848], [[0, 2], [1, 3]], [0, 2500000, 0, 2500000], 1000)
        self.assertEqual(sum(weights), TOTAL_WEIGHT)
        self.assertEqual(F((weights[1] + weights[3]) * 2500000, TOTAL_WEIGHT * 100 * 1000), F(481, 500))

    def test_exact_rounding_repair_and_invalid_partition(self):
        weights = integer_weights([.5020000000000001, .1899999999999999, .308], [[0], [1], [2]], [0, 20, 300], 1)
        self.assertEqual(F(sum(w * p for w, p in zip(weights, [0, 20, 300])), TOTAL_WEIGHT * 100), F(481, 500))
        with self.assertRaisesRegex(ValueError, "cannot express"):
            integer_weights([.5, .2, .3], [[0], [1], [2]], [0, 30, 300], 1)
        with self.assertRaises(ValueError):
            integer_weights([.5, .5], [[0], [0]], [0, 100], 1)

    def test_batch_resume_checksums_and_empty_csv_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = (tmp, "base", 0, 8, 20260909, fingerprint()[0])
            first = batch(task)
            self.assertEqual(first["replayed_rounds"], 8)
            self.assertTrue(batch(task)["resumed"])
            root = Path(tmp)
            path = root / "base/00000000-8.csv"
            with path.open(newline="") as handle:
                self.assertEqual(len(list(csv.reader(handle))), 8)
            # Even a manifest claiming an empty CSV's checksum cannot pass IDs.
            path.write_text("")
            first["sha256"][path.name] = digest(path)
            (root / "progress.json").write_text(json.dumps({"complete": True, "model_hash": fingerprint()[0], "count_per_mode": 8, "completed_batches": [first]}))
            with self.assertRaisesRegex(ValueError, "incomplete or overlapping"):
                read_candidates(root, "base")
            with self.assertRaisesRegex(ValueError, "Checkpoint mismatch"):
                batch(task)

    def test_multiframe_books_match_sdk_and_replay_tower(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "books_boosted.jsonl.zst"
            records = [generate("boosted", i, profile="rich") for i in range(3)]
            path.write_bytes(b"".join(zstd.ZstdCompressor().compress((json.dumps(b) + "\n").encode()) for b in records))
            rows = [(b["id"], 1, b["payoutMultiplier"]) for b in records]
            candidates = []
            for b in records:
                r = verify(b, "boosted")
                candidates.append((b["id"], b["payoutMultiplier"], int(bool(r["features"])), r["spins"], r["cascade_wins"], r["max_tower_level"]))
            result = replay_export(path, rows, candidates, "boosted")
            self.assertEqual(result["replayed_rounds"], 3)
            self.assertEqual(len(list(books(path))), 3)
            from utils.rgs_verification import verify_books_and_payout_mults
            payouts, events = verify_books_and_payout_mults(str(path))
            self.assertEqual(payouts, [r[2] for r in rows])
            self.assertEqual(events, result["events"])
            with self.assertRaisesRegex(ValueError, "lengths differ"):
                replay_export(path, rows[:-1], candidates, "boosted")
            bad = list(candidates)
            bad[0] = (*bad[0][:5], 99)
            with self.assertRaisesRegex(ValueError, "summary differs"):
                replay_export(path, rows, bad, "boosted")


if __name__ == "__main__":
    unittest.main()
