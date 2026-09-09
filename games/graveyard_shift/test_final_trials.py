import tempfile
import unittest
from pathlib import Path

import numpy as np

from games.graveyard_shift.final_trials import batch_counts, summarize, ticket_indices


class FinalTrialTests(unittest.TestCase):
    def test_uint64_interval_boundaries_above_float_integer_precision(self):
        cdf = np.array([0, 2**53 + 1, 2**53 + 1, 2**53 + 7], dtype=np.uint64)
        tickets = np.array([0, 2**53, 2**53 + 1, 2**53 + 6], dtype=np.uint64)
        self.assertEqual(ticket_indices(cdf, tickets).tolist(), [1, 1, 3, 3])
        with self.assertRaises(ValueError):
            ticket_indices(cdf, tickets.astype(float))
        with self.assertRaises(ValueError):
            ticket_indices(cdf, np.array([cdf[-1]], dtype=np.uint64))

    def test_saved_batch_is_exactly_resumed_and_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            cdf = np.array([0, 10, 10, 20], dtype=np.uint64)
            identity = {"start": 0, "count": 1000, "seed": 99, "mode_index": 0}
            first = batch_counts(folder, identity, cdf)
            self.assertEqual(int(first.sum()), 1000)
            self.assertEqual(first[0], 0)
            self.assertEqual(first[2], 0)
            self.assertTrue(np.array_equal(first, batch_counts(folder, identity, cdf)))
            (folder / "000000000-1000.npz").write_bytes(b"truncated")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                batch_counts(folder, identity, cdf)

    def test_exact_binary_observations_pass_and_wrong_frequency_fails(self):
        rows = [(0, 12019, 0), (1, 481, 2500000)]
        candidates = [(0, 0, 0, 0, 0, 0), (1, 2500000, 0, 0, 0, 0)]
        exact = summarize(rows, np.array([12019, 481], dtype=np.uint64), "maxzero", candidates)
        self.assertEqual(exact["observed_rtp_exact"], "481/500")
        self.assertTrue(exact["all_sampling_tests_pass"])
        wrong = summarize(rows, np.array([11000, 1500], dtype=np.uint64), "maxzero", candidates)
        self.assertFalse(wrong["all_sampling_tests_pass"])
        self.assertIn("global_cap", wrong["failed_frequency_tests"])


if __name__ == "__main__":
    unittest.main()
