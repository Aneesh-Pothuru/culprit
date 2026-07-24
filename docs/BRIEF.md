# 05 · CULPRIT

**The debugging agent for multi-model systems. It answers three questions
in order: which component caused this failure — which checkpoint
transition made that component regress — and what in the data changed to
cause it.**

`culprit` · Python · MCAP/ROS 2 + agent traces · counterfactual replay ·
checkpoint bisection · data audit

---

## Objective

A modern robot (or agent pipeline) is a stack of models: detector →
tracker → depth → fusion → predictor → planner → controller, often with a
VLM in the middle. When it fails — in simulation or in a live run — the
honest state of the art is an engineer scrubbing logs for six hours,
and the answer usually stops at "the detector was wrong," which is where
the *real* question starts.

CULPRIT automates the full descent:

1. **Component attribution.** Which model produced the failure, and at
   which step did it become unrecoverable? Proven by **counterfactual
   replay** — substitute ground truth for one component's output, re-run
   downstream, see if the failure disappears.
2. **Checkpoint diagnosis.** Given the culprit component, **bisect its
   checkpoint history**: replay the failing input across prior releases
   to find the exact transition where the behavior regressed — and
   confirm the previous checkpoint would have prevented the failure.
3. **Data audit.** Given the regressing transition, diagnose *why*: what
   changed between those two training runs — data manifests, slice
   composition, label distributions — and which training examples most
   influenced the failing behavior. Was it the data? Answer with
   evidence.

One sentence: **`git bisect` for a stack of models — down to the
component, the checkpoint, and the training data.**

---

## Why now

