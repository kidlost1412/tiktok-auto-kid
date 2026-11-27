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
    "khung_mo":   [(56, 180, 968, 1430)],
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
    # Kid 24/11: "giữ 1 khung 3–5 s mà trong đó các khung aff khác hiện lên" — khung to + 2 thẻ nghiêng bật vào lần lượt hai bên (dưới tầm mặt)
    "khung_hien": [(56, 180, 968, 1430), (36, 790, 340, 604), (684, 730, 340, 604)],
    # Kid 24/11: "1 aff lớn 1 khung, có các khung video chạy xung quanh" — khung giữa + 2 cột cảnh phụ trôi dọc ngược chiều (cột dựng riêng ở loc)
    "khung_chay": [(252, 330, 568, 1180)],
    "chay_mot":   [(40, 300, 740, 1250)],      # 1 cột trôi bên phải, khung chính rộng hơn
    "chay_ngang": [(90, 470, 900, 950)],       # 2 thanh ô vuông trôi ngang trên/dưới
    # Kid 24/11 lần 2: "các video xoay tròn quanh người", "hiện rồi mất"
    "xoay_quanh": [(230, 380, 620, 1100)],     # khung giữa + thẻ aff quay vòng như băng chuyền quanh khung (sau khung thì nhỏ, trước khung thì to)
    "hien_mat":   [(56, 180, 968, 1430)],      # khung to + thẻ aff bật lên rồi thu mất, lần lượt từng thẻ
    "chong_the":  [(56, 180, 968, 1430)],      # thẻ aff bay vào từ hai bên, chồng lên nhau như xấp ảnh ở nửa dưới
    "roi_the":    [(56, 180, 968, 1430)],      # thẻ aff rơi từ trên xuống so le như mưa ảnh
}
APPEAR = {"khung_mo": [0.0], "khung_nho": [0.0], "chia_doi": [0.0, 0.0], "chia_ngang": [0.0, 0.0], "luoi_4": [0.0, 0.0, 0.0, 0.0],
          "pip_trai": [0.25], "pip_phai": [0.25], "pip_giua": [0.25], "chia_3": [0.0] * 3, "ba_doc": [0.0] * 3,
          "khung_hien": [0.0, 0.3, 0.6], "khung_chay": [0.0], "chay_mot": [0.0], "chay_ngang": [0.0],
          "xoay_quanh": [0.0], "hien_mat": [0.0], "chong_the": [0.0], "roi_the": [0.0]}
TI_LE_HIEN = {"khung_hien"}        # APPEAR của kiểu này là PHẦN của độ dài đoạn (0,3 → ở 30% đoạn), không phải giây
NGHIENG = {"khung_hien": [0.0, 0.06, -0.05]}      # góc nghiêng (radian) từng ô
# Kiểu "khung + dải cảnh trôi" (Kid 24/11: mỗi video khác nhau — dọc 2 cột / dọc 1 cột / ngang 2 thanh; cảnh trong dải KHÔNG trùng nhau, ưu tiên aff cầm hàng)
# ô (rộng, cao); dải: (trục, vị trí cố định, hướng ±1); khe giữa ô; tốc độ trôi px/s
CHAY = {"khung_chay": {"o": (200, 500), "dai": [("doc", 28, -1), ("doc", 1080 - 28 - 216, 1)]},
        "chay_mot":   {"o": (230, 520), "dai": [("doc", 1080 - 24 - 246, -1)]},
        "chay_ngang": {"o": (240, 240), "dai": [("ngang", 170, -1), ("ngang", 1450, 1)]}}
KHE_CHAY, TOC_CHAY = 18, 75       # Kid 24/11: dải trôi nhanh hơn để khoe nhiều cảnh hơn (40 → 75 px/s)
# Kiểu "thẻ động" quanh khung chính: kích thước thẻ, số thẻ tối đa
# Kid 24/11: thẻ xoay 5–10 cảnh (ít nhất 5), xoay nhanh hơn, nhiều kiểu quỹ đạo
# Kid 24/11 tối: thẻ cắt 3:4 làm mất đầu người → mọi thẻ dọc 9:16 = lấy trọn khung cảnh gốc
THE = {"xoay_quanh": {"o": (220, 392), "toi_da": 8}, "hien_mat": {"o": (340, 604), "toi_da": 4},
       "chong_the": {"o": (330, 586), "toi_da": 6}, "roi_the": {"o": (240, 426), "toi_da": 8}}
# quỹ đạo: x = 540 + px·sin(a), y = cy + py·sin(a) + pz·cos(a); sau=True: cos<0 là vòng sau (nhỏ, khuất sau khung)
QUY_DAO = {"bang_chuyen": dict(px=440, py=0, pz=240, cy=1150, sau=True), "nghieng": dict(px=430, py=280, pz=170, cy=960, sau=True),
           "vong_tron": dict(px=450, py=0, pz=720, cy=930, sau=False), "elip_duoi": dict(px=470, py=0, pz=190, cy=1320, sau=True)}
VONG_XOAY = (6.5, 9.0)   # giây/vòng; Kid 24/11 tối: 2,8–4 s quá nhanh, không kịp nhìn
# Mọi ô của một kiểu nhiều ô vào CÙNG LÚC từ khung đầu của đoạn (không nền mờ trống). Chỉ ô trời (pip) hiện sau để nổi trên cảnh chính.
SO_PHU = {"day": 0, "day_zoom": 0, "khung_mo": 0, "khung_nho": 0, "pip_troi": 1, "pip_giua": 1, "chia_doi": 1, "chia_ngang": 1, "luoi_4": 3,
          "chia_3": 2, "ba_doc": 2, "lat_trang": 2, "khung_hien": 2, "khung_chay": 3, "chay_mot": 3, "chay_ngang": 3,
          "xoay_quanh": 5, "hien_mat": 3, "chong_the": 4, "roi_the": 5}
