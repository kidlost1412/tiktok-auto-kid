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
