"""Ê-kíp AI: ĐẠO DIỄN (lên bảng dựng từng câu, NHÌN ảnh cảnh) + GIÁM KHẢO (xem bản dựng, chấm, yêu cầu sửa).
Máy dựng (dung.py / dung_remotion.py) chỉ làm theo bảng dựng; mọi lựa chọn AI đều được máy kiểm lại."""
import datetime, json, math, re, subprocess, threading
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from ai import goi, lay_json
import prompt_mau
from bo_cuc import SO_PHU, la_chai, ep_bo_cuc
import bo_cuc as BC
import cong_thuc as CT
import sfx as SFX
from cong_thuc import RECIPES, DATA_SPEC, ct_cho_dao_dien
from dung import sentence_times, MENU as MENU_NEN
from soat_kho import bad, nguoi_noi
import kiem_may

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, khung_giay
FPS = 30
SO_TAY = lambda: prompt_mau.doc_luat("SO-TAY-EDITOR.md")   # sổ tay editor cao cấp — mọi vai dựng/chấm đọc

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


# ---------------------------------------------------------------- mệt cảnh (chống lặp cảnh qua video)
KHO_NHO = 80              # kho riêng < 80 cảnh dùng được = "kho nhỏ": hạn mức ứng viên chặt hơn, kho chung được thêm rộng hơn
TOI_DA_MOI_CAU = 10       # mặc định ứng viên mỗi câu (gồm cả cảnh kho chung); config dao_dien.ung_vien_moi_cau, trần TRAN_MOI_CAU
TRAN_MOI_CAU = 14
KHUNG_MOI_CANH = 3        # mặc định số khung/ô ứng viên (đầu–giữa–cuối đoạn dùng được); config dao_dien.khung_moi_canh, 1 = ảnh _khung cũ
TRAN_KHUNG = 4
TOI_DA_TO_SHEET = 4       # tối đa 4 tờ ảnh ứng viên
TRAN_KHO_NHO = 0.60       # kho nhỏ: tổng ứng viên riêng của 1 video ≤ 60% kho
TY_BO_MET = 0.35          # bỏ tối đa 35% cảnh MỆT NHẤT khỏi ứng viên (miễn mọi vai trò của cảnh còn đủ cảnh thay)
W_MET = 1.5               # 1 đơn vị mệt = trừ 1,5 điểm liên quan
MU_DUNG_TRON_DOI = 0.7    # phạt theo TỔNG số lần đã dùng (mọi thời điểm) tăng chậm dần: n ** 0,7 (15 lần ≈ 6,7; 4 lần ≈ 2,6)
W_DUNG_TRON_DOI = 2.0     # 1 lần-quy-đổi = 2 đơn vị mệt (×W_MET = 3 điểm): cảnh dùng 15 lần thua cảnh chưa dùng ~30 điểm, 3 lần ~12 điểm → chỉ cảnh hơn hẳn mới thắng nổi
POOL_TOP = 10             # top-5 mỗi câu bốc ngẫu nhiên có trọng số từ 10 cảnh điểm cao nhất (không còn gần như cố định)
NHIET_TOP = 1.5           # trọng số bốc = exp((điểm − điểm cao nhất)/1,5): cảnh hơn 1,5 điểm chỉ còn ~37% cơ hội
SAN_TOP = 6.0             # cảnh thua điểm cao nhất quá 6 điểm không vào pool (chặn cảnh quá yếu)
PHAT_ANH_EM = 6.0         # video anh em (cùng lời) đã dùng cảnh này
PHAT_MO_CHOT = 30.0       # cảnh trùng cảnh mở/chốt của 6 video gần nhất
SO_VIDEO_MO_CHOT = 6
TY_ANH_EM = 0.30          # 2 video cùng lời đọc: tối đa 30% cảnh chung
TY_KHO_THEM_NHO = 0.45    # kho riêng nhỏ: kho chung được chiếm tới 45% (thay vì 30%) số cảnh + ô phụ
TOI_DA_TO = 32            # 1 khung/ô: 1 tờ = 8 cột × 4 hàng ô 190×338 (≤ 1520 px: model không thu nhỏ → ô ≥ 180 px)
MAX_ANH = TOI_DA_TO_SHEET * TOI_DA_TO


def _cfg_dd(khoa, mac_dinh, lo, hi):
    try:
        v = int((cfg_hub().get("dao_dien") or {}).get(khoa, mac_dinh))
    except Exception:
        v = mac_dinh
    return max(lo, min(hi, v))


def moi_cau():
    return _cfg_dd("ung_vien_moi_cau", TOI_DA_MOI_CAU, 3, TRAN_MOI_CAU)


def khung_moi_canh():
    return _cfg_dd("khung_moi_canh", KHUNG_MOI_CANH, 1, TRAN_KHUNG)


FW, FH, GAP, CAO_TO = 128, 228, 2, 1560        # nhiều khung/ô: mỗi khung 128×228, ô = k khung liền nhau, tờ ≤ 1560 px mỗi chiều


