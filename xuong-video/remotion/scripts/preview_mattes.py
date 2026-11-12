"""Person mattes for the preview of title_behind (CapCut does this natively in the real build).

For frames f0..f1-1 of the edit timeline, takes the main video frame (source frame = src_in_f + f), scales it to
1080x1920 cover and writes RGBA PNG <outdir>/<prefix>-<i>.png (i = f - f0) with the person kept (rembg isnet-general-use).
Run with the venv that has rembg and U2NET_HOME set:  python -X utf8 preview_mattes.py ...
"""
import argparse
import os
import subprocess
import sys

import numpy as np
from PIL import Image
from rembg import new_session, remove

W, H = 1080, 1920


def frame(video, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.4f}", "-i", video, "-frames:v", "1",
                        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    if r.returncode != 0 or len(r.stdout) != W * H * 3:
        raise RuntimeError(f"cannot read frame at {t:.3f}s of {video}: {r.stderr.decode('utf-8', 'replace')[-300:]}")
    return Image.fromarray(np.frombuffer(r.stdout, np.uint8).reshape(H, W, 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--src-in-f", type=int, required=True)
    ap.add_argument("--f0", type=int, required=True)
    ap.add_argument("--f1", type=int, required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    if not os.environ.get("U2NET_HOME"):
        print("ERROR: set U2NET_HOME to the folder holding the rembg models")
        return 2
    os.makedirs(a.outdir, exist_ok=True)
    sess = new_session("isnet-general-use")
    for f in range(a.f0, a.f1):
        out = remove(frame(a.video, (a.src_in_f + f) / 30), session=sess)
        out.save(os.path.join(a.outdir, f"{a.prefix}-{f - a.f0}.png"))
    print(f"matted {a.f1 - a.f0} frames -> {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
