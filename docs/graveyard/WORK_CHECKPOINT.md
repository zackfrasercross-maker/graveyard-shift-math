# Graveyard math checkpoint

Branch: `codex/graveyard-math-foundation`. Start here after a reset.

## Confirmed state

- Math base: `e37dd1f5993db231f72070a0f0bf991ff4f5767a`. Both original branches held SDK examples only.
- Latest reviewed frontend: `8362f2fd1dcc6e90b7fd7c58e507de5cb61e48f9`. Do not fall back to an older visual version.
- User now authorizes work in this separate math repository; the frontend is not being changed.
- `games/graveyard_shift/contract.json` records the seven exact mode aliases/costs, symbols, grid, cap and ladders. Target RTP is 0.962 of the actual mode cost, not of the base bet for every mode.
- No Graveyard paytable, winning geometry, free-spin or retrigger rules have been confirmed. Earlier Buzzin' Riches rules are a different game and must not silently be imported.
- No retrieved evidence establishes previous Stake approval of Graveyard math. No game generator or publish files exist yet.

## Current work

1. Save this contract and source audit as a small remote checkpoint.
2. Implement exact weighted RTP/risk analysis, comparing current published guidance with the pinned SDK.
3. Add analytical Max Win or Zero feasibility (not fabricated reel outcomes), tests, and a saved report.
4. Resolve gameplay rules before generating, optimizing and validating actual event books.

## Persistence

Make small commits after useful verified milestones, with the next step recorded here. Push only this dedicated work branch; do not merge or publish to Stake without that task being requested. Tests passing is not a star award or a full game certification.

## Open design decision

Winning geometry remains unanswered: left-to-right ways, fixed lines, count-anywhere or connected clusters. The frontend's three matching lanterns are explicitly visual QA fixtures, not an approved winning rule.
