"""Viết lời + phương án dựng bằng Claude CLI headless (mỗi lần gọi là phiên MỚI, không lịch sử chat).
viet(ma_sp, so_ban) -> list kịch bản đã qua kiểm."""
import json, random, re
from pathlib import Path


import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, khung_giay, khung_am_tiet
CFG = cfg_hub()
from ai import goi, lay_json, HetHanMuc  # noqa: E402
import prompt_mau  # noqa: E402


def _he_so(ma, chieu):
    try:
        from hieu_qua import he_so
        return he_so(ma, chieu)
    except Exception:
        return {}


def _tom_tat(ma, cho="bien_kich"):
    try:
        from hieu_qua import tom_tat
        return tom_tat(ma, cho)
    except Exception:
        return ""

BANNED = ["chữa khỏi", "khỏi hẳn", "100%", "số 1", "số một", "nhất thị trường", "duy nhất", "không độc", "ăn ngay",
          "tham khảo", "xem chi tiết", "tìm hiểu thêm", "đáng cân nhắc", "theo hướng dẫn của", "quy cách rõ ràng",
          "đúng nhu cầu", " nha", " nè", "giá chỉ", "nghìn đồng", "k/chai"]


def history_sentences(limit=400):
    f = HUB / "lich-su" / "cau-da-dung.txt"
    if not f.exists():
        return []
    return [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()][-limit:]


def cau_cua_sp(ma, limit=150):
    """Câu đã dùng của RIÊNG sản phẩm này (gửi biên kịch). Chưa có sổ riêng → dựng từ hồ sơ các video đã làm của sản phẩm."""
    f = HUB / "lich-su" / f"cau-da-dung-{ma}.txt"
    if not f.exists():
        ds = []
        for j in sorted(Path(CFG["duong_dan"]["ra"]).glob(f"*/{ma}_*.json")):
            try:
                t = (json.loads(j.read_text(encoding="utf-8")).get("kich_ban") or {}).get("text") or ""
            except Exception:
                continue
            ds += [x.strip() for x in re.split(r"(?<=[.!?])\s+", re.sub(r"\[[^\]]*\]", "", t).strip()) if x.strip()]
        ds = list(dict.fromkeys(ds))
        if ds:
            f.write_text("".join(x + "\n" for x in ds), encoding="utf-8")
        return ds[-limit:]
    return [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()][-limit:]


def recent_styles(limit=20):
    f = HUB / "lich-su" / "phong-cach.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()[-limit:] if l.strip()]


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", s.lower())).strip()


DANG_BAI = {   # Kid 10/11: kịch bản phải đa dạng thật sự, không xoay quanh vài ý → mỗi bản một DẠNG BÀI khác
    "ke_chuyen": "Kể chuyện ngắn 1 nhà vườn: tình huống → chuyển biến → chốt",
    "hoi_dap": "Mở bằng câu hỏi nhà nông hay hỏi, trả lời gọn bằng sản phẩm",
    "sai_lam": "Chỉ ra 1 sai lầm phổ biến (giâm cành, trồng mới, bón…) rồi cách làm đúng",
    "truoc_sau": "Đặt trước/sau: khi chưa dùng thế nào, khi dùng thì khác gì (không bịa số liệu)",
    "top_ly_do": "3 lý do ngắn gọn để chọn sản phẩm",
    "meo_nha_nong": "Mẹo nhà nông thực tế, sản phẩm là mảnh ghép chính",
    "canh_bao_mua_vu": "Nhắc đúng thời điểm mùa vụ (trồng mới, tái canh, đầu mưa, sau thu hoạch…)",
    "so_sanh": "So sánh với loại thường (không nêu tên hãng, không chê bai)",
    "cach_dung": "Hướng dẫn nhanh cách pha/cách dùng, nhấn sự tiện và tiết kiệm",
    "qua_tang": "Lấy chương trình quà làm trọng tâm, vẫn nói rõ công dụng",
    "khang_dinh": "Khẳng định thương hiệu, tự tin như TVC",
    "tinh_huong": "Tình huống đời thường ngoài vườn (cây còi, cành giâm chết, rễ thối…) rồi giải pháp",
}


