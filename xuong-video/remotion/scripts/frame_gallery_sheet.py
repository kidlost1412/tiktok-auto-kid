"""Compose the frame style contact sheet from frame_gallery.mjs tiles (called by it; not a public entry point).

python frame_gallery_sheet.py --tiles <dir with <id>-grid.png, <id>-card.png, samples.json> --out sheet.jpg [--profile p.json]
Sample scene: a muted outdoor-looking gradient (stand-in for the speaker) and synthetic "photo" fills in each box, so the
decoration is judged over content, not over flat grey. No footage is read.
"""
import argparse, json, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frame_style as fsy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "public" / "v6" / "fonts" / "BeVietnamPro-Black.ttf"
TW, TH = 270, 480
FILLS = [((214, 168, 96), (92, 128, 64)), ((120, 170, 210), (60, 110, 70)), ((180, 120, 80), (70, 60, 50)), ((150, 190, 120), (40, 90, 60))]


def vgrad(w, h, top, bot):
    g = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return g.resize((w, h))


def scene(boxes):
    img = vgrad(1080, 1920, (176, 196, 205), (78, 96, 70)).convert("RGBA")
    for k, b in enumerate(boxes):
        x0, y0, x1, y1 = [int(v) for v in b["box"]]
        top, bot = FILLS[k % len(FILLS)]
        ph = vgrad(x1 - x0, y1 - y0, top, bot).convert("RGBA")
        m = Image.new("L", ph.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, ph.size[0] - 1, ph.size[1] - 1], radius=b["radius"], fill=255)
        img.paste(ph, (x0, y0), m)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiles", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--profile")
    a = ap.parse_args()
    tiles = Path(a.tiles)
    samples = json.loads((tiles / "samples.json").read_text(encoding="utf-8"))
    cat = fsy.load_catalog()
    liked, rejected = fsy.taste(fsy.read_profile(a.profile)) if a.profile else ([], [])
    styles = cat["styles"]
    cols = 6                                   # 3 styles per row, 2 tiles each
    rows = (len(styles) + 2) // 3
    cap = 64
    sheet = Image.new("RGB", (cols * TW + (cols + 1) * 8, rows * (TH + cap) + (rows + 1) * 8), (24, 24, 24))
    f1, f2 = ImageFont.truetype(str(FONT), 22), ImageFont.truetype(str(FONT), 15)
    dr = ImageDraw.Draw(sheet)
    for i, s in enumerate(styles):
        r, c0 = divmod(i, 3)
        for j, kind in enumerate(("grid", "card")):
            img = scene(samples[kind])
            img.alpha_composite(Image.open(tiles / f"{s['id']}-{kind}.png").convert("RGBA"))
            x = 8 + (c0 * 2 + j) * (TW + 8)
            y = 8 + r * (TH + cap + 8)
            sheet.paste(img.convert("RGB").resize((TW, TH), Image.LANCZOS), (x, y + cap))
        x = 8 + c0 * 2 * (TW + 8)
        y = 8 + r * (TH + cap + 8)
        mark = "  [THÍCH]" if s["id"] in liked else "  [ĐÃ LOẠI]" if s["id"] in rejected else ""
        dr.text((x + 4, y + 6), f"{s['id']}{mark}", font=f1, fill=(255, 120, 120) if s["id"] in rejected else (255, 255, 255))
        dr.text((x + 4, y + 36), s["name_vi"], font=f2, fill=(200, 200, 200))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(a.out, quality=90)


if __name__ == "__main__":
    main()
