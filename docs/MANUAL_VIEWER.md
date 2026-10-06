# Manual measurements

Launch `tools/windows/start_manual_viewer.cmd`.

1. Open a video and enter the athlete and attempt.
2. Pause at the first grip on blue hold 1. Press **CLIMB START**.
3. At each landmark, enter a shared name (A, B, roof), then press **MARK ARRIVAL**. Use identical names across athletes for comparison. Click a recorded point to seek to it; rename or delete it as needed.
4. For each hand, select a hold number. At grab press **GRAB**; at release press **RELEASE**. The display shows elapsed time at the current video frame. Cancel discards an unfinished timer; Undo reverses mistakes. Double-click a closed interval to edit its frame boundaries.
5. At first rope weighting press **CLIMB END**. Start/end buttons replace their previous marker at the current frame.
6. **Save athlete measurements** for each attempt. Keep all `.labels.json` files in one folder. Use different filenames for different attempts.
7. **Export ALL athletes · HTML + CSV**, select that folder, then select the report destination.

The single offline HTML document contains all athletes, climb duration, a point-by-athlete time comparison, every arrival with splits, and every hand/hold interval. Beside it are three combined CSV tables (`-overview`, `-points`, `-holds`) for Excel, pandas or other software. The current unsaved attempt is included in export, replacing its saved equivalent by video checksum and attempt ID. Save separately to resume edits later.

Absolute timestamps are seconds from the video's first presentation timestamp. Arrival times are relative to climb start; splits are relative to the preceding chronological point. Hold durations cover the full marked interval; overview hand totals clip intervals to climb boundaries. Repeated arrivals remain separate. Missing measurements and unfinished timers remain unknown. Totals represent marked intervals, not proof that all contacts were labelled.

Space plays/pauses; arrows move one exact frame; speed changes playback only. Wheel zooms and dragging pans. Processing and exports stay local. Existing label files remain compatible, including legacy rest/clip annotations, which are retained when saved.

Rest and clipping: use START REST / STOP REST for deliberate recovery, and START CLIP / STOP CLIP from taking rope until it is clipped. Set clipping hand and quickdraw number before starting. Cancel removes an unfinished timer. Recorded intervals can be edited or deleted. Exports now include an activities CSV, rest duration/share, rest count and clip duration/count. Totals include marked intervals only. Overlapping rests are merged; rest and clipping totals may overlap. Use a shared named point for first touch of the same hold across athletes.

Scrubbing coalesces slider requests, seeks directly for distant jumps, and decodes on a background thread. Wait for the requested frame to appear before marking; actions refuse to record against a frame still loading. Frame stepping retains actual presentation timestamps.

## Climb Studio v0.4.0

The viewer uses a light workspace with Measure, Points, Hands and Recorded tabs. The header and exported comparison document show the tool version; label schema version remains independent.

On opening a video, its SHA-256 identifies saved measurements in the video folder, project videos folder, artifacts/labels, and the last folder used for labels. The latest matching save loads automatically; exact source timestamps are verified. Use Load labels to select a different attempt. Renaming a video does not change its identity.


## Climb Studio v0.5.0 — collection and live comparison

Add videos selects multiple files. Use the collection selector or Previous/Next to work through them. Workspace drafts, open timers and the last displayed frame persist locally in artifacts/workspaces/current.json; switching retains undo history for the current app session. Save athlete still creates the portable label file. The collection restores after restarting. Hash-based discovery loads existing labels in the background. Comparison currently shows one active attempt per added video.

Compare athletes is inside the application: climb time, marked rest time/count/share, marked clipping time/count, and one column per named point. Fastest marked arrivals are highlighted. Double-click an athlete to return to their video. The lower table lists each rest and clip with start/end seconds from climb start and duration. The Recorded tab also uses climb-relative boundaries; video timestamps remain in tooltips and exported data. Without climb start, relative times stay unknown.

Export all athletes exports the loaded workspace directly; no separate folder selection is needed. It includes workspace drafts as well as saved annotations. Add videos for every athlete to include them in the comparison.


