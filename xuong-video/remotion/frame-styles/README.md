# Frame style library

Decoration-only frames for native CapCut cells (the cell stays a CapCut clip with a rounded rectangle mask, so the
editor can right-click -> Replace). Composition `FrameStyle` (`src/frame-styles/FrameStyle.tsx`) draws ONLY the
decoration, transparent everywhere else.

| File | Role |
|---|---|
| `catalog.json` | styles: id, name_vi, description_vi (when it fits), tags, params, defaults; shared `params_schema` |
| `../scripts/render_frame_style.mjs --jobs jobs.json` | render jobs to PNG (still) or ProRes 4444 `.mov` (entrance), atomic per file |
| `../scripts/frame_gallery.mjs [--profile p.json]` | contact sheet `gallery/gallery.jpg` (2x2 grid + one card per style) |
| `../scripts/frame_style.py pick/mark/list --profile p.json` | requester taste in `gu.frame_styles {liked, rejected}` |

Styles: clean, glow, double, gradient, polaroid, tape, corner, neon, lift (+ label badge on any style: pill or ribbon,
BeVietnamPro Black, ink measured in the browser so Vietnamese diacritics never clip).

## Geometry contract
- Job box `{"box": [x0, y0, x1, y1], "radius": px, "label": {...}}` in canvas px; `radius` = the cell mask corner radius.
- Everything is drawn through an SVG mask whose hole is the box inset by `cover` px with radius `radius - cover`
  (concentric). `cover` = 2 px (anti-alias overlap) for every style except tape (`border_px`). So no style covers the
  video more than its border width, and the ring's inner contour follows the mask arc (tested on pixels).
- Rings are concentric: offset d outside the box has corner radius `radius + d`.
- CapCut mask `roundCorner` (0..1) -> px: `radius = roundCorner * min(box_w, box_h) / 2`. ASSUMED, not measured in a
  CapCut export (prototype values were set by eye). `pipeline-v6/native/layouts.py` uses exactly this formula and its
  inverse, and accepts `params.radius_px` to drive the mask from px — see pipeline-v6/TOOLKIT.md "Frame styles".

## Animation
`animated: true` + `frames` + `enter_f`: strokes draw in over `enter_f` frames (ease-out), filled parts (polaroid card,
tape, label) pop 0.9 -> 1.03 -> 1, glows fade in, neon flickers once; then held. Still PNG = fully drawn.

## Tests
`python -m unittest test_frame_style -v` from `scripts/` (real renders of every style + taste memory).
