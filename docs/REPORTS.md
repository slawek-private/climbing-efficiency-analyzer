# Regenerating offline comparison reports

The committed generator contains no private footage or fixed athlete results.
It accepts either saved label files or an HTML export snapshot. All output is
local, with embedded SVG charts and no network assets. Age is not used.

## From an exported HTML snapshot

```sh
uv run --no-sync python -m viewer.report_cli --source artifacts/reports/all-athletes-labelled-v2.html --output artifacts/reports/comparison.html --focus "Athlete A" --route "Blue route 7c+/8a"
```

Only the supplied HTML is read for measurements. New (0.23+) comparison exports
contain a validated inert JSON snapshot of the original labels; dashboards can
therefore retain full stored precision, including source frames and PTS. Older
HTML snapshots are still accepted at their displayed precision; footwork and
review flags missing from them remain unknown. Source files are not overwritten.

Reports start with a six-column overview and four dashboards: selected checkpoint
arrival, matching quickdraw duration, recorded recovery, and footwork observations
with explicit coverage. Route, athlete, reference, checkpoint and quickdraw controls
work offline. Additional timing tables and charts sit in Details, with raw activity
logs and source provenance. Recovery donuts and ability rankings are absent.

## From saved labels

```sh
uv run --no-sync python -m viewer.report_cli --labels videos --output artifacts/reports/comparison.html --focus "Athlete A"
```

`--labels` accepts a folder of `*.labels.json` or one label file. It validates
the labels and saves a source HTML/CSV snapshot before building the focused
report. Prefer labels when full stored precision is needed; the overview export
itself displays rounded values. `--focus` is optional and must identify exactly
one athlete/attempt in the exported collection. Choose any athlete's name.

The app's **Export all athletes** also produces charts and CSV tables directly.
CLI outputs include a JSON provenance file with the input SHA256 and a focus-gap
CSV when focus is requested. Full activity logs and outcome fields are retained
when present in the source export. Old HTML without an outcome column cannot
recover fall/top results; save/export again from the viewer to include them.

Combined recovery is the union of dedicated rest and chalking across hands,
clipped to climb boundaries. Rest/chalk overlaps count once. Gaps subtract that
union within the gap. Remaining time is unclassified, not verified movement.
Absent annotations are unknown, not zero; lower rest does not establish why
an athlete fell. No causal or age-adjusted ability rankings are calculated.

Keep source reports, output reports, labels, cache frames and videos under the
ignored private directories. Do not upload them to CI or commit them.

## PDF output

Add `--pdf artifacts/reports/comparison.pdf` to either command. PDF generation uses ReportLab locally: vector charts, repeated table headers, page numbers, matching timing comparisons, footwork coverage, evidence and full event tables. PDF files and their telemetry stay outside Git.

## Coaching reports (0.21.0)

**Export → Coaching review** generates a goal-led HTML report from current or
selected attempts with optional local replay sections and stills, printable PDF,
event/summary CSV and full JSON attempt snapshots. Footage is excluded by default.
Coverage and fall onset determine which reviewed footwork metrics are available.
Both export paths now use the same overview. For goal-led evidence and optional
local video sections use `python -m viewer.coaching_report`; see the
[coaching guide](COACHING_REVIEW.md) for commands, media scope, compatibility and
precise measurement definitions.
