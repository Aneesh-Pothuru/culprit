from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schemas.loopkit import TraceEvent, Verdict


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class Component:
    actor: str
    input_key: str
    output_key: str
    oracle_mode: str
    deterministic: bool


@dataclass(frozen=True)
class StackManifest:
    name: str
    components: tuple[Component, ...]
    determinism_score: float


@dataclass(frozen=True)
class Frame:
    index: int
    timestamp: float
    scene: dict[str, Any]
    outputs: dict[str, Any]
    references: dict[str, Any]


def load_json_yaml(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path} must use JSON syntax (a strict YAML subset) in v0.1"
        ) from exc


def load_stack_data(raw: Mapping[str, Any]) -> StackManifest:
    if raw.get("schema") not in (None, "culprit-stack-v1"):
        raise ValueError("unsupported stack manifest schema")
    if not isinstance(raw.get("components"), list) or not raw["components"]:
        raise ValueError("stack manifest must declare at least one component")
    components = tuple(Component(**item) for item in raw["components"])
    actors = [item.actor for item in components]
    if len(actors) != len(set(actors)):
        raise ValueError("component actor names must be unique")
    if not 0.0 <= float(raw["determinism_score"]) <= 1.0:
        raise ValueError("determinism_score must be in [0, 1]")
    return StackManifest(
        name=str(raw["name"]),
        components=components,
        determinism_score=float(raw["determinism_score"]),
    )


def load_stack(path: Path) -> StackManifest:
    return load_stack_data(load_json_yaml(path))


def normalize_events(events: Iterable[TraceEvent]) -> tuple[Frame, ...]:
    grouped: dict[float, list[TraceEvent]] = {}
    for event in events:
        grouped.setdefault(event.timestamp, []).append(event)
    frames: list[Frame] = []
    for index, timestamp in enumerate(sorted(grouped)):
        current = grouped[timestamp]
        scene: dict[str, Any] = {}
        outputs: dict[str, Any] = {}
        references: dict[str, Any] = {}
        for event in current:
            outputs[event.actor] = event.output
            references[event.actor] = event.reference
            if event.metadata and "scene" in event.metadata:
                scene.update(event.metadata["scene"])
        frames.append(Frame(index, timestamp, scene, outputs, references))
    return tuple(frames)


def ingest_agent_trace_data(raw: Mapping[str, Any]) -> tuple[Frame, ...]:
    if raw.get("format") != "loopkit-trace-v1":
        raise ValueError("unsupported agent trace format")
    events = raw.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("agent trace must contain at least one event")
    return normalize_events(TraceEvent(**event) for event in events)


def ingest_agent_trace(path: Path) -> tuple[Frame, ...]:
    return ingest_agent_trace_data(json.loads(path.read_text()))


def ingest_decoded_mcap_data(raw: Mapping[str, Any]) -> tuple[Frame, ...]:
    if raw.get("format") != "decoded-mcap-envelope-v1":
        raise ValueError(
            "raw binary MCAP is not supported in the dependency-free path; "
            "expected decoded-mcap-envelope-v1"
        )
    messages = raw.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("decoded MCAP envelope must contain at least one message")
    return normalize_events(
        TraceEvent(
            timestamp=message["log_time"],
            actor=message["actor"],
            output=message["payload"]["output"],
            reference=message["payload"].get("reference"),
            metadata={"scene": message["payload"].get("scene", {})},
        )
        for message in messages
    )


def ingest_decoded_mcap(path: Path) -> tuple[Frame, ...]:
    return ingest_decoded_mcap_data(json.loads(path.read_text()))


