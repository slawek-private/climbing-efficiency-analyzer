# Athletes, sessions and clipping review

A project is a local container. **New session…** declares Training, or a Competition
event and round. Give it a name/date and an optional team or training goal. The
header always shows the selected session.

**Athletes & sessions** creates athletes, edits names/distinguishing labels and
optional teams, shows athlete history, creates route versions and organizes older
attempts. Two people with the same name need different distinguishing labels.
Names never merge IDs. Create another route version after a physical reset, even
when the colour/name stays the same.

## Add and assign videos

Adding or dropping videos opens an assignment sheet. Choose a session and an
athlete/route version for every row. Check rows and **Assign to checked rows** for
a batch; names stay visible before confirmation. Create athletes/routes inline.
Nothing guesses identity from a filename or silently uses the previous athlete.

**Queue files · assign later** adds files for inspection and optional bulk previews.
They cannot start new measurements until assigned. In **Videos**, filter the
current session, all sessions or needs-assignment items, and athlete/route IDs.
**Assign selected…** and the analysis **Assign athlete…** button finish assignment.
Technical metadata stays under Show recording details.

One recording can contain several athletes' climbs. **New attempt** confirms the
next athlete/session/route, then you mark its boundaries. Attempts have stable IDs
and display numbers within athlete/session/route. Source checksum, frame numbering
and presentation timestamps stay intact. The attempt selector groups an athlete's
attempts and marks the current one. Multiple camera angles of one attempt still
need a separate source-synchronization design.

## Compare the intended work

Training defaults to **athlete progress** in the current session/route version.
**Include previous training sessions** explicitly widens that scope; choose the
exact attempts to include. **Team review** and Competition start with an empty
selection. **Choose athletes & attempts** selects attempts under each athlete.
Team review can also filter an optional team roster recorded with each attempt.
The reference must be included. Competition stays within the selected event/round;
different route IDs and training versus competition cannot silently mix.
Annotated timing is not an official result or athlete ranking.

Tables, dashboards, side by side and exports share the same selection. Reports show
session/route context; CSV/JSON retain IDs and snapshots. Session names/dates
identify repeated attempts in charts and video overlays.

## Decide the method of each completed clip

Start/stop each hand timer as before. Stopping saves the exact interval immediately
and opens **Clipping review** for that event. Choose:

- **Direct:** no observed mouth-held rope stage.
- **Two-stage · rope in mouth:** observed rope held in the mouth before clipping.
- **Cannot tell:** select Hands/rope hidden, Camera misses the method, or Visible
  but unclear. A reason resolves the decision while retaining an unknown method.

No answer is a draft, not a presumed direct clip. Choices never copy to the other
hand or the next clip. Existing started timers retain their stored method. Use the
clip selector or persistent **clip answers needed** button to review forgotten
decisions at their exact frames. Undo/redo, autosave, restart and video switching
preserve the queue. Legacy draft timers can stop before organizing their identity.

**Clip not recorded…** stores a visibility note with an optional known quickdraw
and the current reference frame. It never invents a start/end/duration. A gap at
a known draw excludes that draw's partial timing/method from comparisons;
unknown-number gaps remain notes and are not guessed onto other clips. Skipped
draw numbers do not automatically create missing clips.

Method counts are inside the climb. The direct/two-stage denominator includes
only those two classifiable methods; unknown and unanswered counts are separate.
No recorded clips is not evidence that zero clips occurred.

## Review and export

Check completeness after inspecting the footage. Clip completeness needs an answer
for every recorded clip; Cannot tell with a reason is valid. Identity, boundaries/
result, unfinished timers, unanswered methods and boundary/clip completeness checks
appear before export. Fix them or explicitly **Export clearly marked draft**.
Draft HTML/PDF reports say DRAFT and describe the remaining issues; local CLI
exports retain the same status. Footwork/recovery completeness stays explicit.

## Older work and backups

Old labels remain readable. **Organise existing attempts…** confirms athlete/session/
route for each draft. Reassign aliases to an existing athlete explicitly; similar
names never auto-merge. Existing mouth/direct choices survive. Absent methods
become Answer needed.

Workspace format 3 stores roster, sessions, routes and assignments in one atomic
workspace file. Upgrading keeps `.v1-backup.json` or `.v2-backup.json`. Converting
labels to schema 1.4 keeps `.pre-identity-backup.json`. Project exports use format 2
to carry identities; imports still accept format 1. Stand-alone labels include
referenced identity snapshots. Conflicting session/route IDs are rejected rather
than merging contexts.

Old app versions cannot read new labels/project exports. Do not downgrade over a
new workspace; preserve it and use backups to restore an older installation.
All data stays local: no account, recognition, cloud roster or footage upload.
