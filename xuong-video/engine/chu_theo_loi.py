"""Khung dựng "Chữ theo lời" (kiểu v10 bọ trĩ kol-vip2 Kid duyệt, gộp vào app 23/11) — áp lên MỌI công thức, thay lớp thẻ + phụ đề.
Mỗi cụm ý của lời = 1 khối: chữ DẪN nhỏ thường (hiện từng từ theo lời) + TỪ CHÍNH viết hoa thật to (hiện đúng lúc đọc).
Màu theo ĐOẠN câu chuyện (vấn đề / tên hàng / kết quả / giá trị-chốt), không theo từng từ; bảng màu đổi theo video, đồng điệu, không chói (Kid 23/11).
Khối xen kẽ trên/dưới theo chỗ trống từng cảnh (né mặt người, né nhãn chai). Một chữ khổng lồ vàng kim ở hook (lần vàng kim duy nhất).
Tài liệu: P:/Quan ly tikttok/thu-kol-vip2/BAN-GIAO_khung-dung-chu-theo-loi.md. Không gọi AI."""
import re

from phu_de import cat_cum

FPS = 30
KHUNG = ("the_do_hoa", "chu_theo_loi")       # the_do_hoa = khung thẻ + phụ đề hiện có

# Kid 23/11: "đa dạng màu, tự do nhưng phải đồng điệu, hợp video, không chói lóa". Mỗi bảng: đỏ/cam ấm cho vấn đề, một màu sáng dịu cho giá trị,
# trắng cho kết quả. Không dùng xanh lá (chìm trên nền lá — bài học v10), không neon gắt.
BANG_MAU = {
    "tin":       {"warn": "#FF4D5A", "val": "#5FF0E6", "res": "#FFFFFF", "brand": "#FFFFFF", "dan": "#FFFFFF"},     # v10 Kid duyệt
    "nang_am":   {"warn": "#FF6B3D", "val": "#FFD54F", "res": "#FFFFFF", "brand": "#FFF3D6", "dan": "#FFF8EE"},
    "troi_xanh": {"warn": "#FF5A6E", "val": "#8ED8FF", "res": "#FFFFFF", "brand": "#FFFFFF", "dan": "#F2F8FF"},
    "san_ho":    {"warn": "#FF7A66", "val": "#FFE29A", "res": "#FFFFFF", "brand": "#FFFFFF", "dan": "#FFFFFF"},
    "hoang_hon": {"warn": "#FF5C8A", "val": "#C9B8FF", "res": "#FFFFFF", "brand": "#FFFFFF", "dan": "#FFF6F8"},
    # Kid 24/11: "không phải video nào cũng 1 màu" — thêm bảng khác hẳn tông (không đỏ-trắng), vẫn dịu, chữ chính có màu
    "la_non":    {"warn": "#FF8A3D", "val": "#B8F27C", "res": "#E9FFD6", "brand": "#FFFFFF", "dan": "#F4FFEA"},
    "bien_xanh": {"warn": "#FFB547", "val": "#6FE3FF", "res": "#E3FAFF", "brand": "#FFFFFF", "dan": "#F0FCFF"},
    "kem_nau":   {"warn": "#FF7B54", "val": "#FFD9A0", "res": "#FFF1DC", "brand": "#FFF8EE", "dan": "#FFF8EE"},
    "hong_vang": {"warn": "#FFD166", "val": "#F7A8FF", "res": "#FFFFFF", "brand": "#FFF4FE", "dan": "#FFF4FE"},
    "ngoc_cam":  {"warn": "#FF6F59", "val": "#43E6B0", "res": "#DFFFF4", "brand": "#FFFFFF", "dan": "#F0FFF9"},
    "vang_chanh":{"warn": "#FF9F1C", "val": "#F4F269", "res": "#FFFFFF", "brand": "#FFFDE0", "dan": "#FFFDF0"},
}
TOI_DA_GO = 3
TRAN_MODE = {"type": TOI_DA_GO, "glitch": 1, "dau": 2, "roi": 2}     # gõ phím dày thành ồn (v10); nhiễu/đóng dấu là gia vị, ít mới mạnh
FONT_CHINH = ("Unbounded", "DT Phudu", "Montserrat BI")     # đã thử đủ dấu tiếng Việt viết hoa