def bo_cuc_to(k):
    """(rộng ô, cao ô, số cột, số hàng) của 1 tờ với k khung/ô. k=1: 8×4 ô 190×338 (kiểu cũ)."""
    if k <= 1:
        return 190, 338, 8, 4
    cw, ch = k * FW + (k - 1) * GAP, FH
    return cw, ch, max(1, CAO_TO // cw), max(1, CAO_TO // ch)


def max_anh(k=None):
    cw, ch, cot, hang = bo_cuc_to(khung_moi_canh() if k is None else k)
    return TOI_DA_TO_SHEET * cot * hang


def _ls_dir(hub=None):
    return Path(hub or HUB) / "lich-su"


def doc_lich_su(ma, hub=None):
    """Sổ cảnh đã dùng của sản phẩm, cũ → mới: [{"ngay": date|None, "ids": [cảnh chính], "phu": [cảnh ô phụ]}].
    canh-da-dung-<ma>.txt: mỗi dòng 1 video, KHÔNG có ngày (coi là "cũ"). canh-da-dung-<ma>.jsonl: bản ghi CÓ NGÀY (ghi_lich_su_canh), kèm cả ô phụ.
    Hai sổ cùng được ghi mỗi video: N dòng cuối .txt đã nằm trong .jsonl (N = số bản ghi .jsonl); phần còn lại là sổ không ngày."""
    d = _ls_dir(hub); moi, dong = [], []
    f = d / f"canh-da-dung-{ma}.jsonl"
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(l); moi.append({"ngay": datetime.date.fromisoformat(o["ngay"]), "ids": list(o.get("ids") or []), "phu": list(o.get("phu") or [])})
            except Exception:
                continue
    f = d / f"canh-da-dung-{ma}.txt"
    if f.exists():
        dong = [l.split() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [{"ngay": None, "ids": x, "phu": []} for x in dong[:max(0, len(dong) - len(moi))]] + moi


def id_canh_chinh(segs):
    return [sg["shot"]["id"] for sg in segs or []]


def id_canh_phu(segs):
    return [p["id"] for sg in segs or [] for p in sg.get("phu_shots", [])]


def ghi_lich_su_canh(ma, segs, ma_viec="", hub=None, ngay=None):
    """Thêm 1 bản ghi CÓ NGÀY (cảnh chính + ô phụ) vào canh-da-dung-<ma>.jsonl. Gọi ngay cạnh chỗ ekip ghi dòng .txt của video đó."""
    d = _ls_dir(hub); d.mkdir(parents=True, exist_ok=True)
    o = {"ngay": (ngay or datetime.date.today()).isoformat(), "ids": id_canh_chinh(segs), "phu": id_canh_phu(segs), "viec": ma_viec}
    with open(d / f"canh-da-dung-{ma}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")


def tinh_met(ls, today=None, tranh=(), anh_em=(), hom_nay=()):
    """Độ MỆT của từng cảnh = số lần dùng trong 7 ngày qua (hôm nay ×3, 3 ngày gần ×2, cũ hơn ×1; sổ không ngày: 14 video gần nhất, ×1)
    + PHAT_ANH_EM nếu video anh em đã dùng + hom_nay (id đã dùng ở lô này, mỗi lần ×3). `tranh` (tập cũ) chỉ nâng sàn lên 1.
    (Phạt "đã dùng trong cùng video" áp lúc chọn: cảnh đã dùng không được chọn lại.) → {id: mệt}."""
    today = today or datetime.date.today(); met = {}
    cong = lambda i, w: met.__setitem__(i, met.get(i, 0) + w)
    for r in [r for r in ls if r["ngay"] is None][-14:]:
        for i in r["ids"]:
            cong(i, 1)
    for r in ls:
        if r["ngay"] is None:
            continue
        tuoi = (today - r["ngay"]).days
        w = 3 if tuoi <= 0 else 2 if tuoi <= 3 else 1 if tuoi <= 7 else 0
        if w:
            for i in r["ids"] + r["phu"]:
                cong(i, w)
    for i in tranh:
        met[i] = max(met.get(i, 0), 1)
    for i in hom_nay:
        cong(i, 3)
    for i in set(anh_em):
        cong(i, PHAT_ANH_EM)
    return met


def dem_dung_tron_doi(ls):
    """Tổng số lần mỗi cảnh (chính + ô phụ) từng được dùng trong TOÀN BỘ sổ của sản phẩm → {id: n}. Id không còn trong kho thì bị bỏ qua khi tra."""
    dem = {}
    for r in ls:
        for i in list(r["ids"]) + list(r["phu"]):
            dem[i] = dem.get(i, 0) + 1
    return dem


def mo_chot_gan(ls, n=SO_VIDEO_MO_CHOT):
    """(tập cảnh mở, tập cảnh chốt) của n video gần nhất."""
    g = [r for r in ls if r["ids"]][-n:]
    return {r["ids"][0] for r in g}, {r["ids"][-1] for r in g}


def boi_canh(ma, tranh=(), anh_em=None, hub=None, today=None):
    """Lịch sử dùng cảnh gom 1 chỗ → {"met", "mo", "chot", "anh_em"}.
    tranh: list (có lặp) = cảnh đã dùng ở LÔ này (mỗi lần ×3); set = kiểu cũ (chỉ nâng sàn mệt lên 1).
    anh_em: list CÓ THỨ TỰ cảnh chính của video anh em (hoặc set: mất thứ tự → chỉ phạt cảnh)."""
    ls = doc_lich_su(ma, hub)
    mo, chot = mo_chot_gan(ls)
    anh = list(anh_em or [])
    if isinstance(anh_em, (list, tuple)) and anh:
        mo.add(anh[0]); chot.add(anh[-1])
    soft, lo = (tranh, []) if isinstance(tranh, (set, frozenset)) else ((), list(tranh or []))
    met = tinh_met(ls, today, soft, anh, lo)
    for i, n in dem_dung_tron_doi(ls).items():      # cộng phạt dùng-tron-đời vào độ mệt: cảnh quen mặt (vd. 15/28 video) lùi sau cảnh ít dùng → kho nhỏ xoay vòng đều
        met[i] = met.get(i, 0) + W_DUNG_TRON_DOI * n ** MU_DUNG_TRON_DOI
    return {"met": met, "mo": sorted(mo), "chot": sorted(chot), "anh_em": anh}


def loc_met(ds, met, ty_bo=TY_BO_MET, toi_thieu=6):
    """Bỏ bớt cảnh MỆT NHẤT (≤ ty_bo kho), chỉ khi MỌI vai trò của cảnh đó còn > toi_thieu cảnh → kho nhỏ không bị vét cạn."""
    ds = list(ds); han = int(len(ds) * ty_bo)
    vai = lambda s: set(s.get("vai_tro") or ["_"])
    dem = {}
    for s in ds:
        for v in vai(s):
            dem[v] = dem.get(v, 0) + 1
    giu, bo = list(ds), 0
    for s in sorted(ds, key=lambda s: -met.get(s["id"], 0)):
        if bo >= han or met.get(s["id"], 0) <= 0:
            break
        if all(dem[v] > toi_thieu for v in vai(s)):
            giu.remove(s); bo += 1
            for v in vai(s):
                dem[v] -= 1
    return giu


# ---------------------------------------------------------------- ứng viên cảnh cho từng câu
VAI_TU = {    # vai trò (tên ASCII trong kho) → từ khoá trong lời tiếng Việt có dấu (review #17: trước đây so "chai_ro" với câu có dấu → không bao giờ khớp)
    "chai_ro": ["chai", "gói", "sản phẩm", "nhãn", "bao bì", "chính hãng"], "chai_mo": ["chai", "sản phẩm", "bao bì"],
    "nhan_can": ["nhãn", "thành phần", "công dụng", "hàm lượng", "hướng dẫn", "ghi trên"], "pha_rot": ["pha", "rót", "đổ", "đong", "tỉ lệ", "tỷ lệ", "liều", "bình"],
    "phun": ["phun", "xịt", "tưới", "bình bơm", "sương"], "re": ["rễ", "bộ rễ", "kích rễ"], "cay_con": ["cây con", "cây giống", "giâm", "đọt non", "bầu"],
    "van_de": ["bệnh", "vàng lá", "còi", "chết", "thối", "héo", "nấm", "rụng", "úa", "sâu"], "vuon": ["vườn", "ruộng", "rẫy", "đồi", "cây", "lá"],
    "ket_qua": ["kết quả", "xanh", "tốt", "phát triển", "bung", "đẹp", "năng suất", "sai quả"], "kho_hang": ["kho", "thùng", "kệ", "đóng gói", "giao hàng"],
    "cong_viec": ["làm", "chăm", "nhà vườn", "bà con"], "nguoi_noi": ["chia sẻ", "kể", "người dùng", "khách"], "qua_tang": ["tặng", "quà", "kèm", "biếu"],
}


CAY_RE = {   # cây trồng: mã trong canh.json "cay" ↔ cách nói trong lời (né "mục tiêu", "sáng mai", "cải thiện")
    "ca_phe": r"cà phê|ca_phe", "ho_tieu": r"(?<!mục )\btiêu\b(?! (?:chuẩn|hao|dùng|thụ|diệt|độc|biểu|chí))|ho_tieu",
    "ot": r"\bớt\b|\bot\b", "sau_rieng": r"sầu riêng|sau_rieng", "mai_vang": r"mai vàng|cây mai|vườn mai|gốc mai|mai_vang",
    "rau_mau": r"\brau\b|\bcải\b(?! (?:thiện|tạo|tiến|cách))|dưa leo|rau_mau", "lua": r"\blúa\b|\blua\b",
}
DIEM_CAY = 4
TEN_CAY = {"ca_phe": "cà phê", "ho_tieu": "tiêu", "ot": "ớt", "sau_rieng": "sầu riêng", "mai_vang": "mai vàng", "rau_mau": "rau màu", "lua": "lúa"}


def cay_trong(text):
    t = str(text or "").lower()
    return {k for k, p in CAY_RE.items() if re.search(p, t)}


def _diem_lien_quan(shot, sent, y_canh):
    q = (sent + " " + (y_canh or "")).lower()
    blob = ((shot.get("soat") or {}).get("ghi", "") + " " + shot.get("mo_ta", "") + " " + " ".join(shot.get("the", [])) + " " + (shot.get("noi") or "")).lower()
    toks = {t for t in re.findall(r"\w+", q) if len(t) > 2}
    s = sum(1 for t in toks if t in blob)
    s += 2 * sum(1 for v in shot.get("vai_tro", []) if v.replace("_", " ") in q or v in q or any(k in q for k in VAI_TU.get(v, ())))
    cq, cs = cay_trong(sent), cay_trong(" ".join(map(str, shot.get("cay") or [])))   # lời nhắc cây nào → cảnh đúng cây lên, cảnh cây khác xuống
    if cq and cs:
        s += DIEM_CAY if cq & cs else -DIEM_CAY
    return s + ((shot.get("soat") or {}).get("dep") or 3) * 0.5


def _boc_top(xep, d, k, rng):
    """Bốc k cảnh từ pool (POOL_TOP cảnh đầu của xep) có trọng số exp(điểm/NHIET_TOP), bỏ cảnh thua đầu bảng > SAN_TOP → top-k đổi giữa các video nhưng không lọt cảnh quá yếu.
    d: {id: điểm} của pool. Giữ thứ tự điểm giảm dần."""
    pool = [s for s in xep[:POOL_TOP] if d[s["id"]] >= d[xep[0]["id"]] - SAN_TOP] or xep[:k]
    chon = []
    while pool and len(chon) < k:
        top_d = max(d[s["id"]] for s in pool)
        w = [math.exp((d[s["id"]] - top_d) / NHIET_TOP) for s in pool]
        x = rng.choices(pool, weights=w)[0]
        chon.append(x); pool.remove(x)
    return sorted(chon, key=lambda s: -d[s["id"]])


def ung_vien(sents, y_canh, shots, rng, n_moi_cau=TOI_DA_MOI_CAU, tranh=(), dem_dung=None, met=None, mo_gan=(), chot_gan=()):
    """Ứng viên cho từng câu, xếp theo (liên quan − mệt). KHÔNG còn lọc cứng "đã dùng": cảnh mệt nhất bị loại khỏi danh sách đưa đạo diễn miễn là
    còn đủ cảnh cùng vai trò; mỗi câu ≤ n_moi_cau (n−1 hợp nhất + 1 bất ngờ); kho nhỏ (<80 cảnh) cả video chỉ thấy ≤ 60% kho;
    câu mở không lấy cảnh mở của 6 video gần nhất, câu chốt không lấy cảnh chốt gần nhất.
    met: {id: mệt} (boi_canh). Không có → suy từ dem_dung (đếm cũ, chặn ở 3) + tranh (mệt ≥ 1) cho tương thích."""
    if met is None:
        met = {i: min(c, 3) for i, c in (dem_dung or {}).items()}
        for i in tranh:
            met[i] = max(met.get(i, 0), 1)
    sach = [s for s in shots if s.get("soat") and not bad(s)] or [s for s in shots if not bad(s)] or list(shots)     # không bao giờ rỗng nếu còn cảnh (review #21)
    n, mo_gan, chot_gan = len(sents), set(mo_gan), set(chot_gan)
    if not sach or not n:
        return [[] for _ in sents], {}
    yc = lambda k: y_canh[k] if k < len(y_canh) else ""
    ok = loc_met(sach, met)
    rel = [{s["id"]: _diem_lien_quan(s, st["text"], yc(k)) for s in ok} for k, st in enumerate(sents)]
    if len(sach) < KHO_NHO:                                  # kho nhỏ: chọn trước "bể" ≤ 60% kho cho cả video rồi mới chia theo câu
        tran = max(int(TRAN_KHO_NHO * len(sach)), min(len(sach), n_moi_cau))
        if tran < len(ok):
            g = {s["id"]: 0.6 * max(r[s["id"]] for r in rel) + 0.4 * sum(r[s["id"]] for r in rel) / n - W_MET * met.get(s["id"], 0) + rng.random() * 1.5 for s in ok}
            ok = sorted(ok, key=lambda s: -g[s["id"]])
            chai = [s for s in ok if la_chai(s) and s["id"] not in chot_gan][:3] or [s for s in ok if la_chai(s)][:3]    # luôn giữ vài cảnh chai cho câu chốt
            ok = (chai + [s for s in ok if s not in chai])[:tran]
    chon, per, hien = {}, [], {}
    for k in range(n):
        def diem(s):
            i = s["id"]
            d = rel[k].get(i, 0) - W_MET * met.get(i, 0) - 1.2 * hien.get(i, 0) - rng.random()
            so = s.get("soat") or {}
            if k == 0 and (so.get("chu_muc") or 0) >= 1:   # câu mở: tránh cảnh đã có chữ chèn sẵn (đè chữ móc câu)
                d -= 2.0
            if (so.get("dep") or 3) <= 2:                    # cảnh xấu (điểm máy ≤ 2) chỉ dùng khi thật cần
                d -= 1.0
            return d - (PHAT_MO_CHOT if (k == 0 and i in mo_gan) or (k == n - 1 and i in chot_gan) else 0)
        xep = sorted(ok, key=lambda s: -diem(s))
        top = _boc_top(xep, {s["id"]: diem(s) for s in xep[:POOL_TOP]}, max(1, n_moi_cau - 1), rng)
        con = [s for s in xep if s not in top if met.get(s["id"], 0) <= 1 and not ((k == 0 and s["id"] in mo_gan) or (k == n - 1 and s["id"] in chot_gan))]
        ids = []
        for s in top + rng.sample(con, k=min(1, len(con))):      # 1 cảnh bất ngờ; kho nhỏ có thể không còn gì để thêm
            if s["id"] not in ids:
                ids.append(s["id"]); chon[s["id"]] = s; hien[s["id"]] = hien.get(s["id"], 0) + 1
        per.append(ids)
    return per, chon


def chon_ung_vien(ma, sents, y_canh, shots, rng, tranh=(), anh_em=None, qua=None, chung=None, hub=None, today=None):
    """Toàn bộ khâu chọn ứng viên (không gọi AI, không ghi file) → (per, chon, boi). per[k] = id ứng viên câu k; chon = {id: cảnh}.
    Cảnh kho chung (V-…) thêm 1 cảnh/câu, kho riêng nhỏ (<80 cảnh dùng được) thêm 2 cảnh/câu; tổng ≤ 6/câu. Tổng ảnh ≤ MAX_ANH (2 tờ)."""
    boi = boi_canh(ma, tranh, anh_em, hub, today)
    met, mo, chot = boi["met"], set(boi["mo"]), set(boi["chot"])
    chung = [x for x in (chung or []) if not bad(x)]
    nho = sum(1 for s in shots if s.get("soat") and not bad(s) and not str(s["id"]).startswith(("Q-", "V-"))) < KHO_NHO
    nc = (2 if nho else 1) if chung else 0
    per, chon = ung_vien(sents, y_canh, shots, rng, moi_cau() - nc, met=met, mo_gan=mo, chot_gan=chot)
    n, hien = len(sents), {}
    for k, st in enumerate(sents):
        yc = y_canh[k] if k < len(y_canh) else ""
        def diem(x):
            d = _diem_lien_quan(x, st["text"], yc) - W_MET * met.get(x["id"], 0) - 1.2 * hien.get(x["id"], 0) - rng.random()
            return d - (PHAT_MO_CHOT if (k == 0 and x["id"] in mo) or (k == n - 1 and x["id"] in chot) else 0)
        for x in sorted(chung, key=lambda x: -diem(x))[:nc]:
            chon[x["id"]] = x; per[k].append(x["id"]); hien[x["id"]] = hien.get(x["id"], 0) + 1
    for k, st in enumerate(sents):                      # câu nhắc tới quà (vd. "tặng gói kali bo") → cho đạo diễn cảnh quà thật
        cau = st["text"].lower()
        nhac = [t for t in (qua or {}) if t in cau and re.search(r"tặng|quà|kèm|biếu", cau)]       # chỉ câu nói về QUÀ (lỗi rà soát #7)
        if k == n - 1 and not nhac:                       # mọi video chốt bằng quà → câu chốt luôn có cảnh quà thật để chọn (mỗi món 2 cảnh); lời đã nhắc món nào thì chỉ món đó
            nhac = [t for t in (qua or {}) if any(t in s["text"].lower() and re.search(r"tặng|quà|kèm|biếu", s["text"].lower()) for s in sents)] or list(qua or {})
        for tu_khoa in nhac:
            ds = qua[tu_khoa]
            for x in rng.sample(ds, k=min(3 if len(nhac) == 1 else 2, len(ds))):
                if x["id"] not in per[k]:
                    chon[x["id"]] = x; per[k].append(x["id"])
    aff = sorted([s for s in shots if la_aff(s) and not bad(s, chinh=False) and not str(s["id"]).startswith(("Q-", "V-"))],
                 key=lambda s: (met.get(s["id"], 0), -((s.get("soat") or {}).get("dep") or 3), rng.random()))[:SO_AFF]
    for x in aff:
        chon.setdefault(x["id"], x)
    boi["aff"] = [x["id"] for x in aff]
    tran = max_anh()
    if len(chon) > tran:                                # quá nhiều ảnh: bỏ cảnh MỆT NHẤT (không bỏ quà Q-) cho vừa số tờ tối đa
        for i in sorted([i for i in chon if not str(i).startswith("Q-")], key=lambda i: -met.get(i, 0))[:len(chon) - tran]:
            del chon[i]
        per = [[i for i in p if i in chon] for p in per]
        boi["aff"] = [i for i in boi["aff"] if i in chon]
    NGUON.update(chon)                                  # to_ung_vien cần file/tu/den để cắt khung từ video gốc
    return per, chon, boi


ANH_RIENG = {}
NGUON = {}      # id ứng viên → cảnh (file, tu, den, dep) — điền ở chon_ung_vien


def canh_qua(ma_sp, cfg_kho_qua):
    """Cảnh chai/gói QUÀ TẶNG thật từ kho các sản phẩm khác (đã Chuẩn bị kho). id dạng 'Q-<ma>-<id>', file đường dẫn tuyệt đối."""
    out = {}
    ho = lambda m: "-".join(m.split("-")[:2])
    import unicodedata
    def _chuan(s):
        s = unicodedata.normalize("NFD", str(s).replace("đ", "d").replace("Đ", "D"))
        return " ".join("".join(c for c in s if unicodedata.category(c) != "Mn").lower().split())
    try:                                                # CHỈ quà sản phẩm này thật sự tặng (hồ sơ qua_tang) — không đưa chai sản phẩm khác làm "quà"
        qua_sp = _chuan(" | ".join(json.loads((HUB / "san-pham" / ma_sp / "san-pham.json").read_text(encoding="utf-8")).get("qua_tang") or []))
    except Exception:
        qua_sp = ""
    for tu_khoa, ma in (cfg_kho_qua or {}).items():
        if ma == ma_sp or ho(ma) == ho(ma_sp):          # cùng họ sản phẩm (vd. đạm cá 1L ↔ can 5L) không làm "quà" của nhau
            continue
        if not _chuan(tu_khoa) or _chuan(tu_khoa) not in qua_sp:
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
            x["vai_tro"] = list(s.get("vai_tro", [])) + ["qua_tang"]; x["qua_tu_khoa"] = tu_khoa; x.setdefault("dep", [s["tu"], s.get("den", s["tu"] + s["dai"])])
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


def _nguon_video(ma, sh):
    """Đường dẫn video gốc của cảnh (None nếu không có). Cảnh kho riêng: file tương đối so với kho_video của sản phẩm; quà Q-/kho phụ V-: đã là đường dẫn
    tuyệt đối. Thư mục kho từng bị đổi tên → thử bỏ ' - Copy' khỏi đường dẫn."""
    f = (sh or {}).get("file")
    if not f:
        return None
    p = Path(str(f))
    if not p.is_absolute():
        try:
            kv = json.loads((HUB / "san-pham" / ma / "san-pham.json").read_text(encoding="utf-8")).get("kho_video")
        except Exception:
            kv = None
        if not kv:
            return None
        p = Path(kv) / p
    for q in (p, Path(str(p).replace(" - Copy", ""))):
        if q.exists():
            return q
    return None


def khung_canh(ma, sid, sh, k, dir_cache=None):
    """k khung (đường dẫn jpg 192×342, cắt phủ) của 1 cảnh tại các mốc đầu→cuối đoạn dùng được (dep, không có thì tu–den); cache ở
    <sản phẩm>/_khung3/<id>-<băm>-<j>.jpg. Thiếu nguồn / ffmpeg lỗi → None (người gọi dùng lại ảnh _khung cũ)."""
    src = _nguon_video(ma, sh)
    if not src:
        return None
    dep = sh.get("dep") or [sh.get("tu", 0.0), sh.get("den", sh.get("tu", 0.0) + sh.get("dai", 1.0))]
    a, b = float(dep[0]), float(dep[1])
    if b < a:
        a, b = b, a
    import hashlib
    h = hashlib.md5(f"{src}|{a:.2f}|{b:.2f}|{k}".encode("utf-8")).hexdigest()[:6]
    d = Path(dir_cache or (HUB / "san-pham" / ma / "_khung3")); d.mkdir(parents=True, exist_ok=True)
    out = []
    for j in range(k):
        f = d / f"{sid}-{h}-{j}.jpg"
        if not (f.exists() and f.stat().st_size > 0):
            t = a + (b - a) * (0.08 + 0.84 * j / (k - 1)) if k > 1 else (a + b) / 2
            try:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1",
                                "-vf", "scale=192:342:force_original_aspect_ratio=increase,crop=192:342", "-q:v", "4", str(f)],
                               capture_output=True, timeout=60)
            except Exception:
                pass
        if not (f.exists() and f.stat().st_size > 0):
            return None
        out.append(f)
    return out


