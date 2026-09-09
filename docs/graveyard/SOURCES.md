# Sources and units

Checked 2026-09-09. Primary sources:

- [Current math verification](https://stake-engine.com/docs/approval-guidelines/math-verification): critical requirements and separate risk tiers; inspect live documentation when resuming.
- [Quality rankings](https://stake-engine.com/docs/approval-guidelines/game-quality-rankings): the final rating includes design, execution and gameplay, not just RTP.
- [Official SDK verifier](https://github.com/StakeEngine/math-sdk/blob/307e6812b38489e212f835001f21e9f7d4c18a4d/utils/rgs_verification.py) and [distribution formulas](https://github.com/StakeEngine/math-sdk/blob/307e6812b38489e212f835001f21e9f7d4c18a4d/utils/analysis/distribution_functions.py). Both files match this fork byte-for-byte.
- [Published frontend configuration](https://github.com/zackfrasercross-maker/graveyard-shift-frontend/blob/8362f2fd1dcc6e90b7fd7c58e507de5cb61e48f9/apps/graveyard-shift/src/game/config.ts) and sibling `art.ts`: authoritative product contract, with unresolved math values.

Current critical limits include RTP 90–96.7%, cross-mode difference 0.5 percentage points, a cheapest 1× base mode, base standard deviation ≥0.6, cost ≤2,000×, prize ≤500,000× and non-zero probability ≥1/50. Outcome diversity and viable bet templates also require review.

SDK warnings differ from the live page: probability scaling, ETL normalization, CVaR thresholds, and a 0.05 cross-mode comparison. Preserve the SDK; report both profiles explicitly. Use 0.005 for the documented cross-mode fraction, and a stricter internal target tolerance of 0.000001.

RTP = expected payout in base bets / mode cost. CSV payoutMultiplier uses 100 units per base bet; do not confuse this with wallet monetary units. The production contract has not yet been connected to an RGS adapter.

No popularity ranking or competitor probability distribution was recovered. High volatility is the user's design intent, not evidence that an unbuilt model matches a trending title.
