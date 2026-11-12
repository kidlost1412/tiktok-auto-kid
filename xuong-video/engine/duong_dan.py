"""Đường dẫn của Xưởng Video: MÃ (CODE: engine/, luat/, remotion/, app/ — đi cùng repo)
tách khỏi DỮ LIỆU người dùng (DATA: config.json, .env, san-pham/, lich-su/, ra/, tai-nguyen/, tai-khoan/, ho-so/).

Thư mục dữ liệu chọn theo thứ tự:
  1. biến môi trường XUONG_DATA (tuyệt đối, hoặc tương đối so với thư mục gốc repo);
  2. mặc định <repo>/du-lieu/xuong-video (bản cài mới).
Lần chạy đầu với thư mục dữ liệu trống: tự tạo từ mẫu trong <repo>/xuong-video/mau/."""
import json, os, secrets, shutil, sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]      # <repo>/xuong-video
REPO = CODE.parent


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
        f.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
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
