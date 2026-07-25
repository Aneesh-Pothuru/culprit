# Limits

CULPRIT v0.2 is an installable deterministic reference service, not a
production robotics root-cause system or an external accuracy claim.

## Implemented and verified

- Install-independent component → checkpoint → data Journey 0 on a CPU-only
  toy stack; package resources are included in the wheel.
- Normalization of loopkit agent traces and decoded MCAP-style JSON envelopes
  into the same actor-keyed timeline.
- Ranked per-component deviation scan and actual downstream reference-stack
  re-execution with one oracle substitution at a time.
- Multi-seed counterfactual evidence; confidence comes only from outcome flips
  and the declared determinism score.
- Logarithmic decisive-step and checkpoint bisection.
- Generated same-slice probes plus unrelated controls; rollback confirmation.
- Manifest/config diff, slice comparison, and evidenced cause-class verdict.
- `UNATTRIBUTED` and `UNDETERMINED` reports with explicit reasons and no
  downstream causal claim.
- Shared CLI/HTTP workflow with a SQLite WAL ledger, content-hashed findings,
  per-run JSON/HTML evidence bundles, run listing and retrieval.
- HTTP liveness, storage-backed readiness, safe runtime configuration,
  bounded JSON request bodies, structured access/startup logs, and bearer
  enforcement for non-loopback binds.
- Non-root container with a read-only root filesystem in Compose, dropped
  Linux capabilities, loopback-only host publishing, health check, and
  persistent named volume.

## Reference-engine boundary

- The built-in `tabletop-reference-v1` engine executes exactly
  `perception.detector → planning.planner → control.controller`. Stack
  manifests with other actors are rejected instead of being partially or
  deceptively simulated.
- “Live reference” means the deterministic components are executed in the
  installed Python process. It does not mean connection to a live robot.
- “Trace replay” means a recorded normalized envelope is ingested, one
  component output is substituted, and supported downstream reference
  behavior is re-executed. It is not a browser animation.
- The GitHub Pages workbench is an embedded fixture reconstruction. It does
  not call the Python service on static hosting.

## Not supported or not yet measured

- Raw binary MCAP/rosbag2 decoding is not implemented in the dependency-free
  path. The service consumes `decoded-mcap-envelope-v1`; therefore the broad
  launch claim “raw MCAP ingest working” is not met.
- No ROS 2 runtime, arbitrary model adapter SDK, Foxglove server, Rerun server,
  or live deep link is included.
- The toy components are deterministic functions, not trained PyTorch models.
  Checkpoint records contain behavior parameters rather than model weights.
- The service is synchronous, single-node, and process-local. It has no
  distributed queue, worker leases, horizontal coordination, cancellation, or
  progress streaming.
- SQLite and local artifacts have no built-in remote replication, retention
  policy, encryption-at-rest integration, or automated backup. Operators own
  filesystem permissions and backup/restore.
- Bearer authentication is a deployment guard, not multi-tenant identity,
  RBAC, SSO, secret rotation, or TLS. Non-loopback production use needs an
  authenticated TLS proxy and an external secrets mechanism.
- No Who&When evaluation or external seeded-fault corpus is included. The
  stated launch accuracy measurements are not met.
- `make reproduce-benchmark` measures only generated toy cases. Its numbers
  are regression-test results and must not be presented as real accuracy.
- Tier-3 TracIn/TRAK attribution is not included. `DATA_QUALITY` can only be
  emitted when manifest metadata explicitly records verified label errors.
- Multi-culprit search, triage clustering, contested verdicts, and ASSAY export
  are deferred.
- The default fixture abstention rate is 0% because all toy evidence is
  complete. The oracle-limited journey verifies abstention mechanics; no claim
  is made that a production abstention target has been calibrated.
- Oracle-less components can be suspected but never ruled out. If no
  substitution flips the outcome, CULPRIT records `UNATTRIBUTED` and stops.
