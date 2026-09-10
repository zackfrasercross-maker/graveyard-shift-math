# Math delivery — 2026-09-10

Offline math validation and ZIP integrity have passed. Platform approval and live frontend integration are separate remaining steps.

| File | Bytes | SHA256 |
| --- | ---: | --- |
| Graveyard_Shift_Stake_Math_Upload_v1.zip | 434499693 | ba77c00e001c0ee6179bf4c35a9669b75ba1b28fdaf71fb2a70795536ed68a2e |
| Graveyard_Shift_Math_Validation_v1.zip | 975708 | 3827420a983a70bee5bf9afe3ceaa425d0589e859ea31ccebffd8458c0da04ca |

The upload ZIP contains exactly index.json and seven compressed book/lookup pairs at its root. Extract and import those 15 files together in ACP Math files. The separate validation ZIP is for review and includes the test report, verification results, per-book selection counts, frontend contract, replay fixtures and checksums.

## Evidence

- 39 regression tests passed.
- 700,000 event books independently replayed; 31,357,437 events across the seven files.
- Every book ID/payout matched the final lookup and candidate summary.
- Exactly 96.2% theoretical RTP per mode; theoretical cross-mode spread zero.
- 10,000,000 final weighted selections per mode; 70,000,000 total, all fixed-seed statistical diagnostics passed.
- Same results reproduced after runtime recovery, without changing weights, rules or seed.
- ZIP CRCs and SHA256 of every archived member match the exact tested files.

Base standard deviation is 35× the base bet. Mode costs, symbols, 5×4 layout and both tower ladders match frontend commit 8362f2fd1dcc6e90b7fd7c58e507de5cb61e48f9. Tower progression, clamp/reset/carry behavior and capped-round termination are verified in math events. Visual placement and live playback still require frontend integration.

Six non-binary modes pass the implemented current distribution-risk profile. Max Win or Zero retains its two tail-risk flags. Unmodified SDK warnings are preserved separately in verification.json. ACP statistics parity, viable bet templates, overall quality ranking and release approval have not been completed. This is a tested math submission package, not a claim that the overall game has received three stars.