## v0.5.1 — playback and resetting measurements

Play at the final frame rewinds and starts again. Play during a seek starts after that exact frame appears. At natural completion, the final frame is displayed before playback stops. Pause/resume preserves the visible frame.

Clear measurements opens a confirmation with Current attempt, All videos in collection, and Cancel. Reset removes climb boundaries, checkpoints, closed events, open timers, notes, outcome and review flags while retaining athlete identity and attempt number. It replaces associated saved label files with empty measurements and writes previous documents to artifacts/measurement-backups. Workspace drafts and comparison tables reset too. All-collection reset waits until background label discovery has completed. Videos are retained. To restore, use Load labels and choose the backup for the matching video. Other exported reports are unchanged.

## v0.6.0 — four hand timers and shortcuts

Measure has four direct toggle buttons: Left clip (L), Right clip (R), Left rest (Q), Right rest (W). Press once to start and again to stop. Each timer is independent and shows its running duration. Cancel discards only that activity/hand timer. Quickdraw number is captured when clipping starts; no clipping-hand dropdown is needed.

Other shortcuts: S climb start, E climb end, P arrival point, H left hold grab/release, J right hold grab/release, Space play/pause, arrows exact frame, Ctrl+S save, Ctrl+Z undo, Ctrl+Y redo. These keys do not intercept typing in text, number or selection fields. Set the point name or hold/draw number first, then focus the video to use the shortcut.

A hand rest means a deliberately annotated resting hand, not an inferred off-wall interval. Label schema 1.1.0 adds hand-specific rest semantics; 1.0.0 labels remain loadable with unassigned rests. Overlapping left/right rests merge for overall rest duration/count/share, while individual hand totals remain separate in comparison and export. Clipping, hand rests and hold contacts can overlap and are not inferred from each other. Every activity retains climb-relative and absolute video timestamps. Unfinished unassigned rests from older versions have a separate Stop/Cancel control.

## v0.7.0 — one compact measurement view

All visible telemetry controls now share the video workspace: climb start/end, named points, four rest/clip buttons, quickdraw number, graphical recorded timeline and editable event table. Hands and separate Points/Recorded sections are removed from navigation. Previously labelled hold data remains in saved files and event records; H/J hold shortcuts are disabled.

The timeline has left/right clip and rest lanes. Clip bars show the captured quickdraw number, and tooltips give timing and duration. Click the timeline to seek. The event table includes quickdraw and climb-relative start/end times. Each completed clip prepares quickdraw N+1; completing overlapping timers for the same draw does not skip an extra number. Cancel does not increment. The selected next draw persists when switching videos.

The header switches between Light mode and Dark mode. Theme choice is saved locally and applies on the next launch, including the timeline and dialogs. Compare athletes and HTML/CSV export remain available.

## v0.8.0 — chalking

Left chalk (C) and Right chalk (V) toggle chalking start/stop. Each completed pair records its hand, absolute video PTS/frame, seconds from climb start and duration. Each hand displays its completed-pair count and accumulated duration; unfinished timers remain drafts and do not contribute a completed count/duration. Cancel removes that timer. Chalking has purple lanes in the recorded timeline and is editable in the event table.

Comparison and HTML/CSV exports include completed chalking counts, total chalking time and left/right durations. Total chalking time within the climb merges overlapping hands, while individual hand durations remain separate; the total count counts each completed hand pair. Chalking is independent of rest and clipping and does not create either event automatically. Label schema 1.2.0 adds chalk events; older labels remain supported.

## v0.9.0 — Patterns & efficiency dashboard

Use the Patterns & efficiency tab to compare all loaded athletes or select two. Clipping hands shows the chronological L/R sequence, observed switches and transition opportunities, longest same-hand streak, left/right counts and mean/median clip durations. These are descriptive patterns, not a score or a measurement of grip fatigue. Stance, route geometry and quickdraw location can affect hand choice; dominance is not inferred.

