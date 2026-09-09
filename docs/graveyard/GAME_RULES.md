# Working game rules and multiplier tower

The user approved 1,024 left-to-right ways with cascades. Four rows on five reels provide up to 4^5 ways. Each regular symbol pays for its longest consecutive run from reel one, starting at three reels. There is no fixed-payline or line-bet division. Winning cells shared by several ways are removed once.

The initial simulation paytable is in `rules.json`, in hundredths of a base bet per way for 3/4/5 reels. Wilds substitute regular symbols on reels 2–5; reel one contains regular symbols and scatters. This explicit placement rule avoids paying ambiguous all-wild prefixes several times. Scatters have no separate cash pay.

## Tower lifecycle

| Context | Ladder, bottom to top | Reset |
|---|---|---|
| Base / Ante | 1, 2, 3, 5, 10 | Every paid spin |
| Boosted | 2, 3, 5, 10, 25 | Every paid spin |
| Overtime (10 free spins) | 1, 2, 3, 5, 10 | Every free spin |
| Eternal Overtime (12 free spins) | 1, 2, 3, 5, 10 | Feature entry; carry between free spins |
| Secret Shift (12 free spins) | 2, 3, 5, 10, 25 | Feature entry; carry between free spins |

Every cascade pays at the currently lit tier. Afterwards advance once, refill, then evaluate again. Hold the top tier. A losing board does not advance the tier. Newly triggered features enter their own ladder at the bottom. Round completion explicitly restores the originating paid mode's bottom tier (or base after a bought feature).

Use `tower.level` to position the highlight and `tower.multiplier` for the displayed numeral and payout. Do not infer either from the win amount, symbol count, or animation progress. When boosted, the five slabs read 2/3/5/10/25 from bottom to top.

## Feature rules selected for the working model

The largest visible scatter count on any board during a paid spin selects the feature: 3 → Overtime, 4 → Eternal Overtime, 5+ → Secret Shift. Do not accumulate the same scatter across several cascades. After the final paid cascade, trigger at most one feature. Within a feature, 3+ visible scatters award three additional spins once per completed spin, with at most five retriggers per feature. Ante uses a higher scatter generation weight; final lookup weights and resulting feature hit rates must be audited separately.

Every purchased round shares one 25,000× base-bet cap across the paid spin and any feature. Clip only the final award to the remaining cap, then end further spins/cascades. Never multiply the round cap by the buy cost or the tower. Max Win or Zero retains exactly its two advertised payouts.

These complete the working model for tuning; they are not claims of Stake approval. An outcome generated under a forced simulation profile must still replay against these same rules. A safety-limit violation rejects the candidate instead of discarding unpaid wins.

## Frontend event handoff

`reveal` → spin board; `win` → highlight cells and display the award at its supplied multiplier; `tower` → update the corresponding slab and label; `cascade` → remove the supplied cells and refill with the supplied board. `featureStart/freeSpin/retrigger/featureEnd` drive the real counter, and `roundEnd` supplies the total. Amounts are integer hundredths of a base bet, not wallet currency units. The existing renderer can show these states; the live RGS event adapter still needs implementation and visual verification.
