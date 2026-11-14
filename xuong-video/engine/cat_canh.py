"""MÁY TỰ CẮT CẢNH (không AI): đo khung hình bằng OpenCV → vết cắt thật, đoạn đẹp nhất (nét, ít rung), chuyển động máy.
Cùng một video luôn cho cùng kết quả. Chỉ đọc video, không sửa file gốc.
cat(path) → {"dai": s, "vet_cat": [...], "canh": [{"tu","den","giua","chuyen_dong": "em"|"rung","net","rung","cu_may"}]}
to_anh(ds, out) → ghép ảnh giữa đoạn thành tờ có số để AI điền phiếu."""
import math
from pathlib import Path

import cv2
import numpy as np

MAU_MOI_GIAY = 6          # số mẫu đo mỗi giây
NGUONG_CAT = 0.40         # khác biệt màu giữa 2 mẫu liền nhau → vết cắt
DAI_DOAN = 4.0            # độ dài đoạn lấy ra (giây)
DAI_TOI_THIEU = 2.0
KHAC_HINH = 0.30          # 2 đoạn trong cùng cú máy phải khác hình cỡ này mới lấy cả hai
TOI_DA_MOI_CU = 4
W, H = 160, 284


def _mo(path):
    p = str(Path(path).resolve())
    cap = cv2.VideoCapture(p)
    if not cap.isOpened() and len(p) > 240:                 # đường dẫn dài trên Windows
        cap = cv2.VideoCapture("\\\\?\\" + p)
    return cap


