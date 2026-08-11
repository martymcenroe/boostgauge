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

**The text is binding; the image is inspiration (operator ruling #262, 2026-08-10).** The written sections below are the sole binding specification. The photograph above is reference material — the look the renderer aims for — and is **never a comparator**: no test compares a render against it, no acceptance criterion cites it, and it is never regenerated to track rulings. An AI-generated photograph cannot be regenerated to spec, and a pipeline that depends on that would make every text ruling unlandable — the spec reviewer proved it live by refusing, six runs in a row, to write the photo-comparison test.

Visual-regression baselines in `tests/visual/baselines/` are **self-generated**: the first accepted render becomes the baseline via the explicit `pytest --generate-baselines` human-in-the-loop flow (test strategy 0001 §3). Baselines guard future changes against unintended drift from the *accepted render* — never against the photograph.

> **Revision note (2026-08-09, rulings #228/#229; regen-dependency retired 2026-08-10 by ruling #262):** the needle and redline colors were split (candy-apple needle, brick band — see §Main needle and §Redline arc) after the pipeline caught the matching-reds contradiction. The note that stood here made the color sections binding "until the image is regenerated (tracked in #230)". Ruling #262 retired that dependency: the image is never regenerated, #230 is superseded, and the sections below are binding without qualification.

---

## The numeric render contract (ruling #265, 2026-08-11)

**Every visual acceptance criterion is computed from this section.** The prose subsections below describe intent; these tables carry the values. A test asserting a colour or a position derives it here — nothing is invented, and nothing is measured off the photograph.

This section exists because the spec stage deadlocked six times without it. Where the doc gave a number (`angle(value)`, ruling #255), the drafter wrote real assertions on the first draw; where it gave adjectives ("candy-apple red", "approximately 60–70% opacity"), the same drafter wrote `assert isinstance(img, Image.Image)` — a test that verifies nothing, because inventing a value is forbidden and no value was supplied. Adjectives are not a specification.

### Palette

| Element | Name | RGB | Hex |
|---|---|---|---|
| Dial face | matte black | (10, 10, 12) | `#0A0A0C` |
| Tick marks, numerals, wordmark | white | (255, 255, 255) | `#FFFFFF` |
| Main needle | candy-apple red | (247, 57, 35) | `#F73923` |
| Redline band | brick red | (155, 48, 32) | `#9B3020` |
| Housing chrome — dark stop | — | (130, 132, 127) | `#82847F` |
| Housing chrome — light stop | — | (236, 233, 224) | `#ECE9E0` |

The dial, white, and chrome values are measured from the canonical photograph. The two reds are set by ruling #228's split, which the photograph predates: it shows a single red for both needle and band, which is exactly the contradiction #228 retired. Telltale needle hues remain as named in §Telltale needles; each renders at the opacity below.

### Layout

All lengths are fractions of the output image's edge length (`size`), so the contract is resolution-independent. **R = dial radius = 0.40 × size**, centred at (0.5 × size, 0.5 × size).

| Quantity | Value |
|---|---|
| Dial radius R | 0.40 × size |
| Redline band | inner 0.80 R, outer 1.00 R (spanning values 60–100 per §Redline arc) |
| Main needle tip | 0.86 R from centre |
| Main needle counterweight | 0.18 R opposite the tip |
| Main needle width | 0.035 R |
| Telltale needle width | 0.45 × main needle width |
| Telltale baseline opacity | 65% (alpha 166) — the single value replacing the former 60–70% range |
| Pivot cap radius | 0.10 R |
| Major tick | length 0.10 R, width 0.025 R |
| Minor tick | length 0.05 R, width 0.012 R |
| Numeral cap height | 0.11 R |

The needle tip at 0.86 R sits inside the band's 0.80–1.00 R span, which is what makes issue #1's value=75 criterion (tip inside the band, distinct from it) renderable and testable.

### How a colour is asserted

A sampled pixel is classified by **nearest palette entry**: compute Euclidean RGB distance to every entry in the table above; the pixel must be closest to its expected entry. "Distinct hues" is retired as a phrase — the needle-tip sample must classify as candy-apple, the band sample as brick, and a render that let them converge fails by classification rather than by judgement. Sample away from edges (at least 2 px inside a feature) so anti-aliasing does not decide the result.

---

## Decisions, codified

Each subsection lists one visual decision, its value, and its rationale where non-obvious. **Values in this section are descriptive; where a number is needed, the numeric render contract above is authoritative.**

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

- **Color:** Luminescent candy-apple red. Bright, saturated, slightly orange-shifted (not pink, not magenta) — the vivid red of 1970s factory paint fresh off the line. **Deliberately a different red from the redline band's brick red** so the needle tip reads as a separate element when it crosses the band (ruling on #228, 2026-08-09; the pre-revision spec said the two reds matched, which contradicted #1's distinctness criterion).
- **Geometry:** Narrow tip, slightly wider at the pivot mount. A small counterweight extends past the pivot opposite the pointer end — visible in the canonical image as the short red stub behind the pivot cap.
- **Position at rest:** Pointing to 0 (bottom-left of the arc).
- **Sweep:** Arc from 0 (lower-left) clockwise to 100 (lower-right). The needle sweeps through the upper portion of the dial. **The mapping is numeric and binding (ruling #255, 2026-08-10):** with angles measured at the pivot in standard math convention (0° at 3 o'clock, counterclockwise positive), `angle(value) = 225° − 2.7° × value`, linear — value 0 at 225° (lower-left), value 50 at 90° (straight up), value 100 at −45° (lower-right). A 270° clockwise sweep; the remaining 90° bottom gap holds the wordmark. Measured from the canonical image, which shows exactly this classic tachometer layout. The main needle and all telltale needles share the mapping, and every needle-position test computes its expected axis from it — asserting any geometry not derivable from this mapping is invention, and the spec reviewer rejects it (the run-issue1-124144 halt is the documented case).

### Telltale needles

Per #2 (rendering) consuming #41 (algorithm). Visible only when their `current_peak()` returns non-None.

| Window | Color | Style | Position behavior |
|---|---|---|---|
| 1 minute | Cyan / light blue | Thin, translucent | Hard-hold within window; drops to next-in-window when peak ages out |
| 10 minutes | Orange | Thin, translucent | Same |
| 1 hour | Magenta / purple | Thin, dashed or dotted | Same |
| All-time | Red (same hue as main needle, distinguishable by thinness) | Thin, solid | Never drops without explicit reset |

- **Z-order:** All four telltale needles render BEHIND the main needle. Note that front-versus-behind has no pixel consequence except at overlap, so z-order is an implementation convention rather than an acceptance criterion (ruling #232, 2026-08-09).
- **Translucency:** Approximately 60–70% opacity for the four telltales. They should not compete with the main needle for attention; they should provide peripheral memory.
- **Proximity opacity (ruling #232, 2026-08-09; completion point ruled on #242, per-needle evaluation ruled on #245, 2026-08-10):** a telltale's opacity ramps linearly from its baseline at 3 scale units from the main needle's position to 100% at 2 scale units, and holds 100% anywhere closer. The ramp is evaluated per needle: distance is the scale distance between the telltale's peak value and the main needle's value, and the resulting opacity applies uniformly to the entire needle — never a per-pixel gradient along its geometry (a boundary needle's protruding tip is exactly as opaque as its base). The sliver peeking out beside the wider main needle is therefore fully solid through the entire close-in zone where translucency would wash it out, with a fade band (3 → 2 units) so nothing pops as the main needle sweeps past. Beyond 3 units, the baseline holds. (The pre-revision wording — "ramps up to 100%" within the window — left the completion point unstated; a ramp completing only at coincidence would never show full opacity anywhere visible, since at coincidence the telltale is occluded per the next bullet. The pipeline's requirements gate caught the contradiction with #1's near-overlap test case, which samples 100% at 2 units.)
- **Coincidence is occlusion, by design:** when a telltale's peak equals the current value, the narrower telltale sits fully behind the main needle and disappears. That is correct, not a defect: a telltale reports where the peak WAS once the needle falls back, and at coincidence the main needle itself is displaying the peak — the telltale carries no information at that instant. Visibility requirements apply only at non-coincident angles.
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

- **Color:** Brick red — deeper and browner than the main needle's candy-apple red, visibly a different hue at a glance. (Ruling on #228, 2026-08-09. The pre-revision spec said "matching the main needle," which made a needle tip inside the band indistinguishable from it; the pipeline's requirements gate caught the contradiction with #1's distinctness criterion.)
- **Position:** Upper portion of the scale, **starting at 60** and continuing to 100. (The canonical image's redline starts here — deliberately aggressive. A gauge that redlines at 60% communicates "you're already pushing it" before the user is in trouble.)
- **Form:** A solid ring band occupying approximately the **outer 80%–100% of the dial radius**, spanning scale values 60 to 100. It is a rim band, never a pie segment from the origin — the needle crosses matte black for most of its length and only its tip enters the band. Tick marks in the 60–100 range render on top of the band in white, as in the canonical image.
- **Distinctness is testable:** at any value inside 60–100 the needle tip lies within the band; a render-tier test samples tip pixels against band pixels and the two reds must differ (per #1's acceptance criteria).

## What this doc binds

Code implementing #1 (core gauge renderer) MUST:

1. Produce output satisfying the numeric render contract above — the palette RGBs and the layout fractions — at any `size`, verified by doc-derived checks and pinned thereafter by a self-generated baseline (rulings #262, #265). The canonical photograph is never the comparator.
2. Structure the renderer so swapping skins per #45 requires changing only the skin module, not the application code that calls `render()`.
3. Use the typography, colors, and proportions specified above. Substitutions are permitted only for typefaces (when Eurostile is unavailable) and only with the substitutes listed in the Numerals section.

Code implementing #1 MUST NOT:

1. Hard-code dial dimensions, colors, or geometry outside of the skin module. The application code must call into the skin's `render()` and consume the resulting `PIL.Image` — it must not know that the v1 skin is "Stingray-shaped."
2. Add visual elements not specified here. The aesthetic is functional jewelry — every element earned its place. New ornament requires a separate aesthetic doc revision.
3. Diverge from the numeric render contract's palette. The reds, whites, blacks, and chromes are specific values, not a mood; do not let them drift toward modern flat-design defaults.

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
