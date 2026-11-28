"""Bản nhẹ để Gemini HỌC CẢNH (kiểu 3). Công cụ đọc file của Antigravity chỉ nhận < 100 MB, video DJI/4K hay 150 MB – 4 GB.
Gemini chỉ lấy ~1 hình/giây và tự thu nhỏ dưới 720p → bản 720p, 10 hình/giây, giữ tiếng nhìn như nhau (hỏi Gemini 4 Carbon 28/11).
- Chỉ để AI XEM; dựng video, soát nhãn, tờ ảnh đạo diễn vẫn lấy file gốc.
- Mốc thời gian giữ đúng file gốc (nén lại hẳn, không cắt nhanh -c copy; kiểm độ dài sau khi nén).
- Video nặng mà dài > 15 phút: cắt khúc đều ≤ 10 phút (mỗi khúc một mã trong cùng lô), ghep() cộng lệch giờ rồi gộp thành MỘT phiếu."""
import hashlib, math, subprocess
from pathlib import Path

NGUONG = 90 * 1024 * 1024        # file gốc nặng hơn → làm bản nhẹ
TRAN = 95 * 1024 * 1024          # bản nhẹ phải dưới mức này
TRAN_MOT_KHUC_S = 900            # ≤ 15 phút: một bản nhẹ; dài hơn: cắt khúc
KHUC_S = 600
LECH_S = 0.3                     # độ dài bản nhẹ lệch quá → hỏng (khớp dung sai mép phiếu)
NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def can_nhe(src):
    try:
        return Path(src).stat().st_size > NGUONG
    except OSError:
        return False


def nhieu_khuc(src, dai):
    return can_nhe(src) and (dai or 0) > TRAN_MOT_KHUC_S


def cac_khuc(dai):
    """[(giây bắt đầu, độ dài)] chia đều, mỗi khúc ≤ 10 phút (không để khúc cuối lẻ vài giây)."""
    if dai <= TRAN_MOT_KHUC_S:
        return [(0.0, float(dai))]
    n = math.ceil(dai / KHUC_S)
    d = dai / n
    return [(round(k * d, 3), round(d if k < n - 1 else dai - k * d, 3)) for k in range(n)]


def bitrate(dai):
    """kbps hình để cả file < 90 MiB (trừ 64 kbps tiếng); không dưới 350 (thấp hơn chữ nhãn nhoè), không quá 1200."""
    return max(350, min(1200, int(90 * 8192 / max(float(dai), 1.0)) - 64))


def _nen(src, a, d, out, v):
    co = "'if(gt(iw,ih),-2,min(720,iw))':'if(gt(iw,ih),min(720,ih),-2)'"      # cạnh ngắn ≤ 720, dọc hay ngang đều được
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", str(src), "-t", f"{d:.3f}",
           "-vf", f"fps=10,scale={co}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
           "-maxrate", f"{v}k", "-bufsize", f"{2 * v}k", "-g", "20", "-pix_fmt", "yuv420p",
           "-af", "aresample=async=1:first_pts=0", "-c:a", "aac", "-ac", "1", "-ar", "16000", "-b:a", "48k",
           "-avoid_negative_ts", "make_zero", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=max(600, int(d * 3)), creationflags=NO_WIN)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"không tạo được bản nhẹ: {(r.stderr or '').strip()[-160:]}")


