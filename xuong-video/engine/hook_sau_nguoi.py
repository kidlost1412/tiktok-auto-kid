"""HOOK "CHỮ KHỔNG LỒ SAU NGƯỜI" (v10 Kid duyệt, 24/11): (1) mở đầu CAMERA LÙI RA — nền phóng 1,25× rồi nhả về 1,0× trong ~0,7 s;
(2) có người trong lúc hook → tách người (tach_nguoi) cho đúng đoạn hook, Remotion vẽ chuỗi PNG đó ĐÈ LÊN chữ vàng khổng lồ, DƯỚI mọi chữ khác
→ đầu/vai người che bớt chữ. Người che quá nhiều chữ (> 45 % nét chữ) hoặc không có người → giữ chữ ở trước như cũ."""
import os, subprocess
from pathlib import Path

FPS = 30
KEO_KHUNG, KEO_NHA = 24, 21          # đoạn xử lý 0,8 s; nhả hết zoom ở khung 21 (0,7 s)
KEO_ZOOM = 0.25
TOP_CHU = 170                        # khớp ChuKhongLo (ChuTheoLoi.tsx)
TOP_TOI_DA = 420                     # chữ không được hạ quá thấp khi dời xuống cho đầu che phần dưới
NGUOI_TOI_THIEU, CHE_TOI_DA, CHE_TOI_THIEU = 0.08, 0.45, 0.02


def dung_cat(phu_nguoi, phu_chu, che_toi_da=CHE_TOI_DA):
    """phu_nguoi: tỉ lệ diện tích khung là người; phu_chu: tỉ lệ nét chữ bị người che. → True: dùng lớp tách người (chữ nằm sau người)."""
    return phu_nguoi > NGUOI_TOI_THIEU and CHE_TOI_THIEU <= phu_chu <= che_toi_da


def keo_ra(base):
    """Camera lùi ra ở 0,8 s đầu của base.mp4 (thay file tại chỗ, tiếng giữ nguyên). Lỗi → in ⚠, không làm hỏng dựng."""
    base = Path(base); tmp = base.with_name(base.stem + ".keo.mp4")
    fc = (f"[0:v]split[a][b];[a]trim=end_frame={KEO_KHUNG},setpts=PTS-STARTPTS,scale=2160:3840:flags=bicubic,"
          f"zoompan=z='1+{KEO_ZOOM}*pow(max(0,1-on/{KEO_NHA}),3)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps={FPS},setsar=1[a2];"
          f"[b]trim=start_frame={KEO_KHUNG},setpts=PTS-STARTPTS,setsar=1[b2];[a2][b2]concat=n=2:v=1:a=0,format=yuv420p[v]")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(base), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-r", str(FPS), "-c:a", "copy", "-movflags", "+faststart", str(tmp)], check=True)
        os.replace(tmp, base)
        return True
    except Exception as e:
        print(f"  ⚠ camera lùi ra lỗi: {e}")
        try: tmp.unlink()
        except OSError: pass
        return False


def mat_na_chu(text, top=TOP_CHU):
    """Nét chữ Anton của hook (cỡ như ChuKhongLo) vẽ lên khung 1080×1920 → (mặt nạ bool, (y0, y1) của nét chữ)."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from duong_dan import cfg
    ttf = Path(cfg()["duong_dan"]["remotion"]) / "public" / "Anton-Regular.ttf"
    rong100 = ImageFont.truetype(str(ttf), 100).getlength(text)
    px = int(min(280, 1000 / rong100 * 100 * 0.96))
    font = ImageFont.truetype(str(ttf), px)
    asc, desc = font.getmetrics()
    base_y = top + (1.12 * px - (asc + desc)) / 2 + asc            # đường cơ sở như CSS (dòng cao 1,12)
    im = Image.new("L", (1080, 1920), 0)
    ImageDraw.Draw(im).text(((1080 - font.getlength(text)) / 2, base_y), text, font=font, fill=255, anchor="ls")
    m = np.array(im) > 127; ys = np.where(m.any(1))[0]
    return m, (int(ys.min()), int(ys.max())) if len(ys) else (top, top)


def do_nguoi(base, hook, mau=3):
    """Lấy mẫu `mau` khung trong cửa sổ hook → (diện tích người, đỉnh đầu (px), danh sách mặt nạ người). Không có người → (0, None, [])."""
    import cv2, numpy as np, tach_nguoi
    cap = cv2.VideoCapture(str(base)); fps = cap.get(cv2.CAP_PROP_FPS) or FPS
    f0, f1 = hook["f0"], hook["f1"]; ms = []
    for p in [(i + 1) / (mau + 1) for i in range(mau)]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(round((f0 + (f1 - f0) * p) / FPS * fps)))
        ok, fr = cap.read()
        if ok:
            ms.append(tach_nguoi.person(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)) > 0.5)
    cap.release()
    if not ms:
        return 0.0, None, []
    dt = float(np.median([m.mean() for m in ms]))
    dau = [int(np.where(m.any(1))[0].min()) for m in ms if m.any()]
    return dt, (int(np.median(dau)) if dau else None), ms


def chay(base, work_dir, hook):
    """Chạy cả hai bước trên hook (dict trong loi["hook"]); thành công thì thêm hook["nguoi"]={dir,n,f0} (+ hook["top"] nếu dời chữ xuống)."""
    import numpy as np, tach_nguoi
    keo_ra(base)
    dt, dau, ms = do_nguoi(base, hook)
    if dt <= NGUOI_TOI_THIEU or dau is None:
        print(f"  hook: không có người rõ ({dt:.0%} khung) → chữ ở trước")
        return
    chu, (y0, y1) = mat_na_chu(hook["text"])
    top = TOP_CHU + max(0, min(TOP_TOI_DA - TOP_CHU, dau + int(0.3 * (y1 - y0)) - y1))   # đầu chồng lên ~30 % phần dưới của chữ (kiểu v10)
    if top != TOP_CHU:
        chu, _ = mat_na_chu(hook["text"], top)
    che = max(float((m & chu).sum()) / max(1, int(chu.sum())) for m in ms)
    if not dung_cat(dt, che):
        print(f"  hook: người {dt:.0%} khung, che {che:.0%} nét chữ → chữ ở trước")
        return
    out = Path(work_dir) / "nguoi_hook"
    n = tach_nguoi.tach(base, out, hook["f0"] / FPS, hook["f1"] / FPS)
    if n < 1:
        return
    hook["nguoi"] = {"dir": str(out), "n": n, "f0": hook["f0"]}
    if top != TOP_CHU:
        hook["top"] = top
    print(f"  hook sau người: {n} khung, che {che:.0%} nét chữ, chữ top {top}")
