"""GIÁM KHẢO THEO DANH SÁCH KIỂM + MÁY KIỂM TRƯỚC (Kid 14/11/2026).
Trước đây giám khảo chấm 1–10 "cảm tính" nên điểm dồn ở 5–6, lỗi lặp mãi và không ai biết lỗi do ai. Nay:
  1. Danh sách kiểm CỐ ĐỊNH (MUC): mỗi mục đạt / trượt + lý do ngắn + giây. Điểm = round(10 × số mục đạt / số mục được xét, 1).
  2. Máy tự đo những gì đo được (người nói full màn, chữ đè nhãn, lặp cảnh, thiếu cảnh quà ở câu chốt, cảnh đứng yên quá lâu...)
     TRƯỚC khi gọi AI → mục bị máy bắt là TRƯỢT, AI không cần xem lại.
  3. Mỗi mục có "người sửa được": "dao_dien" (chọn cảnh, nhịp, ý móc câu, hình khớp lời, bố cục) hay "may" (mã dựng/dữ liệu kho:
     chữ đè nhãn, lớp màu, thiếu cảnh quà trong kho, nút giỏ hàng, vùng an toàn). Chỉ lỗi của đạo diễn mới thành BÀI HỌC;
     lỗi máy ghi sang lich-su/loi-may.jsonl để người làm mã xem, KHÔNG đưa cho đạo diễn.
Module thuần tính toán (không gọi AI, không ghi file) — dễ thử."""
import re, unicodedata

from bo_cuc import la_chai
from soat_kho import nguoi_noi
import ne_nhan

W, H = 1080, 1920
DAO_DIEN, MAY = "dao_dien", "may"

# (id, câu hỏi cho giám khảo, người sửa được, nặng?) — thứ tự = thứ tự ưu tiên khi chọn 3 lỗi nặng nhất
MUC = [
    ("hook", "MÓC CÂU: hai khung đầu (hình + chữ mở) khiến người đang lướt dừng lại; chữ mở gây tò mò, không lặp nguyên câu đọc, không chỉ là tên sản phẩm", DAO_DIEN, True),
    ("nhan_ro", "NHÃN RÕ: khi lời nhắc tên sản phẩm thì thấy chai/can với nhãn đọc được", DAO_DIEN, True),
    ("chot_chai", "CHỐT CÓ CHAI: đoạn chốt thấy rõ chai/can sản phẩm", DAO_DIEN, True),
    ("hinh_hop_loi", "HÌNH HỢP LỜI: hình ở từng câu khớp điều đang nói (đủ phù hợp là được, không khắt khe)", DAO_DIEN, False),
    ("chot_qua", "CHỐT CÓ QUÀ: video nào cũng chốt bằng quà tặng (thẻ chốt nêu quà) nên đoạn chốt phải thấy gói quà thật, DÙ lời đọc im về quà; chỉ chọn 'không áp dụng' nếu tờ ảnh không cho thấy kho có cảnh quà", "qua", False),
    ("nut_gio", "NÚT GIỎ HÀNG: đoạn chốt có nút/mũi tên giỏ hàng nhìn thấy được", MAY, False),
    ("khong_che_nhan", "KHÔNG CHE NHÃN: chữ, phụ đề, sticker, khối chữ không đè lên nhãn chai", MAY, True),
    ("nguoi_noi", "NGƯỜI THẬT: có cảnh người thật cầm/dùng/nói về sản phẩm (lệch khẩu hình với lời đọc KHÔNG phải lỗi); chọn 'không áp dụng' nếu tờ ảnh không cho thấy kho có cảnh như vậy", DAO_DIEN, False),
    ("hinh_sach", "HÌNH SẠCH: không tối, mờ, méo, bệt màu/lớp màu phủ, khung chớp", MAY, False),
    ("khoang_tho", "KHOẢNG THỞ: mỗi lúc một điểm nhấn, không hai khối chữ cùng lúc, có nhịp nghỉ cho mắt", DAO_DIEN, False),
    ("da_dang_bo_cuc", "BỐ CỤC & CHỐNG TRÙNG: không lặp một kiểu bố cục suốt bài; khung toàn màn không biến tấu thì phải có chữ lớn (không để khung trơn)", DAO_DIEN, False),
    ("khong_lap", "NHỊP & KHÔNG LẶP: không lặp cảnh na ná nhau, không có cảnh đứng yên quá lâu (~5 s)", DAO_DIEN, False),
    ("vung_an_toan", "VÙNG AN TOÀN: chữ/nút không nằm sát mép trên, sát đáy hay vùng giao diện TikTok", MAY, False),
]
TEN_NGAN = {"hook": "móc câu", "nhan_ro": "nhãn rõ", "chot_chai": "chốt có chai", "hinh_hop_loi": "hình hợp lời", "chot_qua": "chốt có quà",
            "nut_gio": "nút giỏ hàng", "khong_che_nhan": "không che nhãn", "nguoi_noi": "người nói", "hinh_sach": "hình sạch",
            "khoang_tho": "khoảng thở", "da_dang_bo_cuc": "đa dạng bố cục", "khong_lap": "nhịp/không lặp", "vung_an_toan": "vùng an toàn"}
