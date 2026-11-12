"""Preflight + layout for the V6 graphics kit.

Reads kich-ban.json (UTF-8, BOM accepted), measures every text with the real
font (PIL), computes all geometry that the Remotion components draw, and
rejects items that do not fit or leave the safe zone. Writes layout.json which
render_graphics.mjs passes as inputProps (single source of geometry).

Usage: python kit_layout.py --script kich-ban.json --font BeVietnamPro-Black.ttf --out layout.json
Exit 1 with a list of errors if any item is rejected.
"""
import argparse
import base64
import hashlib
import io
import os
import json
import math
import re
import sys

import cv2
import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageFilter, ImageFont

W, H = 1080, 1920
# Visual spec zones (canvas px). Bboxes are [x0, y0, x1, y1], x1/y1 exclusive.
SAFE = (70, 150, 1010, 1560)
TIKTOK = (930, 900, 1080, 1600)  # must stay free
SUB_BAND = (0, 1330, 1080, 1520)  # graphics never overlap

# Base ("scale 1.0") sizes of keyword / checklist / cta / circle strokes / cutout label.
# Every size below is multiplied by style.graphics_scale (sc()); the card-width ceilings
# (KW_MAX_W, CTA_MAX_W) are limits, not sizes, and stay as they are.
KW_MAX_W, KW_PAD_X, KW_PAD_TOP, KW_PAD_BOT = 860, 36, 20, 26
KW_FS_MAX, KW_FS_MIN, KW_RADIUS = 72, 40, 24
KW_LH, KW_ACC_LH, KW_ACC_RATIO = 1.18, 1.10, 1.25
KW_TILT_DEG, KW_POP = -2.0, 1.06
KW_SHADOW, KW_BORDER = 10, 5
KW_LINE_CLEAR, KW_BLOCK_CLEAR, KW_TOP_INK = 6, 10, 10

CL_FS, CL_PAD_Y, CL_PAD_L, CL_TICK, CL_TICK_GAP, CL_PAD_R, CL_GAP, CL_LH = 46, 14, 14, 52, 16, 32, 18, 1.2
CL_SLIDE = 18  # px slide-from-left distance (keeps x >= 70 when x = 90)

CTA_FS, CTA_PAD_Y, CTA_PAD_L, CTA_ARROW_GAP, CTA_ARROW, CTA_PAD_R, CTA_MAX_W = 52, 22, 40, 18, 54, 34, 820
CTA_POP, CTA_BOUNCE = 1.05, 6

CIRCLE_STROKE, CIRCLE_OUTLINE_EACH_SIDE = 11, 7  # orange 11px + 7px circle_outline each side

GS_MIN, GS_MAX = 0.2, 1.5  # accepted style.graphics_scale range
FLASH_PEAK = 0.85  # flash opacity at local frame 0, linear decay to 0 on the last frame

# title_behind (exempt from graphics_scale): one line, BeVietnamPro Black, outline outside the glyphs.
TITLE_W_TARGET, TITLE_W_MIN, TITLE_W_MAX = 0.90, 0.85, 0.95  # ink+outline width / frame width
TITLE_FS_MIN, TITLE_FS_MAX, TITLE_OUTLINE = 120, 420, 10
TITLE_SLAM_F, TITLE_SLAM_SCALE, TITLE_SHAKE = 4, 1.6, 6
TITLE_X0, TITLE_X1 = 20, 1060  # 85-95% width cannot fit x 70-1010; hold frames only need a 20 px frame margin

# title_behind style=outline: letters are stroked only (fill none). Stroke is centred on the glyph edge, width = TITLE_OL_RATIO x font size
# (3.5%: ~10-14 px at the 280-420 px title sizes, ~8 px at the 120 px minimum: reads as a line on a 1080 px canvas, thinner looks hairline on a phone),
# plus a TITLE_OL_HALO px dark (card_bg) halo on each side of the stroke for contrast. Ink extent beyond the glyph edge = stroke/2 + halo.
TITLE_OL_RATIO, TITLE_OL_HALO = 0.035, 3
TITLE_STYLES = ("fill", "outline")
ROTATE_MAX = 15  # rotate_deg range (big_text, keyword, title_behind); keep equal to ROTATE_MAX in pipeline-v6/build/validate_script.py

# cutout (h is final px, not scaled): 6 px white outline + soft shadow baked into the PNG.
CUT_OUTLINE, CUT_PAD, CUT_SHADOW_DY, CUT_SHADOW_SIGMA, CUT_SHADOW_ALPHA = 6, 44, 10, 8.0, 0.45
CUT_POP_F, CUT_OUT_F, CUT_POP_OVERSHOOT, CUT_POP_DEG, CUT_FLOAT_PX = 12, 5, 1.12, 4.0, 4
CUT_ALPHA_MIN, CUT_ISLAND_FRAC = int(0.35 * 255), 0.02
CUT_LB_FS, CUT_LB_PAD_Y, CUT_LB_PAD_X, CUT_LB_GAP = 46, 14, 30, 14

# big_text (exempt from graphics_scale): the "big moment" key number, one line, fill card_accent + card_bg outline + soft glow.
BT_W_TARGET, BT_W_MIN, BT_W_MAX = 0.80, 0.70, 0.90  # ink+outline width / frame width
BT_FS_MIN, BT_FS_MAX, BT_OUTLINE, BT_GLOW = 90, 260, 10, 8  # glow = visible extent (px) of the dark halo beyond the outline
BT_SMALL_RATIO, BT_SMALL_OUTLINE, BT_GAP = 0.36, 6, 14
BT_PEAK_MAX, BT_IN_F, BT_OUT_F = 1.08, 9, 5

CL_HIGHLIGHT_F = 20  # checklist highlight_active: newest pill is card_accent for its first 20 frames

ARROW_BEND, ARROW_HEAD_LEN, ARROW_HEAD_DEG, ARROW_N = 0.18, 46, 28.0, 40  # bend = control offset / length

CIRCLE_N = 140

# frame (framed B-roll panels). Base sizes x graphics_scale (or scale_by_type.frame); the overshoots are factors.
FR_BORDER, FR_RADIUS, FR_SH_DY, FR_SH_BLUR, FR_SH_ALPHA = 8, 30, 12, 24, 0.45  # CSS box-shadow 0 12px 24px rgba(0,0,0,0.45)
FR_LB_FS, FR_LB_PAD_X, FR_LB_PAD_Y, FR_LB_X = 40, 22, 10, 28
FR_POP, FR_LB_POP, FR_SLIDE, FR_ENTER_F = 1.03, 1.08, 40, 8
FR_MIN_BOX = 120  # keep equal to FRAME_MIN_BOX in pipeline-v6/build/validate_script.py
FRAME_PALETTE_KEYS = ("frame_border", "frame_label_bg", "frame_label_text")
# worst-case Vietnamese ink (stacked marks above, dot below): every label pill of a frame is sized for it
FR_PROBE_TOP, FR_PROBE_BOT, FR_LB_CLEAR, FR_LB_INK_PAD = "ỄỖỮẨẪẰẲẴ", "ẶỰẬỊỌỤ", 3, 4  # ink pad: pill stays ~ the old 68 px at 40 px font
CIRCLE_OVERLAP_DEG = 25.0