TOI_DA_PHU = {"lat_trang": 7, "khung_chay": 12, "chay_mot": 6, "chay_ngang": 12, "hien_mat": 4, "xoay_quanh": 8, "chong_the": 6, "roi_the": 8}       # lat_trang: cảnh chính + 2–7 cảnh phụ (tổng 3–8 cảnh); SO_PHU là mức TỐI THIỂU
LAT_MIN = 0.28                      # lát lật trang ngắn nhất (giây)
# Kid 10/11: "không hẳn phải 4 khung, 1 khung 2 khung cũng được, đa dạng để tránh trùng" → lưới 4 chỉ là kiểu hiếm
TRONG_SO = {"day": 0.26, "day_zoom": 0.12, "pip_troi": 0.15, "pip_giua": 0.08, "khung_mo": 0.13, "khung_nho": 0.08,
            "chia_doi": 0.09, "chia_ngang": 0.07, "luoi_4": 0.04}
MAY_CHON = frozenset(TRONG_SO)                            # kiểu MÁY được tự chọn khi đạo diễn không chọn (kiểu mới chỉ do đạo diễn chọn)
NEN_RO = {"day", "day_zoom", "pip_troi", "pip_giua"}      # kiểu giữ cảnh chính toàn màn làm nền
HOP_MO = {"khung_mo", "khung_nho", "chia_doi", "chia_ngang", "luoi_4", "chia_3", "ba_doc", "khung_hien", "khung_chay", "chay_mot", "chay_ngang",
          "xoay_quanh", "hien_mat", "chong_the", "roi_the"}   # "khung trên nền mờ" = kiểu có RECTS mà KHÔNG thuộc NEN_RO (build boxblur ở loc())
