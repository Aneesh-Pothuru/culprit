(() => {
  "use strict";

  const COMPONENTS = [
    "perception.detector",
    "planning.planner",
    "control.controller",
  ];

  const makeFrames = (mode) => Array.from({ length: 12 }, (_, index) => {
    const target = index === 7;
    const lowLight = mode !== "nominal" && target;
    const detectorReference = mode === "oracle-limited" && target ? null : true;
    const detectorOutput = mode === "nominal" || !target;
    const detectorConfidence = target
      ? (mode === "nominal" ? 0.91 : mode === "oracle-limited" ? 0.34 : 0.12)
      : 0.92 - ((index % 3) * 0.02);
    const command = detectorOutput ? "grasp" : "hold";
    return {
      index,
      timestamp: Number((index / 10).toFixed(1)),
      scene: {
        lighting: lowLight ? "low" : "daylight",
        object_present: true,
        target_frame: target,
        exposure_ev: lowLight ? -2.1 : -0.2,
      },
      outputs: {
        "perception.detector": detectorOutput,
        "planning.planner": command,
        "control.controller": command,
      },
      references: {
        "perception.detector": detectorReference,
        "planning.planner": command,
        "control.controller": command,
      },
      detectorConfidence,
    };
  });

  const scenarios = {
    "incident-004": {
      number: "004",
      title: "Tabletop low-light miss",
      fixture: "tabletop-low-light-v1",
      status: "ATTRIBUTED",
      source: "checked-in Python fixture",
      scope: "Deterministic CPU toy stack. This case mirrors the checked-in Python artifact; it is not a production robotics claim.",
      frames: makeFrames("attributed"),
      decisiveFrame: 7,
      culprit: "perception.detector",
      flips: {
        "perception.detector": 1,
        "planning.planner": 0,
        "control.controller": 0,
      },
      checkpoint: { previous: "ckpt-3", current: "ckpt-4", evaluations: 2 },
      dataVerdict: "DATA_COMPOSITION",
      attributedReason: "oracle substitution reproducibly flipped the task outcome",
      missingEvidence: [],
      manifests: {
        previousLowLight: 0.041,
        currentLowLight: 0.007,
        regressionLowLight: 31 / 38,
      },
    },
    "incident-007": {
      number: "007",
      title: "Reference gap",
      fixture: "oracle-limited-preview",
      status: "UNATTRIBUTED",
      source: "illustrative abstention path",
      scope: "Illustrative embedded case for the shipped abstention policy. No component is named because a detector reference is unavailable and no tested substitution flips the outcome.",
      frames: makeFrames("oracle-limited"),
      decisiveFrame: 7,
      culprit: null,
      flips: {
        "perception.detector": 0,
        "planning.planner": 0,
        "control.controller": 0,
      },
      checkpoint: null,
      dataVerdict: null,
      attributedReason: "no available oracle substitution flipped the task outcome",
      missingEvidence: ["perception.detector ground-truth reference"],
      manifests: null,
    },
    "control-002": {
      number: "C02",
      title: "Daylight control",
      fixture: "nominal-control",
      status: "NOMINAL",
      source: "deterministic control preview",
      scope: "Deterministic nominal control. The task already succeeds, so CULPRIT does not open a causal investigation.",
      frames: makeFrames("nominal"),
      decisiveFrame: null,
      culprit: null,
      flips: {
        "perception.detector": 0,
        "planning.planner": 0,
        "control.controller": 0,
      },
      checkpoint: null,
      dataVerdict: null,
      attributedReason: "baseline task outcome passes",
      missingEvidence: [],
      manifests: null,
    },
  };

  const state = {
    scenarioId: "incident-004",
    frame: 7,
    playing: false,
    playbackRate: 1,
    timer: null,
    intervention: "perception.detector",
    replayResult: { component: "perception.detector", successes: 10, seeds: 10 },
    bisectionRan: true,
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let toastTimer;

  const timecode = (seconds) => {
    const milliseconds = Math.round(seconds * 1000);
    return `00:00:${String(Math.floor(milliseconds / 1000)).padStart(2, "0")}.${String(milliseconds % 1000).padStart(3, "0")}`;
  };

  const activeScenario = () => scenarios[state.scenarioId];
  const activeFrame = () => activeScenario().frames[state.frame];

  const showToast = (message) => {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 2200);
  };

  const copyText = async (text, message) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (_error) {
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    showToast(message);
  };

  const findingPayload = () => {
    const scenario = activeScenario();
    const frame = activeFrame();
    return {
      schema: "culprit-browser-finding-v1",
      generated_from: scenario.source,
      fixture: scenario.fixture,
      status: scenario.status,
      selected_frame: frame.index,
      timestamp: frame.timestamp,
      component: scenario.culprit
        ? {
            verdict: "ATTRIBUTED",
            actor: scenario.culprit,
            intervention: state.intervention,
            outcome_flips: scenario.flips,
            reason: scenario.attributedReason,
          }
        : {
            verdict: scenario.status === "NOMINAL" ? "NOT_APPLICABLE" : "UNATTRIBUTED",
            actor: null,
            outcome_flips: scenario.flips,
            reason: scenario.attributedReason,
            missing_evidence: scenario.missingEvidence,
          },
      checkpoint: scenario.checkpoint,
      data: scenario.dataVerdict && scenario.manifests
        ? {
            verdict: scenario.dataVerdict,
            tier: 2,
            low_light_share: scenario.manifests,
          }
        : null,
      limits: {
        raw_mcap: false,
        external_benchmark: false,
        tier3_tda: false,
        browser_execution: "embedded deterministic reconstruction; use the Python CLI for source generation",
      },
    };
  };

  const plainFinding = () => {
    const scenario = activeScenario();
    if (scenario.status === "ATTRIBUTED") {
      return `CULPRIT ${scenario.number}: ${scenario.culprit} caused the failure at frame 7 (0.7s). Its oracle substitution flipped 10/10 outcomes. Regression boundary: ckpt-3 → ckpt-4; rollback confirmed. Tier-2 finding: DATA_COMPOSITION, low-light share 4.1% → 0.7%, while 81.6% of the regression set is low-light. Scope: deterministic synthetic fixture.`;
    }
    if (scenario.status === "UNATTRIBUTED") {
      return `CULPRIT ${scenario.number}: UNATTRIBUTED. No available substitution flipped the outcome. Missing evidence: ${scenario.missingEvidence.join(", ")}. Checkpoint and data descent were not run. Scope: illustrative abstention path.`;
    }
    return `CULPRIT ${scenario.number}: NOMINAL. The daylight control completes the task; no causal investigation was opened.`;
  };

  const drawScene = () => {
    const canvas = $("#sceneCanvas");
    const context = canvas.getContext("2d");
    const box = canvas.getBoundingClientRect();
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.floor(box.width * ratio));
    canvas.height = Math.max(1, Math.floor(box.height * ratio));
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    const width = box.width;
    const height = box.height;
    const frame = activeFrame();
    const fault = activeScenario().status !== "NOMINAL" && frame.index === 7;

    const gradient = context.createLinearGradient(0, 0, width, height);
    gradient.addColorStop(0, fault ? "#292922" : "#3a3a34");
    gradient.addColorStop(.45, "#171816");
    gradient.addColorStop(1, "#060706");
    context.fillStyle = gradient;
    context.fillRect(0, 0, width, height);

    context.save();
    context.globalAlpha = .18;
    context.strokeStyle = "#b7b5aa";
    context.lineWidth = 1;
    for (let x = -height; x < width + height; x += 48) {
      context.beginPath();
      context.moveTo(x, 0);
      context.lineTo(x - height, height);
      context.stroke();
    }
    context.restore();

    context.beginPath();
    context.moveTo(width * .08, height * .49);
    context.lineTo(width * .93, height * .43);
    context.lineTo(width * .83, height * .94);
    context.lineTo(width * .02, height * .78);
    context.closePath();
    const tableGradient = context.createLinearGradient(0, height * .45, 0, height);
    tableGradient.addColorStop(0, "#5b5b54");
    tableGradient.addColorStop(1, "#171815");
    context.fillStyle = tableGradient;
    context.fill();
    context.strokeStyle = "#8b8980";
    context.globalAlpha = .55;
    context.stroke();
    context.globalAlpha = 1;

    const targetX = width * .63;
    const targetY = height * .56;
    const targetW = Math.max(34, width * .09);
    const targetH = Math.max(48, height * .16);
    const targetGradient = context.createLinearGradient(targetX, targetY, targetX + targetW, targetY);
    targetGradient.addColorStop(0, "#4f504b");
    targetGradient.addColorStop(.55, "#a2a096");
    targetGradient.addColorStop(1, "#292a27");
    context.fillStyle = targetGradient;
    context.beginPath();
    context.roundRect(targetX, targetY, targetW, targetH, [10, 10, 6, 6]);
    context.fill();
    context.strokeStyle = "#b7b5aa";
    context.stroke();
    context.beginPath();
    context.ellipse(targetX + targetW + 8, targetY + targetH * .46, 11, 17, 0, -Math.PI / 2, Math.PI / 2);
    context.stroke();

    const joint1 = { x: width * .03, y: height * .28 };
    const joint2 = { x: width * .28, y: height * (.31 + state.frame * .004) };
    const joint3 = { x: width * (.47 + state.frame * .006), y: height * .42 };
    context.lineCap = "round";
    context.strokeStyle = "#8a8980";
    context.lineWidth = Math.max(18, width * .035);
    context.beginPath();
    context.moveTo(joint1.x, joint1.y);
    context.lineTo(joint2.x, joint2.y);
    context.lineTo(joint3.x, joint3.y);
    context.stroke();
    context.strokeStyle = "#292a27";
    context.lineWidth = Math.max(12, width * .024);
    context.stroke();
    [joint1, joint2, joint3].forEach((joint, index) => {
      context.beginPath();
      context.arc(joint.x, joint.y, 14 - index * 2, 0, Math.PI * 2);
      context.fillStyle = "#a5a298";
      context.fill();
      context.strokeStyle = "#252623";
      context.lineWidth = 6;
      context.stroke();
    });
    context.strokeStyle = "#aaa89f";
    context.lineWidth = 5;
    context.beginPath();
    context.moveTo(joint3.x + 3, joint3.y);
    context.lineTo(joint3.x + 28, joint3.y - 13);
    context.moveTo(joint3.x + 3, joint3.y);
    context.lineTo(joint3.x + 28, joint3.y + 13);
    context.stroke();

    if (fault) {
      context.save();
      context.strokeStyle = "#ffb000";
      context.lineWidth = 2;
      context.setLineDash([7, 5]);
      context.strokeRect(targetX - 15, targetY - 18, targetW + 30, targetH + 36);
      context.setLineDash([]);
      context.fillStyle = "#ff4937";
      context.beginPath();
      context.arc(targetX + targetW / 2, targetY + targetH / 2, 4, 0, Math.PI * 2);
      context.fill();
      context.restore();
    } else {
      context.save();
      context.strokeStyle = activeScenario().status === "NOMINAL" ? "#83c890" : "#77766e";
      context.lineWidth = 1;
      context.strokeRect(targetX - 8, targetY - 10, targetW + 16, targetH + 20);
      context.restore();
    }
  };

  const drawOutcomeGraph = () => {
    const canvas = $("#outcomeGraph");
    const context = canvas.getContext("2d");
    const box = canvas.getBoundingClientRect();
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.max(1, Math.floor(box.width * ratio));
    canvas.height = Math.max(1, Math.floor(box.height * ratio));
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    const width = box.width;
    const height = box.height;
    const scenario = activeScenario();
    const colors = ["#ffb000", "#71d5d0", "#ddd8cb"];

    context.strokeStyle = "#292a26";
    context.lineWidth = 1;
    [0, .25, .5, .75, 1].forEach((value) => {
      const y = 10 + (height - 28) * (1 - value);
      context.beginPath();
      context.moveTo(14, y);
      context.lineTo(width - 14, y);
      context.stroke();
    });

    COMPONENTS.forEach((component, componentIndex) => {
      const groupStart = 22 + componentIndex * ((width - 44) / 3);
      const groupWidth = (width - 70) / 3;
      const rate = scenario.flips[component];
      const seeds = 10;
      for (let seed = 0; seed < seeds; seed += 1) {
        const x = groupStart + seed * (groupWidth / seeds);
        const flip = seed < Math.round(rate * seeds);
        const y = flip ? 13 : height - 21;
        context.fillStyle = flip ? colors[componentIndex] : "#393a35";
        context.fillRect(x, y, Math.max(3, groupWidth / seeds - 3), flip ? height - 34 : 4);
      }
    });

    if (scenario.status === "ATTRIBUTED") {
      context.fillStyle = "#ffb000";
      context.font = "700 8px monospace";
      context.fillText("CAUSAL SIGNAL", 25, 21);
    } else {
      context.fillStyle = "#77766f";
      context.font = "700 8px monospace";
      context.fillText(scenario.status === "NOMINAL" ? "NO FAILURE TO FLIP" : "NO DISCRIMINATING FLIP", 25, 21);
    }
  };

  const payloadForFrame = () => {
    const frame = activeFrame();
    return {
      frame: frame.index,
      timestamp: frame.timestamp,
      scene: frame.scene,
      outputs: frame.outputs,
      references: frame.references,
      detector_confidence: Number(frame.detectorConfidence.toFixed(2)),
    };
  };

  const renderTree = () => {
    const scenario = activeScenario();
    const tree = $("#evidenceTree");
    if (scenario.status === "ATTRIBUTED") {
      $("#treeStatus").textContent = "3 LEVELS EVIDENCED";
      tree.innerHTML = `
        <button type="button" class="tree-node is-proven" data-inspect="component"><span>A</span><i></i><strong>perception.detector</strong><small>10/10 outcome flips</small></button>
        <div class="tree-connector"><i></i><span>CAUSE</span></div>
        <button type="button" class="tree-node is-proven" data-inspect="checkpoint"><span>B</span><i></i><strong>ckpt-3 → ckpt-4</strong><small>rollback confirmed</small></button>
        <div class="tree-connector"><i></i><span>CAUSE</span></div>
        <button type="button" class="tree-node is-proven" data-inspect="slices"><span>C</span><i></i><strong>DATA_COMPOSITION</strong><small>low-light depleted</small></button>`;
    } else if (scenario.status === "UNATTRIBUTED") {
      $("#treeStatus").textContent = "DESCENT STOPPED";
      tree.innerHTML = `
        <button type="button" class="tree-node is-unresolved" data-inspect="component"><span>?</span><i></i><strong>UNATTRIBUTED</strong><small>no tested outcome flip</small></button>
        <div class="tree-connector"><i></i><span>STOP</span></div>
        <button type="button" class="tree-node is-locked" disabled><span>B</span><i></i><strong>checkpoint locked</strong><small>component gate required</small></button>
        <div class="tree-connector"><i></i><span>STOP</span></div>
        <button type="button" class="tree-node is-locked" disabled><span>C</span><i></i><strong>data verdict locked</strong><small>boundary gate required</small></button>`;
    } else {
      $("#treeStatus").textContent = "NO INCIDENT";
      tree.innerHTML = `
        <button type="button" class="tree-node is-proven" data-inspect="component"><span>✓</span><i></i><strong>NOMINAL OUTCOME</strong><small>grasp succeeds</small></button>
        <div class="tree-connector"><i></i><span>END</span></div>
        <button type="button" class="tree-node is-locked" disabled><span>B</span><i></i><strong>no bisection</strong><small>not applicable</small></button>
        <div class="tree-connector"><i></i><span>END</span></div>
        <button type="button" class="tree-node is-locked" disabled><span>C</span><i></i><strong>no data audit</strong><small>not applicable</small></button>`;
    }
    tree.querySelectorAll("[data-inspect]").forEach((button) => {
      button.addEventListener("click", () => {
        const destination = button.dataset.inspect === "slices" ? "slices" : "record";
        selectTab(destination);
      });
    });
  };

  const renderScenario = () => {
    const scenario = activeScenario();
    $("#caseId").textContent = `CASE // ${scenario.number}`;
    $("#caseTitle").textContent = scenario.title;
    $("#scopeText").textContent = scenario.scope;
    $$(".case-item").forEach((button) => button.classList.toggle("is-active", button.dataset.case === state.scenarioId));
    renderTree();

    const attributed = scenario.status === "ATTRIBUTED";
    const nominal = scenario.status === "NOMINAL";
    $$("#componentToggles button").forEach((button) => {
      const missingOracle = scenario.status === "UNATTRIBUTED"
        && button.dataset.component === "perception.detector";
      button.disabled = nominal || missingOracle;
      button.setAttribute("aria-pressed", String(!nominal && button.dataset.component === state.intervention));
    });
    $("#runReplay").disabled = nominal;
    $("#runHint").textContent = nominal ? "baseline already passes" : "10 deterministic seeds";
    $("#runBisection").disabled = !attributed;
    $$("#checkpointTrack button").forEach((button) => { button.disabled = !attributed; });
    $("#bisectionGate").textContent = attributed ? "ATTRIBUTION GATE PASSED" : "LOCKED · NO ATTRIBUTION";
    $("#checkpointTrack").style.opacity = attributed ? "1" : ".35";
    $("#bisectLog").innerHTML = attributed
      ? "<span><b>eval 01</b> ckpt-3 · PASS · narrow right</span><span><b>eval 02</b> ckpt-4 · FAIL · boundary found</span>"
      : `<span><b>not run</b> ${nominal ? "baseline outcome is nominal" : "component attribution is unresolved"}</span>`;

    const result = $("#replayResult");
    result.className = "replay-result";
    if (attributed) {
      result.innerHTML = "<span>LAST REPLAY</span><strong>OUTCOME FLIPPED · 10/10</strong><small>perception.detector reference applied</small>";
    } else if (nominal) {
      result.classList.add("is-unresolved");
      result.innerHTML = "<span>BASELINE</span><strong>TASK ALREADY PASSES</strong><small>no incident investigation opened</small>";
    } else {
      result.classList.add("is-unresolved");
      result.innerHTML = "<span>VERDICT</span><strong>UNATTRIBUTED · 0/10</strong><small>detector reference unavailable</small>";
    }

    $("#outcomeSummary").textContent = attributed
      ? "Detector oracle recovers the grasp; downstream substitutions do not."
      : nominal
        ? "The baseline succeeds; interventions do not produce a causal finding."
        : "No available substitution changes the failed outcome. The system abstains.";
    $("#graphLegend").innerHTML = COMPONENTS.map((component, index) => {
      const label = ["DETECTOR", "PLANNER", "CONTROL"][index];
      const key = ["detector-key", "planner-key", "control-key"][index];
      return `<span><i class="${key}"></i> ${label} <strong>${Math.round(scenario.flips[component] * 100)}%</strong></span>`;
    }).join("");
    $("#outcomeGraph").setAttribute("aria-label", `Outcome flip rates: detector ${scenario.flips["perception.detector"] * 100} percent, planner ${scenario.flips["planning.planner"] * 100} percent, controller ${scenario.flips["control.controller"] * 100} percent.`);

    if (attributed) {
      $("#sliceAudit").innerHTML = `
        <div><span>CKPT-3 · LOW LIGHT</span><i><b style="--slice:41%"></b></i><strong>4.1%</strong></div>
        <div><span>CKPT-4 · LOW LIGHT</span><i><b style="--slice:7%"></b></i><strong>0.7%</strong></div>
        <div class="regression-slice"><span>REGRESSION SET · LOW LIGHT</span><i><b style="--slice:81.6%"></b></i><strong>81.6%</strong></div>
        <dl><div><dt>Previous manifest</dt><dd>sha256:e8e05256…</dd></div><div><dt>Current manifest</dt><dd>sha256:4aab2c15…</dd></div><div><dt>Config hash</dt><dd>unchanged</dd></div><div><dt>Tier-3 TDA</dt><dd>not available</dd></div></dl>`;
      $("#recordList").innerHTML = "<div><dt>Finding schema</dt><dd>culprit-finding-v1</dd></div><div><dt>Determinism</dt><dd>1.00</dd></div><div><dt>Decisive step</dt><dd>frame 7 · 0.7s</dd></div><div><dt>Probe set</dt><dd>46 probes · 8 controls</dd></div><div><dt>Cause class</dt><dd>DATA_COMPOSITION</dd></div>";
    } else {
      $("#sliceAudit").innerHTML = `<p class="record-limit">${nominal ? "No data audit is needed for a passing control." : "Training-slice audit is locked. CULPRIT requires an attributed component and bounded checkpoint transition before making a data claim."}</p>`;
      $("#recordList").innerHTML = `<div><dt>Finding status</dt><dd>${scenario.status}</dd></div><div><dt>Component</dt><dd>none named</dd></div><div><dt>Checkpoint search</dt><dd>not run</dd></div><div><dt>Data verdict</dt><dd>not emitted</dd></div>`;
    }
    renderFrame();
  };

  const renderFrame = () => {
    const frame = activeFrame();
    const scenario = activeScenario();
    const fault = scenario.status !== "NOMINAL" && frame.index === 7;
    $("#frameReadout").textContent = `${String(frame.index).padStart(2, "0")} / 11`;
    $("#timecodeReadout").textContent = timecode(frame.timestamp);
    $("#dockTimecode").textContent = timecode(frame.timestamp);
    $("#timelineScrubber").value = String(frame.index);
    $("#detectorConfidence").textContent = frame.detectorConfidence.toFixed(2);
    $("#plannerCommand").textContent = frame.outputs["planning.planner"].toUpperCase();
    $("#controllerState").textContent = frame.outputs["control.controller"].toUpperCase();
    $("#sceneExposure").textContent = `EV ${frame.scene.exposure_ev < 0 ? "−" : "+"}${Math.abs(frame.scene.exposure_ev).toFixed(1)}`;
    $("#sceneOutcome").textContent = frame.index < 11
      ? "TASK // IN PROGRESS"
      : scenario.status === "NOMINAL" ? "TASK // PASSED" : "TASK // FAILED";
    $("#greaseAnnotation").classList.toggle("is-hidden", !fault);
    $("#sceneDescription").textContent = `Frame ${frame.index}: target present in ${frame.scene.lighting}. Detector output is ${frame.outputs["perception.detector"]}; reference is ${frame.references["perception.detector"] === null ? "unavailable" : frame.references["perception.detector"]}. Planner and controller command ${frame.outputs["planning.planner"]}.`;
    const payload = payloadForFrame();
    $("#payloadPath").textContent = `/frames/${frame.index}`;
    $("#payloadInspector").innerHTML = `<code>${escapeHtml(JSON.stringify(payload, null, 2))}</code>`;
    drawScene();
  };

  const escapeHtml = (value) => value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");

  const setFrame = (nextFrame) => {
    state.frame = Math.max(0, Math.min(11, nextFrame));
    renderFrame();
  };

  const stopPlayback = () => {
    state.playing = false;
    window.clearInterval(state.timer);
    state.timer = null;
    $("#togglePlayback").textContent = "▶";
    $("#togglePlayback").setAttribute("aria-label", "Play replay");
    $("#togglePlayback").setAttribute("aria-pressed", "false");
  };

  const startPlayback = () => {
    if (state.frame >= 11) setFrame(0);
    state.playing = true;
    $("#togglePlayback").textContent = "Ⅱ";
    $("#togglePlayback").setAttribute("aria-label", "Pause replay");
    $("#togglePlayback").setAttribute("aria-pressed", "true");
    const duration = reducedMotion.matches ? 750 : 500 / state.playbackRate;
    state.timer = window.setInterval(() => {
      if (state.frame >= 11) {
        stopPlayback();
        return;
      }
      setFrame(state.frame + 1);
    }, duration);
  };

  const selectTab = (name) => {
    $$(".inspector-tabs [role='tab']").forEach((tab) => {
      const selected = tab.dataset.tab === name;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    $$(".tab-panel").forEach((panel) => { panel.hidden = panel.id !== `panel-${name}`; });
  };

  const runReplay = () => {
    const scenario = activeScenario();
    const component = state.intervention;
    const result = $("#replayResult");
    const targetRate = scenario.flips[component];
    const seeds = 10;
    let completed = 0;
    result.className = "replay-result";
    result.innerHTML = `<span>REPLAYING LOCAL FIXTURE</span><strong>SEED 0 / ${seeds}</strong><small>${component} reference applied</small>`;
    $("#runReplay").disabled = true;

    const finish = () => {
      const successes = Math.round(targetRate * seeds);
      result.className = "replay-result";
      if (scenario.status === "UNATTRIBUTED") result.classList.add("is-unresolved");
      else if (successes === 0) result.classList.add("is-failed");
      result.innerHTML = `<span>COUNTERFACTUAL COMPLETE</span><strong>${successes > 0 ? "OUTCOME FLIPPED" : scenario.status === "UNATTRIBUTED" ? "UNATTRIBUTED" : "NO OUTCOME FLIP"} · ${successes}/${seeds}</strong><small>${component} reference applied</small>`;
      state.replayResult = { component, successes, seeds };
      $("#runReplay").disabled = scenario.status === "NOMINAL";
      showToast(successes > 0 ? "Causal signal reproduced across 10/10 seeds" : "No outcome flip; no causal claim");
    };

    if (reducedMotion.matches) {
      finish();
      return;
    }
    const replayTimer = window.setInterval(() => {
      completed += 1;
      result.querySelector("strong").textContent = `SEED ${completed} / ${seeds}`;
      if (completed >= seeds) {
        window.clearInterval(replayTimer);
        finish();
      }
    }, 65);
  };

  const runBisection = () => {
    const scenario = activeScenario();
    if (scenario.status !== "ATTRIBUTED") return;
    const log = $("#bisectLog");
    const button = $("#runBisection");
    button.disabled = true;
    log.innerHTML = "<span><b>search</b> evaluating probe set across bounded history…</span>";
    const steps = [
      "<span><b>eval 01</b> ckpt-3 · PASS · narrow right</span>",
      "<span><b>eval 02</b> ckpt-4 · FAIL · boundary found</span>",
    ];
    if (reducedMotion.matches) {
      log.innerHTML = steps.join("");
      button.disabled = false;
      showToast("Regression boundary reproduced: ckpt-3 → ckpt-4");
      return;
    }
    window.setTimeout(() => { log.innerHTML = steps[0]; }, 350);
    window.setTimeout(() => {
      log.insertAdjacentHTML("beforeend", steps[1]);
      button.disabled = false;
      showToast("Regression boundary reproduced: ckpt-3 → ckpt-4");
    }, 800);
  };

  const chooseScenario = (scenarioId) => {
    stopPlayback();
    state.scenarioId = scenarioId;
    state.frame = scenarios[scenarioId].decisiveFrame ?? 7;
    state.intervention = scenarios[scenarioId].status === "UNATTRIBUTED"
      ? "planning.planner"
      : "perception.detector";
    state.replayResult = null;
    renderScenario();
    drawOutcomeGraph();
    showToast(`${scenarios[scenarioId].title} loaded`);
  };

  $$(".case-item").forEach((button) => {
    button.addEventListener("click", () => chooseScenario(button.dataset.case));
  });

  $$("#componentToggles button").forEach((button) => {
    button.addEventListener("click", () => {
      state.intervention = button.dataset.component;
      $$("#componentToggles button").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
    });
  });

  $("#runReplay").addEventListener("click", runReplay);
  $("#runBisection").addEventListener("click", runBisection);
  $("#togglePlayback").addEventListener("click", () => state.playing ? stopPlayback() : startPlayback());
  $("#resetPlayback").addEventListener("click", () => { stopPlayback(); setFrame(0); });
  $("#previousFrame").addEventListener("click", () => { stopPlayback(); setFrame(state.frame - 1); });
  $("#nextFrame").addEventListener("click", () => { stopPlayback(); setFrame(state.frame + 1); });
  $("#timelineScrubber").addEventListener("input", (event) => { stopPlayback(); setFrame(Number(event.target.value)); });
  $("#playbackRate").addEventListener("click", () => {
    const rates = [1, 2, .5];
    const index = rates.indexOf(state.playbackRate);
    state.playbackRate = rates[(index + 1) % rates.length];
    $("#playbackRate").textContent = `${state.playbackRate}×`;
    if (state.playing) {
      stopPlayback();
      startPlayback();
    }
  });

  $$(".inspector-tabs [role='tab']").forEach((tab) => {
    tab.addEventListener("click", () => selectTab(tab.dataset.tab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const tabs = $$(".inspector-tabs [role='tab']");
      const direction = event.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(tabs.indexOf(tab) + direction + tabs.length) % tabs.length];
      next.focus();
      selectTab(next.dataset.tab);
    });
  });

  $("#copyPayload").addEventListener("click", () => copyText(JSON.stringify(payloadForFrame(), null, 2), "Selected frame payload copied"));
  $("#copyFinding").addEventListener("click", () => copyText(plainFinding(), "Finding copied"));
  $("#exportFinding").addEventListener("click", () => {
    const blob = new Blob([`${JSON.stringify(findingPayload(), null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `culprit-${activeScenario().number.toLowerCase()}-finding.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    showToast("Evidence packet exported");
  });

  window.addEventListener("keydown", (event) => {
    if (event.target.matches("input, button, a")) return;
    if (event.code === "Space") {
      event.preventDefault();
      state.playing ? stopPlayback() : startPlayback();
    } else if (event.key === "ArrowLeft") {
      stopPlayback();
      setFrame(state.frame - 1);
    } else if (event.key === "ArrowRight") {
      stopPlayback();
      setFrame(state.frame + 1);
    }
  });
  window.addEventListener("resize", () => {
    drawScene();
    drawOutcomeGraph();
  });

  renderScenario();
  drawOutcomeGraph();
})();
