"""Face-crop check: never cut the person's face/head in a frame panel or a B-roll.

For every frame-panel clip and every B-roll item of a kich-ban.json it samples 3 timeline frames (first, middle, last of the clip
span), grabs the matching SOURCE frame with ffmpeg, computes the crop window the pipeline shows there (cover-fit into the box,
zoom at that moment about `center`: the same geometry as FrameClipVideo in src/kit/KitElement.tsx, bake_zoom.py and
cover_exposure() in pipeline-v6/build/validate_script.py), detects faces on the FULL source frame and flags
  FACE_CUT  a face crossing the crop edge with > 25 % of its area outside the crop;
  FACE_OUT  a face (area > 0.5 % of the source frame) fully outside the crop, above its top within 1 face-height
            (crop shows the body below, head cut off).
Detector: OpenCV Haar cascades (frontal alt2 + frontal default + profile on the frame and its mirror). Chosen over YuNet because
it ships with opencv (no model download); it only finds upright, fairly frontal/profile faces, so a miss is possible (reported
as "no face found", never as OK-by-detection) and rotated or tiny faces are ignored by design (area floor).
Needs opencv with bundled cascades (opencv-python-headless 4.x; the 5.x wheels ship none).

Usage: python check_framing.py --script kich-ban.json [--out report.json] [--offset SECONDS]
Exit 1 if any FACE_CUT / FACE_OUT, 0 otherwise.
"""
import argparse
import json
import subprocess
import sys

import numpy as np

FPS = 30
W, H = 1080, 1920
CUT_FRAC = 0.25      # FACE_CUT: more than this share of the face area outside the crop
MIN_FACE_AREA = 0.005  # share of the source frame area; smaller detections are ignored (also FACE_OUT's floor)
EASE = {"linear": lambda t: t, "ease_in": lambda t: t * t, "ease_out": lambda t: 1 - (1 - t) ** 2,
        "ease_in_out": lambda t: 2 * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 2) / 2}


def crop_window(src_w, src_h, box_w, box_h, zoom, center):
    """Source-pixel crop [x0, y0, x1, y1] shown in a box_w x box_h box: cover-fit scale k, then zoom about `center` (normalized
    source coords) placed at the box centre. Not clamped: if it leaves the source the renderer would show an empty edge."""
    k = max(box_w / src_w, box_h / src_h)
    half_w, half_h = box_w / (2 * zoom * k), box_h / (2 * zoom * k)  # visible half extent in source px
    cx, cy = center[0] * src_w, center[1] * src_h
    return [cx - half_w, cy - half_h, cx + half_w, cy + half_h]


def zoom_at(clip, t):
    """Zoom of a clip at timeline frame t (held at the endpoints), same ramp as FrameClipVideo."""
    z = clip.get("zoom") or {}
    z0, z1 = float(z.get("from", 1.0)), float(z.get("to", 1.0))
    n = clip["f1"] - clip["f0"]
    p = (min(max(t, clip["f0"]), clip["f1"] - 1) - clip["f0"]) / (n - 1) if n > 1 else 0.0
    return z0 + (z1 - z0) * EASE[z.get("easing", "linear")](p)