TOAN = ("day", "day_zoom")                                # toàn màn thuần (không ô chèn)
NHIEU_O = {"chia_doi", "chia_ngang", "luoi_4", "chia_3", "ba_doc"}   # kiểu nhiều ô: mọi ô hiện cùng lúc, 1 "pop" cho cả kiểu
GAN_NHAT = {"chong_the": "hien_mat", "roi_the": "hien_mat", "xoay_quanh": "khung_hien", "hien_mat": "khung_hien", "khung_chay": "khung_hien", "chay_mot": "khung_hien", "chay_ngang": "khung_hien", "khung_hien": "khung_mo", "luoi_4": "chia_3", "chia_3": "chia_doi", "ba_doc": "chia_ngang", "chia_doi": "khung_mo", "chia_ngang": "khung_mo",
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
    "khung_hien": ("giữ 1 khung to (hợp aff cầm chai) 3–5 s, trong lúc đó 2 thẻ cảnh phụ nghiêng bật vào lần lượt hai bên (ưu tiên aff/người khác), đoạn ≥ 2,8 s", 2),
    "khung_chay": ("khung giữa (aff) + 2 cột cảnh aff/tư liệu khác nhau trôi dọc ngược chiều hai bên, đoạn ≥ 2,5 s", 3),
    "chay_mot": ("khung chính rộng bên trái + 1 cột cảnh aff/tư liệu khác nhau trôi dọc bên phải, đoạn ≥ 2,5 s", 3),
    "chay_ngang": ("khung chính giữa + 2 thanh ô vuông cảnh aff khác nhau trôi ngang trên/dưới, đoạn ≥ 2,5 s", 3),
    "xoay_quanh": ("khung giữa (aff/người) + 5–8 thẻ aff khác quay vòng quanh khung (băng chuyền / nghiêng / vòng tròn, chiều và tốc độ máy đổi mỗi lần), đoạn ≥ 2,5 s", 5),
    "chong_the": ("khung to + 4–6 thẻ aff khác bay vào từ hai bên chồng lên nhau như xấp ảnh ở nửa dưới (khoe nhiều người dùng), đoạn ≥ 2,8 s", 4),
    "roi_the": ("khung to + 5–8 thẻ aff khác rơi so le từ trên xuống như mưa ảnh (khoe độ lan truyền), đoạn ≥ 2,5 s", 5),
    "hien_mat": ("khung to + 3–4 thẻ aff khác lần lượt bật lên rồi thu mất ở chỗ trống (không che mặt/nhãn), đoạn ≥ 2,8 s", 3),
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
    if (shot or {}).get("nhan_can_hop") and not ((shot or {}).get("soat") or {}).get("nhan"):
        p = 0.0                                           # kho kiểu 3: có chai SP mà chưa định vị nhãn → không phóng, khỏi cắt mất nhãn
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


O_HEP = {"chia_doi", "chia_ngang", "luoi_4", "chia_3", "ba_doc", "pip_troi", "pip_giua"}   # kiểu có ô nhỏ/hẹp: cảnh người toàn/trung vào ô sẽ mất đầu hoặc mặt bé tí


def la_nguoi(s):
    """Cảnh có người (soát: mat ≥ 1) hoặc cảnh aff (người thật cầm/nói về sản phẩm)."""
    return ((s.get("soat") or {}).get("mat") or 0) >= 1 or _aff(s)


O_CAO = {"chia_ngang", "ba_doc"}    # ô dọc cao (≥ 1080 px): người đứng/ngồi vẫn trọn đầu (loc neo trên) → aff vào được

def vua_o_hep(s, K=None):
    """Cảnh vào được ô hẹp/nhỏ: không có người (chai, lá, tay, chi tiết) HOẶC người đã cận (co_canh can → mặt to). Người toàn/trung/chưa rõ cỡ cảnh → không.
    K là ô dọc cao (O_CAO) → mọi cảnh đều vừa (Kid 23/11: aff ghép cặp trong ô dọc là cách chống reup tốt)."""
    return K in O_CAO or not la_nguoi(s) or s.get("co_canh") in ("can", "can_canh")


def canh_o_hep(L, shot, phu):
    """Các cảnh nằm trong ô hẹp của kiểu L (kiểu nền rõ: chỉ ô phụ đầu; kiểu khung: cả cảnh chính + phụ). Kiểu khác → []."""
    if L not in O_HEP:
        return []
    return list(phu[:1]) if L in NEN_RO else [shot] + list(phu[:SO_PHU[L]])


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
        if d < 2.2 or k == 0:
            opts.pop("luoi_4", None)
        for kk in NHIEU_O:        # mỗi kiểu nhiều ô tối đa 1 lần/video
            if dem.get(kk):
                opts.pop(kk, None)
        if not vua_o_hep(sg["shot"]):     # cảnh chính là người toàn/trung: không nhét vào ô hẹp (trừ ô dọc cao)
            for kk in [x for x in opts if x in O_HEP and x not in NEN_RO and x not in O_CAO]:
                opts.pop(kk)
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


def ep_bo_cuc(segs, layouts, rng, lay_phu=None, khung=None, kho_canh=None, used=None, mo=None):
    """Như _ep_bo_cuc + lượt VỪA KHUNG cuối (áp cả lên kiểu đạo diễn chọn):
    (1) ô hẹp/nhỏ (O_HEP) chỉ nhận cảnh vua_o_hep; cảnh phụ không vừa → thử đổi qua lay_phu (≤ 3 lần), vẫn không vừa → hạ về khung_mo (cảnh trọn trong khung lớn);
    (2) mỗi kiểu nhiều ô (NHIEU_O) tối đa 1 lần/video: lần thứ 2 trở đi → khung_mo."""
    L, ghi = _ep_bo_cuc(segs, layouts, rng, lay_phu)
    for i, sg in enumerate(segs):
        K = L[i]
        if K not in O_HEP:
            continue
        phu = list(sg.get("phu_shots", []))
        if K in NEN_RO:
            sl = [0]                                  # chỉ ô phụ đầu nằm trong ô nhỏ
        else:
            sl = [j for j in range(min(len(phu), SO_PHU[K]))]
        for j in sl:
            for _ in range(3):
                if j >= len(phu) or vua_o_hep(phu[j], K) or not lay_phu:
                    break
                moi = list(lay_phu(sg, 1))[:1]
                if moi and vua_o_hep(moi[0], K):
                    phu[j] = moi[0]
        sg["phu_shots"] = phu
        if not all(vua_o_hep(s, K) for s in canh_o_hep(K, sg["shot"], phu)):
            ghi.append(f"đoạn {i}: {K}→khung_mo (cảnh người toàn/trung không vừa ô hẹp)"); L[i] = "khung_mo"
    da = set()
    co_qua = lambda i: any(str(p.get("id", "")).startswith("Q-") for p in segs[i].get("phu_shots") or [])
    for i in sorted(range(len(L)), key=lambda i: not co_qua(i)):     # đoạn có ô QUÀ THẬT giữ kiểu trước, đoạn khác cùng kiểu mới bị hạ
        K = L[i]
        if K in NHIEU_O:
            if K in da:
                ghi.append(f"đoạn {i}: {K}→khung_mo (mỗi kiểu nhiều ô tối đa 1 lần/video)"); L[i] = "khung_mo"
            da.add(K)
    if khung == "chu_theo_loi":
        _khung_loi(segs, L, ghi, lay_phu, rng, kho_canh, used, mo)
    else:
        _aff_don(segs, L, lay_phu, ghi)
    return L, ghi


O_KHUNG_LOI = 2     # khung "chữ theo lời" (Kid 23/11): hình toàn màn + chữ to là chính; chia ô / khung nền mờ chỉ 1–2 lần mỗi video


# Kid 24/11: mỗi kiểu ≤ 1 lần/video, tính riêng ngoài O_KHUNG_LOI; KHÔNG video nào cũng có — mỗi video khác một chút (xác suất + kiểu dải ngẫu nhiên)
# Kid 24/11 lần 2: "các kiểu edit đó anh muốn claude nó quyết, đa dạng mới mẻ liên tục" → ĐẠO DIỄN chọn kiểu đặc biệt (giữ nguyên, ngoài trần O_KHUNG_LOI);
# đạo diễn không chọn kiểu nào → máy bốc 1 kiểu (xác suất P_MAY_DAC_BIET), tránh kiểu các video gần đây đã dùng (kieu_gan).
DAC_BIET = {"khung_hien": 2.8, "khung_chay": 2.5, "chay_mot": 2.5, "chay_ngang": 2.5, "xoay_quanh": 2.5, "hien_mat": 2.8, "chong_the": 2.8, "roi_the": 2.5}   # kiểu → đoạn tối thiểu (giây)
TOI_DA_DAC_BIET = 2
THE_DE = {"khung_hien", "hien_mat", "xoay_quanh", "chong_the", "roi_the"}   # kiểu đặt thẻ ĐÈ lên khung chính
NHAN_TO = 0.30             # nhãn chai > 30% khung → thẻ đè không né được (giám khảo 24/11: "ô chèn che nhãn can" 2 lần)
P_MAY_DAC_BIET = 0.75
KIEU_CHAY = ("khung_chay", "chay_mot", "chay_ngang")
_DA_DUNG = []            # kiểu đặc biệt đã dùng trong tiến trình này (2 video cùng lô chưa kịp ghi sổ)


def kieu_gan(n=6):
    """Kiểu đặc biệt của n video gần nhất (sổ lich-su/bo-cuc-gan.txt + video vừa dựng trong tiến trình) — để video sau khác video trước."""
    ds = []
    try:
        from duong_dan import DATA
        f = Path(DATA) / "lich-su" / "bo-cuc-gan.txt"
        if f.exists():
            ds = [l.split() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()][-n:]
    except Exception:
        ds = []
    return [k for l in ds for k in l if k in DAC_BIET] + list(_DA_DUNG)


def ghi_kieu(layouts):
    """Ghi 1 dòng kiểu bố cục của video vừa xong vào sổ (gọi cạnh ghi_lich_su_canh)."""
    try:
        from duong_dan import DATA
        d = Path(DATA) / "lich-su"; d.mkdir(parents=True, exist_ok=True)
        with open(d / "bo-cuc-gan.txt", "a", encoding="utf-8") as f:
            f.write(" ".join(layouts) + "\n")
    except Exception:
        pass


def _canh_sach(s):
    sx = s.get("soat") or {}
    return not (sx.get("chu_muc", 2 if sx.get("chu") else 0) >= 2 or (sx.get("dep") or 3) <= 1 or sx.get("hang_khac"))


def tu_lieu(sg, n, kho_canh, used, rng, mo=None):
    """Cảnh cho dải trôi: mỗi ô một FILE khác, chưa dùng ở video này, không mờ, không chữ chèn nặng. Ưu tiên (Kid 24/11 "người xem nhìn sự uy tín,
    sự lan truyền"): aff cầm sản phẩm → aff/người khác → cảnh rót/pha/phun → cảnh khác (chỉ khi thiếu nguồn)."""
    def hang(s):
        vt = set(s.get("vai_tro") or [])
        if la_nguoi(s) and (la_chai(s) or vt & {"chai_ro", "chai_mo", "nhan_can"}):
            return 0
        if la_nguoi(s):
            return 1
        return 2 if vt & {"pha_rot", "phun", "cong_viec"} else 3
    da = {sg["shot"]["file"]} | {f for f, _ in (used or ())}
    pool = [s for s in kho_canh or [] if s["file"] not in da and _canh_sach(s) and not (mo and mo(s))]
    pool.sort(key=lambda s: (hang(s), rng.random()))
    out = []
    for s in pool:
        if s["file"] not in {x["file"] for x in out}:
            out.append(s)
        if len(out) >= n:
            break
    for s in out:
        if used is not None:
            used.add((s["file"], int(s["tu"])))
    return out


def _phu_cho(sg, n, lay_phu, nguoi):
    """n cảnh phụ khác file cảnh chính, không trùng nhau; nguoi=True: ưu tiên aff/người (thẻ "aff khác hiện lên"), thiếu thì cảnh tư liệu bất kỳ."""
    co, du = [], []
    for s in list(sg.get("phu_shots") or []) + [x for _ in range(3 * n) for x in (list(lay_phu(sg, 1))[:1] if lay_phu else [])]:
        if s["file"] == sg["shot"]["file"] or any(s["file"] == x["file"] for x in co + du):
            continue
        (co if (la_nguoi(s) or not nguoi) else du).append(s)
        if len(co) >= n:
            break
    return (co + du)[:n]


def so_phu_dac_biet(K, d):
    return sum(so_o_chay(K, d + 0.3)) if K in CHAY else TOI_DA_PHU.get(K, SO_PHU[K])


def _khung_loi(segs, L, ghi, lay_phu=None, rng=None, kho_canh=None, used=None, mo=None):
    """Khung chữ theo lời: giữ tối đa O_KHUNG_LOI đoạn có ô/khung thường (ưu tiên đoạn giữa video), còn lại về toàn màn.
    Kiểu ĐẶC BIỆT (DAC_BIET) ngoài trần đó: đạo diễn chọn thì giữ (≤ TOI_DA_DAC_BIET, không đầu/cuối, không liền nhau, đủ dài);
    đạo diễn không chọn → máy bốc 1 kiểu ít dùng gần đây cho đoạn aff/người dài nhất. Cảnh phụ của kiểu đặc biệt: file khác nhau, chưa dùng, aff cầm hàng trước.
    Aff đứng một mình > AFF_DON giây → đặt vào khung to trên nền mờ (Kid: "chèn khung to bao quanh làm mờ là được, chả cần nghĩ nhiều")."""
    import random as _r
    rng = rng or _r.Random(len(segs))
    n, moi = len(L), {}
    truoc = _DA_DUNG[-1:]                               # kiểu video liền trước (cùng lô) đã dùng
    for i, K in enumerate(L):                           # đạo diễn chọn
        if K not in DAC_BIET:
            continue
        if 0 < i < n - 1 and float(segs[i]["dur"]) >= DAC_BIET[K] - 0.3 and len(moi) < TOI_DA_DAC_BIET and i - 1 not in moi:
            if K in truoc:                              # 2 video liền nhau không cùng kiểu đặc biệt: đổi sang kiểu khác vừa đoạn
                K = rng.choice([k for k, dm in DAC_BIET.items() if k != K and float(segs[i]["dur"]) >= dm - 0.3] or [K])
            moi[i] = K
        else:
            L[i] = "khung_mo"; ghi.append(f"đoạn {i}: {K} không hợp chỗ (đầu/cuối, ngắn, liền nhau) → khung_mo")
    if not moi and rng.random() < P_MAY_DAC_BIET:
        gan = kieu_gan()
        ung = sorted((i for i in range(1, n - 1) if la_nguoi(segs[i]["shot"])), key=lambda i: -float(segs[i]["dur"]))
        for i in ung:
            hop = [K for K, dm in DAC_BIET.items() if float(segs[i]["dur"]) >= dm]
            if hop:
                w = [1.0 / (1 + 3 * gan.count(K)) for K in hop]
                moi[i] = rng.choices(hop, weights=w)[0]
                break
    for i, K in list(moi.items()):
        nh = (segs[i]["shot"].get("soat") or {}).get("nhan")
        if K in THE_DE and nh and len(nh) == 4 and (float(nh[2]) - float(nh[0])) * (float(nh[3]) - float(nh[1])) > NHAN_TO:
            K = moi[i] = rng.choice(KIEU_CHAY)          # nhãn chiếm gần hết khung (can cận): thẻ đè lên kiểu gì cũng che → dải trôi ngoài khung
            ghi.append(f"đoạn {i}: nhãn to, thẻ sẽ che → {K}")
        can = so_phu_dac_biet(K, float(segs[i]["dur"]))
        if kho_canh:
            co = [p for p in segs[i].get("phu_shots") or [] if p["file"] != segs[i]["shot"]["file"] and _canh_sach(p)]
            co = [p for j, p in enumerate(co) if p["file"] not in {x["file"] for x in co[:j]}]
            phu = (co + tu_lieu(dict(segs[i], phu_shots=co), can - len(co), kho_canh, (used or set()) | {(p["file"], 0) for p in co}, rng, mo))[:can]
            if used is not None:
                used.update((p["file"], int(p["tu"])) for p in phu)
        else:
            phu = _phu_cho(segs[i], SO_PHU[K], lay_phu, True)
        if len(phu) >= SO_PHU[K]:
            segs[i]["phu_shots"] = phu
        else:
            del moi[i]; L[i] = "khung_mo"; ghi.append(f"đoạn {i}: {K} thiếu cảnh phụ → khung_mo")
    co_o = [i for i, K in enumerate(L) if K not in DON_O and i not in moi and not any(str(p.get("id", "")).startswith("Q-") for p in segs[i].get("phu_shots") or [])]   # ô quà ở chốt: luôn giữ
    giu = sorted(co_o, key=lambda i: abs(i - len(L) / 2))[:O_KHUNG_LOI]
    for i in co_o:
        if i not in giu:
            L[i] = "day" if float(segs[i]["dur"]) <= 2.8 else "day_zoom"
            ghi.append(f"đoạn {i}: khung chữ theo lời → toàn màn (ô/khung chỉ {O_KHUNG_LOI} lần)")
    for i, K in moi.items():
        L[i] = K; ghi.append(f"đoạn {i}: {K} ({float(segs[i]['dur']):.1f}s)")
        _DA_DUNG.append(K)
    del _DA_DUNG[:-4]
    for i, sg in enumerate(segs):
        if L[i] in ("day", "day_zoom") and float(sg["dur"]) > AFF_DON and _aff(sg["shot"]):
            L[i] = "khung_mo"; ghi.append(f"đoạn {i}: aff đứng 1 mình > {AFF_DON} s → khung to nền mờ")


AFF_DON, TUA_AFF = 2.0, 1.35
DON_O = {"day", "day_zoom", "khung_mo", "khung_nho"}


def _con_lai(sg):
    sh = sg["shot"]
    return float(sh.get("den", float(sh["tu"]) + float(sh["dai"]))) - float(sg.get("src_start", sh["tu"]))


def _aff_don(segs, L, lay_phu, ghi):
    """Kid 23/11 (chống reup): cảnh aff đứng MỘT MÌNH toàn khung > AFF_DON giây phải (1) ghép thêm khung aff/người khác (chia_ngang, ô dọc cao giữ đầu),
    hoặc (2) tua nhanh TUA_AFF lần (đủ cảnh), hoặc (3) đánh dấu can_chu_lon để lớp chữ đặt khối chữ to. Đoạn chốt (cuối) giữ gọn → chỉ (2)/(3)."""
    for i, sg in enumerate(segs):
        if L[i] not in DON_O or float(sg["dur"]) <= AFF_DON or not _aff(sg["shot"]):
            continue
        if i < len(segs) - 1 and "chia_ngang" not in L and float(sg["dur"]) >= 1.5 and lay_phu:
            ban = None
            for _ in range(4):
                moi = list(lay_phu(sg, 1))[:1]
                if moi and la_nguoi(moi[0]) and moi[0]["file"] != sg["shot"]["file"]:
                    ban = moi[0]; break
            if ban:
                sg["phu_shots"] = [ban] + [p for p in sg.get("phu_shots", []) if p is not ban]
                L[i] = "chia_ngang"; ghi.append(f"đoạn {i}: aff đứng 1 mình → chia_ngang ghép aff khác"); continue
        if _con_lai(sg) >= float(sg["dur"]) * TUA_AFF + 0.1:
            sg["tua_nhanh"] = TUA_AFF; ghi.append(f"đoạn {i}: aff đứng 1 mình → tua nhanh x{TUA_AFF}"); continue
        sg["can_chu_lon"] = True; ghi.append(f"đoạn {i}: aff đứng 1 mình, không ghép/tua được → cần chữ lớn")


def _ep_bo_cuc(segs, layouts, rng, lay_phu=None):
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
        if K == "luoi_4" and dur(i) < 2.2:
            return False
        if K in NHIEU_O and any(cur[j] == K for j in range(n) if j != i):
            return False
        if K in O_HEP and K not in NEN_RO and not vua_o_hep(sh(i), K):
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
    if sg.get("bo_cuc") != "lat_trang":   # ô phụ nằm trong ô hẹp/nhỏ: ưu tiên cảnh vừa khung (không người toàn/trung; ô dọc cao nhận cả)
        K = sg.get("bo_cuc")
        vua = [s for s in ok if vua_o_hep(s, K)]
        if len(vua) >= n:
            ok, hay = vua, [s for s in hay if vua_o_hep(s, K)]
    if not ok:                # kho quá ít cảnh sạch (review #21): lấy lại chính cảnh chính nhưng ở đoạn khác của nó, không sập dựng
        s = sg["shot"]; slack = max(0.0, float(s["dai"]) - float(sg["dur"]) - 0.3)
        mot = round(float(s["tu"]) + (slack if float(sg.get("src_start", s["tu"])) - float(s["tu"]) < slack / 2 else 0.0), 2)
        return [{"shot": s, "src_start": mot} for _ in range(n)]
    out = []
    for _ in range(n):
        ds = hay if rng.random() < 0.6 and hay else ok
        da_f = {f for f, _ in used}                   # Kid 27/11: mỗi clip gốc (cùng người, cùng áo) một lần trong video; hết clip khác mới lấy lại
        pool = [s for s in ds if s["file"] not in da_f] or [s for s in ok if s["file"] not in da_f] or \
            [s for s in ds if (s["file"], int(s["tu"])) not in used] or ok
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


def _troi(w, h, d, opt, k, chai, ay=0.5, truc=None, cx=None, bien=None, fy=None):
    """Ô/khung: phóng lớn 4–6% rồi trôi chậm qua lại trong phần dư → khung không đứng yên (review #14). Cảnh chai: biên độ nhỏ, không cắt nhãn.
    fy: tâm mặt theo chiều dọc (0–1 trong cảnh) → mặt nằm ở ~38% chiều cao ô, không mất đầu."""
    zs, a = (1.04, 0.3) if chai else (1.06, 0.5)
    dr = int(opt.get("huong") or 1) * (1 if k % 2 == 0 else -1)
    fx = f"(0.5+{dr * a:.2f}*(2*t/{d:.3f}-1))"
    if cx is not None:            # dải hẹp: giữ tâm ngang tại cx (0–1 trong cảnh, vd. mặt người hoặc giữa khung chai), chỉ trôi rất nhẹ
        b = 0.1 if bien is None else bien
        y = f"clip(ih*{fy:.3f}-{h}*0.38,0,ih-{h})" if fy is not None else f"(ih-{h})*{ay}"
        return (f"scale={int(w * zs) // 2 * 2}:{int(h * zs) // 2 * 2}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}:"
                f"x='clip(iw*{cx:.3f}-{w}/2+(iw-{w})*{dr * b:.2f}*(2*t/{d:.3f}-1),0,iw-{w})':y='{y}'")
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
    truoc = []
    if key in THE:
        fcc, sau, truoc, tthe = _the(i, key, d, grade, opt, phu_shots, mask_idx[1], an_tu, shot)
        fc += fcc; times += tthe
        for k, (lab, x, y, en) in enumerate(sau):        # thẻ vòng sau: vẽ TRƯỚC khung chính → khuất sau khung
            fc.append(f"[{cur}][{lab}]overlay=x='{x}':y='{y}':eval=frame:enable='{en}'[tb{i}_{k}]"); cur = f"tb{i}_{k}"
    for k, ((x, y, w, h), ta) in enumerate(zip(o_hien(shot) if key == "khung_hien" else RECTS[key], APPEAR[key])):
        ta = (round(max(ta * d, an_tu + 0.05), 3) if key in TI_LE_HIEN else round(ta + an_tu, 3)) if ta > 0 else 0
        pw, ph = w + 2 * B, h + 2 * B
        o_shot = shot if (L not in NEN_RO and k == 0) else phu_shots[k - (0 if L in NEN_RO else 1)]    # cảnh nằm trong ô này
        ay_o, truc_o = ((0.25, "x") if L == "chia_3" else (0.5, None))
        if la_nguoi(o_shot):            # cảnh có người: giữ phần trên (chừa đầu), chỉ trôi ngang
            ay_o, truc_o = min(ay_o, 0.2), "x"
        nh_o = (o_shot.get("soat") or {}).get("nhan") if L == "ba_doc" else None
        cx_o = round(0.5 * 0.5 + 0.5 * min(max((float(nh_o[0]) + float(nh_o[2])) / 2, 0.0), 1.0), 3) if nh_o and len(nh_o) == 4 else (0.5 if L == "ba_doc" else None)   # chia_3: ô ngang của cảnh dọc → neo phần trên (đầu người), chỉ trôi ngang
        mat, fy_o, bien_o = o_shot.get("_mat"), None, None
        nh_c = (o_shot.get("soat") or {}).get("nhan")
        if not mat and nh_c and len(nh_c) == 4 and not la_nguoi(o_shot):    # cảnh chai/quà: canh ô theo nhãn (v10_8: ô chia_3 neo phần trên → chỉ thấy lá, mất chai TC01)
            cx_o, fy_o, bien_o, truc_o = (float(nh_c[0]) + float(nh_c[2])) / 2, (float(nh_c[1]) + float(nh_c[3])) / 2, 0.03, None
        if mat:                        # có mặt người: canh ô theo mặt (Kid 23/11: aff cầm chai mà ô cắt mất mặt), trôi rất nhẹ để mặt không trượt ra mép
            cx_o, fy_o, bien_o = mat[0], mat[1], 0.03
        fc.append(f"[s{i}_{k}]{_troi(w, h, d, opt, k, la_chai(o_shot), ay_o, truc_o, cx_o, bien_o, fy_o)},{grade},unsharp=5:5:0.5,"
                  f"pad={pw}:{ph}:{B}:{B}:color={opt['vien']},format=yuva420p[p{i}_{k}]")
        fc.append(f"[{mask_idx[k]}:v]format=gray,{tail}[mk{i}_{k}]")
        nxt = f"o{i}_{k}"
        goc = (NGHIENG.get(key) or [0.0] * 9)[k]
        xoay = f",rotate={goc}:c=none:ow=rotw({goc}):oh=roth({goc})" if goc else ""     # thẻ nghiêng: góc ngoài trong suốt
        if goc:
            pw, ph = _xoay_kt(pw, ph, goc)
        cx0, cy0 = x - B + (w + 2 * B) / 2, y - B + (h + 2 * B) / 2                    # tâm ô cố định, ô xoay/nảy quanh tâm
        fc.append(f"[p{i}_{k}][mk{i}_{k}]alphamerge{xoay}[q{i}_{k}]")
        if ta > 0:      # ô phụ hiện bằng "nảy to dần" 0,16 s, luôn đục (không alpha mờ → hết bóng ma), và chỉ sau khi chuyển cảnh xong
            e = f"min(1,max(0,(t-{ta})/0.16))"
            fc.append(f"[q{i}_{k}]scale=w='trunc({pw}*(0.84+0.16*{e})/2)*2':h='trunc({ph}*(0.84+0.16*{e})/2)*2':eval=frame[r{i}_{k}]")
            fc.append(f"[{cur}][r{i}_{k}]overlay=x='{cx0}-w/2':y='{cy0}-h/2':eval=frame:enable='gte(t,{ta})'[{nxt}]")
            times.append(ta)
        else:
            fc.append(f"[{cur}][q{i}_{k}]overlay=x='{cx0}-w/2':y='{cy0}-h/2':eval=frame[{nxt}]")
        cur = nxt
    if key in CHAY:
        fc += _dai_chay(i, key, d, grade, opt, phu_shots, mask_idx[1], cur)
        cur = f"cc{i}"
    for k, (lab, x, y, en) in enumerate(truoc):
        fc.append(f"[{cur}][{lab}]overlay=x='{x}':y='{y}':eval=frame:enable='{en}'[tz{i}_{k}]"); cur = f"tz{i}_{k}"
    fc.append(f"[{cur}]format=yuv420p[v{i}]")
    if L in NHIEU_O and i > 0:      # mọi ô vào cùng lúc → MỘT pop cho cả kiểu (đoạn 0: không pop, khỏi tiếng ở giây 0)
        times = [round(an_tu, 3)]
    return fc, times


CHO_THE = [(36, 790), (684, 730), (36, 240), (684, 260)]     # khung_hien: chỗ đặt thẻ 340×604 (dưới trái, dưới phải, trên trái, trên phải)


def o_hien(shot):
    """khung_hien: khung to + 2 thẻ đặt ở chỗ ÍT che nhãn chai và mặt người nhất của cảnh chính (giám khảo 24/11: "hai ô chèn che nhãn can")."""
    (mx, my, mw, mh), (tw, th) = RECTS["khung_hien"][0], RECTS["khung_hien"][1][2:]
    sx = lambda v: mx + float(v) * mw
    sy = lambda v: my + float(v) * mh
    tranh = []
    n = (shot.get("soat") or {}).get("nhan")
    if n and len(n) == 4:
        tranh.append(((sx(n[0]) - 30, sy(n[1]) - 30, sx(n[2]) + 30, sy(n[3]) + 30), 3.0))
    m = shot.get("_mat")
    if m:
        tranh.append(((sx(m[0]) - 230, sy(m[1]) - 280, sx(m[0]) + 230, sy(m[1]) + 280), 2.0))   # mặt cận trong khung to: hộp rộng
    def phat(c):
        x, y = c
        return sum(k * max(0, min(x + tw, b[2]) - max(x, b[0])) * max(0, min(y + th, b[3]) - max(y, b[1])) for b, k in tranh) + (0 if c in CHO_THE[:2] else 1)
    tot = sorted(CHO_THE, key=phat)
    a = tot[0]
    b = next((c for c in tot[1:] if abs(c[0] - a[0]) > 200 or abs(c[1] - a[1]) > 520), tot[1])     # 2 thẻ không chồng lên nhau
    return [RECTS["khung_hien"][0], (a[0], a[1], tw, th), (b[0], b[1], tw, th)]


def _xoay_kt(w, h, a):
    import math
    return int(math.ceil((abs(w * math.cos(a)) + abs(h * math.sin(a))) / 2)) * 2, int(math.ceil((abs(w * math.sin(a)) + abs(h * math.cos(a))) / 2)) * 2


def so_o_chay(L, d):
    """Số ô cần cho từng dải của kiểu L trong đoạn d giây: đủ phủ kín màn + quãng trôi (không lặp vòng)."""
    (tw, th), dai = CHAY[L]["o"], CHAY[L]["dai"]
    return [int(-(-((H if t == "doc" else W) + TOC_CHAY * d) // ((th if t == "doc" else tw) + 2 * B + KHE_CHAY))) for t, _, _ in dai]


def _dai_chay(i, L, d, grade, opt, phu_shots, mk, cur):
    """Dải ô cảnh phụ trôi quanh khung chính. Mỗi ô một cảnh khác (phu_shots theo thứ tự ưu tiên); thiếu cảnh mới lặp lại. Ra nhãn [cc{i}]."""
    (tw, th), pw, ph = CHAY[L]["o"], CHAY[L]["o"][0] + 2 * B, CHAY[L]["o"][1] + 2 * B
    can = so_o_chay(L, d)
    n = max(1, len(phu_shots))
    gan = [[(c0 + k) % n for k in range(c)] for c0, c in zip([sum(can[:j]) for j in range(len(can))], can)]
    dung = {}
    for g in gan:
        for j in g:
            dung[j] = dung.get(j, 0) + 1
    fc = [f"[{mk}:v]format=gray,trim=duration={d:.3f},setpts=PTS-STARTPTS,split={sum(dung.values())}" + "".join(f"[mt{i}_{m}]" for m in range(sum(dung.values())))]
    m = 0
    nhan = {j: [] for j in dung}
    for j, sl in dung.items():
        sh = phu_shots[j] if j < len(phu_shots) else phu_shots[0]
        mat = sh.get("_mat")
        fc.append(f"[s{i}_{j + 1}]{_troi(tw, th, d, opt, j, la_chai(sh), 0.2 if la_nguoi(sh) else 0.5, 'x', mat[0] if mat else None, 0.03 if mat else None, mat[1] if mat else None)},"
                  f"{grade},pad={pw}:{ph}:{B}:{B}:color={opt['vien']},format=yuva420p,split={sl}" + "".join(f"[tp{i}_{j}_{c}]" for c in range(sl)))
        for c in range(sl):
            nhan[j].append(f"[tq{i}_{j}_{c}]")
            fc.append(f"[tp{i}_{j}_{c}][mt{i}_{m}]alphamerge[tq{i}_{j}_{c}]"); m += 1
    fc += [f"[s{i}_{j + 1}]nullsink" for j in range(len(phu_shots)) if j not in dung]     # cảnh phụ dư: bỏ, không để đầu ra treo
    for c, ((truc, pos, huong), g) in enumerate(zip(CHAY[L]["dai"], gan)):
        o = [nhan[j].pop() for j in g]
        dem = f"{pw}:{ph + KHE_CHAY}" if truc == "doc" else f"{pw + KHE_CHAY}:{ph}"
        for k, x in enumerate(o):
            fc.append(f"{x}pad={dem}:0:0:color=black@0[g{i}_{c}_{k}]")
        fc.append("".join(f"[g{i}_{c}_{k}]" for k in range(len(o))) + (f"vstack" if truc == "doc" else "hstack") + f"=inputs={len(o)}[dc{i}_{c}]" if len(o) > 1
                  else f"[g{i}_{c}_0]null[dc{i}_{c}]")
        dl = len(o) * ((ph + KHE_CHAY) if truc == "doc" else (pw + KHE_CHAY))
        man = H if truc == "doc" else W
        chay = f"-{TOC_CHAY}*t" if huong < 0 else f"{man - dl}+{TOC_CHAY}*t"      # trôi lên/trái từ mép đầu; xuống/phải từ mép cuối
        xy = f"x={pos}:y='{chay}'" if truc == "doc" else f"x='{chay}':y={pos}"
        ra = f"cc{i}" if c == len(gan) - 1 else f"cd{i}_{c}"
        fc.append(f"[{cur}][dc{i}_{c}]overlay={xy}:eval=frame[{ra}]")
        cur = ra
    return fc


def _the(i, L, d, grade, opt, phu_shots, mk, an_tu, shot):
    """Thẻ cảnh phụ động quanh khung chính → (filters, thẻ vẽ sau khung, thẻ vẽ trước khung, mốc thẻ hiện).
    xoay_quanh: thẻ quay vòng theo 1 quỹ đạo QUY_DAO (chiều, tốc độ, quỹ đạo đổi mỗi lần; vòng sau nhỏ và khuất sau khung).
    hien_mat: từng thẻ bật lên rồi thu mất ở chỗ trống. chong_the: thẻ bay vào từ hai bên chồng thành xấp. roi_the: thẻ rơi so le từ trên xuống."""
    import math, random as _r
    rng = _r.Random(f"{shot.get('file')}|{i}|{L}|{d:.2f}")
    tw, th = THE[L]["o"]; pw, ph = tw + 2 * B, th + 2 * B
    n = max(1, min(len(phu_shots), THE[L]["toi_da"]))
    fc = [f"[{mk}:v]format=gray,trim=duration={d:.3f},setpts=PTS-STARTPTS" + (f",split={n}" if n > 1 else "") + "".join(f"[tm{i}_{m}]" for m in range(n))]
    fc += [f"[s{i}_{j + 1}]nullsink" for j in range(n, len(phu_shots))]
    sau, truoc, times = [], [], []
    bd = round(an_tu + 0.2, 3)
    if L == "xoay_quanh":
        q = QUY_DAO[rng.choice(sorted(QUY_DAO))]
        T, huong, pha = round(rng.uniform(*VONG_XOAY), 2), rng.choice((1, -1)), round(rng.uniform(0, 6.28), 3)
    elif L == "hien_mat":
        a0, b0 = o_hien(shot)[1:3]
        cho = [(a0[0], a0[1]), (b0[0], b0[1])]
        buoc = max(0.5, (d - 0.12 - bd) / n)
    elif L == "chong_the":
        buoc = max(0.2, min(0.45, (d - 0.7 - bd) / n))
    else:
        roi = round(rng.uniform(1.0, 1.4), 2)
        buoc = max(0.18, (d - roi - bd) / max(1, n - 1))
        cot = [round(140 + (800 * (j + 0.5) / n)) for j in range(n)]
        rng.shuffle(cot)
    for k in range(n):
        sh = phu_shots[k]
        mat = sh.get("_mat")
        fc.append(f"[s{i}_{k + 1}]{_troi(tw, th, d, opt, k, la_chai(sh), 0.2 if la_nguoi(sh) else 0.5, 'x', mat[0] if mat else None, 0.03 if mat else None, mat[1] if mat else None)},"
                  f"{grade},unsharp=5:5:0.5,pad={pw}:{ph}:{B}:{B}:color={opt['vien']},format=yuva420p[tc{i}_{k}]")
        if L == "xoay_quanh":
            a = f"({huong}*2*PI*t/{T}+{round(2 * math.pi * k / n + pha, 4)})"
            x, y = f"540+{q['px']}*sin({a})-w/2", f"{q['cy']}+{q['py']}*sin({a})+{q['pz']}*cos({a})-h/2"
            if q["sau"]:
                fc.append(f"[tc{i}_{k}][tm{i}_{k}]alphamerge,scale=w='trunc({pw}*(0.72+0.14*(1+cos({a})))/2)*2':h='trunc({ph}*(0.72+0.14*(1+cos({a})))/2)*2':eval=frame,"
                          f"split=2[ts{i}_{k}][tf{i}_{k}s]")
                sau.append((f"ts{i}_{k}", x, y, f"lt(cos({a}),0)"))
                truoc.append((f"tf{i}_{k}s", x, y, f"gte(cos({a}),0)"))
            else:
                fc.append(f"[tc{i}_{k}][tm{i}_{k}]alphamerge[tf{i}_{k}s]")
                truoc.append((f"tf{i}_{k}s", x, y, "1"))
            continue
        goc = round(rng.uniform(0.04, 0.12) * (1 if k % 2 == 0 else -1), 3) if L != "hien_mat" else (0.05 if k % 2 == 0 else -0.05)
        rw, rh = _xoay_kt(pw, ph, goc)
        xoay = f"alphamerge,rotate={goc}:c=none:ow=rotw({goc}):oh=roth({goc})"
        if L == "hien_mat":
            ta, tb = round(bd + 0.05 + k * buoc, 3), round(min(d, bd + 0.05 + (k + 1) * buoc + 0.1), 3)
            cx, cy = cho[k % 2][0] - B + pw / 2, cho[k % 2][1] - B + ph / 2
            e = f"max(0,min(1,min((t-{ta})/0.16,({tb}-t)/0.14)))"
            fc.append(f"[tc{i}_{k}][tm{i}_{k}]{xoay},scale=w='max(2,trunc({rw}*(0.3+0.7*{e})/2)*2)':h='max(2,trunc({rh}*(0.3+0.7*{e})/2)*2)':eval=frame[tf{i}_{k}s]")
            truoc.append((f"tf{i}_{k}s", f"{cx}-w/2", f"{cy}-h/2", f"between(t,{ta},{tb})"))
            times.append(ta)
        elif L == "chong_the":       # bay vào từ hai bên, hạ cánh quanh nửa dưới, thẻ sau đè thẻ trước, nằm lại thành xấp
            ta = round(bd + k * buoc, 3)
            x0 = -rw if k % 2 == 0 else W
            xl, yl = 540 - rw / 2 + rng.randint(-110, 110), 1360 - rh / 2 + rng.randint(-70, 70)
            e = f"(1-pow(1-max(0,min(1,(t-{ta})/0.24)),3))"
            fc.append(f"[tc{i}_{k}][tm{i}_{k}]{xoay}[tf{i}_{k}s]")
            truoc.append((f"tf{i}_{k}s", f"{x0}+({xl - x0})*{e}", f"{yl + 160}-160*{e}", f"gte(t,{ta})"))
            times.append(ta)
        else:                        # roi_the: rơi thẳng qua màn, cột so le
            ta = round(bd + k * buoc, 3)
            fc.append(f"[tc{i}_{k}][tm{i}_{k}]{xoay}[tf{i}_{k}s]")
            truoc.append((f"tf{i}_{k}s", f"{cot[k]}-w/2", f"-h+({H}+h)*(t-{ta})/{roi}", f"between(t,{ta},{round(ta + roi, 3)})"))
    return fc, sau, truoc, times


def mask_sizes(L, opt):
    if L in THE:
        return [(w, h) for (_, _, w, h) in RECTS[L]] + [THE[L]["o"]]
    if L in CHAY:
        return [(w, h) for (_, _, w, h) in RECTS[L]] + [CHAY[L]["o"]]
    return [] if L in ("day", "day_zoom", "lat_trang") else [(w, h) for (_, _, w, h) in RECTS[_key(L, opt)]]
