from __future__ import annotations

import shutil
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from .core import (
    Frame,
    build_toy_frames,
    canonical_hash,
    ingest_agent_trace_data,
    ingest_decoded_mcap_data,
    investigate,
    load_stack_data,
)
from .fixtures import fixture_documents
from .report import write_finding
from .storage import InvestigationStore


SUPPORTED_MODES = ("live-reference", "trace-replay")
SUPPORTED_TRACE_FORMATS = ("loopkit-trace-v1", "decoded-mcap-envelope-v1")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return dict(value)


def _manifest_mapping(value: Any) -> dict[str, dict[str, Any]]:
    manifests = _mapping(value, "manifests")
    result: dict[str, dict[str, Any]] = {}
    for checkpoint, manifest in manifests.items():
        result[str(checkpoint)] = _mapping(
            manifest, f"manifest for {checkpoint}"
        )
    return result


def _oracle_limited(frames: tuple[Frame, ...]) -> tuple[Frame, ...]:
    return tuple(
        replace(
            frame,
            references={actor: None for actor in frame.references},
        )
        for frame in frames
    )


def execute_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Execute one complete investigation without persistence."""
    request = _mapping(payload, "investigation request")
    mode = str(request.get("mode", "live-reference"))
    if mode not in SUPPORTED_MODES:
        raise ValueError(
            f"mode must be one of {', '.join(SUPPORTED_MODES)}"
        )
    seeds = int(request.get("seeds", 10))
    packaged_stack, packaged_registry, packaged_manifests = fixture_documents()
    stack_document = _mapping(request.get("stack", packaged_stack), "stack")
    registry = _mapping(request.get("registry", packaged_registry), "registry")
    manifests = _manifest_mapping(
        request.get("manifests", packaged_manifests)
    )
    stack = load_stack_data(stack_document)

    if mode == "live-reference":
        scenario = str(request.get("scenario", "failure"))
        if scenario == "failure":
            frames = build_toy_frames()
        elif scenario == "passing":
            frames = build_toy_frames(low_light_recall=1.0)
        elif scenario == "oracle-limited":
            frames = _oracle_limited(build_toy_frames())
        else:
            raise ValueError(
                "live-reference scenario must be failure, passing, or "
                "oracle-limited"
            )
        execution_mode = "live_reference_execution"
        source = f"tabletop-low-light-v1:{scenario}"
    else:
        trace = _mapping(request.get("trace"), "trace")
        trace_format = str(request.get("trace_format", trace.get("format", "")))
        if trace_format not in SUPPORTED_TRACE_FORMATS:
            raise ValueError(
                "trace_format must be loopkit-trace-v1 or "
                "decoded-mcap-envelope-v1"
            )
        if trace.get("format") != trace_format:
            raise ValueError("trace_format does not match trace.format")
        if trace_format == "loopkit-trace-v1":
            frames = ingest_agent_trace_data(trace)
        else:
            frames = ingest_decoded_mcap_data(trace)
        execution_mode = "normalized_trace_replay"
        source = str(request.get("source", trace_format))

    finding = investigate(
        frames,
        stack,
        registry,
        manifests,
        execution_mode=execution_mode,
        source=source,
        seeds=seeds,
    )
    finding["request"] = {
        "mode": mode,
        "scenario": request.get("scenario") if mode == "live-reference" else None,
        "trace_format": (
            request.get("trace_format") if mode == "trace-replay" else None
        ),
    }
    return finding


class InvestigationManager:
    def __init__(self, store: InvestigationStore, artifact_root: Path):
        self.store = store
        self.artifact_root = artifact_root.resolve()
        self.artifact_root.mkdir(parents=True, exist_ok=True)

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        request = _mapping(payload, "investigation request")
        mode = str(request.get("mode", "live-reference"))
        run_id = uuid.uuid4().hex
        self.store.start(run_id, mode, request)
        staging = Path(
            tempfile.mkdtemp(prefix=f".{run_id}-", dir=self.artifact_root)
        )
        final_dir = self.artifact_root / run_id
        try:
            finding = execute_payload(request)
            finding["run_id"] = run_id
            finding_hash = canonical_hash(finding)
            finding["finding_hash"] = finding_hash
            write_finding(staging / "report.html", finding)
            if final_dir.exists():
                raise RuntimeError(f"artifact directory already exists: {final_dir}")
            staging.replace(final_dir)
            self.store.complete(run_id, finding, finding_hash, final_dir)
            record = self.store.get(run_id)
            if record is None:
                raise RuntimeError("completed investigation is not readable")
            return record
        except Exception as exc:
            self.store.fail(run_id, str(exc))
            shutil.rmtree(staging, ignore_errors=True)
            raise
