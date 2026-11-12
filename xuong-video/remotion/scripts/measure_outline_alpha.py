"""Alpha probes for a title_behind style=outline render (used by test_text_style.mjs).

Rebuilds the glyph mask with PIL at the layout's font size/baseline, scans the row through the ink centre and prints JSON with the
rendered alpha (0..1) of one decoded frame at: the centre of the first ink run (letter body, between the two outline strokes),
the left outline stroke (glyph edge), the gap between the first two runs (letter counter) and the stroke width in px.
Usage: python measure_outline_alpha.py --layout layout.json --id <id> --mov <file.mov> --frame N --font <ttf>
"""
import argparse
import json
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--mov", required=True)
    ap.add_argument("--frame", type=int, required=True)
    ap.add_argument("--font", required=True)
    a = ap.parse_args()
    with open(a.layout, encoding="utf-8") as fh:
        it = next(i for i in json.load(fh)["items"] if i["id"] == a.id)
    L = it["layout"]
    f = ImageFont.truetype(a.font, L["font_size"])
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).text((540 - f.getlength(L["text"]) / 2, L["baseline"]), L["text"], font=f, fill=255, anchor="ls")
    t, b = f.getbbox(L["text"], anchor="ls")[1], f.getbbox(L["text"], anchor="ls")[3]
    row_y = int(round(L["baseline"] + (t + b) / 2))
    row = np.array(mask)[row_y] > 127
    edges = np.flatnonzero(np.diff(row.astype(np.int8)))
    runs = [(int(edges[i]) + 1, int(edges[i + 1]) + 1) for i in range(0, len(edges) - 1, 2)]  # [x0, x1) of each ink run on the row
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", a.mov, "-vf", f"select='eq(n,{a.frame})'", "-frames:v", "1", "-pix_fmt", "rgba", "-f", "rawvideo", "pipe:1"],
                         capture_output=True, check=True).stdout
    al = np.frombuffer(raw, np.uint8).reshape(H, W, 4)[:, :, 3] / 255.0
    r0, r1 = runs[0], runs[1]
    out = {"row_y": row_y, "run0": r0, "run1": r1, "stroke_w": L["dims"]["stroke_w"],
           "alpha_stroke_center": float(al[row_y, r0[0]]), "alpha_body_center": float(al[row_y, (r0[0] + r0[1]) // 2]),
           "alpha_counter_center": float(al[row_y, (r0[1] + r1[0]) // 2]), "body_width": r0[1] - r0[0], "counter_width": r1[0] - r0[1]}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
