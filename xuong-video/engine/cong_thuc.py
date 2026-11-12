"""8 CÔNG THỨC DỰNG (Kid duyệt 10/11/2026) + xếp khối theo câu/vùng + kiểm nội dung khối + chống lặp trong ngày."""
import re

FPS = 30
RECIPES = {
    "tvc_sang": {"ten": "TVC sang", "mo": ["hook_mat_na", "hook_bang", "hook_go_may"], "giua": ["lower_third", "vong_tron", "da_quang", "nhan_dan"],
                 "chot": ["the_qua", "nut_gio_hang"], "phu_de": ["mo_sang", "to_dan", "quet_mau", "hop_mo"], "chuyen_canh": ["fade", "smoothleft", "smoothup"],
                 "chuyen_dong": ["zoom_vao", "zoom_ra"], "mau": ["am", "mat", "tu_nhien"], "nhac": ["tvc-doanh-nghiep", "piano-nhe", "tiktok"],
                 "sfx": ["gon", "vua"], "atmos": {"leak": 0.7, "vignette": 0.6, "grain": 0.3}, "nhip": "vua"},
    "soi_dong": {"ten": "Bán hàng sôi động", "mo": ["hook_dap", "hook_tem", "hook_tung_tu"], "giua": ["bong_chu", "dai_chay", "nhan_dan", "mui_ten_chi"],
                 "chot": ["hop_qua", "nut_gio_hang", "the_qua"], "phu_de": ["o_nhay", "vien_day", "nhich_len"], "chuyen_canh": ["slideleft", "slideup", "zoomin", "hon_hop"],
                 "chuyen_dong": ["hon_hop"], "mau": ["tuoi", "tuong_phan"], "nhac": ["vui-mua-sam", "tiktok"],
                 "sfx": ["soi_dong", "mo_dau_am"], "atmos": {"leak": 0.3, "vignette": 0.2, "grain": 0.0}, "nhip": "nhanh"},
    "danh_sach": {"ten": "Danh sách lý do", "mo": ["hook_bang", "hook_go_may", "hook_mat_na"], "giua": ["checklist"],
                  "chot": ["bang_qua", "the_qua"], "phu_de": ["to_dan", "gach_chay", "o_nhay"], "chuyen_canh": ["slideleft", "slideup", "smoothleft"],
                  "chuyen_dong": ["zoom_vao", "lia_trai", "lia_phai"], "mau": ["tuoi", "tu_nhien"], "nhac": ["tvc-doanh-nghiep", "vui-mua-sam", "tiktok"],
                  "sfx": ["vua"], "atmos": {"leak": 0.3, "vignette": 0.3, "grain": 0.0}, "nhip": "vua"},
    "con_so": {"ten": "Con số", "mo": ["hook_dap", "hook_tung_tu"], "giua": ["so_dem", "bong_chu", "da_quang"],
               "chot": ["nut_gio_hang", "the_qua"], "phu_de": ["vien_day", "to_dan", "nhich_len"], "chuyen_canh": ["zoomin", "slideup", "hon_hop"],
               "chuyen_dong": ["zoom_vao", "hon_hop"], "mau": ["tuong_phan", "tuoi"], "nhac": ["vui-mua-sam", "tvc-doanh-nghiep", "tiktok"],
               "sfx": ["vua", "soi_dong", "mo_dau_am"], "atmos": {"leak": 0.2, "vignette": 0.4, "grain": 0.0}, "nhip": "nhanh"},
    "so_sanh": {"ten": "So sánh", "mo": ["hook_hoi", "hook_tem", "hook_dap"], "giua": ["so_sanh", "vong_tron"],
                "chot": ["the_qua", "hop_qua"], "phu_de": ["o_nhay", "to_dan", "gach_chay"], "chuyen_canh": ["slideleft", "smoothleft", "hon_hop"],
                "chuyen_dong": ["zoom_vao", "zoom_ra"], "mau": ["tu_nhien", "tuoi"], "nhac": ["tvc-doanh-nghiep", "tiktok"],
                "sfx": ["vua", "mo_dau_am"], "atmos": {"leak": 0.2, "vignette": 0.3, "grain": 0.0}, "nhip": "vua"},
    "ke_chuyen": {"ten": "Kể chuyện nhà vườn", "mo": ["hook_go_may", "hook_hoi", "hook_mat_na"], "giua": ["lower_third", "da_quang"],
                  "chot": ["the_qua", "nut_gio_hang"], "phu_de": ["mo_sang", "hop_mo", "to_dan"], "chuyen_canh": ["fade", "smoothup"],
                  "chuyen_dong": ["zoom_vao", "lia_trai", "lia_phai"], "mau": ["am", "mat"], "nhac": ["que-acoustic", "tiktok"],
                  "sfx": ["gon", "vua"], "atmos": {"leak": 0.5, "vignette": 0.5, "grain": 0.4}, "nhip": "vua"},
    "tin_nhanh": {"ten": "Tin nhanh mùa vụ", "mo": ["hook_tem", "hook_bang"], "giua": ["canh_bao", "dai_chay", "mui_ten_chi"],
                  "chot": ["nut_gio_hang", "the_qua"], "phu_de": ["vien_day", "o_nhay", "gach_chay"], "chuyen_canh": ["slideleft", "slideup", "hon_hop"],
                  "chuyen_dong": ["hon_hop"], "mau": ["tuong_phan", "tuoi"], "nhac": ["vui-mua-sam", "tiktok"],
                  "sfx": ["soi_dong", "mo_dau_am"], "atmos": {"leak": 0.1, "vignette": 0.3, "grain": 0.0}, "nhip": "nhanh"},
    "qua_tang": {"ten": "Quà tặng là chính", "mo": ["hook_dap", "hook_tem", "hook_bang"], "giua": ["bong_chu", "nhan_dan"],
                 "chot": ["hop_qua", "bang_qua"], "phu_de": ["o_nhay", "nhich_len", "to_dan"], "chuyen_canh": ["slideup", "zoomin", "hon_hop"],
                 "chuyen_dong": ["hon_hop", "zoom_vao"], "mau": ["tuoi", "am"], "nhac": ["vui-mua-sam", "tet-le-hoi", "tiktok"],
                 "sfx": ["soi_dong", "mo_dau_am", "vua"], "atmos": {"leak": 0.4, "vignette": 0.2, "grain": 0.0}, "nhip": "vua"},
}
KHOI_MO = sorted({k for r in RECIPES.values() for k in r["mo"]})
KHOI_CHOT = sorted({k for r in RECIPES.values() for k in r["chot"]})
ZONE = {"lower_third": "LOWER"}           # còn lại đều ở vùng TOP (trừ hook_dap: CENTER, ngắn)
SO_HOP_LE = {1, 2, 3, 5, 10, 200, 250, 300, 500, 15000}   # số đã có trong sự thật sản phẩm/quà

