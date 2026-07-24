# Limits

This v0.1 is a deterministic reference harness, not a production robotics
root-cause system.

## Implemented and verified

- Full component → checkpoint → data Journey 0 on a CPU-only toy stack.
- Normalization of loopkit agent traces and decoded MCAP-style JSON envelopes
  into the same actor-keyed timeline.
- Ranked per-component deviation scan.
- Multi-seed counterfactual replay; confidence comes only from outcome flips
  and a declared determinism score.
- Logarithmic decisive-step and checkpoint bisection.
- Generated same-slice probes plus unrelated controls; rollback confirmation.
- Manifest/config diff, slice comparison, evidenced cause-class verdict.
- `UNATTRIBUTED` and `UNDETERMINED` paths with reasons.

## Not supported or not yet measured

- Raw binary MCAP/rosbag2 decoding is optional and not implemented in the
  dependency-free path. The demo consumes the normalized JSON envelope that a
  binary adapter must emit. Therefore the launch claim “MCAP ingest working”
  is not met.
- No ROS 2 runtime, Foxglove server, Rerun server, or real deep link is
  included.
- The toy components are deterministic functions, not trained PyTorch models.
  Checkpoint records contain behavior parameters rather than large weights.
- The installed CLI expects to run from a clone containing the bundled
  `demo/` fixtures. A standalone wheel with embedded fixture resources is
  deferred; the specified Journey 0 is clone-based.
- The heuristic suspect ranker replaces the optional LLM hypothesis agent.
- No Who&When evaluation or external seeded-fault corpus is included. Those
  launch measurements are not met.
- `make reproduce-benchmark` measures only generated toy cases. Its numbers
  are regression-test results and must not be presented as real accuracy.
- Tier-3 TracIn/TRAK attribution is not included. `DATA_QUALITY` can only be
  emitted when manifest metadata explicitly records verified label errors.
- Multi-culprit search, triage clustering, contested verdicts, and ASSAY export
  are deferred.
- The demo abstention rate is 0% because all toy evidence is complete. Tests
  exercise abstention; no claim is made that a 10–20% production target has
  been calibrated.
- Oracle-less components can be suspected but never ruled out. This reference
  implementation refuses a confident component verdict if no substitution
  flips the outcome.
