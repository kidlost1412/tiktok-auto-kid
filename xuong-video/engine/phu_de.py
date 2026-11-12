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


def chia_dong(text, dong_ai, words, emph_keys=()):
    plain = re.sub(r"\[[^\]]*\]\s*", "", text).strip()
    lines = dong_ai if dong_ai and _toks(" ".join(dong_ai)) == _toks(plain) and all(3 <= len(l.split()) <= 12 for l in dong_ai) \
        else auto_lines(plain)
    keys = [k.lower() for k in emph_keys if k]
    out = []
    for ln, (a, b) in zip(lines, chia_tu([_tu_dem(ln) for ln in lines], words)):
        ws = words[a:b]
        if not ws:
            continue
        out.append({"text": ln, "f0": int(round(ws[0]["s"] * FPS)), "f1": int(round(ws[-1]["e"] * FPS)),
                    "words": [{"w": w["w"], "f0": int(round(w["s"] * FPS)), "f1": int(round(w["e"] * FPS)),
                               "emph": any(k in w["w"].lower() for k in keys)} for w in ws]})
    return out, (lines is dong_ai)
