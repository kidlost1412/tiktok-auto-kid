"""Every-frame alpha check of rendered kit clips (R9).

For each item in layout.json, decodes <dir>/<id>.mov with ffmpeg to RGBA and,
for EVERY frame: alpha bbox (alpha > 8/255) must be non-empty when the layout
says something is visible (empty before the first checklist item), inside the
safe zone, outside the TikTok button zone and outside the subtitle band.
Also checks pixel format has alpha and frame count == f1 - f0.
Per-type rules: title_behind uses the relaxed x margin on hold frames and only the
TikTok/sub-band/vertical rules on the first `slam_frames` frames; flash is exempt from
zone checks but must be a white full-frame layer at frame 0 (alpha >= 0.8), decay
monotonically and be empty on its last frame.

Usage: python check_frames.py --layout layout.json --dir <render dir> --out frame-checks.json
Exit 1 if any frame fails.
"""
import argparse
import json
import subprocess
import sys

import numpy as np

sys.path.insert(0, __import__("os").path.dirname(__file__))
from kit_layout import H, W, zone_errors  # noqa: E402

ALPHA_MIN = 8


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                        "stream=codec_name,profile,pix_fmt,width,height,nb_read_frames,r_frame_rate", "-of", "json", path],
                       capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)["streams"][0]


def frames_rgba(path):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgba", "-"], stdout=subprocess.PIPE)
    n = W * H * 4
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 4)
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg decode failed for {path}")


def check_item(it, d):
    path = f"{d}/{it['id']}.mov"
    st = probe(path)
    errs = []
    if not st["pix_fmt"].startswith("yuva"):
        errs.append(f"pix_fmt {st['pix_fmt']} has no alpha")
    if int(st["nb_read_frames"]) != it["frames"]:
        errs.append(f"frame count {st['nb_read_frames']} != {it['frames']}")
    if (st["width"], st["height"]) != (W, H):
        errs.append(f"size {st['width']}x{st['height']}")
    bboxes, bad = [], []
    exit_none = it["layout"].get("exit_none", False)
    amax_peak = last_amax = 0
    zone, slam = it.get("zone", "std"), it.get("slam_frames", 0)
    amax_prev = 256
    for i, fr in enumerate(frames_rgba(path)):
        if it["type"] == "flash":
            amax = int(fr[:, :, 3].max())
            if amax > amax_prev:
                bad.append(f"frame {i}: flash alpha rose to {amax} (was {amax_prev})")
            amax_prev = amax
            if i == 0:
                solid = fr[:, :, 3] >= 0.8 * 255
                if not solid.all():
                    bad.append(f"frame 0: flash not full-frame (alpha>=0.8 on {solid.mean():.1%} of pixels)")
                elif fr[:, :, :3][solid].min() < 250:
                    bad.append(f"frame 0: flash not white (min rgb {int(fr[:, :, :3][solid].min())})")
        last_amax = int(fr[:, :, 3].max())
        amax_peak = max(amax_peak, last_amax)
        a = fr[:, :, 3] > ALPHA_MIN
        ys, xs = np.nonzero(a.any(axis=1))[0], np.nonzero(a.any(axis=0))[0]
        expect = i >= it["visible_from"] and not (it.get("expect_empty_last") and i == it["frames"] - 1)
        if len(xs) == 0:
            bboxes.append(None)
            if expect:
                bad.append(f"frame {i}: empty alpha")
            continue
        bb = [int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1]
        bboxes.append(bb)
        if not expect:
            bad.append(f"frame {i}: alpha {bb} where the frame should be empty")
        kind = "title_slam" if (zone == "title" and i < slam) else zone
        bad += [f"frame {i}: {e}" for e in zone_errors(bb, kind)]
    if exit_none:  # no out animation: last frame non-empty and at full opacity (>= 95% of the peak alpha of the clip)
        if bboxes and bboxes[-1] is None:
            bad.append("last frame empty although exit is none")
        elif last_amax < 0.95 * amax_peak:
            bad.append(f"last frame alpha {last_amax} < 95% of peak alpha {amax_peak} although exit is none")
    nonempty = [b for b in bboxes if b]
    union = [min(b[0] for b in nonempty), min(b[1] for b in nonempty), max(b[2] for b in nonempty), max(b[3] for b in nonempty)] if nonempty else None
    errs += bad
    return {"id": it["id"], "pix_fmt": st["pix_fmt"], "codec": st["codec_name"], "profile": st.get("profile"),
            "frames_decoded": len(bboxes), "empty_frames": sum(b is None for b in bboxes), "union_bbox": union,
            "pass": not errs, "errors": errs[:20], "error_count": len(errs), "bbox_per_frame": bboxes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.layout, encoding="utf-8-sig") as fh:
        lay = json.load(fh)
    res = [check_item(it, a.dir) for it in lay["items"]]
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False)
    for r in res:
        print(f"{r['id']} {'PASS' if r['pass'] else 'FAIL'} {r['codec']}/{r['profile']} {r['pix_fmt']} frames={r['frames_decoded']} "
              f"empty={r['empty_frames']} union_bbox={r['union_bbox']}" + ("" if r["pass"] else f" errors={r['error_count']}: {r['errors'][:3]}"))
    ok = all(r["pass"] for r in res)
    print("ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
