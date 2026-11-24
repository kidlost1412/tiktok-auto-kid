"""Dò tâm khuôn mặt trong đoạn cảnh (OpenCV Haar, không AI) để ô hẹp/khung chia canh theo mặt người, không canh theo chai
(Kid 23/11: khung aff cầm chai đẹp mà ô cắt mất mặt). Lỗi/không thấy mặt → None, bố cục dùng cách canh cũ."""
from pathlib import Path

import cv2

_CASC = None
_NHO = {}


def _casc():
    global _CASC
    if _CASC is None:
        _CASC = [cv2.CascadeClassifier(cv2.data.haarcascades + f) for f in
                 ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml")]
    return _CASC


def mat_trong_anh(img):
    """→ [(fx, fy, cao)] mọi ứng viên mặt, theo tỉ lệ 0–1 của ảnh."""
    h, w = img.shape[:2]
    g = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img)
    nho = max(24, w // 14)
    ds = []
    for c in _casc():
        ds += [tuple(r) for r in c.detectMultiScale(g, 1.1, 6, minSize=(nho, nho))]
        ds += [(w - x - fw, y, fw, fh) for x, y, fw, fh in c.detectMultiScale(cv2.flip(g, 1), 1.1, 6, minSize=(nho, nho))]
    return [((x + fw / 2) / w, (y + fh / 2) / h, fh / h) for x, y, fw, fh in ds]


def chon_mat(khung):
    """khung: [[ứng viên] mỗi khung]. Mặt thật lặp lại ở nhiều khung; nhãn chai/áo chỉ thoáng qua → lấy cụm có mặt ở nhiều khung nhất (hoà: mặt to hơn).
    Chỉ thấy ở 1 khung trong ≥ 3 khung → không tin."""
    ung = [(i, m) for i, ds in enumerate(khung) for m in ds]
    best = None
    for _, m in ung:
        cum = [(j, c) for j, c in ung if abs(c[0] - m[0]) < 0.12 and abs(c[1] - m[1]) < 0.12]
        diem = (len({j for j, _ in cum}), m[2])
        if best is None or diem > best[0]:
            best = (diem, cum)
    if not best or (len(khung) >= 3 and best[0][0] < 2):
        return None
    cum = best[1]
    return round(float(sum(c[0] for _, c in cum) / len(cum)), 3), round(float(sum(c[1] for _, c in cum) / len(cum)), 3)


def tam_mat(path, t0, dai, crop=None):
    """Tâm mặt (fx, fy) trên 4 khung của đoạn [t0, t0+dai], toạ độ trong cảnh đã cắt crop=(x,y,w,h) tỉ lệ."""
    key = (str(path), round(float(t0), 2), round(float(dai), 2), tuple(crop or ()))
    if key in _NHO:
        return _NHO[key]
    kq = None
    try:
        cap = cv2.VideoCapture(str(Path(path).resolve()))
        khung = []
        for p in (0.15, 0.4, 0.65, 0.9):
            cap.set(cv2.CAP_PROP_POS_MSEC, (float(t0) + float(dai) * p) * 1000)
            ok, fr = cap.read()
            if not ok:
                continue
            if crop:
                H, W = fr.shape[:2]
                fr = fr[int(H * crop[1]):int(H * (crop[1] + crop[3])), int(W * crop[0]):int(W * (crop[0] + crop[2]))]
            s = 480 / max(fr.shape[:2])
            khung.append(mat_trong_anh(cv2.resize(fr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)))
        cap.release()
        kq = chon_mat(khung)
    except Exception:
        kq = None
    _NHO[key] = kq
    return kq
