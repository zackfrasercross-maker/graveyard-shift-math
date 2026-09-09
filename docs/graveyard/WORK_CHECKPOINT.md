# Graveyard math checkpoint

## Latest saved state — resume here

Updated 2026-09-09 after the execution environment disconnected.

- The approved 1,024-way rules and all seven mode generators are complete in source. Do not restart from an older frontend or ask for winning geometry again.
- Source, simulator, exact optimizer, exporter, tests and seven-mode weighting report are saved in remote commit b081ed48d57e1ff11a813116d4cc392fd4180e31. Subsequent documentation/recovery changes do not change the model fingerprint.
- 36 audit/engine/pipeline tests passed. 700,000 candidates (100,000 per mode) were independently replayed during generation; zero safety-limit candidate rejections.
- Every final lookup has exact RTP 481/500 (96.2%). All six non-binary modes pass the implemented current distribution-risk profile. Maxzero retains tail probability and tail liability risk classes. See weighting-audit.json; do not claim Stake certification.
- Standard deviation per mode cost: base 35; ante 25; boosted 15; bonus 3; super 3.5; hidden 3.5; maxzero 4.808799850274494 approximately. Read the exact recorded float from weighting-audit.json rather than treating this rounded value as a gate.
- Original hidden batch 74000 had an empty summary CSV. Same-seed regeneration reproduced the original compressed-book SHA256 and rebuilt the summary.
- Hidden batch 56000 had a compressed-file checksum mismatch after restoration. repair.py regenerated it and matched the original expected event SHA256 before replacing it. A complete checksum scan found no other damaged batches.
- Final assembled-file replay completed for base (1,611,389 events), ante (2,546,521), boosted (1,609,372), bonus (7,479,076), super (8,859,617), maxzero (400,000). Each had 100,000 ID/payout/summary-matched rounds. Hidden final replay and the combined final archive remain unconfirmed because the execution environment went offline.
- The unmodified SDK independently warns on ETL40 for ante, boosted and bonus; on ETL40/ETL10k for super; and on P10k/ETL10k for maxzero. These are separately reported from the current documented profile because its formulas/units differ. Hidden's SDK result still needs collection.
- Frontend branch remains at 8362f2fd1dcc6e90b7fd7c58e507de5cb61e48f9; config.ts and art.ts blob hashes still match contract.json. Live event integration and visual tower placement are not verified by offline math.

## Exact next actions

1. Reconnect the execution environment. Inspect existing final reports before regenerating anything. The most recent export command was running when connectivity failed; it may have completed.
2. Existing workspace: /workspace/scratch/b527f7704526/graveyard-shift-math.
3. Candidates: /workspace/scratch/b527f7704526/math-runs/d476a9c7741ee124.
4. Weights: /workspace/scratch/b527f7704526/math-weighted-v1.
5. Final export: /workspace/scratch/b527f7704526/graveyard-math-verified-v1. Inspect verification.json, export-progress.json and audit_hidden.json. Re-run the export command only to resume/validate: it reuses already completed files if validator/model/weights/file hashes match.
6. Collect all seven final integrity reports, verify totals and preserve a generated-data archive. No completed archive has been delivered or durably saved yet. The source and seeds can reproduce it if local data is lost.
7. Update this checkpoint and README with observed results. Add the final report/fixture mapping to GitHub in another small commit.
8. Frontend integration remains separate: use FRONTEND_HANDOFF.md, especially array-cell conversion, tier indexing, feature persistence, capped-spin termination, and wallet amount units. Do not claim visual reference alignment from math tests.
9. ACP statistics parity, viable bet template and Stake's full quality review remain release gates. No main-branch merge or deployment is authorized by this checkpoint.

## Recovery instructions

Use requirements-graveyard.txt (Python 3.12; NumPy 2.3.5, SciPy 1.17.0, zstandard 0.25.0). README.md contains complete commands. Generation fingerprint is d476a9c7741ee1245c3f4591b6295a48ee87659dcad0f30f999859c7ea5b733d. The five fingerprinted files are engine.py, replay.py, simulate.py, rules.json and contract.json. Do not edit them and reuse old populations as if nothing changed.

Local and remote commit metadata differ because checkpoints were published through Git data tools; their trees were compared before each successful publication. Preserve local work when reconciling; do not reset a user's checkout. Subsequent doc/recovery checkpoint files were saved directly through GitHub while execution was unavailable.


## Earlier milestone history


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

## Candidate checkpoint (2026-09-09)

- Generator checkpoint saved remotely at `9ad42572be5de7f966228d65d8584dc40ad40922`.
- `simulate.py` now provides deterministic 1,000-round batches, checksums and atomic progress snapshots. Every candidate is independently replayed before writing.
- Run `python -m games.graveyard_shift.simulate --output /tmp/graveyard-runs --count 100000 --workers 4` to reproduce 100,000 candidates per mode, seed 20260909. Generation fingerprint: `d476a9c7741ee1245c3f4591b6295a48ee87659dcad0f30f999859c7ea5b733d`.
- 700,000 candidate rounds generated with no safety-limit rejections. These are deliberately stratified candidates, NOT final selection probabilities or claimed RTP.
- Resume validation detected one empty hidden-mode summary CSV; deterministic regeneration is being checked against the original compressed-book hash before weighting continues.
- 32 audit/engine tests pass, including strict integer events, retrigger cap, tower advancement, per-feature persistence and final restoration.
- Next checkpoint: complete integer weight fitting for all seven modes, then independently validate assembled exports and publish measured reports.

## Integer-weight checkpoint (2026-09-09)

- Simulation/replay source saved remotely at `f56f5382e8098de02f3ecb2b62624acbea8bc722`.
- Hidden batch summary repaired by regenerating the same seed; compressed-book SHA256 matched the original exactly. All seven candidate ID sequences now contain 100,000 complete rows.
- Final integer weights produce exact `481/500` RTP in ALL seven modes; complete-round events/payouts were not edited. `weighting-audit.json` records measurements.
- Standard deviation per mode cost: base 35, ante 25, boosted 15, bonus 3, super 3.5, hidden 3.5, maxzero approximately 4.809. The hidden target was lowered from an infeasible 4 to 3.5 with explicit tail-risk margin. This is not a competitor-math comparison.
- Six modes pass the implemented current distribution-risk profile. Binary maxzero retains tail probability and tail liability risk classes by design; do not hide these or modify the SDK.
- 36 tests pass, including multi-frame compressed-file compatibility with the unmodified SDK, integer rounding feasibility, malformed batch summaries and payout/event joins.
- Run optimizer: `python -m games.graveyard_shift.optimize /tmp/graveyard-runs/d476a9c7741ee124 --output /tmp/graveyard-weights`.
- Run final export: `python -m games.graveyard_shift.export /tmp/graveyard-runs/d476a9c7741ee124 /tmp/graveyard-weights --output /tmp/graveyard-verified --workers 4`. It independently replays final assembled files and resumes only identical validated outputs.
- Final-file replay is currently running. NEXT: collect seven final integrity reports, compare SDK warnings, save a reproducible generated-data archive, document frontend tower/event integration limits.
