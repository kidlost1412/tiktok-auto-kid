"""Loại cảnh dính CHỮ/ĐỒ HOẠ LẠ chèn sẵn trong video nguồn (sticker giá của shop khác, thanh caption, bình luận, logo CapCut…) —
chữ trên nhãn sản phẩm (soat.nhan) thì KHÔNG tính. Hai tầng, không AI:
 (a) từ khoá trong soat.ghi (sticker/logo/CapCut/watermark/chữ chèn/bình luận…);
 (b) OpenCV: nét mảnh tương phản cao (top-hat/black-hat) xếp thành dải chữ nằm ngang dày đặc, nằm ngoài khung nhãn, trung vị 3 khung.
     Điểm = phần diện tích khung bị các dải đó chiếm. Cache bền theo (file, đoạn) trong <DATA>/cache-chu-la.json.
la_chu_la(shot, d) → bool; diem_chu_la(shot, kho) → điểm; loc_chu_la(ds, kho, toi_thieu=12) → bỏ cảnh dính chữ lạ (giữ đủ tối thiểu)."""
import json, re, threading
from pathlib import Path

import cv2
import numpy as np

import sys as _s0; _s0.path.insert(0, str(Path(__file__).resolve().parent))
from duong_dan import DATA, ghi_json
from do_net import doc_khung, _doan, _duong_dan

NGUONG = 0.01           # điểm ≥ NGUONG = dính chữ lạ. Hiệu chỉnh 24/11 trên 4 kho (435 cảnh mẫu): bắt ~28% cảnh chu_muc 1, ~2% cảnh chu_muc 0 (đa số là cảnh có chữ thật mà AI soát bỏ sót)
TU_KHOA = re.compile(r"sticker|logo|capcut|watermark|chữ chèn|chữ đè|chữ lạ|caption|bình luận|phụ đề|nhãn dán|mã id|tên kênh|@\w+", re.I)
SO_KHUNG = 3
RONG = 360              # thu khung về rộng 360 trước khi phân tích
MANH = 90               # ngưỡng độ tương phản nét mảnh (0-255)
LE_NHAN = 0.04          # nới khung nhãn mỗi phía (tỉ lệ khung) khi loại trừ
_KHOA = threading.Lock()
_NHO = None


def _f_cache():
    return Path(DATA) / "cache-chu-la.json"


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


def diem_1khung(img, nhan=None):
    """Điểm chữ lạ của 1 khung BGR: phần diện tích khung bị các dải nét MẢNH (sáng hoặc tối, top-hat/black-hat 9px) xếp ngang dày đặc chiếm —
    đúng kiểu chữ chèn viền/phụ đề/sticker. Vùng nhãn sản phẩm (nhan) bị che đi trước khi đo."""
    h, w = img.shape[:2]
    g = cv2.cvtColor(cv2.resize(img, (RONG, max(1, round(h * RONG / w)))), cv2.COLOR_BGR2GRAY)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    m = ((cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k) > MANH) | (cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, k) > MANH)).astype(np.uint8)
    H, W = m.shape
    if nhan and len(nhan) == 4:
        x0, y0, x1, y1 = nhan
        m[max(0, int((y0 - LE_NHAN) * H)):int((y1 + LE_NHAN) * H) + 1, max(0, int((x0 - LE_NHAN) * W)):int((x1 + LE_NHAN) * W) + 1] = 0
    c = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5)))
    n, _, st, _ = cv2.connectedComponentsWithStats(c, connectivity=8)
    tong = 0.0
    for i in range(1, n):
        x, y, ww, hh, _a = st[i]
        if ww < W * 0.12 or not (H * 0.02 <= hh <= H * 0.12) or ww < 3 * hh:
            continue                                   # không phải dải chữ (quá hẹp / cao / vuông)
        fill = m[y:y + hh, x:x + ww].mean()            # mật độ nét thật trong dải: lá/cỏ thưa hơn chữ
        if fill >= 0.12:
            tong += ww * hh * min(1.0, fill / 0.25)
    return tong / float(H * W)


def diem_khung(khung, nhan=None):
    """Điểm chữ lạ của cảnh = trung vị điểm từng khung BGR (phụ đề đổi chữ liên tục nên không đòi chữ đứng yên)."""
    ds = sorted(diem_1khung(k, nhan) for k in khung)
    return ds[len(ds) // 2] if len(ds) % 2 else (ds[len(ds) // 2 - 1] + ds[len(ds) // 2]) / 2 if ds else 0.0


def diem_chu_la(shot, kho=None, doc=None):
    """Điểm chữ lạ của cảnh (0 = sạch). Không đọc được video → 0 (không loại oan). doc: hàm đọc khung thay thế (path, ts, crop)."""
    f = _duong_dan(shot, kho)
    a, b = _doan(shot)
    crop = shot.get("crop")
    nhan = (shot.get("soat") or {}).get("nhan")
    khoa = f"{shot.get('file')}|{a:.2f}|{b:.2f}|{crop}|{nhan}"
    nho = _cache()
    if khoa in nho and doc is None:
        return float(nho[khoa])
    ts = [a + (b - a) * (0.1 + 0.8 * j / (SO_KHUNG - 1)) for j in range(SO_KHUNG)]
    try:
        d = round(diem_khung((doc or doc_khung)(f, ts, crop), nhan), 4)
    except Exception:
        return 0.0
    if doc is None:
        nho[khoa] = d
    return d


def la_chu_la(shot, d, nguong=None):
    ng = NGUONG if nguong is None else nguong
    return d >= ng or bool(TU_KHOA.search((shot.get("soat") or {}).get("ghi") or ""))


def loc_chu_la(ds, kho=None, toi_thieu=12, nguong=None):
    """Bỏ cảnh dính chữ lạ khỏi ds. Còn < toi_thieu (tối đa 70% kho) → bù các cảnh ít chữ lạ nhất. Giữ thứ tự gốc."""
    from concurrent.futures import ThreadPoolExecutor
    ds = list(ds)
    with ThreadPoolExecutor(max_workers=4) as ex:
        d = list(ex.map(lambda s: diem_chu_la(s, kho), ds))
    luu_cache()
    giu = [i for i, (x, sh) in enumerate(zip(d, ds)) if not la_chu_la(sh, x, nguong)]
    san = min(toi_thieu, int(len(ds) * 0.7))
    if len(giu) < san:
        giu = sorted(sorted(range(len(ds)), key=lambda i: d[i])[:san])
    return [ds[i] for i in giu]
