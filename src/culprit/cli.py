from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from .core import (
    audit_data,
    bisect_checkpoints,
    build_toy_frames,
    counterfactual_trials,
    investigate_fixture,
    load_json_yaml,
)
from .fixtures import fixture_documents
from .report import write_finding
from .service import ServiceConfig, serve
from .storage import InvestigationStore
from .workflow import InvestigationManager, execute_payload


_CWD = Path.cwd()
_SOURCE_ROOT = Path(__file__).resolve().parents[2]
ROOT = _CWD if (_CWD / "demo" / "stack.yaml").is_file() else _SOURCE_ROOT
DEMO_DIR = (
    _CWD / "docs" / "demo"
    if (_CWD / "docs").is_dir()
    else _CWD / "culprit-demo"
)


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def print_summary(finding: dict[str, Any]) -> None:
    component = finding["component"]
    if finding.get("status") != "ATTRIBUTED":
        print(
            f"VERDICT {finding.get('status', 'UNDETERMINED')} "
            f"reason={component.get('reason', 'insufficient evidence')}"
        )
        print(
            "MODE "
            + str(finding.get("evidence", {}).get("execution_mode", "unknown"))
        )
        return
    step = finding["decisive_step"]
    checkpoint = finding["checkpoint"]
    data = finding["data"]
    strongest = max(
        component["counterfactuals"],
        key=lambda item: item["flip_rate"],
    )
    print(
        f"COMPONENT {component['component']} confidence={component['confidence']:.2f} "
        f"frame={step['frame']} flips={strongest['outcome_flips']}/{strongest['seeds']}"
    )
    print(
        f"CHECKPOINT {checkpoint['previous']} -> {checkpoint['current']} "
        f"rollback_confirmed={checkpoint['rollback_confirmed']}"
    )
    diff = data["manifest_diff"]
    print(
        f"DATA {data['verdict']} low_light "
        f"{diff['previous_low_light_share']:.1%} -> "
        f"{diff['current_low_light_share']:.1%}"
    )
    print(f"MODE {finding['evidence']['execution_mode']}")


def run_demo() -> int:
    if (ROOT / "demo" / "stack.yaml").is_file():
        finding = investigate_fixture(ROOT)
    else:
        finding = execute_payload({"mode": "live-reference"})
    write_finding(DEMO_DIR / "index.html", finding)
    print_summary(finding)
    print(f"REPORT {(DEMO_DIR / 'index.html').resolve()}")
    print("STATIC MODE generated fixture replay; no service was started")
    return 0


