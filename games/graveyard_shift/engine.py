"""Seeded whole-round generator with explicit multiplier-tower events.

All payouts are integers in 1/100 base bet. Sampling profiles are simulation
strata, not the final RGS probabilities; only final lookup weights set RTP.
"""
from __future__ import annotations
import hashlib
import json
import random
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

from games.graveyard_shift.audit import contract, mode_spec

RULES = json.loads(Path(__file__).with_name("rules.json").read_text())
CONTRACT = contract()
SYMBOLS = tuple(CONTRACT["symbols"])
REGULAR = SYMBOLS[:10]
CAP = CONTRACT["max_payout_base_bet"] * 100
RULES_HASH = hashlib.sha256(json.dumps({"rules": RULES, "contract": CONTRACT}, sort_keys=True).encode()).hexdigest()


class GenerationLimit(RuntimeError):
    """Reject the simulation instead of silently discarding unpaid cascades."""


def validate_board(board):
    if len(board) != 5 or any(len(c) != 4 for c in board):
        raise ValueError("Expected a column-major 5x4 board")
    if any(s not in SYMBOLS for col in board for s in col):
        raise ValueError("Unknown frontend symbol")
    if "wild" in board[0]:
        raise ValueError("Regular ways spins do not place wilds on reel one")


def evaluate(board):
    """Count each symbol's longest run by products of matching row counts."""
    wins, cells = [], set()
    for symbol in set(board[0]) - {"scatter", "wild"}:
        positions, ways = [], 1
        for reel, column in enumerate(board):
            matches = [(reel, row) for row, s in enumerate(column) if s == symbol or s == "wild"]
            if not matches:
                break
            ways *= len(matches)
            positions.append(matches)
        count = len(positions)
        if count >= 3:
            matched = [cell for column in positions for cell in column]
            amount = RULES["paytable"][symbol][count - 3] * ways
            wins.append({"symbol": symbol, "reels": count, "ways": ways, "amount": amount})
            cells.update(matched)
    return sorted(wins, key=lambda w: w["symbol"]), sorted(cells)


@dataclass
class Tower:
    ladder: str
    level: int = 0

    @property
    def multiplier(self):
        return CONTRACT["multiplier_ladders"][self.ladder][self.level]

    def advance(self):
        self.level = min(self.level + 1, len(CONTRACT["multiplier_ladders"][self.ladder]) - 1)

    def event(self, reason):
        return {"type": "tower", "ladder": self.ladder, "level": self.level,
                "multiplier": self.multiplier, "reason": reason}


class Source:
    def __init__(self, rng, mode, profile="normal"):
        self.rng, self.mode, self.profile = rng, mode, profile
        weights = list(RULES["base_symbol_weights"])
        if mode == "ante":
            weights[-1] *= RULES["ante_scatter_weight_factor"]
        if profile == "rich":
            weights = [6, 6, 6, 6, 6, 8, 10, 12, 16, 24, 9, 2]
        elif profile == "cap":
            weights = [1] * 9 + [85, 8, 1]
        elif profile == "dry":
            weights[-2:] = [0, 0]
        self.cumulatives = []
        for reel in range(5):
            w = weights.copy()
            if reel == 0:
                w[10] = 0
            total, cumulative = 0, []
            for weight in w:
                total += weight
                cumulative.append(total)
            self.cumulatives.append(cumulative)

    def symbol(self, reel):
        cumulative = self.cumulatives[reel]
        return SYMBOLS[bisect_right(cumulative, self.rng.randrange(cumulative[-1]))]

    def board(self):
        if self.profile == "dry":
            return [[self.rng.choice(REGULAR[:5] if r == 0 else REGULAR[5:] if r == 1 else REGULAR)
                     for _ in range(4)] for r in range(5)]
        return [[self.symbol(r) for _ in range(4)] for r in range(5)]

    def refill(self, board, cells):
        removed = set(cells)
        result = []
        for reel, column in enumerate(board):
            survivors = [s for row, s in enumerate(column) if (reel, row) not in removed]
            result.append([self.symbol(reel) for _ in range(4 - len(survivors))] + survivors)
        return result


def scatter_count(board):
    return sum(s == "scatter" for col in board for s in col)


