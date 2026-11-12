"""Ê-kíp AI: ĐẠO DIỄN (lên bảng dựng từng câu, NHÌN ảnh cảnh) + GIÁM KHẢO (xem bản dựng, chấm, yêu cầu sửa).
Máy dựng (dung.py / dung_remotion.py) chỉ làm theo bảng dựng; mọi lựa chọn AI đều được máy kiểm lại."""
import json, re, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from ai import goi, lay_json
from bo_cuc import SO_PHU, la_chai
from cong_thuc import RECIPES, DATA_SPEC
from dung import sentence_times, MENU as MENU_NEN
from soat_kho import bad, nguoi_noi

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
FPS = 30
SO_TAY = lambda: (CODE / "luat" / "SO-TAY-EDITOR.md").read_text(encoding="utf-8")   # sổ tay editor cao cấp — mọi vai dựng/chấm đọc

GU = {   # mỗi đạo diễn một gu → cùng lời ra các video khác hẳn nhau
    "tvc_cao_cap": "Đạo diễn TVC cao cấp: nhịp chắc, cảnh đẹp nhất, ít mà sang, chữ gọn, màu sạch, chuyển cảnh mượt; khoe sản phẩm như quảng cáo truyền hình.",
    "viral_soi_dong": "Đạo diễn viral TikTok: mở đầu giật mắt trong 1 giây, nhịp nhanh, nhiều cú cắt, chia khung, zoom đập vào chữ nhấn, SFX dày, năng lượng cao.",
    "ke_chuyen_nha_vuon": "Đạo diễn kể chuyện nhà vườn: chân thật, gần gũi, cảnh vườn và tay người làm, nhịp vừa, cảm giác người thật việc thật.",
    "chuyen_gia_tin_nhanh": "Đạo diễn kiểu chuyên gia/tin nhanh: rõ ràng, nhiều thông tin trực quan (danh sách, số đếm, so sánh), cảnh minh hoạ đúng từng ý.",
}
BO_CUC_MO_TA = {
    "day": "toàn màn hình nguyên cảnh (≤2,8 s, quá thì máy đổi sang phóng cắt)",
    "day_zoom": "phóng cắt 1 vùng của cảnh, toàn màn (đổi khung gốc — chống reup)",
    "pip_troi": "cảnh chính toàn màn + 1 ô cảnh phụ lớn, đặt GIỮA phía trên (vùng trời) (KHÔNG dùng khi cảnh chính là chai cận)",
    "pip_giua": "cảnh chính + ô phụ ngang lớn, đặt GIỮA phía trên (KHÔNG dùng khi cảnh chính là chai cận)",
    "khung_mo": "cảnh thu vào khung bo góc lớn trên nền mờ của chính nó",
    "khung_nho": "khung bo góc nhỏ hơn trên nền mờ",
    "chia_doi": "2 ô trên/dưới (cảnh chính + 1 phụ), ô 2 hiện sau — hợp so sánh trước/sau",
    "chia_ngang": "2 cột cạnh nhau (cảnh chính + 1 phụ)",
    "luoi_4": "lưới 2×2 (cảnh chính + 3 phụ) hiện lần lượt — chỉ 1 lần/video, đoạn ≥ 2,2 s",
}


# ---------------------------------------------------------------- ứng viên cảnh cho từng câu
def _diem_lien_quan(shot, sent, y_canh):
    q = (sent + " " + (y_canh or "")).lower()
    blob = ((shot.get("soat") or {}).get("ghi", "") + " " + shot.get("mo_ta", "") + " " + " ".join(shot.get("the", []))).lower()
    toks = {t for t in re.findall(r"\w+", q) if len(t) > 2}
    s = sum(1 for t in toks if t in blob)
    s += 2 * sum(1 for v in shot.get("vai_tro", []) if v.replace("_", " ") in q or v in q)
    return s + ((shot.get("soat") or {}).get("dep") or 3) * 0.5


