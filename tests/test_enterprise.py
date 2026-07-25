from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from culprit.service import ServiceConfig, build_server
from culprit.storage import InvestigationStore
from culprit.workflow import InvestigationManager, execute_payload


ROOT = Path(__file__).resolve().parents[1]


class DurableWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        runtime = Path(self.temporary.name)
        self.database = runtime / "state" / "culprit.sqlite3"
        self.artifacts = runtime / "evidence"
        self.store = InvestigationStore(self.database)
        self.manager = InvestigationManager(self.store, self.artifacts)

    def tearDown(self):
        self.temporary.cleanup()

    def test_live_reference_descent_persists_complete_evidence(self):
        record = self.manager.run(
            {"mode": "live-reference", "scenario": "failure", "seeds": 10}
        )
        self.assertEqual(record["status"], "COMPLETED")
        self.assertEqual(record["finding"]["status"], "ATTRIBUTED")
        self.assertEqual(
            record["finding"]["component"]["component"],
            "perception.detector",
        )
        self.assertEqual(record["finding"]["checkpoint"]["current"], "ckpt-4")
        self.assertEqual(
            record["finding"]["data"]["verdict"], "DATA_COMPOSITION"
        )
        self.assertEqual(
            record["finding"]["evidence"]["execution_mode"],
            "live_reference_execution",
        )
        artifact_dir = Path(record["artifact_dir"])
        self.assertTrue((artifact_dir / "finding.json").is_file())
        self.assertTrue((artifact_dir / "report.html").is_file())
        self.assertTrue(record["finding_hash"].startswith("sha256:"))

        reopened = InvestigationStore(self.database).get(record["id"])
        self.assertEqual(reopened["finding_hash"], record["finding_hash"])

    def test_oracle_limited_run_stops_unattributed_and_keeps_report(self):
        record = self.manager.run(
            {
                "mode": "live-reference",
                "scenario": "oracle-limited",
            }
        )
        finding = record["finding"]
        self.assertEqual(finding["status"], "UNATTRIBUTED")
        self.assertIsNone(finding["component"]["component"])
        self.assertIsNone(finding["checkpoint"])
        self.assertIsNone(finding["data"])
        report = (Path(record["artifact_dir"]) / "report.html").read_text()
        self.assertIn("No causal claim was issued", report)
        self.assertIn("UNATTRIBUTED", report)

    def test_both_trace_envelopes_execute_the_same_normalized_replay(self):
        agent_trace = json.loads(
            (ROOT / "demo" / "agent-trace.json").read_text()
        )
        decoded_mcap = json.loads(
            (ROOT / "demo" / "decoded-mcap.json").read_text()
        )
        agent = execute_payload(
            {
                "mode": "trace-replay",
                "trace_format": "loopkit-trace-v1",
                "trace": agent_trace,
                "source": "agent-fixture",
            }
        )
        mcap = execute_payload(
            {
                "mode": "trace-replay",
                "trace_format": "decoded-mcap-envelope-v1",
                "trace": decoded_mcap,
                "source": "decoded-mcap-fixture",
            }
        )
        self.assertEqual(
            agent["component"]["component"], mcap["component"]["component"]
        )
        self.assertEqual(agent["decisive_step"], mcap["decisive_step"])
        self.assertEqual(
            agent["evidence"]["execution_mode"], "normalized_trace_replay"
        )

    def test_failed_validation_is_recorded_without_false_finding(self):
        with self.assertRaisesRegex(ValueError, "mode must be one of"):
            self.manager.run({"mode": "magic"})
        records = self.store.list()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "FAILED")
        self.assertIsNone(records[0]["finding"])


class ServiceJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        runtime = Path(self.temporary.name)
        config = ServiceConfig(
            host="127.0.0.1",
            port=0,
            database=runtime / "culprit.sqlite3",
            artifact_dir=runtime / "artifacts",
            max_body_bytes=1024 * 1024,
        )
        self.server = build_server(config)
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        host, port = self.server.server_address[:2]
        self.base = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def request(
        self, path: str, *, method: str = "GET", payload: dict | None = None
    ) -> tuple[int, str, bytes]:
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        request = Request(
            self.base + path,
            data=body,
            headers=headers,
            method=method,
        )
        with urlopen(request, timeout=3) as response:
            return (
                response.status,
                response.headers["Content-Type"],
                response.read(),
            )

    def test_liveness_readiness_config_and_full_http_investigation(self):
        status, _, body = self.request("/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")

        status, _, body = self.request("/readyz")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ready")

        status, _, body = self.request("/v1/config")
        config = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(config["engine"], "tabletop-reference-v1")
        self.assertEqual(config["authentication"], "loopback-only")

        status, _, body = self.request(
            "/v1/investigations",
            method="POST",
            payload={"mode": "live-reference", "scenario": "failure"},
        )
        record = json.loads(body)
        self.assertEqual(status, 201)
        self.assertEqual(record["finding"]["status"], "ATTRIBUTED")
        run_id = record["id"]

        status, _, body = self.request(
            f"/v1/investigations/{run_id}/finding"
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["finding_hash"], record["finding_hash"])

        status, content_type, body = self.request(
            f"/v1/investigations/{run_id}/report"
        )
        self.assertEqual(status, 200)
        self.assertTrue(content_type.startswith("text/html"))
        self.assertIn(b"Three evidenced verdicts", body)

        status, _, body = self.request("/v1/investigations?limit=10")
        listing = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["investigations"][0]["id"], run_id)

    def test_invalid_http_investigation_returns_422_and_failed_ledger(self):
        with self.assertRaises(HTTPError) as caught:
            self.request(
                "/v1/investigations",
                method="POST",
                payload={"mode": "not-real"},
            )
        self.assertEqual(caught.exception.code, 422)
        caught.exception.close()
        status, _, body = self.request("/v1/investigations")
        self.assertEqual(status, 200)
        records = json.loads(body)["investigations"]
        self.assertEqual(records[0]["status"], "FAILED")

    def test_non_loopback_binding_requires_token(self):
        config = ServiceConfig(
            host="0.0.0.0",
            port=8765,
            database=Path(self.temporary.name) / "other.sqlite3",
            artifact_dir=Path(self.temporary.name) / "other-artifacts",
        )
        with self.assertRaisesRegex(ValueError, "API_TOKEN"):
            config.validate()


if __name__ == "__main__":
    unittest.main()