TEN_MUC = [m[0] for m in MUC]
MUC_NANG = {m[0] for m in MUC if m[3]}
NGUONG_DAT = 7.0
TOI_THIEU_AI = 0.6           # AI phải trả lời ≥ 60% số mục được hỏi, ít hơn = trả lời hỏng
STATIC_S = 5.0               # một cảnh đứng yên quá chừng này giây
CHONG_NHAN = 0.10            # chữ phủ ≥ 10% diện tích khung nhãn = che nhãn
CHONG_NHAN_PHU_DE = 0.25    # phụ đề chỉ chạm mép dưới nhãn (≤ 25%) vẫn đọc được tên — tờ ảnh 22/11: 11/12 ca 10% là oan hoặc chỉ chạm mép
CAO_PHU_DE = 150             # dải phụ đề (1–2 dòng) quanh center_y
CENTER_Y_MAC_DINH = 1490


def chu_so_huu(muc, co_canh_qua=True):
    """Ai sửa được lỗi mục này: 'dao_dien' | 'may'. 'chot_qua': kho CÓ cảnh quà mà đạo diễn không chọn → đạo diễn; kho không có → dữ liệu (máy)."""
    for m in MUC:
        if m[0] == muc:
            return (DAO_DIEN if co_canh_qua else MAY) if m[2] == "qua" else m[2]
    return DAO_DIEN


