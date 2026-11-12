"""Bố cục khung hình — chống reup: cùng cảnh gốc nhưng không để nguyên khung toàn màn quá ~2,8 s.
Kiểu (theo video mẫu TC01-V15 Kid gửi):
  day       toàn màn (chỉ đoạn ngắn ≤ 2,8 s)
  pip_troi  cảnh chính toàn màn + ô cảnh phụ bo góc viền trắng đặt vào vùng trời (trái/phải), trượt vào
  khung_mo  cảnh thu nhỏ bo góc viền trắng trên nền chính nó làm mờ
  chia_doi  2 ô trên/dưới, ô 2 hiện sau
  luoi_4    lưới 2×2, 4 ô hiện lần lượt
Trả về đoạn filter FFmpeg cho từng đoạn cảnh + mốc ô xuất hiện (để gắn SFX)."""
from pathlib import Path

W, H, FPS = 1080, 1920, 30
B = 8          # viền trắng
R = 30         # bo góc
MASK_DIR = Path(__file__).resolve().parent / "_mask"

RECTS = {   # (x, y, w, h) — w,h là phần hình bên trong viền
    "khung_mo":   [(82, 200, 900, 1350)],
    "khung_nho":  [(160, 260, 760, 1140)],
    "chia_doi":   [(32, 170, 1000, 740), (32, 946, 1000, 740)],
    "chia_ngang": [(24, 330, 508, 1080), (548, 330, 508, 1080)],
    "luoi_4":     [(36, 170, 490, 720), (554, 170, 490, 720), (36, 924, 490, 720), (554, 924, 490, 720)],
    "pip_trai":   [(165, 220, 750, 600)],   # Kid 10/11: ô chèn phải ở GIỮA, đủ to (không ô nhỏ ở góc)
    "pip_phai":   [(165, 220, 750, 600)],
    "pip_giua":   [(130, 250, 820, 560)],
}
APPEAR = {"khung_mo": [0.0], "khung_nho": [0.0], "chia_doi": [0.0, 0.35], "chia_ngang": [0.0, 0.35], "luoi_4": [0.0, 0.3, 0.6, 0.9],
          "pip_trai": [0.25], "pip_phai": [0.25], "pip_giua": [0.25]}
SO_PHU = {"day": 0, "day_zoom": 0, "khung_mo": 0, "khung_nho": 0, "pip_troi": 1, "pip_giua": 1, "chia_doi": 1, "chia_ngang": 1, "luoi_4": 3}
# Kid 10/11: "không hẳn phải 4 khung, 1 khung 2 khung cũng được, đa dạng để tránh trùng" → lưới 4 chỉ là kiểu hiếm
TRONG_SO = {"day": 0.26, "day_zoom": 0.12, "pip_troi": 0.15, "pip_giua": 0.08, "khung_mo": 0.13, "khung_nho": 0.08,
            "chia_doi": 0.09, "chia_ngang": 0.07, "luoi_4": 0.04}
NEN_RO = {"day", "day_zoom", "pip_troi", "pip_giua"}      # kiểu giữ cảnh chính toàn màn làm nền


def tuy_chon(rng):
    """Biến thể nhỏ mỗi đoạn: bên đặt ô, màu viền, vùng cắt khi phóng."""
    return {"side": rng.choice(["trai", "phai"]),
            "vien": rng.choices(["white", "0xFFD400", "0x2E9E44"], weights=[0.7, 0.15, 0.15])[0],
            "ox": round(rng.uniform(0.15, 0.85), 2), "oy": round(rng.uniform(0.2, 0.7), 2), "z": rng.choice([1.25, 1.35, 1.45])}


def _key(L, opt):
    return {"pip_troi": "pip_" + opt["side"]}.get(L, L)


def la_chai(shot):
    """Cảnh chai/sản phẩm cận: theo vai trò HOẶC theo khung chai AI soát đánh dấu (chai cao ≥ 30% khung hoặc chiếm ≥ 12% diện tích)."""
    if set(shot.get("vai_tro", [])) & {"chai_ro", "chai_mo", "nhan_can", "kho_hang"}:
        return True
    n = (shot.get("soat") or {}).get("nhan")
    if n and len(n) == 4:
        w, h = float(n[2]) - float(n[0]), float(n[3]) - float(n[1])
        return h >= 0.30 or w * h >= 0.12
    return False


