# Coaching review

Use **Measure → Footwork** to expand the optional review controls. Keep the video
large with **View → Hide inspector**; running hand and foot timers remain visible.
**View → Appearance** offers System, Light, Dark and increased contrast.

## Mark observations before interpreting them

- **Mark left/right slip:** choose the original frame, confirm the limb and review
  state, then write what is visible. An intentional release is stored separately
  when intent is set to intentional. Use More for simultaneous or uncertain slips.
- **Both feet off:** start and stop at the original frames, then review intent and
  certainty. Neither foot may visibly contact a hold, wall, rock or volume. Smears,
  heel hooks and toe hooks count as contact. This observation does not measure
  force or prove that the arms bear the entire load.
- **Review coverage:** annotate non-overlapping reviewed or obscured intervals.
  Reviewed means both feet were visible and all slips and feet-off intervals in
  that interval were reviewed and annotated. Unmarked coverage stays unknown.
- **Fall onset:** for failed attempts, mark the frame where falling starts using
  More. It excludes fall flight. Until onset is reviewed, footwork totals stay
  unknown. The existing climb end/outcome remains a separate measurement.

Confirmed unplanned slips are counted only inside reviewed coverage. Intentional
cuts stay separate. Both-feet-off duration is intersected with the union of reviewed
coverage, clipped to climb boundaries and fall onset. Its percentage uses reviewed
seconds as the denominator. An unresolved feet-off interval overlapping reviewed
coverage keeps duration totals unknown. A running timer is a recoverable draft.
A reviewed interval with no events is a reviewed zero; absent coverage is unknown.
There is no technique score, fatigue inference or automated causal explanation.

Example: a 60-second climb with 6 seconds obscured has 54 reviewed seconds.
Two confirmed slips and 2.4 seconds feet off give 4.4% of reviewed time, split into
1.6 seconds intentional and 0.8 seconds unplanned. A candidate in the hidden
section does not become a confirmed slip.

Select an observation or a Feet timeline marker to edit it. **Replay** loops the
moment with two seconds of context on either side; Pause or a manual seek stops
that loop. Undo/redo, autosave and project exports include the new observations.

## Agree the next session

**Coaching goal and context** records the goal, athlete reflection, agreed next
action and next-session check, plus discipline, route grade, wall angle and route
familiarity. Observation, coach interpretation and agreed action are separate
fields on each footwork event. These are human-entered judgments, not model results.

**Export → Coaching review** uses the current attempt or the selected comparison
attempts. The report leads with the goal, coverage, up to three key moments,
reflection and next action. Expand the full evidence index for all observations,
hand intervals, checkpoint comments and source frame/PTS provenance. Multiple
attempts include matched named checkpoint arrivals relative to each climb start;
the first selected attempt is the reference. Different routes and ambiguous or
missing arrivals have no comparison delta. Timing differences are not ability ranks.

Choose the media scope explicitly:

| Choice | What it contains | Sharing |
| --- | --- | --- |
| Measurements only (default) | HTML, event/summary CSV and JSON; optional PDF | No footage included |
| Link originals | Replay links to local original files | Requires the same paths and a browser that supports the codec |
| Portable sections and stills | H.264 review clips and evidence PNGs in a sibling media folder | Share the HTML **and** its media folder |

Portable sections preserve one encoded frame per selected source frame and the
source PTS spacing; frame rate is not equalized or interpolated. Pixels are
compressed and may be cropped by one edge pixel for even H.264 dimensions.
A prepared local preview is preferred for extraction when available. Source SHA256,
frame, PTS and time base remain attached to the observations; the JSON includes
full attempt snapshots and clip mappings. Missing or mismatched sources stop media
export. Export runs in the background and supports cancellation; failed exports
leave the previous report intact. Existing label files are protected from sidecar
overwrites. No footage is uploaded and no external fonts or scripts are loaded.

PDFs contain static evidence and, when portable media is chosen, highlighted
stills. Replay is in the HTML. The app's preview-cache budget does not delete your
exported reports/media. Remove older report media folders yourself when no longer
needed. Names can be replaced with Athlete 1, Athlete 2, etc.; this does not redact
faces or names in notes. Keep exports private unless sharing is intended.

## Reproduce outside the GUI

```sh
uv run --no-sync python -m viewer.coaching_report --labels labels --output artifacts/coaching/review.html --pdf
uv run --no-sync python -m viewer.coaching_report --labels labels/attempt.labels.json --output artifacts/coaching/with-video.html --media clips --video-dir videos --pdf
```

`--labels` accepts one or more files/folders. `--video-dir` contains originals with
filenames matching the labels. `--cache-root` can point at the app data root to
reuse prepared previews; `--include-hands` includes all hand/point video sections.
`--anonymous` replaces athlete names. CLI output stays local.

## Compatibility

Labels remain schema 1.2 until a coaching or footwork feature is saved; then the
schema becomes 1.3, with definition version 1.0.0. The source identity is unchanged.
Saving over older labels creates a sibling `.pre-coaching-backup.json` once,
retaining the previous document. Older apps cannot read schema 1.3; restore that
backup only when deliberately returning to an older version. New apps read older
labels without inventing measurements.

These features implement the literature-informed design review. No professional
coach interviews or field validation are claimed. A coach/athlete pilot remains a
separate evaluation before adding inferred technique ratings.

Recording file-quality guidance was checked against [Google Photos backup
quality](https://support.google.com/photos/answer/6220791) and [YouTube upload
processing](https://support.google.com/youtube/answer/71674). Keep the exact original
file used for measurements, even when a service preserves its captured quality.