SO = re.compile(r"\d|^(một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|mươi|lăm|mốt|trăm|nghìn|ngàn|triệu|nửa|rưỡi|chục)$", re.I)
DON_VI = {"lít", "ml", "mi", "li", "nắp", "bình", "phuy", "can", "chai", "gói", "kg", "ký", "lượt", "ngày", "công", "sào", "gốc", "cây", "lần",
          "%", "phần", "trăm", "đồng", "tuần", "tháng", "giờ", "phút", "tấn", "tạ", "hũ", "lọ", "thùng"}
XAU = re.compile(r"\b(vẫn|trễ|lỡ|muộn|khô|cháy|rụng|xoăn|vàng|thối|hư|sâu|bệnh|mất|tốn|phí|còi|cọc|héo|gục|nấm|rệp|trĩ|lụi|chậm|yếu|đói)\b", re.I)
NOI = {"là", "thì", "mà", "rồi", "nha", "nhé", "nhá", "á", "ạ", "đó", "luôn", "vậy", "và", "nên", "cho", "để", "khi", "với"}     # từ nối cuối cụm: đọc thì có, chữ trên hình bỏ
TOT = re.compile(r"\b(xanh|bung|nở|mập|khỏe|khoẻ|trắng|dày|bóng|mướt|sạch|lớn|to|đậu|sai trái|ra rễ|ra hoa|đẻ nhánh|phục hồi)\b", re.I)
GIA_TRI = re.compile(r"\b(giỏ|tặng|quà|miễn|nắp|pha|lít|bình|phuy|đặt|mua|chốt|ship|kéo dài|bền|nhanh)\b", re.I)


def _sach(w):
    return re.sub(r"[^\w%]", "", str(w).lower())


def _cam(ws, ten):
    """Chỗ không được ngắt cụm: giữa các chữ của tên hàng (kể cả viết thường), trong cụm số + đơn vị, "mi li"."""
    s = [_sach(w["w"]) for w in ws]
    cam = [False] * len(s)
    k = min(3, len(ten))
    for a in range(len(s)):
        if k >= 2 and s[a:a + k] == ten[:k]:
            b = a + k
            while b < len(s) and s[b] in ten:
                b += 1
            for i in range(a + 1, b):
                cam[i] = True
    for i in range(1, len(s)):
        so_truoc = SO.search(s[i - 1]) or s[i - 1] in SO_CHU
        if (so_truoc and (SO.search(s[i]) or s[i] in SO_CHU or s[i] in DON_VI)) or (s[i - 1], s[i]) == ("mi", "li"):
            cam[i] = True
    return cam


def _cat_khoi(sents, ten=()):
    """Câu → cụm ý (3–7 từ) có mốc thời gian; cụm quá ngắn (< 0,7 s) gộp với cụm sau nếu vẫn ≤ 8 từ."""
    out = []
    for si, s in enumerate(sents):
        ws = s["words"]
        hien = [w["w"] for w in ws]
        i = 0
        cum = []
        for c in cat_cum(hien, 3, 7, _cam(ws, list(ten))):
            n = len(c.split())
            cum.append(ws[i:i + n]); i += n
        if i < len(ws):
            cum[-1:] = [(cum[-1] if cum else []) + ws[i:]]
        gop = []
        for c in cum:
            if gop and (gop[-1][-1]["e"] - gop[-1][0]["s"] < 0.7) and len(gop[-1]) + len(c) <= 8:
                gop[-1] = gop[-1] + c
            else:
                gop.append(list(c))
        out += [{"si": si, "ws": c} for c in gop if c]
    return out


def _tim(ws, cum):
    """Vị trí cụm từ (list chữ đã sạch) trong ws → (a, b) hoặc None."""
    s = [_sach(w["w"]) for w in ws]
    for a in range(len(s) - len(cum) + 1):
        if s[a:a + len(cum)] == cum:
            return a, a + len(cum)
    return None


