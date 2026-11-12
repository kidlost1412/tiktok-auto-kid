"""Contact sheet: hold frame (frames-7, before the out animation) of every item
composited over mid-grey and over the main video frame at the same global
frame. Usage: python contact_sheet.py --layout layout.json --dir <render dir> --main <video> --out sheet.png"""
import argparse
import json
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

TW, TH, LAB = 360, 640, 34
GUIDE = (255, 0, 255, 255)


def frame_png(args):
    r = subprocess.run(["ffmpeg", "-v", "error", *args, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                       capture_output=True, check=True)
    return Image.frombuffer("RGBA", (1080, 1920), r.stdout[:1080 * 1920 * 4], "raw", "RGBA", 0, 1)


def guides(img):
    d = ImageDraw.Draw(img)
    d.rectangle([70, 150, 1010, 1560], outline=GUIDE, width=3)
    d.rectangle([930, 900, 1080, 1600], outline=(255, 160, 0, 255), width=3)
    d.rectangle([0, 1330, 1080, 1520], outline=(0, 200, 255, 255), width=3)
    return img


def main():
    ap = argparse.ArgumentParser()
    for k in ("layout", "dir", "main", "out", "font"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    items = json.load(open(a.layout, encoding="utf-8-sig"))["items"]
    font = ImageFont.truetype(a.font, 22)
    cols = 4  # item pairs per row
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 2 * TW, rows * (TH + LAB)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for n, it in enumerate(items):
        hold = max(0, it["frames"] - 7)
        g = frame_png(["-i", f"{a.dir}/{it['id']}.mov", "-vf", f"select=eq(n\\,{hold})"])
        gf = it["f0"] + hold
        bg = frame_png(["-ss", f"{gf / 30:.4f}", "-i", a.main, "-vf", "scale=1080:1920"]).convert("RGBA")
        grey = Image.new("RGBA", (1080, 1920), (128, 128, 128, 255))
        x, y = (n % cols) * 2 * TW, (n // cols) * (TH + LAB)
        for k, base in enumerate((grey, bg)):
            comp = guides(Image.alpha_composite(base, g))
            sheet.paste(comp.convert("RGB").resize((TW, TH), Image.LANCZOS), (x + k * TW, y + LAB))
        d.text((x + 8, y + 4), f"{it['id']} {it['type']} f{it['f0']}-{it['f1']} hold local {hold} (global {gf})", fill=(255, 255, 255), font=font)
    sheet.save(a.out)
    print(f"contact sheet {sheet.size} -> {a.out}")
    # Full-size hold frames of text items for close inspection of diacritics.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
