"""CHUYỂN CẢNH MẠNH tại nhát cắt CÓ SẴN của video quay (15/11/2026, chủ kênh: "thêm hiệu ứng chuyển cảnh mạnh kịch tính giữa 2 nhân vật").
Làm trực tiếp trên hình quay quanh mỗi nhát cắt (±5 khung), 3 kiểu:
  whip  – lia ngang: cảnh cũ vụt đi, cảnh mới lao vào theo hướng dir (±1), nhòe chuyển động ngang + chớp sáng ở nhát cắt
  zoom  – phóng nhòe tỏa từ tâm (trung bình nhiều lớp phóng) + chớp trắng
  glitch– tách kênh màu RGB + xé dải ngang lệch + chớp
  16/11 thêm (mẫu Chanh Neon + mẫu web Pinterest 2): blur (nhòe gaussian + phóng nhẹ) · stripes (sọc dọc trắng mảnh dâng lên trắng xóa,
  cắt ở đỉnh) · warp (méo sóng gợn nước + tối nhẹ) · flash (lóe trắng có vệt sáng chéo) · spin (xoay nhòe quanh tâm) · vwhip (lia dọc)
  17/11 thêm (mẫu Pinterest 885379608014812731): burst (quầng sáng MÀU bung từ tâm → ngập gần trắng → lộ cảnh sau, có vòng sáng cong quét;
  màu --tint R,G,B, mặc định vàng ấm) · rblur (cú đấm zoom nhòe hướng tâm: cảnh trước phóng to nhòe tỏa, cảnh sau từ phóng to nhòe lắng về nét,
  không chớp trắng) · slices (khung cuối của cảnh trước chia 6 dải dọc trượt so le lên/xuống để lộ cảnh sau – chạy SAU nhát cắt, nên span 8–10)
  Mỗi mục: "giây:kiểu[:hướng[:số khung span]]"
  python engine/chuyen_canh_manh.py base.mp4 out.mp4 --cuts "2.7:whip:-1,5.167:glitch,11.267:zoom" [--span 5]
  Trong code: ap(src, out, [(2.7, "whip", -1), (5.167, "glitch")], span=5)
23/11: chép từ bộ kol-vip2 (tools/cutfx.py, bản v10 Kid duyệt) cho khung dựng "chữ theo lời". Chỉ cần OpenCV + numpy + ffmpeg (đều có trong bộ cài).
v10 dùng: whip, flash, glitch, zoom (6 nhát/21 s, chỉ ở chỗ đổi ý)."""
import argparse, subprocess
import cv2
import numpy as np


KIEU = ("whip", "vwhip", "zoom", "glitch", "flash", "blur", "stripes", "warp", "spin", "burst", "rblur", "slices", "bloom", "ripple")


def ap(src, out, cuts, span=5, tint="255,200,40"):
    """cuts: [(giây, kiểu[, hướng ±1[, số khung span]])] — hiệu ứng chạy ±span khung quanh nhát cắt có sẵn trong src."""
    a = argparse.Namespace(src=str(src), out=str(out), span=span, tint=tint)
    _chay(a, [(float(c[0]), c[1], float(c[2]) if len(c) > 2 else 1.0, (int(c[3]) if len(c) > 3 else span) / 30.0) for c in cuts])


def main():
    p_ = argparse.ArgumentParser()
    p_.add_argument("src"); p_.add_argument("out"); p_.add_argument("--cuts", required=True); p_.add_argument("--span", type=int, default=5)
    p_.add_argument("--tint", default="255,200,40", help="màu R,G,B của kiểu burst")
    a = p_.parse_args()
    cuts = []
    for c in a.cuts.split(","):
        p = c.split(":"); cuts.append((float(p[0]), p[1], float(p[2]) if len(p) > 2 and p[2] else 1.0, (int(p[3]) if len(p) > 3 else a.span) / 30.0))
    _chay(a, cuts)


