"""Loại cảnh dính CHỮ/ĐỒ HOẠ LẠ chèn sẵn trong video nguồn (sticker giá của shop khác, thanh caption, bình luận, mũi tên, logo CapCut…) —
chữ trên nhãn sản phẩm (soat.nhan) thì KHÔNG tính. Ba tầng, không AI:
 (a) từ khoá trong soat.ghi (sticker/logo/CapCut/watermark/chữ chèn/bình luận…);
 (b) OpenCV từng khung (thu rộng 360, vùng nhãn bị che):
     - CHỮ: nét mảnh tương phản cao (top-hat/black-hat) xếp thành dải chữ nằm ngang dày đặc;
     - MŨI TÊN/STICKER: mảng đỏ/vàng bão hoà, PHẲNG (độ lệch xám trong mảng nhỏ), hình gọn, cỡ sticker (mũi tên đỏ/vàng trong video "chỉ chỗ");
     - KHUNG BÌNH LUẬN/CHIP CHỮ: khối chữ nhật trắng-sáng hoặc đơn sắc bão hoà có CẠNH TRÊN + CẠNH DƯỚI thẳng, sắc (bong bóng "Trả lời bình luận", chip chữ vàng/xanh);
     - ẢNH GHÉP (inset): khung chữ nhật cạnh thẳng 4 phía, giữ nguyên vị trí qua các khung;
 (c) tín hiệu phụ giữa các khung: điểm ảnh có nét mạnh mà đứng yên y hệt qua cả 3 khung trong khi cảnh đang chuyển động (lớp phủ tĩnh, cảnh thì không).
     Gộp thành 1 điểm (đơn vị 0.01 = ngưỡng NGUONG). Cache bền theo (file, đoạn, phiên bản thuật toán) trong <DATA>/cache-chu-la.json.
la_chu_la(shot, d) → bool; diem_chu_la(shot, kho) → điểm; loc_chu_la(ds, kho, toi_thieu=12) → bỏ cảnh dính chữ lạ (giữ đủ tối thiểu)."""
import json, re, threading
from pathlib import Path

import cv2
import numpy as np

import sys as _s0; _s0.path.insert(0, str(Path(__file__).resolve().parent))
from duong_dan import DATA, ghi_json
from do_net import doc_khung, _doan, _duong_dan

PHIEN_BAN = "v2"        # đổi khi đổi thuật toán/ngưỡng → điểm cũ trong cache tự bị bỏ
NGUONG = 0.01           # điểm ≥ NGUONG = dính chữ lạ (đơn vị: 1.0 của mỗi tín hiệu = NGUONG)
TU_KHOA = re.compile(r"sticker|logo|capcut|watermark|chữ chèn|chữ đè|chữ lạ|caption|bình luận|phụ đề|nhãn dán|mã id|tên kênh|@\w+", re.I)
SO_KHUNG = 3
RONG = 360              # thu khung về rộng 360 trước khi phân tích
MANH = 90               # ngưỡng độ tương phản nét mảnh (0-255)
LE_NHAN = 0.04          # nới khung nhãn mỗi phía (tỉ lệ khung) khi loại trừ
CANH_THANG = 0.8        # cạnh trên/dưới của khối: ≥ 80% chiều dài có bậc sáng ≥ 70 (Sobel)
TINH_NG = 0.012         # tín hiệu phụ "nét đứng yên" (phần diện tích khung) đủ ngưỡng
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


def _nho(img):
    h, w = img.shape[:2]
    return cv2.resize(img, (RONG, max(1, round(h * RONG / w))), interpolation=cv2.INTER_AREA)


def _che(m, nhan, bang=0.0):
    """Xoá (=0/False) vùng nhãn sản phẩm (nới LE_NHAN) khỏi mặt nạ m, tại chỗ."""
    if nhan and len(nhan) == 4:
        H, W = m.shape[:2]
        x0, y0, x1, y1 = nhan
        m[max(0, int((y0 - LE_NHAN) * H)):int((y1 + LE_NHAN) * H) + 1, max(0, int((x0 - LE_NHAN) * W)):int((x1 + LE_NHAN) * W) + 1] = bang
    return m