def sample_frames(f0, f1):
    """First, middle and last timeline frame of [f0, f1), without repeats."""
    return sorted({f0, (f0 + f1 - 1) // 2, f1 - 1})


def judge(face, crop, src_w, src_h):
    """face/crop: [x0, y0, x1, y1] source px. Returns (verdict, outside_fraction); verdict in OK | FACE_CUT | FACE_OUT.
    Faces smaller than MIN_FACE_AREA of the source frame never flag."""
    fw, fh = face[2] - face[0], face[3] - face[1]
    if fw * fh <= MIN_FACE_AREA * src_w * src_h:
        return "OK", 0.0
    iw = max(0.0, min(face[2], crop[2]) - max(face[0], crop[0]))
    ih = max(0.0, min(face[3], crop[3]) - max(face[1], crop[1]))
    outside = 1.0 - iw * ih / (fw * fh)
    if outside <= 1e-9:
        return "OK", 0.0
    if iw * ih > 0:
        return ("FACE_CUT" if outside > CUT_FRAC else "OK"), outside
    if face[3] <= crop[1] and crop[1] - face[3] <= fh:  # fully above the crop top, within one face-height
        return "FACE_OUT", 1.0
    return "OK", 1.0


def suggest_center(face, crop, src_w, src_h):
    """Smallest change of `center` (normalized) that puts the whole face inside a crop of the same size, per axis; None on an axis
    where the face is larger than the crop (then 'note' says so). Result is clamped to the range that keeps the crop inside the
    source (no empty edge)."""
    half_w, half_h = (crop[2] - crop[0]) / 2, (crop[3] - crop[1]) / 2
    cx, cy = (crop[0] + crop[2]) / 2, (crop[1] + crop[3]) / 2
    out, note = [], None
    for c, lo_f, hi_f, half, size in ((cx, face[0], face[2], half_w, src_w), (cy, face[1], face[3], half_h, src_h)):
        lo, hi = hi_f - half, lo_f + half  # centre range that contains the face
        if lo > hi:
            out.append(None)
            note = "face larger than the crop: lower zoom or switch shot"
            continue
        e_lo, e_hi = half, size - half  # centre range that keeps the crop inside the source
        g_lo, g_hi = max(lo, e_lo), min(hi, e_hi)
        # a face inside the source always leaves g_lo <= g_hi; a detector box sticking out of the frame may not: stay inside the source
        new = min(max(c, g_lo), g_hi) if g_lo <= g_hi else min(max(c, e_lo), e_hi)
        out.append(round(new / size, 4))
    return {"center": out, "note": note}


def iou(a, b):
    iw, ih = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    inter = max(0, iw) * max(0, ih)
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def nms(boxes, thr=0.3):
    keep = []
    for b in sorted(boxes, key=lambda b: -(b[2] - b[0]) * (b[3] - b[1])):
        if all(iou(b, k) <= thr for k in keep):
            keep.append(b)
    return keep


def confirmed(hits, need=2, thr=0.4):
    """hits: [(detector index, box)]. Keep boxes that at least `need` different detectors found (IoU > thr): single-cascade
    hits are mostly small false positives on leaves and soil (measured on the TC01 V11 sources)."""
    return [b for i, b in hits if len({i} | {j for j, o in hits if j != i and iou(b, o) > thr}) >= need]


class HaarDetector:
    def __init__(self):
        import cv2
        self.cv2 = cv2
        d = cv2.data.haarcascades
        self.cascades = [cv2.CascadeClassifier(d + n) for n in ("haarcascade_frontalface_alt2.xml", "haarcascade_frontalface_default.xml", "haarcascade_profileface.xml")]
        if any(c.empty() for c in self.cascades):
            raise RuntimeError(f"haar cascades not found in {d} (need opencv-python-headless 4.x, not 5.x)")

    def __call__(self, bgr):
        cv2 = self.cv2
        h, w = bgr.shape[:2]
        gray = cv2.equalizeHist(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
        side = int((MIN_FACE_AREA * w * h) ** 0.5 * 0.9)
        found = []
        for ci, c in enumerate(self.cascades):
            views = [(gray, False)] + ([(cv2.flip(gray, 1), True)] if ci == 2 else [])  # profile cascade looks left only: mirror too
            for img, flipped in views:
                for x, y, fw, fh in c.detectMultiScale(img, scaleFactor=1.1, minNeighbors=4, minSize=(side, side)):
                    x = w - x - fw if flipped else x
                    found.append((ci, [float(x), float(y), float(x + fw), float(y + fh)]))
        return nms(confirmed(found))


def grab_frame(path, seconds):
    """Source frame at `seconds` (relative to the container start, like ffmpeg -ss) as a BGR array."""
    import cv2
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, seconds):.6f}", "-i", path, "-map", "0:v:0", "-frames:v", "1",
                        "-f", "image2pipe", "-c:v", "png", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"ffmpeg could not read a frame at {seconds:.3f}s of {path}: {r.stderr.decode('utf-8', 'replace')[-300:]}")
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)


