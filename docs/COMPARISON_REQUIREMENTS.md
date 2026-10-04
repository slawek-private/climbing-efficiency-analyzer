# Climber comparison on the blue route

Scope clarified 2026-10-04: compare the climbers' attempts on the same blue
route. Current local footage contains eight MOV files. File names are provisional
attempt identifiers, not verified climber identities. Processing remains local.

This is a requirements draft within M0, not a completed M1 metrics specification
or an accuracy claim. A metric whose events cannot be established must be
unavailable with a reason, rather than zero or a plausible estimate.

## Intended comparison table

The primary presentation is a detailed, self-contained **HTML report**, readable
offline on the workstation. Include a searchable comparison table, expandable
per-attempt detail, rest/contact/clip timelines when validated events exist,
measurement definitions, per-event confidence, quality verdicts and reasons for
unavailable values. Support printing/saving to PDF. No external assets, telemetry
or uploads. Keep HTML artifacts with private local results, outside Git.

The initial report at `artifacts/reports/blue-route-report.html` contains the
eight-video inventory and explicit unavailable measurements. It is not an
analytical result. Regenerate it with `python tools/build_html_report.py`.

One row per attempt: attempt/climber ID, outcome (completed, failure, abandoned,
or unknown), measured climbing time, time to failure when observable, furthest
blue hold reached, unique blue holds contacted, progress speed, rest count,
total rest time and rest share of climbing time. Include confidence/quality
and missing-data indicators. Keep preparation, lowering and footage after the
attempt outside the comparison interval.

## Accepted timing definition and remaining definitions

The user's final clarification supersedes holds gained per minute: the primary
comparison called "speed" is **climb duration**, from the first hand grip on
blue hold 1 until the climber first weights the rope. Lower duration is faster
only when comparing equivalent progress/outcomes. Rest time remains included.
This is elapsed time in seconds, not distance or holds per unit time.

| Measurement | Proposed definition | Required evidence |
| --- | --- | --- |
| Start | First grip by either hand on blue-route hold 1. No upward movement or release of the ground is required. A persistence check may confirm the grip but must backdate start to its onset. | Verified hold 1 identity, hand contact and presentation timestamp. |
| Climbing time / speed comparison | Elapsed seconds from start to first rope-weighting, including all intervening rests. This is the user's primary comparison. | Explicit start and rope-weighting boundaries, presentation timestamps. |
| Time to failure | Same interval as climbing time for a failed attempt: stop when the climber first weights the rope. A fall's onset is not the endpoint unless rope-weighting occurs then. | Visible evidence of rope support; rope tension or static resting alone does not establish loading. |
| Holds reached | Unique numbered blue-route holds with a sustained hand contact. Also show furthest progression rank; rank and unique contact count are different. Regrabs do not increase unique count. | Common route hold map and confirmed hand contacts. |
| Hold-to-hold timing | Optional supporting contact-to-contact durations; holds gained per minute is not the requested primary speed metric. | Common route ordering and timestamps. |
| Rest count | Separate stationary recovery intervals, allowing hand shaking/switches while hip progression stays low. A moving reach alone is not a rest. Thresholds and treatment of planning pauses remain to be validated. | Registered hip motion, hand contacts and temporal evidence. |
| Rest duration/share | Sum of rest intervals within the attempt; divide by measured climbing time. | Observable intervals; overlap counted once. |
| Hand rest | For each rest, time each hand is off the wall and number of hand switches. Occluded hands are unknown unless supported by other evidence. | Contact states with uncertainty. |

A completed climb should report time to completion, with time to failure marked
not applicable. A recording that cuts off should report an incomplete observation,
not a failure. Multiple attempts in one video need separate attempt intervals.
Rope hangs, falls, rests and lowering must be distinct states.

If recording begins with a hand already gripping hold 1, the true start is
unobserved: do not substitute video timestamp zero. If rope-weighting is hidden
or its evidence is ambiguous, report an uncertain boundary or unavailable
duration. Video alone does not directly measure rope force. Completion and
intentional post-completion lowering must not be labelled failure merely because
the rope eventually carries weight.

Rest count, total rest duration, rest share, unique hand holds reached and furthest
hold reached use the same start-to-rope-weighting comparison interval for failed
attempts. Their operational thresholds still need ground-truth validation.

## Fair comparison

Compare equivalent route sections as well as whole attempts: someone who falls
early has less opportunity to accumulate rests. Show progress alongside duration
and rest counts. Route-wide totals are unavailable if the camera misses required
events. Use identical thresholds across climbers; do not tune each attempt to
make its results look reasonable. Report duration error and event precision/
recall against labels before calling any comparison accurate.

The common blue hold map needs stable identifiers across videos despite changes
in viewpoint. Colour alone does not establish route identity. Vertical speed
in metres requires calibration; pixel displacement under camera movement cannot
be presented as physical speed.

## Current evidence and milestone boundary

The existing M0 models do not yet establish reliable blue-route contacts, rests,
failure or progress. No comparison numbers have been calculated. The original
three-video benchmark describes the files present at that time; the current
Current file hashes and container metadata are private in
`artifacts/video_inventory.json`. Container durations are inventory metadata,
not climbing times.

The comparison goal guides M0 candidate selection and later milestones. Human
labels for evaluation are allowed; the eventual analysis command must need no
manual tagging at runtime. Rest and failure labels will be needed to validate
the proposed measurements. Stop for milestone review before production work.
