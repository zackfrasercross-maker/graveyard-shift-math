# Graveyard math workbench

This branch implements the approved 1,024-way cascading game, all seven modes, authoritative multiplier-tower events, independent payout replay, deterministic candidate generation and exact whole-round integer weighting. Resume from WORK_CHECKPOINT.md; GAME_RULES.md defines the working rules.

All seven weighted distributions achieve exactly 481/500 (96.2%) of their actual mode cost. This is theoretical lookup RTP, not a promise about finite play sessions. The 100,000 candidates per mode deliberately oversample different conditions; their unweighted average is not the game's RTP. Selection weights tune valid complete rounds, never replace payouts or events.

## Reproduce

Use Python 3.12 and requirements-graveyard.txt. Run from the repository root:

    python -m pip install -r requirements-graveyard.txt
    python -m unittest discover -s games/graveyard_shift -p 'test_*.py'
    python -m games.graveyard_shift.simulate --output /tmp/graveyard-runs --count 100000 --workers 4
    python -m games.graveyard_shift.optimize /tmp/graveyard-runs/d476a9c7741ee124 --output /tmp/graveyard-weights
    python -m games.graveyard_shift.export /tmp/graveyard-runs/d476a9c7741ee124 /tmp/graveyard-weights --output /tmp/graveyard-verified --workers 4

Use the actual fingerprint directory printed by generation if later source changes alter it. Resume the same commands after interruption. Completed batches and exports are reused only when identities and checksums agree. Optimizer results are saved atomically after each mode.

If restored data is damaged, run the repair module with the candidate directory. It regenerates damaged batches and refuses replacement unless the original compressed event-file SHA256 is reproduced with the original seed.

## Outputs and current status

The exporter produces index.json, seven compressed event books, seven headerless id/weight/payoutMultiplier lookup tables, per-mode integrity/risk reports, frontend contract/rules, replay fixtures and checksums. Final files are independently replayed and joined to lookups: IDs, ways, awards, survivor order, tower transitions, free-spin counts and round caps must agree.

weighting-audit.json is the saved seven-mode numerical result. Final assembled-file verification was interrupted by an execution-environment disconnect: six modes had completed, while Hidden Bonus final replay and the combined export still need confirmation. No completed downloadable data archive is being claimed. Source and reproduction commands are saved on this branch.

Event amounts are hundredths of a base bet, not wallet currency units. Neither buy cost nor tower multiplies the shared 25,000× round cap. maxzero-feasibility.json is an earlier analytical checkpoint, not the final seven-mode result.

## Quality and risk

Base standard deviation is 35 base bets. These measured distributions are not a verified match to a competitor's proprietary math or evidence that the game is trending.

Six modes pass the implemented current distribution-risk profile. Max Win or Zero retains two prizes: zero or 25,000×. At 1,000× cost its exact hit probability is 481/12500 (3.848%). Tail-probability and tail-liability risk classes remain exceeded and require template assessment.

Current-profile ETL is E[payout × indicator] / mode_cost with strict comparisons. CVaR uses exactly the upper 0.1% probability, splitting boundary atoms. The pinned SDK uses different thresholds, inclusive boundaries and ETL normalization. Its warnings are separately recorded rather than suppressed. ACP parity must be confirmed at submission.

Live frontend event playback, visual tower alignment, ACP statistics/templates and Stake's overall quality review remain outstanding. No three-star award, certification or deployment is claimed. See FRONTEND_HANDOFF.md before replacing preview outcomes with authoritative events.