def dem_lich_su(ten, n=200):
    f = HUB / "lich-su" / ten
    return f.read_text(encoding="utf-8").splitlines()[-n:] if f.exists() else []


def ctx_bien_kich(sp, n, angles, used, styles, dang=None, mo_dau=None, qc=None, hieu_qua=""):
    """Dữ liệu điền vào mẫu prompt/bien-kich.md (chỗ nào cần logic/khối tuỳ chọn thì tính ở đây; khối rỗng → "")."""
    luat = prompt_mau.doc_luat("LUAT-SAN-XUAT.md")
    luat = luat.split("## Dựng")[0].rstrip()          # phần Dựng là việc của đạo diễn/máy dựng, biên kịch không cần
    so_gu_f = HUB / "lich-su" / "so-gu.md"
    so_gu = so_gu_f.read_text(encoding="utf-8")[-3000:].strip() if so_gu_f.exists() else ""
    so_gu = ("=== SỔ GU CỦA CHỦ HÀNG ===" + chr(10) + so_gu + chr(10)) if so_gu else ""
    kg, kat = khung_giay(sp), khung_am_tiet(sp)
    return {
        "luat": luat,
        # mã nội bộ, tên giỏ hàng và mục rỗng không giúp viết lời → không gửi
        "san_pham": json.dumps({k: v for k, v in sp.items() if k not in ("ma", "ten_gio") and v not in ("", [], {}, None)},
                               ensure_ascii=False, indent=1),
        "so_gu": so_gu,
        "so_lieu_tiktok": "" if not hieu_qua else chr(10) + "=== SỐ LIỆU THẬT TỪ TIKTOK (video đã đăng) ===" + chr(10) + hieu_qua + chr(10),
        "ten_phai_nhac": json.dumps(ten_phai_nhac(sp), ensure_ascii=False),
        "so_ban": n,
        "angles": json.dumps(angles, ensure_ascii=False),
        "dang": json.dumps([f"{d}: {DANG_BAI[d]}" for d in (dang or [])], ensure_ascii=False),
        "quy_cach": ("quy_cach = " + json.dumps(qc, ensure_ascii=False) + "  ← bản thứ i nói về QUY CÁCH qc[i] (dung tích/đóng gói), chỉ dùng mức quà của ĐÚNG quy cách đó.") if qc else "",
        "cau_mo_da_dung": json.dumps((mo_dau or [])[-60:], ensure_ascii=False),
        "giay_toi_thieu": f"{kg[0]:g}", "giay_toi_da": f"{kg[1]:g}",
        "am_tiet_toi_thieu": kat[0], "am_tiet_toi_da": kat[1], "am_tiet_muc_tieu": (kat[0] + kat[1]) // 2,
        "cau_toi_thieu": kat[4], "cau_toi_da": kat[5],
        "cau_da_dung": json.dumps(used[-150:], ensure_ascii=False),
        "giong": "|".join(CFG["giong"]["danh_sach"]),
    }


def build_prompt(sp, n, angles, used, styles, dang=None, mo_dau=None, qc=None, hieu_qua=""):
    return prompt_mau.dien("bien-kich", **ctx_bien_kich(sp, n, angles, used, styles, dang, mo_dau, qc, hieu_qua))


def ctx_xem_thu(ma, sp, n=3):
    """Dữ liệu thật của sản phẩm cho nút "Xem thử" (chọn góc/dạng bài/quy cách đầu danh sách, không ngẫu nhiên, không ghi sổ)."""
    sp_ai = {k: v for k, v in sp.items() if k not in ("kho_video", "loai_tru", "vai_tro_rieng", "cat_khung", "doc_la", "mau_thuong_hieu", "kho_them", "shop_product_id")}
    goc = [g["ma"] for g in sp.get("goc_ban") or []] or ["cong-dung", "cach-dung", "thuong-hieu", "qua-tang"]
    angles = (goc * n)[:n]
    dang = list(DANG_BAI)[:n]
    qcs = [q["ten"] for q in sp.get("quy_cach") or []]
    qc = [qcs[i % len(qcs)] for i in range(n)] if qcs else None
    return ctx_bien_kich(sp_ai, n, angles, cau_cua_sp(ma), recent_styles(), dang, dem_lich_su(f"mo-dau-{ma}.txt"), qc, _tom_tat(ma))