def ung_vien(sents, y_canh, shots, rng, n_moi_cau=9, tranh=(), dem_dung=None):
    """Mỗi câu ~9 cảnh: phần lớn liên quan nhất + vài cảnh đẹp ngẫu nhiên để AI có lựa chọn bất ngờ."""
    dung_duoc = [s for s in shots if s.get("soat") and not bad(s) and s["id"] not in tranh] or [s for s in shots if not bad(s)]
    chon, per = {}, []
    for k, st in enumerate(sents):
        yc = y_canh[k] if k < len(y_canh) else ""
        dd = dem_dung or {}
        xep = sorted(dung_duoc, key=lambda s: -_diem_lien_quan(s, st["text"], yc) + 1.5 * dd.get(s["id"], 0) - rng.random() * 1.5)
        top = [s for s in xep[:n_moi_cau * 3] if s["id"] not in chon][:n_moi_cau - 2] or xep[:n_moi_cau - 2]   # kho nhỏ: cho dùng lại ứng viên
        con = [s for s in dung_duoc if s["id"] not in chon and s not in top]
        them = rng.sample(con, k=min(2, len(con)))           # kho nhỏ: có thể không còn cảnh để thêm
        ids = [s["id"] for s in top + them]
        for s in top + them:
            chon[s["id"]] = s
        per.append(ids)
    return per, chon


ANH_RIENG = {}


def canh_qua(ma_sp, cfg_kho_qua):
    """Cảnh chai/gói QUÀ TẶNG thật từ kho các sản phẩm khác (đã Chuẩn bị kho). id dạng 'Q-<ma>-<id>', file đường dẫn tuyệt đối."""
    out = {}
    ho = lambda m: "-".join(m.split("-")[:2])
    for tu_khoa, ma in (cfg_kho_qua or {}).items():
        if ma == ma_sp or ho(ma) == ho(ma_sp):          # cùng họ sản phẩm (vd. đạm cá 1L ↔ can 5L) không làm "quà" của nhau
            continue
        d = HUB / "san-pham" / ma
        if not (d / "canh.json").exists():
            continue
        sp = json.loads((d / "san-pham.json").read_text(encoding="utf-8"))
        ds = []
        for s in json.loads((d / "canh.json").read_text(encoding="utf-8")):
            if not s.get("soat") or bad(s) or nguoi_noi(s) or not ({"chai_ro", "nhan_can"} & set(s.get("vai_tro", []))):
                continue
            x = dict(s); x["id"] = f"Q-{ma}-{s['id']}"; x["file"] = str(Path(sp["kho_video"]) / s["file"])
            x["vai_tro"] = list(s.get("vai_tro", [])) + ["qua_tang"]; x.setdefault("dep", [s["tu"], s.get("den", s["tu"] + s["dai"])])
            ANH_RIENG[x["id"]] = d / "_khung" / f"{s['id']}.jpg"
            ds.append(x)
        if ds:
            out[tu_khoa] = sorted(ds, key=lambda z: -((z.get("soat") or {}).get("dep") or 3))[:12]
    return out


def canh_them(ds_ma):
    """Cảnh từ các KHO PHỤ (kho cảnh dùng chung hoặc kho sản phẩm khác) cho video của một sản phẩm — xem kho_chung.py.
    id 'V-<id>' cho kho đầu, 'V-<chữ a,b,..><id>' cho các kho sau (để không trùng id giữa các kho). Mỗi cảnh có "kho_them" = mã kho.
    Chỉ cảnh đã qua AI soát và dùng được (cùng luật như kho chính). Phụ thôi: segs_tu_bang giới hạn tối đa TY_LE_KHO_THEM số cảnh."""
    from kho_chung import canh_pool
    out = []
    for i, ma in enumerate(ds_ma or []):
        for x in canh_pool(ma, "V-" + ("" if i == 0 else chr(ord("a") + i - 1))):
            ANH_RIENG[x["id"]] = Path(x["_khung_goc"])
            out.append(x)
    return out


