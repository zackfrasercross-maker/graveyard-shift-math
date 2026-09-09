# Graveyard math checkpoint

Branch: `codex/graveyard-math-foundation`. Start here after a reset.

## Confirmed state

- Math base: `e37dd1f5993db231f72070a0f0bf991ff4f5767a`. Both original branches held SDK examples only.
- Latest reviewed frontend: `8362f2fd1dcc6e90b7fd7c58e507de5cb61e48f9`. Do not fall back to an older visual version.
- User now authorizes work in this separate math repository; the frontend is not being changed.
- `games/graveyard_shift/contract.json` records the seven exact mode aliases/costs, symbols, grid, cap and ladders. Target RTP is 0.962 of the actual mode cost, not of the base bet for every mode.
- User approved 1,024 left-to-right ways, cascades and the multiplier tower. `GAME_RULES.md` records the complete working rules selected for simulation, including explicit bonus persistence/reset behavior.
- No retrieved evidence establishes previous Stake approval of Graveyard math. A seeded round generator and independent event/payout replay now exist; large simulation exports are next.

## Saved milestones

- Remote checkpoint `ad4d092b203fb04a6c4ec0b8fcdce9173750d9c3`: frontend contract and source audit.
- Exact auditor and regression fixtures added. `python -m games.graveyard_shift.checkpoint` reproduces the next checkpoint report.
- Max Win or Zero: exact analytical hit probability 481/12500 at 96.2% RTP; current-profile risk classes exceeded are tail probability and tail liability. This is not a critical rejection or an approval result.
- Remote audit checkpoint: `09a3d130a36502ed20f432c9291b4e9c80316758`.
- Generator supports all seven modes. The independent path-walking replay checks ways, survivor order, tower transitions, feature counts, and complete-round caps. No large-population RTP result yet.

## Next work

1. Run generation in resumable batches, checkpointing seeds, IDs, rules hash and completed batches. Never reuse batches with a different rules hash.
2. Independently replay every exported round; save proof and source hashes.
3. Measure all seven distributions and tune complete-round weights.
4. Optimize final integer selection weights against all modes' 96.2% targets, then evaluate diversity, full event integrity and current risk profiles.
5. Validate frontend playback against exported authoritative events before considering a Stake submission.

## Persistence

Make small commits after useful verified milestones, with the next step recorded here. Push only this dedicated work branch; do not merge or publish to Stake without that task being requested. Tests passing is not a star award or a full game certification.

## Design status

Winning geometry is resolved. Do not ask for it again. Read `GAME_RULES.md` and `rules.json`; earlier frontend preview fixtures are not production outcomes. Mathematical fit, outcome diversity, current risk profiles and live integration remain to be validated.
