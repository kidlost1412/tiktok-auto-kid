"""Kiểm âm sau khi trộn: đo bản âm cuối bằng ffmpeg + chấm lịch SFX; trả số liệu, 1 dòng tóm tắt tiếng Việt và tối đa 5
"chỗ nên nghe" (giây, gì, vì sao) để người nghe tập trung đúng chỗ. Máy KHÔNG nghe được — đây chỉ là rà lỗi cơ học.

Hàm thuần (không đụng thư mục dữ liệu):
  do_am_thanh(file)            -> {dai, lufs, dinh_that_db, lra, im_lang:[(từ, đến)], dut_dot_ngot, cuoi_db}
  chi_so_lich(ev, total)       -> {so_cu_chi, cu_chi_moi_10s, cu_chi_toi_da_10s, lo_dai_nhat, ty_le_nang, file_lap, va_cham}
  kiem_am(file, ev, total)     -> {"do", "lich", "van_de", "tom_tat", "nghe_thu"}
ev = lịch từ sfx.len_lich (mỗi sự kiện: nhom, file, t, [t_neo], [vai], [cum], [lap_ok], [ly_do]). Mốc nghe thấy = t_neo nếu có, không thì t."""
import json, math, re, subprocess

DONG_HO = 0.08          # tiếng trong 80 ms = 1 cử chỉ
VA_CHAM = 0.25          # 2 tiếng khác họ gần hơn mức này = va chạm
IM_LANG_S = 2.0
NGUONG_IM = -45         # dB
TOI_DA_10S, TOI_THIEU_10S = 8.0, 1.5
LUFS_KHOANG = (-20.0, -12.0)
DINH_THAT_TOI_DA = -1.0


def _ffmpeg(args, timeout=180):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.stderr


def thoi_luong(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True, timeout=30)
    try:
        return float(r.stdout.strip().split()[0])
    except Exception:
        return 0.0


def _so(m, mac_dinh=None):
    return float(m.group(1)) if m else mac_dinh


def do_am_thanh(f):
    """Đo bản âm cuối: độ to tổng (LUFS), đỉnh thật (dBFS), quãng lặng > 2 s, kết thúc đột ngột."""
    f = str(f)
    dai = thoi_luong(f)
    e = _ffmpeg(["-i", f, "-vn", "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"])
    tail = e[e.rfind("Summary"):] if "Summary" in e else e
    lufs = _so(re.search(r"I:\s*(-?[\d.]+|-inf)\s*LUFS", tail))
    dinh = _so(re.search(r"Peak:\s*(-?[\d.]+|-inf)\s*dBFS", tail))
    lra = _so(re.search(r"LRA:\s*([\d.]+)\s*LU", tail))
    s = _ffmpeg(["-i", f, "-vn", "-af", f"silencedetect=noise={NGUONG_IM}dB:d={IM_LANG_S}", "-f", "null", "-"])
    im, bat_dau = [], None
    for m in re.finditer(r"silence_start:\s*(-?[\d.]+)|silence_end:\s*([\d.]+)", s):
        if m.group(1) is not None:
            bat_dau = max(0.0, float(m.group(1)))
        elif bat_dau is not None:
            im.append((round(bat_dau, 2), round(float(m.group(2)), 2)))
            bat_dau = None
    if bat_dau is not None and dai - bat_dau >= IM_LANG_S:       # lặng kéo tới hết file
        im.append((round(bat_dau, 2), round(dai, 2)))
    # cắt đột ngột = 20 ms cuối còn to (> -40 dBFS) mà so với đoạn 0,5–0,3 s trước đó chỉ giảm dưới 12 dB (không có đuôi tắt dần)
    cuoi_db = _so(re.search(r"max_volume:\s*(-?[\d.]+) dB", _ffmpeg(["-sseof", "-0.02", "-i", f, "-vn", "-af", "volumedetect", "-f", "null", "-"])), -91.0)
    truoc_db = _so(re.search(r"max_volume:\s*(-?[\d.]+) dB", _ffmpeg(["-sseof", "-0.5", "-t", "0.2", "-i", f, "-vn", "-af", "volumedetect", "-f", "null", "-"])), -91.0)
    return {"dai": round(dai, 3), "lufs": lufs, "dinh_that_db": dinh, "lra": lra, "im_lang": im,
            "cuoi_db": cuoi_db, "dut_dot_ngot": cuoi_db > -40.0 and cuoi_db - truoc_db > -12.0}