def mask(w, h):
    """Mặt nạ bo góc (gồm cả viền) — tạo 1 lần, lưu lại."""
    MASK_DIR.mkdir(exist_ok=True)
    f = MASK_DIR / f"m{w}x{h}.png"
    if not f.exists():
        from PIL import Image, ImageDraw
        im = Image.new("L", (w + 2 * B, h + 2 * B), 0)
        ImageDraw.Draw(im).rounded_rectangle([0, 0, w + 2 * B - 1, h + 2 * B - 1], radius=R, fill=255)
        im.save(f)
    return f


def chon_bo_cuc(segs, rng, nhip="vua"):
    """Gán kiểu bố cục cho từng đoạn. Luật: khung toàn màn nguyên gốc > 2,8 s bắt buộc đổi kiểu; không lặp kiểu liền nhau;
    lưới 4 tối đa 1 lần; cả video không dùng 1 kiểu quá 3 lần."""
    out, prev, dem = [], None, {}
    for k, sg in enumerate(segs):
        d = sg["dur"]
        opts = dict(TRONG_SO)
        if nhip == "nhanh":
            opts["day"] += 0.08
        if d > 2.8:
            opts.pop("day")
        if d < 1.5:
            opts.pop("chia_doi", None); opts.pop("chia_ngang", None)
        if la_chai(sg["shot"]):   # cảnh chai cận: ô trên trời sẽ che nắp/logo
            opts.pop("pip_troi", None); opts.pop("pip_giua", None)
        if d < 2.2 or dem.get("luoi_4") or k == 0:
            opts.pop("luoi_4", None)
        for kk in list(opts):
            if (kk == prev and kk != "day") or dem.get(kk, 0) >= 3:
                opts.pop(kk)
        if k == len(segs) - 1:   # đoạn chốt có bảng quà/nút giỏ hàng → bố cục gọn để chữ chốt dễ đọc
            opts = {kk: v for kk, v in opts.items() if kk in ("day", "day_zoom", "khung_mo")} or {"day_zoom": 1}
        if k == 0:            # câu mở: ưu tiên rõ ràng
            opts = {kk: v for kk, v in opts.items() if kk in ("day", "day_zoom", "khung_mo", "pip_troi")} or {"khung_mo": 1}
        opts = opts or {"khung_nho": 1}
        keys = list(opts); L = rng.choices(keys, weights=[opts[x] for x in keys])[0]
        dem[L] = dem.get(L, 0) + 1
        out.append(L); prev = L
    return out


def chon_phu(sg, n, shots, rng, used):
    """Chọn n cảnh phụ khác file cảnh chính, ưu tiên cảnh vườn/phun/pha để ô phụ có nội dung khác."""
    sx = lambda s: s.get("soat") or {}
    ok = [s for s in shots if "nguoi_noi" not in s["vai_tro"] and s["file"] != sg["shot"]["file"]
          and not (sx(s).get("chu") or sx(s).get("hang_khac") or (sx(s).get("dep") or 3) <= 1)]   # AI đã soát: bỏ chữ chèn, hàng khác, xấu
    hay = [s for s in ok if set(s["vai_tro"]) & {"phun", "pha_rot", "cong_viec", "van_de", "vuon"}]
    if la_chai(sg["shot"]):   # cảnh chính là chai → ô phụ phải là cảnh vườn/phun, không chai chồng chai
        hay = [s for s in hay if not la_chai(s)]
        ok = hay or ok
    out = []
    for _ in range(n):
        pool = [s for s in (hay if rng.random() < 0.6 and hay else ok) if (s["file"], int(s["tu"])) not in used] or ok
        s = rng.choice(pool)
        used.add((s["file"], int(s["tu"])))
        slack = max(0.0, s["dai"] - sg["dur"] - 0.3)
        out.append({"shot": s, "src_start": round(s["tu"] + 0.3 * (s["tu"] < 0.3) + rng.uniform(0, slack), 2)})
    return out