def do(path):
    """→ (dài, [t], [hist], [nét], [(dx, dy)]) lấy mẫu MAU_MOI_GIAY lần/giây."""
    cap = _mo(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if not (5 <= fps <= 240):
        fps = 30.0
    buoc = max(1, int(round(fps / MAU_MOI_GIAY)))
    han = cv2.createHanningWindow((W, H), cv2.CV_32F)
    t, hs, net, dich = [], [], [], []
    truoc = None
    i = 0
    while True:
        if not cap.grab():
            break
        if i % buoc == 0:
            ok, fr = cap.retrieve()
            if not ok:
                break
            s = cv2.resize(fr, (W, H), interpolation=cv2.INTER_AREA)
            g = cv2.cvtColor(s, cv2.COLOR_BGR2GRAY)
            h = cv2.calcHist([cv2.cvtColor(s, cv2.COLOR_BGR2HSV)], [0, 1], None, [16, 8], [0, 180, 0, 256])
            cv2.normalize(h, h, 1.0, 0.0, cv2.NORM_L1)
            g32 = g.astype(np.float32)
            if truoc is None:
                dich.append((0.0, 0.0))
            else:
                (dx, dy), r = cv2.phaseCorrelate(truoc, g32, han)
                dich.append((float(dx), float(dy)) if r >= 0.08 and abs(dx) < 40 and abs(dy) < 40 else None)   # None = không đo được (lá động, đổi cảnh)
            truoc = g32
            net.append(float(cv2.Laplacian(g, cv2.CV_64F).var()))
            hs.append(h); t.append(i / fps)
        i += 1
    cap.release()
    return i / fps, t, hs, net, dich


def _khac(a, b):
    return float(cv2.compareHist(a, b, cv2.HISTCMP_BHATTACHARYYA))


def _chuyen_dong(dich):
    """Đo chuyển động máy trong 1 đoạn từ các độ dịch (px trên khung rộng 160) → ("em" | "rung", độ rung).
    "rung" khi quá nửa độ dịch không đo được (hình loạn) hoặc độ giật giữa 2 mẫu liền nhau cao; còn lại "em". Chỉ để chọn đoạn êm nhất, KHÔNG gửi cho AI."""
    tong = len(dich)
    dich = [d for d in dich if d is not None]
    if tong and len(dich) < 0.5 * tong:                     # quá nửa không đo được → hình loạn/rung mạnh
        return "rung", 9.0
    if len(dich) < 2:
        return "em", 0.0
    dx = np.array([d[0] for d in dich]); dy = np.array([d[1] for d in dich])
    rung = float(np.hypot(np.diff(dx), np.diff(dy)).mean())
    return ("rung" if rung > 1.6 else "em"), rung


def cat(path):
    dai, t, hs, net, dich = do(path)
    n = len(t)
    if n < MAU_MOI_GIAY * DAI_TOI_THIEU:
        return {"dai": round(dai, 2), "vet_cat": [], "canh": []}
    vet = []
    for i in range(1, n):
        if _khac(hs[i - 1], hs[i]) > NGUONG_CAT and (not vet or t[i] - vet[-1] > 0.5):
            vet.append(t[i])
    moc = [0.0] + vet + [dai]
    net_chuan = float(np.percentile(net, 90)) or 1.0
    L = int(round(DAI_DOAN * MAU_MOI_GIAY))
    ra = []
    for a, b in zip(moc, moc[1:]):
        a2, b2 = a + (0.2 if a > 0 else 0.0), b - 0.2          # tránh dính khung chuyển cảnh
        ia = next((i for i in range(n) if t[i] >= a2), n)
        ib = max((i for i in range(n) if t[i] <= b2), default=-1)
        so = ib - ia + 1
        if so < DAI_TOI_THIEU * MAU_MOI_GIAY:
            continue
        l = min(L, so)
        ung = []
        for s in range(ia, ib - l + 2, max(1, MAU_MOI_GIAY // 2)):
            e = s + l
            kieu, rung = _chuyen_dong(dich[s + 1:e])
            diem = float(np.median(net[s:e])) / net_chuan - 0.25 * rung
            ung.append((diem, s, e, kieu, rung))
        ung.sort(reverse=True)
        toi_da = min(TOI_DA_MOI_CU, max(1, math.ceil((b - a) / 8.0)))
        chon = []
        for diem, s, e, kieu, rung in ung:
            if len(chon) >= toi_da:
                break
            g = (s + e) // 2
            if any(not (e <= c["s"] or s >= c["e"]) for c in chon):
                continue
            if any(_khac(hs[g], hs[c["g"]]) < KHAC_HINH for c in chon):
                continue
            chon.append({"s": s, "e": e, "g": g, "kieu": kieu, "rung": rung, "diem": diem})
        for c in sorted(chon, key=lambda c: c["s"]):
            ra.append({"tu": round(t[c["s"]], 2), "den": round(min(t[c["e"] - 1] + 1.0 / MAU_MOI_GIAY, b2), 2), "giua": round(t[c["g"]], 2),
                       "chuyen_dong": c["kieu"], "net": round(float(np.median(net[c["s"]:c["e"]])) / net_chuan, 2), "rung": round(c["rung"], 2),
                       "cu_may": [round(a, 2), round(b, 2)]})
    return {"dai": round(dai, 2), "vet_cat": [round(v, 2) for v in vet], "canh": ra}


def khung(path, giay, rong=360, cao=640):
    cap = _mo(path)
    cap.set(cv2.CAP_PROP_POS_MSEC, giay * 1000.0)
    ok, fr = cap.read()
    cap.release()
    if not ok:
        return np.zeros((cao, rong, 3), np.uint8)
    h, w = fr.shape[:2]
    k = min(rong / w, cao / h)
    s = cv2.resize(fr, (max(1, int(w * k)), max(1, int(h * k))), interpolation=cv2.INTER_AREA)
    nen = np.zeros((cao, rong, 3), np.uint8)
    y, x = (cao - s.shape[0]) // 2, (rong - s.shape[1]) // 2
    nen[y:y + s.shape[0], x:x + s.shape[1]] = s
    return nen


def to_anh(ds, out, cot=4, hang=3, rong=360, cao=640):
    """ds: [(so, path, giay)] → các tờ ảnh <out>-1.jpg… (mỗi tờ cot×hang ô, số vàng góc trên trái). Trả danh sách file."""
    moi = cot * hang
    files = []
    for k in range(0, len(ds), moi):
        o = []
        for so, path, giay in ds[k:k + moi]:
            im = khung(path, giay, rong, cao)
            cv2.rectangle(im, (0, 0), (96, 56), (0, 0, 0), -1)
            cv2.putText(im, str(so), (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 230, 255), 4)
            cv2.rectangle(im, (0, 0), (rong - 1, cao - 1), (255, 255, 255), 2)
            o.append(im)
        while len(o) % cot:
            o.append(np.zeros((cao, rong, 3), np.uint8))
        to = np.vstack([np.hstack(o[r:r + cot]) for r in range(0, len(o), cot)])
        f = Path(f"{out}-{k // moi + 1}.jpg")
        cv2.imencode(".jpg", to, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tofile(str(f))
        files.append(f)
    return files
