# Authoritative frontend handoff

The current frontend branch was rechecked at commit 8362f2fd1dcc6e90b7fd7c58e507de5cb61e48f9. Its 5×4 board, render symbols, seven mode aliases/costs, 25,000× cap and both tower ladders match contract.json. No frontend files were changed by this math work. Its probability fields remain null; live integration is not completed or visually verified.

Request the selected mode ID from RGS and consume one returned book in event order. Never generate another random outcome in the client. RGS remains authoritative for wallet settlement. Paid amount = base bet × mode cost. Book payout = base bet × payoutMultiplier / 100, without multiplying by mode cost again.

| Event | Required action |
| --- | --- |
| roundStart | Validate mode, cost and rulesHash; begin one round lifecycle. |
| tower | Apply ladder, level and multiplier together; await animation. |
| reveal | Display the supplied column-major board. |
| win | Highlight supplied cells; show credited award, current multiplier and cumulative total. |
| cascade | Remove supplied cells once and refill with the supplied board, preserving survivor order. |
| spinEnd | End this spin's cascades; add no extra tower advance. |
| featureTrigger / featureStart | Present the named feature and initialize its counter. The next tower event supplies its ladder. |
| freeSpin | Display number and remaining; remaining excludes the spin starting now. |
| retrigger | Apply awarded spins and replace the counter with supplied remaining. |
| cap | Present the round cap. No further board or award follows; spinEnd is omitted on capped spins. |
| featureEnd | Finish with played count and total, including early capped finishes. |
| binaryResult | Run the dedicated Max Win or Zero result. Variant is cosmetic, never another prize draw or fake near miss. |
| roundEnd | Reconcile the authoritative total and restore controls when settlement allows. |

Math cells are [reel, row] pairs. Map them to the current renderer's { reel, row } Cell objects. The render symbol is caretakerSymbol; caretaker is its configuration alias. Preserve the existing asset filenames.

## Multiplier tower

Level 0 is the bottom slab; level 4 is the top. For a DOM array ordered top-to-bottom, highlight index is 4 - event.level. For a bottom-to-top array, use event.level. Multipliers are not array indexes.

| Level, bottom upward | Base | Boosted |
| --- | ---: | ---: |
| 0 | ×1 | ×2 |
| 1 | ×2 | ×3 |
| 2 | ×3 | ×5 |
| 3 | ×5 | ×10 |
| 4 | ×10 | ×25 |

Replace the dynamic numeral stack with the selected ladder. Do not overlay duplicate base labels over boosted labels. Reference artwork determines physical slab placement; events determine the active slab. Math tests validate tiers and awards, not pixels.

A win pays at the currently lit tier; cascade_advance then advances once before the next board is evaluated. Clamp at the top. Losing boards never advance. Base/Ante/Boosted reset each paid spin. Overtime resets each free spin. Eternal Overtime and Secret Shift carry their tier through the feature. Each new feature begins at its own bottom tier. round_restore restores Boosted after a Boosted paid round; bought features restore Base. Do not retroactively apply a new tier to the preceding win.

## Remaining frontend acceptance

Replay the exported fixtures for zero, top-tier cascades, retriggers, capped rounds and both binary results on desktop and portrait. Compare displayed awards, counters and tier states to the event sequence; then check physical slab alignment against the reference. Test normal speed, turbo, skipped animation and reduced motion without changing outcomes/order. Reconnect must not credit events twice. Stopping autoplay prevents the next purchase; it does not discard the current outcome.

These are integration acceptance checks still to do, not completed UI tests. Stake must assess viable bet templates and overall quality; the offline math audit cannot award three stars.
