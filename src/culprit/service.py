from __future__ import annotations

import hmac
import json
import os
import signal
import tempfile
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .storage import InvestigationStore
from .workflow import InvestigationManager


@dataclass(frozen=True)
class ServiceConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    database: Path = Path(".culprit/culprit.sqlite3")
    artifact_dir: Path = Path(".culprit/artifacts")
    api_token: str | None = None
    max_body_bytes: int = 5 * 1024 * 1024

    @classmethod
    def from_environment(cls) -> "ServiceConfig":
        token = os.getenv("CULPRIT_API_TOKEN") or None
        return cls(
            host=os.getenv("CULPRIT_HOST", "127.0.0.1"),
            port=int(os.getenv("CULPRIT_PORT", "8765")),
            database=Path(
                os.getenv("CULPRIT_DATABASE", ".culprit/culprit.sqlite3")
            ),
            artifact_dir=Path(
                os.getenv("CULPRIT_ARTIFACT_DIR", ".culprit/artifacts")
            ),
            api_token=token,
            max_body_bytes=int(
                os.getenv("CULPRIT_MAX_BODY_BYTES", str(5 * 1024 * 1024))
            ),
        )

    def validate(self) -> None:
        if not 0 <= self.port <= 65535:
            raise ValueError("port must be between 0 and 65535")
        if self.max_body_bytes < 1024:
            raise ValueError("max_body_bytes must be at least 1024")
        loopback_hosts = {"127.0.0.1", "::1", "localhost"}
        if self.host not in loopback_hosts and not self.api_token:
            raise ValueError(
                "CULPRIT_API_TOKEN is required when binding beyond loopback"
            )

    def public(self) -> dict[str, Any]:
        return {
            "service": "culprit",
            "version": __version__,
            "host": self.host,
            "port": self.port,
            "authentication": "bearer" if self.api_token else "loopback-only",
            "max_body_bytes": self.max_body_bytes,
            "modes": ["live-reference", "trace-replay"],
            "engine": "tabletop-reference-v1",
            "persistence": "sqlite",
        }


class CulpritHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        *,
        config: ServiceConfig,
        store: InvestigationStore,
        manager: InvestigationManager,
    ):
        super().__init__(address, handler)
        self.config = config
        self.store = store
        self.manager = manager