PALETTE_KEYS = ("card_bg", "card_border", "card_shadow", "card_text", "card_accent", "pill_bg", "pill_text",
                "tick", "circle", "circle_outline", "cta_bg", "cta_text")
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

WIDTH_SLACK = 1.03  # browser shaping vs PIL measurement margin


def rect_intersects(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def sc(v, s):
    """Scale a base size by graphics_scale; whole px, never below 1."""
    return max(1, int(v * s + 0.5))


def zone_errors(bbox, kind="std"):
    """kind: std = full safe zone; title = hold frames of title_behind (x margin 20 only);
    title_slam = first slam frames of title_behind (scale 1.6, may leave the frame sideways);
    none = flash (full frame by design)."""
    errs = []
    if kind == "none":
        return errs
    x0, y0, x1, y1 = bbox
    safe = {"std": SAFE, "title": (TITLE_X0, SAFE[1], TITLE_X1, SAFE[3]), "title_slam": (-10**6, SAFE[1], 10**6, SAFE[3])}[kind]
    if x0 < safe[0] or y0 < safe[1] or x1 > safe[2] or y1 > safe[3]:
        errs.append(f"bbox {fmt(bbox)} outside safe zone {safe}")
    if rect_intersects(bbox, TIKTOK):
        errs.append(f"bbox {fmt(bbox)} enters TikTok button zone {TIKTOK}")
    if rect_intersects(bbox, SUB_BAND):
        errs.append(f"bbox {fmt(bbox)} overlaps subtitle band y {SUB_BAND[1]}-{SUB_BAND[3]}")
    return errs


def fmt(b):
    return "[" + ",".join(f"{v:.0f}" for v in b) + "]"


def inside(a, b):
    return a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]


def union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def transformed_bbox(box, cx, cy, scale, deg):
    """Bbox of rect `box` after scale+rotate around (cx, cy)."""
    a = math.radians(deg)
    pts = []
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])):
        dx, dy = (x - cx) * scale, (y - cy) * scale
        pts.append((cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)))
    return [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]


def rotate_deg_of(g, errs):
    """rotate_deg (default 0): degrees about the block's own centre for the whole duration. Returns float or None (error appended)."""
    v = g.get("rotate_deg", 0)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not -ROTATE_MAX <= v <= ROTATE_MAX:
        errs.append(f"{g.get('type')} rotate_deg must be a number in [-{ROTATE_MAX}, {ROTATE_MAX}], got {v!r}")
        return None
    return float(v)


def scaled_rotated_bbox(box, sc_center, scale, rot_center, deg):
    """Bbox of rect `box` after scaling about sc_center, then rotating about rot_center (rotation is the outer transform)."""
    if deg == 0:
        return transformed_bbox(box, sc_center[0], sc_center[1], scale, 0)
    a = math.radians(deg)
    pts = []
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])):
        x = sc_center[0] + (x - sc_center[0]) * scale
        y = sc_center[1] + (y - sc_center[1]) * scale
        dx, dy = x - rot_center[0], y - rot_center[1]
        pts.append((rot_center[0] + dx * math.cos(a) - dy * math.sin(a), rot_center[1] + dx * math.sin(a) + dy * math.cos(a)))
    return [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]


class Measure:
    def __init__(self, font_path):
        self.path = font_path
        self.cache = {}
        self.cmap = TTFont(font_path).getBestCmap()

    def width(self, text, size):
        key = (size,)
        if key not in self.cache:
            self.cache[key] = ImageFont.truetype(self.path, size)
        return self.cache[key].getlength(text) * WIDTH_SLACK

    def ink(self, text, size, lh):
        """(ink_top, ink_bottom) of text relative to the top of a CSS line box of height lh
        (CSS centres the font content area asc+desc inside the line box)."""
        f = ImageFont.truetype(self.path, size)
        asc, desc = f.getmetrics()
        base = (lh - (asc + desc)) / 2 + asc
        b = f.getbbox(text, anchor="ls")
        return base + b[1], base + b[3]

    def missing(self, text):
        return sorted({c for c in text if c != " " and ord(c) not in self.cmap})