DATA_SPEC = """Nội dung khối (chữ IN HOA ngắn, đúng sự thật sản phẩm; mỗi dòng ≤ 26 ký tự):
- hook_*: {"text": "<câu mở ≤ 28 ký tự>"}; hook_dap thêm "nhan": <chỉ số chữ cần tô, 0-based>; hook_bang thêm "mau": "do"|"xanh"
- checklist: {"tieu_de": "<tuỳ chọn>", "items": ["<2–4 ý ≤ 22 ký tự>"]}
- so_dem: {"nhan_trai": "1 CHAI", "so": <số có trong sự thật: 200, 300, 500, 15000…>, "don_vi": "LÍT"}
- so_sanh: {"trai_tieu_de": "LOẠI THƯỜNG", "trai": ["≤3 ý"], "phai_tieu_de": "<TÊN SẢN PHẨM>", "phai": ["≤3 ý"]}  (không nêu tên hãng khác)
- vong_tron: {"nhan": "..."} · lower_third: {"dong1": "<TÊN SẢN PHẨM IN HOA>", "dong2": "..."} · nhan_dan: {"text": "≤ 16 ký tự"}
- da_quang: {"text"} · canh_bao: {"tieu_de": "LƯU Ý", "text"} · dai_chay: {"text"} · bong_chu: {"text": "≤ 14 ký tự"} · mui_ten_chi: {"text"}
- hop_qua: {"dong1", "dong2"} · bang_qua: {"tieu_de", "cac_muc": ["Mua 1 chai: ...", ...]} · nut_gio_hang: {"dong1", "text"} · the_qua: {"dong1", "dong2", "kieu": "hop_do|hop_xanh|nhan_vang|the_trang"}"""


def fallback(ten):
    """Khối giữa dự phòng CHUNG cho mọi sản phẩm — chỉ dùng tên sản phẩm (lỗi rà soát #5: trước đây cứng chữ Nano Đồng)."""
    ten = (ten or "").upper()[:30]
    return {"lower_third": {"dong1": ten, "dong2": "Chính hãng Toàn Cầu"}, "nhan_dan": {"text": "CHÍNH HÃNG"},
            "vong_tron": {"nhan": ten[:22]}, "mui_ten_chi": {"text": ten[:22]}, "dai_chay": {"text": ten}}


def _txt(x, n=34):
    return re.sub(r"\s+", " ", str(x or "")).strip()[:n]


