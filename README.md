# CULPRIT

CULPRIT is an execution-backed debugging harness for multi-model systems. It
answers three questions in order: which component caused the failure, which
checkpoint transition introduced it, and what changed in the training data.

The repository contains three deliberately separate surfaces:

1. The [GitHub Pages workbench](docs/app/index.html) is a static, interactive
   reconstruction over embedded fixture data. It never claims to run a robot,
   model, or Python process.
2. The installed `culprit` CLI executes normalization, counterfactual replay,
   decisive-step and checkpoint bisection, manifest audit, and evidence
   generation.
3. `culprit serve` exposes the same installed workflow through a local HTTP API
   with SQLite persistence, health/readiness contracts, and durable JSON/HTML
   evidence bundles.

The source thesis is in [docs/BRIEF.md](docs/BRIEF.md). This remains a compact
reference engine rather than a production robotics accuracy claim; read
[LIMITS.md](LIMITS.md) before applying its findings outside the bundled stack.

## Ten-minute journey

```bash
git clone https://github.com/Aneesh-Pothuru/culprit
cd culprit
python -m pip install .

# Generate the static report used by Pages.
culprit demo

# Actually execute the packaged CPU reference stack and persist the evidence.
culprit investigate --mode live-reference

# Prove the honest stop path when usable references are absent.
culprit investigate --mode live-reference --scenario oracle-limited

# Inspect the durable ledger.
culprit runs
```

No key, GPU, ROS install, or network is required. Package resources make this
journey work from an installed wheel without a repository checkout. Runtime
state is written beneath `.culprit/` by default:

```text
.culprit/
├── culprit.sqlite3
└── artifacts/
    └── <run-id>/
        ├── finding.json
        └── report.html
```

The failure fixture is a deterministic
`detector → planner → controller` tabletop stack with five checkpoints.
Checkpoint 4 drops the low-light training slice. A complete run:

1. normalizes the evidence and ranks component deviations;
2. re-executes downstream behavior with one oracle substitution at a time;
3. bisects the decisive frame and checkpoint 3 → 4 transition;
4. confirms rollback, audits the manifest/slice change, and records
   `DATA_COMPOSITION`;
5. hashes and persists the finding plus a standalone HTML evidence report.

![CULPRIT component-to-data finding report](docs/assets/demo.jpg)

## Replay a normalized trace

The installed CLI accepts the two dependency-free envelopes implemented by the
core. Multi-frame evidence must mark at least one
`metadata.scene.target_frame: true`; a single-frame incident is unambiguous.

```bash
culprit investigate \
  --mode trace-replay \
  --trace demo/agent-trace.json \
  --trace-format loopkit-trace-v1

culprit investigate \
  --mode trace-replay \
  --trace demo/decoded-mcap.json \
  --trace-format decoded-mcap-envelope-v1
```

Supply a compatible stack, checkpoint registry, and manifest directory with
`--stack`, `--registry`, and `--manifests`. The built-in engine intentionally
rejects arbitrary component graphs; it currently executes exactly the shipped
tabletop reference contract.

## Local HTTP service

Start the loopback-only, keyless service:

```bash
culprit serve
```

Startup emits one structured JSON event. The operational contract is:

```bash
curl -fsS http://127.0.0.1:8765/healthz
curl -fsS http://127.0.0.1:8765/readyz
curl -fsS http://127.0.0.1:8765/v1/config

curl -fsS -X POST http://127.0.0.1:8765/v1/investigations \
  -H 'Content-Type: application/json' \
  -d '{"mode":"live-reference","scenario":"failure","seeds":10}'

curl -fsS http://127.0.0.1:8765/v1/investigations
```

`POST /v1/investigations` is synchronous in v0.2. It returns the durable ledger
record, finding, hash, and artifact location. Recorded traces are submitted
inline with `"mode":"trace-replay"`, a supported `trace_format`, and a `trace`
object. Full endpoint and operations details are in
[docs/OPERATIONS.md](docs/OPERATIONS.md).

Configuration is available by CLI flag or environment:

| Setting | Default | Purpose |
|---|---:|---|
| `CULPRIT_HOST` | `127.0.0.1` | Bind address |
| `CULPRIT_PORT` | `8765` | HTTP port |
| `CULPRIT_DATABASE` | `.culprit/culprit.sqlite3` | SQLite ledger |
| `CULPRIT_ARTIFACT_DIR` | `.culprit/artifacts` | Evidence bundles |
| `CULPRIT_API_TOKEN` | unset | Bearer token; required beyond loopback |
| `CULPRIT_MAX_BODY_BYTES` | `5242880` | Request limit |

The service refuses a non-loopback bind without a bearer token. It does not
provide TLS or multi-tenant authorization; put a real authenticated TLS proxy
in front of it if local-only operation is insufficient.

## Container

The image runs as a non-root user and persists only `/var/lib/culprit`. Remote
container binding requires a token:

```bash
export CULPRIT_API_TOKEN='replace-with-a-long-random-value'
docker compose up --build

curl -fsS http://127.0.0.1:8765/healthz
curl -fsS -H "Authorization: Bearer $CULPRIT_API_TOKEN" \
  http://127.0.0.1:8765/v1/config
```

The Compose port is published only on host loopback, the root filesystem is
read-only, Linux capabilities are dropped, and the SQLite/artifact directory
uses a named volume.

## Development and evidence commands

```bash
make demo
make test
make lint
make service-check
make reproduce-counterfactuals
make reproduce-benchmark

culprit bisect
culprit audit-data
culprit show <run-id>
```

`stack.yaml` and `registry.yaml` use JSON syntax, which is valid YAML and can
be parsed with the standard library. `make reproduce-benchmark` is an internal
deterministic regression suite, not an external accuracy result.

## Evidence flow

```text
static Pages workbench ── embedded fixture reconstruction only

CLI / HTTP request
  → validate + normalize
  → execute counterfactual trials
  → decisive-step bisection
  → checkpoint bisection + rollback probes
  → manifest + slice audit
  → ATTRIBUTED / UNATTRIBUTED / UNDETERMINED finding
  → finding hash + SQLite ledger + JSON/HTML evidence bundle
```
