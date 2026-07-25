# CULPRIT local service operations

## Modes

| Mode | What executes | Appropriate claim |
|---|---|---|
| `live-reference` | The packaged deterministic tabletop components run in the installed Python process. | The reference engine executed now. |
| `trace-replay` | A loopkit or decoded-MCAP JSON envelope is normalized; the supported downstream reference stack is re-executed under substitutions. | The recorded evidence was replayed by the installed engine. |
| GitHub Pages workbench | Embedded JavaScript fixture data changes visible reconstruction state. | Interactive reconstruction only; no backend executed. |

## Startup and shutdown

```bash
culprit serve
```

The default bind is `127.0.0.1:8765`, with runtime state under `.culprit/`.
`SIGINT` and `SIGTERM` stop the HTTP accept loop and close the listening socket.
Startup and shutdown events are JSON lines suitable for a local supervisor.

A non-loopback bind is rejected unless `CULPRIT_API_TOKEN` or `--api-token` is
set. Health and readiness remain unauthenticated for orchestrators. All `/v1`
routes require `Authorization: Bearer <token>` when a token is configured.

## Probes

- `GET /healthz`: process liveness and version. It does not touch storage.
- `GET /readyz`: SQLite `quick_check`, database query, and an artifact-directory
  write probe. Returns `503` if any check fails.
- `GET /v1/config`: non-secret runtime contract—version, mode, engine, body
  limit, persistence kind, and authentication mode.

## Investigation API

`POST /v1/investigations` accepts JSON and returns `201` with the persisted
record.

Reference execution:

```json
{
  "mode": "live-reference",
  "scenario": "failure",
  "seeds": 10
}
```

`scenario` is `failure`, `passing`, or `oracle-limited`. The last two complete
with `UNATTRIBUTED` because no tested substitution supports a causal claim.

Recorded evidence:

```json
{
  "mode": "trace-replay",
  "trace_format": "loopkit-trace-v1",
  "source": "incident-004",
  "trace": {
    "format": "loopkit-trace-v1",
    "events": []
  }
}
```

The trace must contain events. An optional inline `stack`, `registry`, and
`manifests` object replaces packaged reference documents. The server accepts
inline data rather than arbitrary server filesystem paths. Invalid contracts
return `422` and remain visible as `FAILED` ledger entries without a finding.

Retrieval:

- `GET /v1/investigations?limit=50`
- `GET /v1/investigations/{id}`
- `GET /v1/investigations/{id}/finding`
- `GET /v1/investigations/{id}/report`

The body limit defaults to 5 MiB and is configurable. Responses use `no-store`,
`nosniff`, and frame-denial headers.

## Persistence and recovery

Each request is inserted as `RUNNING` before execution and transitions once to
`COMPLETED` or `FAILED`. Completed rows retain the request, finding, content
hash, artifact directory, and timestamps. Artifacts are built in a temporary
directory and atomically renamed into `<artifact-root>/<run-id>`.

SQLite uses WAL mode and a five-second busy timeout. Back up the database and
artifact root as one logical unit:

1. stop writers or take a SQLite-consistent backup;
2. copy the database, `-wal`/`-shm` files when present, and artifact directory;
3. restore filesystem ownership before readiness is enabled.

There is no automatic retention or replication. Deleting a ledger row or
artifact is an operator action and no deletion endpoint is exposed.

## Container boundary

`Dockerfile` runs as the unprivileged `culprit` user. `compose.yaml` requires a
token, publishes only to host loopback, mounts a named volume at
`/var/lib/culprit`, uses a read-only root filesystem plus `/tmp` tmpfs, drops
all capabilities, and enables `no-new-privileges`.

The image intentionally refuses to start on `0.0.0.0` without a token. TLS,
RBAC, SSO, multi-node scheduling, and remote artifact storage are outside v0.2.