def clean_data(loai, d):
    """Kiểm/cắt nội dung khối; trả None nếu khối không dùng được."""
    d = dict(d or {})
    if loai.startswith("hook_"):
        if not d.get("text"):
            return None
        d["text"] = _txt(d["text"], 30)
    elif loai == "checklist":
        items = [_txt(i, 24) for i in d.get("items", []) if i][:4]
        if len(items) < 2:
            return None
        d["items"] = items
    elif loai == "so_dem":
        try:
            so = int(str(d.get("so")).replace(".", "").replace(",", ""))
        except Exception:
            return None
        if so not in SO_HOP_LE:
            return None
        d["so"] = so
    elif loai == "so_sanh":
        if not d.get("trai") or not d.get("phai"):
            return None
    elif loai in ("hop_qua", "the_qua"):
        if not d.get("dong1"):
            return None
    elif loai == "bang_qua":
        if not d.get("cac_muc"):
            return None
    elif loai in ("vong_tron", "nhan_dan", "da_quang", "canh_bao", "dai_chay", "bong_chu", "mui_ten_chi", "lower_third", "nut_gio_hang"):
        if not any(d.get(k) for k in ("text", "nhan", "dong1")):
            return None
    return d


def xep_khoi(recipe_key, khoi_ai, sents, total, st, rng, ten_thuong_hieu):
    """→ danh sách block {loai,f0,f1,data} đã xếp vùng, không đè; luôn có 1 câu mở + 1 khối chốt."""
    R = RECIPES[recipe_key]
    dur_f = int(round(total * FPS))
    S = lambda i: sents[max(0, min(i, len(sents) - 1))]
    hook, mids, cta = None, [], None
    sach = []                                         # đạo diễn trả rác → bỏ/ép kiểu an toàn (lỗi rà soát #2)
    for k in khoi_ai or []:
        if not isinstance(k, dict) or not isinstance(k.get("loai"), str):
            continue
        try:
            cau = int(float(str(k.get("cau", 1)).strip()))
        except Exception:
            cau = 1
        sach.append({"loai": k["loai"], "cau": cau, "du_lieu": k.get("du_lieu") if isinstance(k.get("du_lieu"), dict) else {}})
    for k in sach:
        loai = k.get("loai")
        d = clean_data(loai, k.get("du_lieu"))
        if d is None:
            continue
        if loai in KHOI_MO and hook is None:
            hook = (loai if loai in R["mo"] else rng.choice(R["mo"]), d)
        elif loai in R["giua"] and len(mids) < 2:     # khối giữa ngoài công thức → bỏ (dữ liệu không khớp loại khác)
            mids.append((loai, d, int(k.get("cau", 1))))
        elif loai in KHOI_CHOT and cta is None:
            cta = (loai if loai in R["chot"] else rng.choice(R["chot"]), d)
    if not mids and len(sents) >= 4:                 # luôn có ít nhất 1 khối nhấn giữa bài
        fb = fallback(ten_thuong_hieu)
        hop = [m for m in R["giua"] if m in fb]
        if hop:                                       # không có loại hợp công thức → bỏ khối giữa, không bịa chữ
            loai = rng.choice(hop)
            mids.append((loai, dict(fb[loai]), rng.choice(range(1, len(sents) - 1))))
    hook_text = hook[1] if hook else {"text": _txt(st.get("chu_the_mo") or ten_thuong_hieu, 30), "nhan": 0}
    hook = (st.get("ep_mo") or (hook[0] if hook else rng.choice(R["mo"])), hook_text)
    d1, d2 = st.get("chu_chot_1") or "QUÀ TẶNG THEO ĐƠN", st.get("chu_chot_2") or "BẤM GIỎ HÀNG"
    loai_chot = st.get("ep_chot") or (cta[0] if cta else "the_qua")
    data = dict(cta[1]) if cta else {}
    data.setdefault("dong1", d1); data.setdefault("dong2", d2); data.setdefault("text", d2)
    data.setdefault("kieu", rng.choice(["hop_do", "hop_xanh", "nhan_vang", "the_trang"]))
    if loai_chot == "bang_qua" and not data.get("cac_muc"):
        data["cac_muc"] = st.get("_qua") or []          # lấy đúng các mức quà trong hồ sơ sản phẩm
        if not data["cac_muc"]:
            loai_chot = "hop_qua"
    cta = (loai_chot, data)
    blocks = []
    h_end = 1.5 if hook[0] == "hook_dap" else min(S(0)["e"] + 0.3, 3.2)
    blocks.append({"loai": hook[0], "f0": 2, "f1": int(h_end * FPS), "data": hook[1], "zone": "CENTER" if hook[0] == "hook_dap" else "TOP"})
    cta_f0 = max(int(round((sents[-1]["s"] - 0.15) * FPS)), dur_f - 5 * FPS)
    for loai, d, ci in mids:
        ci = max(1, min(ci, len(sents) - 2)) if len(sents) > 2 else 0
        a = int(S(ci)["s"] * FPS)
        b = int(min(S(ci)["e"] + 0.4, S(ci)["s"] + 4.2) * FPS)
        b = max(b, a + int(1.8 * FPS))
        zone = ZONE.get(loai, "TOP")
        clash = [x for x in blocks if x["zone"] in (zone, "CENTER") and not (b <= x["f0"] or a >= x["f1"])]
        if clash:
            a = max(x["f1"] for x in clash) + 3
            b = max(b, a + int(1.6 * FPS))
        if b > cta_f0 - 3:
            b = cta_f0 - 3
        if b - a < int(1.4 * FPS):
            continue
        blocks.append({"loai": loai, "f0": a, "f1": b, "data": d, "zone": zone})
    blocks.append({"loai": cta[0], "f0": cta_f0, "f1": dur_f, "data": cta[1], "zone": "TOP"})
    return blocks, cta_f0