def _chuan(s):
    """So tên không phân biệt hoa thường / dấu câu / khoảng trắng: 'NPK 33-11-11' ~ 'npk 33 11 11'."""
    return " " + " ".join(re.findall(r"\w+", (s or "").lower())) + " "


def ten_phai_nhac(sp):
    """Các cách gọi hợp lệ của sản phẩm (lời đọc phải chứa ít nhất 1): tên ngắn, tên gọi, tên khác."""
    ds = [sp.get("ten_ngan"), sp.get("ten_goi")] + list(sp.get("ten_khac") or [])
    if sp.get("ma") == "nano-dong":
        ds.append("chai nano đồng này")
    return [x for x in ds if isinstance(x, str) and x.strip()]


def check(item, sp, used_norm):
    errs = []
    text = item.get("text", "")
    plain = re.sub(r"\[[^\]]*\]", "", text)
    n = len(re.findall(r"\w+", plain))
    _lo, _hi, nho, lon, _c1, _c2 = khung_am_tiet(sp)
    if not nho <= n <= lon:
        errs.append(f"{n} âm tiết (cần {_lo}–{_hi})")
    if not any(_chuan(nm) in _chuan(plain) for nm in ten_phai_nhac(sp)):
        errs.append("thiếu tên thương hiệu")
    low = " " + plain.lower() + " "
    errs += [f"từ cấm '{b.strip()}'" for b in BANNED
             if re.search(r"(?<!\w)" + re.escape(b.strip()) + r"(?!\w)", low)]   # khớp nguyên từ, không bắt "nha" trong "nhanh"
    sents = [s for s in re.split(r"(?<=[.!?])\s+", plain.strip()) if s.strip()]
    errs += [f"lặp câu: {s[:30]}" for s in sents if norm(s) in used_norm and len(s.split()) >= 4]
    if item.get("giong") not in CFG["giong"]["danh_sach"]:
        item["giong"] = random.choice(list(CFG["giong"]["danh_sach"]))
    if len(item.get("canh", [])) < len(sents):
        item["canh"] = item.get("canh", []) + [{"vai_tro": ["chai_ro"]}] * (len(sents) - len(item.get("canh", [])))
    pcs = item.get("phong_cach") or [{}]
    item["phong_cach"] = pcs if isinstance(pcs, list) else [pcs]
    return errs, sents