Rest & chalk compares counts, total hand time and average intervals. Same quickdraw compares hand, clipping duration and completion time from climb start at each labelled draw. Same point compares named arrivals. Time allocation charts use exclusive bands for clipping, rest, chalking, overlap between different activities and unclassified time, so the chart sums to the marked climb duration without counting overlap twice. Unclassified time is not measured movement time. Missing activity remains unknown; zeros for one hand only describe the marked subset when the activity was labelled for another hand.

Exports now include hand-patterns and matched-clips CSVs plus a hand-patterns section in HTML, alongside existing overview, points, holds and activities. Changes to labels update the dashboard immediately. Unfinished timers are flagged and excluded from completed patterns.

## v0.10.0 — remove mistakes and configurable frame jumps

Frame step beside the decoder chooses 1–120 exact frames per arrow/button press; its initial default is 5 and it persists locally. Shift+Left/Right always moves one frame. Frame jumps use indexed presentation timestamps, including variable-frame-rate videos. Repeated clicks during a pending seek accumulate from the requested frame.

Select recorded rows, or click a timeline bar to select its event, then use Delete selected or the Delete key. Ctrl/Shift selection permits deleting multiple rows. Select point rows and press Delete to remove arrivals. The × beside climb start/end clears that boundary; × beside an activity discards its unfinished timer. Ctrl+Z/Undo restores accidental removal. Deletions update workspace drafts, timeline, counts and dashboards immediately. Save athlete updates the portable label file.

## v0.11.0 — shared points, athlete reset and resource usage

Point names are shared across the collection through an editable selector. Existing names such as REST are imported from labels; choose the shared name, then mark this athlete arrival. New names are added to the collection and reused for other athletes. Arrival timestamps remain individual and are never copied between videos. Clearing measurements retains the shared point catalogue.

Clear this athlete beside the athlete field confirms before resetting every loaded attempt with that athlete name. Other athletes stay untouched. Saved labels are reset, workspace/dashboard updates immediately, and previous documents are backed up locally.

The bottom strip samples process CPU, core equivalents, process RAM, GPU-device utilisation, device VRAM and process VRAM roughly every two seconds on a background worker. Core equivalents represent CPU time divided by one core capacity; CPU percent is normalised by total logical cores. GPU/device values include other applications. NVIDIA WDDM may not expose process VRAM, shown as n/a rather than zero. GPU data comes from local nvidia-smi, with no downloads, uploads or telemetry. Windows subprocess flags are isolated in platform_runtime.py.

## v0.11.1 — chalking contributes to total rest

Total marked rest is the union of dedicated-rest and chalking intervals, clipped to climb start/end and merged across both hands. Total rest episodes count connected intervals in that union; total rest share divides that time by climb duration. Dedicated rest and chalking retain separate event types, counts, durations and timeline colours. Their subtotals can overlap and must not be added to obtain total rest. Each hand also has a union-based total recovery duration. Unfinished timers do not contribute. Missing labels remain unknown. Older CSV rest_marked_seconds fields continue to mean dedicated rest; new total_rest_marked_seconds/count/share fields express the combined definition. Time allocation keeps separate exclusive activity bands and overlap without counting a rest total again as a separate band.

## v0.11.2 — 4K pause/resume fix

Playback requests no longer restart the completion-poll timer: 15 ms playback updates previously postponed the 20 ms completion check, starving frame display. A regression test verifies that repeated requests start this timer only once. Continuous playback keeps decoding forward instead of seeking on clock gaps. A bounded nearby-frame cache supports resuming without repeated long GOP seeks. Supported 4K H.264/HEVC uses NVIDIA CUDA automatically when no decoder preference was explicitly set; unavailable hardware falls back to CPU. Explicit CPU/GPU choices remain saved.


## v0.12.0 — between-clip split timers

Patterns & efficiency / Between clips derives splits from successive completed clip events, without extra manual timers. Gap time runs from previous clip completion to next clip start. Completion-to-completion time includes that gap plus the next clip duration. Each gap reports dedicated rest, chalking, their union as total marked rest, and time outside marked rest. Recovery intervals crossing a gap boundary are clipped to the gap. The residual is unclassified, not active movement. Zero means no marked interval in that gap. Overlapping clips produce unavailable splits instead of negative values. The same table is exported to HTML and a between-clips CSV. Incomplete clip timers are excluded.

