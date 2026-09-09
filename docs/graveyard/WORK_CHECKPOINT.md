# Graveyard math checkpoint

Branch: `codex/graveyard-math-foundation`. Start here after a reset.

## Confirmed state

- Math base: `e37dd1f5993db231f72070a0f0bf991ff4f5767a`. Both original branches held SDK examples only.
- Latest reviewed frontend: `8362f2fd1dcc6e90b7fd7c58e507de5cb61e48f9`. Do not fall back to an older visual version.
- User now authorizes work in this separate math repository; the frontend is not being changed.
- `games/graveyard_shift/contract.json` records the seven exact mode aliases/costs, symbols, grid, cap and ladders. Target RTP is 0.962 of the actual mode cost, not of the base bet for every mode.
- No Graveyard paytable, winning geometry, free-spin or retrigger rules have been confirmed. Earlier Buzzin' Riches rules are a different game and must not silently be imported.
- No retrieved evidence establishes previous Stake approval of Graveyard math. No game generator or publish files exist yet.

## Saved milestones

- Remote checkpoint `ad4d092b203fb04a6c4ec0b8fcdce9173750d9c3`: frontend contract and source audit.
- Exact auditor and regression fixtures added. `python -m games.graveyard_shift.checkpoint` reproduces the next checkpoint report.
- Max Win or Zero: exact analytical hit probability 481/12500 at 96.2% RTP; current-profile risk classes exceeded are tail probability and tail liability. This is not a critical rejection or an approval result.
- The other six modes are unmeasured. No generated game outcomes exist.

## Next work

1. Resolve winning geometry and the bonus rules. These were left null in the approved frontend.
2. Implement genuine complete-round events using those rules, with independent payout replay.
3. Generate reproducible simulations in resumable batches, checkpointing seeds, IDs, rules hash and completed batches.
4. Optimize final integer selection weights against all modes' 96.2% targets, then evaluate diversity, full event integrity and current risk profiles.
5. Validate frontend playback against exported authoritative events before considering a Stake submission.

## Persistence

Make small commits after useful verified milestones, with the next step recorded here. Push only this dedicated work branch; do not merge or publish to Stake without that task being requested. Tests passing is not a star award or a full game certification.

## Open design decision

Winning geometry remains unanswered: left-to-right ways, fixed lines, count-anywhere or connected clusters. The frontend's three matching lanterns are explicitly visual QA fixtures, not an approved winning rule.
