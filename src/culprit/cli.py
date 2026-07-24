from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .core import (
    audit_data,
    bisect_checkpoints,
    build_toy_frames,
    counterfactual_trials,
    investigate_fixture,
    load_json_yaml,
)
from .report import write_finding


_CWD = Path.cwd()
_SOURCE_ROOT = Path(__file__).resolve().parents[2]
ROOT = _CWD if (_CWD / "demo" / "stack.yaml").is_file() else _SOURCE_ROOT
DEMO_DIR = (
    _CWD / "docs" / "demo"
    if (_CWD / "docs").is_dir()
    else _CWD / "culprit-demo"
)


def print_summary(finding: dict) -> None:
    component = finding["component"]
    step = finding["decisive_step"]
    checkpoint = finding["checkpoint"]
    data = finding["data"]
    print(
        f"COMPONENT {component['component']} confidence={component['confidence']:.2f} "
        f"frame={step['frame']} flips=10/10"
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


def run_investigation(*, quiet: bool = False) -> int:
    finding = investigate_fixture(ROOT)
    write_finding(DEMO_DIR / "index.html", finding)
    if not quiet:
        print_summary(finding)
        print(f"REPORT {(DEMO_DIR / 'index.html').relative_to(ROOT)}")
    return 0


def run_bisect() -> int:
    registry = load_json_yaml(ROOT / "demo" / "registry.yaml")
    result = bisect_checkpoints(registry)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verdict"] == "REGRESSION_FOUND" else 2


def run_audit() -> int:
    registry = load_json_yaml(ROOT / "demo" / "registry.yaml")
    bisection = bisect_checkpoints(registry)
    previous = load_json_yaml(
        ROOT / "demo" / "manifests" / f"{bisection['previous']}.json"
    )
    current = load_json_yaml(
        ROOT / "demo" / "manifests" / f"{bisection['current']}.json"
    )
    result = audit_data(previous, current, bisection)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


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
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"WROTE {target.relative_to(ROOT)}")
    return 0


def reproduce_benchmark() -> int:
    # Generate multiple deterministic fault placements to ensure the mechanism
    # is not coupled to one timestamp. This remains an internal regression test.
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
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"WROTE {target.relative_to(ROOT)}")
    return 0


def check() -> int:
    finding = investigate_fixture(ROOT)
    assert finding["component"]["component"] == "perception.detector"
    assert finding["checkpoint"]["previous"] == "ckpt-3"
    assert finding["checkpoint"]["current"] == "ckpt-4"
    assert finding["data"]["verdict"] == "DATA_COMPOSITION"
    print("CULPRIT self-check passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="culprit")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    investigate = sub.add_parser("investigate")
    investigate.add_argument("--live", action="store_true")
    investigate.add_argument("--quiet", action="store_true")
    sub.add_parser("bisect")
    sub.add_parser("audit-data")
    sub.add_parser("reproduce-benchmark")
    sub.add_parser("reproduce-counterfactuals")
    sub.add_parser("check")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        return run_investigation()
    if args.command == "investigate":
        return run_investigation(quiet=args.quiet)
    if args.command == "bisect":
        return run_bisect()
    if args.command == "audit-data":
        return run_audit()
    if args.command == "reproduce-benchmark":
        return reproduce_benchmark()
    if args.command == "reproduce-counterfactuals":
        return reproduce_counterfactuals()
    if args.command == "check":
        return check()
    raise AssertionError(args.command)