def _pipeline_outputs(
    scene: dict[str, Any],
    *,
    low_light_recall: float,
    substitute: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    is_low_light = scene["lighting"] == "low"
    detector = bool(scene["object_present"] and (not is_low_light or low_light_recall >= 0.5))
    detector_reference = bool(scene["object_present"])
    if substitute == "perception.detector":
        detector = detector_reference

    planner = "grasp" if detector else "hold"
    planner_reference = "grasp" if detector else "hold"
    if substitute == "planning.planner":
        planner = planner_reference

    controller = planner
    controller_reference = planner
    if substitute == "control.controller":
        controller = controller_reference
    return (
        {
            "perception.detector": detector,
            "planning.planner": planner,
            "control.controller": controller,
        },
        {
            "perception.detector": detector_reference,
            "planning.planner": planner_reference,
            "control.controller": controller_reference,
        },
    )


def build_toy_frames(
    low_light_recall: float = 0.0, fault_frame: int = 7
) -> tuple[Frame, ...]:
    frames: list[Frame] = []
    for index in range(12):
        scene = {
            "object_present": True,
            "lighting": "low" if index == fault_frame else "daylight",
            "target_frame": index == fault_frame,
        }
        outputs, references = _pipeline_outputs(
            scene, low_light_recall=low_light_recall
        )
        frames.append(
            Frame(
                index=index,
                timestamp=round(index / 10, 3),
                scene=scene,
                outputs=outputs,
                references=references,
            )
        )
    return tuple(frames)


def outcome(
    frames: tuple[Frame, ...],
    *,
    substitute: str | None = None,
    substitute_until: int | None = None,
) -> bool:
    if not frames:
        raise ValueError("counterfactual replay requires at least one frame")
    marked_targets = {
        frame.index for frame in frames if frame.scene.get("target_frame") is True
    }
    if not marked_targets:
        if len(frames) != 1:
            raise ValueError(
                "multi-frame traces must mark at least one scene.target_frame"
            )
        marked_targets = {frames[0].index}
    target_commands: list[str] = []
    for frame in frames:
        active_substitute = substitute
        if substitute_until is not None and frame.index > substitute_until:
            active_substitute = None
        # Start from the recorded component output, apply one oracle
        # substitution, then re-run every downstream deterministic component.
        detector = frame.outputs["perception.detector"]
        if active_substitute == "perception.detector":
            detector = frame.references["perception.detector"]
        planner = "grasp" if detector else "hold"
        if active_substitute == "planning.planner":
            planner = "grasp" if detector else "hold"
        controller = planner
        if active_substitute == "control.controller":
            controller = planner
        if frame.index in marked_targets:
            target_commands.append(controller)
    return target_commands == ["grasp"]


def deviation_scan(
    frames: tuple[Frame, ...], stack: StackManifest
) -> tuple[dict[str, Any], ...]:
    ranked: list[dict[str, Any]] = []
    for component in stack.components:
        compared = 0
        deviations = 0
        decisive_frames: list[int] = []
        for frame in frames:
            reference = frame.references.get(component.actor)
            if component.oracle_mode == "none" or reference is None:
                continue
            compared += 1
            if frame.outputs.get(component.actor) != reference:
                deviations += 1
                decisive_frames.append(frame.index)
        score = deviations / compared if compared else 0.0
        ranked.append(
            {
                "actor": component.actor,
                "oracle_mode": component.oracle_mode,
                "compared": compared,
                "deviations": deviations,
                "score": score,
                "frames": decisive_frames,
            }
        )
    return tuple(sorted(ranked, key=lambda item: (-item["score"], item["actor"])))


def counterfactual_trials(
    frames: tuple[Frame, ...], actor: str, seeds: int = 10
) -> dict[str, Any]:
    baseline = outcome(frames)
    results = [outcome(frames, substitute=actor) for _seed in range(seeds)]
    flips = sum(result != baseline for result in results)
    return {
        "actor": actor,
        "baseline_success": baseline,
        "seeds": seeds,
        "successes": sum(results),
        "outcome_flips": flips,
        "flip_rate": flips / seeds,
    }


def attribute_component(
    frames: tuple[Frame, ...], stack: StackManifest, seeds: int = 10
) -> dict[str, Any]:
    scan = deviation_scan(frames, stack)
    trials = [
        counterfactual_trials(frames, item["actor"], seeds=seeds) for item in scan
    ]
    strongest = max(trials, key=lambda item: item["flip_rate"])
    if strongest["flip_rate"] <= 0.0:
        return {
            "verdict": Verdict.UNATTRIBUTED.value,
            "component": None,
            "confidence": 0.0,
            "reason": "no oracle substitution flipped the task outcome",
            "scan": scan,
            "counterfactuals": trials,
            "ruled_out": [],
        }
    confidence = strongest["flip_rate"] * stack.determinism_score
    ruled_out = [
        item["actor"] for item in trials if item["actor"] != strongest["actor"] and item["flip_rate"] == 0
    ]
    return {
        "verdict": Verdict.ATTRIBUTED.value,
        "component": strongest["actor"],
        "confidence": confidence,
        "reason": "oracle substitution reproducibly flipped the task outcome",
        "scan": scan,
        "counterfactuals": trials,
        "ruled_out": ruled_out,
    }


def decisive_step_bisect(
    frames: tuple[Frame, ...], actor: str
) -> dict[str, Any]:
    low = 0
    high = len(frames) - 1
    replays = 0
    answer: int | None = None
    while low <= high:
        midpoint = (low + high) // 2
        replays += 1
        if outcome(frames, substitute=actor, substitute_until=midpoint):
            answer = midpoint
            high = midpoint - 1
        else:
            low = midpoint + 1
    if answer is None:
        return {
            "verdict": Verdict.UNATTRIBUTED.value,
            "frame": None,
            "replays": replays,
        }
    return {
        "verdict": Verdict.ATTRIBUTED.value,
        "frame": answer,
        "timestamp": frames[answer].timestamp,
        "replays": replays,
        "complexity_bound": math.ceil(math.log2(len(frames) + 1)),
    }


def build_probe_set() -> tuple[dict[str, Any], ...]:
    probes = [
        {"probe_id": f"probe-{index:02d}", "slice": "low_light", "control": False}
        for index in range(31)
    ]
    probes.extend(
        {"probe_id": f"probe-{index:02d}", "slice": "backlit", "control": False}
        for index in range(31, 38)
    )
    probes.extend(
        {"probe_id": f"control-{index:02d}", "slice": "daylight", "control": True}
        for index in range(8)
    )
    return tuple(probes)


def _checkpoint_passes(checkpoint: dict[str, Any], probe: dict[str, Any]) -> bool:
    if probe["control"]:
        return True
    return float(checkpoint["behavior"]["adverse_light_recall"]) >= 0.5


def bisect_checkpoints(
    registry: dict[str, Any], component: str = "perception.detector"
) -> dict[str, Any]:
    component_record = registry.get("components", {}).get(component)
    if not component_record:
        return {
            "verdict": Verdict.UNDETERMINED.value,
            "reason": f"checkpoint history is unavailable for {component}",
            "evaluations": 0,
        }
    checkpoints = component_record.get("checkpoints", [])
    if not checkpoints:
        return {
            "verdict": Verdict.UNDETERMINED.value,
            "reason": f"checkpoint history is empty for {component}",
            "evaluations": 0,
        }
    probes = build_probe_set()
    low = 0
    high = len(checkpoints) - 1
    first_bad: int | None = None
    evaluations = 0
    while low <= high:
        midpoint = (low + high) // 2
        evaluations += 1
        passes = all(_checkpoint_passes(checkpoints[midpoint], probe) for probe in probes)
        if passes:
            low = midpoint + 1
        else:
            first_bad = midpoint
            high = midpoint - 1
    if first_bad is None or first_bad == 0:
        return {
            "verdict": Verdict.UNDETERMINED.value,
            "reason": "no bounded pass-to-fail checkpoint transition",
            "evaluations": evaluations,
        }
    previous = checkpoints[first_bad - 1]
    current = checkpoints[first_bad]
    regression_set = [
        probe
        for probe in probes
        if _checkpoint_passes(previous, probe)
        and not _checkpoint_passes(current, probe)
    ]
    controls_hold = all(
        _checkpoint_passes(current, probe) for probe in probes if probe["control"]
    )
    return {
        "verdict": "REGRESSION_FOUND",
        "previous": previous["id"],
        "current": current["id"],
        "evaluations": evaluations,
        "rollback_confirmed": bool(regression_set) and controls_hold,
        "regression_set": regression_set,
        "probe_count": len(probes),
        "control_count": sum(probe["control"] for probe in probes),
        "previous_record": previous,
        "current_record": current,
    }


def audit_data(
    previous_manifest: dict[str, Any],
    current_manifest: dict[str, Any],
    bisection: dict[str, Any],
) -> dict[str, Any]:
    expected_previous = bisection["previous_record"]["training_manifest_hash"]
    expected_current = bisection["current_record"]["training_manifest_hash"]
    actual_previous = canonical_hash(previous_manifest)
    actual_current = canonical_hash(current_manifest)
    if expected_previous != actual_previous or expected_current != actual_current:
        raise ValueError("training manifest content hash does not match registry")
    previous_total = sum(previous_manifest["slices"].values())
    current_total = sum(current_manifest["slices"].values())
    previous_low = previous_manifest["slices"].get("low_light", 0) / previous_total
    current_low = current_manifest["slices"].get("low_light", 0) / current_total
    regression_set = bisection.get("regression_set", [])
    regression_low = (
        sum(item["slice"] == "low_light" for item in regression_set)
        / len(regression_set)
        if regression_set
        else 0.0
    )
    manifest_diff = {
        "previous_hash": expected_previous,
        "current_hash": expected_current,
        "previous_low_light_share": previous_low,
        "current_low_light_share": current_low,
        "regression_set_low_light_share": regression_low,
    }
    if bisection["previous_record"]["config_hash"] != bisection["current_record"]["config_hash"]:
        verdict = Verdict.TRAINING_CONFIG
        reason = "training config hash changed at the regressing transition"
    elif current_manifest.get("verified_label_errors", 0) > 0:
        verdict = Verdict.DATA_QUALITY
        reason = "verified label errors are recorded in the changed manifest"
    elif current_low < previous_low * 0.5 and regression_low >= 0.5:
        verdict = Verdict.DATA_COMPOSITION
        reason = "depleted low-light training share matches the regression-set slice"
    else:
        verdict = Verdict.UNDETERMINED
        reason = "tier-1/2 metadata does not distinguish a cause"
    return {
        "verdict": verdict.value,
        "reason": reason,
        "manifest_diff": manifest_diff,
        "tier": 2,
    }


def investigate_fixture(root: Path) -> dict[str, Any]:
    stack = load_stack(root / "demo" / "stack.yaml")
    registry = load_json_yaml(root / "demo" / "registry.yaml")
    frames = build_toy_frames()
    manifests = {
        path.stem: load_json_yaml(path)
        for path in (root / "demo" / "manifests").glob("*.json")
    }
    return investigate(
        frames,
        stack,
        registry,
        manifests,
        execution_mode="live_reference_execution",
        source="tabletop-low-light-v1",
    )


def investigate(
    frames: tuple[Frame, ...],
    stack: StackManifest,
    registry: dict[str, Any],
    manifests: Mapping[str, dict[str, Any]],
    *,
    execution_mode: str,
    source: str,
    seeds: int = 10,
) -> dict[str, Any]:
    """Run the complete supported descent over normalized evidence.

    The built-in replay engine currently models the reference tabletop stack.
    It re-executes downstream detector/planner/controller behavior; callers
    must not present it as a generic ROS or arbitrary Python runtime.
    """
    if seeds < 1 or seeds > 10_000:
        raise ValueError("seeds must be between 1 and 10000")
    expected_actors = {
        "perception.detector",
        "planning.planner",
        "control.controller",
    }
    actors = {item.actor for item in stack.components}
    if actors != expected_actors:
        raise ValueError(
            "the built-in tabletop-reference-v1 engine requires exactly "
            "perception.detector, planning.planner, and control.controller"
        )
    component = attribute_component(frames, stack, seeds=seeds)
    evidence = {
        "execution_mode": execution_mode,
        "engine": "tabletop-reference-v1",
        "source": source,
        "frame_count": len(frames),
        "stack": stack.name,
        "stack_hash": canonical_hash(
            {
                "name": stack.name,
                "determinism_score": stack.determinism_score,
                "components": [asdict(item) for item in stack.components],
            }
        ),
        "registry_hash": canonical_hash(registry),
        "seeds": seeds,
    }
    if component["verdict"] != Verdict.ATTRIBUTED.value:
        return {
            "schema": "culprit-finding-v1",
            "fixture": source,
            "status": Verdict.UNATTRIBUTED.value,
            "component": component,
            "decisive_step": None,
            "checkpoint": None,
            "data": None,
            "evidence": evidence,
            "limits": {
                "external_benchmark": False,
                "raw_mcap": False,
                "tier3_tda": False,
            },
        }
    step = decisive_step_bisect(frames, component["component"])
    checkpoint = bisect_checkpoints(registry, component["component"])
    if checkpoint["verdict"] != "REGRESSION_FOUND":
        return {
            "schema": "culprit-finding-v1",
            "fixture": source,
            "status": Verdict.UNDETERMINED.value,
            "component": component,
            "decisive_step": step,
            "checkpoint": checkpoint,
            "data": None,
            "evidence": evidence,
            "limits": {
                "external_benchmark": False,
                "raw_mcap": False,
                "tier3_tda": False,
            },
        }
    previous_manifest = manifests.get(checkpoint["previous"])
    current_manifest = manifests.get(checkpoint["current"])
    if previous_manifest is None or current_manifest is None:
        missing = [
            checkpoint_id
            for checkpoint_id, manifest in (
                (checkpoint["previous"], previous_manifest),
                (checkpoint["current"], current_manifest),
            )
            if manifest is None
        ]
        data = {
            "verdict": Verdict.UNDETERMINED.value,
            "reason": "training manifests are unavailable: " + ", ".join(missing),
            "manifest_diff": None,
            "tier": 0,
        }
    else:
        data = audit_data(previous_manifest, current_manifest, checkpoint)
    # Internal records are useful for computation but overly noisy in reports.
    checkpoint_public = {
        key: value
        for key, value in checkpoint.items()
        if key not in {"previous_record", "current_record"}
    }
    return {
        "schema": "culprit-finding-v1",
        "fixture": source,
        "status": (
            Verdict.ATTRIBUTED.value
            if data["verdict"] != Verdict.UNDETERMINED.value
            else Verdict.UNDETERMINED.value
        ),
        "component": component,
        "decisive_step": step,
        "checkpoint": checkpoint_public,
        "data": data,
        "evidence": evidence,
        "limits": {
            "external_benchmark": False,
            "raw_mcap": False,
            "tier3_tda": False,
        },
    }