def diem_1khung(img, nhan=None):
    """Điểm CHỮ của 1 khung BGR: phần diện tích khung bị các dải nét MẢNH (sáng hoặc tối, top-hat/black-hat 9px) xếp ngang dày đặc chiếm —
    đúng kiểu chữ chèn viền/phụ đề/sticker. Vùng nhãn sản phẩm (nhan) bị che đi trước khi đo."""
    g = cv2.cvtColor(_nho(img), cv2.COLOR_BGR2GRAY)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    m = ((cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k) > MANH) | (cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, k) > MANH)).astype(np.uint8)
    H, W = m.shape
    _che(m, nhan, 0)
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


def _mui_ten(hsv, g, nhan):
    """Có sticker/mũi tên phẳng không: mảng đỏ hoặc vàng bão hoà, cỡ 250–4000px (ở rộng 360), gọn (solidity ≥ .55, lấp 30–80% khung bao),
    độ lệch xám trong mảng ≤ 5.5 (vật thật có vân nên lệch cao hơn), và đúng MÀU STICKER: đỏ thuần (S ≥ 245, V ≥ 215 — loại đất đỏ, nắp chai tối)
    hoặc vàng mũi tên (hue 23–28, V ≥ 244) có viền sắc (độ dốc sáng quanh mảng ≥ 85 — loại lá vàng, nước vàng nhoè)."""
    H_, S, V = hsv[..., 0].astype(np.int16), hsv[..., 1], hsv[..., 2]
    m = ((((H_ <= 8) | (H_ >= 170)) & (S >= 190) & (V >= 170)) | ((H_ >= 18) & (H_ <= 34) & (S >= 190) & (V >= 190))).astype(np.uint8)
    h, w = m.shape
    _che(m, nhan, 0)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lb, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    gm = None
    for i in range(1, n):
        x, y, bw, bh, a = st[i]
        if a < 250 or a > 4000 or bw > 0.22 * w or bh > 0.22 * h or not (0.3 <= a / (bw * bh) <= 0.8):
            continue
        cm = (lb[y:y + bh, x:x + bw] == i).astype(np.uint8)
        cs, _ = cv2.findContours(cm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        hull = cv2.contourArea(cv2.convexHull(max(cs, key=cv2.contourArea)))
        if a / max(hull, 1.0) < 0.55 or g[y:y + bh, x:x + bw][cm > 0].std() > 5.5:
            continue
        hue = float(np.median(np.where(H_[y:y + bh, x:x + bw][cm > 0] >= 90, H_[y:y + bh, x:x + bw][cm > 0] - 180, H_[y:y + bh, x:x + bw][cm > 0])))
        sat, val = float(np.median(S[y:y + bh, x:x + bw][cm > 0])), float(np.median(V[y:y + bh, x:x + bw][cm > 0]))
        if abs(hue) <= 5 and sat >= 245 and val >= 215:
            return 1
        if 23 <= hue <= 28 and val >= 244:
            if gm is None:
                gm = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
            ve = cv2.dilate(cm, np.ones((3, 3), np.uint8)) - cv2.erode(cm, np.ones((3, 3), np.uint8))
            if gm[y:y + bh, x:x + bw][ve > 0].mean() >= 85:
                return 1
    return 0


def _canh(gy, x, y, w, h):
    """Độ thẳng-sắc của cạnh trên và cạnh dưới khối (x,y,w,h): phần cột (ở giữa 70%) có bậc sáng dọc ≥ 70 quanh đường biên."""
    H = gy.shape[0]
    x0, x1 = x + int(w * 0.15), x + int(w * 0.85)
    r = []
    for yc in (y, y + h - 1):
        a, b = max(0, yc - 3), min(H, yc + 4)
        r.append(float((gy[a:b, x0:x1].max(axis=0) >= 70).mean()) if b > a and x1 > x0 else 0.0)
    return r


def _khoi(s_bgr, hsv, g, nhan):
    """Khối chữ nhật sáng-trắng (bong bóng bình luận, hộp chữ) hoặc đơn sắc bão hoà (chip chữ) có cạnh trên & dưới thẳng sắc, chứa nét chữ.
    Trả (độ thẳng cạnh nhỏ nhất của khối tốt nhất)."""
    h, w = g.shape
    gy = np.abs(cv2.Sobel(cv2.GaussianBlur(g, (3, 3), 0), cv2.CV_16S, 0, 1))
    wm = ((hsv[..., 2] >= 225) & (hsv[..., 1] <= 40)).astype(np.float32)
    sm = ((hsv[..., 1] >= 120) & (hsv[..., 2] >= 140)).astype(np.uint8)
    best = 0.0
    for loai, m in (("w", (cv2.blur(wm, (7, 7)) >= 0.5).astype(np.uint8)), ("s", cv2.morphologyEx(sm, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)))):
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (21, 9)))
        _che(m, nhan, 0)
        n, lb, st, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
        for i in range(1, n):
            x, y, bw, bh, a = st[i]
            if y == 0 or bw < 0.16 * w or bw < 1.4 * bh or bh < 0.025 * h or not (0.004 * h * w <= bw * bh <= 0.12 * h * w):
                continue
            if x == 0 and x + bw >= w:
                continue
            cm = (lb[y:y + bh, x:x + bw] == i).astype(np.uint8)
            cs, _ = cv2.findContours(cm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            sol = np.zeros_like(cm)
            cv2.drawContours(sol, cs, -1, 1, -1)
            if sol.sum() / float(bw * bh) < 0.72:
                continue
            reg = s_bgr[y:y + bh, x:x + bw].astype(np.int16)
            nen = np.median(reg.reshape(-1, 3), axis=0)
            lech = np.abs(reg - nen).max(axis=2)
            if (lech > 60).mean() < 0.006 or (lech <= 16).mean() < 0.45:
                continue                                   # không có nét chữ bên trong / không đơn sắc (trời, mây, tán lá, áo trắng) → không phải khung chữ
            if loai == "w" and nen.min() < 247:
                continue                                   # bong bóng bình luận trắng gần tuyệt đối (≥ 247); trời/mây thường 215–245
            best = max(best, min(_canh(gy, x, y, bw, bh)))
    return best


def _inset(g):
    """Khung chữ nhật lớn (≥ 12% cao khung) có CẢ 4 cạnh thẳng sắc: cạnh ngang dài (≥ 18% rộng) ghép cặp, hai cạnh dọc phủ ≥ 90% chiều cao.
    Trả list (x, y, w) khung ứng viên của 1 khung hình — dùng để xét có đứng yên qua các khung không."""
    h, w = g.shape
    b = cv2.GaussianBlur(g, (3, 3), 0)
    gx = np.abs(cv2.Sobel(b, cv2.CV_16S, 1, 0))
    e = (np.abs(cv2.Sobel(b, cv2.CV_16S, 0, 1)) > 14 * 4).astype(np.uint8)
    e = cv2.morphologyEx(e, cv2.MORPH_CLOSE, np.ones((1, 13), np.uint8))
    L = int(0.18 * w)
    o = cv2.morphologyEx(e, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (L, 1)))
    n, _, st, _ = cv2.connectedComponentsWithStats(o, connectivity=8)
    hs = sorted((tuple(int(v) for v in s[:4]) for s in st[1:] if s[2] >= L and s[3] <= 10), key=lambda s: -s[2])[:60]
    out = []
    for i, a in enumerate(hs):
        for c in hs[i + 1:]:
            t, bo = (a, c) if a[1] < c[1] else (c, a)
            dy = bo[1] - t[1]
            if dy < 0.12 * h or dy > 0.8 * h or abs(t[0] - bo[0]) > 16 or abs(t[0] + t[2] - bo[0] - bo[2]) > 16:
                continue
            x0, x1 = max(t[0], bo[0]), min(t[0] + t[2], bo[0] + bo[2])
            y0, y1 = t[1] + t[3] // 2, bo[1] + bo[3] // 2
            ok = True
            for xc in (x0, x1):
                col = gx[y0 + int(0.1 * (y1 - y0)):y1 - int(0.1 * (y1 - y0)), max(0, xc - 3):min(w, xc + 4)]
                if col.size == 0 or (col.max(axis=1) >= 56).mean() < 0.9:
                    ok = False
                    break
            if ok:
                out.append((x0, y0, x1 - x0))
    return out


