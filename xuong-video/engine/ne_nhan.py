"""NÉ NHÃN CHAI: biết chai nằm đâu trên màn hình (AI soát đánh dấu khung quanh chai ở từng cảnh) → dời khối chữ / mũi tên
giỏ hàng sang chỗ trống. Editor cao cấp: chữ đặt vào khoảng trống, KHÔNG BAO GIỜ che sản phẩm."""
W, H, FPS = 1080, 1920, 30
RECT = {"khung_mo": (82, 200, 900, 1350), "khung_nho": (160, 260, 760, 1140), "chia_doi": (32, 170, 1000, 740),
        "chia_ngang": (24, 330, 508, 1080), "luoi_4": (36, 170, 490, 720)}
CAO = {"checklist": 380, "so_sanh": 360, "bang_qua": 430, "so_dem": 200, "hop_qua": 230, "nut_gio_hang": 170, "the_qua": 230,
       "canh_bao": 170, "dai_chay": 130, "hook_tung_tu": 300}
VUNG_PHU_DE = (1380, 1600)


def hop_man_hinh(d):
    """Khung chai (tỉ lệ 0–1 trong cảnh) → toạ độ trên khung 1080×1920 theo bố cục đoạn đó."""
    n = d.get("nhan")
    if not n or len(n) != 4:
        return None
    x0, y0, x1, y1 = [float(v) for v in n]
    L, o = d.get("bo_cuc") or "day", d.get("opt") or {}
    if L in ("day", "pip_troi", "pip_giua"):
        b = (x0 * W, y0 * H, x1 * W, y1 * H); pad = 0.06
    elif L == "day_zoom":
        z = float(o.get("z", 1.35)); ox = float(o.get("ox", 0.5)) + 0.03; oy = float(o.get("oy", 0.5))
        cx, cy = (W * z - W) * ox, (H * z - H) * oy
        b = (x0 * W * z - cx, y0 * H * z - cy, x1 * W * z - cx, y1 * H * z - cy); pad = 0.05
    elif L in RECT:
        rx, ry, rw, rh = RECT[L]
        sc = max(rw / W, rh / H); sw, sh = W * sc, H * sc
        dx, dy = (sw - rw) / 2, (sh - rh) / 2
        b = (rx + x0 * sw - dx, ry + y0 * sh - dy, rx + x1 * sw - dx, ry + y1 * sh - dy)
        b = (max(b[0], rx), max(b[1], ry), min(b[2], rx + rw), min(b[3], ry + rh)); pad = 0.03
    else:
        return None
    w, h = b[2] - b[0], b[3] - b[1]
    return (b[0] - w * pad, b[1] - h * pad, b[2] + w * pad, b[3] + h * pad)


def _chong(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def hop_trong(doan, t0, t1):
    return [h for d in doan if d["t1"] > t0 and d["t0"] < t1 for h in [hop_man_hinh(d)] if h]


def dat_khoi(blocks, doan):
    """Gán b['top'] cho khối nằm trong Zone (câu mở, khối giữa, chốt) để không đè chai. Trả số khối đã dời."""
    doi = 0
    for b in blocks or []:
        hops = hop_trong(doan, b["f0"] / FPS, b["f1"] / FPS)
        if not hops:
            continue
        cao = CAO.get(b["loai"], 260)
        mac_dinh = 250
        ung = [mac_dinh, 140, 1060, 860, 560]
        def diem(top):
            khung = (60, top, 940, top + cao)
            phat = sum(_chong(khung, h) for h in hops) / (880 * cao)
            if top + cao > VUNG_PHU_DE[0]:
                phat += 1        # không đè phụ đề
            return phat + (0 if top == mac_dinh else 0.04)     # ưu tiên vị trí quen
        tot = min(ung, key=diem)
        if tot != mac_dinh:
            b["top"] = tot; doi += 1
    return doi


def dat_mui_ten(cta_f0, dur_f, doan):
    hops = hop_trong(doan, cta_f0 / FPS, dur_f / FPS)
    if not hops:
        return None
    ung = (1250, 1130, 1010, 890, 770, 650)          # luôn trên dòng phụ đề (≥ 1380)
    phat = lambda top: sum(_chong((40, top, 520, top + 110), h) for h in hops) / (480 * 110)
    for top in ung:
        if phat(top) < 0.08:
            return top
    tot = min(ung, key=phat)
    return tot if phat(tot) < 0.3 else -999   # chai chiếm chỗ mũi tên ở mọi vị trí → bỏ mũi tên (khối chốt đã có nút giỏ hàng)