class CulpritRequestHandler(BaseHTTPRequestHandler):
    server: CulpritHTTPServer
    server_version = "Culprit"
    sys_version = ""

    def log_message(self, format: str, *args: object) -> None:
        print(
            json.dumps(
                {
                    "event": "http_access",
                    "client": self.client_address[0],
                    "message": format % args,
                },
                sort_keys=True,
            ),
            flush=True,
        )

    def _headers(self, content_type: str, length: int) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")

    def _json(self, status: HTTPStatus, payload: Any) -> None:
        body = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self._headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, status: HTTPStatus, body: bytes) -> None:
        self.send_response(status)
        self._headers("text/html; charset=utf-8", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _authenticated(self) -> bool:
        token = self.server.config.api_token
        if not token:
            return True
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {token}"
        if hmac.compare_digest(supplied, expected):
            return True
        self._json(
            HTTPStatus.UNAUTHORIZED,
            {"error": {"code": "unauthorized", "message": "bearer token required"}},
        )
        return False

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/":
            self._json(
                HTTPStatus.OK,
                {
                    "service": "culprit",
                    "version": __version__,
                    "health": "/healthz",
                    "readiness": "/readyz",
                    "api": "/v1/investigations",
                },
            )
            return
        if path == "/healthz":
            self._json(
                HTTPStatus.OK,
                {"status": "ok", "service": "culprit", "version": __version__},
            )
            return
        if path == "/readyz":
            ready, detail = self.server.store.ready()
            try:
                with tempfile.NamedTemporaryFile(
                    dir=self.server.manager.artifact_root
                ):
                    pass
            except OSError as exc:
                ready = False
                detail = f"artifact storage: {exc}"
            self._json(
                HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE,
                {"status": "ready" if ready else "not_ready", "detail": detail},
            )
            return
        if not self._authenticated():
            return
        if path == "/v1/config":
            self._json(HTTPStatus.OK, self.server.config.public())
            return
        if path == "/v1/investigations":
            try:
                limit = int(parse_qs(parsed.query).get("limit", ["50"])[0])
            except ValueError:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": {"code": "invalid_limit", "message": "limit must be an integer"}},
                )
                return
            records = [self._summary(item) for item in self.server.store.list(limit)]
            self._json(
                HTTPStatus.OK,
                {"investigations": records, "count": len(records)},
            )
            return
        parts = path.strip("/").split("/")
        if len(parts) >= 3 and parts[:2] == ["v1", "investigations"]:
            run_id = parts[2]
            if not run_id.isalnum():
                self._json(
                    HTTPStatus.NOT_FOUND,
                    {"error": {"code": "not_found", "message": "investigation not found"}},
                )
                return
            record = self.server.store.get(run_id)
            if record is None:
                self._json(
                    HTTPStatus.NOT_FOUND,
                    {"error": {"code": "not_found", "message": "investigation not found"}},
                )
                return
            if len(parts) == 3:
                self._json(HTTPStatus.OK, record)
                return
            if len(parts) == 4 and parts[3] == "finding":
                if record["finding"] is None:
                    self._json(
                        HTTPStatus.CONFLICT,
                        {"error": {"code": "not_complete", "message": "finding is unavailable"}},
                    )
                else:
                    self._json(HTTPStatus.OK, record["finding"])
                return
            if len(parts) == 4 and parts[3] == "report":
                artifact_dir = record.get("artifact_dir")
                if not artifact_dir:
                    self._json(
                        HTTPStatus.CONFLICT,
                        {"error": {"code": "not_complete", "message": "report is unavailable"}},
                    )
                    return
                report = Path(artifact_dir).resolve() / "report.html"
                try:
                    report.relative_to(self.server.manager.artifact_root)
                    body = report.read_bytes()
                except (OSError, ValueError):
                    self._json(
                        HTTPStatus.NOT_FOUND,
                        {"error": {"code": "artifact_missing", "message": "report not found"}},
                    )
                    return
                self._html(HTTPStatus.OK, body)
                return
        self._json(
            HTTPStatus.NOT_FOUND,
            {"error": {"code": "not_found", "message": "route not found"}},
        )

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/")
        if path != "/v1/investigations":
            self._json(
                HTTPStatus.NOT_FOUND,
                {"error": {"code": "not_found", "message": "route not found"}},
            )
            return
        if not self._authenticated():
            return
        content_type = self.headers.get("Content-Type", "")
        if content_type.split(";", 1)[0].strip() != "application/json":
            self._json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"error": {"code": "content_type", "message": "application/json required"}},
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": {"code": "empty_body", "message": "JSON body required"}},
            )
            return
        if length > self.server.config.max_body_bytes:
            self._json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": {"code": "body_too_large", "message": "request exceeds configured limit"}},
            )
            return
        try:
            payload = json.loads(self.rfile.read(length))
            record = self.server.manager.run(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": {"code": "invalid_json", "message": str(exc)}},
            )
            return
        except ValueError as exc:
            self._json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": {"code": "invalid_investigation", "message": str(exc)}},
            )
            return
        except Exception:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": {"code": "internal_error", "message": "investigation failed"}},
            )
            return
        self._json(HTTPStatus.CREATED, record)

    @staticmethod
    def _summary(record: dict[str, Any]) -> dict[str, Any]:
        finding = record.get("finding") or {}
        component = finding.get("component") or {}
        return {
            "id": record["id"],
            "status": record["status"],
            "mode": record["mode"],
            "verdict": finding.get("status"),
            "component": component.get("component"),
            "finding_hash": record.get("finding_hash"),
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        }


def build_server(config: ServiceConfig) -> CulpritHTTPServer:
    config.validate()
    store = InvestigationStore(config.database)
    manager = InvestigationManager(store, config.artifact_dir)
    return CulpritHTTPServer(
        (config.host, config.port),
        CulpritRequestHandler,
        config=config,
        store=store,
        manager=manager,
    )


def serve(config: ServiceConfig) -> None:
    server = build_server(config)
    address, port = server.server_address[:2]
    print(
        json.dumps(
            {
                "event": "service_started",
                "address": address,
                "port": port,
                "version": __version__,
                "authentication": "bearer" if config.api_token else "loopback-only",
            },
            sort_keys=True,
        ),
        flush=True,
    )

    def stop(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    previous_handlers: dict[int, Any] = {}
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, stop)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        print(json.dumps({"event": "service_stopped"}, sort_keys=True), flush=True)
