# Climb Studio 0.24.0

Identify the athlete, session and route before measuring, and answer the clipping
method for each completed timer.

- Training sessions, optional teams, competition events/rounds and stable athlete
  and route identities; renaming an athlete preserves their history.
- Required batch video assignment with an unassigned preview queue for later
  identification. File dialog and drag/drop share this flow.
- Visible session/attempt navigation, athlete history and reassignment; different
  athletes can have separate bounded attempts in the same source recording.
- Personal training progress and explicit team/competition attempt selection;
  tables, dashboards, side by side and reports share the scope.
- Event-specific Direct / Two-stage / Cannot tell decisions after stopping a clip;
  unknown requires a reason, and forgotten answers have a persistent review queue.
- Separate missing/partial clip notes with no invented timing. Reports retain
  context, classifiable-method denominators and explicit draft status.
- Backed-up workspace migration, portable identity snapshots and format-2 project
  exports. Older labels and format-1 project imports remain readable.

[Workflow guide](https://github.com/slawek-private/climbing-efficiency-analyzer/blob/v0.24.0/docs/ATHLETE_SESSIONS.md). Original source checksums, frames, PTS,
recovery-union definitions and footwork coverage semantics are preserved.

Installed 0.19–0.23 apps can update through the compatibility manifest. Updating
does not infer identities or rewrite old labels in place; organizing old attempts
requires explicit assignment. New formats require 0.24 or later. Local backups
are kept before workspace/label conversion. macOS/Windows installers are built
and checked by the release workflow.
