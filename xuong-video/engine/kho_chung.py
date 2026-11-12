"""KHO CẢNH DÙNG CHUNG + KHO PHỤ khi làm video.
- Hồ sơ san-pham.json có "loai": "kho-chung" => chỉ là kho cảnh để sản phẩm khác mượn, KHÔNG bán, KHÔNG làm video cho nó.
  (Cờ cũ "chi_la_kho_canh": true vẫn được hiểu là kho chung.)
- "tron_mac_dinh": true => kho này tự được trộn vào video của mọi sản phẩm khi anh chưa chọn gì (video-vuon: giữ đúng hành vi cũ).
- "kho_them": [mã, ...] trong hồ sơ sản phẩm = lựa chọn gần nhất của anh "Dùng thêm cảnh từ kho khác" (UI lưu, tự động dùng lại).
Cảnh kho phụ chỉ là PHỤ (b-roll/ô phụ): dao_dien.py giới hạn tối đa TY_LE_KHO_THEM số cảnh của 1 video."""
import json, re
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
SP = HUB / "san-pham"
TY_LE_KHO_THEM = 0.30          # tối đa 30% số cảnh (kể cả ô phụ) của 1 video lấy từ kho phụ


def la_kho_chung(sp):
    return bool(sp) and (sp.get("loai") == "kho-chung" or bool(sp.get("chi_la_kho_canh")))


def _doc(ma):
    try:
        return json.loads((SP / ma / "san-pham.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def ds_kho_chung():
    """Mã các kho cảnh dùng chung (theo thứ tự tên)."""
    return [d.name for d in sorted(SP.iterdir()) if d.is_dir() and la_kho_chung(_doc(d.name))]


def mac_dinh_kho_them(ma_sp):
    """Chưa từng chọn → các kho chung đánh dấu tron_mac_dinh (hiện chỉ video-vuon)."""
    return [m for m in ds_kho_chung() if (_doc(m) or {}).get("tron_mac_dinh") and m != ma_sp]


def kho_them_cua(ma_sp, sp=None):
    """Danh sách mã kho phụ cho video của ma_sp: lựa chọn đã nhớ nếu có, không thì mặc định. Chỉ giữ kho có thật, có cảnh, khác chính nó.
    Kho chung không tự mượn kho khác."""
    sp = sp if sp is not None else (_doc(ma_sp) or {})
    if la_kho_chung(sp):
        return []
    ds = sp.get("kho_them")
    if not isinstance(ds, list):
        ds = mac_dinh_kho_them(ma_sp)
    out = []
    for m in ds:
        if isinstance(m, str) and m != ma_sp and m not in out and re.fullmatch(r"[a-z0-9-]+", m) and (SP / m / "canh.json").exists():
            out.append(m)
    return out


_CACHE = {}


def dem_dung_duoc(ma):
    """Số cảnh dùng được làm cảnh phụ (đã qua AI soát, không lỗi nặng, không chai/nhãn/hàng khác) — nhớ theo giờ sửa file."""
    f = SP / ma / "canh.json"
    if not f.exists():
        return 0
    k = (str(f), f.stat().st_mtime)
    if k not in _CACHE:
        _CACHE[k] = len(canh_pool(ma))
    return _CACHE[k]


def canh_pool(ma, tien_to="V-"):
    """Cảnh của kho `ma` dùng được làm cảnh phụ. id = tien_to + id gốc, file là đường dẫn tuyệt đối, gắn "kho_them": ma.
    Bỏ cảnh có chai/gói/nhãn (có thể là hãng khác), cảnh chưa soát, cảnh lỗi."""
    from soat_kho import bad
    d = SP / ma
    sp = _doc(ma)
    if not sp or not (d / "canh.json").exists():
        return []
    out = []
    for s in json.loads((d / "canh.json").read_text(encoding="utf-8")):
        x0 = s.get("soat") or {}
        if not x0 or bad(s) or x0.get("nhan") or x0.get("hang_khac") or {"chai_ro", "nhan_can", "kho_hang"} & set(s.get("vai_tro", [])):
            continue
        x = dict(s); x["id"] = tien_to + s["id"]; x["file"] = str(Path(sp["kho_video"]) / s["file"])
        x.setdefault("dep", [s["tu"], s.get("den", s["tu"] + s["dai"])])
        x["kho_them"] = ma; x["_khung_goc"] = str(d / "_khung" / f"{s['id']}.jpg")
        out.append(x)
    return out