- **Attribution barely works and is measured.** Who&When (127 annotated
  multi-agent failure logs): best methods hit **53.5%** on the
  responsible agent, **14.2%** on the decisive step; o1 and R1 below
  practical usability ([ICML 2025 Spotlight](https://arxiv.org/abs/2505.00212)).
  A 14.2% ceiling is an invitation — and the structural reason it's
  beatable is that all incumbent methods *read logs*, while CULPRIT
  *re-runs the system*.
- **Robotics has the taxonomy, not the tool.** Failures divide cleanly
  into perception / planning / execution, and detection frameworks exist
  ([Recover](https://arxiv.org/pdf/2404.00756),
  [I-FailSense](https://arxiv.org/pdf/2509.16072)) — but production
  systems still handle failures implicitly: reject, page a human, safe-
  stop. Root cause is a manual craft.
- **The checkpoint/data layer is ready but unassembled.** Training-data
  attribution is practical at useful scale — TRAK is ~100× faster than
  comparable-efficacy methods ([TRAK](https://arxiv.org/pdf/2303.14186)),
  TracIn decomposes prediction changes along the training path — with
  known fragility caveats in distributed settings
  ([fragility](https://arxiv.org/pdf/2605.15520)). Nobody has wired TDA
  into a failure-debugging loop where the *failing production input*
  selects the query.
- **Adjacent fields solved their version.** Microservice RCA has working
  LLM-agent tooling over multi-modal observability
  ([TAMO](https://arxiv.org/pdf/2504.20462),
  [MicroRCA-Agent](https://arxiv.org/pdf/2509.15635)). The techniques
  transfer.
- **The logs exist.** MCAP is rosbag2's default since ROS 2 Iron;
  Foxglove/Rerun made replay routine
  ([tooling](https://foxglove.dev/robotics/rviz-vs-foxglove-vs-rerun)).

**The blog post this proves:** "which model broke the robot — and it was
the March data refresh." A real attribution number against a benchmark
you built. This is a paper, not just a project.

---

## Non-goals

- Not a visualizer (links out to Foxglove/Rerun).
- Not an online monitor; post-hoc on failed runs (live-failure logs are
  ingested the same as sim logs — "live" means the *source*, not
  real-time operation).
- Not automatic repair. It names, localizes, and evidences; the fix is
  human (a P2 emits the failing case as a regression test).

---

## Personas

| Persona | Cares about |
|---|---|
| **Systems engineer** with a bad run | "Which of the eleven models, and show me the counterfactual." |
| **Component owner** (detector team) | "Prove it's my model — then tell me which checkpoint and *why*." |
| **ML infra / data lead** | "Was the regression a data problem? Which refresh, which slice?" |
| **Triage lead** | "Are these 40 failures one root cause or forty?" |

---

## User journeys

### Journey 0 — the demo (no API key, <10 minutes)

```bash
git clone …/culprit && make demo
```

Ships a **toy three-component stack** (detector → planner → controller in
a 2D tabletop sim, all tiny CPU models) with a seeded fault and — the
part that shows the whole product — a seeded *history*: five checkpoints
of the detector, where ckpt-4's fine-tune data dropped low-light
examples. `make demo` replays a recorded investigation end to end:
component named by counterfactual, checkpoint transition found by
bisection, data diff showing the missing slice. One HTML report, three
verdicts deep. Then `culprit investigate --live` re-runs the whole thing
locally in ~5 minutes, CPU only, keyless.

### J1 — One bad run, one named component

A pick-and-place run fails; the arm closes on air.

```bash
culprit investigate run_01J8 --stack manipulation-v4
```

```
VERDICT   perception.depth_estimator          confidence 0.86
STEP      t=14.220s (frame 1707) — decisive step
CLAIM     depth underestimated the mug rim by 3.1cm; grasp pose
          inherited the error; planner and controller executed it faithfully

COUNTERFACTUAL  depth ← stereo reference   → grasp succeeds (8/10 seeds)
                detector ← reference        → still fails   (0/10)

RULED OUT  planner (correct given input) · controller (4mm tracking, in spec)
EVIDENCE   foxglove://…?t=14.2 · 3 replays · report.html
```

### J2 — Descend: which checkpoint regressed?

The depth team asks when this behavior appeared.

```bash
culprit bisect --component perception.depth_estimator \
               --input run_01J8@t=14.2 --history registry.yaml
```

CULPRIT replays the failing input (plus a small probe set of similar
cases) across the checkpoint history — binary search, log(n) evaluations:

```
ckpt v2025.11  PASS   ckpt v2026.01  PASS
ckpt v2026.03  FAIL   ← regression introduced here
ckpt v2026.05  FAIL   (current)

CONFIRMED  v2026.01 on the full failing run → task succeeds (7/10)
REGRESSION SET  38 probe inputs now failing that v2026.01 passed
```

The verdict upgrades: not just "depth is wrong" but "depth regressed at
the v2026.01 → v2026.03 transition, and rolling back fixes this failure."

### J3 — Descend again: was it the data?

```bash
culprit audit-data --transition v2026.01..v2026.03
```

Tiered, cheap-first:

```
TIER 1  manifest diff        training-set hash changed: +214k samples
                             (spring refresh), −9k (dedup pass)
TIER 2  slice analysis       low-light samples: 4.1% → 0.7% of training mix
                             regression set is 82% low-light  ← smoking gun
TIER 3  per-example TDA      (optional, GPU notebook) TracIn over the 38
                             regression cases → top influencers are the
                             dedup pass's removed near-duplicates

VERDICT  DATA_COMPOSITION    the dedup pass disproportionately removed
                             low-light examples; v2026.03 lost the slice
REMEDY   restore slice / reweight; failing cases exported as eval suite
```

The three tiers matter: manifest and slice analysis are free and answer
most cases; per-example attribution is reserved for when they don't,
and runs in a Kaggle notebook. When evidence is insufficient the verdict
is `UNDETERMINED` — with which tier fell short.

### J4 — Sim failures and live failures, same pipeline

Overnight, SIEVE flags 40 failing scenarios (sim); the field team uploads
2 MCAPs from live incidents. Both ingest identically. `culprit triage`
clusters all 42 by (component, signature): 23 are the depth/low-light
cluster — already diagnosed, linked to the open finding; 6 are
`ENV_DEFECT` (the scenario was broken, filed to SIEVE); 2 stay
`UNATTRIBUTED`, honestly.

### End-to-end journey (the product loop)

Failure arrives (sim sweep or live log) → ingest + normalize → deviation
scan ranks suspects → counterfactual replay names the component →
bisection names the checkpoint transition → data audit names the cause
class (`DATA_COMPOSITION` / `DATA_QUALITY` / `TRAINING_CONFIG` /
`UNDETERMINED`) → regression set exported as an eval suite (ASSAY) so
the failure can never silently return → finding cluster tracked until
the fixed checkpoint ships and the counterfactual confirms it.

---

## PRD

### P0 — component attribution (the descent's first rung)

| ID | Requirement |
|---|---|
| P0-1 | **Stack manifest** — components, dotted `actor` names, topics/trace keys, per-component **reference oracle** (ground truth channel > slow reference model > consistency check > none), determinism notes. |
| P0-2 | **Ingest** — MCAP/rosbag2 *and* agent traces (loopkit format) → one normalized actor-keyed timeline. Sim and live logs identical after ingest. |
| P0-3 | **Deviation scan** — cheap pass scoring every component's output against its oracle per step; ranked candidates before any replay. |
| P0-4 | **Counterfactual replay** — substitute a component's output with its oracle, deterministically re-run downstream, multi-seed; outcome-flip is the evidence. |
| P0-5 | **Decisive-step bisection** — earliest T where substitution flips the outcome; log(n) replays. |
| P0-6 | **Verdict report** — component, step, confidence *computed from counterfactual strength*, ruled-out list, `UNATTRIBUTED` when warranted, deep links (Foxglove/Rerun). |

### P0 — checkpoint & data diagnosis (the new rungs)

| ID | Requirement |
|---|---|
| P0-7 | **Checkpoint registry format** — per component: ordered checkpoints, each with training-data manifest hash, config hash, eval scores. (A YAML file; teams have this info, nobody links it.) |
| P0-8 | **Checkpoint bisection** — replay failing input + auto-built probe set across the history; find the regressing transition; confirm rollback fixes the original failure; emit the regression set. |
| P0-9 | **Data audit tiers 1–2** — manifest diff (what data changed between the two training runs) and slice analysis (composition shift vs. regression-set characteristics). Pure metadata + cheap inference; no training access needed. |
| P0-10 | **Cause-class verdicts** — `DATA_COMPOSITION`, `DATA_QUALITY` (label errors in influencers), `TRAINING_CONFIG`, `UNDETERMINED` — each with the evidence that earned it. |

### P1

| ID | Requirement |
|---|---|
| P1-1 | **Tier-3 TDA** — TracIn/TRAK-style per-example attribution over the regression set, packaged as a Kaggle/Colab notebook (GPU-free-tier), with the known fragility caveats stated in the output. |
| P1-2 | **Triage clustering** — many runs → few root causes; cluster→finding links. |
| P1-3 | **Attribution benchmark** — seeded-fault corpus for the robot path (built with SIEVE), Who&When for the agent path; publish both numbers. |
| P1-4 | **Regression-set export** — one command emits the failing cases as an ASSAY suite. |
| P1-5 | **Contested-verdict workflow** — re-run the counterfactual against a challenger checkpoint (`--substitute component=vX`). |

### P2

- Repair proposals (bias: regression test > patch).
- Cross-run causal graph (whose errors propagate furthest).
- Live-mode deviation scan (online flagging).

### Success metrics

| Metric | Target |
|---|---|
| Demo: clone → three-verdict report (component→checkpoint→data) | < 10 min replay, < 30 min live, $0, CPU |
| Responsible-component accuracy, seeded-fault benchmark | ≥ 85% |
| Decisive-step accuracy (±3 frames) | ≥ 60% |
| Who&When (agent path) | **beat 53.5% / 14.2%**, published |
| Checkpoint-transition identification on seeded regressions | ≥ 90% (it's bisection — should be near-perfect when replays are deterministic; publish where it isn't) |
| Data-audit cause-class accuracy on seeded data faults (composition shifts, label corruption, config changes) | ≥ 70%, per-class breakdown published |
| `UNATTRIBUTED`/`UNDETERMINED` rate | 10–20% — a system that never abstains is lying |
| Counterfactual reproducibility across seeds | ≥ 90% |

### Launch-day definition

`make demo` (keyless replay + live CPU re-run of the full descent),
seeded-fault benchmark with published component/checkpoint/data numbers,
Who&When agent-path number published, MCAP + agent-trace ingest both
working, LIMITS.md (oracle requirements, determinism requirements,
tier-3 caveats, abstention rates).

### Risks

| Risk | Mitigation |
|---|---|
| Replay nondeterminism | Determinism declared per-stack in the manifest; determinism score reported; confident verdicts refused below threshold |
| No oracle for a component | Graded oracle modes; oracle-less components can be ruled *in*, never out — stated in every report |
| TDA is fragile and expensive | It's tier 3 of 3, optional, notebook-packaged, caveats printed in the output; tiers 1–2 (metadata + slices) carry most cases |
| Checkpoint registry doesn't exist at most orgs | The format is deliberately trivial (one YAML); the demo shows why you want it; partial registries still support bisection over what exists |
| Multi-cause failures | Multi-culprit verdicts supported and benchmarked, not forced to single attribution |
| Politics — verdicts blame teams | Falsifiable by construction (contested-verdict re-runs), explicit ruled-out lists, honest abstention |

---

## System design

```
 MCAP / rosbag2 ─┐                       stack.yaml (components, oracles,
 agent traces ───┼─▶ ┌─────────┐          determinism) + registry.yaml
                 │   │ INGEST  │─▶ actor-keyed timeline    (checkpoints ×
                 └── └─────────┘        │                   data manifests)
                                        ▼
                          ┌──────────────────────┐
                          │   DEVIATION SCAN     │ outputs vs oracles, cheap
                          └──────────┬───────────┘
                                     ▼  ranked candidates
                          ┌──────────────────────┐   ┌─────────────────┐
                          │ HYPOTHESIS AGENT     │──▶│ REPLAY HARNESS  │
                          │ (LLM proposes;       │◀──│ deterministic,  │
                          │  replay disposes)    │   │ seeded, sandbox │
                          └──────────┬───────────┘   └─────────────────┘
                                     ▼
              STAGE 1: component verdict (counterfactual + step bisect)
                                     │ culprit component
                                     ▼
                          ┌──────────────────────┐
                          │ CHECKPOINT BISECTOR  │ failing input + probe set
                          │ (registry replay)    │ across history → transition
                          └──────────┬───────────┘
                                     ▼ regressing transition + regression set
                          ┌──────────────────────┐
                          │ DATA AUDITOR         │ T1 manifest diff
                          │ (tiered)             │ T2 slice analysis
                          │                      │ T3 TDA notebook (opt)
                          └──────────┬───────────┘
                                     ▼
                          ┌──────────────────────┐
                          │ VERDICT + REPORT     │ component → checkpoint →
                          │ (+ ASSAY export)     │ cause class, all evidenced
                          └──────────────────────┘
```

**One strong opinion, applied three times: propose cheaply, verify by
execution.** Stage 1: the LLM ranks suspects, the replay proves them.
Stage 2: bisection *is* execution — no reasoning required, just a good
probe set. Stage 3: metadata and slice statistics before per-example
attribution, and attribution output is labeled as *suggestive*, never as
proof (the fragility literature earns that label). Confidence always
comes from what re-ran, never from what a model asserted.

**The probe set makes bisection honest.** One failing input can flip for
irrelevant reasons; CULPRIT auto-builds a probe set of similar cases
(same slice signature) plus a control set of unrelated passing cases, so
a "regressing transition" means *the failure class* appeared there —
not one flaky sample.

**Sim and live converge at ingest.** Everything downstream of the
normalized timeline is source-agnostic; a SIEVE scenario failure and a
field MCAP get the same descent. That's the "simulation failures or
live-time failures" requirement, made structural.

### Interfaces

- **← SIEVE** — highest-volume input (failed scenarios, pre-partitioned);
  `ENV_DEFECT` findings route back.
- **← BATON** — agent traces; fork-at-checkpoint as the agent-side
  counterfactual (v0.3).
- **→ ASSAY** — regression sets export as suites; attribution accuracy is
  itself an ASSAY suite.
- **→ TERRARIUM** — an agent failure's minimal repro becomes a TERRARIUM
  task.
- **loopkit** — trace format is the shared spine.

### Milestones

| | Scope |
|---|---|
| **v0.1** | Toy stack + seeded history, ingest, deviation scan, counterfactual replay, component verdicts. **Journey 0 (stage 1) works.** |
| **v0.2** | Step bisection, checkpoint bisector + registry format, data audit tiers 1–2, full-descent demo. |
| **v0.3** | Agent-trace mode, Who&When run, seeded-fault benchmark, tier-3 notebook. **Launch** with published numbers. |
| **v1.0** | Triage clustering, contested verdicts, ASSAY export, write-up. |

### Stack & free tier

Python 3.12 · `mcap` + `mcap-ros2-support` · toy stack in pure
PyTorch-CPU (demo needs no GPU, no ROS install — ROS 2 replay via Docker
is the real-stack path) · SQLite for verdicts/registry · tier-3 TDA on
Kaggle/Colab free GPU · LLM hypothesis agent on Gemini free tier
(~10–30 requests per investigation) with `--no-llm` heuristic mode ·
reports static on GitHub Pages. Total required spend: **$0**.