def danh_sach_cau_hoi(may_truot=()):
    """Văn bản danh sách kiểm gửi giám khảo ({{muc}}). Mục máy đã bắt trượt được ghi rõ để AI bỏ qua."""
    truot = set(may_truot)
    out = []
    for i, (k, hoi, _, _) in enumerate(MUC, 1):
        out.append(f'{i}. "{k}" — {hoi}' + ("  [MÁY ĐÃ KIỂM: TRƯỢT — bỏ qua mục này, không đưa vào kết quả]" if k in truot else ""))
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ máy đo
def _bo_dau(s):
    s = unicodedata.normalize("NFD", str(s or "").replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


_RE_QUA = re.compile(r"\b(quà|tặng|biếu|kèm theo)\b")


def nhac_qua(text):
    """Câu có nhắc quà tặng không (quà, tặng, biếu, kèm theo; có dấu để không nhầm 'quá', 'tăng')."""
    return bool(_RE_QUA.search(unicodedata.normalize("NFC", str(text or "")).lower()))


def _chong(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _moc(segs):
    """[(t0, t1)] mỗi đoạn."""
    t, out = 0.0, []
    for s in segs:
        out.append((t, t + float(s.get("dur") or 0))); t += float(s.get("dur") or 0)
    return out


def _doan(segs, info):
    """Danh sách đoạn {t0,t1,bo_cuc,opt,nhan} — ưu tiên info['doan'] (khung nhãn THẬT sau punch/trôi khung); không có thì dựng từ segs."""
    d = (info or {}).get("doan")
    if d:
        return d
    out = []
    for s, (a, b) in zip(segs, _moc(segs)):
        out.append({"t0": a, "t1": b, "bo_cuc": s.get("bo_cuc"), "opt": s.get("opt"), "nhan": (s["shot"].get("soat") or {}).get("nhan")})
    return out


def _giay(ts, toi_da=3):
    ts = sorted({round(float(t), 1) for t in ts})
    return ", ".join(f"{t:g}s" for t in ts[:toi_da]) + ("…" if len(ts) > toi_da else "")


def _khoi_chu(props):
    """[(f0, f1, rect)] các khối chữ lớn (top mặc định 250 — như ne_nhan.dat_khoi)."""
    out = []
    for b in (props or {}).get("blocks") or []:
        try:
            top = float(b.get("top", 250)); cao = ne_nhan.CAO.get(b.get("loai"), 260)
            out.append((b["f0"], b["f1"], (60.0, top, 940.0, top + cao), b.get("loai")))
        except Exception:
            continue
    return out


def _dai_phu_de(props, info):
    """[(t0, t1, rect)] dải phụ đề. Ưu tiên toạ độ TỪNG DÒNG nếu mã dựng có ghi (props.lines[i].y|center_y hoặc info.cap_lines);
    không có thì dải cố định quanh cap.center_y (dung_remotion.CENTER_Y)."""
    fps = 30.0
    cy0 = float(((props or {}).get("cap") or {}).get("center_y") or (info or {}).get("cap_center_y") or CENTER_Y_MAC_DINH)
    dong = list((info or {}).get("cap_lines") or []) or list((props or {}).get("lines") or [])
    out = []
    for ln in dong:
        try:
            y = ln.get("y", ln.get("center_y", cy0))
            y = float(y if y is not None else cy0)
            out.append((ln["f0"] / fps, ln["f1"] / fps, (40.0, y - CAO_PHU_DE / 2, 1040.0, y + CAO_PHU_DE / 2)))
        except Exception:
            continue
    return out


def kiem(segs, sents=None, info=None, props=None, co_qua=True, co_canh_qua=False):
    """Máy kiểm bản dựng từ bảng dựng + hồ sơ dựng. → danh sách phát hiện [{muc, nguoi_sua, giay, chi_tiet, sua}].
    segs: đoạn cảnh (shot, dur, bo_cuc, phu_shots, cau); sents: câu có s/e/text; info: hồ sơ chuan_bi (doan, blocks…); props: props.json của lớp chữ;
    co_qua: sản phẩm có tặng quà; co_canh_qua: kho có cảnh quà thật (để biết lỗi thiếu quà là do đạo diễn hay do kho)."""
    segs = list(segs or [])
    if not segs:
        return []
    kq, mo = [], _moc(segs)

    def them(muc, giay, chi_tiet, sua="", ai=None):
        kq.append({"muc": muc, "nguoi_sua": ai or chu_so_huu(muc, co_canh_qua), "giay": giay, "chi_tiet": chi_tiet, "sua": sua})

    # 1) khung trơn: đoạn toàn màn ≥ 1,2 s không có chữ lớn (dễ bị đánh trùng nội dung gốc) — dung_remotion ghi info["khung_tron"]
    tron = [float(x[0]) for x in ((info or {}).get("khung_tron") or []) if isinstance(x, (list, tuple)) and x]
    if len(tron) >= 2:                       # cho phép MỘT nhịp thở hình sạch
        them("da_dang_bo_cuc", tron[0], f"{len(tron)} đoạn toàn màn trơn (không ô chèn, không chữ lớn) lúc {_giay(tron)}",
             "thêm chữ lớn hoặc đổi bố cục (chia ô, ô chèn, lật trang) ở các đoạn đó; chỉ giữ một nhịp thở")

    # 2) chữ / phụ đề đè nhãn
    doan = _doan(segs, info)
    khoi, dai = _khoi_chu(props), _dai_phu_de(props, info)
    cap_mac_dinh = float(((props or {}).get("cap") or {}).get("center_y") or (info or {}).get("cap_center_y") or CENTER_Y_MAC_DINH)
    band = (40.0, cap_mac_dinh - CAO_PHU_DE / 2, 1040.0, cap_mac_dinh + CAO_PHU_DE / 2)
    t_khoi, t_cap = [], []
    for d in doan:
        hop = ne_nhan.hop_man_hinh(d) if d.get("nhan") else None
        if not hop:
            continue
        dien = max(1.0, (hop[2] - hop[0]) * (hop[3] - hop[1]))
        t0, t1 = float(d["t0"]), float(d["t1"])
        for f0, f1, rect, _loai in khoi:
            if f1 / 30.0 > t0 and f0 / 30.0 < t1 and _chong(rect, hop) / dien >= CHONG_NHAN:
                t_khoi.append(max(t0, f0 / 30.0))
        cs = [] if ((props or {}).get("cap") or {}).get("bat") is False else [r for a, b, r in dai if b > t0 and a < t1] if dai else [band]   # tắt phụ đề → không có gì để đè
        if any(_chong(r, hop) / dien >= CHONG_NHAN_PHU_DE for r in cs):
            t_cap.append(t0)
    if t_khoi:
        them("khong_che_nhan", min(t_khoi), f"khối chữ đè nhãn chai lúc {_giay(t_khoi)}", "dời khối chữ ra khỏi nhãn", MAY)
    if t_cap:
        them("khong_che_nhan", min(t_cap), f"phụ đề đè nhãn chai lúc {_giay(t_cap)}", "dời phụ đề / chọn cảnh nhãn không nằm sát đáy", MAY)

    # 3) lặp cảnh / đứng yên
    seen, lap = {}, []
    for i, s in enumerate(segs):
        for sh in [s["shot"]] + list(s.get("phu_shots") or []):
            k = sh.get("id")
            if k in seen and seen[k] != i:
                lap.append(mo[i][0])
            seen.setdefault(k, i)
    for i in range(1, len(segs)):
        a, b = segs[i - 1], segs[i]
        if a["shot"].get("file") and a["shot"].get("file") == b["shot"].get("file") and abs(float(a.get("src_start") or 0) - float(b.get("src_start") or 0)) < 1.5:
            lap.append(mo[i][0])
    if lap:
        them("khong_lap", min(lap), f"cảnh bị lặp/na ná liền kề lúc {_giay(lap)}", "đổi sang cảnh khác hẳn")
    tinh = [a for s, (a, b) in zip(segs, mo) if (b - a) > STATIC_S]
    if tinh:
        them("khong_lap", tinh[0], f"một cảnh đứng yên quá {STATIC_S:g} giây lúc {_giay(tinh)}", "cắt thêm cảnh hoặc rút ngắn")

    # 4) đoạn chốt: chai, quà
    n_cau = len(sents or [])
    cuoi = [(s, ab) for s, ab in zip(segs, mo) if n_cau and s.get("cau") == n_cau - 1] or [(segs[-1], mo[-1])]
    t_chot = cuoi[0][1][0]
    if not any((la_chai(sh) and not str(sh.get("id", "")).startswith("Q-")) or nguoi_noi(sh) for s, _ in cuoi for sh in [s["shot"]] + list(s.get("phu_shots") or [])):   # chai QUÀ không phải chai sản phẩm
        them("chot_chai", t_chot, "đoạn chốt không có cảnh chai/can rõ", "đổi cảnh chốt sang cảnh chai rõ")
    text_cuoi = (sents[-1].get("text") if sents else "") or ""
    if co_qua and sents and (nhac_qua(text_cuoi) or co_canh_qua):       # mọi video chốt bằng quà: kho có cảnh quà thì đoạn chốt phải có, dù lời im
        co_q = any(str(sh.get("id", "")).startswith("Q-") for s, _ in cuoi for sh in [s["shot"]] + list(s.get("phu_shots") or []))
        if not co_q:
            them("chot_qua", t_chot, "video chốt bằng quà tặng nhưng không có cảnh quà thật (Q-) ở đoạn chốt",
                 "chốt bằng cảnh gói quà thật" if co_canh_qua else "")
    # 5) nút giỏ hàng bị bỏ (chai chiếm mọi chỗ mũi tên) mà khối chốt cũng không phải nút giỏ hàng
    if props and (props.get("arrow") or {}).get("top") == -999:
        bl = props.get("blocks") or []
        if not bl or bl[-1].get("loai") not in ("nut_gio_hang", "chot_tinh"):
            them("nut_gio", t_chot, "mũi tên giỏ hàng bị bỏ vì không còn chỗ trống", "", MAY)
    # 6) vùng an toàn: khối chữ sát mép trên (< 130 px) hoặc tràn xuống vùng giao diện TikTok (> 1650 px)
    sai = [f0 / 30.0 for f0, f1, r, _l in khoi if r[1] < 130 or r[3] > 1650]
    if sai:
        them("vung_an_toan", min(sai), f"khối chữ lọt vùng an toàn lúc {_giay(sai)}", "", MAY)
    return kq


# ------------------------------------------------------------------------------------------------ gộp máy + AI → điểm
def tinh_diem(muc):
    """muc: [{id, dat: True|False|None}] — None = không áp dụng (bỏ khỏi mẫu số). → (điểm 0–10 làm tròn 1 số, số đạt, số xét)."""
    xet = [m for m in muc if m.get("dat") is not None]
    if not xet:
        return None, 0, 0
    dat = sum(1 for m in xet if m["dat"])
    return round(10.0 * dat / len(xet), 1), dat, len(xet)


def _bool(v):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = _bo_dau(v).strip()
    if s in ("true", "dat", "co", "pass", "ok", "yes", "1"):
        return True
    if s in ("false", "truot", "khong", "fail", "no", "0"):
        return False
    return None


def hop_nhat(kq_ai, may, co_canh_qua=True):
    """Gộp kết quả AI (dict có 'muc': [{id, dat, ly_do, giay}]) với phát hiện của máy. → dict {diem, dat, loi, sua, muc, may} hoặc None nếu AI trả hỏng
    (không có 'muc' đủ — kể cả kiểu cũ chỉ có 'diem'; khi đó dùng hop_nhat_cu)."""
    may_theo_muc = {}
    for f in may or []:
        may_theo_muc.setdefault(f["muc"], []).append(f)
    hoi = [k for k in TEN_MUC if k not in may_theo_muc]
    ai = {}
    for m in (kq_ai or {}).get("muc") or []:
        if isinstance(m, dict) and m.get("id") in TEN_MUC and m["id"] not in may_theo_muc:
            ai[m["id"]] = m
    if hoi and len(ai) < TOI_THIEU_AI * len(hoi):
        return None
    muc = []
    for k in TEN_MUC:
        if k in may_theo_muc:
            f = may_theo_muc[k][0]
            muc.append({"id": k, "dat": False, "ly_do": "; ".join(x["chi_tiet"] for x in may_theo_muc[k])[:200], "giay": f.get("giay"),
                        "nguon": "may", "nguoi_sua": f["nguoi_sua"], "sua": f.get("sua") or ""})
        elif k in ai:
            m = ai[k]; d = _bool(m.get("dat"))
            g = m.get("giay")
            try:
                g = round(float(g), 1) if g is not None and g != "" else None
            except (TypeError, ValueError):
                g = None
            muc.append({"id": k, "dat": d, "ly_do": str(m.get("ly_do") or "")[:160], "giay": g, "nguon": "ai",
                        "nguoi_sua": chu_so_huu(k, co_canh_qua)})
    diem, _, _ = tinh_diem(muc)
    truot = [m for m in muc if m["dat"] is False]
    nang = any(m["id"] in MUC_NANG for m in truot)
    thu_tu = {k: i for i, k in enumerate(TEN_MUC)}
    loi = []
    for m in sorted(truot, key=lambda m: thu_tu[m["id"]])[:3]:
        g = f"{m['giay']:g}s " if m.get("giay") is not None else ""
        loi.append(("[máy] " if m["nguon"] == "may" else "") + f"{g}{TEN_NGAN[m['id']]}: {m['ly_do'] or 'trượt'}")
    sua = str((kq_ai or {}).get("sua") or "").strip()
    goi_y = [f["sua"] for f in may or [] if f.get("sua") and f["nguoi_sua"] == DAO_DIEN]
    if goi_y:
        sua = (sua + " " + "; ".join(dict.fromkeys(goi_y))).strip()
    return {"diem": diem, "dat": bool(diem is not None and diem >= NGUONG_DAT and not nang), "loi": loi, "sua": "" if diem is not None and diem >= 10 else sua[:300],
            "muc": muc, "may": list(may or [])}


def hop_nhat_cu(kq_ai, may):
    """AI trả kiểu cũ (chỉ 'diem', vd. đề bài giám khảo cũ người dùng đã ghim): giữ điểm AI nhưng không cao hơn điểm danh sách kiểm cho các mục máy đã bắt."""
    diem = kq_ai.get("diem")
    loi = [str(x) for x in (kq_ai.get("loi") or []) if x]
    if may:
        tong = len(TEN_MUC)
        tran = round(10.0 * (tong - len({f["muc"] for f in may})) / tong, 1)
        diem = min(float(diem), tran) if diem is not None else None
        loi = [f"[máy] {f['chi_tiet']}" for f in may][:3] + loi
    return {"diem": diem, "dat": bool(kq_ai.get("dat")) and diem is not None and diem >= NGUONG_DAT, "loi": loi[:3], "sua": kq_ai.get("sua") or "",
            "muc": [], "may": list(may or [])}


# ------------------------------------------------------------------------------------------------ bài học
_RE_MAY = re.compile(r"vùng an toàn|giao diện tiktok|đè (lên )?nhãn|che (khuất |mất )?nhãn|phụ đề|lớp phủ|lớp màu|overlay|bệt màu|"
                     r"dấu reup|bình luận gốc|watermark|khối chữ|chữ .{0,40}(chồng|sát|đè)|(đè|che) nút|\d+ ?% trên|sticker|"
                     r"tem chữ|chữ lạ|vòng tròn đè|ô rót thuốc đè", re.I)


def la_loi_may(dong):
    """Dòng bài học cũ nói về lỗi do máy dựng/dữ liệu (chữ đè nhãn, phụ đề, giỏ hàng, lớp màu, vùng an toàn…) — đạo diễn không sửa được."""
    return bool(_RE_MAY.search(str(dong or "")))


def _tu(s):
    return {w for w in re.findall(r"[0-9a-zà-ỹ]+", str(s).lower()) if len(w) > 1}


def tuong_tu(a, b, nguong=0.6):
    """2 bài học na ná nhau: |giao| / |nhỏ hơn| ≥ nguong (chịu được câu ngắn là con của câu dài)."""
    x, y = _tu(a), _tu(b)
    if not x or not y:
        return False
    return len(x & y) / min(len(x), len(y)) >= nguong


def gop_tuong_tu(dong, nguong=0.6):
    """Giữ 1 dòng cho mỗi nhóm bài học na ná nhau; giữ dòng DÀI hơn (nhiều chi tiết) ở vị trí cuối cùng gặp. Thứ tự giữ nguyên."""
    out = []
    for d in dong:
        for i, o in enumerate(out):
            if tuong_tu(d, o, nguong):
                if len(d) > len(o):
                    out[i] = d
                break
        else:
            out.append(d)
    return out


def tach_bai_hoc(r, co_canh_qua=True):
    """Kết quả 1 giám khảo → (dòng bài học cho ĐẠO DIỄN, bản ghi lỗi máy cho loi-may.jsonl).
    Chỉ mục trượt có người sửa là đạo diễn mới thành bài học (dạng '- <mục>: <lý do>'); lỗi máy/dữ liệu không bao giờ."""
    hoc, may = [], []
    if not r.get("muc"):                      # giám khảo kiểu cũ (chỉ có lỗi chữ tự do): lọc lỗi máy theo từ khoá
        return [f"- {x}" for x in (str(y) for y in r.get("loi") or []) if len(x) > 8 and not x.startswith(("[máy]", "chưa chấm")) and not la_loi_may(x)], may
    for m in r.get("muc") or []:
        if m.get("dat") is not False:
            continue
        ai = m.get("nguoi_sua") or chu_so_huu(m["id"], co_canh_qua)
        if ai == DAO_DIEN:
            ly = m.get("sua") if m.get("nguon") == "may" and m.get("sua") else m.get("ly_do")      # máy đo: dùng lời khuyên chung (không có mốc giây)
            ly = re.sub(r"\s+", " ", str(ly or "")).strip(" .;-")
            ly = re.sub(r"^\d+([.,]\d+)?\s*s\s*[:,-]?\s*", "", ly)
            if len(ly) > 6:
                hoc.append(f"- {TEN_NGAN.get(m['id'], m['id'])}: {ly}")
        elif ai == MAY:
            may.append({"muc": m["id"], "nguon": m.get("nguon", "ai"), "giay": m.get("giay"), "chi_tiet": m.get("ly_do") or ""})
    for f in r.get("may") or []:
        if f.get("nguoi_sua") == MAY and not any(x["muc"] == f["muc"] and x["chi_tiet"] == f["chi_tiet"] for x in may):
            may.append({"muc": f["muc"], "nguon": "may", "giay": f.get("giay"), "chi_tiet": f["chi_tiet"]})
    return hoc, may