### v0.12.1 — timestamped comments
Pause and choose **Comment at current frame**. Select a marked point and choose **Edit selected comment** to add, change or clear its comment. Comments retain exact frame, video time and climb-relative time; save with labels and export in points CSV and HTML. Delete and undo work as for other points.

### v0.12.2 — GPU video orientation
Apply rotation from the frame index for both CPU and CUDA decoding. CUDA frames can omit display rotation metadata; portrait 4K videos now retain the same orientation on both decoders.

### v0.13.0 — climb result
Climb end (E) pauses and asks **Fell / failed** or **Topped**. Cancel leaves the end unchanged. **Edit result** changes the outcome without moving the end frame. Clearing end resets result to unknown. Results save with labels, appear in the athlete comparison and export in HTML/CSV. Existing failed/completed schema values are retained.

### v0.14.0 — precision video timeline
A zoomable ruler replaces the plain video slider. Choose full video, 60/30/15/5/1 seconds, or zoom continuously with the mouse wheel (down to 0.5 seconds). Drag to scrub to the nearest exact PTS frame. Shift+wheel or right-drag pans; Centre on playhead recentres. Coloured activity lanes and start/end/point ticks provide context. Hover shows milliseconds. Scrubbing reuses asynchronous, debounced decoding; timeline painting does not decode frames.

### v0.15.0 — smooth local preview cache and timer layout
Choose **Prepare smooth preview** once per video. Preparation runs in a background worker with progress and cancellation; prepared previews automatically load on subsequent opens. The cache stores independent JPEG frames at up to 1280 pixels, allowing direct forward/backward access without decoding a long video GOP. Labels always retain original source SHA256, PTS and frame number; no frames are dropped or interpolated. Portrait rotation is baked into preview pixels. Previews are lossy viewing aids, not analysis inputs. Private caches live under ignored `artifacts/preview-cache`, can be deleted while the app is closed, and are not uploaded. Original videos remain intact. Timer labels have reserved height and the measurement panel scrolls when space is tight.

HTML comparison exports include recovery-share donut charts, dedicated rest/chalk/combined rest percentages, shared REST arrival bars and clipping totals for eight-clip attempts. Missing recovery is shown as unknown. Charts and fonts are embedded/local with no network resources. Time outside recovery is not labelled active movement.

### v0.16.0 — macOS, live charts and reusable reports
The **Charts** tab updates from loaded measurements and highlights a selected athlete. It shares recovery donuts, recovery percentages, REST arrivals and matched clipping charts with report exports. The **PDF** button writes a local vector PDF with repeated headers and page numbers. The report CLI accepts labels or exported HTML; see REPORTS.md. Apple Silicon setup is documented in SETUP_MACOS.md. Windows CUDA tools are optional via the `analysis` extra. Generated reports, source snapshots and historical footage telemetry are excluded from Git.

## Trackpad navigation

On MacBook trackpads, pinch over the video to zoom at the pointer; use two-finger
scrolling to pan the enlarged image. Two-finger double-tap resets to Fit view
(if Smart Zoom is enabled in macOS Trackpad settings). Over the time ruler, pinch
to change the visible time range, two-finger scroll to pan through time, and
double-tap to show the full video. Ctrl + two-finger vertical scroll also zooms.
Mouse wheel zoom, Shift+wheel timeline panning, drag panning and the Timeline zoom
selector remain available. Zero-delta scroll begin/end events do not change zoom.
These gestures use Qt native gesture/pixel scroll events; real MacBook validation
is still required.

Clip method: before stopping a clip timer, choose **Rope to mouth** (rope pulled up and held in the mouth before clipping) or **Direct · no mouth** (moved to a favourable position and clipped in one pull). The method is stored on the completed clip as optional `clip_method` (`mouth` / `direct`) and the selector resets to *not set*, so every clip is a deliberate choice; unset clips stay unknown. Edit a clip to change its method. The timeline shows `M` / `D` after the quickdraw number. Comparison shows mouth and direct clip counts within the climb (unmarked when no clip has a method), and the activities and matched-clips CSVs and PDF clip table include the method. Labels without the field stay valid.

