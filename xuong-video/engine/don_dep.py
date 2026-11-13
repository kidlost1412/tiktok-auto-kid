"""Tự dọn ổ đĩa (chạy sau mỗi lô + khi mở app). CHỈ xoá file tạm do hub tự sinh — KHÔNG xoá video thành phẩm, footage gốc.
- ra/<ngày>/_tam (file dựng dở còn sót khi lô bị dừng)
- ra/<ngày>/_giong cũ hơn 7 ngày (giọng đọc đã ghép vào video)
- ra/<ngày>/_ban-chua-dat cũ hơn 5 ngày (bản giám khảo chưa đạt, đã có bản dựng lại)
- nhật ký app dài quá 5 MB → giữ phần cuối
dung_luong() → số liệu cho app (dung lượng từng ngày, ổ còn trống)."""
import json, shutil, time
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, KEM


def _ra():
    return Path(cfg_hub()["duong_dan"]["ra"])


def _size(p):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def don(log=print):
    ra, now, giai_phong = _ra(), time.time(), 0
    if not ra.exists():
        return 0
    for ngay in ra.iterdir():
        if not ngay.is_dir():
            continue
        for ten, ngay_giu in (("_tam", 0), ("_giong", 7), ("_ban-chua-dat", 5)):
            d = ngay / ten
            if d.exists() and now - d.stat().st_mtime > ngay_giu * 86400 + (3600 if ten == "_tam" else 0):
                giai_phong += _size(d); shutil.rmtree(d, ignore_errors=True)
    # file dựng dở còn sót khi lô crash: *.part.mp4 (ffmpeg chưa xong) và *.__sach.mp4 (lam_sach chưa xong) cũ hơn 1 giờ
    for mau in ("*.part.mp4", "*.__sach.mp4", "_kem/*.part.mp4"):
        for f in ra.glob("*/" + mau):
            try:
                if f.is_file() and now - f.stat().st_mtime > 3600:
                    giai_phong += f.stat().st_size; f.unlink()
            except OSError:
                pass
    # video ĐÃ ĐĂNG (TryPost báo) quá N ngày → Thùng rác. CHỈ đúng 4 file <id>.{mp4,jpg,json,txt} (mp4 ở ra/<ngày>/, 3 file kia ở ra/<ngày>/_kem/ hoặc chỗ cũ), kiểm nằm trong ra/.
    try:
        import datetime, re, subprocess
        cfg = cfg_hub()
        n = int(cfg.get("trypost", {}).get("giu_sau_dang_ngay", 30))
        tt_f = HUB / "lich-su" / "trypost.json"
        tt = json.loads(tt_f.read_text(encoding="utf-8")) if tt_f.exists() else {}
        han = datetime.datetime.now() - datetime.timedelta(days=n)
        ra_r = ra.resolve(); bo = []
        for vid, t in tt.items():
            if t.get("trang_thai") != "da_dang" or n < 0 or not re.fullmatch(r"[\w.\-]+", vid) or ".." in vid:
                continue
            try:
                luc = datetime.datetime.fromisoformat(str(t.get("luc_nhan") or t.get("luc"))[:19])
            except Exception:
                continue
            if luc >= han:
                continue
            for ngay in ra.iterdir():
                if not ngay.is_dir() or ngay.name.startswith("_"):
                    continue
                for rel in (vid + ".mp4", *(f"{KEM}/{vid}{d}" for d in (".jpg", ".json", ".txt")), *(vid + d for d in (".jpg", ".json", ".txt"))):
                    f = (ngay / rel).resolve()
                    if f.exists() and f.is_file() and ra_r in f.parents:
                        giai_phong += f.stat().st_size; bo.append(str(f))
        for k in range(0, len(bo), 20):        # lô nhỏ, thoát dấu ', không bật hộp thoại, có giới hạn thời gian
            ps = "Add-Type -AssemblyName Microsoft.VisualBasic; " + "; ".join(
                "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('" + x.replace("'", "''") + "','OnlyErrorDialogs','SendToRecycleBin')"
                for x in bo[k:k + 20])
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, timeout=120)
        if bo:
            log(f"🧹 {len(bo)} file của video đã đăng quá {n} ngày → Thùng rác")
    except Exception as e:
        log(f"  (dọn video đã đăng lỗi: {str(e)[:100]})")
    for f in (HUB / "lich-su").glob("*.log"):
        if f.stat().st_size > 5_000_000:
            f.write_bytes(f.read_bytes()[-1_000_000:])
    if giai_phong:
        log(f"🧹 Đã dọn file tạm: {giai_phong / 1e9:.2f} GB")
    return giai_phong


def dung_luong():
    ra = _ra()
    ngay = []
    if ra.exists():
        for d in sorted([x for x in ra.iterdir() if x.is_dir()], reverse=True):
            ngay.append({"ngay": d.name, "gb": round(_size(d) / 1e9, 2), "video": len([x for x in d.glob("*.mp4") if not x.name.endswith(".part.mp4")])})
    o = shutil.disk_usage(ra if ra.exists() else HUB)
    return {"o_trong_gb": round(o.free / 1e9, 1), "o_tong_gb": round(o.total / 1e9, 1),
            "ra_gb": round(sum(x["gb"] for x in ngay), 2), "ngay": ngay}


if __name__ == "__main__":
    don(); print(json.dumps(dung_luong(), ensure_ascii=False, indent=1))
