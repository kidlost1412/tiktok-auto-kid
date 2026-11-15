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
    # kiểu mới (vùng an toàn TikTok: viền ngoài nằm trong y 228–1576, lề ngang ≥ 32; chừa cột nút bên phải ở phần trên)
    "chia_3":     [(40, 236, 1000, 700), (40, 968, 484, 600), (556, 968, 484, 600)],      # 1 ô to trên + 2 ô dưới
    "ba_doc":     [(38, 290, 316, 1240), (382, 290, 316, 1240), (726, 290, 316, 1240)],   # 3 dải dọc
}
APPEAR = {"khung_mo": [0.0], "khung_nho": [0.0], "chia_doi": [0.0, 0.0], "chia_ngang": [0.0, 0.0], "luoi_4": [0.0, 0.0, 0.0, 0.0],
          "pip_trai": [0.25], "pip_phai": [0.25], "pip_giua": [0.25], "chia_3": [0.0] * 3, "ba_doc": [0.0] * 3}
# Mọi ô của một kiểu nhiều ô vào CÙNG LÚC từ khung đầu của đoạn (không nền mờ trống). Chỉ ô trời (pip) hiện sau để nổi trên cảnh chính.
SO_PHU = {"day": 0, "day_zoom": 0, "khung_mo": 0, "khung_nho": 0, "pip_troi": 1, "pip_giua": 1, "chia_doi": 1, "chia_ngang": 1, "luoi_4": 3,
          "chia_3": 2, "ba_doc": 2, "lat_trang": 2}
TOI_DA_PHU = {"lat_trang": 7}       # lat_trang: cảnh chính + 2–7 cảnh phụ (tổng 3–8 cảnh); SO_PHU là mức TỐI THIỂU
LAT_MIN = 0.28                      # lát lật trang ngắn nhất (giây)
# Kid 10/11: "không hẳn phải 4 khung, 1 khung 2 khung cũng được, đa dạng để tránh trùng" → lưới 4 chỉ là kiểu hiếm
TRONG_SO = {"day": 0.26, "day_zoom": 0.12, "pip_troi": 0.15, "pip_giua": 0.08, "khung_mo": 0.13, "khung_nho": 0.08,
            "chia_doi": 0.09, "chia_ngang": 0.07, "luoi_4": 0.04}
MAY_CHON = frozenset(TRONG_SO)                            # kiểu MÁY được tự chọn khi đạo diễn không chọn (kiểu mới chỉ do đạo diễn chọn)
NEN_RO = {"day", "day_zoom", "pip_troi", "pip_giua"}      # kiểu giữ cảnh chính toàn màn làm nền
HOP_MO = {"khung_mo", "khung_nho", "chia_doi", "chia_ngang", "luoi_4", "chia_3", "ba_doc"}   # "khung trên nền mờ" = kiểu có RECTS mà KHÔNG thuộc NEN_RO (build boxblur ở loc())
TOAN = ("day", "day_zoom")                                # toàn màn thuần (không ô chèn)
NHIEU_O = {"chia_doi", "chia_ngang", "luoi_4", "chia_3", "ba_doc"}   # kiểu nhiều ô: mọi ô hiện cùng lúc, 1 "pop" cho cả kiểu
GAN_NHAT = {"luoi_4": "chia_3", "chia_3": "chia_doi", "ba_doc": "chia_ngang", "chia_doi": "khung_mo", "chia_ngang": "khung_mo",
            "pip_troi": "khung_mo", "pip_giua": "khung_mo", "lat_trang": "day_zoom"}   # thiếu cảnh phụ → kiểu gần nhất cần ít phụ hơn