def dac_trung_khung(img, nhan=None):
    """Số đo của 1 khung BGR: chu (điểm chữ), mui_ten (0/1), khoi (độ thẳng cạnh 0–1), inset (list khung ứng viên)."""
    s = _nho(img)
    hsv, g = cv2.cvtColor(s, cv2.COLOR_BGR2HSV), cv2.cvtColor(s, cv2.COLOR_BGR2GRAY)
    return {"chu": diem_1khung(img, nhan), "mui_ten": _mui_ten(hsv, g, nhan), "khoi": _khoi(s, hsv, g, nhan), "inset": _inset(g)}


def tinh_dung_yen(khung, nhan=None):
    """Phần diện tích khung gồm điểm có NÉT MẠNH mà y hệt (±6) qua 3 khung — lớp phủ tĩnh. (0 nếu < 3 khung hoặc gần như cả khung đứng yên: tripod/ảnh tĩnh.)"""
    if len(khung) < 3:
        return 0.0
    g = [cv2.GaussianBlur(cv2.cvtColor(_nho(x), cv2.COLOR_BGR2GRAY), (3, 3), 0) for x in khung[:3]]
    a, b, c = (x.astype(np.int16) for x in g)
    st = (np.abs(a - b) <= 6) & (np.abs(b - c) <= 6) & (np.abs(a - c) <= 6)
    if st.mean() > 0.5:
        return 0.0
    ed = (np.abs(cv2.Sobel(g[1], cv2.CV_16S, 1, 0)) + np.abs(cv2.Sobel(g[1], cv2.CV_16S, 0, 1))) >= 120
    _che(ed, nhan, False)
    return float((st & ed).sum()) / ed.size