def items(script):
    """(label, box_w, box_h, clip) for every frame-panel clip and every B-roll item."""
    for g in script.get("graphics") or []:
        if g.get("type") != "frame":
            continue
        for pi, p in enumerate(g.get("panels") or []):
            x0, y0, x1, y1 = p["box"]
            for ci, c in enumerate(p.get("clips") or []):
                yield {"id": g["id"], "kind": "frame", "panel": pi, "clip": ci, "label": c.get("label")}, x1 - x0, y1 - y0, c
    for b in script.get("broll") or []:
        yield {"id": b["id"], "kind": "broll", "panel": None, "clip": None, "label": None}, W, H, b


def check_item(meta, box_w, box_h, clip, detect, offset, reader=grab_frame):
    samples = []
    for t in sample_frames(clip["f0"], clip["f1"]):
        src_t = (clip["src_in_f"] + (t - clip["f0"])) / FPS + offset
        img = reader(clip["path"], src_t)
        sh, sw = img.shape[:2]
        z = zoom_at(clip, t)
        crop = crop_window(sw, sh, box_w, box_h, z, clip.get("center", [0.5, 0.5]))
        faces = detect(img)
        verdict, worst = "OK", None
        flags = []
        for fc in faces:
            v, out = judge(fc, crop, sw, sh)
            if v != "OK":
                flags.append({"face": [round(x, 1) for x in fc], "verdict": v, "outside_fraction": round(out, 3),
                              "suggest": suggest_center(fc, crop, sw, sh)})
                if verdict == "OK" or v == "FACE_CUT":
                    verdict = v
        samples.append({"timeline_f": t, "source_s": round(src_t, 3), "source_size": [sw, sh], "zoom": round(z, 4),
                        "crop": [round(x, 1) for x in crop], "faces": [[round(x, 1) for x in f] for f in faces], "verdict": verdict, "flags": flags})
    bad = [s["verdict"] for s in samples if s["verdict"] != "OK"]
    return {**meta, "path": clip["path"], "center": clip.get("center", [0.5, 0.5]), "samples": samples,
            "verdict": "FACE_CUT" if "FACE_CUT" in bad else "FACE_OUT" if bad else "OK",
            "faces_seen": any(s["faces"] for s in samples)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--out")
    ap.add_argument("--offset", type=float, default=0.0, help="seconds added to every source time (container start offset)")
    a = ap.parse_args()
    with open(a.script, "r", encoding="utf-8-sig") as fh:
        script = json.load(fh)
    detect = HaarDetector()
    results = []
    for meta, bw, bh, clip in items(script):
        r = check_item(meta, bw, bh, clip, detect, a.offset)
        results.append(r)
        where = r["id"] + (f" panel {r['panel']} clip {r['clip']}" if r["kind"] == "frame" else "")
        print(f"{r['verdict']:8s} {where}" + ("" if r["faces_seen"] else "  (no face found)"))
        for s in r["samples"]:
            for fl in s["flags"]:
                print(f"           f{s['timeline_f']} {fl['verdict']} face {fl['face']} crop {s['crop']} -> center {fl['suggest']['center']}"
                      + (f" ({fl['suggest']['note']})" if fl["suggest"]["note"] else ""))
    nbad = sum(r["verdict"] != "OK" for r in results)
    print(f"check_framing: {len(results)} clips, {nbad} flagged, {sum(not r['faces_seen'] for r in results)} without any detected face")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"script": a.script, "clips": len(results), "flagged": nbad, "items": results}, fh, ensure_ascii=False, indent=1)
    return 1 if nbad else 0


if __name__ == "__main__":
    sys.exit(main())