TRAN_HOP_MO, SAN_TOAN, TOI_DA_LIEN = 0.45, 0.35, 2        # ≤45% đoạn khung-trên-nền-mờ, ≥35% toàn màn thuần, ≤2 đoạn liền cùng kiểu
VIEN_TEN = {"trang": "white", "vang": "0xFFD400", "xanh": "0x2E9E44"}
MO_TA = {   # kiểu → (mô tả 1 dòng cho đạo diễn, số cảnh phụ cần)
    "day": ("toàn màn nguyên cảnh; quá 2,8 s máy tự đổi khung giữa đoạn (phóng cắt) chứ không đổi kiểu", 0),
    "day_zoom": ("phóng cắt 1 vùng của cảnh, toàn màn, đổi hẳn khung gốc", 0),
    "pip_troi": ("cảnh chính toàn màn + 1 ô cảnh phụ lớn bật vào giữa phía trên (tránh khi cảnh chính là chai cận)", 1),
    "pip_giua": ("cảnh chính toàn màn + 1 ô phụ ngang lớn giữa phía trên (tránh khi cảnh chính là chai cận)", 1),
    "khung_mo": ("cảnh thu vào khung bo góc lớn, viền trắng, trên nền mờ của chính nó", 0),
    "khung_nho": ("khung bo góc nhỏ hơn trên nền mờ, chừa chỗ cho chữ", 0),
    "chia_doi": ("2 ô trên/dưới cùng vào một lúc (chính + 1 phụ), hợp so sánh trước/sau", 1),
    "chia_ngang": ("2 cột cạnh nhau cùng vào một lúc (chính + 1 phụ), hợp hai người cùng cầm chai", 1),
    "luoi_4": ("lưới 2×2 cùng vào một lúc (chính + 3 phụ), rất hiếm, chỉ 1 lần/video, đoạn ≥ 2,2 s", 3),
    "chia_3": ("1 ô to ở trên + 2 ô nhỏ cạnh nhau ở dưới, cùng vào một lúc (chính + 2 phụ), hợp nhiều nhà vườn cùng nói về sản phẩm", 2),
    "ba_doc": ("3 dải dọc cạnh nhau cùng vào một lúc (chính + 2 phụ), hợp 3 người đứng cầm chai", 2),
    "lat_trang": ("lật trang nhanh: cảnh chính + 2–7 cảnh phụ (tổng 3–8) cắt cứng liên tiếp toàn màn, mỗi lát ≥ 0,28 s; hợp chuỗi nhà vườn khen sản phẩm", 2),
}


def mo_ta_bo_cuc():
    """{kiểu: {"mo_ta": 1 dòng tiếng Việt, "phu": số cảnh phụ cần (lat_trang: tối thiểu), "phu_toi_da": số cảnh phụ tối đa}} — để dựng prompt đạo diễn."""
    return {k: {"mo_ta": m, "phu": n, "phu_toi_da": TOI_DA_PHU.get(k, n)} for k, (m, n) in MO_TA.items()}


def so_phu_toi_da(L):
    return TOI_DA_PHU.get(L, SO_PHU.get(L, 0))


def punch_an_toan(p, ax, ay, nhan, le=0.06):
    """Phóng cắt p (0.04–0.10) quanh điểm neo (ax, ay ∈ 0–1) mà KHÔNG đẩy khung nhãn chai (nhan = [x0,y0,x1,y1] 0–1) ra ngoài (chừa lề `le`).
    Không có cách nào vừa → giảm p dần, cuối cùng bỏ punch. → (p, ax, ay)."""
    try:
        x0, y0, x1, y1 = [min(1.0, max(0.0, float(v))) for v in nhan]
    except Exception:
        return p, ax, ay
    for pp in (p, p * 0.75, p * 0.5, p * 0.25):
        lx, hx = max(0.0, (x1 + le - (1 - pp)) / pp), min(1.0, (x0 - le) / pp)
        ly, hy = max(0.0, (y1 + le - (1 - pp)) / pp), min(1.0, (y0 - le) / pp)
        if lx <= hx and ly <= hy:
            return round(pp, 3), round(min(max(ax, lx), hx), 3), round(min(max(ay, ly), hy), 3)
    return 0.0, 0.5, 0.5


def tuy_chon(rng, shot=None, vien="white"):
    """Biến thể nhỏ mỗi đoạn: bên đặt ô, vùng cắt khi phóng; + biến thể chống trùng cho cảnh toàn màn
    (punch-in 4–10% neo ngẫu nhiên nhưng không cắt mất nhãn chai, đổi tốc độ 0,92–1,08, lệch màu/tương phản rất nhẹ, hướng trôi khung)."""
    o = {"side": rng.choice(["trai", "phai"]),
         "vien": VIEN_TEN.get(str(vien), vien or "white"),   # MỘT kiểu viền cho cả video (lấy từ plan), không ngẫu nhiên mỗi đoạn
         "ox": round(rng.uniform(0.15, 0.85), 2), "oy": round(rng.uniform(0.2, 0.7), 2), "z": rng.choice([1.25, 1.35, 1.45])}
    p, ax, ay = punch_an_toan(round(rng.uniform(0.04, 0.10), 3), round(rng.uniform(0, 1), 3), round(rng.uniform(0, 1), 3),
                              ((shot or {}).get("soat") or {}).get("nhan"))
    o.update(punch=p, ax=ax, ay=ay, toc_do=rng.choice([0.92, 0.96, 1.0, 1.04, 1.08]), hue=rng.choice([-2, -1, 0, 1, 2]),
             tp=round(rng.uniform(0.98, 1.03), 3), huong=rng.choice([-1, 1]), truc=rng.choice(["x", "y"]))
    return o


