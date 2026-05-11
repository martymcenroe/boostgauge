# 0002 — v1 Aesthetic: Stingray Skin

**Status:** Active
**Created:** 2026-05-11
**Owner:** boostgauge project
**Supersedes:** —
**Sister docs:** `0001-test-strategy.md`

---

## Purpose

This document is the canonical visual specification for boostgauge v1. Every implementation decision affecting how the gauge LOOKS — bezel, face, tick marks, needles, wordmark, color, typography — is codified here and only here. Code that draws the gauge implements this doc.

The doc is also the **first skin manifest** in the system planned by #45. v1 ships exactly one skin (`stingray`). Future skins will produce equivalent docs at `docs/design/0003-aesthetic-<name>.md`, `0004-...`, etc.

## Provenance

The aesthetic anchors on a specific personal memory: a chromed-metal square speedometer mounted on the project owner's blue Schwinn Stingray as a kid with a paper route. The speedometer represented the high luxury of mid-1970s functional jewelry — every element on it earned its place, nothing decorative, the chrome and the matte black face doing all the work. v1 is a faithful descendant of that gauge.

## Canonical reference

The visible target for v1:

![v1 Stingray canonical reference — square chromed-metal housing with round matte-black dial, red pointer at rest, red redline arc on upper half of scale, BOOSTGAUGE wordmark below pivot, mounted on a green Schwinn bicycle](../../images/aesthetic-v1-stingray-canonical.jpg)

Image generated 2026-05-11 via Gemini 2.5 Flash Image. Source prompt is preserved in the comment history of #45 and the report at `docs/reports/active/146-implementation-report.md`.

**The image is binding.** Implementation outputs must be indistinguishable from this image within the visual-regression tolerance defined by `0001-test-strategy.md` §3 (pixel-RMS ≤ 1.0/255 against the committed baseline). The image is the human-facing target; the per-test fixtures in `tests/visual/baselines/` are the programmatic comparators. They must not drift apart.

---

## Decisions, codified

Each subsection lists one visual decision, its value, and its rationale where non-obvious.

### Form factor

