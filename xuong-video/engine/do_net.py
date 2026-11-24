"""Đo độ NÉT của cảnh (OpenCV, không AI): phương sai Laplacian vùng giữa khung, trung vị ~4 khung trong đoạn dùng được của cảnh
(Kid 24/11: đạo diễn hay chọn cảnh rất nhoè). Kết quả cache bền theo (file, đầu đoạn) trong <DATA>/cache-do-net.json.
nhoe(shot, kho) → True nếu cảnh nhoè; diem_net(shot, kho) → điểm (càng cao càng nét); loc_nhoe(ds, kho) → bỏ cảnh nhoè (giữ đủ tối thiểu)."""
import json, re, threading
from pathlib import Path

import cv2

import sys as _s0; _s0.path.insert(0, str(Path(__file__).resolve().parent))
from duong_dan import DATA, ghi_json

NGUONG = 50.0          # điểm < NGUONG = nhoè. Hiệu chỉnh trên kho đạm cá 919 cảnh 24/11: 5% thấp nhất ≈ 68, trung vị ≈ 510; dưới 50 phần lớn là nhoè/rung/đen thật
NGUONG_AI = 120.0      # vùng xám 50–120: chỉ coi là nhoè khi AI soát cũng ghi "mờ/nhoè/rung/mất nét" (soat.ghi); ≥ 120 luôn coi là nét (nền mờ cố ý, lia nhanh thoáng qua)
TU_NHOE = re.compile(r"(?<!nền )(?<!hậu cảnh )\b(mờ|nhoè|nhòe|mất nét|out nét|rung)\b(?! nền)", re.I)
SO_KHUNG = 4           # số khung lấy mẫu / cảnh (trung vị: 1–2 khung rung tay thoáng qua không làm cảnh bị coi nhoè)
RONG = 540             # thu khung về rộng 540 trước khi đo (điểm không phụ thuộc độ phân giải gốc)
VUNG_GIUA = 0.6        # chỉ đo 60% giữa khung (viền/chữ/nền mờ cố ý không ảnh hưởng)
_KHOA = threading.Lock()
_NHO = None            # cache trong bộ nhớ: {khoá: điểm}


def _f_cache():
    return Path(DATA) / "cache-do-net.json"


def _cache():
    global _NHO
    if _NHO is None:
        try:
            _NHO = json.loads(_f_cache().read_text(encoding="utf-8"))
        except Exception:
            _NHO = {}
    return _NHO


def luu_cache():
    with _KHOA:
        try:
            ghi_json(_f_cache(), _cache())
        except Exception:
            pass


def _duong_dan(shot, kho):
    p = Path(str(shot.get("file") or ""))
    return p if p.is_absolute() or not kho else Path(kho) / p


def _doan(shot):
    """(đầu, cuối) đoạn dùng được: "dep" nếu có (đúng đoạn đạo diễn nhìn thấy), không thì tu → tu+dai."""
    tu = float(shot.get("tu", 0.0))
    den = float(shot.get("den", tu + float(shot.get("dai", 1.0))))
    dep = shot.get("dep")
    if dep and len(dep) == 2:
        a, b = max(tu, float(dep[0])), min(den, float(dep[1]))
        if b > a:
            return a, b
    return tu, den


def net_khung(img):
    """Phương sai Laplacian của 1 khung BGR: xám, rộng RONG, 60% giữa."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = g.shape[:2]
    g = cv2.resize(g, (RONG, max(1, round(h * RONG / w))), interpolation=cv2.INTER_AREA)
    h, w = g.shape[:2]
    dy, dx = int(h * (1 - VUNG_GIUA) / 2), int(w * (1 - VUNG_GIUA) / 2)
    return float(cv2.Laplacian(g[dy:h - dy, dx:w - dx], cv2.CV_64F).var())


def doc_khung(path, ts, crop=None):
    """Đọc các khung tại mốc giây ts (bỏ khung đọc lỗi), áp crop [x,y,w,h] tỉ lệ nếu có."""
    out = []
    cap = cv2.VideoCapture(str(Path(path).resolve()))
    try:
        for t in ts:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, fr = cap.read()
            if not ok:
                continue
            if crop:
                H, W = fr.shape[:2]
                fr = fr[int(H * crop[1]):int(H * (crop[1] + crop[3])), int(W * crop[0]):int(W * (crop[0] + crop[2]))]
            if fr.size:
                out.append(fr)
    finally:
        cap.release()
    return out


def diem_net(shot, kho=None, doc=None):
    """Điểm nét (trung vị phương sai Laplacian) của cảnh; không đọc được video → float('inf') (không loại oan cảnh).
    doc: hàm đọc khung thay thế (path, ts, crop) → [ảnh] (để test)."""
    f = _duong_dan(shot, kho)
    a, b = _doan(shot)
    crop = shot.get("crop")
    khoa = f"{shot.get('file')}|{a:.2f}|{b:.2f}|{crop}"
    nho = _cache()
    if khoa in nho and doc is None:
        return float(nho[khoa])
    ts = [a + (b - a) * (0.1 + 0.8 * j / (SO_KHUNG - 1)) for j in range(SO_KHUNG)]
    try:
        khung = (doc or doc_khung)(f, ts, crop)
        ds = sorted(net_khung(x) for x in khung)
    except Exception:
        ds = []
    if not ds:
        return float("inf")                      # video không đọc được: không phán nhoè (máy dựng sẽ báo lỗi file riêng)
    d = round(ds[len(ds) // 2] if len(ds) % 2 else (ds[len(ds) // 2 - 1] + ds[len(ds) // 2]) / 2, 1)
    if doc is None:
        nho[khoa] = d
    return d


def la_nhoe(shot, d, nguong=None):
    """d = điểm nét của cảnh → nhoè? (dưới NGUONG; hoặc dưới NGUONG_AI mà AI soát cũng ghi nhoè)."""
    ng = NGUONG if nguong is None else nguong
    return d < ng or (d < max(NGUONG_AI, ng) and bool(TU_NHOE.search((shot.get("soat") or {}).get("ghi") or "")))


def nhoe(shot, kho=None, nguong=None, doc=None):
    return la_nhoe(shot, diem_net(shot, kho, doc), nguong)


def loc_nhoe(ds, kho=None, toi_thieu=12, nguong=None):
    """Bỏ cảnh nhoè khỏi ds. Còn < toi_thieu cảnh → bù lại các cảnh ÍT nhoè nhất. Đo song song, cache bền. Giữ thứ tự gốc."""
    from concurrent.futures import ThreadPoolExecutor
    ds = list(ds)
    with ThreadPoolExecutor(max_workers=4) as ex:
        d = list(ex.map(lambda s: diem_net(s, kho), ds))
    luu_cache()
    giu = [i for i, (x, sh) in enumerate(zip(d, ds)) if not la_nhoe(sh, x, nguong)]
    san = min(toi_thieu, int(len(ds) * 0.7))                 # sàn: kho nhỏ vẫn loại được cảnh nhoè (không để sàn = cả kho)
    if len(giu) < san:
        giu = sorted(sorted(range(len(ds)), key=lambda i: -d[i])[:san])
    return [ds[i] for i in giu]