# ---------------------------------------------------------------- LỊCH
def _t(x):
    return float(x.get("t_neo", x["t"]))


def _nang(x):
    return x.get("vai") == "hit" or x.get("nhom") in ("dap", "no_lon")


def _cu_chi(ev):
    """[(t, [sự kiện])]: cùng cum = 1 cử chỉ; tiếng cách nhau ≤ 80 ms = 1 cử chỉ."""
    nhom = {}
    for i, x in enumerate(sorted(ev, key=_t)):
        nhom.setdefault(x.get("cum") or f"_{i}", []).append(x)
    out = []
    for v in sorted(nhom.values(), key=lambda v: _t(v[0])):
        if out and _t(v[0]) - out[-1][0] <= DONG_HO:
            out[-1][1].extend(v)
        else:
            out.append((_t(v[0]), list(v)))
    return out


def chi_so_lich(ev, total):
    ev = list(ev or [])
    total = float(total or 0)
    gs = _cu_chi(ev)
    n = len(gs)
    ts = [g[0] for g in gs]
    moc = [0.0] + ts + [max(total, ts[-1] if ts else 0.0)]
    lo = max(((b - a, a, b) for a, b in zip(moc, moc[1:])), default=(total, 0.0, total))
    toi_da = max((sum(1 for t in ts if s <= t < s + 10) for s in ts), default=0)
    nang = sum(1 for g in gs if any(_nang(x) for x in g[1]))
    dem = {}
    for x in ev:
        if not x.get("lap_ok"):
            dem[x["file"]] = dem.get(x["file"], 0) + 1
    chan = sorted(ev, key=_t)
    vc = []
    for i, a in enumerate(chan):
        for b in chan[i + 1:]:
            if _t(b) - _t(a) >= VA_CHAM:
                break
            if a.get("nhom") != b.get("nhom") and not (a.get("cum") and a.get("cum") == b.get("cum")):
                vc.append({"t": round(_t(a), 2), "a": a.get("nhom"), "b": b.get("nhom"), "cach": round(_t(b) - _t(a), 3)})
    return {"so_cu_chi": n, "cu_chi_moi_10s": round(n / total * 10, 2) if total > 0 else 0.0, "cu_chi_toi_da_10s": toi_da,
            "lo_dai_nhat": {"giay": round(lo[0], 2), "tu": round(lo[1], 2), "den": round(lo[2], 2)},
            "so_nang": nang, "ty_le_nang": round(nang / n, 3) if n else 0.0,
            "file_lap": [{"file": f, "so_lan": c} for f, c in sorted(dem.items(), key=lambda kv: -kv[1]) if c > 2],
            "va_cham": vc}


# ---------------------------------------------------------------- TỔNG HỢP
def _vi(x, nd=1):
    return f"{x:.{nd}f}".replace(".", ",") if x is not None else "?"


