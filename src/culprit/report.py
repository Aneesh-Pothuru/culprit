from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def write_finding(path: Path, finding: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_name("finding.json").write_text(
        json.dumps(finding, indent=2, sort_keys=True) + "\n"
    )
    component = finding["component"]
    step = finding["decisive_step"]
    checkpoint = finding["checkpoint"]
    data = finding["data"]
    counterfactual_rows = "\n".join(
        "<tr><td>{}</td><td>{}/{}</td><td>{:.0%}</td></tr>".format(
            html.escape(item["actor"]),
            item["successes"],
            item["seeds"],
            item["flip_rate"],
        )
        for item in component["counterfactuals"]
    )
    regression_set = checkpoint["regression_set"]
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CULPRIT — three-stage finding</title>
<style>
body{{font:16px/1.5 system-ui;max-width:980px;margin:3rem auto;padding:0 1rem;color:#19212b}}
.stage{{border-left:5px solid #8b1e2d;padding:1rem 1.4rem;margin:1.5rem 0;background:#f7f8fa}}
.verdict{{font-weight:800;color:#8b1e2d}} table{{border-collapse:collapse;width:100%}}
th,td{{padding:.45rem;border-bottom:1px solid #ddd;text-align:left}} code{{font-size:.85rem}}
</style></head><body>
<p>CULPRIT / deterministic tabletop investigation</p>
<h1>One failure, three evidenced verdicts</h1>
<section class="stage"><h2>1 · Component</h2>
<p class="verdict">{html.escape(component["component"])}</p>
<p>Confidence {component["confidence"]:.0%}; decisive frame {step["frame"]}
at t={step["timestamp"]:.1f}s, found in {step["replays"]} replays.</p>
<p>Ruled out: {", ".join(component["ruled_out"])}</p>
<table><thead><tr><th>Substitution</th><th>Successes</th><th>Outcome flips</th></tr></thead>
<tbody>{counterfactual_rows}</tbody></table></section>
<section class="stage"><h2>2 · Checkpoint</h2>
<p class="verdict">{checkpoint["previous"]} → {checkpoint["current"]}</p>
<p>Rollback confirmed: {str(checkpoint["rollback_confirmed"]).lower()}.
Binary-search evaluations: {checkpoint["evaluations"]}. Regression set:
{len(regression_set)} cases; controls: {checkpoint["control_count"]}.</p></section>
<section class="stage"><h2>3 · Data</h2>
<p class="verdict">{data["verdict"]}</p><p>{html.escape(data["reason"])}</p>
<p>Low-light share:
{data["manifest_diff"]["previous_low_light_share"]:.1%} →
{data["manifest_diff"]["current_low_light_share"]:.1%}; regression set
{data["manifest_diff"]["regression_set_low_light_share"]:.1%} low-light.</p></section>
<h2>Scope</h2>
<p>This report is generated from a synthetic deterministic fixture. Raw MCAP,
Who&amp;When, public checkpoint, and tier-3 TDA claims are not made. See
LIMITS.md.</p>
</body></html>
"""
    path.write_text(document)