def viet(ma_sp, so_ban, log=print):
    sp = json.loads((HUB / "san-pham" / ma_sp / "san-pham.json").read_text(encoding="utf-8"))
    sp_for_ai = {k: v for k, v in sp.items() if k not in ("kho_video", "loai_tru", "vai_tro_rieng", "cat_khung", "doc_la", "mau_thuong_hieu", "kho_them", "shop_product_id")}
    used_norm = {norm(s) for s in history_sentences()}      # máy chống trùng: câu của mọi sản phẩm
    used = cau_cua_sp(ma_sp)                                 # gửi biên kịch: chỉ câu đã dùng của RIÊNG sản phẩm này
    goc = [g["ma"] for g in sp.get("goc_ban") or []] or ["cong-dung", "cach-dung", "thuong-hieu", "qua-tang"]   # sản phẩm mới chưa có góc bán
    out, tries = [], 0
    while len(out) < so_ban and tries < 4:
        tries += 1
        need = min(10, so_ban - len(out))
        dem_g = {g: 0 for g in goc}
        for l in dem_lich_su(f"goc-{ma_sp}.txt"):
            if l in dem_g: dem_g[l] += 1
        hs_g = _he_so(ma_sp, "goc")             # góc từng ra nhiều view được xoay tới sớm hơn (0.7–1.5), thiếu số liệu → đều nhau
        angles = sorted(goc, key=lambda g: (dem_g[g] / hs_g.get(g, 1.0), random.random()))[:need]
        while len(angles) < need: angles.append(random.choice(goc))
        dem_d = {d: 0 for d in DANG_BAI}
        for l in dem_lich_su(f"dang-{ma_sp}.txt"):
            if l in dem_d: dem_d[l] += 1
        hs_d = _he_so(ma_sp, "dang")
        dang = sorted(DANG_BAI, key=lambda d: (dem_d[d] / hs_d.get(d, 1.0), random.random()))[:need]
        qcs = [q["ten"] for q in sp.get("quy_cach") or []]
        if qcs:
            dem_q = {q: 0 for q in qcs}
            for l in dem_lich_su(f"qc-{ma_sp}.txt"):
                if l in dem_q: dem_q[l] += 1
            qc = [sorted(qcs, key=lambda q: (dem_q[q], random.random()))[i % len(qcs)] for i in range(need)]
        else:
            qc = None
        while len(dang) < need: dang.append(random.choice(list(DANG_BAI)))
        log(f"  gọi Claude viết {need} bản (lần {tries})…")
        try:
            items = lay_json(goi("biên kịch", build_prompt(sp_for_ai, need, angles, used, recent_styles(), dang, dem_lich_su(f"mo-dau-{ma_sp}.txt"), qc, _tom_tat(ma_sp)))[0])
        except HetHanMuc:
            raise
        except Exception as e:
            log(f"  lỗi: {e}"); continue
        if isinstance(items, dict):                       # AI bọc mảng trong đối tượng → lấy mảng đầu tiên
            items = next((v for v in items.values() if isinstance(v, list)), [items])
        items = [x for x in (items or []) if isinstance(x, dict) and isinstance(x.get("text"), str)]
        for i_it, it in enumerate(items):
            errs, sents = check(it, sp, used_norm)
            if errs:
                log(f"  loại 1 bản ({it.get('goc')}): {'; '.join(errs)}"); continue
            for s in sents:
                used_norm.add(norm(s)); used.append(s)
            it["dang"] = dang[i_it] if i_it < len(dang) else ""
            ten_qc = qc[i_it] if qc and i_it < len(qc) else None
            it["quy_cach"] = next((q["ma"] for q in sp.get("quy_cach") or [] if q["ten"] == ten_qc), None)
            if ten_qc:
                with open(HUB / "lich-su" / f"qc-{ma_sp}.txt", "a", encoding="utf-8") as f: f.write(ten_qc + "\n")
            def tag(h):                                # #khong dau, khong khoang trang
                import unicodedata
                h = unicodedata.normalize("NFD", str(h).replace("đ", "d").replace("Đ", "D"))
                h = "".join(ch for ch in h if unicodedata.category(ch) != "Mn")
                h = re.sub(r"[^0-9A-Za-z]", "", h).lower()
                return "#" + h if h else ""
            it["hashtag"] = [t for t in dict.fromkeys(tag(h) for h in (it.get("hashtag") or [])) if t][:3]
            cap = it.get("caption") or []
            def gon(c, n=90):                          # luật caption ≤ 90 ký tự, cắt ở ranh giới từ
                c = re.sub(r"\s+", " ", str(c)).strip()
                return c if len(c) <= n else c[:n].rsplit(" ", 1)[0].rstrip(",;:–-") + "…"
            it["captions"] = [gon(c) for c in (cap if isinstance(cap, list) else [cap]) if str(c).strip()] or [""]
            it["caption"] = it["captions"][0]
            with open(HUB / "lich-su" / f"goc-{ma_sp}.txt", "a", encoding="utf-8") as f: f.write(str(it.get("goc")) + "\n")
            with open(HUB / "lich-su" / f"dang-{ma_sp}.txt", "a", encoding="utf-8") as f: f.write(it["dang"] + "\n")
            with open(HUB / "lich-su" / f"mo-dau-{ma_sp}.txt", "a", encoding="utf-8") as f: f.write((sents[0] if sents else "") + "\n")
            out.append(it)
            if len(out) >= so_ban:
                break
    return out