def _pre(shot):
    cr = shot.get("crop")
    return f"crop=iw*{cr[2]}:ih*{cr[3]}:iw*{cr[0]}:ih*{cr[1]}," if cr else ""


def loc(i, L, d, main_idx, phu_idx, mask_idx, grade, motion, opt, shot, phu_shots):
    """Đoạn filter cho đoạn cảnh i → nhãn [v{i}]. mask_idx: chỉ số input mặt nạ theo thứ tự ô. Trả (filters, mốc ô hiện)."""
    base = f"setsar=1,fps={FPS},tpad=stop_mode=clone:stop_duration=4"
    tail = f"trim=duration={d:.3f},setpts=PTS-STARTPTS"
    cham = f"setpts={float(opt['cham']):.3f}*PTS," if opt.get("cham") else ""   # cảnh ngắn hơn câu → quay chậm trong phạm vi cảnh
    full = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},{base},"
            f"{motion},{grade},unsharp=5:5:0.6,{tail}")
    if L == "day":
        return [f"[{main_idx}:v]{_pre(shot)}{cham}{full},format=yuv420p[v{i}]"], []
    if L == "day_zoom":   # phóng cắt 1 vùng (đổi hẳn khung gốc) + trôi nhẹ
        zw = int(W * opt["z"]) // 2 * 2; zh = int(H * opt["z"]) // 2 * 2
        return [f"[{main_idx}:v]{_pre(shot)}{cham}scale={zw}:{zh}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}:x='(iw-{W})*({opt['ox']}+0.06*t/{d:.3f})':"
                f"y='(ih-{H})*{opt['oy']}',setsar=1,fps={FPS},tpad=stop_mode=clone:stop_duration=4,{grade},unsharp=5:5:0.6,{tail},"
                f"format=yuv420p[v{i}]"], []
    fc = []
    key = _key(L, opt)
    if L in NEN_RO:
        fc.append(f"[{main_idx}:v]{_pre(shot)}{cham}{full}[b{i}]")
        srcs = [f"[{phu_idx[0]}:v]{_pre(phu_shots[0])}{base},{tail}[s{i}_0]"]
        fc += srcs
    else:
        fc.append(f"[{main_idx}:v]{_pre(shot)}{cham}{base},{tail},split=2[m{i}a][m{i}b]")
        fc.append(f"[m{i}a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},{grade},boxblur=28:2,"
                  f"eq=brightness=-0.12:saturation=0.85[b{i}]")
        fc.append(f"[m{i}b]null[s{i}_0]")
        for k, pi in enumerate(phu_idx):
            fc.append(f"[{pi}:v]{_pre(phu_shots[k])}{base},{tail}[s{i}_{k+1}]")
    cur, times = f"b{i}", []
    for k, ((x, y, w, h), ta) in enumerate(zip(RECTS[key], APPEAR[key])):
        fc.append(f"[s{i}_{k}]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},{grade},unsharp=5:5:0.5,"
                  f"pad={w + 2 * B}:{h + 2 * B}:{B}:{B}:color={opt['vien']},format=yuva420p[p{i}_{k}]")
        fc.append(f"[{mask_idx[k]}:v]format=gray,{tail}[mk{i}_{k}]")
        fc.append(f"[p{i}_{k}][mk{i}_{k}]alphamerge" + (f",fade=t=in:st={ta}:d=0.18:alpha=1" if ta > 0 else "") + f"[q{i}_{k}]")
        yy = f"{y - B}+70*max(0\\,min(1\\,({ta}+0.22-t)/0.22))" if ta > 0 else f"{y - B}"
        nxt = f"o{i}_{k}"
        fc.append(f"[{cur}][q{i}_{k}]overlay=x={x - B}:y='{yy}':eval=frame[{nxt}]")
        cur = nxt
        if ta > 0:
            times.append(ta)
    fc.append(f"[{cur}]format=yuv420p[v{i}]")
    return fc, times


def mask_sizes(L, opt):
    return [] if L in ("day", "day_zoom") else [(w, h) for (_, _, w, h) in RECTS[_key(L, opt)]]
