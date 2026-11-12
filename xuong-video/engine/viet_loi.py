"""Viết lời + phương án dựng bằng Claude CLI headless (mỗi lần gọi là phiên MỚI, không lịch sử chat).
viet(ma_sp, so_ban) -> list kịch bản đã qua kiểm."""
import json, random, re, subprocess
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
CFG = cfg_hub()
from dung_remotion import MENU  # noqa: E402  (menu khâu dựng v2: nền FFmpeg + chữ Remotion)
from cong_thuc import RECIPES, DATA_SPEC  # noqa: E402
from ai import goi, lay_json, HetHanMuc  # noqa: E402

BANNED = ["chữa khỏi", "khỏi hẳn", "100%", "số 1", "số một", "nhất thị trường", "duy nhất", "không độc", "ăn ngay",
          "tham khảo", "xem chi tiết", "tìm hiểu thêm", "đáng cân nhắc", "theo hướng dẫn của", "quy cách rõ ràng",
          "đúng nhu cầu", " nha", " nè", "giá chỉ", "nghìn đồng", "k/chai"]
MUSIC_GROUPS = ["que-acoustic", "vui-mua-sam", "tvc-doanh-nghiep", "tet-le-hoi", "chill-nen", "piano-nhe", "tiktok"]


def history_sentences(limit=400):
    f = HUB / "lich-su" / "cau-da-dung.txt"
    if not f.exists():
        return []
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


def build_prompt(sp, n, angles, used, styles, dang=None, mo_dau=None, qc=None):
    luat = (CODE / "luat" / "LUAT-SAN-XUAT.md").read_text(encoding="utf-8")
    so_gu_f = HUB / "lich-su" / "so-gu.md"
    so_gu = so_gu_f.read_text(encoding="utf-8")[-3000:] if so_gu_f.exists() else "(chưa có)"
    return f"""Bạn là BIÊN KỊCH của ê-kíp video quảng cáo TikTok. Chỉ trả về MỘT mảng JSON hợp lệ, không chữ nào khác.

=== LUẬT (bắt buộc) ===
{luat}

=== SẢN PHẨM (chỉ dùng sự thật ở đây; luat_rieng là bắt buộc) ===
{json.dumps(sp, ensure_ascii=False, indent=1)}

=== SỔ GU CỦA CHỦ HÀNG ===
{so_gu}

=== VIỆC CẦN LÀM ===
Viết {n} kịch bản. Bản thứ i dùng GÓC angles[i] và DẠNG BÀI dang[i] (bắt buộc, theo đúng thứ tự):
angles = {json.dumps(angles, ensure_ascii=False)}
dang = {json.dumps([f"{d}: {DANG_BAI[d]}" for d in (dang or [])], ensure_ascii=False)}
{("quy_cach = " + json.dumps(qc, ensure_ascii=False) + "  ← bản thứ i nói về QUY CÁCH qc[i] (dung tích/đóng gói), chỉ dùng mức quà của ĐÚNG quy cách đó.") if qc else ""}
Các bản phải KHÁC HẲN NHAU và khác các video đã làm: ý chính khác, câu mở khác, hình ảnh cụ thể khác (cây khác, tình huống khác,
giai đoạn khác), nhịp câu khác. KHÔNG mở bài giống/na ná các câu mở đã dùng dưới đây.
Viết như copywriter TVC giỏi nhất: câu ngắn, có lực, có hình ảnh, không sáo rỗng.

CÂU MỞ ĐÃ DÙNG GẦN ĐÂY (cấm lặp ý/khung câu):
{json.dumps((mo_dau or [])[-60:], ensure_ascii=False)}
Mỗi bản 77–86 âm tiết (không tính tag), 4–7 câu, kết bằng câu chốt giỏ hàng + đúng MỘT mức quà (xoay vòng giữa các bản).
Dùng tag giọng đúng luật. Không lặp nguyên câu nào trong CÂU ĐÃ DÙNG.

CÂU ĐÃ DÙNG (không được lặp nguyên văn):
{json.dumps(used[-150:], ensure_ascii=False)}

=== ĐỊNH DẠNG MỖI PHẦN TỬ ===
{{"goc": "<mã góc>", "giong": "XuanLuong|NhatPhong",
 "text": "<lời đọc có tag [..], mỗi câu kết thúc bằng . ! hoặc ?>",
 "dong": ["<dòng phụ đề 1>", ...]  ← chia LỜI ĐỌC (bỏ tag) thành dòng phụ đề theo CỤM Ý trọn nghĩa, 5–10 từ/dòng; ghép lại phải đúng y lời đọc,
 "y_canh": ["<câu 1 nên thấy hình gì, ≤12 từ>", ... đúng bằng số câu],
 "nhan_tu": ["<2–4 từ cần phóng to>"],
 "caption": ["3 caption KHÁC NHAU (mỗi video dùng 1), mỗi cái ≤ 90 ký tự: 1 câu hook mạnh khiến người ta dừng lại + gợi giỏ hàng; không nói giá"],
 "hashtag": ["đúng 3 hashtag tiếng Việt không dấu, sát sản phẩm + cây trồng"]}}
"""


def check(item, sp, used_norm):
    errs = []
    text = item.get("text", "")
    plain = re.sub(r"\[[^\]]*\]", "", text)
    n = len(re.findall(r"\w+", plain))
    if not 74 <= n <= 90:
        errs.append(f"{n} âm tiết")
    names = [x.lower() for x in (sp.get("ten_goi"), sp.get("ten_ngan")) if x] + (["chai nano đồng này"] if sp.get("ma") == "nano-dong" else [])
    if not any(nm in plain.lower() for nm in names):
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
    sp_for_ai = {k: v for k, v in sp.items() if k not in ("kho_video", "loai_tru", "vai_tro_rieng", "cat_khung", "doc_la", "mau_thuong_hieu")}
    used = history_sentences()
    used_norm = {norm(s) for s in used}
    goc = [g["ma"] for g in sp.get("goc_ban") or []] or ["cong-dung", "cach-dung", "thuong-hieu", "qua-tang"]   # sản phẩm mới chưa có góc bán
    out, tries = [], 0
    while len(out) < so_ban and tries < 4:
        tries += 1
        need = min(10, so_ban - len(out))
        dem_g = {g: 0 for g in goc}
        for l in dem_lich_su(f"goc-{ma_sp}.txt"):
            if l in dem_g: dem_g[l] += 1
        angles = sorted(goc, key=lambda g: (dem_g[g], random.random()))[:need]
        while len(angles) < need: angles.append(random.choice(goc))
        dem_d = {d: 0 for d in DANG_BAI}
        for l in dem_lich_su(f"dang-{ma_sp}.txt"):
            if l in dem_d: dem_d[l] += 1
        dang = sorted(DANG_BAI, key=lambda d: (dem_d[d], random.random()))[:need]
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
            items = lay_json(goi("biên kịch", build_prompt(sp_for_ai, need, angles, used, recent_styles(), dang, dem_lich_su(f"mo-dau-{ma_sp}.txt"), qc))[0])
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
