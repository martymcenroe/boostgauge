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

**One element of the photograph is explicitly rejected (operator ruling 2026-08-15, #325):** the viewer's reflection ghosted in the glass. The composition — round dial in the square chrome housing, chrome treatment, screws — is approved as shown; the reflection is not. The dial face renders black as night, with no reflection of any kind (§Face). This is the one place the photograph and the binding text deliberately disagree; a render that reproduces the ghost is wrong even though the photograph shows it.

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
| Redline band | crimson | (170, 15, 25) | `#AA0F19` |
| Housing chrome — dark stop | — | (130, 132, 127) | `#82847F` |
| Housing chrome — light stop | — | (236, 233, 224) | `#ECE9E0` |
| Telltale — 1 minute | cyan | (59, 215, 240) | `#3BD7F0` |
| Telltale — 10 minutes | orange | (255, 154, 46) | `#FF9A2E` |
| Telltale — 1 hour | magenta | (212, 91, 232) | `#D45BE8` |
| Telltale — all-time | coral red | (255, 110, 122) | `#FF6E7A` |

The dial, white, and chrome values are measured from the canonical photograph. The two main reds are set by ruling #228's split, which the photograph predates: it shows a single red for both needle and band, which is exactly the contradiction #228 retired. The band's crimson replaced #228's brick by operator ruling 2026-08-25, made against the first contract-faithful render: brick read as brown, not tachometer red. Crimson sits 88 RGB distance from the candy-apple needle — above the floor below — and the palette's tightest pair remains orange/coral at ~88.

**The all-time telltale is its own colour (ruling #267).** §Telltale needles previously specified it as "the same hue as the main needle, distinguishable by thinness." Under nearest-entry classification that needle is unclassifiable by construction — a sampled pixel cannot be attributed to it or to the main needle — which is the #228 defect reintroduced. Thinness cannot rescue a colour test: a pixel carries no width. Coral red keeps it in the red family, as the permanent high-water mark should be, and makes it unmistakable to a classifier.

**Separation is a property of this table (ruling #267):** no two entries are closer than **85** in Euclidean RGB distance — the tightest pair is 10-minute orange against all-time coral, at ~88 — so anti-aliasing cannot flip a classification. Any future palette edit preserves that floor or the assertion method stops being sound.

### Layout

All lengths are fractions of the output image's edge length (`size`), so the contract is resolution-independent. **R = dial radius = 0.40 × size**, centred at (0.5 × size, 0.5 × size).

| Quantity | Value |
|---|---|
| Dial radius R | 0.40 × size |
| Redline band | inner 0.88 R, outer 1.00 R (spanning values 60–100 per §Redline arc; thinned from 0.80 R by ruling 2026-08-25) |
| Main needle tip | 0.86 R from centre |
| Main needle counterweight | 0.18 R opposite the tip |
| Main needle width | 0.035 R |
| Telltale needle width | 0.45 × main needle width |
| Telltale baseline opacity | 65% (alpha 166) — the single value replacing the former 60–70% range |
| Pivot cap radius | 0.10 R |
| Major tick | length 0.10 R, width 0.025 R |
| Minor tick | length 0.05 R, width 0.012 R |
| Numeral cap height | 0.11 R |
| Numeral ring | numeral centres at 0.72 R from the pivot (ruling 2026-08-25 — previously unspecified; every drafter had to invent it) |
| Wordmark cap height | 0.09 R |
| Wordmark placement | horizontally centred; cap-height band centred 0.67 R below the pivot — level with the 0/100 major ticks (ruling 2026-08-25; was 0.55 R) |
| Bezel width | 0.13 × size per side |

The needle tip at 0.86 R reaches to just short of the band's 0.88 R inner edge (ruling 2026-08-25 thinned the band; the operator approved the render showing exactly this relationship). The #1-era distinctness criterion is restated accordingly: at any value inside 60–100, tip pixels (sampled on the needle axis at ≤ 0.86 R) and band pixels (sampled at 0.90–1.00 R on the same radial) must each classify as their own palette entry — the two reds stay testably distinct without the tip entering the band.

### Needle luminescence (ruling 2026-08-15, #327)

"Luminescent" is a value here, not an adjective. The main needle is composited additively (bloom), never alpha-blended flat:

| Layer | Fill | Gaussian passes (radius as fraction of R, weight) |
|---|---|---|
| Needle body | `#F73923` (the palette entry, unchanged) | (0.004, 1.00) (0.012, 0.78) (0.027, 0.52) (0.061, 0.34) |
| Hot core — axis stripe, width 0.016 R | `#FFEED6` | (0.002, 1.00) (0.007, 0.72) (0.022, 0.36) |

Assertions, measured 2026-08-15 from the operator-approved render, sampled perpendicular to the needle axis at 0.45 R along its length:

| Sample point | Measured | Binding assertion |
|---|---|---|
| On axis | (255, 255, 222) | R = 255 AND G ≥ 200 — the core is near-white, not red |
| 0.04 R perpendicular | (242, 8, 0) | R ≥ 180 — glow present beyond the needle's own 0.0175 R half-width |
| 0.10 R perpendicular | (0, 0, 0) | R ≤ 25 — the glow ends; the face stays black |

The middle row is load-bearing: a flat-drawn needle shows face-black at 0.04 R and fails it. Because bloom brightens pixels near the needle, nearest-entry classification samples keep the ≥2 px interior rule AND stay ≥0.10 R from the needle axis; the three samples above are predicate assertions, not classification samples.

### Chrome environment strip (ruling 2026-08-15, #328)

Chrome is a mirror, and a mirror needs a world to reflect. The housing's reflection is generated by sampling this vertical strip (t = 0 at the top of the frame, 1 at the bottom). The 0.485 → 0.500 transition is the horizon and MUST remain a step, never a ramp — the hard split is what makes rendered metal read as metal; a smoothed version reads as plastic (the 2026-08-15 render review's grey-ramp failure is the documented case).

| t | RGB |
|---|---|
| 0.00 | (255, 255, 255) |
| 0.18 | (196, 214, 238) |
| 0.40 | (238, 246, 255) |
| 0.485 | (255, 255, 255) |
| 0.500 | (18, 19, 22) |
| 0.58 | (44, 46, 48) |
| 0.74 | (110, 108, 104) |
| 0.88 | (196, 190, 178) |
| 1.00 | (255, 252, 244) |

Flat regions of the housing sample the strip directly; the rolled inner bezel sweeps its surface normal through the strip, so the horizon reappears compressed around the bore. Specular hot spots per §Bezel: two, top-left and bottom-right, small, blown to 255-white at center, tight falloff.

### How a colour is asserted

A sampled pixel is classified by **nearest palette entry**: compute Euclidean RGB distance to every entry in the table above; the pixel must be closest to its expected entry. "Distinct hues" is retired as a phrase — the needle-tip sample must classify as candy-apple, the band sample as brick, and a render that let them converge fails by classification rather than by judgement. Sample away from edges (at least 2 px inside a feature) so anti-aliasing does not decide the result.

**The chrome housing is an exception**, because it is a mirrored gradient rather than a flat fill: a chrome pixel is verified by predicate — achromatic (max channel − min channel ≤ 14) with a channel mean between 16 and 248 — not by nearest entry. Its two table rows are the gradient's stops, not classification targets. Chrome is sampled at **three or more points spanning the horizon** (§Chrome environment strip), and at least one sample must be dark (mean < 100) and one bright (mean > 200) — the assertion that a horizon EXISTS, which is what separates metal from the grey ramp that reads as plastic (ruling #328; the former mean floor of 127 forbade the dark half of a real reflection).

**Optional elements are never asserted.** Where this doc permits but does not require an element, no test may verify its presence or absence. A test that asserts an optional element is wrong regardless of what the renderer does. (This class is currently empty: the pivot screws, formerly its only member, were promoted to required by ruling #326 and carry their own predicate in §Pivot / center.)

### Radial zones and compositing (ruling 2026-08-25, per #354)

Twelve spec review rounds tripped on the same derivation: what colour survives at a given (radius, angle) once every element has drawn. This section retires the derivation. **A test's expected pixel is read from here, never derived** — a test that cannot cite a row below for its expected colour is wrong by construction.

**Draw order** (later paints over earlier). Static face: housing chrome → bezel-seat shadow → dial face → redline band → tick marks → numerals → wordmark → screws. Dynamic layer above the cached face (#329): telltales → main needle → pivot cap.

**Radial zone table** — the named rings, static face only:

| Radial zone | Occupant | Expected colour at a sample point |
|---|---|---|
| 0.00–0.72 R (excluding rows below) | dial face | `#0A0A0C` flat |
| screw disks: centres ±0.25 R horizontal, radius 0.020 R | screws | `#1A1A1C` |
| numeral ring: centres 0.72 R, cap height 0.11 R, at majors | numerals | white glyph pixels; `#0A0A0C` between glyphs |
| wordmark band: centred 0.67 R below pivot, cap height 0.09 R | wordmark | white glyph pixels; `#0A0A0C` beside them |
| 0.88–1.00 R, values 60–100 | redline band | `#AA0F19` — including BETWEEN ticks in this arc |
| 0.88–1.00 R, values outside 60–100 | dial face | `#0A0A0C` |
| major tick strokes: 0.90–1.00 R at multiples of 10, width 0.025 R | ticks (over band or face) | `#FFFFFF` |
| minor tick strokes: 0.95–1.00 R at even values, width 0.012 R | ticks (over band or face) | `#FFFFFF` |
| 1.00–1.03 R | bezel-seat shadow | darker than the chrome at 1.10 R (S9 predicate) |
| beyond ~1.03 R | chrome housing | the #328 predicate, never nearest-entry |

**The canonical worked examples** — the exact cases the review rounds kept getting wrong:

- A between-tick pixel at 0.95 R in the 60–100 arc is **band crimson**, not face black.
- A between-tick pixel at 0.95 R below value 60 is **face black**.
- A tick-stroke midpoint is **white** on either background; the stroke predicate's ≥100 threshold clears both (face channel mean ~10, crimson band channel mean 70.0).
- The needle tip (0.86 R, dynamic layer) never enters the band (0.88 R inner); tip and band are distinguished by same-radial classification, not by overlap.

---

## Render architecture (ruling 2026-08-15, #329)

**The face is a static asset; only the needles move.**

- **The static face** — bezel, chrome housing, dial face, redline band, tick marks, numerals, wordmark, screws — is rendered once per (size, skin) and cached. It is never redrawn during a session. The expensive chrome (§Chrome environment strip) is therefore a one-time cost, irrelevant to refresh rate.
- **The dynamic layer** — the main needle and the four telltales — composites over the cached face on every refresh.
- **The shared geometry** both halves draw from is this contract's: R = 0.40 × size, centre at (0.5 × size, 0.5 × size), and `angle(value) = 225° − 2.7° × value` (ruling #255).
- **The seam is also the issue boundary:** the static face and the needle layer are implemented and tested as separate deliverables.

Test strategy 0001 is unaffected: both halves produce a `PIL.Image`, Option C throughout, no `tkinter` in tests.

---

## Decisions, codified

Each subsection lists one visual decision, its value, and its rationale where non-obvious. **Values in this section are descriptive; where a number is needed, the numeric render contract above is authoritative.**

### Form factor

- **Housing shape:** Square. Chamfered corners (rounded with a small but visible radius — read the canonical image's bezel; the corners are not sharp 90°).
- **Dial shape:** Round, inscribed within the square housing.
- **Why this combination:** Honors the Schwinn Stingray nostalgia anchor. Form factor most people associate with "tachometer" is round, but the *housing* of historical bicycle speedometers (Stewart-Warner / Huret / etc.) was often square. The round dial inside a square chromed housing is the period-correct expression. Round-housing variants live in future skins per #45.

### Bezel

- **Material rendering:** Polished chrome. NOT brushed, NOT matte. Generated from the reflected environment defined in §Chrome environment strip (ruling #328) — a mirror with a hard horizon in it, never a grey ramp.
- **Width:** Substantial. Visibly weighty — the bezel is real metal, not a thin frame. As a fraction of total housing width, the bezel reads roughly 12–15% of the housing on each side.
- **Highlights:** Two soft specular hot spots, conventionally at top-left and bottom-right of the curved bezel surface. This is standard chrome-rendering convention from period product photography.
- **Bezel-to-dial transition:** Slight inner shadow where the bezel rolls inward and meets the recessed dial face. The dial sits below the bezel plane — not flush.

### Face

- **Color:** One flat fill of the palette's matte black `#0A0A0C`, uniform across the entire dial face. Black as night (operator ruling 2026-08-15, #325).
- **No overlays, ever:** no gradients, no glass sweep, no specular highlight, no environmental or viewer reflection on the face. The canonical photograph shows a viewer's reflection in the glass; that element is rejected — nothing sits between the paint and the camera.
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

- **Color:** Luminescent candy-apple red — and "luminescent" is bound numerically by §Needle luminescence in the render contract (bloom passes, hot core, and the three measured sample assertions), not by this adjective. Bright, saturated, slightly orange-shifted (not pink, not magenta) — the vivid red of 1970s factory paint fresh off the line. **Deliberately a different red from the redline band's brick red** so the needle tip reads as a separate element when it crosses the band (ruling on #228, 2026-08-09; the pre-revision spec said the two reds matched, which contradicted #1's distinctness criterion).
- **Geometry:** Narrow tip, slightly wider at the pivot mount. A small counterweight extends past the pivot opposite the pointer end — visible in the canonical image as the short red stub behind the pivot cap.
- **Position at rest:** Pointing to 0 (bottom-left of the arc).
- **Sweep:** Arc from 0 (lower-left) clockwise to 100 (lower-right). The needle sweeps through the upper portion of the dial. **The mapping is numeric and binding (ruling #255, 2026-08-10):** with angles measured at the pivot in standard math convention (0° at 3 o'clock, counterclockwise positive), `angle(value) = 225° − 2.7° × value`, linear — value 0 at 225° (lower-left), value 50 at 90° (straight up), value 100 at −45° (lower-right). A 270° clockwise sweep; the remaining 90° bottom gap holds the wordmark. Measured from the canonical image, which shows exactly this classic tachometer layout. The main needle and all telltale needles share the mapping, and every needle-position test computes its expected axis from it — asserting any geometry not derivable from this mapping is invention, and the spec reviewer rejects it (the run-issue1-124144 halt is the documented case).

### Telltale needles

Per #2 (rendering) consuming #41 (algorithm). Visible only when their `current_peak()` returns non-None.

| Window | Color | Style | Position behavior |
|---|---|---|---|
| 1 minute | Cyan (`#3BD7F0`) | Thin, translucent | Hard-hold within window; drops to next-in-window when peak ages out |
| 10 minutes | Orange (`#FF9A2E`) | Thin, translucent | Same |
| 1 hour | Magenta (`#D45BE8`) | Thin, dashed or dotted | Same |
| All-time | Coral red (`#FF6E7A`) — the red family, its own entry (ruling #267) | Thin, solid | Never drops without explicit reset |

The all-time needle was specified here as "the same hue as the main needle, distinguishable by thinness" until ruling #267. That made it unclassifiable — see §The numeric render contract, which carries the values and the reasoning.

- **Z-order:** All four telltale needles render BEHIND the main needle. Note that front-versus-behind has no pixel consequence except at overlap, so z-order is an implementation convention rather than an acceptance criterion (ruling #232, 2026-08-09).
- **Translucency:** Approximately 60–70% opacity for the four telltales. They should not compete with the main needle for attention; they should provide peripheral memory.
- **Proximity opacity (ruling #232, 2026-08-09; completion point ruled on #242, per-needle evaluation ruled on #245, 2026-08-10):** a telltale's opacity ramps linearly from its baseline at 3 scale units from the main needle's position to 100% at 2 scale units, and holds 100% anywhere closer. The ramp is evaluated per needle: distance is the scale distance between the telltale's peak value and the main needle's value, and the resulting opacity applies uniformly to the entire needle — never a per-pixel gradient along its geometry (a boundary needle's protruding tip is exactly as opaque as its base). The sliver peeking out beside the wider main needle is therefore fully solid through the entire close-in zone where translucency would wash it out, with a fade band (3 → 2 units) so nothing pops as the main needle sweeps past. Beyond 3 units, the baseline holds. (The pre-revision wording — "ramps up to 100%" within the window — left the completion point unstated; a ramp completing only at coincidence would never show full opacity anywhere visible, since at coincidence the telltale is occluded per the next bullet. The pipeline's requirements gate caught the contradiction with #1's near-overlap test case, which samples 100% at 2 units.)
- **Coincidence is occlusion, by design:** when a telltale's peak equals the current value, the narrower telltale sits fully behind the main needle and disappears. That is correct, not a defect: a telltale reports where the peak WAS once the needle falls back, and at coincidence the main needle itself is displaying the peak — the telltale carries no information at that instant. Visibility requirements apply only at non-coincident angles.
- **Width relative to main needle:** Approximately 40–50%.

### Pivot / center

- **Pivot cap:** Small chromed disk, same rendering treatment as the bezel (polished chrome with subtle highlights). Covers the attachment point of all five needles.
- **Screw details (required — operator ruling 2026-08-15, #326):** the two dark dots flanking the pivot cap, reading as factory screws. Formerly optional; promoted with literal values:

| Quantity | Value |
|---|---|
| Count | 2 |
| Centers | (−0.25 R, 0) and (+0.25 R, 0) from the pivot, on the horizontal axis |
| Radius | 0.020 R |
| Fill | `#1A1A1C`, flat |

  They verify by predicate, not by nearest-entry classification — `#1A1A1C` sits ~28 RGB-distance from the face's `#0A0A0C`, far under the palette's 85 separation floor, so adding it to the classification table would break the floor. The predicate: the pixel at each screw center matches `#1A1A1C` within ±6 per channel (a 0.020 R disk is ~5 px at size 256, so the center sample is safely interior per the 2-px anti-aliasing rule).

### Wordmark

- **Text:** `BOOSTGAUGE` (one word, all caps).
- **Typeface:** Same family as the numerals (Eurostile-adjacent or substitute). Slightly heavier weight than the numerals (small caps + bold).
- **Color:** White.
- **Position:** Below the pivot cap, centered horizontally, in the lower portion of the dial face.
- **Size:** Approximately 8–10% of dial radius in character height. Smaller than the numerals — it's a brand mark, not a label.

### Redline arc

- **Color:** Crimson (`#AA0F19`) — a saturated tachometer red, visibly a different hue from the main needle's candy-apple at a glance. (Ruling on #228, 2026-08-09, split the two reds; operator ruling 2026-08-25, made against the first contract-faithful render, replaced #228's brick with crimson — brick read as brown, not tachometer red. The 85 separation floor holds: crimson sits 88 from candy-apple.)
- **Position:** Upper portion of the scale, **starting at 60** and continuing to 100. (The canonical image's redline starts here — deliberately aggressive. A gauge that redlines at 60% communicates "you're already pushing it" before the user is in trouble.)
- **Form:** A solid ring band occupying the **outer 88%–100% of the dial radius** (thinned from 80% by ruling 2026-08-25 — the wide band crowded the numerals), spanning scale values 60 to 100. It is a rim band, never a pie segment from the origin — the needle crosses matte black for its whole length; its tip stops just short of the band's inner edge. Tick marks in the 60–100 range render on top of the band in white, as in the canonical image.
- **Distinctness is testable:** at any value inside 60–100, tip pixels (≤ 0.86 R on the needle axis) and band pixels (0.90–1.00 R on the same radial) must each classify as their own palette entry (per #1's acceptance criteria, restated by ruling 2026-08-25).

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