def gioi_han_kho_them(segs, shots, used, ty_le=None):
    """Cảnh kho phụ (shot có "kho_them") chỉ làm phụ: tối đa ty_le (mặc định 30%) tổng số cảnh + ô phụ của video.
    Vượt thì đổi phần dư sang cảnh chưa dùng của chính sản phẩm (giữ nguyên bố cục, thời lượng); hết cảnh thay thì bỏ ô phụ."""
    from kho_chung import TY_LE_KHO_THEM
    ty_le = TY_LE_KHO_THEM if ty_le is None else ty_le
    la_them = lambda s: bool(s.get("kho_them"))
    tong = len(segs) + sum(len(sg.get("phu_shots", [])) for sg in segs)
    han = max(1, int(tong * ty_le)) if tong >= 4 else 0
    if sum(la_them(sg["shot"]) + sum(la_them(p) for p in sg.get("phu_shots", [])) for sg in segs) <= han:
        return segs, []
    own = [s for s in shots if not str(s["id"]).startswith(("Q-", "V-")) and not bad(s) and s["id"] not in used]
    own.sort(key=lambda s: -((s.get("soat") or {}).get("dep") or 3))
    sua, dem = [], 0

    def lay(chinh):
        for s in own:
            if s["id"] in used or (chinh and nguoi_noi(s)):
                continue
            if not chinh and bad(s, chinh=False):
                continue
            used.add(s["id"]); return s
        return None
    for sg in segs:                                           # giữ các cảnh kho phụ xuất hiện trước, cắt phần dư ở sau
        for hang in ("shot", "phu"):
            ds = [sg["shot"]] if hang == "shot" else list(sg.get("phu_shots", []))
            for sh in ds:
                if not la_them(sh):
                    continue
                dem += 1
                if dem <= han:
                    continue
                moi = lay(hang == "shot")
                if hang == "shot":
                    if not moi:
                        continue
                    mid = (moi["dep"][0] + moi["dep"][1]) / 2
                    sg["src_start"] = round(min(max(moi["tu"], mid - sg["dur"] / 2), max(moi["tu"], moi["den"] - sg["dur"])), 2)
                    sg["shot"] = moi
                    if sg["bo_cuc"] in ("pip_troi", "pip_giua") and la_chai(moi):
                        sg["bo_cuc"] = "khung_mo"
                    if nguoi_noi(moi) and sg["bo_cuc"] in ("day", "day_zoom", "pip_troi", "pip_giua"):
                        sg["bo_cuc"] = "khung_nho"
                else:
                    sg["phu_shots"] = [moi if p is sh else p for p in sg["phu_shots"]] if moi else [p for p in sg["phu_shots"] if p is not sh]
                    if len(sg["phu_shots"]) < SO_PHU[sg["bo_cuc"]]:
                        sg["bo_cuc"] = "khung_mo"; sg["phu_shots"] = []
                sua.append(f"giới hạn kho phụ ≤{int(ty_le * 100)}%: câu {sg['cau']} đổi cảnh")
    return segs, sua