def _tu_chinh(ws, keys, ten):
    """(a, b, vai_rieng): khoảng từ chính trong cụm. Ưu tiên: tên hàng → số + đơn vị → từ nhấn của đạo diễn → cụm cuối."""
    n = len(ws)
    s = [_sach(w["w"]) for w in ws]
    if ten:
        for k in range(min(4, len(ten)), min(3, len(ten)) - 1, -1):     # ≥ 3 chữ: "bọ trĩ" (tên con bọ) không phải tên hàng "Bọ Trĩ Top One"
            for a in range(len(ten) - k + 1):
                r = _tim(ws, ten[a:a + k])
                if r:
                    a0, b0 = r
                    while b0 < n and b0 - a0 < 4 and s[b0] in ten:
                        b0 += 1
                    return a0, b0, "brand"
    so_cum, a = [], 0
    while a < n:                                  # mọi cụm số + đơn vị; lấy cụm CUỐI ("1 tháng phun … 4 LƯỢT")
        if SO.search(s[a]):
            b = a + 1
            while b < n and (SO.search(s[b]) or s[b] in DON_VI or s[b] in ("linh", "lẻ")):
                b += 1
            if b - a > 1 or s[a].isdigit():
                so_cum.append((a, b))
            a = b
        else:
            a += 1
    if so_cum:
        a, b = so_cum[-1]
        if len(so_hoa(" ".join(w["w"] for w in ws[a:b]))) <= 16:
            return a, b, None
    for k in sorted((k.split() for k in keys), key=len, reverse=True):
        r = _tim(ws, [_sach(x) for x in k])
        if r and r[1] - r[0] <= 4:
            return r[0], r[1], None
    for i in range(n):                            # Kid 26/11: chữ nặng ("héo", "thối rễ") là từ chính, to + màu cảnh báo — không chìm trong chữ dẫn
        if XAU.fullmatch(s[i]) and s[i] != "vẫn":
            b = i + 1
            while b < n and b - i < 3 and (s[b] in BO_PHAN or XAU.fullmatch(s[b])):
                b += 1
            return i, b, "nang"
    if n <= 3:
        a = 1 if n > 1 and s[0] in NOI else 0
        return a, n, None
    k = 3 if n >= 6 else 2
    a = n - k
    if s[a] in NOI and k > 1:                     # từ chính không mở bằng từ nối ("KHI GIÀN" → dẫn "… khi", chính "GIÀN DƯA…")
        a += 1
    return a, n, None


