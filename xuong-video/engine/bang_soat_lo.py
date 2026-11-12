"""Ảnh soát nhanh cả lô: mỗi video 1 hàng × 4 khung (câu mở, 35%, 65%, chốt). python bang_soat_lo.py <thư mục ngày> [mẫu tên]"""
import subprocess, sys, tempfile
from pathlib import Path

d = Path(sys.argv[1]); pat = sys.argv[2] if len(sys.argv) > 2 else "*.mp4"
vids = sorted(d.glob(pat))
tmp = Path(tempfile.mkdtemp()); rows = []
for k, v in enumerate(vids):
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)], capture_output=True, text=True).stdout)
    tiles = []
    for j, t in enumerate([0.9, dur * 0.35, dur * 0.65, dur - 1.2]):
        o = tmp / f"{k}_{j}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(v), "-frames:v", "1", "-vf",
                        f"scale=216:384,drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='{k+1}':x=6:y=6:fontsize=26:fontcolor=yellow:box=1:boxcolor=black@0.7,format=yuvj420p", str(o)])
        tiles.append(o)
    rows.append(tiles)
out = d / "_soat-lo.jpg"
args = [a for r in rows for t in r for a in ("-i", str(t))]
n = len(rows)
filt = ";".join(f"[{i*4}][{i*4+1}][{i*4+2}][{i*4+3}]hstack=4[r{i}]" for i in range(n)) + ";" + "".join(f"[r{i}]" for i in range(n)) + f"vstack={n}"
subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", filt, str(out)], check=True)
for k, v in enumerate(vids):
    print(k + 1, v.name)
print(out)
