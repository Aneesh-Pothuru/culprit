import json
import tempfile
import unittest
from pathlib import Path

from culprit.core import (
    StackManifest,
    attribute_component,
    audit_data,
    bisect_checkpoints,
    build_toy_frames,
    decisive_step_bisect,
    deviation_scan,
    ingest_agent_trace,
    ingest_decoded_mcap,
    investigate_fixture,
    load_json_yaml,
    load_stack,
)


ROOT = Path(__file__).resolve().parents[1]


class IngestTests(unittest.TestCase):
    def test_agent_and_decoded_mcap_normalize_to_same_timeline(self):
        agent = ingest_agent_trace(ROOT / "demo" / "agent-trace.json")
        mcap = ingest_decoded_mcap(ROOT / "demo" / "decoded-mcap.json")
        self.assertEqual(agent, mcap)
        self.assertEqual(agent[0].outputs["perception.detector"], False)

    def test_raw_or_wrong_mcap_is_refused_honestly(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bad.json"
            target.write_text(json.dumps({"format": "raw-mcap"}))
            with self.assertRaisesRegex(ValueError, "raw binary MCAP"):
                ingest_decoded_mcap(target)


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.stack = load_stack(ROOT / "demo" / "stack.yaml")
        self.frames = build_toy_frames()

    def test_deviation_scan_ranks_detector_first(self):
        scan = deviation_scan(self.frames, self.stack)
        self.assertEqual(scan[0]["actor"], "perception.detector")
        self.assertEqual(scan[0]["frames"], [7])

    def test_counterfactual_attributes_detector_and_rules_out_downstream(self):
        result = attribute_component(self.frames, self.stack)
        self.assertEqual(result["verdict"], "ATTRIBUTED")
        self.assertEqual(result["component"], "perception.detector")
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(
            set(result["ruled_out"]),
            {"planning.planner", "control.controller"},
        )

    def test_decisive_step_uses_logarithmic_replays(self):
        result = decisive_step_bisect(self.frames, "perception.detector")
        self.assertEqual(result["frame"], 7)
        self.assertLessEqual(result["replays"], result["complexity_bound"])

    def test_no_outcome_flip_abstains(self):
        no_oracle_stack = StackManifest(
            name=self.stack.name,
            components=self.stack.components,
            determinism_score=1.0,
        )
        passing_frames = build_toy_frames(low_light_recall=1.0)
        result = attribute_component(passing_frames, no_oracle_stack)
        self.assertEqual(result["verdict"], "UNATTRIBUTED")


class DescentTests(unittest.TestCase):
    def test_checkpoint_bisection_finds_3_to_4_and_confirms_rollback(self):
        registry = load_json_yaml(ROOT / "demo" / "registry.yaml")
        result = bisect_checkpoints(registry)
        self.assertEqual(result["previous"], "ckpt-3")
        self.assertEqual(result["current"], "ckpt-4")
        self.assertTrue(result["rollback_confirmed"])
        self.assertEqual(len(result["regression_set"]), 38)
        self.assertLessEqual(result["evaluations"], 3)

    def test_data_audit_matches_changed_slice(self):
        registry = load_json_yaml(ROOT / "demo" / "registry.yaml")
        bisection = bisect_checkpoints(registry)
        previous = load_json_yaml(ROOT / "demo" / "manifests" / "ckpt-3.json")
        current = load_json_yaml(ROOT / "demo" / "manifests" / "ckpt-4.json")
        result = audit_data(previous, current, bisection)
        self.assertEqual(result["verdict"], "DATA_COMPOSITION")
        self.assertAlmostEqual(
            result["manifest_diff"]["regression_set_low_light_share"],
            31 / 38,
        )

    def test_data_audit_rejects_manifest_hash_mismatch(self):
        registry = load_json_yaml(ROOT / "demo" / "registry.yaml")
        bisection = bisect_checkpoints(registry)
        previous = load_json_yaml(ROOT / "demo" / "manifests" / "ckpt-3.json")
        current = load_json_yaml(ROOT / "demo" / "manifests" / "ckpt-4.json")
        current["slices"]["low_light"] = 8
        with self.assertRaisesRegex(ValueError, "content hash"):
            audit_data(previous, current, bisection)

    def test_full_finding_has_three_evidenced_levels(self):
        result = investigate_fixture(ROOT)
        self.assertEqual(result["component"]["component"], "perception.detector")
        self.assertEqual(result["checkpoint"]["current"], "ckpt-4")
        self.assertEqual(result["data"]["verdict"], "DATA_COMPOSITION")


if __name__ == "__main__":
    unittest.main()