CS = {"một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5, "sáu": 6, "bảy": 7, "tám": 8, "chín": 9}
SO_CHU = set(CS) | {"mười", "mươi", "trăm", "nghìn", "ngàn", "triệu", "chục", "linh", "lẻ"}
MO_HO = {"năm", "ba", "tư", "lăm", "mươi", "linh", "lẻ", "chục", "trăm", "nghìn", "ngàn", "triệu", "mốt"}   # đứng 1 mình dễ là chữ thường


def _doi_so(toks):
    """['hai','trăm','bốn','mươi'] → 240; không đọc được → None."""
    tong = tram = cur = 0
    for t in toks:
        if t in CS:
            cur += CS[t]
        elif t == "mười":
            cur += 10
        elif t in ("mươi", "chục"):
            cur = (cur or 1) * 10
        elif t == "trăm":
            tram, cur = (cur or 1) * 100, 0
        elif t in ("nghìn", "ngàn"):
            tong, tram, cur = tong + (tram + (cur or 1)) * 1000, 0, 0
        elif t == "triệu":
            tong, tram, cur = tong + (tram + (cur or 1)) * 1000000, 0, 0
        elif t in ("linh", "lẻ"):
            continue
        else:
            return None
    return tong + tram + cur


def so_hoa(text):
    """Số đọc bằng chữ → chữ số như v10: "hai trăm bốn mươi mi li" → "240ml", "một tháng" → "1 tháng". Chữ đứng một mình dễ nhầm (năm, ba, tư) chỉ đổi khi theo sau là đơn vị."""
    toks, out, i = str(text).split(), [], 0
    while i < len(toks):
        j = i
        while j < len(toks) and _sach(toks[j]) in SO_CHU:
            j += 1
        sau = _sach(toks[j]) if j < len(toks) else ""
        cum = [_sach(t) for t in toks[i:j]]
        if j > i and cum != ["chục"] and not (j - i == 1 and cum[0] in MO_HO and sau not in DON_VI and (i == 0 or _sach(toks[i - 1]) != "thứ")):     # "cả chục nắp" giữ chữ
            if len(cum) == 2 and all(c in CS for c in cum):          # "hai, ba nắp" là khoảng 2-3, không cộng thành 5
                out.append(f"{CS[cum[0]]}-{CS[cum[1]]}" + re.sub(r"[\w%]+", "", toks[j - 1])); i = j
                continue
            v = _doi_so(cum)
            if v is not None and v >= 10000:              # "một triệu" → "1 triệu", "mười lăm nghìn" → "15.000" (không ra 1000000 khó đọc)
                v = f"{v // 1000000} triệu" if v % 1000000 == 0 else f"{v:,}".replace(",", ".")
            if v is not None:
                out.append(str(v) + re.sub(r"[\w%]+", "", toks[j - 1])); i = j
                continue
        out.append(toks[i]); i += 1
    r = " ".join(out)
    r = re.sub(r"\b(bình) (\d+)(?![\d\s]*(lít|l|ml|mi)\b)", r"\1 \2L", r, flags=re.I)     # "bình mười sáu" = bình 16L
    return re.sub(r"(\d)\s*(mi\s*li|mi-li|mililít|ml)\b", r"\1ml", r, flags=re.I)


def _co(key):
    L = len(key)
    return 178 if L <= 7 else 160 if L <= 10 else 146 if L <= 13 else 128


def _dan_so(ws):
    """Chữ dẫn hiện từng từ theo lời; cụm số đọc gộp thành 1 chữ số, hiện lúc từ đầu cụm được đọc."""
    out, i = [], 0
    while i < len(ws):
        j = i
        while j < len(ws) and _sach(ws[j]["w"]) in SO_CHU:
            j += 1
        if j > i + 1 or (j == i + 1 and _sach(ws[i]["w"]) not in MO_HO):
            g = so_hoa(" ".join(w["w"] for w in ws[i:j]))
            out.append({"w": g.strip(",;:…").lower(), "f": max(0, int(round(ws[i]["s"] * FPS)) - 2)}); i = j
            continue
        out.append({"w": ws[i]["w"].strip(",;:…").lower(), "f": max(0, int(round(ws[i]["s"] * FPS)) - 2)}); i += 1
    return out


BO_PHAN = {"lá", "đọt", "rễ", "bông", "trái", "cây", "hoa", "cành", "đọt"}
SAU_HAI = {"trĩ", "rệp", "sâu", "nấm"}            # tên sâu bệnh: cần chữ đứng trước ("bọ trĩ", "rệp sáp")


def _chu_hook(sents, toi_da=16):
    """Chữ khổng lồ mở video từ câu đầu (Kid 24/11: hook đau thay tên hàng): cụm triệu chứng ("ỚT VÀNG LÁ", "VẪN CÒI?"),
    không có thì cụm số mạnh ("1 TRIỆU NHÀ VƯỜN"); không có gì → None (dùng tên hàng)."""
    ws = [_sach(w["w"]) for w in sents[0]["words"]] if sents and sents[0].get("words") else []
    hoi = "?" if sents and "?" in str(sents[0].get("text", "")) else ""
    for i, w in enumerate(ws):
        if not XAU.fullmatch(w):
            continue
        j = i
        while j + 1 < len(ws) and XAU.fullmatch(ws[j + 1]):
            j += 1
        a, b = i, j + 1
        cat = {k + 1 for k, x in enumerate(sents[0]["words"]) if re.search(r"[,;:.!?…]$", x["w"])}     # không vượt dấu câu
        if a > 0 and ws[a - 1] not in NOI and a not in cat and (b - a == 1 or w in SAU_HAI):
            a -= 1
            while w not in SAU_HAI and i - a < 3 and a > 0 and ws[a - 1] not in NOI and a not in cat:    # "ĐỌT NON RA TRỄ"
                a -= 1
        if b < len(ws) and ws[b] in BO_PHAN:
            b += 1
        if w == "vẫn" and b - a == 1:
            continue
        to = (so_hoa(" ".join(ws[a:b])).upper() + hoi).strip()
        if len(to) <= toi_da:
            return to
    for i in range(len(ws)):                          # cụm số MẠNH (≥ 10 hoặc triệu/nghìn) + tối đa 2 chữ sau; "1 nắp 1" không đủ làm hook
        if ws[i] not in SO_CHU or ws[i] in MO_HO:
            continue
        m = re.match(r"(\d[\d.,]*)(\s+(triệu|nghìn|ngàn))?((\s+[^\s\d]+){0,2})", so_hoa(" ".join(ws[i:i + 6])))
        if not m or (int(re.sub(r"\D", "", m.group(1)) or 0) < 10 and not m.group(3)):
            continue
        duoi = [x for x in m.group(4).split()]
        while duoi and duoi[-1] in NOI:
            duoi.pop()
        to = " ".join([m.group(1) + (m.group(2) or "")] + duoi).upper()
        while len(to) > toi_da and " " in to:
            to = to.rsplit(" ", 1)[0]
        if len(to) <= toi_da and duoi:
            return to
    return None


def tao_khoi(sents, keys, ten_hang, total, rng, bang=None, do_mat=None, nhan_o=None, qua_txt=None):
    """→ dict props.loi cho Remotion ChuTheoLoi. do_mat(t0, t1) → (fx, fy)|None; nhan_o(t0, t1) → [(x0,y0,x1,y1)] hộp nhãn chai trên màn."""
    if not sents:
        return None
    ten = [_sach(x) for x in str(ten_hang or "").split() if _sach(x)]
    khoi = _cat_khoi(sents, ten)
    # đoạn câu chuyện: trước câu có tên hàng = vấn đề; câu tên hàng = kết quả (tên = brand); sau đó: số/giỏ/quà = giá trị, còn lại kết quả; 2 câu cuối = chốt
    co_ten = next((i for i, s in enumerate(sents) if ten and _tim(s["words"], ten[:3])), None)
    if co_ten is None:
        co_ten = max(1, round(len(sents) * 0.4))
    ns = len(sents)
    bang = bang or rng.choice(sorted(BANG_MAU))
    mau = BANG_MAU[bang]
    fchinh = rng.choice(FONT_CHINH)
    ften = rng.choice([f for f in FONT_CHINH if f != fchinh])
    out, truoc_mode, _lap, deco, tail_dung, tren = [], None, 0, {"shake": 0, "under": 0}, 0, None
    kb = next((k for k, kh in enumerate(khoi) if _tu_chinh(kh["ws"], keys, ten)[2] == "brand"), None)
    dem_mode, dem_look = {}, {"hop": 0, "vien": 0}
    for k, kh in enumerate(khoi):
        ws, si = kh["ws"], kh["si"]
        a, b, vr = _tu_chinh(ws, keys, ten)
        # chữ sau từ chính: chỉ là từ nối ("là", "rồi"…) → bỏ khỏi hình; ≤ 3 từ → ĐUÔI nhỏ (1 lần/video); dài hơn → từ chính = cụm cuối
        e = len(ws)
        while e > b and _sach(ws[e - 1]["w"]) in NOI:
            e -= 1
        if b < e:
            if e - b <= 3 and not tail_dung:
                tail_dung = 1
            elif vr == "nang" and e - b <= 5:            # chữ nặng giữ làm từ chính, phần sau thành dòng đuôi nhỏ
                pass
            elif vr != "brand":
                a, b = (len(ws) - min(3, len(ws)), len(ws))
                e = len(ws)
                cam = _cam(ws, ten)
                while a > 0 and cam[a]:                   # không cắt giữa cụm số ("10 | 6 LÀ ĐỦ" → "16L LÀ ĐỦ")
                    a -= 1
        if a > 0 and _sach(ws[a]["w"]) in SO_CHU and _sach(ws[a - 1]["w"]) == "bình":
            a -= 1                                        # "BÌNH 16L" đi liền
        ws_hien = ws[:e] if b <= e else ws
        while b - a > 1 and _sach(ws[b - 1]["w"]) in NOI:   # từ chính không kết bằng từ nối ("TIỀN LÀ" → "TIỀN")
            b -= 1
        key = re.sub(r"(\d)ML\b", r"\1ml", so_hoa(" ".join(w["w"] for w in ws[a:b]).strip(" ,.;:…!?")).upper())
        dan = _dan_so(ws[:a])
        duoi = so_hoa(" ".join(w["w"] for w in ws_hien[b:]).strip(" ,.;:…")).lower() if b < len(ws_hien) else ""
        txt = " ".join(_sach(w["w"]) for w in ws)
        if vr == "brand":
            vai = "brand"
        elif (kb is not None and k < kb and si <= co_ten) or (kb is None and si < co_ten):    # vấn đề: mọi khối trước khối tên hàng
            vai = "warn"
        elif si >= ns - 2 or (si > co_ten and (SO.search(key.lower()) or GIA_TRI.search(txt))):
            vai = "val"
        else:
            vai = "res"
        so = bool(SO.search(key.lower()))
        # Kid 26/11: màu theo NGHĨA của từ chính, không chỉ theo đoạn: chữ nặng (héo, thối, gục…) luôn màu cảnh báo dù nằm sau tên hàng;
        # chữ kết quả tốt (xanh, bung, rễ trắng…) mang màu giá trị thay vì trắng trơn.
        nang = vai != "brand" and bool(XAU.search(key.lower()))
        tot = vai == "res" and bool(TOT.search(key.lower()))
        mau_k = mau["warn"] if nang else mau["val"] if tot else mau[vai]
        if vai == "brand":
            uu = ["type", "slam", "nay", "roi"] if so else ["slam", "nay", "quet"]
        elif nang:
            uu = ["dau", "glitch", "slam"]
        elif so:
            uu = ["type", "slam", "nay", "roi"]
        elif vai == "warn":
            uu = ["slam", "fade", "quet"]
        elif vai == "val":
            uu = ["fade", "type", "slam", "quet", "nay"]
        else:
            uu = ["slam", "fade", "quet", "nay"]
        con = [m for m in uu if dem_mode.get(m, 0) < TRAN_MODE.get(m, 99) and m != truoc_mode]     # không lặp kiểu liền kề, có trần mỗi kiểu
        mode = rng.choice(con or [m for m in ("slam", "fade") if m != truoc_mode])
        dem_mode[mode] = dem_mode.get(mode, 0) + 1
        truoc_mode = mode
        d = None
        if (vai == "warn" or nang) and XAU.search(txt) and mode not in ("dau", "glitch") and deco["shake"] < 1 and rng.random() < 0.6:
            d = "shake"
        elif vai == "val" and not so and deco["under"] < 1 and k > 2 and rng.random() < 0.5:
            d = "under"
        if d:
            deco[d] += 1
        look = "gloss" if vai == "brand" else "flat"
        if look == "flat" and mode not in ("glitch", "dau") and not d:          # nhãn dán / chữ rỗng: điểm nhấn, ≤ 2 lần mỗi kiểu
            if (vai == "val" or tot or so) and dem_look["hop"] < 2 and rng.random() < 0.4:
                look = "hop"
            elif vai in ("res", "warn") and mode in ("fade", "slam", "quet") and dem_look["vien"] < 2 and rng.random() < 0.3:
                look = "vien"
            dem_look[look] = dem_look.get(look, 0) + 1
        nghieng = rng.choice([-4, -3, 3, 4]) if vai != "brand" and mode != "dau" and rng.random() < 0.3 else 0
        for x in dan:                                     # chữ dẫn: từ nặng / con số đổi màu riêng
            if XAU.fullmatch(_sach(x["w"])):
                x["m"] = mau["warn"]
            elif re.search(r"\d", x["w"]):
                x["m"] = mau["val"]
        f0 = max(0, int(round(ws[0]["s"] * FPS)) - 2)
        out.append({"f0": f0, "dan": dan, "key": key, "kf": max(f0, int(round(ws[a]["s"] * FPS)) - 2) if a < len(ws) else f0, "duoi": duoi,
                    "vai": vai, "mau": mau_k, "co": min(_co(key), 132) if vai == "brand" else _co(key), "mode": mode, "deco": d,
                    "font": ften if vai == "brand" else fchinh, "look": look, "nghieng": nghieng,
                    "icon": "gio" if "GIỎ" in key else None, "t_cau": sents[si]["s"]})
    for i, x in enumerate(out):                    # cắt cứng: khối hiện tới lúc khối sau vào
        x["f1"] = out[i + 1]["f0"] if i + 1 < len(out) else int(round(total * FPS))
    # vị trí: xen kẽ trên/dưới, theo chỗ trống của cảnh (mặt người, nhãn chai). Khối chốt (2 cuối) ở dưới sâu hơn một chút.
    for i, x in enumerate(out):
        t0, t1 = x["f0"] / FPS, x["f1"] / FPS
        diem = {"tren": 0.0, "duoi": 0.0}
        m = do_mat(t0, t1) if do_mat else None
        if m:
            diem["tren" if m[1] < 0.45 else "duoi"] += 2.0 if 0.25 < m[1] < 0.7 else 1.0
        for (x0, y0, x1, y1) in (nhan_o(t0, t1) if nhan_o else []):
            if y0 < 600:
                diem["tren"] += 1.5
            if y1 > 1300:
                diem["duoi"] += 1.5
        if tren is not None:                          # ưu tiên xen kẽ khi cảnh không quyết
            diem["tren" if tren else "duoi"] += 0.6
        tren = diem["tren"] < diem["duoi"] or (diem["tren"] == diem["duoi"] and i % 2 == 0)
        x["vt"] = "tren" if tren else "duoi"
        x["y"] = 360 if tren else (1560 if i >= len(out) - 2 else 1480)
    hook = None
    if out and (ten or _chu_hook(sents)):             # chữ khổng lồ vàng kim (chỉ 1 lần): câu đau/số mạnh của câu mở, không có mới dùng tên hàng
        to = _chu_hook(sents)
        if not to:
            to = " ".join(str(ten_hang).split()[:2]).upper()
            if len(to) > 10:
                to = str(ten_hang).split()[0].upper()
        hook = {"text": to, "f0": 0, "f1": out[1]["f0"] if len(out) > 1 else out[0]["f1"], "kieu": rng.choice(["flicker", "flash", "drop"])}
        out[0]["vt"], out[0]["y"] = "duoi", 1480     # chữ khổng lồ chiếm phía trên → khối đầu xuống dưới
    qua = None
    noi_qua = any(re.search(r"tặng|quà", (x["key"] + " " + " ".join(d["w"] for d in x["dan"])).lower()) for x in out[-3:])
    if qua_txt and out and not noi_qua:              # Kid: video nào cũng khép bằng quà thật → lời chưa nhắc thì hiện dòng quà ở khối cuối, phía đối diện
        cuoi = out[-1]
        qua = {"text": str(qua_txt).upper()[:30], "f0": cuoi["kf"], "f1": cuoi["f1"], "y": 1500 if cuoi["vt"] == "tren" else 380, "mau": mau["val"]}
    return {"khoi": out, "hook": hook, "qua": qua, "bang": bang, "font": fchinh, "font_ten": ften, "dan_mau": mau["dan"],
            "het_loi_f": int(round(sents[-1]["e"] * FPS))}


def lich_am(loi):
    """Khối theo lời → khối cho sfx.len_lich (loại loi_<kiểu hiện>, mốc = lúc từ chính hiện)."""
    bl = []
    if loi and loi.get("hook"):
        h = loi["hook"]
        bl.append({"loai": "loi_hook_" + h["kieu"], "f0": h["f0"], "f1": h["f1"], "text": h["text"]})
    for x in (loi or {}).get("khoi", []):
        bl.append({"loai": f"loi_{x['mode']}", "f0": x["kf"], "f1": x["f1"], "text": x["key"], "vai": x["vai"], "deco": x.get("deco"), "n": 1})
    if loi and loi.get("het_loi_f"):             # v10: chuông khép video lúc hết lời
        bl.append({"loai": "loi_khep", "f0": loi["het_loi_f"], "f1": loi["het_loi_f"] + 30, "text": ""})
    return bl
