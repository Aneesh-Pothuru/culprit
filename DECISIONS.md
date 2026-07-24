# Decisions

## 2026-07-24 — full descent in v0.1

The brief's Journey 0 and P0 tables require component, checkpoint, and data
verdicts, while its milestone table says v0.1 is component-only. Journey 0 and
the full P0 contract win; all three stages are implemented.

## 2026-07-24 — JSON-syntax YAML

`stack.yaml` and `registry.yaml` are JSON documents, a strict YAML subset.
This keeps the keyless path dependency-free without inventing a YAML parser.

## 2026-07-24 — MCAP boundary

Raw MCAP needs the optional `mcap` packages and message schemas. The P0 core
defines and tests the normalized envelope shared by MCAP and agent traces, but
the binary adapter is deferred and recorded as an unmet launch item.

## 2026-07-24 — evidence and confidence

Component confidence is `counterfactual outcome-flip rate × declared
determinism score`. The demo uses ten seeds and refuses attribution if no
candidate flips the outcome. This transparent formula replaces ungrounded
model confidence.

## 2026-07-24 — cause classes

Tier-1/2 rules emit `DATA_COMPOSITION` only when the changed training slice is
both depleted in the new manifest and overrepresented in the regression set.
Config hash changes produce `TRAINING_CONFIG`; explicit verified label-error
metadata can produce `DATA_QUALITY`; otherwise the verdict is `UNDETERMINED`.