def lam(src, dai, thu_muc, do_dai):
    """→ [{"src": bản nhẹ, "lech": giây bắt đầu trong file gốc, "dai": độ dài đo lại}]. Đã có sẵn (lần hỏi lại) thì dùng lại."""
    src = Path(src)
    thu_muc = Path(thu_muc) / hashlib.sha1(str(src.resolve()).lower().encode("utf-8")).hexdigest()[:12]
    thu_muc.mkdir(parents=True, exist_ok=True)
    ra = []
    for k, (a, d) in enumerate(cac_khuc(dai)):
        out = thu_muc / f"khuc{k + 1}.mp4"
        do = do_dai(out) if out.exists() else None
        if not (do and abs(do - d) <= LECH_S and out.stat().st_size < TRAN):
            v = bitrate(d)
            _nen(src, a, d, out, v)
            if out.stat().st_size >= TRAN:              # cảnh rất nhiều chi tiết: bitrate trần vẫn vượt → nén mạnh thêm một lần
                _nen(src, a, d, out, max(300, int(v * 0.6)))
            if out.stat().st_size >= TRAN:
                raise RuntimeError(f"bản nhẹ vẫn nặng {out.stat().st_size // 1048576} MB")
            do = do_dai(out)
            if not do or abs(do - d) > LECH_S:
                raise RuntimeError(f"bản nhẹ lệch giờ ({do}s ≠ {d:.2f}s)")
        ra.append({"src": str(out.resolve()), "lech": a, "dai": d})
    return ra


def _doi_gio(x, keys, lech):
    if isinstance(x, dict):
        for k in keys:
            if isinstance(x.get(k), (int, float)) and not isinstance(x.get(k), bool):
                x[k] = round(x[k] + lech, 3)


def ghep(cac):
    """cac: [(phiếu khúc, lệch giây)] theo thứ tự → MỘT phiếu theo giờ file gốc. Vật trùng id mà khác loại/vai → đổi id (thêm _k<n>)."""
    out = {"tom_tat": "", "kieu_video": "", "vat": [], "bo_qua": [], "doan": []}
    co = {}
    tom = []
    for n, (f, lech) in enumerate(cac, 1):
        f = f if isinstance(f, dict) else {}
        out["kieu_video"] = out["kieu_video"] or f.get("kieu_video") or ""
        if f.get("tom_tat"):
            tom.append(str(f["tom_tat"]))
        doi = {}
        for x in f.get("vat") or []:
            if not isinstance(x, dict) or not x.get("id"):
                continue
            x = dict(x); cu = x["id"]
            if cu in co and (co[cu].get("loai"), co[cu].get("la")) != (x.get("loai"), x.get("la")):
                x["id"] = f"{cu}_k{n}"; doi[cu] = x["id"]
            if x["id"] not in co:
                co[x["id"]] = x; out["vat"].append(x)
        for b in f.get("bo_qua") or []:
            b = dict(b) if isinstance(b, dict) else b
            _doi_gio(b, ("tu", "den"), lech); out["bo_qua"].append(b)
        for d in f.get("doan") or []:
            if not isinstance(d, dict):
                out["doan"].append(d); continue
            d = dict(d)
            _doi_gio(d, ("tu", "den"), lech)
            for k in ("dau_hieu", "sinh_vat"):
                if isinstance(d.get(k), list):
                    d[k] = [dict(x) for x in d[k]]; [_doi_gio(x, ("tai",), lech) for x in d[k]]
            if isinstance(d.get("loi"), list):
                d["loi"] = [dict(x) if isinstance(x, dict) else x for x in d["loi"]]; [_doi_gio(x, ("tu", "den"), lech) for x in d["loi"]]
            if isinstance(d.get("gia_qua"), dict):
                d["gia_qua"] = {kn: ([dict(x) if isinstance(x, dict) else x for x in ds] if isinstance(ds, list) else ds) for kn, ds in d["gia_qua"].items()}
                for ds in d["gia_qua"].values():
                    if isinstance(ds, list):
                        [_doi_gio(x, ("tu", "den"), lech) for x in ds]
            if doi:
                if isinstance(d.get("viec"), list):
                    d["viec"] = [dict(x, vat=doi.get(x.get("vat"), x.get("vat"))) if isinstance(x, dict) else x for x in d["viec"]]
                if isinstance(d.get("vat_thay"), list):
                    d["vat_thay"] = [dict(x, id=doi.get(x.get("id"), x.get("id"))) if isinstance(x, dict) else x for x in d["vat_thay"]]
            out["doan"].append(d)
    out["tom_tat"] = " ".join(tom)
    return out
