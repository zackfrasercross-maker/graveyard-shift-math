import copy
import json
import unittest
from games.graveyard_shift.engine import CAP, RULES, Source, Tower, evaluate, generate
from games.graveyard_shift.replay import reference_ways, verify


class EngineTests(unittest.TestCase):
    def test_tower_ladders_and_clamping(self):
        for name, expected in [("base", [1, 2, 3, 5, 10, 10]), ("boosted", [2, 3, 5, 10, 25, 25])]:
            tower = Tower(name)
            observed = []
            for _ in range(6):
                observed.append(tower.multiplier)
                tower.advance()
            self.assertEqual(observed, expected)

    def test_1024_ways_maximum_without_line_bet_division(self):
        board = [["caretakerSymbol"] * 4 for _ in range(5)]
        wins, cells = evaluate(board)
        self.assertEqual(wins[0]["ways"], 1024)
        self.assertEqual(wins[0]["amount"], 1024 * 500)
        self.assertEqual(len(cells), 20)
        self.assertEqual(evaluate(board), reference_ways(board))

    def test_every_mode_independently_replays_and_restores_tower(self):
        for mode in ["base", "ante", "boosted", "bonus", "super", "hidden", "maxzero"]:
            for profile in ["dry", "normal", "rich", "cap"]:
                with self.subTest(mode=mode, profile=profile):
                    book = generate(mode, 31, profile=profile)
                    verify(json.loads(json.dumps(book)), mode)
                    self.assertEqual(book["events"][-2]["reason"], "round_restore")
                    self.assertEqual(book["events"][-2]["level"], 0)

    def test_paid_scatter_triggers_are_real_boards(self):
        for feature in ["bonus", "super", "hidden"]:
            book = generate("base", 400, profile="dry", force_feature=feature)
            self.assertIn(feature, verify(book, "base")["features"])

    def test_persistent_bonus_tower_does_not_reset_between_spins(self):
        for mode in ["super", "hidden"]:
            book = generate(mode, 14)
            starts = [e["level"] for e in book["events"] if e["type"] == "tower" and e["reason"] == "spin_start"]
            self.assertEqual(starts, sorted(starts))
            verify(book, mode)

    def test_standard_free_spins_reset_each_spin(self):
        book = generate("bonus", 14)
        starts = [e["level"] for e in book["events"] if e["type"] == "tower" and e["reason"] == "spin_start"]
        self.assertEqual(set(starts), {0})

    def test_settlement_cap_stops_further_wins(self):
        book = generate("hidden", 3, profile="cap")
        self.assertEqual(book["payoutMultiplier"], CAP)
        cap_index = next(i for i, e in enumerate(book["events"]) if e["type"] == "cap")
        self.assertFalse(any(e["type"] in ("win", "reveal", "cascade") for e in book["events"][cap_index + 1:]))
        verify(book, "hidden")

    def test_tampered_tower_rejected(self):
        book = generate("boosted", 3, profile="rich")
        next(e for e in book["events"] if e["type"] == "tower")["multiplier"] = 1
        with self.assertRaises(ValueError):
            verify(book, "boosted")

    def test_tampered_payout_rejected(self):
        book = generate("super", 4)
        book["payoutMultiplier"] += 10
        with self.assertRaises(ValueError):
            verify(book, "super")

    def test_missing_tower_step_rejected(self):
        book = generate("base", 3, profile="cap")
        index = next(i for i, e in enumerate(book["events"]) if e["type"] == "tower" and e["reason"] == "cascade_advance")
        book["events"].pop(index)
        for i, event in enumerate(book["events"]):
            event["index"] = i
        with self.assertRaises(ValueError):
            verify(book, "base")

    def test_seed_reproducibility(self):
        self.assertEqual(generate("hidden", 19), generate("hidden", 19))
        self.assertNotEqual(generate("hidden", 19), generate("hidden", 20))


if __name__ == "__main__":
    unittest.main()
