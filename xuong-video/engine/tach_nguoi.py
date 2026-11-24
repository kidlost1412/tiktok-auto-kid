"""TÁCH NGƯỜI NHANH bằng mô hình PP-HumanSeg (models/human_segmentation_pphumanseg_2023mar.onnx, OpenCV Zoo, Apache-2.0) – 16/11/2026.
Nhanh hơn GrabCut (matte.py) nhiều lần, không cần vẽ đa giác mồi. Dùng cho CHỮ / THẺ NẰM SAU ĐẦU người nói.
  python engine/tach_nguoi.py base.mp4 outdir --t0 9.3 --t1 11.2 [--feather 2] [--smooth 0.55]   ·   trong code: tach(src, outdir, t0, t1)
Ra chuỗi PNG RGBA cỡ khung (frame_000001.png…): phủ LÊN TRÊN lớp chữ khổng lồ → chữ nằm SAU người.
23/11: chép từ bộ kol-vip2 (tools/humanmatte.py, bản v10 Kid duyệt) cho khung dựng "chữ theo lời". Mô hình 6 MB ở mau/mo-hinh (Apache-2.0).
Có 3 lượt: cả khung → vùng quanh người → vùng ĐẦU–VAI độ phân giải cao (viền quanh đầu sắc nhất, vì chữ/thẻ nằm quanh đầu)."""
import argparse, subprocess
from pathlib import Path
import cv2, numpy as np
import onnxruntime as ort

MO_HINH = Path(__file__).resolve().parent.parent / "mau" / "mo-hinh" / "human_segmentation_pphumanseg_2023mar.onnx"
SIZE = 192
_SESS = None


def _sess():
    global _SESS
    if _SESS is None:
        so = ort.SessionOptions(); so.intra_op_num_threads = 4
        _SESS = ort.InferenceSession(str(MO_HINH), so, providers=["CPUExecutionProvider"])
    return _SESS


def run(rgb):
    SESS = _sess()
    x = cv2.resize(rgb, (SIZE, SIZE), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    x = ((x - 0.5) / 0.5).transpose(2, 0, 1)[None]
    o = SESS.run(None, {SESS.get_inputs()[0].name: x})[0][0]
    if not (np.allclose(o.sum(0), 1.0, atol=1e-2) and o.min() >= 0):
        e = np.exp(o - o.max(0)); o = e / e.sum(0)
    return cv2.resize(o[1], (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR)


def person(rgb):
    h, w = rgb.shape[:2]; m = run(rgb)
    ys, xs = np.where(m > 0.5)
    if len(ys):
        px, py = int(0.2 * (np.ptp(xs) + 1)) + 20, int(0.1 * (np.ptp(ys) + 1)) + 20
        x0, x1, y0, y1 = max(0, xs.min() - px), min(w, xs.max() + px + 1), max(0, ys.min() - py), min(h, ys.max() + py + 1)
        m2 = np.zeros_like(m); m2[y0:y1, x0:x1] = run(rgb[y0:y1, x0:x1]); m = np.maximum(m, m2)
        ys, xs = np.where(m > 0.5); top = ys.min(); hh = int(0.30 * (ys.max() - top + 1))
        band = m[top:top + hh] > 0.5; cols = np.where(band.any(0))[0]
        if len(cols) and hh > 24:
            p2 = int(0.4 * (np.ptp(cols) + 1)) + 16
            hx0, hx1, hy0, hy1 = max(0, cols.min() - p2), min(w, cols.max() + p2 + 1), max(0, top - int(0.3 * hh) - 10), min(h, top + hh + 10)
            m[hy0:hy1, hx0:hx1] = run(rgb[hy0:hy1, hx0:hx1])
    # 16/11: MŨ ĐEN trên nền tối (chóp mũ chỉ 30–60 %) → chữ sau đầu lộ qua mũ. Vùng ĐẦU: hạ ngưỡng 0,2 + lấp lỗ + BAO LỒI
    # (đỉnh đầu/mũ luôn lồi) → đặc 100 %.
    ys, xs = np.where(m > 0.5)
    if len(ys):
        top = ys.min(); hh = int(0.30 * (ys.max() - top + 1)); y0 = max(0, top - 40); y1 = min(h, top + hh)
        band = (m[y0:y1] > 0.2).astype(np.uint8)
        cs, _ = cv2.findContours(band, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cs:
            c = max(cs, key=cv2.contourArea); fill = np.zeros_like(band); cv2.drawContours(fill, [cv2.convexHull(c)], -1, 1, -1)
            m[y0:y1] = np.maximum(m[y0:y1], fill.astype(np.float32))
    bm = (m > 0.5).astype(np.uint8); n, lab, st, _ = cv2.connectedComponentsWithStats(bm, 8)
    if n > 2:
        big = st[1:, 4].max(); keep = np.zeros(n, bool); keep[1:] = st[1:, 4] >= 0.25 * big
        m = m * keep[lab]
    return m


def tach(src, out, t0, t1, feather=2.0, smooth=0.55):
    """Tách người từ giây t0 tới t1 của src → out/frame_000001.png… (RGBA). Trả số khung đã ghi."""
    return _chay(argparse.Namespace(src=str(src), out=str(out), t0=float(t0), t1=float(t1), feather=feather, smooth=smooth))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out"); ap.add_argument("--t0", type=float, required=True); ap.add_argument("--t1", type=float, required=True)
    ap.add_argument("--feather", type=float, default=2.0); ap.add_argument("--smooth", type=float, default=0.55, help="pha trộn mặt nạ khung trước (chống rung viền)")
    ap.add_argument("--fps", type=int, default=30)
    print(f"tách người: {_chay(ap.parse_args())} khung")


def _chay(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(a.src); fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(a.t0 * fps)))
    n = int(round((a.t1 - a.t0) * fps)); prev = None
    for i in range(n):
        ok, f = cap.read()
        if not ok: break
        m = person(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        if prev is not None: m = a.smooth * prev + (1 - a.smooth) * m
        prev = m
        al = np.clip((m - 0.5) * 6 + 0.5, 0, 1)                    # viền gọn
        if a.feather > 0: al = cv2.GaussianBlur(al, (0, 0), a.feather)
        rgba = np.dstack([f, (al * 255).astype(np.uint8)])
        cv2.imwrite(str(out / f"frame_{i + 1:06d}.png"), rgba, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        k = i + 1
    cap.release()
    return locals().get("k", 0)


if __name__ == "__main__":
    main()
