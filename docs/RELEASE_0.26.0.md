# Climb Studio 0.26.0

A designed first screen and a consistent component layer across both platforms.

- Home opens first: start a training session or a competition event, open a single
  video, import a `.climbproject`, or continue a project from its tile. Tiles show a
  poster frame from the project's own videos and one pending item (clip answers,
  videos without an athlete, attempts without start and end). Right-click a tile
  to rename, export, show its folder or delete it. Settings chooses Home or the
  last project at startup.
- New session flow: kind and name, then route version and athletes, then the
  existing assignment sheet. Nothing is created until Finish. Compare opens
  scoped by session kind (athlete progress or competition round).
- Launch shows a splash before the heavy imports and fades into the window.
  Opening a video shows its first frame behind a thin progress line with Cancel.
- One app bar: project, session menu and a pending-clips chip on the left; save
  state, Add videos and Export on the right. Session management lives in the
  session menu. The saved state fades after three seconds.
- Nineteen theme-tinted line icons replace glyph buttons. Combo, spin, date,
  checkbox and radio controls are styled; cards have a border token and surfaces
  a visible step in both themes. Helper paragraphs become info popovers.
- Video analysis: play, step, timecode and speed together on the left; timeline
  range, fit and options on the right. Climb time is a 28 px stat. Hand tiles
  read Clip / Rest / Chalk and pulse while running; columns stay equal. Review
  tabs are a segmented control. Focus view shows a stop button per running timer.
- Compare: scope controls as chips, athlete and attempt first in the table and
  charts with session context beneath, the aligned metric card marked primary,
  More metrics as a vertical page list, side by side on the main transport.
- Videos: one toolbar, Status column (Open, Ready, Needs athlete), preview advice
  (Not needed, Recommended, Ready), table sized to its rows.
- Grouped settings, recording tips with a contents list, a tour bubble that
  points at its target and glides between steps.
- Fixes: `&` in two labels was eaten as a mnemonic; the project button no longer
  launches with a focus ring; the NOW badge skips ruler labels it would cover.
- Windows: immersive dark title bar, rounded corners on Windows 11, themed menu
  bar and point-sized timecode. Built from source; not yet validated on Windows.

Original hashes, frames, PTS, recovery unions, footwork eligibility and
athlete/session identities are unchanged. No new dependencies or cloud services.
Posters are cached in the ignored artifacts folder. The Projects dialog is no
longer in the File menu; Home is the project browser. Installed compatible
versions can update using Help → Check for updates.