Synchronized tab: plays every video in the collection side by side on one shared clock. **Align at** chooses the moment that becomes 0 s: climb start (default) or the first arrival at a shared named point. Videos without that mark are listed and left out. Play/pause (Space), step ±1 s or ±1/30 s (arrow keys use the frame-step setting), change speed or drag the slider; each tile shows the frame at its own aligned time and notes when its video has not started yet or has ended. Frames are decoded per video in the background and drop rather than drift when decoding cannot keep up; prepare smooth previews for several 4K videos. The view reads saved and in-progress measurements but never changes them.

Hardware decoding: the decoder menu offers **Apple GPU · VideoToolbox** on macOS and **NVIDIA GPU · CUDA** elsewhere. In automatic mode (no saved choice) macOS uses VideoToolbox for every H.264/HEVC file and Windows uses CUDA for 4K H.264/HEVC; failures fall back to CPU. The Synchronized tab uses the same automatic choice for each tile. Hardware frames map to the same indexed PTS frames as CPU decoding; a macOS test compares both after forward and backward seeks.

## 0.18.0 · projects, library, storage, updates and guidance

**Projects.** The header shows the open project; click it (or File › Projects…) to create, open, rename, export, import or delete projects. Each project keeps its own collection, labels, reports and backups; the original layout is the default project “My climbs”. Smooth previews and frame indexes are shared by checksum. *Export* writes one `.climbproject` zip: collection, labels and reports, plus the videos if chosen (stored uncompressed). *Import* checks every archive path (no absolute paths, `..` or unexpected folders) and unpacks into a new project, rewriting video and label paths to their new location. Deleting a project removes its folder only, including videos imported into it, never videos stored elsewhere.

**Import & library.** Lists every video in the project with resolution (rotation applied), frame rate, codec, HDR, duration, file size and an estimate of its smooth preview size from a sampled frame. Previews are *Recommended* for 4K and for HEVC at 1080p or more. *Prepare all recommended* or *Prepare selected* queues videos one after another in the background; progress appears per row and the open video switches to its preview as soon as it is ready. Remove from project keeps files and labels. The equalising of footage to 60 fps is deliberately not offered: resampling would invent duplicated frames and change the checksum that ties labels to the original file; Side by side already aligns different frame rates by timestamp.

**Storage.** File › Storage lists cached previews and frame indexes per video, with the total. A limit (default 20 GB) removes least-recently-used previews automatically after each preparation and at start-up, never the open video's. Interrupted preparations are cleaned up. Labels, reports and videos are never stored or deleted here.

**Smooth preview by default.** Whenever a prepared preview exists it is used for the video workspace, playback, stepping and every Side by side tile; hover the preview controls for an explanation of what preparation does.

**Side by side** (formerly Synchronized) chooses the column count that makes the videos largest for the window and their aspect ratio, with 2 px gaps; athlete and time are overlaid on each video. Full screen uses the whole display.

**Hands.** Clip, rest and chalk timers sit in a LEFT HAND and a RIGHT HAND card with the timeline's colours (clip blue, rest green, chalk purple). A running timer fills its button and shows its time in orange.

**Defaults.** Add videos opens the folder used last time. The point name starts as the point marked most recently.

**Guidance.** On start, recording tips explain camera position, 1080p/4K, 60 fps, HDR and why YouTube, Google Photos or messaging apps re-encode footage (switch off in the dialog; Help › Recording tips reopens it). A guided tour runs once and can be replayed from Help › Show tour.

**Updates.** Installed apps check GitHub Releases at most daily (Help › Check for updates automatically). *Update now* downloads the installer for this platform, verifies it against the release's `SHA256SUMS.txt`, and restarts: macOS swaps the app bundle in place after the app quits and restores the previous one if anything fails; Windows runs the installer silently and relaunches. If the app cannot replace itself (run from the disk image, no write permission, source checkout), *Download* opens the release page instead.