- **Housing shape:** Square. Chamfered corners (rounded with a small but visible radius — read the canonical image's bezel; the corners are not sharp 90°).
- **Dial shape:** Round, inscribed within the square housing.
- **Why this combination:** Honors the Schwinn Stingray nostalgia anchor. Form factor most people associate with "tachometer" is round, but the *housing* of historical bicycle speedometers (Stewart-Warner / Huret / etc.) was often square. The round dial inside a square chromed housing is the period-correct expression. Round-housing variants live in future skins per #45.

### Bezel

- **Material rendering:** Polished chrome. NOT brushed, NOT matte.
- **Width:** Substantial. Visibly weighty — the bezel is real metal, not a thin frame. As a fraction of total housing width, the bezel reads roughly 12–15% of the housing on each side.
- **Highlights:** Two soft specular hot spots, conventionally at top-left and bottom-right of the curved bezel surface. This is standard chrome-rendering convention from period product photography.
- **Bezel-to-dial transition:** Slight inner shadow where the bezel rolls inward and meets the recessed dial face. The dial sits below the bezel plane — not flush.

### Face

- **Color:** Matte black. Carbon-black ish, not pitch black — has just enough depth to absorb light convincingly under interior lighting without going dead flat.
- **Texture:** Smooth. No grain, no print pattern, no fake "carbon fiber" weave.

### Tick marks

- **Color:** Pure white.
- **Major marks:** Bold. Length approximately 10% of dial radius. Aligned to integer multiples of 10 on the scale (0, 10, 20, …, 100). 11 total.
- **Minor marks:** Thin. Length approximately 5% of dial radius. 4 between each pair of majors. 40 total.
- **Position:** Just inside the dial's outer edge. The ring of tick marks defines the visual boundary of the active dial area.
- **Style:** Confident, not precision-engineering. These are factory-tachometer marks — solid and trustworthy, not vernier-graduated. No serifs, no flourishes.

### Numerals

- **Family:** Period sans-serif. Eurostile-adjacent. The numerals in the canonical image are in this family. Acceptable substitutes if Eurostile is unavailable in implementation: Helvetica Neue Bold, DIN, Futura. NOT: Arial (too generic), Times (not period-correct), display fonts.
- **Color:** Pure white, matching the tick marks.
- **Position:** Inside the tick-mark ring, aligned to the major ticks.
- **Values shown:** 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100. Every major.
- **Size:** Big enough to read at a glance from working distance (~2 ft from screen at 256×256 px gauge). Approximately 10–12% of dial radius in character height.

### Main needle

- **Color:** Red. Saturated, slightly orange-shifted red (not pink, not magenta) — what 1970s factory paints actually used.
- **Geometry:** Narrow tip, slightly wider at the pivot mount. A small counterweight extends past the pivot opposite the pointer end — visible in the canonical image as the short red stub behind the pivot cap.
- **Position at rest:** Pointing to 0 (bottom-left of the arc).
- **Sweep:** Arc from 0 (lower-left) clockwise to 100 (lower-right). The needle sweeps through the upper portion of the dial.

### Telltale needles

Per #2 (rendering) consuming #41 (algorithm). Visible only when their `current_peak()` returns non-None.

| Window | Color | Style | Position behavior |
|---|---|---|---|
| 1 minute | Cyan / light blue | Thin, translucent | Hard-hold within window; drops to next-in-window when peak ages out |
| 10 minutes | Orange | Thin, translucent | Same |
| 1 hour | Magenta / purple | Thin, dashed or dotted | Same |
| All-time | Red (same hue as main needle, distinguishable by thinness) | Thin, solid | Never drops without explicit reset |

- **Z-order:** All four telltale needles render BEHIND the main needle.
- **Translucency:** Approximately 60–70% opacity for the four telltales. They should not compete with the main needle for attention; they should provide peripheral memory.
- **Width relative to main needle:** Approximately 40–50%.

### Pivot / center

- **Pivot cap:** Small chromed disk, same rendering treatment as the bezel (polished chrome with subtle highlights). Covers the attachment point of all five needles.
- **Optional detail dots:** Two small dark dots flanking the pivot cap in the canonical image — these read as factory screws or a reset mechanism. Implementation may include them; they are not load-bearing. If included, they should be approximately the size of a minor tick mark and rendered in the same dark-on-dial-face style.

### Wordmark

- **Text:** `BOOSTGAUGE` (one word, all caps).
- **Typeface:** Same family as the numerals (Eurostile-adjacent or substitute). Slightly heavier weight than the numerals (small caps + bold).
- **Color:** White.
- **Position:** Below the pivot cap, centered horizontally, in the lower portion of the dial face.
- **Size:** Approximately 8–10% of dial radius in character height. Smaller than the numerals — it's a brand mark, not a label.

### Redline arc

- **Color:** Saturated red, matching the main needle.
- **Position:** Upper portion of the scale, **starting at 60** and continuing to 100. (The canonical image's redline starts here — deliberately aggressive. A gauge that redlines at 60% communicates "you're already pushing it" before the user is in trouble.)
- **Form:** A solid arc band along the outside of the tick-mark ring, hugging the inner edge of the bezel.
- **Width:** Approximately 5% of dial radius.

## What this doc binds

Code implementing #1 (core gauge renderer) MUST:

1. Produce output indistinguishable from the canonical image at 256×256 px under the test strategy's visual-regression tolerance.
2. Structure the renderer so swapping skins per #45 requires changing only the skin module, not the application code that calls `render()`.
3. Use the typography, colors, and proportions specified above. Substitutions are permitted only for typefaces (when Eurostile is unavailable) and only with the substitutes listed in the Numerals section.

Code implementing #1 MUST NOT:

1. Hard-code dial dimensions, colors, or geometry outside of the skin module. The application code must call into the skin's `render()` and consume the resulting `PIL.Image` — it must not know that the v1 skin is "Stingray-shaped."
2. Add visual elements not specified here. The aesthetic is functional jewelry — every element earned its place. New ornament requires a separate aesthetic doc revision.
3. Diverge from the canonical image's color palette. The reds, whites, blacks, and chromes are specific; do not let them drift toward modern flat-design defaults.

## Out of scope

- Animation behavior (needle damping, ease curves) — defer to #1's LLD.
- The actual main-needle position-from-value math — defer to #1's LLD.
- Skin-loading mechanics — #45's territory.
- Specific test fixtures — #36's spike-commits follow-up (#42) lands those.
- Marketing / website / product imagery beyond the canonical reference — out of scope of all current issues.

## References

- **Canonical image:** `images/aesthetic-v1-stingray-canonical.jpg`
- **Sister doc:** `0001-test-strategy.md` (binds the testing approach the same way this doc binds the visual approach)
- **#1:** core gauge renderer (the v1 implementation of this aesthetic)
- **#2:** telltale needle rendering (telltale color/style decisions live here in §Telltale needles)
- **#41:** telltale algorithm (skin-independent; produces the peak values this doc renders)
- **#45:** skins system (this doc is the first skin manifest; future skins follow the same structure)
