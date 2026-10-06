
## Clearer video analysis and accessible comparison

- Measure is now **Video analysis**, with distinct left/right hand columns and
  clearer activity colours on idle and running timer buttons.
- Events filters: activity, hand and quickdraw/hold/method/note search. Visible/total
  counts; filtered edits and deletes preserve the selected event's identity.
- Completeness checks moved into **Check completeness…**, with plain-language
  explanations of what a full review means and how reports use it.
- A gold current-frame line with a contrasting outline, pointer and **NOW** label.
- Plain-language **Mark where the fall starts** replaces “Mark fall onset”.
- **Choose athletes** selects exactly the attempts to compare. The reference
  is one of the checked attempts; empty selections are supported.
- One shared side-by-side slider, with aligned, read-only annotation timelines
  under each video. Markers follow displayed source frames, including while loading.
- Colour-independent chart values, reference labels, full-name hover details,
  patterned allocation bands with matching legends, and foot marker shapes.
  HTML/PDF focus athletes are labelled in text.
- Missing comparison videos report an error without repeatedly trying to index
  them; Reload retries.

No schema or metric changes. Original video hashes, frames and PTS are preserved;
rest/chalk overlaps still count once and missing measurements remain unknown.
