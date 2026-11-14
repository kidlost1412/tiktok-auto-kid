"""Tự dọn ổ đĩa (chạy sau mỗi lô + khi mở app). CHỈ xoá file tạm do hub tự sinh — KHÔNG xoá video thành phẩm, footage gốc.
- ra/<ngày>/_tam/lo-* (file dựng dở còn sót khi lô bị dừng; KHÔNG xoá khi đang có lô chạy, chỉ xoá lô không file nào mới hơn `don_tam_gio` = 6 giờ)
- ra/<ngày>/_giong cũ hơn 7 ngày (giọng đọc đã ghép vào video)
- ra/<ngày>/_ban-chua-dat cũ hơn 5 ngày (bản giám khảo chưa đạt, đã có bản dựng lại)
- nhật ký app dài quá 5 MB → giữ phần cuối
dung_luong() → số liệu cho app (dung lượng từng ngày, ổ còn trống)."""
import json, os, secrets, shutil, time
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, KEM


# ---------------------------------------------------------------- khoá lô (dang-chay.lock)
# Dòng đầu GIỮ NGUYÊN dạng "<pid> <mã sp>" (app đọc cột 1 = PID, phần còn lại = mã sản phẩm). Danh tính tiến trình (giờ tạo + token ngẫu nhiên)
# nằm ở file kèm dang-chay.lock.id → PID bị cấp lại cho một python khác (vd. chính app) không còn bị tính là "lô đang chạy".
def _f_khoa():
    return HUB / "lich-su" / "dang-chay.lock"


def _id_f(f):
    return f.with_name(f.name + ".id")


def thong_tin_tien_trinh(pid):
    """(tên file chạy, giờ tạo tiến trình dạng số) của PID; (None, None) nếu PID không còn. Windows: OpenProcess/GetProcessTimes."""
    pid = int(pid)
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return "python", None
        except OSError:
            return None, None
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE; k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    h = k.OpenProcess(0x1000, False, pid)              # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None, None
    try:
        code = wintypes.DWORD()
        if k.GetExitCodeProcess(h, ctypes.byref(code)) and code.value != 259:      # 259 = STILL_ACTIVE; đã thoát mà còn handle ai đó giữ
            return None, None
        t = [wintypes.FILETIME() for _ in range(4)]
        ct = None
        if k.GetProcessTimes(h, *[ctypes.byref(x) for x in t]):
            ct = (t[0].dwHighDateTime << 32) | t[0].dwLowDateTime
        buf = ctypes.create_unicode_buffer(1024); n = wintypes.DWORD(1024)
        ten = Path(buf.value).name if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ""
        return ten, ct
    finally:
        k.CloseHandle(h)


def doc_khoa(f=None):
    """{"pid","ma","token","ctime","t0"} của file khoá, None nếu không có/hỏng. token/ctime/t0 có thể thiếu (khoá kiểu cũ)."""
    f = Path(f or _f_khoa())
    try:
        cot = f.read_text(encoding="utf-8").split(None, 1)
        d = {"pid": int(cot[0]), "ma": cot[1].strip() if len(cot) > 1 else ""}
    except Exception:
        return None
    try:
        x = json.loads(_id_f(f).read_text(encoding="utf-8"))
        if x.get("pid") == d["pid"]:                  # file .id của khoá khác (khoá bị xoá tay) → bỏ
            d.update(token=x.get("token"), ctime=x.get("ctime"), t0=x.get("t0"))
    except Exception:
        pass
    return d


def khoa_con_song(f=None):
    """Thông tin khoá nếu lô đó THẬT SỰ còn chạy: PID còn sống, là tiến trình python, và (khi có ghi) đúng giờ tạo tiến trình đó. Không thì None."""
    d = doc_khoa(f)
    if not d:
        return None
    try:
        ten, ct = thong_tin_tien_trinh(d["pid"])
    except Exception:
        return None
    if not ten or not ten.lower().startswith(("python", "pythonw")):
        return None
    if d.get("ctime") and ct and abs(int(d["ctime"]) - ct) > 10_000_000:        # lệch > 1 s (FILETIME 100 ns) = PID đã cấp lại cho tiến trình khác
        return None
    return d