def _load_manifest_directory(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_dir():
        raise ValueError(f"manifest directory does not exist: {path}")
    manifests = {
        item.stem: load_json_yaml(item) for item in sorted(path.glob("*.json"))
    }
    if not manifests:
        raise ValueError(f"manifest directory contains no JSON files: {path}")
    return manifests


def _investigation_payload(args: argparse.Namespace) -> dict[str, Any]:
    mode = "live-reference" if args.live else args.mode
    payload: dict[str, Any] = {
        "mode": mode,
        "seeds": args.seeds,
    }
    if mode == "live-reference":
        payload["scenario"] = args.scenario
    else:
        if args.trace is None:
            raise ValueError("--trace is required in trace-replay mode")
        trace = load_json_yaml(args.trace)
        payload["trace"] = trace
        payload["trace_format"] = args.trace_format or trace.get("format")
        payload["source"] = args.source or args.trace.name
    if args.stack:
        payload["stack"] = load_json_yaml(args.stack)
    if args.registry:
        payload["registry"] = load_json_yaml(args.registry)
    if args.manifests:
        payload["manifests"] = _load_manifest_directory(args.manifests)
    return payload


def run_investigation(args: argparse.Namespace) -> int:
    try:
        payload = _investigation_payload(args)
        store = InvestigationStore(args.database)
        manager = InvestigationManager(store, args.artifact_dir)
        record = manager.run(payload)
    except ValueError as exc:
        print(f"ERROR {exc}")
        return 2
    finding = record["finding"]
    if args.json:
        _print_json(record)
    elif not args.quiet:
        print_summary(finding)
        print(f"RUN {record['id']}")
        print(f"EVIDENCE {record['artifact_dir']}")
        print(f"FINDING_HASH {record['finding_hash']}")
    return 0 if record["status"] == "COMPLETED" else 2


def run_bisect(args: argparse.Namespace) -> int:
    if args.registry:
        registry = load_json_yaml(args.registry)
    elif (ROOT / "demo" / "registry.yaml").is_file():
        registry = load_json_yaml(ROOT / "demo" / "registry.yaml")
    else:
        _, registry, _ = fixture_documents()
    result = bisect_checkpoints(registry, args.component)
    _print_json(result)
    return 0 if result["verdict"] == "REGRESSION_FOUND" else 2


def run_audit(args: argparse.Namespace) -> int:
    if args.registry:
        registry = load_json_yaml(args.registry)
    else:
        _, registry, _ = fixture_documents()
    bisection = bisect_checkpoints(registry, args.component)
    if bisection["verdict"] != "REGRESSION_FOUND":
        _print_json(bisection)
        return 2
    if args.manifests:
        manifests = _load_manifest_directory(args.manifests)
    else:
        _, _, manifests = fixture_documents()
    previous = manifests.get(bisection["previous"])
    current = manifests.get(bisection["current"])
    if previous is None or current is None:
        print("ERROR required transition manifests are unavailable")
        return 2
    result = audit_data(previous, current, bisection)
    _print_json(result)
    return 0 if result["verdict"] != "UNDETERMINED" else 2


def reproduce_counterfactuals() -> int:
    frames = build_toy_frames()
    results = {
        actor: counterfactual_trials(frames, actor, seeds=100)
        for actor in (
            "perception.detector",
            "planning.planner",
            "control.controller",
        )
    }
    payload = {
        "fixture": "tabletop-low-light-v1",
        "seeds": 100,
        "results": results,
        "scope": "deterministic fixture; not a production reproducibility estimate",
    }
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    target = DEMO_DIR / "counterfactual-results.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _print_json(payload)
    print(f"WROTE {target.resolve()}")
    return 0


def reproduce_benchmark() -> int:
    cases = []
    for fault_frame in range(2, 10):
        frames = build_toy_frames(fault_frame=fault_frame)
        detector = counterfactual_trials(frames, "perception.detector", seeds=5)
        planner = counterfactual_trials(frames, "planning.planner", seeds=5)
        cases.append(
            {
                "fault_frame": fault_frame,
                "component_correct": detector["flip_rate"] == 1.0
                and planner["flip_rate"] == 0.0,
            }
        )
    accuracy = sum(case["component_correct"] for case in cases) / len(cases)
    payload = {
        "fixture": "generated-tabletop-faults-v1",
        "cases": len(cases),
        "responsible_component_accuracy": accuracy,
        "scope": "internal deterministic regression suite; not Who&When or an external benchmark",
    }
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    target = DEMO_DIR / "benchmark-results.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _print_json(payload)
    print(f"WROTE {target.resolve()}")
    return 0


def check() -> int:
    finding = execute_payload({"mode": "live-reference"})
    assert finding["component"]["component"] == "perception.detector"
    assert finding["checkpoint"]["previous"] == "ckpt-3"
    assert finding["checkpoint"]["current"] == "ckpt-4"
    assert finding["data"]["verdict"] == "DATA_COMPOSITION"
    abstention = execute_payload(
        {"mode": "live-reference", "scenario": "oracle-limited"}
    )
    assert abstention["status"] == "UNATTRIBUTED"
    print("CULPRIT self-check passed")
    return 0


def run_service(args: argparse.Namespace) -> int:
    environment = ServiceConfig.from_environment()
    config = replace(
        environment,
        host=args.host if args.host is not None else environment.host,
        port=args.port if args.port is not None else environment.port,
        database=(
            args.database if args.database is not None else environment.database
        ),
        artifact_dir=(
            args.artifact_dir
            if args.artifact_dir is not None
            else environment.artifact_dir
        ),
        api_token=(
            args.api_token
            if args.api_token is not None
            else environment.api_token
        ),
        max_body_bytes=(
            args.max_body_bytes
            if args.max_body_bytes is not None
            else environment.max_body_bytes
        ),
    )
    try:
        serve(config)
    except ValueError as exc:
        print(f"ERROR {exc}")
        return 2
    return 0


def list_runs(args: argparse.Namespace) -> int:
    store = InvestigationStore(args.database)
    records = store.list(args.limit)
    if args.json:
        _print_json(records)
        return 0
    for record in records:
        finding = record.get("finding") or {}
        component = finding.get("component") or {}
        print(
            f"{record['id']} {record['status']} "
            f"{finding.get('status', '-')} "
            f"{component.get('component') or '-'} "
            f"{record['created_at']}"
        )
    return 0


def show_run(args: argparse.Namespace) -> int:
    store = InvestigationStore(args.database)
    record = store.get(args.run_id)
    if record is None:
        print(f"ERROR investigation not found: {args.run_id}")
        return 2
    _print_json(record)
    return 0


def _add_persistence_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(".culprit/culprit.sqlite3"),
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path(".culprit/artifacts"),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="culprit")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "demo",
        help="generate the static deterministic fixture report",
    )

    investigate_parser = sub.add_parser(
        "investigate",
        help="execute and persist a live reference run or normalized trace replay",
    )
    investigate_parser.add_argument(
        "--mode",
        choices=("live-reference", "trace-replay"),
        default="live-reference",
    )
    investigate_parser.add_argument(
        "--live",
        action="store_true",
        help="compatibility alias for --mode live-reference",
    )
    investigate_parser.add_argument(
        "--scenario",
        choices=("failure", "passing", "oracle-limited"),
        default="failure",
    )
    investigate_parser.add_argument("--trace", type=Path)
    investigate_parser.add_argument(
        "--trace-format",
        choices=("loopkit-trace-v1", "decoded-mcap-envelope-v1"),
    )
    investigate_parser.add_argument("--source")
    investigate_parser.add_argument("--stack", type=Path)
    investigate_parser.add_argument("--registry", type=Path)
    investigate_parser.add_argument("--manifests", type=Path)
    investigate_parser.add_argument("--seeds", type=int, default=10)
    investigate_parser.add_argument("--quiet", action="store_true")
    investigate_parser.add_argument("--json", action="store_true")
    _add_persistence_arguments(investigate_parser)

    bisect_parser = sub.add_parser("bisect")
    bisect_parser.add_argument("--registry", type=Path)
    bisect_parser.add_argument(
        "--component", default="perception.detector"
    )

    audit_parser = sub.add_parser("audit-data")
    audit_parser.add_argument("--registry", type=Path)
    audit_parser.add_argument("--manifests", type=Path)
    audit_parser.add_argument(
        "--component", default="perception.detector"
    )

    sub.add_parser("reproduce-benchmark")
    sub.add_parser("reproduce-counterfactuals")
    sub.add_parser("check")

    serve_parser = sub.add_parser(
        "serve",
        help="start the durable local HTTP investigation service",
    )
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)
    serve_parser.add_argument("--database", type=Path)
    serve_parser.add_argument("--artifact-dir", type=Path)
    serve_parser.add_argument("--api-token")
    serve_parser.add_argument("--max-body-bytes", type=int)

    runs_parser = sub.add_parser("runs")
    runs_parser.add_argument("--database", type=Path, default=Path(".culprit/culprit.sqlite3"))
    runs_parser.add_argument("--limit", type=int, default=50)
    runs_parser.add_argument("--json", action="store_true")

    show_parser = sub.add_parser("show")
    show_parser.add_argument("run_id")
    show_parser.add_argument("--database", type=Path, default=Path(".culprit/culprit.sqlite3"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        return run_demo()
    if args.command == "investigate":
        return run_investigation(args)
    if args.command == "bisect":
        return run_bisect(args)
    if args.command == "audit-data":
        return run_audit(args)
    if args.command == "reproduce-benchmark":
        return reproduce_benchmark()
    if args.command == "reproduce-counterfactuals":
        return reproduce_counterfactuals()
    if args.command == "check":
        return check()
    if args.command == "serve":
        return run_service(args)
    if args.command == "runs":
        return list_runs(args)
    if args.command == "show":
        return show_run(args)
    raise AssertionError(args.command)
