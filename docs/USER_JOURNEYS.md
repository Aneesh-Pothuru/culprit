# CULPRIT user journeys

The product has two valid endings:

- **Attributed** — at least one oracle substitution reproducibly flips the task
  outcome. The investigation may descend to checkpoint and data evidence.
- **Unattributed** — no available substitution flips the outcome, or the
  required oracle is absent. The product stops, explains why, and exports the
  unresolved evidence without inventing a culprit.

The interactive site demonstrates both endings with deterministic embedded
data. Only `tabletop-low-light-v1` mirrors the shipped Python fixture; the
oracle-limited case is explicitly marked as an illustrative abstention path.

## 1. Robotics engineer — from failed run to decisive moment

**Trigger:** a pick-and-place run closes on air.

1. Open the investigation and select the low-light tabletop incident.
2. Replay the 12 frames or scrub the timecode spine.
3. Watch the scene, component telemetry, and raw payload remain synchronized.
4. Jump to the single anomaly marker at frame 7 / 00:00:00.700.
5. Compare the detector output (`false`) with its available reference
   (`true`); see planner and controller behave consistently with the bad input.
6. Toggle the detector oracle and run the counterfactual replay.
7. Observe the task outcome flip across 10/10 deterministic seeds.

**Attributed ending:** `perception.detector` is evidenced; downstream actors are
ruled out. The engineer exports a finding containing the selected time,
intervention, outcome, and evidence hashes.

**Unattributed ending:** in the oracle-limited case, no intervention can be
validated. The workbench states `UNATTRIBUTED`, lists the missing reference, and
does not enable checkpoint or data conclusions.

## 2. Incident responder — establish an evidence-preserving narrative

**Trigger:** an incident arrives with a normalized trace and decoded MCAP-style
envelope.

1. Read the case ledger: source type, fixture/synthetic status, determinism
   score, and evidence availability.
2. Reconstruct the event sequence without mutating the source evidence.
3. Use play/pause/step, anomaly markers, and the event log to identify the
   transition from nominal behavior to failure.
4. Inspect payload and reference side by side at the selected frame.
5. Run one-component-at-a-time interventions; the interface prevents a
   multi-variable intervention from masquerading as a clean attribution.
6. Copy the plain-language finding into an incident channel or download the
   JSON evidence packet.

**Attributed ending:** the incident record names the component, decisive frame,
tested substitution, flip rate, and ruled-out actors.

**Unattributed ending:** the record names no component and preserves the failed
hypotheses and missing evidence for escalation.

## 3. Model owner — locate the regressing checkpoint

**Trigger:** the detector owner accepts component attribution and asks when the
behavior changed.

1. Review the component outcome-flip graph rather than relying on the initial
   deviation rank.
2. Start checkpoint bisection only after the attribution gate passes.
3. Follow the deterministic search: evaluate the midpoint, narrow the boundary,
   and verify `ckpt-3` passes while `ckpt-4` fails.
4. Inspect the 38-case regression set and eight daylight controls.
5. Confirm that rollback to `ckpt-3` restores the task outcome.
6. Export the boundary and probe-set summary for release triage.

**Attributed ending:** `ckpt-3 → ckpt-4` is recorded as the first bounded
pass-to-fail transition with rollback confirmation.

**Unattributed ending:** bisection remains locked because searching model
history without a component-level causal test would create a misleading
finding.

## 4. Data steward — determine whether the changed slice matches the failure

**Trigger:** a bounded checkpoint transition has identical training-config
hashes but different training-manifest hashes.

1. Open the training-slice audit after bisection.
2. Compare low-light share in `ckpt-3` (4.1%) with `ckpt-4` (0.7%).
3. Compare that direction with the regression set, which is 81.6% low-light.
4. Inspect immutable manifest hashes and the exact cause-class rule.
5. Record `DATA_COMPOSITION`: depleted low-light share matches the affected
   probes.
6. Note that tier-3 per-example attribution is unavailable in v0.1 and is not
   fabricated by the demo.

**Attributed ending:** the steward gets a slice-level finding and can recommend
restoring/reweighting the slice.

**Unattributed ending:** if manifest/slice evidence does not discriminate a
cause, the product reports `UNDETERMINED`; it does not upgrade correlation to a
data-quality or per-example attribution claim.

## Cross-role handoff

```text
incident responder
  preserves source + reconstructs time
        ↓
robotics engineer
  tests component interventions
        ↓ only when an outcome flips
model owner
  bisects checkpoint history + confirms rollback
        ↓ only when a boundary is bounded
data steward
  compares manifests, slices, and regression set
        ↓
exported finding with explicit scope and unavailable tiers
```
