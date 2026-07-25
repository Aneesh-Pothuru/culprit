# CULPRIT product and UX research

Reviewed 2026-07-24 against primary product documentation, research papers,
and investigation guidance. CULPRIT is not trying to replace a robotics data
viewer. Its product surface starts where synchronized inspection ends: test a
causal hypothesis, find the regressing checkpoint, and connect that transition
to training-data evidence.

## Competitive patterns

| Source | Relevant surface | Pattern retained | Deliberate difference |
| --- | --- | --- | --- |
| [Foxglove visualization](https://foxglove.dev/product/visualization) and [timeline-aware log panel](https://docs.foxglove.dev/docs/visualization/panels/log) | multimodal robotics investigation | A shared playhead must coordinate imagery-like context, messages, plots, and selected events. Event markers should jump directly to the relevant moment. | CULPRIT uses one prescribed reconstruction layout and turns a selected moment into an executable counterfactual, instead of offering a general panel builder. |
| [Rerun Viewer overview](https://rerun.io/docs/reference/viewer/overview), [timeline](https://rerun.io/docs/reference/viewer/timeline), and [navigation model](https://rerun.io/docs/getting-started/configure-the-viewer/navigating-the-viewer) | temporal/spatial debugging | Central viewport, entity/evidence hierarchy, selection details, scrubber, play/pause/step, and synchronized streams form a strong investigation grammar. | CULPRIT fixes the hierarchy to component → checkpoint → data and makes the outcome-flip test the primary action. |
| [NASA mishap investigation](https://sma.nasa.gov/sma-disciplines/mishap-investigation) and [NPR 8621.1B](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_8621_001B_&page_name=all) | structured incident investigation | Preserve evidence, reconstruct a timeline, distinguish events from conditions, test cause/effect, and produce an event-and-causal-factor tree. | The workbench visually separates observation, intervention, inference, and abstention; it never presents a correlation as a proven cause. |
| [Who&When](https://arxiv.org/abs/2505.00212) | multi-agent failure attribution research | Responsible actor and decisive step are separate questions, and both need measured evidence. | The shipped fixture makes no Who&When benchmark claim. It demonstrates deterministic re-execution only. |
| [TRAK](https://proceedings.mlr.press/v202/park23c.html) and [TracIn](https://arxiv.org/abs/2002.08484) | training-data attribution | Training examples can be connected to model behavior, but cost and approximation quality must remain visible. | v0.1 stops at manifest and slice evidence (tier 2). Tier-3 example influence is labelled unavailable rather than simulated. |

## Product direction

The interface is a cinematic evidence room rather than a generic dashboard:

- A **timecode spine** is the primary navigation. Playback, steps, event
  markers, logs, telemetry, and the scene reconstruction share one playhead.
- A **monochrome reconstruction field** shows the tabletop scene as a
  deterministic canvas rendering. Amber grease-pencil annotations appear only
  at evidenced moments.
- A spatial **causal descent** connects the detector outcome flip to the
  `ckpt-3 → ckpt-4` boundary and then to the depleted low-light slice.
- Every finding labels its epistemic state: recorded observation, deterministic
  replay, inferred boundary, ruled out, or unavailable.
- The interface makes the negative path first-class. When no substitution
  flips the outcome, the tree stops at `UNATTRIBUTED` and checkpoint/data
  controls remain unavailable.

## Journey-driven information architecture

1. **Landing / briefing** — states the problem, thesis, evidence standard,
   proof fixture, mechanism, architecture, and limits.
2. **Reconstruction workbench** — select a case, replay time, inspect payloads,
   intervene on components, run counterfactuals, bisect checkpoints, audit
   training slices, and export a finding.
3. **Generated finding** — retains the Python-produced static report as an
   auditable artifact under `docs/demo/`.
4. **Repository evidence** — links the interface back to the deterministic
   Python implementation, fixtures, tests, and explicit limits.

## Accessibility and responsive decisions

- All controls are native buttons, inputs, links, or tabs with programmatic
  names, visible focus, and keyboard operation.
- The canvas reconstruction is accompanied by a live textual scene
  description and tabular/payload equivalents for graphs.
- Color is never the only status cue; verdict words and line/marker shapes are
  also used.
- Motion respects `prefers-reduced-motion`; playback remains manually
  step-able.
- Desktop uses an evidence-room layout. Narrow screens linearize case,
  reconstruction, analysis, and timecode without hiding functionality.
