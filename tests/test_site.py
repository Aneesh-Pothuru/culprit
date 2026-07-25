import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentInventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.links = []

    def handle_starttag(self, _tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if "href" in attributes:
            self.links.append(attributes["href"])


class ProductSiteTests(unittest.TestCase):
    def test_pages_parse_with_unique_ids_and_resolved_local_links(self):
        for path in (ROOT / "docs" / "index.html", ROOT / "docs" / "app" / "index.html"):
            parser = DocumentInventory()
            parser.feed(path.read_text())
            parser.close()
            self.assertEqual(len(parser.ids), len(set(parser.ids)), path)
            for target in parser.links:
                if target.startswith(("https://", "http://", "#")):
                    continue
                clean_target = target.split("#", 1)[0]
                candidate = path.parent / clean_target
                if clean_target.endswith("/"):
                    candidate /= "index.html"
                self.assertTrue(candidate.exists(), f"{path}: missing {target}")

    def test_workbench_exposes_every_required_interaction(self):
        document = (ROOT / "docs" / "app" / "index.html").read_text()
        expected_controls = {
            "timelineScrubber",
            "togglePlayback",
            "previousFrame",
            "nextFrame",
            "resetPlayback",
            "componentToggles",
            "runReplay",
            "runBisection",
            "outcomeGraph",
            "evidenceTree",
            "sliceAudit",
            "payloadInspector",
            "copyFinding",
            "exportFinding",
        }
        found_ids = set(re.findall(r'\bid="([^"]+)"', document))
        self.assertTrue(expected_controls.issubset(found_ids))

    def test_browser_fixture_preserves_authoritative_verdicts_and_abstention(self):
        script = (ROOT / "docs" / "app" / "app.js").read_text()
        for evidence in (
            "perception.detector",
            "decisiveFrame: 7",
            'previous: "ckpt-3"',
            'current: "ckpt-4"',
            'dataVerdict: "DATA_COMPOSITION"',
            'status: "UNATTRIBUTED"',
            "missing_evidence",
        ):
            self.assertIn(evidence, script)

    def test_evidence_tabs_use_one_keyboard_tab_stop(self):
        document = (ROOT / "docs" / "app" / "index.html").read_text()
        self.assertEqual(document.count('role="tab"'), 3)
        self.assertEqual(document.count('tabindex="0"'), 1)
        self.assertEqual(document.count('tabindex="-1"'), 2)
        script = (ROOT / "docs" / "app" / "app.js").read_text()
        self.assertIn("tab.tabIndex = selected ? 0 : -1;", script)


if __name__ == "__main__":
    unittest.main()
