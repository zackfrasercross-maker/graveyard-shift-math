"""Independent path-enumerating payout replay and strict tower/event checker.

Does not call the generator's ways evaluator, tower class or spin loop.
"""
from games.graveyard_shift.engine import RULES, CONTRACT, RULES_HASH, SYMBOLS, CAP


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_board(board):
    require(isinstance(board, list) and len(board) == 5, "board reels")
    require(all(isinstance(c, list) and len(c) == 4 for c in board), "board rows")
    require(all(s in SYMBOLS for c in board for s in c), "board symbol")
    require("wild" not in board[0], "wild on reel one")


def reference_ways(board):
    """Walk winning paths; no product-of-counts calculation is reused."""
    amounts, paths, lengths, removed = {}, {}, {}, set()
    def walk(symbol, path):
        reel = len(path)
        children = [] if reel == 5 else [row for row, s in enumerate(board[reel]) if s in (symbol, "wild")]
        if children:
            for row in children:
                walk(symbol, path + [(reel, row)])
        elif reel >= 3:
            amounts[symbol] = amounts.get(symbol, 0) + RULES["paytable"][symbol][reel - 3]
            paths[symbol] = paths.get(symbol, 0) + 1
            lengths[symbol] = reel
            removed.update(path)
    for row, symbol in enumerate(board[0]):
        if symbol not in ("scatter", "wild"):
            walk(symbol, [(0, row)])
    return [{"symbol": s, "reels": lengths[s], "ways": paths[s], "amount": amounts[s]} for s in sorted(amounts)], sorted(removed)


class Replay:
    def __init__(self, book):
        require(type(book.get("id")) is int and book["id"] >= 0, "book id")
        require(type(book.get("payoutMultiplier")) is int, "integer book payout")
        self.book, self.events, self.pos, self.total = book, book["events"], 0, 0
        self.spins, self.wins, self.features, self.maximum_level = 0, 0, [], 0
        for index, event in enumerate(self.events):
            require(type(event.get("index")) is int and event["index"] == index, "event sequence index")

    def take(self, kind, **expected):
        require(self.pos < len(self.events), f"missing {kind}")
        event = self.events[self.pos]
        self.pos += 1
        require(event.get("type") == kind, f"expected {kind}, got {event.get('type')}")
        for key, value in expected.items():
            if type(value) in (int, bool):
                require(type(event.get(key)) is type(value), f"{kind}.{key} integer/boolean type")
            require(event.get(key) == value, f"{kind}.{key} mismatch")
        return event

    def tower(self, ladder, level, reason):
        self.take("tower", ladder=ladder, level=level,
                  multiplier=CONTRACT["multiplier_ladders"][ladder][level], reason=reason)
        self.maximum_level = max(self.maximum_level, level)

    def spin(self, phase, number, ladder, level):
        self.spins += 1
        self.tower(ladder, level, "spin_start")
        event = self.take("reveal", phase=phase, spin=number)
        board = event["board"]
        check_board(board)
        scatters = sum(s == "scatter" for c in board for s in c)
        while True:
            wins, cells = reference_ways(board)
            if not wins:
                self.take("spinEnd", scatters=scatters, total=self.total)
                return level, scatters
            self.wins += 1
            base = sum(w["amount"] for w in wins)
            mult = CONTRACT["multiplier_ladders"][ladder][level]
            award = min(base * mult, CAP - self.total)
            self.total += award
            event = self.take("win", wins=wins, baseAmount=base, multiplier=mult,
                              rawAward=base * mult, award=award, total=self.total)
            require([tuple(c) for c in event["cells"]] == cells, "winning cell union")
            if self.total == CAP:
                self.take("cap", total=CAP)
                return level, scatters
            level = min(level + 1, 4)
            self.tower(ladder, level, "cascade_advance")
            event = self.take("cascade")
            require([tuple(c) for c in event["cells"]] == cells, "removed cell union")
            next_board = event["board"]
            check_board(next_board)
            removed = set(cells)
            for reel, column in enumerate(board):
                survivors = [s for row, s in enumerate(column) if (reel, row) not in removed]
                require(not survivors or next_board[reel][-len(survivors):] == survivors, "cascade survivor order")
            board = next_board
            scatters = max(scatters, sum(s == "scatter" for c in board for s in c))

    def feature(self, mode):
        config = RULES["features"][mode]
        self.features.append(mode)
        remaining, played, awarded, level = config["spins"], 0, 0, 0
        self.take("featureStart", mode=mode, spins=remaining)
        while remaining > 0 and self.total < CAP:
            played += 1
            remaining -= 1
            self.take("freeSpin", number=played, remaining=remaining)
            level, scatters = self.spin(mode, played, config["ladder"], level if config["carry_tier"] else 0)
            if self.total < CAP and scatters >= 3 and awarded < RULES["retrigger"]["maximum_awards_per_feature"]:
                remaining += RULES["retrigger"]["extra_spins"]
                awarded += 1
                self.take("retrigger", scatters=scatters, awarded=RULES["retrigger"]["extra_spins"], remaining=remaining)
        self.take("featureEnd", mode=mode, played=played, total=self.total, capped=self.total == CAP)

    def run(self, expected_mode):
        mode = expected_mode
        spec = next(m for m in CONTRACT["modes"] if m["id"] == mode)
        self.take("roundStart", mode=mode, cost=spec["cost"], rulesHash=RULES_HASH)
        if mode == "maxzero":
            event = self.take("binaryResult")
            require(event["result"] in ("max", "zero"), "binary identity")
            self.total = CAP if event["result"] == "max" else 0
            require(event["award"] == self.total, "binary award")
        elif mode in RULES["features"]:
            self.feature(mode)
        else:
            _, scatters = self.spin(mode, 0, RULES["paid_tower"][mode], 0)
            if scatters >= 3 and self.total < CAP:
                feature = RULES["paid_scatter_triggers"][str(min(scatters, 5))]
                self.take("featureTrigger", scatters=scatters, mode=feature)
                self.feature(feature)
        self.tower("boosted" if mode == "boosted" else "base", 0, "round_restore")
        self.take("roundEnd", total=self.total)
        require(self.pos == len(self.events), "extra events after settlement")
        require(self.book["payoutMultiplier"] == self.total, "book payout differs from replay")
        return {"spins": self.spins, "cascade_wins": self.wins, "features": self.features,
                "max_tower_level": self.maximum_level, "payout": self.total}


def verify(book, mode):
    return Replay(book).run(mode)