def kiem_am(f, ev, total, do=None):
    """Đo + chấm. do: số đo có sẵn (để test/dùng lại). Trả {"do","lich","van_de":[str],"tom_tat":str,"nghe_thu":[{t,gi,vi_sao}]}."""
    do = do or do_am_thanh(f)
    li = chi_so_lich(ev, total)
    vd = []
    if do["lufs"] is not None and not (LUFS_KHOANG[0] <= do["lufs"] <= LUFS_KHOANG[1]):
        vd.append(f"độ to tổng {_vi(do['lufs'])} LUFS ngoài khoảng {LUFS_KHOANG[0]:.0f}…{LUFS_KHOANG[1]:.0f}")
    if do["dinh_that_db"] is not None and do["dinh_that_db"] > DINH_THAT_TOI_DA:
        vd.append(f"đỉnh thật {_vi(do['dinh_that_db'])} dBFS vượt {DINH_THAT_TOI_DA:.0f} (dễ rè khi đăng)")
    for a, b in do["im_lang"]:
        vd.append(f"lặng {_vi(b - a)} s ({_vi(a)}–{_vi(b)} s)")
    if do["dut_dot_ngot"]:
        vd.append("âm bị cắt đột ngột ở cuối")
    if li["so_cu_chi"] and li["cu_chi_toi_da_10s"] > TOI_DA_10S:
        vd.append(f"dày: {li['cu_chi_toi_da_10s']} cử chỉ trong 10 s")
    if total and total >= 6 and li["cu_chi_moi_10s"] < TOI_THIEU_10S:
        vd.append(f"thưa: {_vi(li['cu_chi_moi_10s'])} cử chỉ/10 s")
    if li["so_cu_chi"] >= 3 and li["ty_le_nang"] > 1 / 3 + 1e-9:
        vd.append(f"nhát nặng {li['so_nang']}/{li['so_cu_chi']} (quá 1/3)")
    for r in li["file_lap"]:
        vd.append(f"file lặp {r['so_lan']} lần: {str(r['file']).replace(chr(92), '/').rsplit('/', 1)[-1]}")
    for v in li["va_cham"]:
        vd.append(f"{v['a']} và {v['b']} chỉ cách {_vi(v['cach'], 2)} s (~{_vi(v['t'])} s)")
    tom = (f"Âm: {_vi(do['lufs'])} LUFS, đỉnh thật {_vi(do['dinh_that_db'])} dBFS; {li['so_cu_chi']} cử chỉ "
           f"({_vi(li['cu_chi_moi_10s'])}/10 s), lỗ dài nhất {_vi(li['lo_dai_nhat']['giay'])} s, nhát nặng {li['so_nang']}/{li['so_cu_chi']}; "
           + ("không thấy lỗi cơ học." if not vd else f"{len(vd)} điểm cần xem: " + "; ".join(vd[:4]) + ("…" if len(vd) > 4 else ".")))
    return {"do": do, "lich": li, "van_de": vd, "tom_tat": tom, "nghe_thu": chon_cho_nghe(do, ev, li, total)}


def chon_cho_nghe(do, ev, li, total, toi_da=5):
    """Tối đa 5 chỗ nên nghe bằng tai: [{"t","gi","vi_sao"}] theo thứ tự thời gian."""
    ds = []
    for v in li["va_cham"]:
        ds.append((9, v["t"], f"{v['a']} + {v['b']} sát nhau", f"chỉ cách {_vi(v['cach'], 2)} s — nghe có lổn nhổn không?"))
    for a, b in do["im_lang"]:
        ds.append((8, a, f"lặng {_vi(b - a)} s", "có đúng là chỗ để thở, hay mất tiếng?"))
    if do["dut_dot_ngot"]:
        ds.append((8, max(0.0, do["dai"] - 0.3), "đoạn cuối", "âm còn to đúng lúc hết file — nghe có bị cắt cụt không?"))
    nang = sorted((x for x in ev if _nang(x)), key=_t)
    for x in nang[:2]:
        ds.append((6, _t(x), f"nhát nặng «{x['nhom']}»", "nhát nặng có hợp hình (không át giọng, không như tiếng nổ lạc)?"))
    for x in ev:
        if x.get("vai") in ("alert", "money", "bell", "magic") and x.get("ly_do"):
            ds.append((5 if x.get("vai") != "alert" else 6, _t(x), f"{x.get('vai')} «{x['nhom']}»", x["ly_do"]))
    gs = _cu_chi(ev)
    if gs:
        s = max((g[0] for g in gs), key=lambda s: (sum(1 for g in gs if s <= g[0] < s + 10), -s))
        n = sum(1 for g in gs if s <= g[0] < s + 10)
        if n >= 5:
            ds.append((4, s, f"đoạn dày nhất ({n} cử chỉ/10 s)", "có rối tai khi vừa nghe giọng vừa nghe tiếng?"))
    lo = li["lo_dai_nhat"]
    if lo["giay"] >= 4.0 and total:
        ds.append((3, lo["tu"] + lo["giay"] / 2, f"lỗ {_vi(lo['giay'])} s không tiếng", "chỗ trống này có chủ ý hay thiếu nhấn?"))
    ds.sort(key=lambda d: (-d[0], d[1]))
    out = []
    for sc, t, gi, vs in ds:
        if all(abs(t - o["t"]) >= 1.0 for o in out):
            out.append({"t": round(t, 2), "gi": gi, "vi_sao": vs})
        if len(out) >= toi_da:
            break
    return sorted(out, key=lambda o: o["t"])
