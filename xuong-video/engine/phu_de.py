"""Chia dòng phụ đề theo cụm ý và gắn mốc thời gian từng từ.
chia_dong(text, dong_ai, words) -> [{"f0","f1","words":[{"w","f0","f1","emph"}]}]"""
import re

FPS = 30


def _toks(s):
    return re.findall(r"\w+", s.lower())


def _tu_dem(s):
    """Các từ được tính (bỏ dấu đứng riêng như – …) — khớp cách gộp từ của giọng (giong.words_from_alignment)."""
    return [w for w in s.split() if re.search(r"\w", w)]


def chia_tu(nhom, words):
    """nhom: [[từ hiển thị của câu/dòng 1], [..2], ...]; words: từ có mốc thời gian của giọng.
    → [(a, b)] chỉ số words[a:b] cho từng nhóm. Số từ khớp → chia tuần tự như cũ. Lệch (đọc thay doc_la nhiều chữ,
    số đọc thành chữ...) → dóng theo từ đã chuẩn hoá (difflib), đoạn không khớp thì nội suy, để câu sau không bị trôi."""
    dem = [len(g) for g in nhom]
    if sum(dem) == len(words):
        out, i = [], 0
        for n in dem:
            out.append((i, i + n)); i += n
        return out
    import difflib
    norm = lambda x: re.sub(r"[^\w]", "", str(x).lower())
    a = [norm(t) for g in nhom for t in g]
    b = [norm(w.get("w", "")) for w in words]
    m = {}
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            m[blk.a + k] = blk.b + k
    da = sorted(m)

    def bien(t):                        # chỉ số trong words ứng với chỗ bắt đầu từ thứ t của lời
        if t in m:
            return m[t]
        p = max((x for x in da if x < t), default=None)
        q = min((x for x in da if x > t), default=None)
        t0, lo = (p + 1, m[p] + 1) if p is not None else (0, 0)
        t1, hi = (q, m[q]) if q is not None else (len(a), len(b))
        if t1 <= t0:
            return lo
        return lo + int(round((t - t0) * (hi - lo) / (t1 - t0)))

    cuts, t = [0], 0
    for n in dem[:-1]:
        t += n
        cuts.append(min(len(b), max(cuts[-1], bien(t))))
    cuts.append(len(b))
    return [(cuts[k], cuts[k + 1]) for k in range(len(dem))]


