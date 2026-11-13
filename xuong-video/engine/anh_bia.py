"""ẢNH BÌA TikTok: chọn khung ĐẸP NHẤT của video (không lấy khung mở đầu xấu / khung đang chuyển cảnh).
Chấm ~20 khung: độ nét, độ sáng vừa, không nhoè chuyển cảnh, cộng điểm đoạn đầu có chữ móc câu → lưu <video>.jpg (1080×1920, không EXIF).
python anh_bia.py <file.mp4|thư mục>"""
import subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageFilter, ImageStat
sys.path.insert(0, str(Path(__file__).resolve().parent))
from duong_dan import kem


def _dur(v):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)],
                                capture_output=True, text=True).stdout or 0)


def chon_bia(video, out=None, n=20, uu_tien=None):
    """uu_tien=(a, b) giây: khoảng khối chữ mở đầu đang hiện → bìa có chữ móc câu."""
    video = Path(video); out = Path(out) if out else kem(video, ".jpg", ghi=True)
    d = _dur(video)
    if d <= 0:
        return None
    tmp = Path(tempfile.mkdtemp())
    ts = [0.9 + (d - 2.2) * i / (n - 1) for i in range(n)]
    if uu_tien:
        a, b = max(0.5, uu_tien[0] + 0.35), max(0.6, uu_tien[1] - 0.2)
        ts += [a + (b - a) * k / 5 for k in range(6)] if b > a else []
    best = None
    for i, t in enumerate(ts):
        f = tmp / f"{i:02d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=270:480", str(f)])
        if not f.exists():
            continue
        im = Image.open(f).convert("L")
        sang = ImageStat.Stat(im).mean[0]
        net = ImageStat.Stat(im.filter(ImageFilter.FIND_EDGES)).var[0] ** 0.5
        # khung đang chuyển cảnh (xfade) thường nhoè: so với khung lệch 0,12 s
        f2 = tmp / f"{i:02d}b.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t + 0.12:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=270:480", str(f2)])
        dong = 0.0
        if f2.exists():
            from PIL import ImageChops
            dong = ImageStat.Stat(ImageChops.difference(im, Image.open(f2).convert("L"))).mean[0]
        diem = net - 0.9 * dong - (0 if 70 <= sang <= 200 else abs(sang - 135) * 0.6)
        if uu_tien and uu_tien[0] + 0.3 <= t <= uu_tien[1]:
            diem *= 1.6          # đang hiện chữ móc câu của câu mở → bìa thu hút hơn
        elif t < min(4.5, d * 0.3):
            diem *= 1.15
        if best is None or diem > best[0]:
            best = (diem, t)
    if best:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{best[1]:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "2",
                        "-map_metadata", "-1", "-fflags", "+bitexact", str(out)])
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return out if out.exists() else None


if __name__ == "__main__":
    tgt = Path(sys.argv[1])
    for v in (sorted(tgt.glob("*.mp4")) if tgt.is_dir() else [tgt]):
        print(chon_bia(v))
