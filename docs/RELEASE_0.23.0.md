## 0.23.0 · comparison overview and clearer reports

- **Compare → Overview** pairs six summary columns with four dashboards:
  checkpoint arrival, matching quickdraw duration, recorded recovery and footwork
  observations with checked/hidden/unreviewed coverage. One athlete selection,
  reference and checkpoint apply throughout. Choose a quickdraw without extending
  the overview into a long list. The selected attempt's activity log is collapsed.
- **More metrics** adds charts below checkpoint, quickdraw and split tables, plus
  a footwork table and coverage-aware timeline. Time allocation follows its table.
- **HTML comparison and coaching reports** start with the same compact summary
  and dashboards. Offline route, athlete, reference, checkpoint and quickdraw
  controls update the presentation and selected evidence. Detailed timing tables,
  matched clip plots, unclassified gaps and raw logs remain available in Details.
  Coaching reports retain optional local video replay, coach observations and
  next-session actions. Repeated recovery donuts are removed.
- **PDF reports** print labels, values and coverage states, followed by evidence,
  actions and full timing/provenance appendices. Unicode fonts support athlete
  names and notes; charts use vector shapes with explicit labels and patterns.
- **Missing measurements stay unknown.** Recovery overlaps count once. Repeated
  checkpoint arrivals and repeated/unfinished or out-of-bounds clips do not enter
  comparable charts. Confirmed slips apply only to checked, visible footage;
  candidates and intentional feet-off time remain separate. These are observations,
  not a performance score or an explanation of a fall.
- **Export precision:** new comparison HTML includes a validated inert snapshot
  of the original measurements. Rebuilding from it preserves source-frame and PTS
  precision. Older HTML snapshots remain supported at their displayed precision;
  unavailable review flags and footwork are shown as unknown. Complete CSV/JSON
  outputs remain available. No video resampling, schema migration or new dependency.

Installed macOS/Windows apps use the existing compatibility-checked update flow.
Source checkouts can pull main and run with the pinned environment. Tests and
screenshots use fictional data and generated pixels; no private footage is shipped.