def chon_atmos(recipe_key, rng, cuts_f):
    a = RECIPES[recipe_key]["atmos"]
    return {"vignette": rng.random() < a["vignette"], "grain": rng.random() < a["grain"], "leaks": [],
            "hue": rng.choice([0, 20, 40, 300, 330])}


def chu_ky(info):
    """Chữ ký phong cách để chống lặp trong ngày."""
    return "|".join(str(info.get(k)) for k in ("cong_thuc", "hook", "phu_de", "chot", "sfx"))


TAT_CA = {"phu_de": ["to_dan", "mo_sang", "o_nhay", "gach_chay", "nhich_len", "hop_mo", "quet_mau", "vien_day"],
          "sfx": ["gon", "vua", "soi_dong", "mo_dau_am"]}


def chuan_hoa(st, rng, used_sigs, tu_do=False):
    """Ép phương án AI vào đúng công thức + chống trùng chữ ký trong ngày. Trả st mới (có ep_mo/ep_chot/sfx).
    tu_do=True (AI đạo diễn): giữ công thức + lựa chọn của AI nếu hợp lệ, không xoay vòng ép đổi."""
    st = dict(st)
    key = st.get("cong_thuc") if st.get("cong_thuc") in RECIPES else rng.choice(list(RECIPES))
    counts = {k: 0 for k in RECIPES}                 # xoay vòng: không để 1 công thức áp đảo trong ngày
    for s in used_sigs:
        counts[s.split("|")[0]] = counts.get(s.split("|")[0], 0) + 1
    low = min(counts.values())
    if counts.get(key, 0) > low and not tu_do:
        key = rng.choice([k for k, v in counts.items() if v == low])
        st["khoi"] = [k for k in st.get("khoi", []) if k.get("loai") in RECIPES[key]["mo"] + RECIPES[key]["giua"] + RECIPES[key]["chot"]]
    R = RECIPES[key]
    st["cong_thuc"] = key
    for k in ("phu_de", "chuyen_canh", "chuyen_dong", "mau", "nhac"):
        if tu_do and st.get(k) and (k != "phu_de" or st[k] in TAT_CA["phu_de"]):
            continue
        if st.get(k) not in R[k]:
            st[k] = rng.choice(R[k])
    st["nhip"] = R["nhip"]
    ok_sfx = TAT_CA["sfx"] if tu_do else R["sfx"]
    st["sfx"] = st.get("sfx") if st.get("sfx") in ok_sfx or st.get("sfx") == "em" else rng.choice(R["sfx"])
    ai_mo = [k.get("loai") for k in st.get("khoi", []) if k.get("loai") in R["mo"]]
    ai_chot = [k.get("loai") for k in st.get("khoi", []) if k.get("loai") in R["chot"]]
    st["ep_mo"] = ai_mo[0] if ai_mo else rng.choice(R["mo"])
    st["ep_chot"] = ai_chot[0] if ai_chot else rng.choice(R["chot"])
    for _ in range(0 if tu_do else 12):          # đổi dần cho tới khi không trùng video nào trong ngày
        sig = chu_ky({"cong_thuc": key, "hook": st["ep_mo"], "phu_de": st["phu_de"], "chot": st["ep_chot"], "sfx": st["sfx"]})
        if sig not in used_sigs:
            break
        what = rng.choice(["phu_de", "mo", "chot", "sfx"])
        if what == "phu_de":
            st["phu_de"] = rng.choice(R["phu_de"])
        elif what == "mo":
            st["ep_mo"] = rng.choice(R["mo"])
        elif what == "chot":
            st["ep_chot"] = rng.choice(R["chot"])
        else:
            st["sfx"] = rng.choice(R["sfx"])
    sig = chu_ky({"cong_thuc": key, "hook": st["ep_mo"], "phu_de": st["phu_de"], "chot": st["ep_chot"], "sfx": st["sfx"]})
    used_sigs.add(sig)
    return st