def _chay(a, cuts):
    cap = cv2.VideoCapture(a.src); fps = cap.get(cv2.CAP_PROP_FPS); W, H = int(cap.get(3)), int(cap.get(4))
    span = a.span / fps; rng = np.random.default_rng(15)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    TINT = np.float32([float(v) for v in a.tint.split(",")][::-1])            # BGR
    bcx, bcy = W / 2, H * 0.44; brr = np.sqrt(((xx - bcx) / (W * 0.5)) ** 2 + ((yy - bcy) / (W * 0.5)) ** 2); bth = np.arctan2(yy - bcy, xx - bcx)
    hold = {}                                                                 # slices: khung cuối của cảnh trước nhát cắt
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                          "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", a.out], stdin=subprocess.PIPE)
    i = 0
    while True:
        ok, f = cap.read()
        if not ok: break
        t = (i + 0.5) / fps
        act = [(c, st, dr, sp) for c, st, dr, sp in cuts if abs(t - c) <= sp]
        if act:
            c, st, dr, span = act[0]; d = (t - c) / span; e = 1 - abs(d)            # e: 0 → 1 (ngay nhát cắt) → 0
            fl = 0
            if st == "burst":       # 17/11: quầng sáng MÀU bung từ tâm → ngập gần trắng → lộ cảnh sau; vòng sáng cong quét qua
                ff = f.astype(np.float32); u = (d + 1) / 2                  # 0 → 1 suốt chuyển cảnh
                glow = np.exp(-(brr / (0.22 + 2.4 * e ** 1.5)) ** 2)        # quầng to dần tới kín khung
                I = np.clip(1.15 * e ** 0.8 * glow + 0.9 * e ** 4, 0, 1)[:, :, None]
                wh = np.clip(e ** 2.2 * (0.35 + 0.65 * glow), 0, 1)[:, :, None]         # lõi trắng dần ở đỉnh
                col = TINT * (1 - wh) + 255.0 * wh
                lum = ff.mean(2, keepdims=True) / 255.0
                o = ff * (1 - I) + (col * (0.55 + 0.45 * lum)) * I              # nhuộm màu còn thấy dáng hình bên dưới, rồi ngập sáng
                ring = np.exp(-((brr - (0.25 + 1.5 * u)) / (0.035 + 0.05 * u)) ** 2) * (0.5 + 0.5 * np.cos(bth - 1.2 - 5.0 * u * dr)) ** 2
                o = o + (255.0 - o) * np.clip(1.1 * ring * min(1.0, 2.2 * e), 0, 1)[:, :, None]
                sc = 1 + 0.07 * e; M = cv2.getRotationMatrix2D((bcx, bcy), 0, sc)
                f = cv2.warpAffine(np.clip(o, 0, 255).astype(np.uint8), M, (W, H), borderMode=cv2.BORDER_REFLECT)
            elif st == "rblur":     # 17/11: cú đấm zoom nhòe hướng tâm – trước nhát cắt phóng to dần + nhòe tỏa, sau nhát cắt từ phóng to nhòe lắng về nét
                n = 9; acc = np.zeros_like(f, np.float32); base = 1 + 0.62 * e ** 2.2; wsum = 0
                for j in range(n):
                    s_ = base * (1 + 0.26 * e * (j / (n - 1))); wj = 1.0 - 0.5 * j / (n - 1)
                    M = cv2.getRotationMatrix2D((W / 2, H * 0.40), 0, s_); acc += wj * cv2.warpAffine(f, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT); wsum += wj
                f = (acc / wsum).astype(np.uint8)
                if e > 0.15: f = cv2.GaussianBlur(f, (0, 0), 7 * e ** 1.5)
            elif st == "slices":    # 17/11: 6 dải dọc của KHUNG CUỐI cảnh trước trượt so le lên/xuống, lộ cảnh sau (đang chạy) bên dưới
                if d < 0:
                    hold[c] = f.copy(); g = int(round(10 * e ** 3))            # lấy đà: khe tối mảnh hé giữa các dải
                    if g > 0:
                        f = f.copy()
                        for j in range(1, 6): xj = int(round(j * W / 6)); f[:, max(0, xj - g // 2):xj + (g + 1) // 2] = (f[:, max(0, xj - g // 2):xj + (g + 1) // 2] * 0.25).astype(np.uint8)
                elif c in hold:
                    old = hold[c]; o = f.copy(); n = 6
                    for j in range(n):
                        q = np.clip((d - 0.07 * j) / (1 - 0.07 * (n - 1)), 0, 1); q = q * q * (3 - 2 * q); q = q * q   # so le từng dải, vào êm – ra nhanh
                        off = int(round(q * (H + 40))) * (1 if (j % 2 == 0) == (dr > 0) else -1)
                        x0, x1 = int(round(j * W / n)), int(round((j + 1) * W / n))
                        if abs(off) >= H: continue
                        strip = old[:, x0:x1]
                        if 0 < q < 1: kb = 1 + 2 * int(18 * np.sin(np.pi * q)); strip = cv2.blur(strip, (1, kb))
                        if off >= 0: o[off:, x0:x1] = strip[:H - off]
                        else: o[:H + off, x0:x1] = strip[-off:]
                        if 0 < q < 1:                                           # viền tối mảnh 2 bên dải đang trượt
                            ya, yb = (off, H) if off >= 0 else (0, H + off)
                            o[ya:yb, x0:x0 + 3] = (o[ya:yb, x0:x0 + 3] * 0.45).astype(np.uint8); o[ya:yb, x1 - 3:x1] = (o[ya:yb, x1 - 3:x1] * 0.45).astype(np.uint8)
                    f = o
                    if d > 0.97: hold.pop(c, None)
            elif st == "bloom":       # 16/11 hook kiểu Quạ HD: LÓE SÁNG trắng + nhòe + phóng nhẹ ngay nhát nhảy cảnh, tan trong ~4 khung
                g = cv2.GaussianBlur(f, (0, 0), 2 + 16 * e).astype(np.float32); ff = f.astype(np.float32)
                o = ff * (1 - 0.85 * e) + g * 0.85 * e; o = o + (255 - o) * 0.6 * e ** 1.5
                sc = 1 + 0.10 * e; M = cv2.getRotationMatrix2D((W / 2, H * 0.4), 0, sc)
                f = cv2.warpAffine(np.clip(o, 0, 255).astype(np.uint8), M, (W, H), borderMode=cv2.BORDER_REFLECT)
            elif st == "ripple":      # 16/11 hook: hình NHẢY VÀO + GỢN SÓNG tròn lan từ tâm, tắt dần mượt
                cx, cy = W / 2, H * 0.42; dxp, dyp = xx - cx, yy - cy; r = np.sqrt(dxp * dxp + dyp * dyp) + 1e-3
                ph = (1 - e) * 22.0; amp = 11 * e ** 2       # 16/11: giảm (34 → 11) – lần đầu méo mặt
                k = amp * np.sin(r / 70.0 - ph) * np.exp(-r / 1600.0)
                sc = 1 + 0.10 * e ** 2
                mx = cx + dxp / sc + dxp / r * k; my = cy + dyp / sc + dyp / r * k
                f = cv2.remap(f, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                fl = 0.25 * e ** 6
            elif st == "blur":
                k = 1 + 2 * int(e * 22); f = cv2.GaussianBlur(f, (k, k), 0)
                sc = 1 + 0.08 * e; M = cv2.getRotationMatrix2D((W / 2, H * 0.45), 0, sc); f = cv2.warpAffine(f, M, (W, H), borderMode=cv2.BORDER_REFLECT)
            elif st == "stripes":
                wash = e ** 1.4; pat = ((xx.astype(np.int32) % 14) < 4).astype(np.float32)[:, :, None]
                f = f.astype(np.float32); f = f * (1 - 0.85 * wash) + 255 * 0.85 * wash
                f = np.clip(f + pat * 120 * min(1, e * 1.6) * (1 - 0.6 * wash), 0, 255).astype(np.uint8)
            elif st == "warp":
                amp = 26 * e; mx = xx + amp * np.sin(yy / 38.0 + t * 30); my = yy + 0.4 * amp * np.cos(xx / 52.0 + t * 24)
                f = cv2.remap(f, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                f = cv2.addWeighted(f, 1 - 0.35 * e, np.zeros_like(f), 0.35 * e, 0)
            elif st == "flash":
                g = cv2.GaussianBlur(f, (0, 0), 1 + 10 * e); streak = np.clip(1 - np.abs((xx * 0.6 + yy * 0.8 - (W + H) * 0.5 * (0.6 + 0.8 * (d + 1) / 2) )) / 260, 0, 1)[:, :, None]
                f = np.clip(g.astype(np.float32) * (1 - 0.9 * e ** 2) + 255 * 0.9 * e ** 2 + 120 * streak * e, 0, 255).astype(np.uint8)
            elif st == "spin":
                acc = np.zeros_like(f, np.float32); n = 6
                for j in range(n):
                    M = cv2.getRotationMatrix2D((W / 2, H / 2), dr * 14 * e * (j / (n - 1)), 1 + 0.25 * e); acc += cv2.warpAffine(f, M, (W, H), borderMode=cv2.BORDER_REFLECT)
                f = (acc / n).astype(np.uint8); fl = 0.3 * e ** 4
            elif st == "vwhip":
                off = dr * e * e * 0.3 * H * (1 if d < 0 else -1); sc = 1 + 0.3 * e
                M = np.float32([[sc, 0, W / 2 * (1 - sc)], [0, sc, off + H / 2 * (1 - sc)]]); f = cv2.warpAffine(f, M, (W, H), borderMode=cv2.BORDER_REFLECT)
                k = max(1, int(e * 240)); f = cv2.blur(f, (1, k)); fl = 0.45 * e ** 4
            elif st == "whip":
                off = dr * e * e * 0.28 * W * (1 if d < 0 else -1)          # cũ vụt đi theo dir, mới lao vào từ phía ngược lại
                sc = 1 + 0.3 * e                                              # phóng để mép lật gương không lọt vào khung
                M = np.float32([[sc, 0, off + W / 2 * (1 - sc)], [0, sc, H / 2 * (1 - sc)]]); f = cv2.warpAffine(f, M, (W, H), borderMode=cv2.BORDER_REFLECT)
                k = max(1, int(e * 240)); f = cv2.blur(f, (k, 1))
                fl = 0.55 * e ** 4
            elif st == "zoom":
                acc = np.zeros_like(f, np.float32); n = 6
                for j in range(n):
                    s = 1 + 0.32 * e * (j / (n - 1)) + 0.12 * e
                    M = cv2.getRotationMatrix2D((W / 2, H * 0.42), 0, s); acc += cv2.warpAffine(f, M, (W, H), borderMode=cv2.BORDER_REFLECT)
                f = (acc / n).astype(np.uint8); fl = 0.6 * e ** 3
            else:   # glitch
                sh = int(e * 38); b, g, r = cv2.split(f)
                r = np.roll(r, sh, axis=1); b = np.roll(b, -sh, axis=1); f = cv2.merge([b, g, r])
                for _ in range(int(3 + 9 * e)):
                    y0 = int(rng.uniform(0, H - 40)); h = int(rng.uniform(12, 90)); dx = int(rng.uniform(-1, 1) * 110 * e)
                    f[y0:y0 + h] = np.roll(f[y0:y0 + h], dx, axis=1)
                fl = 0.4 * e ** 5
            if fl > 0.01: f = cv2.addWeighted(f, 1 - fl, np.full_like(f, 255), fl, 0)
        p.stdin.write(f.tobytes()); i += 1
    p.stdin.close(); p.wait(); cap.release()
    if p.returncode:
        raise RuntimeError(f"chuyen_canh_manh: ffmpeg lỗi {p.returncode}")


if __name__ == "__main__":
    main()