def to_ung_vien(ma, ids, out, cols=8):
    d = HUB / "san-pham" / ma / "_khung"
    tw, th = 200, 356
    rows = (len(ids) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), "black")
    try:
        font = ImageFont.truetype("arialbd.ttf", 30)
    except Exception:
        font = ImageFont.load_default()
    dr = ImageDraw.Draw(sheet)
    for i, sid in enumerate(ids):
        x, y = (i % cols) * tw, (i // cols) * th
        f_anh = ANH_RIENG.get(sid) or (d / f"{sid}.jpg")          # cảnh quà tặng lấy từ kho sản phẩm khác
        sheet.paste(Image.open(f_anh).resize((tw, th)), (x, y))
        nhan = sid if len(sid) <= 6 else sid.replace("Q-", "Q:").replace("V-", "V:")
        rong = min(tw - 2, int(dr.textlength(nhan, font=font)) + 12)
        dr.rectangle([x, y, x + rong, y + 38], fill="black"); dr.text((x + 6, y + 3), nhan, fill="yellow", font=font)
    sheet.save(out, quality=85)
    return out


# ---------------------------------------------------------------- ĐẠO DIỄN
PROMPT_DD = """=== SỔ TAY EDITOR CAO CẤP (bắt buộc) ===
{so_tay}

=== GU CỦA BẠN ===
{gu}

=== SỔ GU CỦA CHỦ HÀNG (bắt buộc tôn trọng) ===
{so_gu}

=== BÀI HỌC TỪ GIÁM KHẢO (lỗi các bản trước — TRÁNH lặp lại) ===
{bai_hoc}
- Khối chữ/phụ đề không được che chữ trên nhãn chai: câu có khối chữ giữa bài nên dùng cảnh vườn/rễ/phun, hoặc bố cục khung_nho.
- Lời nói tới thứ gì (rễ, nhãn thành phần, cây con, phun…) thì hình PHẢI thấy đúng thứ đó.

=== SẢN PHẨM ===
{sp}

=== LỜI ĐỌC (đã có giọng, mốc thời gian từng câu, đơn vị giây) ===
{cau}
Tổng thời lượng video: {total} s. Chữ nhấn do biên kịch đề xuất: {nhan}

=== CẢNH ỨNG VIÊN ===
Xem tờ ảnh (số vàng = id). Danh sách: id | vai trò | mô tả | dài (s)
{ds}
Gợi ý theo câu (không bắt buộc): {goi_y}

=== VIỆC CẦN LÀM ===
Lên BẢNG DỰNG cho video này theo gu của bạn. Chọn cảnh NHÌN ĐÚNG ý từng câu (đọc tới đâu, hình tới đó), mở đầu phải giật mắt,
câu chốt phải có cảnh chai sản phẩm rõ nhãn. Không dùng 1 cảnh 2 lần. Mỗi câu 1–2 cảnh; mỗi cảnh ≥ 1,8 s (thường 2–3,5 s) — Kid: không chuyển cảnh quá nhanh, để người xem kịp nhìn.
Chống reup: không để cảnh nguyên khung toàn màn quá 2,8 s — đổi bố cục.
ĐA DẠNG BỐ CỤC (bắt buộc): ít nhất 1/3 số đoạn dùng khung/ô/chia (khung_mo, khung_nho, pip_troi, pip_giua, chia_doi, chia_ngang, luoi_4);
mỗi video có ≥ 1 lần chia_doi/chia_ngang/luoi_4 (ô phụ lấy cảnh khác: người dùng sản phẩm, vườn, rễ…) và ≥ 1 ô trời (pip_troi/pip_giua)
trên cảnh vườn có trời. Cảnh NGƯỜI NÓI (AFF dùng sản phẩm) rất nên dùng làm ô phụ hoặc trong khung — tăng chân thật.

BỐ CỤC: {bo_cuc}
CÔNG THỨC DỰNG (chọn 1): {ct}
{data_spec}
MENU: phu_de={phu_de}; mau_nhan={mau_nhan}; chuyen_canh={chuyen_canh}; chuyen_dong={chuyen_dong}; mau={mau}; sfx={sfx}; nhac={nhac}

Trả về DUY NHẤT 1 đối tượng JSON:
{{"cong_thuc":"..","phu_de":"..","mau_nhan":"..","chuyen_canh":"..","chuyen_dong":"..","mau":"..","sfx":"..","nhac":"..",
 "nhan_tu":["2–4 từ cần phóng to"],
 "khoi":[{{"loai":"<khối mở của công thức>","cau":0,"du_lieu":{{..}}}}, {{"loai":"<0–2 khối giữa>","cau":<k>,"du_lieu":{{..}}}}, {{"loai":"<khối chốt>","cau":{cuoi},"du_lieu":{{..}}}}],
 "doan":[{{"cau":0,"canh":[{{"id":"<id>","bo_cuc":"<bố cục>","phu":["<id ô phụ nếu bố cục cần>"]}}]}}, ... đủ {n} câu],
 "ly_do":"≤12 từ: ý tưởng dựng"}}"""


def dao_dien(ma, sp, voice, script, shots, gu_key, work, rng, gop_y="", tranh=(), qua=None, chung=None):
    sents = sentence_times(voice["text"], voice["words"])
    total = round(max(voice["dur"] + 0.6, 20.3), 2)
    f_dd = HUB / "lich-su" / f"canh-da-dung-{ma}.txt"
    dem_dung = {}
    if f_dd.exists():
        for i in f_dd.read_text(encoding="utf-8").split():
            dem_dung[i] = dem_dung.get(i, 0) + 1
    per, chon = ung_vien(sents, script.get("y_canh", []), shots, rng, tranh=tranh, dem_dung=dem_dung)
    if chung:                                           # cảnh vườn dùng chung: mỗi câu thêm 2 cảnh vườn hợp ý nhất
        yc = script.get("y_canh", [])
        for k, st in enumerate(sents):
            xep = sorted([x for x in chung if x["id"] not in chon and x["id"] not in tranh],
                         key=lambda x: -_diem_lien_quan(x, st["text"], yc[k] if k < len(yc) else "") - rng.random())
            for x in xep[:2]:
                chon[x["id"]] = x; per[k].append(x["id"])
    for k, st in enumerate(sents):                      # câu nhắc tới quà (vd. "tặng gói kali bo") → cho đạo diễn cảnh quà thật
        for tu_khoa, ds in (qua or {}).items():
            cau = st["text"].lower()
            if tu_khoa in cau and re.search(r"tặng|quà|kèm|biếu", cau):          # chỉ câu nói về QUÀ (lỗi rà soát #7)
                for x in rng.sample(ds, k=min(3, len(ds))):
                    chon[x["id"]] = x; per[k].append(x["id"])
    ids = list(chon)
    anh = to_ung_vien(ma, ids, Path(work) / f"ung-vien-{gu_key}.jpg")
    so_gu_f = HUB / "lich-su" / "so-gu.md"
    so_gu = so_gu_f.read_text(encoding="utf-8")[-4000:] if so_gu_f.exists() else "(chưa có)"
    sp_ngan = {k: sp.get(k) for k in ("ten_goi", "su_that_duoc_noi", "qua_tang", "khong_duoc_noi", "nhan_dien_chai")}
    bh_f = HUB / "lich-su" / "bai-hoc.txt"
    bai_hoc = "\n".join(bh_f.read_text(encoding="utf-8").splitlines()[-30:]) if bh_f.exists() else "(chưa có)"
    p = PROMPT_DD.format(
        gu=GU[gu_key], so_gu=so_gu, bai_hoc=bai_hoc, so_tay=SO_TAY(), sp=json.dumps(sp_ngan, ensure_ascii=False),
        cau="\n".join(f"[{k}] {s['s']:.1f}–{s['e']:.1f}s: {s['text']}" for k, s in enumerate(sents)),
        total=total, nhan=script.get("nhan_tu", []),
        ds="\n".join(f"{i} | {'QUÀ TẶNG THẬT (dùng ở câu nhắc quà) | ' if i.startswith('Q-') else ('CẢNH KHO PHỤ (b-roll, chỉ làm cảnh phụ/chuyển ý, không quá ~30% số cảnh) | ' if i.startswith('V-') else '')}{','.join(chon[i]['vai_tro'])}{' | NGƯỜI NÓI (chỉ đặt trong khung/ô)' if nguoi_noi(chon[i]) else ''} | {(chon[i].get('soat') or {}).get('ghi') or chon[i]['mo_ta'][:60]} | {chon[i]['dai']}"
                     for i in ids),
        goi_y=json.dumps({k: v for k, v in enumerate(per)}),
        bo_cuc=json.dumps(BO_CUC_MO_TA, ensure_ascii=False),
        ct=json.dumps({k: {"ten": r["ten"], "mo": r["mo"], "giua": r["giua"], "chot": r["chot"], "phu_de": r.get("phu_de"), "sfx": r.get("sfx")}
                       for k, r in RECIPES.items()}, ensure_ascii=False),
        data_spec=DATA_SPEC, phu_de=["to_dan", "mo_sang", "o_nhay", "gach_chay", "nhich_len", "hop_mo", "quet_mau", "vien_day"],
        mau_nhan=["vang", "xanh_la", "cam", "do", "xanh_duong"], chuyen_canh=MENU_NEN["chuyen_canh"], chuyen_dong=MENU_NEN["chuyen_dong"],
        mau=list(MENU_NEN["mau"]), sfx=["gon", "vua", "soi_dong", "mo_dau_am"],
        nhac=["que-acoustic", "vui-mua-sam", "tvc-doanh-nghiep", "tet-le-hoi", "chill-nen", "piano-nhe"],
        cuoi=len(sents) - 1, n=len(sents))
    try:                                  # số liệu thật: gu/công thức dựng nào từng ra nhiều view (gợi ý, không phải luật)
        from hieu_qua import tom_tat
        hq = tom_tat(ma, "dao_dien")
    except Exception:
        hq = ""
    if hq:
        p += "\n\n=== SỐ LIỆU THẬT TỪ TIKTOK (gợi ý khi chọn bố cục/nhịp, không phải luật) ===\n" + hq
    if gop_y:
        p += f"\n\n=== GIÁM KHẢO YÊU CẦU SỬA BẢN TRƯỚC (bắt buộc làm theo) ===\n{gop_y}"
    txt, _ = goi(f"đạo diễn {gu_key}", p, anh=[anh])
    edl = lay_json(txt)
    if not isinstance(edl, dict):
        raise ValueError("bảng dựng không phải đối tượng JSON")
    edl["gu"] = gu_key
    return edl, sents, total


def segs_tu_bang(edl, sents, total, shots):
    """Bảng dựng của AI → các đoạn cảnh cho máy dựng. Máy kiểm: id có thật, không lỗi, không trùng, độ dài hợp lý."""
    by = {s["id"]: s for s in shots}
    w = len(shots[0]["id"]) if shots else 4          # id 3 chữ số (Nano Đồng) hoặc 4 (kho mới)
    def k_id(x):                                     # id lệch độ dài (3/4 chữ số) hay nhãn Q:/V: → tìm đúng cảnh
        x = str(x).strip().replace("Q:", "Q-").replace("V:", "V-")
        if x in by:
            return x
        for z in (x.zfill(w), x.zfill(3), x.zfill(4), x.lstrip("0").zfill(3), x.lstrip("0").zfill(4)):
            if z in by:
                return z
        return x
    bounds = []
    for k, s in enumerate(sents):
        a = 0.0 if k == 0 else (sents[k - 1]["e"] + s["s"]) / 2
        b = total if k == len(sents) - 1 else (s["e"] + sents[k + 1]["s"]) / 2
        bounds.append((a, b))
    plan = {int(d.get("cau", -1)): d.get("canh", []) for d in edl.get("doan", []) if isinstance(d, dict)}
    used, segs, sua = set(), [], []
    for k, (a, b) in enumerate(bounds):
        items = [c for c in plan.get(k, []) if isinstance(c, dict) and k_id(c.get("id", "")) in by]
        items = [c for c in items if k_id(c["id"]) not in used and not bad(by[k_id(c["id"])])]
        span = b - a
        items = items[:max(1, int(span // 1.8))]          # mỗi cảnh ≥ 1,8 s (Kid: chậm lại 0,5–1 s)
        if not items:   # AI bỏ sót / chọn sai → máy chọn cảnh chai rõ chưa dùng
            sp_shots = [s for s in shots if not str(s["id"]).startswith(("Q-", "V-"))]       # dự phòng chỉ lấy cảnh của chính sản phẩm
            alt = [s for s in sp_shots if not bad(s) and s["id"] not in used and la_chai(s)] or [s for s in sp_shots if not bad(s)] or shots
            items = [{"id": alt[0]["id"], "bo_cuc": "khung_mo"}]; sua.append(f"câu {k}: thiếu cảnh hợp lệ")
        dur = span / len(items)
        for c in items:
            sh = by[k_id(c["id"])]; used.add(sh["id"])
            mid = (sh["dep"][0] + sh["dep"][1]) / 2
            start = min(max(sh["tu"], mid - dur / 2), max(sh["tu"], sh["den"] - dur))
            L = c.get("bo_cuc") if c.get("bo_cuc") in SO_PHU else "day_zoom"
            if L in ("pip_troi", "pip_giua") and la_chai(sh):
                L = "khung_mo"; sua.append(f"câu {k}: ô trời trên cảnh chai → khung")
            if nguoi_noi(sh) and L in ("day", "day_zoom", "pip_troi", "pip_giua"):   # người nói: đặt trong khung, không full màn
                L = "khung_nho"
            if L == "day" and dur > 2.8:
                L = "day_zoom"
            if L == "luoi_4" and (dur < 2.2 or any(sg.get("bo_cuc") == "luoi_4" for sg in segs)):
                L = "chia_doi"
            phu = []
            for pid in c.get("phu") or []:
                pid = k_id(pid)
                if pid in by and pid not in used and not bad(by[pid], chinh=False):
                    phu.append(by[pid]); used.add(pid)
            segs.append({"shot": sh, "src_start": round(start, 2), "dur": round(dur, 3), "bo_cuc": L, "phu_shots": phu[:SO_PHU[L]],
                         "cau": k})
    # Câu chốt PHẢI thấy chai sản phẩm (giám khảo bắt lỗi này nhiều nhất): đoạn cuối không phải cảnh chai → đổi sang cảnh chai đẹp chưa dùng
    if segs and not la_chai(segs[-1]["shot"]):
        sp_chai = sorted([s for s in shots if not str(s["id"]).startswith(("Q-", "V-")) and la_chai(s) and not bad(s) and s["id"] not in used
                          and not nguoi_noi(s)], key=lambda s: -((s.get("soat") or {}).get("dep") or 3))
        if sp_chai:
            sh = sp_chai[0]; used.add(sh["id"]); cu = segs[-1]
            mid = (sh["dep"][0] + sh["dep"][1]) / 2
            cu.update(shot=sh, src_start=round(min(max(sh["tu"], mid - cu["dur"] / 2), max(sh["tu"], sh["den"] - cu["dur"])), 2),
                      bo_cuc="khung_mo" if cu["bo_cuc"] in ("pip_troi", "pip_giua", "luoi_4") else cu["bo_cuc"], phu_shots=[])
            sua.append("câu chốt: đổi sang cảnh chai rõ")
    segs, sua2 = _bu_bo_cuc(segs, shots, used)
    segs, sua3 = gioi_han_kho_them(segs, shots, used)          # kho phụ chỉ là cảnh phụ (≤ 30%)
    return segs, sua + sua2 + sua3


def _bu_bo_cuc(segs, shots, used):
    """Máy bù nếu đạo diễn dùng quá nhiều toàn màn: ≥ 1/3 đoạn là khung/ô/chia, ≥ 1 chia 2/lưới, ≥ 1 ô trời khi có cảnh vườn."""
    import random as _r
    rng = _r.Random(len(segs) * 7 + sum(sum(map(ord, str(sg["shot"]["id"]))) for sg in segs))
    sua = []
    toan = ("day", "day_zoom")
    chai = {"chai_ro", "nhan_can", "kho_hang"}
    phu_pool = [s for s in shots if not bad(s, chinh=False) and s["id"] not in used and not str(s["id"]).startswith("Q-")]   # không chèn chai quà vào ô phụ ngẫu nhiên
    nguoi = [s for s in phu_pool if nguoi_noi(s)]

    def lay_phu(n, main):
        out = []
        for _ in range(n):
            pool = [s for s in (nguoi if rng.random() < 0.5 and nguoi else phu_pool) if s["file"] != main["file"] and s["id"] not in used]
            if not pool:
                break
            x = rng.choice(pool); used.add(x["id"]); out.append(x)
        return out

    def doi(sg, L):
        need = SO_PHU[L] - len(sg.get("phu_shots", []))
        sg["phu_shots"] = (sg.get("phu_shots", []) + lay_phu(max(0, need), sg["shot"]))[:SO_PHU[L]]
        if len(sg["phu_shots"]) < SO_PHU[L]:
            return False
        sua.append(f"bù bố cục: {sg['bo_cuc']}→{L}"); sg["bo_cuc"] = L
        return True
    co = lambda Ls: any(sg["bo_cuc"] in Ls for sg in segs)
    ung = [sg for sg in segs[1:-1] if sg["bo_cuc"] in toan]          # giữ câu mở + câu chốt gọn
    rng.shuffle(ung)
    if not co(("chia_doi", "chia_ngang", "luoi_4")):
        for sg in ung:
            if sg["dur"] >= 1.5 and doi(sg, "chia_doi" if rng.random() < 0.6 else "chia_ngang"):
                break
    if not co(("pip_troi", "pip_giua")):
        for sg in ung:
            if sg["bo_cuc"] in toan and not la_chai(sg["shot"]) and not nguoi_noi(sg["shot"]) and doi(sg, rng.choice(["pip_troi", "pip_giua"])):
                break
    for sg in ung:
        if sum(1 for x in segs if x["bo_cuc"] not in toan) >= len(segs) / 3:
            break
        if sg["bo_cuc"] in toan:
            doi(sg, rng.choice(["khung_mo", "khung_nho", "chia_doi"] if sg["dur"] >= 1.5 else ["khung_mo", "khung_nho"]))
    return segs, sua


# ---------------------------------------------------------------- GIÁM KHẢO
def to_ban_dung(video, sents, out, blocks=None):
    """Ảnh soát bản dựng: 1 khung ở ~65% mỗi câu (khối chữ có hiệu ứng đã hiện đủ) (+ đầu/cuối), có ghi số câu."""
    def moc(s):                       # 65% câu, kẹp trong câu (cách mép 0,05 s nếu câu đủ dài)
        a, b = s["s"], s["e"]
        t = a + 0.65 * (b - a)
        if b - a > 0.1:
            t = min(max(t, a + 0.05), b - 0.05)
        return round(t, 2)
    ts = [0.5] + [moc(s) for s in sents] + [round(sents[-1]["e"] - 0.2, 2)]
    tmp = Path(out).with_suffix(""); tmp.mkdir(exist_ok=True)
    ims = []
    for i, t in enumerate(ts):
        f = tmp / f"{i:02d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=270:480", str(f)])
        if f.exists():
            ims.append((t, f))
    cols = 6; rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 270, rows * 480), "black"); dr = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arialbd.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
    for i, (t, f) in enumerate(ims):
        x, y = (i % cols) * 270, (i // cols) * 480
        sheet.paste(Image.open(f), (x, y)); dr.rectangle([x, y, x + 120, y + 34], fill="black")
        dr.text((x + 5, y + 3), f"{t:.1f}s", fill="yellow", font=font)
    sheet.save(out, quality=85)
    return out, ts


PROMPT_GK = """Bạn là editor trưởng chấm bản dựng video quảng cáo {ten}, theo SỔ TAY EDITOR CAO CẤP dưới đây.
{so_tay}
 Xem tờ ảnh: mỗi ô là 1 khung của video ở giây ghi góc trên trái.
Lời đọc theo thời gian:
{cau}
Bảng dựng đạo diễn đã làm (tóm tắt): {tom}
SỔ GU CỦA CHỦ HÀNG: {so_gu}

Chấm theo tiêu chí: (1) hình hợp lời (đủ phù hợp là được, không khắt khe); (2) mở đầu giật mắt; (3) câu chốt thấy rõ chai {ten}; (4) chữ/khối không che sản phẩm,
không đè nhau, đọc được; (5) người đang nói chỉ được nằm trong khung/ô (không full màn), không chữ chèn to che hình, không hàng khác; (6) đẹp, sang, đa dạng, không nhàm; (7) không lỗi hình (tối, mờ, méo).
Trả về DUY NHẤT JSON, NGẮN GỌN: {{"diem": 1-10, "dat": true|false (đạt khi ≥ 7 và không lỗi nặng), "loi": ["tối đa 3 lỗi nặng nhất, mỗi lỗi ≤ 12 từ, có giây"],
"sua": "≤ 35 từ chỉ dẫn đổi cảnh/bố cục; rỗng nếu đạt"}}"""


def giam_khao(sp, video, sents, edl, work):
    anh, _ = to_ban_dung(video, sents, Path(work) / "ban-dung.jpg")
    so_gu_f = HUB / "lich-su" / "so-gu.md"
    tom = {"cong_thuc": edl.get("cong_thuc"), "gu": edl.get("gu"), "khoi": [k.get("loai") for k in edl.get("khoi", []) if isinstance(k, dict)],
           "y_tuong": edl.get("ly_do")}
    p = PROMPT_GK.format(so_tay=SO_TAY(), ten=sp["ten_goi"], cau="\n".join(f"{s['s']:.1f}–{s['e']:.1f}s: {s['text']}" for s in sents),
                         tom=json.dumps(tom, ensure_ascii=False),
                         so_gu=so_gu_f.read_text(encoding="utf-8")[-2000:] if so_gu_f.exists() else "(chưa có)")
    for lan in range(2):                 # trả sai định dạng → hỏi lại 1 lần; vẫn sai thì để trống điểm (không ghi 0 gây hiểu nhầm)
        txt, _ = goi("giám khảo", p, anh=[anh])
        try:
            kq = lay_json(txt)
            if isinstance(kq, dict) and "diem" in kq:
                return kq
        except Exception:
            pass
        p += "\n\nNHẮC: chỉ trả về đúng 1 đối tượng JSON theo mẫu, không chữ nào khác."
    return {"diem": None, "dat": None, "loi": ["giám khảo chưa chấm được"], "sua": ""}
