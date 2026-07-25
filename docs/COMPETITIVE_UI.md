# Competitive UI review

Reviewed 2026-07-24 against robotics visualization and AI trace-debugging
interfaces.

| Product | Relevant surface | What works |
| --- | --- | --- |
| [Foxglove](https://foxglove.dev/product/visualization) | multimodal robotics investigation | Time-synchronized panels connect what the system perceived, decided, and did at the decisive moment. |
| [Rerun](https://rerun.io/docs/getting-started/configure-the-viewer) | temporal visual debugging | A central viewport, entity hierarchy, selection detail, and scrubber preserve spatial and temporal context. |
| [Arize Phoenix](https://arize.com/docs/phoenix/) | AI troubleshooting | Trace-first navigation connects a failure to the exact model, tool, or retrieval span. |
| [LangSmith](https://www.langchain.com/langsmith/observability) | agent trace debugging | Nested calls, timing, inputs, and outputs support descent from symptom to responsible step. |

## Direction adopted

- Turn the three verdicts into a connected causal descent: component →
  checkpoint → data.
- Make counterfactual outcome flips and replay counts the visual source of
  confidence.
- Mark the decisive frame on a compact time rail and retain ruled-out actors.
- Use warm amber for investigation, red for the proven regression boundary,
  and cyan for replay evidence.
- Keep the synthetic scope visible in the primary workspace, not buried in a
  footer.

The result is a forensic workbench rather than a static incident summary.