class Round:
    def __init__(self, mode, source):
        self.mode, self.source, self.total, self.events = mode, source, 0, []

    def emit(self, kind, **data):
        self.events.append({"type": kind, **data})

    def spin(self, phase, index, tower, board=None):
        board = self.source.board() if board is None else board
        self.events.append(tower.event("spin_start"))
        self.emit("reveal", board=board, phase=phase, spin=index)
        highest_scatter = scatter_count(board)
        for _ in range(RULES["safety_max_cascades"]):
            wins, cells = evaluate(board)
            if not wins:
                self.emit("spinEnd", scatters=highest_scatter, total=self.total)
                return highest_scatter
            amount = sum(w["amount"] for w in wins)
            raw = amount * tower.multiplier
            credited = min(raw, CAP - self.total)
            self.total += credited
            self.emit("win", wins=wins, cells=cells, baseAmount=amount, multiplier=tower.multiplier,
                      rawAward=raw, award=credited, total=self.total)
            if self.total == CAP:
                self.emit("cap", total=self.total)
                return highest_scatter
            tower.advance()
            self.events.append(tower.event("cascade_advance"))
            board = self.source.refill(board, cells)
            highest_scatter = max(highest_scatter, scatter_count(board))
            self.emit("cascade", cells=cells, board=board)
        raise GenerationLimit("Cascade safety limit: discard and report this simulation")

    def feature(self, mode):
        feature = RULES["features"][mode]
        left, played, retriggers = feature["spins"], 0, 0
        tower = Tower(feature["ladder"])
        self.emit("featureStart", mode=mode, spins=left)
        while left and self.total < CAP:
            if not feature["carry_tier"]:
                tower.level = 0
            left -= 1
            played += 1
            self.emit("freeSpin", number=played, remaining=left)
            scatters = self.spin(mode, played, tower)
            if self.total == CAP:
                break
            if scatters >= RULES["retrigger"]["minimum_scatters"] and retriggers < RULES["retrigger"]["maximum_awards_per_feature"]:
                left += RULES["retrigger"]["extra_spins"]
                retriggers += 1
                self.emit("retrigger", scatters=scatters, awarded=RULES["retrigger"]["extra_spins"], remaining=left)
        self.emit("featureEnd", mode=mode, played=played, total=self.total, capped=self.total == CAP)


def generate(mode, identifier, seed=20260909, profile="normal", force_feature=None):
    mode_spec(mode)
    seed_bytes = hashlib.sha256(f"{RULES_HASH}:{seed}:{mode}:{identifier}".encode()).digest()
    rng = random.Random(int.from_bytes(seed_bytes[:16], "big"))
    source = Source(rng, mode, profile)
    round_ = Round(mode, source)
    round_.emit("roundStart", mode=mode, cost=mode_spec(mode)["cost"], rulesHash=RULES_HASH)
    if mode == "maxzero":
        # Uniform candidate strata. Exported weights, never this quota, set RTP.
        win = bool(identifier % 2)
        round_.emit("binaryResult", result="max" if win else "zero", award=CAP if win else 0,
                    variant=rng.randrange(1000000))
        round_.total = CAP if win else 0
    elif mode in RULES["features"]:
        round_.feature(mode)
    else:
        board = source.board()
        if force_feature:
            count = {"bonus": 3, "super": 4, "hidden": 5}[force_feature]
            # A real scatter board, not a paid feature outcome pasted into base.
            for col in board:
                for row in range(4):
                    if col[row] == "scatter":
                        col[row] = rng.choice(REGULAR)
            for reel in range(count):
                board[reel][rng.randrange(4)] = "scatter"
        count = round_.spin(mode, 0, Tower(RULES["paid_tower"][mode]), board)
        if count >= 3 and round_.total < CAP:
            feature = RULES["paid_scatter_triggers"][str(min(count, 5))]
            round_.emit("featureTrigger", scatters=count, mode=feature)
            round_.feature(feature)
    # Explicit restore avoids leaving a bought-feature ladder on the base HUD.
    restored = "boosted" if mode == "boosted" else "base"
    round_.events.append(Tower(restored).event("round_restore"))
    round_.emit("roundEnd", total=round_.total)
    for index, event in enumerate(round_.events):
        event["index"] = index
    return {"id": identifier, "events": round_.events, "payoutMultiplier": round_.total}