def nhan_hieu_dung(L, opt, nhan):
    """Khung nhãn chai (0–1 trong cảnh gốc) → khung THẬT sau punch-in / trôi khung, để ne_nhan dời chữ đúng chỗ (ne_nhan đọc doan[].nhan).
    Toàn màn/ô trời: dời theo punch; khung/ô chia: nới 4% mỗi phía cho phần trôi nhẹ. Cảnh không có nhãn → None."""
    if not nhan or len(nhan) != 4:
        return nhan
    try:
        x0, y0, x1, y1 = [float(v) for v in nhan]
    except Exception:
        return nhan
    o = opt or {}
    if L == "lat_trang":
        return None                      # mỗi lát một cảnh khác nhau: không có một khung nhãn chung
    if L in ("day", "pip_troi", "pip_giua") and (o.get("punch") or o.get("doi_khung")):
        def dich(p, ax, ay):
            f = lambda v, a: (v - a * p) / (1 - p)
            return [min(max(f(x0, ax), 0.0), 1.0), min(max(f(y0, ay), 0.0), 1.0), min(max(f(x1, ax), 0.0), 1.0), min(max(f(y1, ay), 0.0), 1.0)]
        b = dich(float(o["punch"]), float(o.get("ax", 0.5)), float(o.get("ay", 0.5))) if o.get("punch") else [x0, y0, x1, y1]
        if L == "day" and o.get("doi_khung"):       # nửa sau đoạn phóng thêm → khung nhãn là hợp của hai nửa
            b2 = dich(float(o["p2"]), float(o["ax2"]), float(o["ay2"])) if o.get("p2") else [x0, y0, x1, y1]
            b = [min(b[0], b2[0]), min(b[1], b2[1]), max(b[2], b2[2]), max(b[3], b2[3])]
        return [round(v, 3) for v in b]
    if L in HOP_MO:
        return [round(max(x0 - 0.04, 0.0), 3), round(max(y0 - 0.04, 0.0), 3), round(min(x1 + 0.04, 1.0), 3), round(min(y1 + 0.04, 1.0), 3)]
    return nhan


def dat_doi_khung(opt, nhan=None):
    """Đoạn "day" quá 2,8 s: nửa sau đổi khung (cắt cứng, phóng thêm 8–12% neo đối diện, không cắt mất nhãn) thay vì đổi sang kiểu khác."""
    p, ax, ay = punch_an_toan(0.11, 1 - float(opt.get("ax", 0.5)), 1 - float(opt.get("ay", 0.5)), nhan) if nhan else (0.11, 1 - float(opt.get("ax", 0.5)), 1 - float(opt.get("ay", 0.5)))
    if p <= 0:
        p, ax, ay = 0.05, 0.5, 0.5
    opt.update(doi_khung=True, p2=p, ax2=ax, ay2=ay)
    return opt


def _key(L, opt):
    return {"pip_troi": "pip_" + opt["side"]}.get(L, L)


def la_chai(shot):
    """Cảnh chai/sản phẩm cận: theo vai trò HOẶC theo khung chai AI soát đánh dấu (chai cao ≥ 30% khung hoặc chiếm ≥ 12% diện tích)."""
    if (shot.get("soat") or {}).get("hang_khac"):          # chai hãng khác: chỉ làm nền, không tính là chai sản phẩm
        return False
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


def _nguoi_noi(s):
    """Người có thể đang nói. CHỈ để tham khảo: máy KHÔNG còn né cảnh người nói/aff ở toàn màn (miệng lệch tiếng không quan trọng, aff là cảnh quý nhất)."""
    m = (s.get("soat") or {}).get("mat") or 0
    return m >= 2 or (m == 1 and s.get("co_canh") not in ("toan", None))


