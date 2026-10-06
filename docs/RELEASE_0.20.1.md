# Climb Studio 0.20.1

This release addresses the approved usability and data-recovery audit. No footage leaves the computer. Source checksums, frame numbers and presentation timestamps remain unchanged.

- Autosave uses the project folder, full source checksum and a stable attempt ID. Renaming an athlete or attempt no longer changes storage identity. **New attempt** and **Open another attempt** are in the athlete menu. Missing videos stay in the project; opening their entry offers **Locate**, with checksum verification.
- Save status reflects persisted labels. A persistent failure banner offers Retry, Save copy and Show folder. Failed saves prevent switching away or restarting for an update. Workspace failures are reported separately. Older labels are preserved when migrated to the new identity; the first workspace format upgrade keeps a `.v1-backup.json` copy.
- Playback uses two compact rows. **Hide controls** gives the video the full width; a running-timer strip remains visible. History is collapsed by default. Clip technique and draw are captured when each hand starts its timer. Recorded tiles show the complete interval duration and open its editor. Guidance is opt-in under Help.
- Compare shares route, reference attempt, selected attempts and checkpoint across Table, Charts, More metrics and Side by side. Set a route through the athlete menu. Existing `blue` route values are retained; users should distinguish different routes before comparing. Table gaps are relative to the reference, with review state visible. Charts use actual checkpoint names and quickdraws; no eight-clip requirement. Exports include the selected comparison and preserve detailed fields.
- Side by side retains its position when switching tabs. Double-click a video to measure that attempt at the displayed frame. Frame stepping follows the next/previous actual timestamp across selected videos, including variable frame rates. Up to 16 selected tiles can be displayed.
- Library defaults to readiness, preview estimate and an action for each video. Recording metadata is available with **Show recording details**. Preparation confirms aggregate estimates and available disk space; jobs show queue position, phase, completion, failure or cancellation. Preview writing stops below 512 MB free and removes the partial output. Estimates are samples, not guarantees.
- Storage is a cache budget, not a reservation. It excludes source videos and measurements. Active playback and queued previews are protected from eviction, so their total can temporarily exceed the budget.
- Installed updates require a matching `update.json` release manifest with a supported OS, architecture, source-version range and migration policy. Unknown compatibility opens the release page instead of silently installing. Review the version, size and expandable release notes before downloading. Restart remains an explicit action after saving. The macOS swap refuses to modify a still-running app and restores the original if the second rename or relaunch command fails.

## Compatibility and validation limits

Labels gain an optional attempt ID and pending-clip method; routes can now be named. Workspace format is version 2. Earlier clients may not read new labels: keep the migration backups if you need to return to 0.19.0. Existing 0.19.0 updaters can install this release using their original checksum flow; compatibility-manifest enforcement starts with 0.20.1.

macOS installers target Apple Silicon / macOS 14+. Windows installers target x64 / Windows 10 or 11. Builds remain unsigned and the macOS app is not notarized. An operating-system launch acceptance does not prove a future app cannot crash; the swap recovery tests cover filesystem and launch-command failures, not arbitrary post-launch crashes.

Validation uses generated footage, fictional labels, automated tests and synthetic Qt captures, including 1024×768. CI builds and runs bundled self-checks on macOS and Windows. These checks do not substitute for hands-on Windows usability testing or performance measurements on real 4K footage.

The 0.20.0 release job was blocked by Windows checks and did not publish installers. This bundled release includes the Windows layout and fixture-lifecycle corrections.
