"""Đường dẫn của Xưởng Video: MÃ (CODE: engine/, luat/, remotion/, app/ — đi cùng repo)
tách khỏi DỮ LIỆU người dùng (DATA: config.json, .env, san-pham/, lich-su/, ra/, tai-nguyen/, tai-khoan/, ho-so/).

Thư mục dữ liệu chọn theo thứ tự:
  1. biến môi trường XUONG_DATA (tuyệt đối, hoặc tương đối so với thư mục gốc repo);
  2. mặc định <repo>/du-lieu/xuong-video (bản cài mới).
Lần chạy đầu với thư mục dữ liệu trống: tự tạo từ mẫu trong <repo>/xuong-video/mau/."""
import json, os, secrets, shutil, sys, threading
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]      # <repo>/xuong-video
REPO = CODE.parent


# Khoá dùng chung cho danh-gia.json: server (bấm ✅/❌) và tự duyệt (duyet.py) cùng khoá này, khỏi ghi đè nhau.
KHOA_DANH_GIA = threading.RLock()


def ghi_nguyen_tu(f, noi_dung, ma_hoa="utf-8"):
    """Ghi file kiểu nguyên tử: ghi vào file tạm cùng thư mục → flush+fsync → os.replace. Mất điện/crash giữa chừng
    thì file cũ vẫn nguyên, không bao giờ để lại JSON cụt. noi_dung: str (hoặc bytes)."""
    f = Path(f); f.parent.mkdir(parents=True, exist_ok=True)
    tam = f.with_name(f"{f.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with open(tam, "wb") as fh:
            fh.write(noi_dung if isinstance(noi_dung, bytes) else noi_dung.encode(ma_hoa))
            fh.flush(); os.fsync(fh.fileno())
        os.replace(tam, f)
    finally:
        try:
            tam.unlink()
        except OSError:
            pass


def ghi_json(f, obj, **kw):
    """json.dumps rồi ghi nguyên tử (mặc định ensure_ascii=False)."""
    kw.setdefault("ensure_ascii", False)
    ghi_nguyen_tu(f, json.dumps(obj, **kw))


def ten_tien_trinh(pid):
    """Tên file chạy (vd. 'python.exe') của PID, None nếu PID không còn / không đọc được. Windows: tasklist."""
    import csv, io, subprocess
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for row in csv.reader(io.StringIO(r.stdout)):
            if len(row) >= 2 and row[1].strip() == str(int(pid)):
                return row[0].strip()
    except Exception:
        pass
    return None


def pid_la_lo_sx(pid, ten=None):
    """File khoá dang-chay.lock chỉ còn hiệu lực nếu PID ghi trong đó VẪN là tiến trình python (lô sản xuất).
    PID bị Windows cấp lại cho tiến trình khác (chrome, notepad...) → coi là khoá cũ. ten: để test (tên tiến trình giả định)."""
    ten = ten_tien_trinh(pid) if ten is None else ten
    return bool(ten) and ten.lower().startswith(("python", "pythonw"))


def _tim_data():
    v = (os.environ.get("XUONG_DATA") or "").strip().strip('"')
    if not v or v.startswith("${"):             # launcher để nguyên ${XUONG_DATA} khi chưa đặt
        return REPO / "du-lieu" / "xuong-video"
    p = Path(v)
    return p if p.is_absolute() else REPO / p


DATA = _tim_data()
_DA_KHOI_TAO = False


def khoi_tao():
    """Tạo thư mục dữ liệu từ mẫu nếu còn trống (không bao giờ ghi đè thứ đã có)."""
    global _DA_KHOI_TAO
    if _DA_KHOI_TAO:
        return
    _DA_KHOI_TAO = True
    DATA.mkdir(parents=True, exist_ok=True)
    mau, f = CODE / "mau", DATA / "config.json"
    if not f.exists() and (mau / "config.mau.json").exists():
        c = json.loads((mau / "config.mau.json").read_text(encoding="utf-8"))
        c.setdefault("trypost", {})["khoa"] = secrets.token_urlsafe(24)      # khoá cổng /trypost/* — sinh riêng cho mỗi máy
        ghi_json(f, c, indent=2)
        for d in ("ho-so", "san-pham"):
            if (mau / d).is_dir():
                shutil.copytree(mau / d, DATA / d, dirs_exist_ok=True)
        if (mau / "env.mau").exists() and not (DATA / ".env").exists():
            shutil.copy(mau / "env.mau", DATA / ".env")
    for d in ("lich-su", "ra", "san-pham", "ho-so", "tai-khoan", "tai-nguyen"):
        (DATA / d).mkdir(exist_ok=True)


def cfg_tho():
    """config.json đúng như đang lưu (để ghi lại, không chèn đường dẫn đã giải)."""
    khoi_tao()
    return json.loads((DATA / "config.json").read_text(encoding="utf-8"))


def _tuyet_doi(v):
    p = Path(str(v))
    return p if p.is_absolute() else DATA / p


def _python_mac_dinh():
    for p in (REPO / "runtime" / "xuong-venv" / "Scripts" / "python.exe", DATA / ".venv" / "Scripts" / "python.exe"):
        if p.exists():
            return str(p)
    return sys.executable


AM_TIET_MOI_GIAY = 3.9          # đo từ giọng thật (sau tốc độ 1,1×): ~3,9 âm tiết/giây


def khung_giay(sp=None, c=None):
    """Độ dài video đích (giây) [min, max]: sp["thoi_luong"] (anh chọn khi làm video, mỗi sản phẩm tự nhớ) → config video → 20–25."""
    v = ((c or cfg_tho()).get("video") or {})
    lo, hi = float(v.get("thoi_luong_min") or 20), float(v.get("thoi_luong_max") or 25)
    t = (sp or {}).get("thoi_luong")
    if isinstance(t, (list, tuple)) and len(t) == 2:
        try:
            a, b = float(t[0]), float(t[1])
            if 10 <= a and b <= 60 and b - a >= 3:
                lo, hi = a, b
        except (TypeError, ValueError):
            pass
    return lo, hi


def khung_am_tiet(sp=None, c=None):
    """(đích_min, đích_max, chấp_nhận_min, chấp_nhận_max, câu_min, câu_max) cho lời đọc theo độ dài video đích.
    Giọng + 0,6 s đệm = video → nhắm giọng dài [min+0,3 ; max−1,0] giây."""
    a, b = khung_giay(sp, c)
    lo, hi = round((a + 0.3) * AM_TIET_MOI_GIAY), round((b - 1.0) * AM_TIET_MOI_GIAY)
    c_lo = max(2, round(lo / 20)); c_hi = max(c_lo + 1, round(hi / 12))
    return lo, hi, max(20, lo - 8), hi + 5, c_lo, c_hi


def cfg():
    """config.json + các đường dẫn đã giải (trống -> mặc định; tương đối -> so với DATA). Mã remotion luôn lấy từ CODE."""
    c = cfg_tho()
    dd = dict(c.get("duong_dan") or {})
    mac_dinh = {"ra": DATA / "ra", "env_file": DATA / ".env", "nhac_mixkit": DATA / "tai-nguyen" / "nhac-mixkit",
                "sfx": DATA / "tai-nguyen" / "sfx"}
    for k, d in mac_dinh.items():
        dd[k] = str(_tuyet_doi(dd[k])) if dd.get(k) else str(d)
    dd["remotion"] = os.environ.get("XUONG_REMOTION") or str(CODE / "remotion")
    dd["python"] = dd.get("python") if dd.get("python") and Path(dd["python"]).exists() else _python_mac_dinh()
    dd["claude"] = dd.get("claude") or shutil.which("claude") or "claude"
    c["duong_dan"] = dd
    return c


# ---- Thư mục ngày: chỉ để video .mp4 thành phẩm; hồ sơ (.json), bìa (.jpg), caption (.txt), bảng ghi (.csv) nằm trong _kem/ ----
KEM = "_kem"


def thu_muc_kem(ngay_dir, tao=False):
    """ra/<ngày>/_kem (tao=True: tạo nếu chưa có)."""
    p = Path(ngay_dir) / KEM
    if tao:
        p.mkdir(parents=True, exist_ok=True)
    return p


def kem(mp4, ext, ghi=False):
    """File đi kèm video: <ngày>/_kem/<tên>.<ext>. Đọc (ghi=False): ưu tiên _kem/, không có thì cạnh .mp4 (thư mục cũ);
    cả hai đều chưa có → trả đường dẫn mới trong _kem/. Ghi (ghi=True): luôn trả đường dẫn trong _kem/ (đã tạo thư mục)."""
    mp4 = Path(mp4); ext = ext if ext.startswith(".") else "." + ext
    moi = mp4.parent / KEM / (mp4.stem + ext)
    if ghi:
        moi.parent.mkdir(parents=True, exist_ok=True)
        return moi
    if moi.exists():
        return moi
    cu = mp4.with_suffix(ext)
    return cu if cu.exists() else moi


def kem_ngay(ngay_dir, ten, ghi=False):
    """File cấp ngày (vd. bang-ghi-ekip.csv) — cùng quy tắc như kem()."""
    ngay_dir = Path(ngay_dir)
    moi = ngay_dir / KEM / ten
    if ghi:
        moi.parent.mkdir(parents=True, exist_ok=True)
        return moi
    if moi.exists():
        return moi
    cu = ngay_dir / ten
    return cu if cu.exists() else moi


def glob_kem(ra, mau):
    """Mọi file khớp `mau` (vd. 'ma_*.json') trong ra/<ngày>/_kem/ và ra/<ngày>/ (thư mục cũ) — mỗi (ngày, tên) một lần, _kem ưu tiên."""
    thay, thay_ten = {}, []
    for p in list(Path(ra).glob("*/" + KEM + "/" + mau)) + list(Path(ra).glob("*/" + mau)):
        if not p.is_file():
            continue
        k = (p.parent.parent.name if p.parent.name == KEM else p.parent.name, p.name)
        if k not in thay:
            thay[k] = p
    return sorted(thay.values(), key=lambda p: (p.parent.parent.name if p.parent.name == KEM else p.parent.name, p.name))


def don_kem_cu(ra, dang_chay=False):
    """Chuyển hồ sơ/bìa/caption/csv cũ nằm trực tiếp trong ra/<ngày>/ vào ra/<ngày>/_kem/. Không đụng .mp4; bỏ qua file nếu đích đã có.
    Idempotent. dang_chay=True (đang có lô sản xuất) → không làm gì. Trả {"da_chuyen": n, "bo_qua": n, "ngay": n}."""
    kq = {"da_chuyen": 0, "bo_qua": 0, "ngay": 0}
    ra = Path(ra)
    if dang_chay or not ra.is_dir():
        return kq
    for d in sorted(ra.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        fs = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() != ".mp4"]
        if not fs:
            continue
        kq["ngay"] += 1
        dich = d / KEM
        for f in fs:
            try:
                dich.mkdir(exist_ok=True)
                if (dich / f.name).exists():
                    kq["bo_qua"] += 1
                    continue
                shutil.move(str(f), str(dich / f.name))
                kq["da_chuyen"] += 1
            except OSError:
                kq["bo_qua"] += 1
    return kq