def wrap(m, text, size, max_w, max_lines):
    """Greedy word wrap. Returns lines or None if impossible within max_lines."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if m.width(cand, size) <= max_w:
            cur = cand
        else:
            if not cur:
                return None  # single word too wide
            lines.append(cur)
            cur = w
            if m.width(cur, size) > max_w:
                return None
    if cur:
        lines.append(cur)
    return lines if len(lines) <= max_lines else None


def get_palette(script):
    """style.palette is mandatory: no defaults. Returns (palette, errors).
    frame_* keys are required (and passed on) only when the script has a frame graphic."""
    pal = (script.get("style") or {}).get("palette")
    if not isinstance(pal, dict):
        return None, ["style.palette missing (colors are designed per video; no default)"]
    errs = [f"style.palette.{k} missing or not #RRGGBB: {pal.get(k)!r}" for k in PALETTE_KEYS
            if not (isinstance(pal.get(k), str) and HEX.match(pal[k]))]
    out = {k: pal.get(k) for k in PALETTE_KEYS}
    if "title_fill" in pal:  # optional extra palette key, referenced by title_behind.fill
        if not (isinstance(pal["title_fill"], str) and HEX.match(pal["title_fill"])):
            errs.append(f"style.palette.title_fill not #RRGGBB: {pal['title_fill']!r}")
        out["title_fill"] = pal["title_fill"]
    if any(g.get("type") == "frame" for g in script.get("graphics") or []):
        errs += [f"style.palette.{k} missing or not #RRGGBB: {pal.get(k)!r} (required when a frame graphic exists)" for k in FRAME_PALETTE_KEYS
                 if not (isinstance(pal.get(k), str) and HEX.match(pal[k]))]
        out.update({k: pal.get(k) for k in FRAME_PALETTE_KEYS})
    return out, errs


def get_scale(script):
    """style.graphics_scale is mandatory: no default. Returns (scale, errors)."""
    v = (script.get("style") or {}).get("graphics_scale")
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not GS_MIN <= v <= GS_MAX:
        return None, [f"style.graphics_scale missing or not a number in [{GS_MIN}, {GS_MAX}]: {v!r}"]
    return float(v), []


def get_scale_by_type(script):
    """style.scale_by_type (optional): {type: factor}. Overrides graphics_scale for that type."""
    v = (script.get("style") or {}).get("scale_by_type")
    if v is None:
        return {}, []
    if not isinstance(v, dict):
        return {}, [f"style.scale_by_type must be an object, got {v!r}"]
    errs = []
    for k, x in v.items():
        if k not in LAYOUT:
            errs.append(f"style.scale_by_type has unknown graphic type {k!r}")
        elif isinstance(x, bool) or not isinstance(x, (int, float)) or not GS_MIN <= x <= GS_MAX:
            errs.append(f"style.scale_by_type.{k} not a number in [{GS_MIN}, {GS_MAX}]: {x!r}")
    return {k: float(x) for k, x in v.items() if isinstance(x, (int, float)) and not isinstance(x, bool)}, errs


def layout_keyword(m, g, errs, pal, S):
    text, accent, cy = g["text"], g.get("accent"), g["y"]
    rot = rotate_deg_of(g, errs)  # adds to the built-in KW_TILT_DEG
    if rot is None:
        return None
    pad_x, pad_top, pad_bot = sc(KW_PAD_X, S), sc(KW_PAD_TOP, S), sc(KW_PAD_BOT, S)
    border, shadow, radius = sc(KW_BORDER, S), sc(KW_SHADOW, S), sc(KW_RADIUS, S)
    line_clear, block_clear, top_ink = sc(KW_LINE_CLEAR, S), sc(KW_BLOCK_CLEAR, S), sc(KW_TOP_INK, S)
    fs_max, fs_min = sc(KW_FS_MAX, S), sc(KW_FS_MIN, S)
    inner = KW_MAX_W - 2 * pad_x
    for size in range(fs_max, fs_min - 1, -2):
        asz = round(size * KW_ACC_RATIO)
        tl = wrap(m, text, size, inner, 2)
        al = wrap(m, accent, asz, inner, 2) if accent else []
        if tl is not None and al is not None:
            break
    else:
        asz_min = round(fs_min * KW_ACC_RATIO)
        errs.append(f"keyword text {text!r} / accent {accent!r} does not fit width {KW_MAX_W} in 2 lines at {fs_min}px "
                    f"(text width at {fs_min}px = {m.width(text, fs_min):.0f}, accent at {asz_min}px = {m.width(accent or '', asz_min):.0f}, inner {inner})")
        return None
    # Place lines top-down; each line's ink must clear the previous line's ink
    # (stacked marks like "Ễ"/"Í" vs dot-below "Ợ") by CLEAR px (more between text and accent).
    specs = [(t, size, round(size * KW_LH), pal["card_text"]) for t in tl] + [(t, asz, round(asz * KW_ACC_LH), pal["card_accent"]) for t in al]
    lines, prev_bottom, y = [], None, None
    for i, (t, sz, lh, col) in enumerate(specs):
        it, ib = m.ink(t, sz, lh)
        if prev_bottom is None:
            top = max(pad_top, math.ceil(border + top_ink - it))
        else:
            clear = line_clear if i != len(tl) else block_clear
            top = max(y, math.ceil(prev_bottom + clear - it))
        lines.append({"text": t, "size": sz, "lh": lh, "top": top, "color": col, "w": m.width(t, sz), "ink": [top + it, top + ib]})
        prev_bottom, y = top + ib, top + lh
    last_ink = max(l["ink"][1] for l in lines)
    bw = math.ceil(max(l["w"] for l in lines) + 2 * pad_x)
    bh = math.ceil(max(y, last_ink) + pad_bot)
    left, top = 540 - bw / 2, cy - bh / 2
    box = [left, top, left + bw, top + bh]
    def ink_block(name, ls):
        return {"name": name, "box": [540 - max(l["w"] for l in ls) / 2, top + min(l["ink"][0] for l in ls),
                                      540 + max(l["w"] for l in ls) / 2, top + max(l["ink"][1] for l in ls)]}
    blocks = [ink_block("text", lines[:len(tl)])]
    if al:
        blocks.append(ink_block("accent", lines[len(tl):]))
    inner_box = [left + border, top + border, left + bw - border, top + bh - border]
    for b in blocks:
        if not inside(b["box"], inner_box):
            errs.append(f"keyword {b['name']} ink {fmt(b['box'])} outside box interior {fmt(inner_box)}")
    outer = [box[0], box[1], box[2] + shadow, box[3] + shadow]
    pred = transformed_bbox(outer, 540, cy, KW_POP, KW_TILT_DEG + rot)
    for l in lines:
        l["w"] = math.ceil(l["w"])
    return {"box": box, "lines": lines, "blocks": blocks, "pred_bbox": pred, "rotate_deg": rot, "font_size": size, "accent_size": asz if al else None,
            "dims": {"radius": radius, "border": border, "shadow": shadow}}


def layout_checklist(m, g, errs, pal, S):
    x, y0, f0 = g["x"], g["y"], g["f0"]
    fs, pad_y, pad_l, tick, tick_gap = sc(CL_FS, S), sc(CL_PAD_Y, S), sc(CL_PAD_L, S), sc(CL_TICK, S), sc(CL_TICK_GAP, S)
    pad_r, gap, slide = sc(CL_PAD_R, S), sc(CL_GAP, S), sc(CL_SLIDE, S)
    rows, blocks = [], []
    lh = round(fs * CL_LH)
    ph = lh + 2 * pad_y
    y = y0
    for it in g["items"]:
        tw = math.ceil(m.width(it["text"], fs))
        pw = pad_l + tick + tick_gap + tw + pad_r
        lf = it["f"] - f0
        if lf < 0 or it["f"] >= g["f1"]:
            errs.append(f"item {it['text']!r} f={it['f']} outside [{f0},{g['f1']})")
        it_t, it_b = m.ink(it["text"], fs, lh)
        ink = [x + pad_l + tick + tick_gap, y + (ph - lh) / 2 + it_t, x + pw - pad_r, y + (ph - lh) / 2 + it_b]
        if not inside(ink, [x, y + 2, x + pw, y + ph - 2]):
            errs.append(f"checklist {it['text']!r} ink {fmt(ink)} outside pill {fmt([x, y, x + pw, y + ph])}")
        rows.append({"text": it["text"], "lf": lf, "x": x, "y": y, "w": pw, "h": ph, "tw": tw})
        blocks.append({"name": it["text"], "box": [x, y, x + pw, y + ph]})
        y += ph + gap
    pred = union([[b["box"][0] - slide, b["box"][1], b["box"][2], b["box"][3]] for b in blocks])
    first = min(r["lf"] for r in rows)
    hl = g.get("highlight_active", False)
    if not isinstance(hl, bool):
        errs.append(f"checklist highlight_active must be true/false, got {hl!r}")
    return {"rows": rows, "highlight_active": hl is True, "highlight_f": CL_HIGHLIGHT_F, "blocks": blocks, "pred_bbox": pred, "font_size": fs, "lh": lh, "visible_from": first,
            "dims": {"tick": tick, "pad_l": pad_l, "tick_gap": tick_gap, "slide": slide}}


def layout_cta(m, g, errs, pal, S):
    fs, pad_y, pad_l, arrow_gap, arrow_d, pad_r, bounce = (sc(v, S) for v in (CTA_FS, CTA_PAD_Y, CTA_PAD_L, CTA_ARROW_GAP, CTA_ARROW, CTA_PAD_R, CTA_BOUNCE))
    tw = math.ceil(m.width(g["text"], fs))
    lh = round(fs * 1.2)
    pw = pad_l + tw + arrow_gap + arrow_d + pad_r
    ph = lh + 2 * pad_y
    if pw > CTA_MAX_W:
        errs.append(f"cta text {g['text']!r} pill width {pw} > {CTA_MAX_W}")
    left, top = 540 - pw / 2, g["y"] - ph / 2
    box = [left, top, left + pw, top + ph]
    i_t, i_b = m.ink(g["text"], fs, lh)
    text_box = [left + pad_l, top + pad_y + i_t, left + pad_l + tw, top + pad_y + i_b]
    if not inside(text_box, [left, top + 2, left + pw, top + ph - 2]):
        errs.append(f"cta ink {fmt(text_box)} outside pill {fmt(box)}")
    ax = left + pad_l + tw + arrow_gap
    ay = top + (ph - arrow_d) / 2
    arrow_box = [ax - bounce, ay, ax + arrow_d, ay + arrow_d + bounce]
    pred = transformed_bbox(box, 540, g["y"], CTA_POP, 0)
    return {"text": g["text"], "box": box, "tw": tw, "lh": lh, "font_size": fs, "arrow": [ax, ay, arrow_d],
            "dims": {"pad_l": pad_l, "bounce": bounce},
            "blocks": [{"name": "text", "box": text_box}, {"name": "arrow", "box": arrow_box}], "pred_bbox": pred}


def circle_unit_points(seed_text):
    """Hand-drawn imperfect ellipse on the unit circle: start/end overlap 25 deg,
    low-frequency wobble, slight spiral so the two ends do not meet."""
    h = hashlib.sha256(seed_text.encode("utf-8")).digest()
    p1, p2, p3 = (h[i] / 255 * 2 * math.pi for i in range(3))
    start = math.radians(200 + h[3] / 255 * 40)  # begin upper-left, like a right-handed stroke
    sweep = 2 * math.pi + math.radians(CIRCLE_OVERLAP_DEG)
    pts = []
    for i in range(CIRCLE_N + 1):
        t = i / CIRCLE_N
        a = start + sweep * t
        # radius drifts inward over the stroke (ends pass each other ~9% apart),
        # plus low-frequency wobble; whole loop tilted ~-4 deg like a quick hand stroke
        r = 1.035 - 0.09 * t + 0.025 * math.sin(2 * a + p1) + 0.015 * math.sin(3 * a + p2)
        x, y = r * math.cos(a), r * (1 + 0.04 * math.sin(a + p3)) * math.sin(a)
        rot = math.radians(-4)
        pts.append([round(x * math.cos(rot) - y * math.sin(rot) * 0.5, 5), round(x * math.sin(rot) * 0.5 + y * math.cos(rot), 5)])
    return pts


def circle_geom(keys, lf_global):
    """Ease-in-out (smoothstep) interpolation of cx, cy, rx, ry between keys by global frame (clamped to key range)."""
    ks = sorted(keys, key=lambda k: k["f"])
    if lf_global <= ks[0]["f"]:
        k = ks[0]
        return k["cx"], k["cy"], k["rx"], k["ry"]
    for a, b in zip(ks, ks[1:]):
        if lf_global <= b["f"]:
            u = (lf_global - a["f"]) / (b["f"] - a["f"])
            u = u * u * (3 - 2 * u)
            return tuple(a[n] + (b[n] - a[n]) * u for n in ("cx", "cy", "rx", "ry"))
    k = ks[-1]
    return k["cx"], k["cy"], k["rx"], k["ry"]


def layout_circle(m, g, errs, pal, S):
    if g.get("label"):
        errs.append(f"circle label {g['label']!r} not implemented in kit v1 (all TC01 circles use label=null)")
    pts = circle_unit_points(g["id"])
    stroke = sc(CIRCLE_STROKE, S)
    outline = stroke + 2 * sc(CIRCLE_OUTLINE_EACH_SIDE, S)
    per_frame = []
    for lf in range(g["f1"] - g["f0"]):
        cx, cy, rx, ry = circle_geom(g["keys"], g["f0"] + lf)
        xs = [cx + p[0] * rx for p in pts]
        ys = [cy + p[1] * ry for p in pts]
        s = outline / 2
        per_frame.append([min(xs) - s, min(ys) - s, max(xs) + s, max(ys) + s])
    return {"unit_points": pts, "keys": g["keys"], "pred_bbox": union(per_frame), "pred_bbox_per_frame": per_frame, "blocks": [],
            "dims": {"stroke": stroke, "outline": outline}}


def missing_keys(g, errs, keys):
    bad = [k for k in keys if g.get(k) is None]
    if bad:
        errs.append(f"{g.get('type')} is missing required field(s) {bad}")
    return bool(bad)


def layout_title(m, g, errs, pal, S):
    """title_behind: one line, spans ~90% of the frame; exempt from graphics_scale."""
    if missing_keys(g, errs, ("text", "y")):
        return None
    text, y = g["text"].strip(), g["y"]
    if not text:
        errs.append("title_behind text is empty")
        return None
    rot = rotate_deg_of(g, errs)
    style = g.get("style", "fill")
    if style not in TITLE_STYLES:
        errs.append(f"title_behind style must be one of {TITLE_STYLES}, got {style!r}")
    if rot is None or style not in TITLE_STYLES:
        return None
    outline = style == "outline"
    l, t, r, b = ImageFont.truetype(m.path, 100).getbbox(text, anchor="ls")
    if outline:  # ink width = glyph width + stroke + 2 halo, all linear in size: solve for 90% of the frame width
        size = int((TITLE_W_TARGET * W - 2 * TITLE_OL_HALO) / ((r - l) / 100 + TITLE_OL_RATIO))
    else:
        size = int(100 * (TITLE_W_TARGET * W - 2 * TITLE_OUTLINE) / (r - l))
    if size < TITLE_FS_MIN:
        errs.append(f"title_behind text {text!r} too long: spanning {TITLE_W_TARGET:.0%} of the width needs {size}px font < minimum {TITLE_FS_MIN}px")
        return None
    size = min(size, TITLE_FS_MAX)
    f = ImageFont.truetype(m.path, size)
    l, t, r, b = f.getbbox(text, anchor="ls")
    adv = f.getlength(text)
    stroke_w = round(TITLE_OL_RATIO * size, 2)
    o = stroke_w / 2 + TITLE_OL_HALO if outline else TITLE_OUTLINE  # ink extent beyond the glyph edge
    ratio = (r - l + 2 * o) / W
    if not TITLE_W_MIN <= ratio <= TITLE_W_MAX:
        errs.append(f"title_behind text {text!r} spans {ratio:.0%} of the width at {size}px (allowed {TITLE_W_MIN:.0%}-{TITLE_W_MAX:.0%}): text too short")
        return None
    baseline = y - (t + b) / 2  # ink box vertically centred on y
    ox = 540 - adv / 2
    slack = 0.01 * (r - l)  # browser shaping/kerning vs PIL
    hold = [ox + l - o - slack, baseline + t - o, ox + r + o + slack, baseline + b + o]
    shake = TITLE_SHAKE
    rhold = scaled_rotated_bbox(hold, (540, y), 1.0, (540, y), rot)  # zone checks use the ROTATED box
    pred = [rhold[0] - shake, rhold[1] - shake, rhold[2] + shake, rhold[3] + shake]
    slam = scaled_rotated_bbox(hold, (540, y), TITLE_SLAM_SCALE, (540, y), rot)
    fk = g.get("fill")
    if fk is not None and (not isinstance(fk, str) or fk not in pal or not pal[fk]):
        errs.append(f"title_behind fill {fk!r} is not a key of style.palette")
        return None
    return {"text": text, "fill": pal[fk] if fk else pal["card_text"], "font_size": size, "baseline": baseline, "center": [540, y], "rotate_deg": rot, "title_style": style,
            "dims": {"outline": o, "shake": shake, **({"stroke_w": stroke_w, "halo": TITLE_OL_HALO} if outline else {})}, "zone": "title",
            "blocks": [], "pred_bbox": pred, "slam_bbox": slam, "slam_frames": TITLE_SLAM_F, "span_ratio": round(ratio, 3)}


def layout_big_text(m, g, errs, pal, S):
    """big_text: the key number of the video. accent = big line (card_accent, card_bg outline, glow),
    text = optional smaller line ABOVE it (card_text); with only `text` it is the big line. Exempt from graphics_scale."""
    if missing_keys(g, errs, ("text", "cy")):
        return None
    # keyword convention: `accent` is the big yellow key number; `text` is the smaller line above it.
    # Without `accent`, `text` is the big line.
    cy = g["cy"]
    rot = rotate_deg_of(g, errs)
    if rot is None:
        return None
    text, small = ((g["accent"].strip(), g["text"].strip()) if (g.get("accent") or "").strip() else (g["text"].strip(), ""))
    if not text:
        errs.append("big_text text is empty")
        return None
    if g["f1"] - g["f0"] < BT_IN_F + BT_OUT_F:
        errs.append(f"big_text needs at least {BT_IN_F + BT_OUT_F} frames (in {BT_IN_F} + out {BT_OUT_F}), got {g['f1'] - g['f0']}")
        return None
    o = BT_OUTLINE
    f100 = ImageFont.truetype(m.path, 100)
    l100, _, r100, _ = f100.getbbox(text, anchor="ls")
    res, hold_glow = None, None
    for target in (BT_W_TARGET, BT_W_MIN):
        size = int(100 * (target * W - 2 * o) / (r100 - l100))
        if size < BT_FS_MIN:
            errs.append(f"big_text text {text!r} too long: {target:.0%} of the width needs {size}px font < minimum {BT_FS_MIN}px")
            return None
        size = min(size, BT_FS_MAX)
        f = ImageFont.truetype(m.path, size)
        l, t, r, b = f.getbbox(text, anchor="ls")
        adv = f.getlength(text)
        ratio = (r - l + 2 * o) / W
        if ratio < BT_W_MIN - 0.005:
            errs.append(f"big_text text {text!r} spans {ratio:.0%} of the width at the {BT_FS_MAX}px cap (allowed {BT_W_MIN:.0%}-{BT_W_MAX:.0%}): text too short")
            return None
        baseline = cy - (t + b) / 2  # ink box vertically centred on cy
        slack = 0.005 * (r - l)
        ox = 540 - adv / 2
        big = [ox + l - o - slack, baseline + t - o, ox + r + o + slack, baseline + b + o]
        blocks = [{"name": "text", "box": big}]
        group = [big]
        lay = {"text": text, "font_size": size, "baseline": baseline, "center": [540, cy], "span_ratio": round(ratio, 3)}
        if small:
            ssz = round(size * BT_SMALL_RATIO)
            sf = ImageFont.truetype(m.path, ssz)
            sl, st, sr, sb = sf.getbbox(small, anchor="ls")
            sw = sf.getlength(small)
            so = BT_SMALL_OUTLINE
            if sr - sl + 2 * so > (r - l):
                errs.append(f"big_text small line {small!r} at {ssz}px is wider ({sr - sl + 2 * so:.0f}px) than the big line ({r - l:.0f}px)")
                return None
            sbase = big[1] - BT_GAP - so - sb  # small ink bottom + outline sits BT_GAP above the big box
            sslack = 0.01 * (sr - sl)
            sbox = [540 - sw / 2 + sl - so - sslack, sbase + st - so, 540 - sw / 2 + sr + so + sslack, sbase + sb + so]
            blocks.append({"name": "accent", "box": sbox})
            group.append(sbox)
            lay["accent"] = {"text": small, "size": ssz, "baseline": sbase, "outline": so}
        hold = union(group)
        hold_glow = [hold[0] - BT_GLOW, hold[1] - BT_GLOW, hold[2] + BT_GLOW, hold[3] + BT_GLOW]
        # Largest overshoot (<= 1.08) whose bbox still clears every zone; the hold itself must clear them.
        # rotation (about the centre of the whole block) is the outer transform, the pop scale (about 540, cy) the inner one.
        rc = (540, (hold[1] + hold[3]) / 2)
        peak, e = BT_PEAK_MAX, []
        while peak >= 1.0 - 1e-9:
            e = zone_errors(scaled_rotated_bbox(hold_glow, (540, cy), peak, rc, rot))
            if not e:
                break
            peak = round(peak - 0.01, 2)
        if not e and peak >= 1.0 - 1e-9:
            res = dict(lay, blocks=blocks, pred_bbox=scaled_rotated_bbox(hold_glow, (540, cy), peak, rc, rot),
                       hold_bbox=scaled_rotated_bbox(hold_glow, (540, cy), 1.0, rc, rot), rotate_deg=rot, rotate_center=list(rc),
                       dims={"outline": o, "glow": BT_GLOW, "peak": peak, "in_f": BT_IN_F, "out_f": BT_OUT_F})
            break
    if res is None:
        hb = scaled_rotated_bbox(hold_glow, (540, cy), 1.0, rc, rot)
        rtag = f", rotated {rot:g} deg" if rot else ""
        errs += [f"big_text hold bbox {fmt(hb)} (glow incl.{rtag}): {x}" for x in zone_errors(hb)]
        return None
    return res


def layout_arrow(m, g, errs, pal, S):
    """arrow: hand-drawn curved arrow from `from` to `to` (px), palette circle + circle_outline, draws on in 8 frames."""
    pts_in = []
    for k in ("from", "to"):
        v = g.get(k)
        if not (isinstance(v, list) and len(v) == 2 and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in v)):
            errs.append(f"arrow {k!r} must be [x, y] numbers, got {v!r}")
        else:
            pts_in.append(v)
    if len(pts_in) < 2:
        return None
    (x0, y0), (x1, y1) = pts_in
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 120:
        errs.append(f"arrow too short ({length:.0f}px < 120px)")
        return None
    h = hashlib.sha256(g["id"].encode("utf-8")).digest()
    side = 1 if h[0] % 2 else -1
    bend = side * ARROW_BEND * length * (0.85 + h[1] / 255 * 0.3)
    cx, cy = (x0 + x1) / 2 - dy / length * bend, (y0 + y1) / 2 + dx / length * bend  # quadratic control point
    pts = []
    for i in range(ARROW_N + 1):
        t = i / ARROW_N
        wob = 1.5 * math.sin(t * 9 + h[2]) * math.sin(math.pi * t)  # slight hand tremor, zero at both ends
        pts.append([round((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1 - dy / length * wob, 2),
                    round((1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1 + dx / length * wob, 2)])
    ta = math.atan2(y1 - pts[-2][1], x1 - pts[-2][0])  # end tangent
    hl = sc(ARROW_HEAD_LEN, S)
    head = [[round(x1 - hl * math.cos(ta + d * math.radians(ARROW_HEAD_DEG)), 2), round(y1 - hl * math.sin(ta + d * math.radians(ARROW_HEAD_DEG)), 2)]
            for d in (1, -1)]
    stroke = sc(CIRCLE_STROKE, S)
    outline = stroke + 2 * sc(CIRCLE_OUTLINE_EACH_SIDE, S)
    allp = pts + head
    e = outline / 2
    pred = [min(p[0] for p in allp) - e, min(p[1] for p in allp) - e, max(p[0] for p in allp) + e, max(p[1] for p in allp) + e]
    return {"body": pts, "head": head, "tip": [x1, y1], "pred_bbox": pred, "blocks": [], "dims": {"stroke": stroke, "outline": outline}}


def clean_alpha(im):
    """Cutout cleanup before outlining: alpha < 0.35 -> 0 (kills shadow fringes), drop disconnected alpha
    islands smaller than 2% of the largest component."""
    a = np.array(im.getchannel("A"))
    a[a < CUT_ALPHA_MIN] = 0
    n, lab, stats, _ = cv2.connectedComponentsWithStats((a > 0).astype(np.uint8), connectivity=8)
    if n > 2:
        areas = stats[1:, cv2.CC_STAT_AREA]
        keep = np.zeros(n, bool)
        keep[1:] = areas >= CUT_ISLAND_FRAC * areas.max()
        a[~keep[lab]] = 0
    im = im.copy()
    im.putalpha(Image.fromarray(a))
    return im


def cutout_png(path, h, errs):
    """Image scaled to height h with a white outline (dilated alpha) and a soft drop shadow baked in.
    Returns (data_uri, (canvas_w, canvas_h), visible_bbox_in_canvas, image_w) or None."""
    if not isinstance(path, str) or not os.path.isfile(path):
        errs.append(f"cutout image missing or not a file: {path!r}")
        return None
    try:
        im = Image.open(path)
        im.load()
    except Exception as e:  # noqa: BLE001 - reported as a layout error, never swallowed
        errs.append(f"cutout image unreadable: {path!r}: {e}")
        return None
    if "A" not in im.getbands():
        errs.append(f"cutout image has no alpha channel: {path!r} (mode {im.mode})")
        return None
    im = clean_alpha(im.convert("RGBA"))
    box = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if box is None:
        errs.append(f"cutout image is fully transparent: {path!r}")
        return None
    im = im.crop(box)
    w0 = max(1, round(im.width * h / im.height))
    im = im.resize((w0, h), Image.LANCZOS)
    ea = cv2.erode(np.array(im.getchannel("A")), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))  # erode 1 px at final size
    im.putalpha(Image.fromarray(ea))
    cw, ch = w0 + 2 * CUT_PAD, h + 2 * CUT_PAD
    cw, ch = cw + cw % 2, ch + ch % 2  # even canvas so the centre is an integer
    ox, oy = (cw - w0) // 2, (ch - h) // 2
    base = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    base.paste(im, (ox, oy))
    a = np.array(base.getchannel("A"))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * CUT_OUTLINE + 1, 2 * CUT_OUTLINE + 1))
    a_out = cv2.dilate(a, k)
    sh = Image.new("L", (cw, ch), 0)
    sh.paste(Image.fromarray(a_out), (0, CUT_SHADOW_DY))
    sh = sh.filter(ImageFilter.GaussianBlur(CUT_SHADOW_SIGMA)).point(lambda v: int(v * CUT_SHADOW_ALPHA))
    shadow = Image.merge("RGBA", (*Image.new("RGB", (cw, ch), (0, 0, 0)).split(), sh))
    outline = Image.merge("RGBA", (*Image.new("RGB", (cw, ch), (255, 255, 255)).split(), Image.fromarray(a_out)))
    out = Image.alpha_composite(Image.alpha_composite(shadow, outline), base)
    vis = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"), (cw, ch), vis, w0


def layout_cutout(m, g, errs, pal, S):
    if missing_keys(g, errs, ("image", "cx", "cy", "h")):
        return None
    cx, cy, h = g["cx"], g["cy"], g["h"]
    if not isinstance(h, int) or h <= 0:
        errs.append(f"cutout h must be a positive integer px, got {h!r}")
        return None
    if g["f1"] - g["f0"] < CUT_POP_F + CUT_OUT_F:
        errs.append(f"cutout needs at least {CUT_POP_F + CUT_OUT_F} frames (pop-in {CUT_POP_F} + out {CUT_OUT_F}), got {g['f1'] - g['f0']}")
        return None
    res = cutout_png(g["image"], h, errs)
    if res is None:
        return None
    uri, (cw, ch), vis, w0 = res
    left, top = cx - cw / 2, cy - ch / 2
    img_vis = [left + vis[0], top + vis[1], left + vis[2], top + vis[3]]
    blocks = [{"name": "image", "box": [cx - w0 / 2 - CUT_OUTLINE, cy - h / 2 - CUT_OUTLINE, cx + w0 / 2 + CUT_OUTLINE, cy + h / 2 + CUT_OUTLINE]}]
    lay = {"src": uri, "canvas": [left, top, cw, ch], "center": [cx, cy], "image_w": w0, "image_visible_bbox": img_vis,
           "dims": {"float_px": CUT_FLOAT_PX, "pop_f": CUT_POP_F, "out_f": CUT_OUT_F, "overshoot": CUT_POP_OVERSHOOT, "deg": CUT_POP_DEG}}
    group = [img_vis]
    if g.get("label"):
        fs, pad_y, pad_x, gap = sc(CUT_LB_FS, S), sc(CUT_LB_PAD_Y, S), sc(CUT_LB_PAD_X, S), sc(CUT_LB_GAP, S)
        lh = round(fs * 1.2)
        tw = math.ceil(m.width(g["label"], fs))
        pw, ph = tw + 2 * pad_x, lh + 2 * pad_y
        pl, pt = cx - pw / 2, cy + h / 2 + CUT_OUTLINE + gap
        pill = [pl, pt, pl + pw, pt + ph]
        i_t, i_b = m.ink(g["label"], fs, lh)
        ink = [pl + pad_x, pt + pad_y + i_t, pl + pad_x + tw, pt + pad_y + i_b]
        if not inside(ink, [pl, pt + 2, pl + pw, pt + ph - 2]):
            errs.append(f"cutout label ink {fmt(ink)} outside pill {fmt(pill)}")
        lay["label"] = {"text": g["label"], "box": pill, "tw": tw, "lh": lh, "font_size": fs, "pad_x": pad_x}
        blocks.append({"name": "label", "box": pill})
        group.append(pill)
    # Conservative prediction: pop overshoot scale + 4 deg rotation about the image centre, plus the float.
    pb = [transformed_bbox(b, cx, cy, CUT_POP_OVERSHOOT, CUT_POP_DEG) for b in group]
    pred = union(pb)
    pred = [pred[0], pred[1] - CUT_FLOAT_PX, pred[2], pred[3] + CUT_FLOAT_PX]
    lay.update({"blocks": blocks, "pred_bbox": pred})
    return lay


def layout_frame(m, g, errs, pal, S):
    """frame: 1+ panels of B-roll clips with border, rounded corners, drop shadow and a label pill straddling the top border.
    All frames below are LOCAL (0 = g.f0). The validator (pipeline-v6/build/validate_script.py) owns the timing/source rules;
    this only computes geometry and rejects what does not fit. Defaults are written out explicitly."""
    f0, f1 = g["f0"], g["f1"]
    xf = g.get("xfade_f", 0)
    if not (isinstance(xf, int) and not isinstance(xf, bool) and 0 <= xf <= 12 and xf % 2 == 0):
        errs.append(f"frame xfade_f must be an even integer in 0..12, got {xf!r}")
        return None
    h = xf // 2
    style = g.get("style", "card")
    if style not in ("card", "blend"):
        errs.append(f"frame style must be 'card' or 'blend', got {style!r}")
        return None
    blend = style == "blend"  # borderless feathered panels blended into the scene: no border/radius/shadow/labels, may overlap
    b, radius, dy, blur = (0, 0, 0, 0) if blend else (sc(FR_BORDER, S), sc(FR_RADIUS, S), sc(FR_SH_DY, S), sc(FR_SH_BLUR, S))
    fs, pad_x, pad_y, lb_x, slide = sc(FR_LB_FS, S), sc(FR_LB_PAD_X, S), sc(FR_LB_PAD_Y, S), sc(FR_LB_X, S), sc(FR_SLIDE, S)
    lh = round(fs * 1.2)
    # One pill height + text offset for ALL labels of this frame (a label swap must not jump): the ink band of the probe set
    # and every label, vertically centred, with FR_LB_INK_PAD (>= FR_LB_CLEAR) px above and below it.
    if blend and any(c.get("label") for p in g.get("panels") or [] for c in p["clips"]):
        errs.append("frame style blend has no label pills: remove clip label")
        return None
    texts = [FR_PROBE_TOP, FR_PROBE_BOT] + [c["label"] for p in g.get("panels") or [] for c in p["clips"] if c.get("label")]
    inks = [m.ink(t, fs, lh) for t in texts]
    ink_t, ink_b = min(i[0] for i in inks), max(i[1] for i in inks)
    lb_pad = max(sc(FR_LB_INK_PAD, S), FR_LB_CLEAR)
    ph = math.ceil(ink_b - ink_t + 2 * lb_pad)
    text_top = (ph - (ink_b - ink_t)) / 2 - ink_t  # top of the CSS line box inside the pill
    full_bleed = g.get("full_bleed", False)
    if not isinstance(full_bleed, bool):
        errs.append(f"frame full_bleed must be a boolean, got {full_bleed!r}")
        return None
    panels, preds, outers, labels = [], [], [], []  # labels: (panel index, local f0, local f1, pill box)
    zone_preds = []  # full_bleed: only label pills are zone-checked (video boxes may cover the whole canvas)
    for pi, p in enumerate(g.get("panels") or []):
        x0, y0, x1, y1 = p["box"]
        if (full_bleed or blend) and not (0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H and x1 - x0 >= FR_MIN_BOX and y1 - y0 >= FR_MIN_BOX):
            errs.append(f"frame {style if blend else 'full_bleed'} panel {pi} box {[x0, y0, x1, y1]} must lie inside the {W}x{H} canvas and be >= {FR_MIN_BOX} px")
            return None
        enter = p.get("enter", "pop")
        feather = {k: p.get("feather", {}).get(k, 0) for k in ("top", "bottom", "left", "right")}
        outer = [x0 - b, y0 - b, x1 + b, y1 + b]
        shadow = [outer[0] - blur, outer[1] + dy - blur, outer[2] + blur, outer[3] + dy + blur]  # offset + blur counted as extent
        group = [outer, shadow]
        lgroup = []
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        clips, prev_label = [], None
        n = len(p["clips"])
        for ci, c in enumerate(p["clips"]):
            h_in, h_out = (h if ci > 0 else 0), (h if ci < n - 1 else 0)
            z = c.get("zoom") or {}
            spec = {"f0": c["f0"] - f0, "f1": c["f1"] - f0, "seq_from": c["f0"] - h_in - f0, "seq_len": c["f1"] - c["f0"] + h_in + h_out,
                    "h_in": h_in, "h_out": h_out, "zoom_from": float(z.get("from", 1.0)), "zoom_to": float(z.get("to", 1.0)),
                    "easing": z.get("easing", "linear"), "center": list(c.get("center", [0.5, 0.5])),
                    "proxy": {"path": c["path"], "src_start_f": c["src_in_f"] - h_in, "frames": c["f1"] - c["f0"] + h_in + h_out,
                              "src": f"frame/{g['id']}_p{pi}_c{ci}.mp4"}, "label": None}
            lb = c.get("label")
            if lb:
                tw = math.ceil(m.width(lb, fs))
                pw = tw + 2 * pad_x
                if pw > (x1 - x0) - 2 * lb_x:
                    errs.append(f"frame panel {pi} label {lb!r} pill width {pw} > panel width {x1 - x0} - 2x{lb_x}")
                    return None
                pl, pt = x0 + lb_x, (y0 - b / 2) - ph / 2  # vertical centre on the top border line
                pill = [pl, pt, pl + pw, pt + ph]
                i_t, i_b = m.ink(lb, fs, lh)
                ink = [pl + pad_x, pt + text_top + i_t, pl + pad_x + tw, pt + text_top + i_b]
                if not inside(ink, [pl, pt + FR_LB_CLEAR, pl + pw, pt + ph - FR_LB_CLEAR]):
                    errs.append(f"frame label ink {fmt(ink)} outside pill {fmt(pill)}")
                pop_in = ci > 0 and lb != prev_label
                nxt = p["clips"][ci + 1].get("label") if ci < n - 1 else lb
                spec["label"] = {"text": lb, "box": pill, "tw": tw, "lh": lh, "font_size": fs, "pad_x": pad_x, "text_top": text_top,
                                 "pop_in": pop_in, "pop_out": ci < n - 1 and nxt != lb}
                lbb = transformed_bbox(pill, (pill[0] + pill[2]) / 2, (pill[1] + pill[3]) / 2, FR_LB_POP if pop_in else 1.0, 0)
                group.append(lbb)
                lgroup.append(lbb)
                labels.append((pi, max(spec["f0"], p["f_in"] - f0), spec["f1"], pill))
            prev_label = lb
            clips.append(spec)
        grp = union(group)
        if enter == "pop":
            pred = transformed_bbox(grp, cx, cy, FR_POP, 0)  # transform origin = panel box centre
        elif enter == "slide":
            pred = [grp[0], grp[1] - slide, grp[2], grp[3]]
        else:
            pred = grp
        preds.append(pred)
        if full_bleed and lgroup:
            lg = union(lgroup)
            zone_preds.append(transformed_bbox(lg, cx, cy, FR_POP, 0) if enter == "pop"
                              else [lg[0], lg[1] - slide, lg[2], lg[3]] if enter == "slide" else lg)
        outers.append(outer)
        panels.append({"box": [x0, y0, x1, y1], "f_in": p["f_in"] - f0, "enter": enter, "clips": clips, "pred_bbox": pred, "feather": feather})
    blocks = [{"name": f"panel {i}", "box": o} for i, o in enumerate(outers)]
    # full_bleed grids are tiled edge to edge with a small gap: only the video boxes must not overlap (borders may touch)
    solid = [p["box"] for p in panels] if full_bleed else outers
    for i in range(0 if blend else len(solid)):  # blend panels overlap on purpose (cross-fade): no overlap rule
        for j in range(i + 1, len(solid)):
            if rect_intersects(solid[i], solid[j]):
                errs.append(f"frame panels intersect{'' if full_bleed else ' (borders incl.)'}: panel {i} {fmt(solid[i])} vs panel {j} {fmt(solid[j])}")
    for i, (pa, a0, a1, ba) in enumerate(labels):
        for pb, b0, b1, bb in labels[i + 1:]:
            if pa != pb and a0 < b1 and b0 < a1 and rect_intersects(ba, bb):
                errs.append(f"frame labels of panel {pa} {fmt(ba)} and panel {pb} {fmt(bb)} intersect while both visible")
        for k, o in enumerate(outers):
            if k != pa and rect_intersects(ba, o):
                errs.append(f"frame label of panel {pa} {fmt(ba)} overlaps panel {k} {fmt(o)}")
        blocks.append({"name": f"label panel {pa} f{a0}-{a1}", "box": ba})
    lay = {"panels": panels, "xfade_f": xf, "pred_bbox": union(preds), "blocks": [], "frame_blocks": blocks,
            "dims": {"border": b, "radius": radius, "shadow_dy": dy, "shadow_blur": blur, "shadow_alpha": FR_SH_ALPHA,
                     "slide": slide, "pop": FR_POP, "label_pop": FR_LB_POP, "enter_f": FR_ENTER_F}, "style": style}
    if full_bleed or blend:
        lay["zone_bbox"] = union(zone_preds) if zone_preds else None
        lay["zone"] = "none"  # rendered alpha bbox (check_frames.py) cannot separate pills from video: skipped; pills are checked here
    return lay


def layout_flash(m, g, errs, pal, S):
    if g["f1"] - g["f0"] < 2:
        errs.append("flash needs at least 2 frames")
        return None
    return {"blocks": [], "pred_bbox": [0, 0, W, H], "zone": "none", "expect_empty_last": True, "peak": FLASH_PEAK}


LAYOUT = {"keyword": layout_keyword, "checklist": layout_checklist, "cta": layout_cta, "circle": layout_circle,
          "title_behind": layout_title, "cutout": layout_cutout, "flash": layout_flash, "big_text": layout_big_text, "arrow": layout_arrow,
          "frame": layout_frame}


def item_texts(g):
    t = [g.get("text") or "", g.get("accent") or "", g.get("label") or ""]
    t += [i["text"] for i in g.get("items", [])]
    t += [c.get("label") or "" for p in g.get("panels") or [] for c in p.get("clips") or []]
    return "".join(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--font", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-zone-check", action="store_true", help="fixture use only: let off-zone items through to test the frame checker")
    a = ap.parse_args()
    with open(a.script, "r", encoding="utf-8-sig") as fh:
        script = json.load(fh)
    if script.get("fps") != 30 or script.get("width") != W or script.get("height") != H:
        print(f"ERROR: kit expects 30 fps {W}x{H}, got {script.get('fps')} {script.get('width')}x{script.get('height')}")
        return 1
    pal, perr = get_palette(script)
    if perr:
        print("REJECTED:")
        for e in perr:
            print("  " + e)
        return 1
    scale, serr = get_scale(script)
    if serr:
        print("REJECTED:")
        for e in serr:
            print("  " + e)
        return 1
    by_type, terr = get_scale_by_type(script)
    if terr:
        print("REJECTED:")
        for e in terr:
            print("  " + e)
        return 1
    m = Measure(a.font)
    out, all_errs = [], []
    for g in script.get("graphics", []):
        errs = []
        gid = g.get("id", "?")
        for k in ("f0", "f1"):
            if not isinstance(g.get(k), int):
                errs.append(f"{k} must be an integer frame (R1), got {g.get(k)!r}")
        if not errs and not (0 <= g["f0"] < g["f1"] <= script["duration_f"]):
            errs.append(f"bad range f0={g['f0']} f1={g['f1']} duration_f={script['duration_f']}")
        fn = LAYOUT.get(g.get("type"))
        if fn is None:
            errs.append(f"unknown graphic type {g.get('type')!r}")
        if g.get("exit", "default") not in ("none", "default"):
            errs.append(f"exit must be 'none' or 'default', got {g.get('exit')!r}")
        miss = m.missing(item_texts(g))
        if miss:
            errs.append(f"font lacks glyphs {miss!r}")
        lay = None
        if not errs:
            lay = fn(m, g, errs, pal, by_type.get(g["type"], scale))
        if lay is not None:
            bl = lay["blocks"]
            for i in range(len(bl)):
                for j in range(i + 1, len(bl)):
                    if rect_intersects(bl[i]["box"], bl[j]["box"]):
                        errs.append(f"layout boxes intersect: {bl[i]['name']!r} {fmt(bl[i]['box'])} vs {bl[j]['name']!r} {fmt(bl[j]['box'])}")
            if not a.no_zone_check:
                zk = "std" if "zone_bbox" in lay else lay.get("zone", "std")
                zb = lay.get("zone_bbox", lay["pred_bbox"])  # frame full_bleed: label pills only (may be None)
                if zb is not None:
                    errs += [f"predicted {e}" for e in zone_errors(zb, zk)]
                if lay.get("slam_bbox"):
                    errs += [f"predicted slam-in {e}" for e in zone_errors(lay["slam_bbox"], "title_slam")]
        if errs:
            all_errs += [f"{gid}: {e}" for e in errs]
            continue
        lay["palette"] = pal
        lay["exit_none"] = g.get("exit") == "none"
        lay.pop("pred_bbox_per_frame", None)
        visible_from = lay.pop("visible_from", 0)
        out.append({"id": gid, "type": g["type"], "f0": g["f0"], "f1": g["f1"], "frames": g["f1"] - g["f0"],
                    "visible_from": visible_from, "zone": lay.get("zone", "std"), "slam_frames": lay.get("slam_frames", 0),
                    "expect_empty_last": bool(lay.get("expect_empty_last")) and not lay["exit_none"], "item": g, "layout": lay})
    if all_errs:
        print("REJECTED:")
        for e in all_errs:
            print("  " + e)
        return 1
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"graphics_scale": scale, "scale_by_type": by_type, "items": out, "zones": {"safe": SAFE, "tiktok": TIKTOK, "sub_band": SUB_BAND}}, fh, ensure_ascii=False, indent=1)
    for o in out:
        L = o["layout"]
        print(f"{o['id']} {o['type']:12s} frames={o['frames']:3d} pred_bbox={fmt(L['pred_bbox'])}"
              + (f" font={L.get('font_size')}" if L.get("font_size") else "")
              + (f" accent={L.get('accent_size')}" if L.get("accent_size") else "")
              + (f" visible_from={o['visible_from']}" if o["visible_from"] else ""))
    print(f"OK {len(out)} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
