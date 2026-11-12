"""Chia dòng phụ đề theo cụm ý và gắn mốc thời gian từng từ.
chia_dong(text, dong_ai, words) -> [{"f0","f1","words":[{"w","f0","f1","emph"}]}]"""
import re

FPS = 30


def _toks(s):
    return re.findall(r"\w+", s.lower())


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
    out, i = [], 0
    for ln in lines:
        n = len([w for w in ln.split() if re.search(r"\w", w)])
        ws = words[i:i + n]; i += n
        if not ws:
            continue
        out.append({"text": ln, "f0": int(round(ws[0]["s"] * FPS)), "f1": int(round(ws[-1]["e"] * FPS)),
                    "words": [{"w": w["w"], "f0": int(round(w["s"] * FPS)), "f1": int(round(w["e"] * FPS)),
                               "emph": any(k in w["w"].lower() for k in keys)} for w in ws]})
    return out, (lines is dong_ai)
