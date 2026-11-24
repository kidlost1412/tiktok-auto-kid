"""Đo độ NÉT của cảnh (OpenCV, không AI), trung vị ~4 khung trong đoạn dùng được của cảnh
(Kid 24/11: đạo diễn hay chọn cảnh rất nhoè). Kết quả cache bền theo (file, đầu đoạn) trong <DATA>/cache-do-net.json.
Điểm 1 khung (v2): xám rộng 540 → làm mịn σ=2 (bỏ nhiễu hạt/nén) → Laplacian, chia lưới 4×3 trên 80% giữa, lấy tile NÉT NHẤT (phân vị 85:
chủ thể nét trên nền mờ vẫn đạt) theo 2 cách — tuyệt đối và chuẩn hoá theo độ tương phản cục bộ (cảnh thấp tương phản mà nét vẫn đạt);
lấy cái cao hơn. Nhoè do rung/lia (gradient lệch 1 hướng, tensor cấu trúc) bị phạt; vùng nhãn chai (soat.nhan) nét → cảnh không nhoè.
nhoe(shot, kho) → True nếu cảnh nhoè; diem_net(shot, kho) → điểm (càng cao càng nét); loc_nhoe(ds, kho) → bỏ cảnh nhoè (giữ đủ tối thiểu)."""
import json, re, threading
from pathlib import Path

import cv2
import numpy as np

import sys as _s0; _s0.path.insert(0, str(Path(__file__).resolve().parent))
from duong_dan import DATA, ghi_json

PHIEN_BAN = "v2"      # đổi khi đổi cách tính điểm → điểm cache cũ bị bỏ, đo lại
NGUONG = 50.0          # điểm < NGUONG = nhoè. v2 (hiệu chỉnh 24/11 trên ~600 khung thật + khung nhoè giả): điểm = 50 ⇔ lưới-tile nét nhất mịn σ2 ≈ 1.5 (tuyệt đối) và 8e-4 (chuẩn hoá)
NGUONG_AI = 120.0      # vùng xám 50–120: chỉ coi là nhoè khi AI soát cũng ghi "mờ/nhoè/rung/mất nét" (soat.ghi); ≥ 120 luôn coi là nét (nền mờ cố ý, lia nhanh thoáng qua)
A0, N0 = 1.5, 8e-4     # mốc "vừa đủ nét" của điểm tuyệt đối / chuẩn hoá (ứng với điểm NGUONG)
LUOI = (4, 3)          # lưới tile (hàng, cột) trên vùng đo
PHAN_VI = 85           # lấy tile nét ở phân vị này (không lấy trung bình: chủ thể nét + nền bokeh vẫn đạt)
LECH_HUONG = 3.0       # tensor cấu trúc: λ1/λ2 ≥ mốc này mà không nét rõ → nhoè rung/lia (chuyển động 1 hướng)
LECH_NET_TOI_DA = 4.0  # …chỉ phạt khi điểm tuyệt đối A < mốc này (cảnh có vân dọc/ngang thật như hàng rào, thân cây vẫn nét thì thôi)
TU_NHOE = re.compile(r"(?<!nền )(?<!hậu cảnh )\b(mờ|nhoè|nhòe|mất nét|out nét|rung)\b(?! nền)", re.I)
SO_KHUNG = 4           # số khung lấy mẫu / cảnh (trung vị: 1–2 khung rung tay thoáng qua không làm cảnh bị coi nhoè)
RONG = 540             # thu khung về rộng 540 trước khi đo (điểm không phụ thuộc độ phân giải gốc)
VUNG_GIUA = 0.8        # chỉ đo 80% giữa khung (viền/chữ đè mép không ảnh hưởng)
_KHOA = threading.Lock()
_NHO = None            # cache trong bộ nhớ: {khoá: điểm}


def _f_cache():
    return Path(DATA) / "cache-do-net.json"


def _cache():
    global _NHO
    if _NHO is None:
        try:
            _NHO = {k: v for k, v in json.loads(_f_cache().read_text(encoding="utf-8")).items() if k.startswith(PHIEN_BAN + "|")}
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


def _tile_diem(g, b, hang, cot):
    """(A, N) của vùng g (xám float32) với b = bản làm mịn σ2: tile nét nhất (phân vị PHAN_VI) theo Laplacian(b) tuyệt đối / chia (phương sai g + 400)."""
    lap = cv2.Laplacian(b, cv2.CV_32F)
    h, w = g.shape
    ys, xs = np.linspace(0, h, hang + 1).astype(int), np.linspace(0, w, cot + 1).astype(int)
    lv, nz = [], []
    for i in range(hang):
        for j in range(cot):
            sl = (slice(ys[i], ys[i + 1]), slice(xs[j], xs[j + 1]))
            v = float(lap[sl].var())
            lv.append(v)
            nz.append(v / (float(g[sl].var()) + 400.0))
    return float(np.percentile(lv, PHAN_VI)), float(np.percentile(nz, PHAN_VI))


def _quy(a, n):
    return 50.0 * max(a / A0, n / N0)


def _lech_huong(g):
    """λ1/λ2 của tensor cấu trúc gradient (1 = đều mọi hướng; lớn = chỉ còn nét theo 1 hướng → nhoè chuyển động)."""
    gx, gy = cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)
    xx, yy, xy = float((gx * gx).mean()), float((gy * gy).mean()), float((gx * gy).mean())
    d = (((xx - yy) / 2) ** 2 + xy * xy) ** 0.5
    return (((xx + yy) / 2 + d) / ((xx + yy) / 2 - d + 1e-6))


def net_khung(img, nhan=None):
    """Điểm nét 1 khung BGR (≥ NGUONG = nét; cao hơn = nét hơn). nhan = [x0,y0,x1,y1] 0–1 (khung nhãn chai của soát): nhãn nét → cả khung tính là nét."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = g.shape[:2]
    g = cv2.resize(g, (RONG, max(1, round(h * RONG / w))), interpolation=cv2.INTER_AREA).astype(np.float32)
    h, w = g.shape
    b = cv2.GaussianBlur(g, (0, 0), 2.0)
    dy, dx = int(h * (1 - VUNG_GIUA) / 2), int(w * (1 - VUNG_GIUA) / 2)
    mid = (slice(dy, h - dy), slice(dx, w - dx))
    a, n = _tile_diem(g[mid], b[mid], *LUOI)
    d = _quy(a, n)
    if a < LECH_NET_TOI_DA and _lech_huong(g[mid]) >= LECH_HUONG:
        d = min(d, 0.8 * NGUONG)
    if nhan and len(nhan) == 4:
        try:
            x0, y0, x1, y1 = [min(1.0, max(0.0, float(v))) for v in nhan]
            sl = (slice(int(h * y0), int(h * y1)), slice(int(w * x0), int(w * x1)))
            if (sl[0].stop - sl[0].start) >= 48 and (sl[1].stop - sl[1].start) >= 48:
                d = max(d, _quy(*_tile_diem(g[sl], b[sl], 2, 2)))
        except (TypeError, ValueError):
            pass
    return float(d)


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
    nhan = (shot.get("soat") or {}).get("nhan")
    khoa = f"{PHIEN_BAN}|{shot.get('file')}|{a:.2f}|{b:.2f}|{crop}|{nhan}"
    nho = _cache()
    if khoa in nho and doc is None:
        return float(nho[khoa])
    ts = [a + (b - a) * (0.1 + 0.8 * j / (SO_KHUNG - 1)) for j in range(SO_KHUNG)]
    try:
        khung = (doc or doc_khung)(f, ts, crop)
        ds = sorted(net_khung(x, nhan) for x in khung)
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