def auto_lines(plain):
    """Dự phòng: tách theo câu, rồi dấu phẩy; gộp mẩu ngắn, bẻ mẩu dài."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", plain.strip()):
        parts = [p.strip() for p in re.split(r"(?<=[,;:…])\s+", sent) if p.strip()]
        buf = []
        for p in parts:
            cur = sum(len(x.split()) for x in buf)
            if buf and cur + len(p.split()) > 11:      # thêm vào sẽ quá dài → xuống dòng ở dấu câu
                out.append(" ".join(buf)); buf = []
            buf.append(p)
            if sum(len(x.split()) for x in buf) >= 6:
                out.append(" ".join(buf)); buf = []
        if buf:
            if out and len(" ".join(buf).split()) < 4 and len(out[-1].split()) + len(" ".join(buf).split()) <= 12 and not re.search(r"[.!?]$", out[-1]):
                out[-1] += " " + " ".join(buf)
            else:
                out.append(" ".join(buf))
    final = []
    for ln in out:
        ws = ln.split()
        while len(ws) > 11:
            cut = len(ws) // 2
            final.append(" ".join(ws[:cut])); ws = ws[cut:]
        final.append(" ".join(ws))
    return final


MAC_DINH = {"bat": True, "co": 50, "co_chu": 1.0, "y": 1500, "tu_moi_dong": [2, 5]}   # co 44 → 50 (+14%); co_chu = hệ số nhân người dùng chỉnh
CO_CHU_DUOI, CO_CHU_TREN = 0.7, 1.6
SO_CHU = {"không", "một", "hai", "ba", "bốn", "tư", "năm", "lăm", "sáu", "bảy", "tám", "chín", "mười", "mươi", "mốt", "trăm", "nghìn", "ngàn",
          "triệu", "tỷ", "linh", "lẻ", "rưỡi"}
DON_VI = {"ml", "lít", "lit", "l", "kg", "g", "gam", "gói", "chai", "phần", "%", "m", "cm", "mm", "ha", "sào", "lần", "con", "lá", "ngày", "giờ", "phút", "đồng", "k"}


def cau_hinh(cfg=None):
    """Đọc config["phu_de"] = {bat, co, y, tu_moi_dong:[ít,nhiều]}; thiếu/sai → mặc định hợp lý."""
    raw = (cfg or {}).get("phu_de") if isinstance(cfg, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    out = dict(MAC_DINH)
    if isinstance(raw.get("bat"), bool):
        out["bat"] = raw["bat"]
    for k, lo, hi in (("co", 24, 90), ("y", 300, 1700)):
        try:
            out[k] = int(min(hi, max(lo, int(float(raw[k])))))
        except Exception:
            pass
    if out["co"] == 44:                      # 44 = mặc định cũ còn nằm trong config.json → lên cỡ mới
        out["co"] = MAC_DINH["co"]
    try:
        out["co_chu"] = round(min(CO_CHU_TREN, max(CO_CHU_DUOI, float(raw["co_chu"]))), 2)
    except Exception:
        pass
    out["co"] = int(min(90, max(24, round(out["co"] * out["co_chu"]))))      # cỡ chữ cuối (px) = co × co_chu
    try:
        a, b = [int(x) for x in raw["tu_moi_dong"]][:2]
        a = max(1, min(a, 8)); b = max(a, min(b, 8))
        out["tu_moi_dong"] = [a, b]
    except Exception:
        pass
    return out


def _chuan(w):
    return re.sub(r"[^\w%]", "", str(w).lower())


def _la_so(w):
    c = _chuan(w)
    return bool(c) and (c in SO_CHU or bool(re.fullmatch(r"\d+([.,]\d+)?", c)))


def _cam_cat(ws):
    """cam[i] = True nếu KHÔNG được ngắt giữa ws[i-1] và ws[i]: tên riêng viết hoa liền nhau (Bọ Trĩ Top One), cụm số (hai trăm bốn mươi), số + đơn vị (240 ml)."""
    cam = [False] * len(ws)
    for i in range(1, len(ws)):
        a, b = ws[i - 1], ws[i]
        if re.search(r"[,;:…!?.]$", a):
            continue
        ca, cb = _chuan(a), _chuan(b)
        if a[:1].isupper() and b[:1].isupper():
            cam[i] = True
        elif _la_so(a) and (_la_so(b) or (cb in DON_VI and re.search(r"\d", ca))):
            cam[i] = True
    return cam


def _cat_doan(ws, cam, lo, hi):
    """Chia ws (không có dấu câu giữa chừng) thành các cụm ≤ hi từ, cân đối, tránh cắt chỗ cấm.
    Ngắt ngay sau chữ số bị phạt nặng: "một nắp pha một | bình" đọc hỏng nghĩa (Kid 23/11), "một nắp pha | một bình" mới đúng."""
    n = len(ws)
    if n <= hi:
        return [(0, n)]
    ly_tuong = n / -(-n // hi)
    INF = 1e9
    best = [INF] * (n + 1); tr = [0] * (n + 1); best[0] = 0
    for j in range(1, n + 1):
        for i in range(j):
            if best[i] >= INF or (i > 0 and cam[i]):
                continue
            sz = j - i
            c = best[i] + (sz - ly_tuong) ** 2 + (1000 if sz > hi else 0) + (300 if sz < lo else 0) + (400 if j < n and _la_so(ws[j - 1]) else 0)
            if c < best[j]:
                best[j], tr[j] = c, i
    out, j = [], n
    while j > 0:
        out.append((tr[j], j)); j = tr[j]
    return out[::-1]


def cat_cum(ws, lo=2, hi=5, cam_them=None):
    """Chia danh sách từ hiển thị thành cụm lo–hi từ: ngắt ở dấu câu trước, rồi cân đối; không cắt tên riêng / số.
    cam_them[i] = True: thêm chỗ cấm ngắt giữa ws[i-1] và ws[i] (vd. tên hàng viết thường, "mi li")."""
    if not ws:
        return []
    cam = _cam_cat(ws)
    if cam_them:
        cam = [a or bool(b) for a, b in zip(cam, cam_them)]
    doan, a = [], 0
    for i, w in enumerate(ws):
        if re.search(r"[,;:…!?.]$", w) and i + 1 < len(ws):
            doan.append((a, i + 1)); a = i + 1
    doan.append((a, len(ws)))
    cum = []
    for a, b in doan:
        cum += [(a + x, a + y) for x, y in _cat_doan(ws[a:b], cam[a:b], lo, hi)]
    ra = []
    for a, b in cum:                                   # cụm 1 từ → gộp vào cụm kề nếu không quá dài
        if b - a < lo and ra and ra[-1][1] - ra[-1][0] + (b - a) <= hi and not re.search(r"[.!?]$", ws[ra[-1][1] - 1]):
            ra[-1] = (ra[-1][0], b)
        else:
            ra.append((a, b))
    if len(ra) > 1 and ra[0][1] - ra[0][0] < lo and ra[0][1] - ra[0][0] + ra[1][1] - ra[1][0] <= hi:
        ra[1] = (ra[0][0], ra[1][1]); ra = ra[1:]
    return [" ".join(ws[a:b]) for a, b in ra]


def _chu_cua_khoi(d):
    """Mọi chữ trong data của khối (để biết khối đang nói gì)."""
    if isinstance(d, str):
        return [d]
    if isinstance(d, dict):
        return [x for v in d.values() for x in _chu_cua_khoi(v)]
    if isinstance(d, (list, tuple)):
        return [x for v in d for x in _chu_cua_khoi(v)]
    if isinstance(d, (int, float)):
        return [str(d)]
    return []


def loc_phu_de(lines, blocks, nguong=0.6):
    """Bỏ dòng phụ đề đang trùng chữ với khối đang hiện cùng lúc (khối nói rồi, phụ đề đọc lại là thừa)."""
    out = []
    for ln in lines or []:
        tk = [t for t in _toks(" ".join(w["w"] for w in ln["words"]))]
        trung = False
        for b in blocks or []:
            if b["f1"] <= ln["f0"] or b["f0"] >= ln["f1"]:
                continue
            bt = set(_toks(" ".join(_chu_cua_khoi(b.get("data")))))
            if tk and sum(t in bt for t in tk) / len(tk) >= nguong:
                trung = True; break
        if not trung:
            out.append(ln)
    return out


def _bo_dau_cuoi(s):
    return re.sub(r"[,;:.…]+$", "", str(s).rstrip())


def chia_dong(text, dong_ai, words, emph_keys=(), tu_min=2, tu_max=5):
    plain = re.sub(r"\[[^\]]*\]\s*", "", text).strip()
    dung_ai = bool(dong_ai and _toks(" ".join(dong_ai)) == _toks(plain))
    base = dong_ai if dung_ai else auto_lines(plain)
    lines = [c for ln in base for c in cat_cum(_tu_dem(ln), tu_min, tu_max)]
    keys = [k.lower() for k in emph_keys if k]
    out = []
    for ln, (a, b) in zip(lines, chia_tu([_tu_dem(ln) for ln in lines], words)):
        ws = words[a:b]
        if not ws:
            continue
        # dấu phẩy/chấm cuối dòng chiếm chỗ bên phải → cụm chữ trông lệch trái (căn theo mắt, Kid 23/11); giữ ? !
        out.append({"text": _bo_dau_cuoi(ln), "f0": int(round(ws[0]["s"] * FPS)), "f1": int(round(ws[-1]["e"] * FPS)),
                    "words": [{"w": _bo_dau_cuoi(w["w"]) if i == len(ws) - 1 else w["w"], "f0": int(round(w["s"] * FPS)), "f1": int(round(w["e"] * FPS)),
                               "emph": any(k in w["w"].lower() for k in keys)} for i, w in enumerate(ws)]})
    return out, dung_ai