def _ben(ds):
    """Có ≥ 2 khung (hoặc cả khung nếu chỉ có 1–2) chứa khung ứng viên (x,y,w) ở gần cùng vị trí."""
    need = min(2, len(ds))
    for a in ds:
        for c in a:
            if sum(any(abs(c[0] - d[0]) <= 8 and abs(c[1] - d[1]) <= 8 and abs(c[2] - d[2]) <= 10 for d in b) for b in ds) >= need:
                return True
    return False


def diem_khung(khung, nhan=None):
    """Điểm chữ/đồ hoạ lạ của cảnh (đơn vị: NGUONG = 1 tín hiệu đủ ngưỡng). Chữ lấy trung vị 3 khung (phụ đề đổi chữ liên tục);
    mũi tên/khối cần ≥ nửa số khung; ảnh ghép cần đứng yên ≥ 2 khung; tín hiệu đứng yên chỉ cộng thêm."""
    if not khung:
        return 0.0
    f = [dac_trung_khung(k, nhan) for k in khung]
    n = len(f)
    chu = sorted(x["chu"] for x in f)
    chu = chu[n // 2] if n % 2 else (chu[n // 2 - 1] + chu[n // 2]) / 2
    return round(NGUONG * _gop(chu / NGUONG, f, tinh_dung_yen(khung, nhan)), 4)


def _gop(chu, f, tinh):
    """Gộp các tín hiệu (đơn vị ngưỡng, ≥ 1 = dính). Hiệu chỉnh 24/11 trên 707 cảnh (136 cảnh soi bằng mắt):
    chữ (trung vị 3 khung) | mũi tên ≥ 1 khung (đúng màu + phẳng + viền sắc → gần như không dương tính giả) | khung bình luận ≥ nửa số khung |
    chữ YẾU (max 3 khung ≥ 0.003) + nét đứng yên ≥ 0.008 | khung bình luận 1 khung hoặc ảnh ghép đứng yên + nét đứng yên ≥ 0.004."""
    n = len(f)
    mui = 1.0 if any(x["mui_ten"] for x in f) else 0.0
    khoi = 1.0 if sum(x["khoi"] >= CANH_THANG for x in f) >= (n + 1) // 2 else 0.0
    yeu = min(tinh / TINH_NG, max(x["chu"] for x in f) / (NGUONG * 0.3))
    phu = 1.0 if tinh >= 0.004 and (any(x["khoi"] >= CANH_THANG for x in f) or _ben([x["inset"] for x in f])) else 0.0
    return max(chu, mui, khoi, yeu, phu)


def diem_chu_la(shot, kho=None, doc=None):
    """Điểm chữ lạ của cảnh (0 = sạch). Không đọc được video → 0 (không loại oan). doc: hàm đọc khung thay thế (path, ts, crop)."""
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
        d = diem_khung((doc or doc_khung)(f, ts, crop), nhan)
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