def to_ung_vien(ma, ids, out, cols=None, k=None):
    """Tờ ảnh ứng viên cho đạo diễn. k = số khung/ô (mặc định config dao_dien.khung_moi_canh = 3): mỗi ô gồm k khung liền nhau theo thời gian
    (đầu → giữa → cuối đoạn dùng được của cảnh, cắt từ video gốc, có cache); k=1 hoặc thiếu video gốc → ảnh _khung cũ. Tờ ≤ 1560 px mỗi chiều,
    tối đa TOI_DA_TO_SHEET tờ. Trả LIST đường dẫn tờ (tờ 1 = out, tờ 2 = <out>-2.jpg); id rỗng → []. Thiếu cả ảnh → ô xám có số id (không sập)."""
    k = khung_moi_canh() if k is None else max(1, int(k))
    tw, th, c, r = bo_cuc_to(k)
    cols = cols or c
    per_to = cols * r
    d = HUB / "san-pham" / ma / "_khung"
    ids = list(ids)[:TOI_DA_TO_SHEET * per_to]
    if not ids:
        return []
    if k > 1:                                                     # cắt khung song song (ffmpeg), đã có cache thì bỏ qua
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=6) as ex:
            cat = dict(zip(ids, ex.map(lambda sid: khung_canh(ma, sid, NGUON.get(sid), k), ids)))
    else:
        cat = {}
    try:
        font = ImageFont.truetype("arialbd.ttf", 30)
        nho = ImageFont.truetype("arialbd.ttf", 16)
    except Exception:
        font = nho = ImageFont.load_default()
    outs = []
    for t in range(0, len(ids), per_to):
        nhom = ids[t:t + per_to]
        rows = (len(nhom) + cols - 1) // cols
        sheet = Image.new("RGB", ((cols if k <= 1 else min(cols, len(nhom))) * tw, rows * th), "black")
        dr = ImageDraw.Draw(sheet)
        for i, sid in enumerate(nhom):
            x, y = (i % cols) * tw, (i // cols) * th
            fs = cat.get(sid)
            try:
                if fs:                                            # k khung theo thời gian: 1 = đầu, 2 = giữa, … cuối
                    for j, fj in enumerate(fs):
                        xj = x + j * (FW + GAP)
                        sheet.paste(Image.open(fj).convert("RGB").resize((FW, FH)), (xj, y))
                        dr.rectangle([xj, y + FH - 20, xj + 16, y + FH - 1], fill="black"); dr.text((xj + 3, y + FH - 19), str(j + 1), fill="white", font=nho)
                    dr.rectangle([x, y, x + tw - 1, y + th - 1], outline=(255, 200, 0), width=2)
                else:
                    f_anh = ANH_RIENG.get(sid) or (d / f"{sid}.jpg")          # cảnh quà tặng lấy từ kho sản phẩm khác
                    im = Image.open(f_anh).convert("RGB")
                    if k > 1:                                     # ô nhiều khung nhưng chỉ có 1 ảnh: đặt giữa ô
                        sheet.paste(im.resize((FW, FH)), (x + (tw - FW) // 2, y))
                    else:
                        sheet.paste(im.resize((tw, th)), (x, y))
            except Exception:
                dr.rectangle([x, y, x + tw - 1, y + th - 1], fill=(70, 70, 70))
            nhan = sid if len(sid) <= 6 else sid.replace("Q-", "Q:").replace("V-", "V:")
            rong = min(tw - 2, int(dr.textlength(nhan, font=font)) + 12)
            dr.rectangle([x, y, x + rong, y + 38], fill="black"); dr.text((x + 6, y + 3), nhan, fill="yellow", font=font)
        f_out = Path(out) if t == 0 else Path(out).with_name(Path(out).stem + f"-{t // per_to + 1}" + Path(out).suffix)
        sheet.save(f_out, quality=85)
        outs.append(f_out)
    return outs


# ---------------------------------------------------------------- ĐẠO DIỄN
def bai_hoc_cho(ma):
    """Bài học giám khảo gửi đạo diễn: luật CHUNG (mọi sản phẩm) + bài học RIÊNG của đúng sản phẩm đang làm — không lẫn sản phẩm khác."""
    def doc(f, n):          # bỏ bài học cũ về lỗi MÁY (chữ đè nhãn, phụ đề, giỏ hàng, lớp màu…: đạo diễn không sửa được) + gộp bài học na ná nhau
        if not f.exists():
            return []
        dong = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not kiem_may.la_loi_may(l)]
        return kiem_may.gop_tuong_tu(dong)[-n:]
    chung = doc(HUB / "lich-su" / "bai-hoc.txt", 20)
    rieng = doc(HUB / "lich-su" / f"bai-hoc-{ma}.txt", 15)
    if not chung and not rieng:
        return "(chưa có)"
    return "\n".join(chung + (["Riêng sản phẩm này:"] + rieng if rieng else []))


SO_AFF = 10               # số cảnh AFF (người thật cầm/nói về sản phẩm) luôn có trong tờ ứng viên


def la_aff(s):
    """Cảnh AFF: người thật đang cầm / dùng / nói về sản phẩm — bằng chứng người khác cũng mua (Kid 15/11: quý nhất, lệch khẩu hình không sao)."""
    return nguoi_noi(s) and not (s.get("soat") or {}).get("hang_khac")


def tu_danh_so(sents):
    """Lời đọc đánh số TỪNG TỪ (số thứ tự toàn bài) để đạo diễn canh điểm cắt và chữ theo từ: '[0] 0:Khoan 1:đổ …'."""
    out, i = [], 0
    for k, s in enumerate(sents):
        ws = []
        for w in s.get("words") or []:
            ws.append(f"{i}:{w['w']}"); i += 1
        out.append(f"[{k}] " + " ".join(ws))
    return chr(10).join(out)


def khoi_cho_dao_dien():
    """Danh mục khối chữ (sinh từ cong_thuc.mo_ta_khoi) gửi đạo diễn: loại — mô tả | dữ liệu | giới hạn."""
    dong = []
    for loai, m in CT.mo_ta_khoi().items():
        dong.append(f"- {loai} ({m.get('nhom')}): {m.get('mo_ta')} | du_lieu: {json.dumps(m.get('du_lieu'), ensure_ascii=False)} | {m.get('toi_da')}")
    return chr(10).join(dong)


def am_cho_dao_dien():
    try:
        return chr(10).join(f"- {k}: {v}" for k, v in SFX.mo_ta_am().items())
    except Exception:
        return "- khong: không có âm"


COT_DS = "Cột: id | vai trò | cỡ cảnh | mô tả | nói: lời người trong clip lúc đó (chỉ để hiểu cảnh) | dài (s)"


def dong_ds(i, s):
    """1 dòng cảnh ứng viên gửi đạo diễn: id | vai trò[ | NGƯỜI NÓI…] | cỡ cảnh (nếu biết) | mô tả[ | nói: …] | dài.
    Cảnh học kiểu 2 (có phiếu): mô tả đầy đủ ≤ 90 ký tự + lời đang nói; cảnh cũ giữ cách ghi cũ."""
    kieu2 = s.get("kieu") == 2
    mo = (s.get("mo_ta") or "")[:90] if kieu2 and s.get("mo_ta") else ((s.get("soat") or {}).get("ghi") or s.get("mo_ta", "")[:60])
    cot = [str(i), ",".join(s.get("vai_tro", [])) + (" | AFF người thật cầm/nói về sản phẩm" if la_aff(s) else "")]
    if s.get("co_canh"):
        cot.append(str(s["co_canh"]))
    cay = sorted(cay_trong(" ".join(map(str, s.get("cay") or []))))
    cot.append(mo + (f" [cây: {', '.join(TEN_CAY[c] for c in cay)}]" if cay else "") + (" [CÓ CHỮ GỐC trong hình]" if ((s_ := (s.get("soat") or {})).get("chu_muc") or 0) >= 1 else ""))
    if kieu2 and s.get("noi"):
        cot.append("nói: " + str(s["noi"])[:80])
    cot.append(str(s["dai"]))
    return " | ".join(cot)


def ctx_dao_dien(ma, sp, voice, script, shots, gu_key, rng, gop_y="", tranh=(), qua=None, chung=None, anh_em=None, used_sigs=None, ra_boi=None):
    """Dữ liệu điền vào mẫu prompt/dao-dien.md → (ctx, sents, total, ids cảnh ứng viên). Không ghi file, không gọi AI.
    tranh: list cảnh đã dùng ở lô này (hoặc set kiểu cũ). anh_em: list có thứ tự cảnh chính của video anh em cùng lời. used_sigs: chữ ký công thức hôm nay
    (đạo diễn không được mời 2 công thức dùng nhiều nhất). ra_boi (dict) nhận {met, mo, chot, anh_em} để segs_tu_bang dùng cùng số liệu (qua edl["_boi"])."""
    sents = sentence_times(voice["text"], voice["words"])
    total = round(max(voice["dur"] + 0.6, khung_giay(sp)[0] + 0.3), 2)      # khớp dung.render (độ dài đích theo sản phẩm)
    per, chon, boi = chon_ung_vien(ma, sents, script.get("y_canh", []), shots, rng, tranh, anh_em, qua, chung)
    if not chon:
        raise ValueError("kho không có cảnh dùng được để đưa đạo diễn")
    if ra_boi is not None:
        ra_boi.update(boi)
    ids = list(chon)
    try:                                       # công thức đưa đạo diễn: bỏ 2 công thức dùng nhiều nhất hôm nay
        ct_ds = ct_cho_dao_dien(list(used_sigs or []))
    except RuntimeError:
        ct_ds = list(RECIPES)
    so_gu_f = HUB / "lich-su" / "so-gu.md"
    so_gu = so_gu_f.read_text(encoding="utf-8")[-4000:].strip() if so_gu_f.exists() else ""
    so_gu = f"=== SỔ GU CỦA CHỦ HÀNG (bắt buộc tôn trọng) ===\n{so_gu}\n\n" if so_gu else ""      # chưa có sổ gu → không gửi khung trống
    sp_ngan = {k: sp.get(k) for k in ("ten_goi", "ten_ngan", "su_that_duoc_noi", "qua_tang", "khong_duoc_noi", "nhan_dien_chai") if sp.get(k)}
    try:                                  # số liệu thật: gu/công thức dựng nào từng ra nhiều view (gợi ý, không phải luật)
        from hieu_qua import tom_tat
        hq = tom_tat(ma, "dao_dien")
    except Exception:
        hq = ""
    ctx = dict(
        gu=GU[gu_key], so_gu=so_gu, bai_hoc=bai_hoc_cho(ma), so_tay=SO_TAY(), sp=json.dumps(sp_ngan, ensure_ascii=False),
        cau="\n".join(f"[{k}] {s['s']:.1f}–{s['e']:.1f}s: {s['text']}" for k, s in enumerate(sents)),
        total=total, nhan=script.get("nhan_tu", []),
        ds=COT_DS + "\n" + "\n".join(dong_ds(i, chon[i]) for i in ids),
        goi_y=json.dumps({k: v for k, v in enumerate(per)}),
        bo_cuc=chr(10).join(f"- {k}: {v['mo_ta']} (cảnh phụ: {v['phu']}" + (f"–{v['phu_toi_da']}" if v['phu_toi_da'] != v['phu'] else "") + ")" for k, v in BC.mo_ta_bo_cuc().items()),
        tu=tu_danh_so(sents), khoi_mo_ta=khoi_cho_dao_dien(), am=am_cho_dao_dien(),
        aff=json.dumps(boi.get("aff") or [], ensure_ascii=False), don_ban=(script.get("don_ban") or "(biên kịch không ghi)"),
        ct=json.dumps({k: {"ten": r["ten"], "mo": r["mo"], "giua": r["giua"], "chot": r["chot"], "phu_de": r.get("phu_de"), "sfx": r.get("sfx")}
                       for k, r in RECIPES.items() if k in ct_ds}, ensure_ascii=False),
        data_spec=DATA_SPEC, phu_de=["to_dan", "mo_sang", "o_nhay", "gach_chay", "nhich_len", "hop_mo", "quet_mau", "vien_day"],
        mau_nhan=["vang", "xanh_la", "cam", "do", "xanh_duong"], chuyen_canh=MENU_NEN["chuyen_canh"], chuyen_dong=MENU_NEN["chuyen_dong"],
        mau=list(MENU_NEN["mau"]), sfx=["gon", "vua", "soi_dong", "mo_dau_am"],
        nhac=["que-acoustic", "vui-mua-sam", "tvc-doanh-nghiep", "tet-le-hoi", "chill-nen", "piano-nhe"],
        cuoi=len(sents) - 1, n=len(sents),
        so_lieu_tiktok=("\n\n=== SỐ LIỆU THẬT TỪ TIKTOK (gợi ý khi chọn bố cục/nhịp, không phải luật) ===\n" + hq) if hq else "",
        gop_y_giam_khao=f"\n\n=== GIÁM KHẢO YÊU CẦU SỬA BẢN TRƯỚC (bắt buộc làm theo) ===\n{gop_y}" if gop_y else "")
    return ctx, sents, total, ids


def dao_dien(ma, sp, voice, script, shots, gu_key, work, rng, gop_y="", tranh=(), qua=None, chung=None, anh_em=None, used_sigs=None):
    boi = {}
    ctx, sents, total, ids = ctx_dao_dien(ma, sp, voice, script, shots, gu_key, rng, gop_y, tranh, qua, chung, anh_em, used_sigs, boi)
    anh = to_ung_vien(ma, ids, Path(work) / f"ung-vien-{gu_key}.jpg")
    p = prompt_mau.dien("dao-dien", **ctx)
    txt, _ = goi(f"đạo diễn {gu_key}", p, anh=anh)
    edl = lay_json(txt)
    if not isinstance(edl, dict):
        raise ValueError("bảng dựng không phải đối tượng JSON")
    edl["gu"] = gu_key
    edl["_boi"] = {"met": {i: v for i, v in boi.get("met", {}).items() if v > 0}, "mo": boi.get("mo", []), "chot": boi.get("chot", []),
                   "anh_em": boi.get("anh_em", [])}          # segs_tu_bang dùng lại để chọn/đổi cảnh theo cùng độ mệt
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
    plan = {}
    for d in edl.get("doan", []):                    # đạo diễn trả rác (cau không phải số, canh null) → bỏ đoạn đó, không sập (review #1)
        try:
            plan[int(d.get("cau", -1))] = d.get("canh") or []
        except Exception:
            continue
    tu_s = [w["s"] for s in sents for w in (s.get("words") or [])]      # giây bắt đầu của từng từ (số thứ tự toàn bài)
    tu_cau, _i = [], 0
    for s in sents:
        n_w = len(s.get("words") or []); tu_cau.append((_i, _i + n_w)); _i += n_w
    boi = edl.get("_boi") or {}
    met = boi.get("met") or {}
    mo_gan, chot_gan, anh = set(boi.get("mo") or []), set(boi.get("chot") or []), list(boi.get("anh_em") or [])
    phat = lambda s: met.get(s["id"], 0) + (PHAT_ANH_EM if s["id"] in anh else 0)
    dep_ = lambda s: (s.get("soat") or {}).get("dep") or 3
    used, segs, sua = set(), [], []
    for k, (a, b) in enumerate(bounds):
        items = [c for c in plan.get(k, []) if isinstance(c, dict) and k_id(c.get("id", "")) in by]
        items = [c for c in items if k_id(c["id"]) not in used and not bad(by[k_id(c["id"])])]
        span = b - a
        items = items[:max(1, int(span // 1.1))]          # mỗi cảnh ≥ ~1,1 s (lật nhanh thì dùng bố cục lat_trang)
        if not items:   # AI bỏ sót / chọn sai → máy chọn cảnh chai rõ chưa dùng
            sp_shots = [s for s in shots if not str(s["id"]).startswith(("Q-", "V-"))]       # dự phòng chỉ lấy cảnh của chính sản phẩm
            alt = [s for s in sp_shots if not bad(s) and s["id"] not in used and la_chai(s)] or [s for s in sp_shots if not bad(s)] or shots
            alt = sorted(alt, key=lambda s: (phat(s) + (PHAT_MO_CHOT if (k == 0 and s["id"] in mo_gan) or (k == len(sents) - 1 and s["id"] in chot_gan) else 0), -dep_(s)))
            items = [{"id": alt[0]["id"]}]; sua.append(f"câu {k}: thiếu cảnh hợp lệ")
        dur = span / len(items)
        moc = [a + j * dur for j in range(len(items))] + [b]
        try:                                   # đạo diễn ghi "tu" (số thứ tự từ) cho cảnh thứ 2 trở đi → cắt đúng lúc từ đó được đọc
            lo, hi = tu_cau[k]
            cat = [a] + [max(a, tu_s[int(c["tu"])] - 0.08) for c in items[1:]] + [b]
            if all(lo <= int(c["tu"]) < hi for c in items[1:]) and all(cat[j + 1] - cat[j] >= 0.9 for j in range(len(items))):
                moc = cat
        except Exception:
            pass
        for j_c, c in enumerate(items):
            dur = moc[j_c + 1] - moc[j_c]
            sh = by[k_id(c["id"])]; used.add(sh["id"])
            mid = (sh["dep"][0] + sh["dep"][1]) / 2
            start = min(max(sh["tu"], mid - dur / 2), max(sh["tu"], sh["den"] - dur))
            may = c.get("bo_cuc") not in SO_PHU          # đạo diễn không chọn (hoặc chọn sai tên) → máy tự gán, được chạy trần/sàn
            L = c.get("bo_cuc") if not may else "day_zoom"
            if L in ("pip_troi", "pip_giua") and la_chai(sh):
                L = "khung_mo"; sua.append(f"câu {k}: ô trời trên cảnh chai → khung")
            if L == "luoi_4" and (dur < 2.2 or any(sg.get("bo_cuc") == "luoi_4" for sg in segs)):
                L = "chia_doi"
            phu = []
            for pid in c.get("phu") or []:
                pid = k_id(pid)
                if pid in by and pid not in used and not bad(by[pid], chinh=False):
                    phu.append(by[pid]); used.add(pid)
            segs.append({"shot": sh, "src_start": round(start, 2), "dur": round(dur, 3), "bo_cuc": L, "phu_shots": phu[:BC.so_phu_toi_da(L)],
                         "cau": k})
            if may:
                segs[-1]["bo_cuc_may"] = True
    # Câu chốt PHẢI thấy chai sản phẩm (giám khảo bắt lỗi này nhiều nhất): đoạn cuối không phải cảnh chai → đổi sang cảnh chai đẹp chưa dùng
    la_q = lambda s: str(s.get("id", "")).startswith("Q-")
    if segs and (la_q(segs[-1]["shot"]) or (not la_chai(segs[-1]["shot"]) and not la_aff(segs[-1]["shot"]))):       # chốt bằng người thật cầm chai cũng đạt; chai QUÀ không phải chai sản phẩm
        sp_chai = sorted([s for s in shots if not str(s["id"]).startswith(("Q-", "V-")) and la_chai(s) and not bad(s) and s["id"] not in used
                          and not nguoi_noi(s)], key=lambda s: (phat(s) + (PHAT_MO_CHOT if s["id"] in chot_gan else 0), -dep_(s)))
        if sp_chai:
            sh = sp_chai[0]; used.add(sh["id"]); cu = segs[-1]
            mid = (sh["dep"][0] + sh["dep"][1]) / 2
            qua_giu = [s for s in [cu["shot"]] + list(cu.get("phu_shots") or []) if la_q(s)][:1]       # cảnh quà đang có ở đoạn chốt: giữ làm cảnh phụ
            bc = "khung_mo" if cu["bo_cuc"] in ("pip_troi", "pip_giua", "luoi_4") else cu["bo_cuc"]
            if qua_giu and cu["dur"] >= 1.5 and (BC.so_phu_toi_da(bc) < 1 or bc in ("pip_troi", "pip_giua")):
                bc = "chia_ngang"; cu.pop("bo_cuc_may", None)       # kiểu 2 ô (chai chính + quà) đạo diễn-chọn: máy không đổi lại làm mất ô quà
            cu.update(shot=sh, src_start=round(min(max(sh["tu"], mid - cu["dur"] / 2), max(sh["tu"], sh["den"] - cu["dur"])), 2),
                      bo_cuc=bc, phu_shots=qua_giu[:BC.so_phu_toi_da(bc)])
            sua.append("câu chốt: đổi sang cảnh chai rõ" + (", giữ cảnh quà làm ô phụ" if cu["phu_shots"] else ""))
    sua += _doi_mo_chot_anh_em(segs, shots, used, met, mo_gan, chot_gan, anh)
    segs, sua2 = _bu_bo_cuc(segs, shots, used, met)
    own = sum(1 for s in shots if s.get("soat") and not bad(s) and not str(s["id"]).startswith(("Q-", "V-")))
    segs, sua3 = gioi_han_kho_them(segs, shots, used, None if own >= KHO_NHO else TY_KHO_THEM_NHO)   # kho riêng nhỏ: kho chung được nhiều hơn
    return segs, sua + sua2 + sua3


def _dat_canh(sg, moi):
    """Gán cảnh mới cho đoạn (giữ độ dài), sửa bố cục nếu cảnh mới không hợp (ô trời trên chai; người nói full màn)."""
    mid = (moi["dep"][0] + moi["dep"][1]) / 2
    sg["src_start"] = round(min(max(moi["tu"], mid - sg["dur"] / 2), max(moi["tu"], moi["den"] - sg["dur"])), 2)
    sg["shot"] = moi
    if sg["bo_cuc"] in ("pip_troi", "pip_giua") and la_chai(moi):
        sg["bo_cuc"] = "khung_mo"; sg["phu_shots"] = []


def _doi_mo_chot_anh_em(segs, shots, used, met, mo_gan, chot_gan, anh):
    """Máy kiểm lại SAU đạo diễn (đạo diễn chỉ thấy gợi ý): (1) cảnh mở không trùng cảnh mở của 6 video gần nhất / bản anh em,
    (2) cảnh chốt (vẫn phải là chai) không trùng cảnh chốt gần nhất, (3) 2 bản anh em chung ≤ 30% cảnh (ưu tiên đổi cảnh trùng đúng vị trí).
    Chỉ đổi khi có cảnh thay cùng vai trò (chai↔chai, ngoài chai↔ngoài chai); không có thì giữ nguyên (kho quá nhỏ). Trả ghi chú."""
    sua, n, anh_s = [], len(segs), set(anh)
    if not n:
        return sua
    cung = lambda a, b: la_chai(a) == la_chai(b) and (not a.get("vai_tro") or not b.get("vai_tro") or bool(set(a["vai_tro"]) & set(b["vai_tro"])) or la_chai(a))
    muc = lambda s: met.get(s["id"], 0) + (PHAT_ANH_EM if s["id"] in anh_s else 0) - 0.5 * ((s.get("soat") or {}).get("dep") or 3)

    def thay(i, cam):
        cu = segs[i]["shot"]
        pool = [s for s in shots if s["id"] not in used and s["id"] not in cam and not bad(s) and cung(cu, s)
                and (nguoi_noi(s) <= nguoi_noi(cu))]
        if i == n - 1:
            pool = [s for s in pool if la_chai(s) and not nguoi_noi(s)]
        if not pool:
            return False
        moi = min(pool, key=muc)
        used.add(moi["id"]); sua.append(f"đoạn {i}: đổi {cu['id']}→{moi['id']} (chống lặp)")
        _dat_canh(segs[i], moi)
        return True
    if segs[0]["shot"]["id"] in mo_gan:
        thay(0, mo_gan | anh_s | {segs[-1]["shot"]["id"]})
    if n > 1 and segs[-1]["shot"]["id"] in chot_gan:
        thay(n - 1, chot_gan | anh_s | {segs[0]["shot"]["id"]})
    if anh_s:
        han = int(TY_ANH_EM * n + 1e-9)
        chung = [i for i, sg in enumerate(segs) if sg["shot"]["id"] in anh_s]
        chung.sort(key=lambda i: (not (i < len(anh) and anh[i] == segs[i]["shot"]["id"]), i == 0 or i == n - 1))   # trùng đúng vị trí trước
        for i in chung:
            if sum(sg["shot"]["id"] in anh_s for sg in segs) <= han:
                break
            thay(i, anh_s | (mo_gan if i == 0 else set()) | (chot_gan if i == n - 1 else set()))
    return sua


def _bu_bo_cuc(segs, shots, used, met=None):
    """Một lượt ép trần/sàn bố cục lên bảng dựng (bo_cuc.ep_bo_cuc): ≤ 45% khung-trên-nền-mờ, ≥ 35% toàn màn, ≤ 2 đoạn liền cùng kiểu,
    người nói không full màn; bù chia/ô trời/≥ 1/3 không toàn màn chỉ trong giới hạn đó. Ô phụ lấy cảnh ÍT MỆT trước và được ghi vào `used`."""
    import random as _r
    rng = _r.Random(len(segs) * 7 + sum(sum(map(ord, str(sg["shot"]["id"]))) for sg in segs))
    met = met or {}
    phu_pool = [s for s in shots if not bad(s, chinh=False) and s["id"] not in used and not str(s["id"]).startswith("Q-")]   # không chèn chai quà vào ô phụ ngẫu nhiên
    nguoi = [s for s in phu_pool if nguoi_noi(s)]

    def lay_phu(sg, n):
        out = []
        for _ in range(n):
            ds = nguoi if rng.random() < 0.4 and nguoi else phu_pool
            pool = [s for s in ds if s["file"] != sg["shot"]["file"] and s["id"] not in used]
            if la_chai(sg["shot"]):
                pool = [s for s in pool if not la_chai(s)] or pool
            if not pool:
                break
            x = min(pool, key=lambda s: met.get(s["id"], 0) + rng.random() * 2)
            used.add(x["id"]); out.append(x)
        return out
    L, sua = ep_bo_cuc(segs, [sg["bo_cuc"] for sg in segs], rng, lay_phu)
    for sg, k in zip(segs, L):
        if k != sg["bo_cuc"]:
            sg["bo_cuc"] = k
        sg["phu_shots"] = list(sg.get("phu_shots", []))[:BC.so_phu_toi_da(k)]
    return segs, ["bù bố cục: " + x for x in sua]


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


def ctx_giam_khao(sp, sents, edl, may=()):
    """Dữ liệu điền vào mẫu prompt/giam-khao.md. Không gọi AI. may: phát hiện của máy kiểm (kiem_may.kiem) — mục máy đã bắt trượt được báo cho AI bỏ qua."""
    so_gu_f = HUB / "lich-su" / "so-gu.md"
    tom = {"cong_thuc": edl.get("cong_thuc"), "gu": edl.get("gu"), "khoi": [k.get("loai") for k in edl.get("khoi", []) if isinstance(k, dict)],
           "y_tuong": edl.get("ly_do")}
    return dict(so_tay=SO_TAY(), ten=sp.get("ten_ngan") or sp["ten_goi"], cau="\n".join(f"{s['s']:.1f}–{s['e']:.1f}s: {s['text']}" for s in sents),
                tom=json.dumps(tom, ensure_ascii=False), muc=kiem_may.danh_sach_cau_hoi({f["muc"] for f in may or []}),
                so_gu=("SỔ GU CỦA CHỦ HÀNG: " + so_gu_f.read_text(encoding="utf-8")[-2000:].strip() + chr(10)) if so_gu_f.exists() and so_gu_f.read_text(encoding="utf-8").strip() else "")


GK_SONG_SONG_MAC_DINH = 2           # số cuộc trò chuyện Antigravity chấm cùng lúc trong 1 tiến trình
GK_HAN_S = 120                      # chờ Antigravity tối đa chừng này giây cho 1 video
GK_MODEL = "gemini-4-hydrogen-high"
_GK_KHOA = threading.Lock()
_GK_SEM = {"n": 0, "sem": None}
_GK_DA_BAO = set()                  # mỗi lý do chuyển sang Claude chỉ báo 1 lần / tiến trình


def _gk_cau_hinh():
    c = cfg_hub().get("giam_khao") or {}
    c = c if isinstance(c, dict) else {}
    may = str(c.get("may") or "gemini").lower()
    try:
        n = max(1, min(4, int(c.get("song_song") or GK_SONG_SONG_MAC_DINH)))
    except Exception:
        n = GK_SONG_SONG_MAC_DINH
    try:
        han = max(30, int(c.get("han_s") or GK_HAN_S))
    except Exception:
        han = GK_HAN_S
    return {"may": "claude" if may == "claude" else "gemini", "model": str(c.get("model") or GK_MODEL), "song_song": n, "han_s": han}


def _gk_sem(n):
    with _GK_KHOA:
        if _GK_SEM["sem"] is None or _GK_SEM["n"] != n:
            _GK_SEM.update(n=n, sem=threading.BoundedSemaphore(n))
        return _GK_SEM["sem"]


def _gk_bao_mot_lan(khoa, msg):
    if khoa not in _GK_DA_BAO:
        _GK_DA_BAO.add(khoa)
        print(f"  (giám khảo: {msg} → chuyển sang chấm bằng Claude)")


def _gk_json(txt):
    try:
        kq = lay_json(txt)
    except Exception:
        return None
    return kq if isinstance(kq, dict) and ("muc" in kq or "diem" in kq) else None


def cham_gemini(p, anh, work, cfgg, runner=None, video=None):
    """Chấm bằng Gemini qua Antigravity (không tốn API). → dict JSON thô của AI. Ném lỗi nếu Antigravity chưa mở / quá hạn / trả sai
    (người gọi tự chuyển sang Claude). Ảnh (+ video mp4 có tiếng nếu có `video`) + file kết quả đặt trong lich-su/_giam-khao (xoá sau khi đọc);
    tối đa cfgg['song_song'] cuộc cùng lúc. Gemini xem được video và nghe được tiếng nên được đưa cả file video; Claude thì chỉ có ảnh."""
    import hoc_canh as hc
    if runner is None:
        if not hc.trang_thai_agy().get("mo"):
            raise hc.ChuaMo(hc._msg_chua_mo())
        runner = hc.hoi_mot_lan
    import uuid, shutil
    d = HUB / "lich-su" / "_giam-khao"; d.mkdir(parents=True, exist_ok=True)
    ma = uuid.uuid4().hex[:10]
    f_anh, f_out = d / f"{ma}.jpg", d / f"{ma}.json"
    f_vid = d / f"{ma}.mp4" if video and Path(video).is_file() else None
    try:
        shutil.copyfile(anh, f_anh)
        if f_vid:
            shutil.copyfile(video, f_vid)
        pj = None
        try:
            if runner is hc.hoi_mot_lan:
                pj = hc.tim_project(d)
        except Exception:
            pj = None
        goi_y = (f"\n\nTỜ ẢNH CẦN XEM nằm ở file này (mở và xem ảnh): {f_anh}\nGHI KẾT QUẢ vào đúng file này (UTF-8, chỉ JSON thuần, bắt đầu bằng {{ và kết thúc bằng }}): {f_out}\n"
                 "CHỈ được dùng công cụ XEM ảnh/video nêu trên và công cụ GHI đúng 1 file kết quả. KHÔNG chạy lệnh terminal/PowerShell/script, không tìm web, "
                 "không tạo kế hoạch/ghi chú/artifact, không đọc hay ghi file nào khác, không hỏi lại.")
        if f_vid:
            goi_y = (f"\n\nVIDEO THẬT (có tiếng) nằm ở file này — mở XEM và NGHE cả video, không chỉ tờ ảnh: {f_vid}\n"
                     "Chú ý: giọng đọc có khớp hình đúng lúc không; nhạc nền với giọng có cân (nhạc không át giọng); hiệu ứng âm thanh có hợp cảnh; "
                     "nhịp cắt cảnh; chữ trên màn hình có đọc kịp, rõ. Mục nào trượt vì nghe/xem video thì ghi giây xảy ra." + goi_y)
        with _gk_sem(cfgg["song_song"]):
            txt = runner(cfgg["model"], p + goi_y, str(f_out), han=cfgg["han_s"], **({"project": pj} if pj else {}))
        return txt
    finally:
        for f in (f_anh, f_vid, f_out, f_out.with_name(f_out.name + ".tmp")):
            try:
                if f:
                    f.unlink()
            except OSError:
                pass


def _gk_ket(tho, may, co_canh_qua):
    """JSON thô của AI → kết quả đã gộp với máy kiểm; None nếu AI trả hỏng. Đề bài cũ (chỉ có 'diem') vẫn dùng được."""
    if not tho:
        return None
    if tho.get("muc"):
        return kiem_may.hop_nhat(tho, may, co_canh_qua)
    return kiem_may.hop_nhat_cu(tho, may) if tho.get("diem") is not None else None


def cham_claude(p, anh, hop_le=lambda kq: True):
    """Chấm bằng Claude (cách cũ): trả sai định dạng → hỏi lại 1 lần. → dict JSON thô hợp lệ hoặc None."""
    for lan in range(2):
        txt, _ = goi("giám khảo", p, anh=[anh])
        kq = _gk_json(txt)
        if kq is not None and hop_le(kq):
            return kq
        p += "\n\nNHẮC: chỉ trả về đúng 1 đối tượng JSON theo mẫu (có mảng \"muc\"), không chữ nào khác."
    return None


def giam_khao(sp, video, sents, edl, work, segs=None, info=None, props_f=None, co_canh_qua=False, runner=None):
    """Chấm 1 video: (1) máy kiểm trước (kiem_may.kiem, cần segs), (2) AI trả lời danh sách kiểm — mặc định Gemini qua Antigravity, không được thì Claude,
    (3) gộp thành {diem, dat, loi, sua, muc, may, nguon}. diem = 10 × số mục đạt / số mục xét."""
    props = None
    if props_f:
        try:
            props = json.loads(Path(props_f).read_text(encoding="utf-8"))
        except Exception:
            props = None
    may = []
    if segs:
        try:
            may = kiem_may.kiem(segs, sents, info, props, co_qua=bool(sp.get("qua_tang")), co_canh_qua=co_canh_qua)
        except Exception as e:
            print(f"  (máy kiểm trước lỗi: {type(e).__name__}: {str(e)[:80]})")
    anh, _ = to_ban_dung(video, sents, Path(work) / "ban-dung.jpg")
    p = prompt_mau.dien("giam-khao", **ctx_giam_khao(sp, sents, edl, may))
    cg = _gk_cau_hinh()
    kq, nguon = None, "claude"
    if cg["may"] == "gemini":
        try:
            kq = _gk_ket(_gk_json(cham_gemini(p, anh, work, cg, runner, video=video)), may, co_canh_qua)
            if kq is None:
                _gk_bao_mot_lan("sai-dinh-dang", "Gemini trả sai định dạng / thiếu mục kiểm")
            else:
                nguon = "gemini"
        except Exception as e:
            _gk_bao_mot_lan(type(e).__name__, f"Antigravity không chấm được ({str(e)[:90]})")
    if kq is None:
        kq = _gk_ket(cham_claude(p, anh, lambda k: _gk_ket(k, may, co_canh_qua) is not None), may, co_canh_qua)
    if kq is None:
        return {"diem": None, "dat": None, "loi": ["giám khảo chưa chấm được"], "sua": "", "muc": [], "may": may, "nguon": nguon}
    kq["nguon"] = nguon
    return kq
