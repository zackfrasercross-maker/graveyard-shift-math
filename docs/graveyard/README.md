# Graveyard math workbench

This branch contains a contract, exact distribution auditor, regression tests and an analytical feasibility report. It does **not** contain a finished slot model, certified RTP for seven modes, event books, or a Stake-ready submission. Resume from [WORK_CHECKPOINT.md](WORK_CHECKPOINT.md).

## Run

From the repository root (Python):

```sh
python -m unittest games.graveyard_shift.test_audit -v
python -m games.graveyard_shift.audit --maxzero-feasibility
python -m games.graveyard_shift.checkpoint
```

The first two commands use the standard library. The checkpoint command additionally uses the repository's SDK dependencies to compare its actual verifier. It saves `maxzero-feasibility.json`.

Later, audit a real weighted lookup table:

```sh
python -m games.graveyard_shift.audit --mode base --lut path/to/lookUpTable_base_0.csv
```

Input is headerless `id,weight,payoutMultiplier`. Non-integers, invalid weights, duplicate IDs, above-cap prizes and invalid Max Win or Zero prizes are rejected. A successful numerical audit is not an event-book validation. Cross-mode analysis is available as `suite_report` and requires all seven modes.

## What the numbers mean

For the locked binary feature, 481 winning weight units out of 12,500 gives exactly 96.2% RTP at 1,000× cost and a 25,000× base-bet prize. Those are two payout classes, **not** a production simulation population. This mode cannot be tuned by adding smaller prizes without changing its advertised identity.

The other mode means required by the RTP target are 0.962×, 2.886×, 9.62×, 96.2×, 288.6× and 481× base bet, respectively. These are target means, not measured game returns. Many incompatible distributions can share these means; neither RTP nor a volatility label defines the actual game rules.

## Risk interpretation

The current-profile analytical result exceeds the tail-probability and tail-liability classes. These are non-critical risk checks; final exposure/template consequences depend on the whole game. The SDK separately reports its older thresholds and normalization. The auditor never suppresses or edits those warnings.

Current ETL is implemented as `E[payout × indicator] / mode_cost`, using strict threshold comparisons. CVaR uses exactly the top 0.1% probability, splitting a discrete boundary atom. Confirm these conventions against ACP statistics during actual submission; they differ from the SDK's inclusive-boundary CVaR and ETL implementation. No platform-parity certification is claimed.

## Still required

Approved winning and bonus rules; a deterministic seeded game generator with genuine cascade/feature events; independent payout replay; weighted optimization of complete rounds; 100k–1m varied simulations per slot mode; event/lookup integrity; risk and diversity reports; and frontend/RGS replay verification. Forced simulation quotas must never be mistaken for final sampling probabilities. Do not use the frontend's QA fixtures as production outcomes.