def lay_khoa_lo(ma_sp, f=None):
    """Tạo khoá lô ĐỘC QUYỀN (O_EXCL, tuần tự hoá bằng khoá HĐH): 2 lô khởi động cùng giây chỉ 1 lô qua. Trả token (chuỗi) nếu lấy được,
    None nếu đang có lô khác chạy. Khoá cũ (tiến trình đã chết / PID cấp lại) tự được dọn."""
    from su_kien import khoa_tep
    f = Path(f or _f_khoa()); f.parent.mkdir(parents=True, exist_ok=True)
    try:
        with khoa_tep(f, 5):
            if f.exists():
                if khoa_con_song(f):
                    return None
                f.unlink()
            fd = os.open(str(f), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(f"{os.getpid()} {ma_sp}")
            token = secrets.token_hex(8)
            try:
                _id_f(f).write_text(json.dumps({"pid": os.getpid(), "token": token, "ctime": thong_tin_tien_trinh(os.getpid())[1],
                                                "t0": time.time()}), encoding="utf-8")
            except Exception:
                pass
            return token
    except (OSError, TimeoutError):
        return None


def nha_khoa_lo(token, f=None):
    """Xoá khoá lô của CHÍNH MÌNH (token khớp; khoá kiểu cũ không có token thì xoá luôn). Khoá của lô khác giữ nguyên."""
    f = Path(f or _f_khoa())
    d = doc_khoa(f)
    if d and d.get("token") and token and d["token"] != token:
        return False
    for x in (f, _id_f(f)):
        try:
            x.unlink()
        except OSError:
            pass
    return True


def _moi_nhat(p):
    """Giờ sửa mới nhất trong cây thư mục p (kể cả chính p)."""
    m = p.stat().st_mtime
    for r, ds, fs in os.walk(p):
        for n in ds + fs:
            try:
                m = max(m, os.stat(os.path.join(r, n)).st_mtime)
            except OSError:
                pass
    return m


def _ra():
    return Path(cfg_hub()["duong_dan"]["ra"])


def _size(p):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def don(log=print):
    ra, now, giai_phong = _ra(), time.time(), 0
    if not ra.exists():
        return 0
    try:
        kh = khoa_con_song(); lo_chay = bool(kh) and kh["pid"] != os.getpid()      # lô KHÁC đang chạy (lô của chính mình đã tự xoá _tam rồi gọi don)
        san_tam = max(1.0, float(cfg_hub().get("don_tam_gio", 6))) * 3600        # sàn tuổi: thư mục tạm mới hơn mức này không bao giờ bị xoá
    except Exception:
        lo_chay, san_tam = True, 6 * 3600
    for ngay in ra.iterdir():
        if not ngay.is_dir():
            continue
        for ten, ngay_giu in (("_giong", 7), ("_ban-chua-dat", 5)):
            d = ngay / ten
            if d.exists() and now - d.stat().st_mtime > ngay_giu * 86400:
                giai_phong += _size(d); shutil.rmtree(d, ignore_errors=True)
        tam = ngay / "_tam"
        if lo_chay or not tam.is_dir():     # đang có lô chạy (app hay cửa sổ lệnh) → KHÔNG đụng _tam của bất kỳ ngày nào
            continue
        for lo in tam.iterdir():            # _tam/lo-HHMMSS: mtime thư mục cha không đổi khi lô chạy lâu → xét file MỚI NHẤT trong từng lô
            try:
                if now - _moi_nhat(lo) > san_tam:
                    giai_phong += _size(lo) if lo.is_dir() else lo.stat().st_size
                    shutil.rmtree(lo, ignore_errors=True) if lo.is_dir() else lo.unlink()
            except OSError:
                pass
        try:
            tam.rmdir()                     # chỉ xoá được khi đã rỗng
        except OSError:
            pass
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
        try:
            if f.stat().st_size > 5_000_000:
                f.write_bytes(f.read_bytes()[-1_000_000:])
        except OSError:
            pass
    try:                                    # sổ lịch sử chỉ lớn lên → giữ N dòng cuối khi quá cỡ (giữ dòng tiêu đề của .csv); không cắt khi lô đang ghi
        if lo_chay:
            raise OSError
        from su_kien import _cat_dong
        ls = HUB / "lich-su"
        for mau, giu, byte in (("nhat-ky.txt", 8000, 1_500_000), ("lo.jsonl", 2000, 400_000), ("cau-da-dung*.txt", 4000, 400_000),
                               ("canh-da-dung-*.txt", 600, 120_000), ("giong.csv", 4000, 400_000), ("token.csv", 8000, 1_500_000)):
            for f in ls.glob(mau):
                _cat_dong(f, giu, byte, "utf-8-sig" if f.suffix == ".csv" else "utf-8", f.suffix == ".csv")
    except Exception:
        pass
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