def la_dao_dien(sg):
    """Đoạn do đạo diễn chọn bố cục (có "bo_cuc" hợp lệ, không bị đánh dấu "bo_cuc_may" do máy tự gán) → máy không đổi sang kiểu khác để chạy trần/sàn."""
    return bool(sg.get("bo_cuc")) and sg.get("bo_cuc") in SO_PHU and not sg.get("bo_cuc_may")


def ep_bo_cuc(segs, layouts, rng, lay_phu=None):
    """Lượt kiểm bố cục (gọi ở dao_dien.segs_tu_bang VÀ dung.render — chạy lại không đổi gì thêm).
    ĐOẠN ĐẠO DIỄN CHỌN (sg["bo_cuc"] hợp lệ, không có sg["bo_cuc_may"]): giữ nguyên kiểu, chỉ sửa hai lỗi thật:
      (a) "day" > 2,8 s → KHÔNG đổi kiểu, đặt sg["doi_khung"]=True (dung.render cắt đổi khung phóng thêm ở giữa đoạn);
      (b) kiểu cần N cảnh phụ mà thiếu → lấy thêm qua lay_phu; vẫn thiếu → kiểu gần nhất vừa đủ (GAN_NHAT); lat_trang đoạn quá ngắn → day_zoom.
    ĐOẠN KHÔNG CÓ LỰA CHỌN ĐẠO DIỄN (máy tự gán): trần/sàn như cũ — "khung trên nền mờ" ≤ 45%, toàn màn thuần ≥ 35%, không quá 2 đoạn liền cùng kiểu,
      ô trời không trên cảnh chai, day ≤ 2,8 s, lưới 4 tối đa 1, chia ≥ 1,5 s; bù ≥ 1/3 đoạn không toàn màn, ≥ 1 chia/lưới, ≥ 1 ô trời (nếu hợp);
      câu mở/chốt không bị đổi sang chia/lưới/ô trời. Máy chỉ chọn trong MAY_CHON.
    segs: [{shot, dur, phu_shots?, ...}]; layouts: kiểu hiện tại từng đoạn (None → day_zoom). lay_phu(sg, n) → list cảnh phụ (có thể trống).
    Trả (layouts mới, ghi chú: danh sách "đoạn i: ... (lý do)")."""
    n = len(segs)
    L = [(layouts[i] if layouts and i < len(layouts) else None) or "day_zoom" for i in range(n)]
    L = [k if k in SO_PHU else "day_zoom" for k in L]
    ghi, cam = [], set()
    if not n:
        return L, ghi
    dd = [la_dao_dien(sg) for sg in segs]
    sh, dur = (lambda i: segs[i]["shot"]), (lambda i: segs[i]["dur"])
    chai = lambda i: la_chai(sh(i))

    def hop_cung(i, K, cur):          # luật cứng của đoạn máy-tự-gán i với kiểu K (cur = danh sách kiểu hiện hành)
        if K in ("pip_troi", "pip_giua") and chai(i):
            return False
        if K == "day" and dur(i) > 2.8:
            return False
        if K == "luoi_4" and (dur(i) < 2.2 or any(cur[j] == "luoi_4" for j in range(n) if j != i)):
            return False
        return not (K in ("chia_doi", "chia_ngang") and dur(i) < 1.5)

    def them_phu(i, K):               # đủ ô phụ cho K? (lấy thêm qua lay_phu nếu thiếu)
        need = SO_PHU[K] - len(segs[i].get("phu_shots", []))
        if need > 0 and lay_phu:
            segs[i]["phu_shots"] = list(segs[i].get("phu_shots", [])) + list(lay_phu(segs[i], need))[:need]
        return len(segs[i].get("phu_shots", [])) >= SO_PHU[K]

    def sua_dd(i):                    # đạo diễn chọn: chỉ sửa khi KHÔNG thể dựng
        K = L[i]
        if K == "lat_trang" and dur(i) < 2 * LAT_MIN:
            K = "day_zoom"
        while SO_PHU[K] and not them_phu(i, K):
            K = GAN_NHAT.get(K, "khung_mo")
        return K

    def sua_cung(i):                  # máy tự gán: đưa kiểu hiện tại về hợp luật cứng
        K = L[i]
        if K in ("pip_troi", "pip_giua") and chai(i):
            return "khung_mo"
        if K == "day" and dur(i) > 2.8:
            return "day_zoom"
        if K == "luoi_4" and (dur(i) < 2.2 or "luoi_4" in L[:i]):
            return "chia_doi" if dur(i) >= 1.5 else "khung_mo"
        if K in ("chia_doi", "chia_ngang") and dur(i) < 1.5:
            return "khung_mo"
        if SO_PHU[K] and not them_phu(i, K):
            return "khung_mo" if chai(i) else "day_zoom"
        return K
    for i in range(n):
        K = sua_dd(i) if dd[i] else sua_cung(i)
        if K != L[i]:
            ghi.append(f"đoạn {i}: {L[i]}→{K} (" + ("thiếu cảnh phụ/quá ngắn, giữ ý đạo diễn gần nhất" if dd[i] else "luật cứng") + ")"); L[i] = K
        if dd[i] and K == "day" and dur(i) > 2.8 and not segs[i].get("doi_khung"):
            segs[i]["doi_khung"] = True
            ghi.append(f"đoạn {i}: day {dur(i):.1f}s > 2,8 s → đổi khung giữa đoạn, giữ kiểu đạo diễn chọn (chống reup)")
    tu_do = [i for i in range(n) if not dd[i]]
    if not tu_do:
        return L, ghi
    han_mo, san_toan = int(TRAN_HOP_MO * n + 1e-9), -int(-SAN_TOAN * n // 1)       # floor(45%·n), ceil(35%·n)
    nho = -int(-n // 3)                                                              # ≥ 1/3 đoạn không toàn màn thuần
    co_chia = lambda c: any(k in ("chia_doi", "chia_ngang", "luoi_4") for k in c)

    def gia(c):                       # chi phí vi phạm (càng thấp càng tốt)
        mo, toan = sum(k in HOP_MO for k in c), sum(k in TOAN for k in c)
        lien = sum(1 for i in range(2, n) if c[i] == c[i - 1] == c[i - 2])
        return (10 * (max(0, mo - han_mo) + max(0, san_toan - toan)) + 8 * lien + 4 * max(0, nho - (n - toan))
                + (1 if n >= 4 and not co_chia(c) and co_chia_duoc else 0) + (1 if n >= 4 and not any(k in ("pip_troi", "pip_giua") for k in c) and pip_duoc else 0))
    co_chia_duoc = any(0 < i < n - 1 and dur(i) >= 1.5 for i in tu_do)
    pip_duoc = any(not chai(i) for i in tu_do)
    for _ in range(40):               # tìm cục bộ (chỉ đoạn máy tự gán): mỗi vòng đổi 1 đoạn nếu giảm được chi phí
        c0 = gia(L); tot = []
        for i in tu_do:
            for K in MAY_CHON:
                if K == L[i] or (i, K) in cam or not hop_cung(i, K, L):
                    continue
                if (i in (0, n - 1) and K in ("pip_troi", "pip_giua", "chia_doi", "chia_ngang", "luoi_4")) or (SO_PHU[K] and not lay_phu and len(segs[i].get("phu_shots", [])) < SO_PHU[K]):
                    continue
                c = L[:i] + [K] + L[i + 1:]
                tot.append((gia(c), (K in HOP_MO) == (L[i] in HOP_MO) and (K in TOAN) == (L[i] in TOAN), rng.random(), i, K))
        tot.sort(key=lambda z: (z[0], not z[1], z[2]))
        if not tot or tot[0][0] >= c0:
            break
        _, _, _, i, K = tot[0]
        if SO_PHU[K] and not them_phu(i, K):
            cam.add((i, K)); continue
        ghi.append(f"đoạn {i}: {L[i]}→{K} (trần/sàn bố cục)"); L[i] = K
    return L, ghi


def _aff(s):
    """Cảnh aff: người thật cầm/dùng/nói về sản phẩm — cảnh quý nhất, KHÔNG bị loại hay trừ điểm vì có mặt người nói."""
    return s.get("loai") == "nguoi_noi" or "nguoi_noi_vao_may" in (s.get("the") or []) or "nguoi_noi" in (s.get("vai_tro") or [])


def chon_phu(sg, n, shots, rng, used):
    """Chọn n cảnh phụ khác file cảnh chính, ưu tiên cảnh vườn/phun/pha và cảnh aff (người thật cầm/nói về sản phẩm) để ô phụ có nội dung khác.
    Loại: chữ chèn nặng (soat.chu_muc ≥ 2), xấu (dep ≤ 1), chai hãng khác ở vai chai cận."""
    sx = lambda s: s.get("soat") or {}
    chai_vai = {"chai_ro", "chai_mo", "nhan_can", "kho_hang"}
    chu = lambda s: sx(s).get("chu_muc", 2 if sx(s).get("chu") else 0)
    ok = [s for s in shots if s["file"] != sg["shot"]["file"] and not (chu(s) >= 2 or (sx(s).get("dep") or 3) <= 1)
          and not (sx(s).get("hang_khac") and set(s["vai_tro"]) & chai_vai)]
    hay = [s for s in ok if set(s["vai_tro"]) & {"phun", "pha_rot", "cong_viec", "van_de", "vuon"} or _aff(s)]
    if la_chai(sg["shot"]):   # cảnh chính là chai → ô phụ ưu tiên cảnh vườn/phun/aff, tránh chai chồng chai không có người
        hay = [s for s in hay if not la_chai(s) or _aff(s)]
        ok = hay or ok
    if not ok:                # kho quá ít cảnh sạch (review #21): lấy lại chính cảnh chính nhưng ở đoạn khác của nó, không sập dựng
        s = sg["shot"]; slack = max(0.0, float(s["dai"]) - float(sg["dur"]) - 0.3)
        mot = round(float(s["tu"]) + (slack if float(sg.get("src_start", s["tu"])) - float(s["tu"]) < slack / 2 else 0.0), 2)
        return [{"shot": s, "src_start": mot} for _ in range(n)]
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


def _punch(opt):
    """Phóng cắt nhẹ có neo ngẫu nhiên (đã tính để không cắt nhãn chai) — chống trùng cho cảnh toàn màn."""
    p = float(opt.get("punch") or 0)
    if p <= 0:
        return ""
    return f"crop=iw*{1 - p:.3f}:ih*{1 - p:.3f}:(iw-ow)*{float(opt.get('ax', 0.5)):.3f}:(ih-oh)*{float(opt.get('ay', 0.5)):.3f},"


def _lech_mau(grade, opt):
    """Lệch màu (±2°) / tương phản (±3%) rất nhẹ mỗi đoạn toàn màn — mắt không thấy nhưng 2 đoạn không còn giống hệt."""
    h, tp = int(opt.get("hue") or 0), float(opt.get("tp") or 1.0)
    return grade + (f",hue=h={h}" if h else "") + (f",eq=contrast={tp:.3f}" if abs(tp - 1) > 0.004 else "")


def _troi(w, h, d, opt, k, chai, ay=0.5, truc=None, cx=None, bien=None):
    """Ô/khung: phóng lớn 4–6% rồi trôi chậm qua lại trong phần dư → khung không đứng yên (review #14). Cảnh chai: biên độ nhỏ, không cắt nhãn."""
    zs, a = (1.04, 0.3) if chai else (1.06, 0.5)
    dr = int(opt.get("huong") or 1) * (1 if k % 2 == 0 else -1)
    fx = f"(0.5+{dr * a:.2f}*(2*t/{d:.3f}-1))"
    if cx is not None:            # dải hẹp: giữ tâm ngang tại cx (0–1 trong cảnh, vd. giữa khung chai ≈ người cầm chai), chỉ trôi rất nhẹ
        b = 0.1 if bien is None else bien
        return (f"scale={int(w * zs) // 2 * 2}:{int(h * zs) // 2 * 2}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}:"
                f"x='clip(iw*{cx:.3f}-{w}/2+(iw-{w})*{dr * b:.2f}*(2*t/{d:.3f}-1),0,iw-{w})':y='(ih-{h})*{ay}'")
    truc = truc or opt.get("truc", "x")        # ay: neo dọc khi chỉ trôi ngang (ô nhiều người: lấy phần trên để không cắt đầu)
    xy = (f"x='(iw-{w})*{fx}':y='(ih-{h})*{ay}'" if truc == "x" else f"x='(iw-{w})/2':y='(ih-{h})*{fx}'")
    return (f"scale={int(w * zs) // 2 * 2}:{int(h * zs) // 2 * 2}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}:{xy}")


def lat_trang_chia(d, so_clip):
    """Chia đoạn d giây cho lật trang: (số lát thật, độ dài mỗi lát, [mốc lật tương đối]). Tối đa 8 lát, mỗi lát ≥ LAT_MIN; thiếu giờ → bớt lát."""
    n = max(1, min(int(so_clip), 8, int(d / LAT_MIN + 1e-9)))
    sl = d / n
    return n, sl, [round(sl * k, 3) for k in range(1, n)]


LAT_PUNCH = [(0.04, 0.5, 0.5), (0.09, 0.2, 0.3), (0.06, 0.8, 0.3), (0.11, 0.3, 0.75), (0.05, 0.7, 0.7), (0.10, 0.5, 0.15), (0.07, 0.1, 0.5), (0.12, 0.9, 0.5)]


def _lat_trang(i, d, main_idx, phu_idx, grade, opt, shot, phu_shots):
    """Lật trang: cảnh chính + cảnh phụ lần lượt toàn màn, cắt cứng, mỗi lát một độ phóng/neo khác để không hai khung nào giống nhau."""
    nguon = [(main_idx, shot)] + list(zip(phu_idx, phu_shots))
    n, sl, _ = lat_trang_chia(d, len(nguon))
    ten, fc = [], []
    for k, (idx, sh) in enumerate(nguon[:n]):
        p, ax, ay = LAT_PUNCH[k % len(LAT_PUNCH)]
        p, ax, ay = punch_an_toan(p, ax, ay, (sh.get("soat") or {}).get("nhan")) if (sh.get("soat") or {}).get("nhan") else (p, ax, ay)
        pc = f"crop=iw*{1 - p:.3f}:ih*{1 - p:.3f}:(iw-ow)*{ax:.3f}:(ih-oh)*{ay:.3f},scale={W}:{H}:flags=lanczos," if p > 0 else ""
        cham = f"setpts={float(opt['cham']):.3f}*PTS," if (k == 0 and opt.get("cham")) else ""
        fc.append(f"[{idx}:v]{_pre(sh)}{cham}scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},{pc}setsar=1,fps={FPS},"
                  f"tpad=stop_mode=clone:stop_duration=4,trim=duration={sl:.3f},setpts=PTS-STARTPTS,{grade},unsharp=5:5:0.6,format=yuv420p[ls{i}_{k}]")
        ten.append(f"[ls{i}_{k}]")
    fc.append("".join(ten) + f"concat=n={n}:v=1:a=0,trim=duration={d:.3f},setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
    return fc


def loc(i, L, d, main_idx, phu_idx, mask_idx, grade, motion, opt, shot, phu_shots, an_tu=0.0):
    """Đoạn filter cho đoạn cảnh i → nhãn [v{i}]. mask_idx: chỉ số input mặt nạ theo thứ tự ô. Trả (filters, mốc ô hiện).
    an_tu: ô phụ chỉ được hiện SAU mốc này (giây trong đoạn) — dung.py đặt = thời gian chuyển cảnh + 0,05 để ô không hiện chồng lên xfade (ma)."""
    base = f"setsar=1,fps={FPS},tpad=stop_mode=clone:stop_duration=4"
    tail = f"trim=duration={d:.3f},setpts=PTS-STARTPTS"
    cham = f"setpts={float(opt['cham']):.3f}*PTS," if opt.get("cham") else ""   # cảnh ngắn hơn câu → quay chậm trong phạm vi cảnh
    gj = _lech_mau(grade, opt)
    full = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},{base},"
            f"{motion},{gj},unsharp=5:5:0.6,{tail}")
    pc = _punch(opt)
    if L == "lat_trang":
        return _lat_trang(i, d, main_idx, phu_idx, grade, opt, shot, phu_shots), []
    if L == "day" and opt.get("doi_khung"):
        h = round(d / 2, 3)
        nen = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},{base},{motion},{gj},unsharp=5:5:0.6")
        p2, ax, ay = float(opt["p2"]), float(opt["ax2"]), float(opt["ay2"])
        return [f"[{main_idx}:v]{_pre(shot)}{pc}{cham}{nen},split=2[da{i}][db{i}]",
                f"[da{i}]trim=duration={h},setpts=PTS-STARTPTS,setsar=1[dc{i}]",
                f"[db{i}]trim=start={h},setpts=PTS-STARTPTS,crop=iw*{1 - p2:.3f}:ih*{1 - p2:.3f}:(iw-ow)*{ax:.3f}:(ih-oh)*{ay:.3f},"
                f"scale={W}:{H}:flags=lanczos,setsar=1[dd{i}]",
                f"[dc{i}][dd{i}]concat=n=2:v=1:a=0,trim=duration={d:.3f},setpts=PTS-STARTPTS,format=yuv420p[v{i}]"], []
    if L == "day":
        return [f"[{main_idx}:v]{_pre(shot)}{pc}{cham}{full},format=yuv420p[v{i}]"], []
    if L == "day_zoom":   # phóng cắt 1 vùng (đổi hẳn khung gốc) + trôi nhẹ
        zw = int(W * opt["z"]) // 2 * 2; zh = int(H * opt["z"]) // 2 * 2
        return [f"[{main_idx}:v]{_pre(shot)}{cham}scale={zw}:{zh}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}:x='(iw-{W})*({opt['ox']}+0.06*t/{d:.3f})':"
                f"y='(ih-{H})*{opt['oy']}',setsar=1,fps={FPS},tpad=stop_mode=clone:stop_duration=4,{gj},unsharp=5:5:0.6,{tail},"
                f"format=yuv420p[v{i}]"], []
    fc = []
    key = _key(L, opt)
    if L in NEN_RO:
        fc.append(f"[{main_idx}:v]{_pre(shot)}{pc}{cham}{full}[b{i}]")
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
        ta = round(ta + an_tu, 3) if ta > 0 else 0
        pw, ph = w + 2 * B, h + 2 * B
        o_shot = shot if (L not in NEN_RO and k == 0) else phu_shots[k - (0 if L in NEN_RO else 1)]    # cảnh nằm trong ô này
        ay_o, truc_o = ((0.25, "x") if L == "chia_3" else (0.5, None))
        nh_o = (o_shot.get("soat") or {}).get("nhan") if L == "ba_doc" else None
        cx_o = round(0.5 * 0.5 + 0.5 * min(max((float(nh_o[0]) + float(nh_o[2])) / 2, 0.0), 1.0), 3) if nh_o and len(nh_o) == 4 else (0.5 if L == "ba_doc" else None)   # chia_3: ô ngang của cảnh dọc → neo phần trên (đầu người), chỉ trôi ngang
        fc.append(f"[s{i}_{k}]{_troi(w, h, d, opt, k, la_chai(o_shot), ay_o, truc_o, cx_o)},{grade},unsharp=5:5:0.5,"
                  f"pad={pw}:{ph}:{B}:{B}:color={opt['vien']},format=yuva420p[p{i}_{k}]")
        fc.append(f"[{mask_idx[k]}:v]format=gray,{tail}[mk{i}_{k}]")
        nxt = f"o{i}_{k}"
        if ta > 0:      # ô phụ hiện bằng "nảy to dần" 0,16 s, luôn đục (không alpha mờ → hết bóng ma), và chỉ sau khi chuyển cảnh xong
            e = f"min(1,max(0,(t-{ta})/0.16))"
            fc.append(f"[p{i}_{k}][mk{i}_{k}]alphamerge[q{i}_{k}]")
            fc.append(f"[q{i}_{k}]scale=w='trunc({pw}*(0.84+0.16*{e})/2)*2':h='trunc({ph}*(0.84+0.16*{e})/2)*2':eval=frame[r{i}_{k}]")
            fc.append(f"[{cur}][r{i}_{k}]overlay=x='{x - B}+({pw}-w)/2':y='{y - B}+({ph}-h)/2':eval=frame:enable='gte(t,{ta})'[{nxt}]")
            times.append(ta)
        else:
            fc.append(f"[p{i}_{k}][mk{i}_{k}]alphamerge[q{i}_{k}]")
            fc.append(f"[{cur}][q{i}_{k}]overlay=x={x - B}:y={y - B}:eval=frame[{nxt}]")
        cur = nxt
    fc.append(f"[{cur}]format=yuv420p[v{i}]")
    if L in NHIEU_O and i > 0:      # mọi ô vào cùng lúc → MỘT pop cho cả kiểu (đoạn 0: không pop, khỏi tiếng ở giây 0)
        times = [round(an_tu, 3)]
    return fc, times


def mask_sizes(L, opt):
    return [] if L in ("day", "day_zoom", "lat_trang") else [(w, h) for (_, _, w, h) in RECTS[_key(L, opt)]]
