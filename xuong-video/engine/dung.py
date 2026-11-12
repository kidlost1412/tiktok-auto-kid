"""Khâu dựng: phương án dựng (JSON) + giọng có mốc từ → MP4 9:16.
Mọi lựa chọn phong cách nằm trong MENU; AI chọn tổ hợp khác nhau cho từng video."""
import json, random, re, subprocess
import bo_cuc as BC
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
CFG = cfg_hub()
W, H, FPS = CFG["video"]["w"], CFG["video"]["h"], CFG["video"]["fps"]

# ---------------------------------------------------------------- MENU
MENU = {
    "font": ["Arial Black", "Segoe UI Black", "Arial", "Segoe UI", "Tahoma", "Verdana", "Trebuchet MS"],
    "phu_de": {  # (màu chữ nền, màu sáng karaoke, viền, kiểu viền 1=viền 3=hộp, viết hoa)
        "vang_vien_den":   ("&H00FFFFFF", "&H0000D7FF", "&H00000000", 1, False),
        "xanh_vien_den":   ("&H00FFFFFF", "&H0044C93A", "&H00000000", 1, False),
        "do_vien_trang":   ("&H00FFFFFF", "&H002E26D7", "&H00101010", 1, True),
        "hop_den_vang":    ("&H00FFFFFF", "&H0000D7FF", "&H96000000", 3, False),
        "hop_xanh_trang":  ("&H00D8FFD8", "&H00FFFFFF", "&H00449E2E", 3, True),
        "hop_do_vang":     ("&H00FFFFFF", "&H0000E5FF", "&H00262ED7", 3, True),
        "trang_bong":      ("&H00B8B8B8", "&H00FFFFFF", "&H00000000", 1, True),
    },
    "kieu_karaoke": ["quet", "nhay_tu", "tung_cum"],   # \kf quét / \k nhảy / hiện 1–2 từ to
    "vi_tri_phu_de": {"duoi": (2, 520), "giua": (5, 0), "tren_giua": (8, 560)},
    "chuyen_canh": ["cat", "fade", "slideleft", "slideup", "zoomin", "smoothleft", "smoothup", "hon_hop"],
    "chuyen_dong": ["zoom_vao", "zoom_ra", "lia_trai", "lia_phai", "dung", "hon_hop"],
    "mau": {
        "tu_nhien": "eq=contrast=1.03:saturation=1.05",
        "tuoi": "eq=contrast=1.06:saturation=1.22:brightness=0.01",
        "am": "eq=contrast=1.05:saturation=1.12,colorbalance=rs=0.04:gs=0.01:bs=-0.04:rm=0.03:bm=-0.03",
        "tuong_phan": "curves=preset=medium_contrast,eq=saturation=1.12",
        "mat": "eq=contrast=1.04:saturation=1.08,colorbalance=bs=0.03:bm=0.02",
    },
    "the_mo": ["bang_do", "bang_xanh", "chu_lon_giua", "gach_chan", "khong"],
    "the_chot": ["khung_xanh", "bang_do", "chu_lon", "the_trang"],
    "nhip": ["vua", "nhanh"],
}
SAFE_TOP = int(H * 0.12)


def pick(menu_key, value):
    opts = MENU[menu_key]
    keys = list(opts) if isinstance(opts, dict) else opts
    return value if value in keys else random.choice(keys)


# ---------------------------------------------------------------- câu & thời gian
def split_sentences(text_no_tag):
    parts = re.split(r"(?<=[.!?])\s+", text_no_tag.strip())
    return [p for p in parts if p.strip()]


def sentence_times(text, words):
    """Ghép từ có mốc thời gian vào từng câu theo số từ (lệch số từ → dóng theo nội dung từ)."""
    plain = re.sub(r"\[[^\]]*\]", "", text)
    sents = split_sentences(plain)
    from phu_de import chia_tu, _tu_dem       # đếm từ như giọng; lệch số từ → dóng theo từ, không trôi câu sau
    out = []
    for s, (a, b) in zip(sents, chia_tu([_tu_dem(s) for s in sents], words)):
        ws = words[a:b]
        if ws:
            out.append({"text": s, "s": ws[0]["s"], "e": ws[-1]["e"], "words": ws})
    return out


# ---------------------------------------------------------------- chọn cảnh
def choose_shots(plan, sents, total, shots, rng):
    """Mỗi câu một (hoặc hai nếu dài) cảnh theo vai trò AI chỉ định; không dùng lại cùng đoạn."""
    by_id = {s["id"]: s for s in shots}
    used, segs = set(), []
    want = plan.get("canh", [])
    fast = plan["phong_cach"].get("nhip") == "nhanh"
    bounds = []
    for k, s in enumerate(sents):
        a = 0.0 if k == 0 else (sents[k - 1]["e"] + s["s"]) / 2
        b = total if k == len(sents) - 1 else (s["e"] + sents[k + 1]["s"]) / 2
        bounds.append((a, b))
    for k, (a, b) in enumerate(bounds):
        spec = want[k] if k < len(want) else {}
        roles = spec.get("vai_tro") or ["chai_ro"]
        roles = roles if isinstance(roles, list) else [roles]
        maxlen = 3.0 if fast else 3.8
        remaining, first = b - a, True
        while remaining > 0.05:
            want_len = min(remaining, maxlen)
            if remaining - want_len < 0.9:          # tránh mẩu cuối quá ngắn
                want_len = remaining
            need = min(want_len, 1.0)              # chấp nhận cảnh ngắn đúng vai trò rồi ghép tiếp
            ok = [s for s in shots if "nguoi_noi" not in s["vai_tro"] and s["dai"] >= need]  # tránh lệch khẩu hình
            fresh = lambda xs: [s for s in xs if (s["file"], int(s["tu"])) not in used]
            forced = [by_id[i] for i in spec.get("shot_ids", []) if i in by_id] if first else []
            tiers = [fresh(forced),
                     fresh([s for s in ok if set(roles) & set(s["vai_tro"])]),
                     [s for s in ok if set(roles) & set(s["vai_tro"])],
                     fresh([s for s in ok if "chai_ro" in s["vai_tro"]]),
                     ok, shots]
            pool = next(t for t in tiers if t)
            sh = pool[0] if pool is tiers[0] else rng.choice(pool)
            take = min(want_len, sh["dai"])
            if remaining - take < 0.6:
                take = remaining if sh["dai"] >= remaining else take
            edge = 0.3 if sh["tu"] < 0.3 else 0.0          # né khung loé/fade ở đầu clip gốc của AFF
            slack = max(0.0, sh["dai"] - take - edge)
            start = sh["tu"] + edge + (rng.uniform(0, slack) if slack > 0.2 else 0)
            used.add((sh["file"], int(sh["tu"])))
            segs.append({"shot": sh, "src_start": round(start, 2), "dur": round(take, 3)})
            remaining -= take; first = False
    merged = []                                         # không để mẩu cảnh < 0,8 s (gây giật/loé)
    for sg in segs:
        if merged and sg["dur"] < 0.8:
            merged[-1]["dur"] = round(merged[-1]["dur"] + sg["dur"], 3)
        else:
            merged.append(sg)
    if len(merged) > 1 and merged[0]["dur"] < 0.8:
        merged[1]["dur"] = round(merged[1]["dur"] + merged[0]["dur"], 3)
        merged[1]["src_start"] = max(merged[1]["shot"]["tu"], merged[1]["src_start"] - merged[0]["dur"])
        merged.pop(0)
    return merged


# ---------------------------------------------------------------- phụ đề ASS
def ass_time(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def chunk_words(ws, mode):
    size = 2 if mode == "tung_cum" else 4
    chunks, cur = [], []
    for w in ws:
        cur.append(w)
        end_punct = re.search(r"[.,!?…:]$", w["w"])
        if len(cur) >= size or (end_punct and len(cur) >= 2):
            chunks.append(cur); cur = []
    if cur:
        if chunks and len(cur) == 1:
            chunks[-1] += cur
        else:
            chunks.append(cur)
    return chunks


def build_ass(plan, sents, total, brand, cta_from):
    st = plan["phong_cach"]
    font = pick("font", st.get("font"))
    pstyle = pick("phu_de", st.get("phu_de"))
    base, hi, outline, bstyle, upper = MENU["phu_de"][pstyle]
    kmode = pick("kieu_karaoke", st.get("kieu_karaoke"))
    align, mv = MENU["vi_tri_phu_de"][pick("vi_tri_phu_de", st.get("vi_tri_phu_de"))]
    size = 104 if kmode == "tung_cum" else 86
    keys = [k.lower() for k in st.get("nhan_tu", [])]
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Sub,{font},{size},{hi},{base},{outline},&H80000000,-1,0,0,0,100,100,0,0,{bstyle},{7 if bstyle == 1 else 16},{2 if bstyle == 1 else 0},{align},110,170,{mv},1",
        f"Style: Brand,{font},60,&H00FFFFFF,&H00FFFFFF,&H00262ED7,&H00262ED7,-1,0,0,0,100,100,1,0,3,16,0,8,90,90,{SAFE_TOP + 40},1",
        f"Style: BrandG,{font},60,&H00FFFFFF,&H00FFFFFF,&H00449E2E,&H00449E2E,-1,0,0,0,100,100,1,0,3,16,0,8,90,90,{SAFE_TOP + 40},1",
        f"Style: Big,{font},118,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,9,4,5,90,90,0,1",
        f"Style: Cta,{font},64,&H00FFFFFF,&H00FFFFFF,&H00449E2E,&H00449E2E,-1,0,0,0,100,100,1,0,3,18,0,8,90,90,{SAFE_TOP + 150},1",
        f"Style: CtaR,{font},64,&H00FFFFFF,&H00FFFFFF,&H00262ED7,&H00262ED7,-1,0,0,0,100,100,1,0,3,18,0,8,90,90,{SAFE_TOP + 150},1",
        f"Style: CtaW,{font},62,&H00262ED7,&H00262ED7,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,1,0,3,18,0,8,90,90,{SAFE_TOP + 150},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    # phụ đề karaoke
    allw = [w for s in sents for w in s["words"]]
    tag = r"\kf" if kmode == "quet" else r"\k"
    chunks = chunk_words(allw, kmode)
    for ci, ch in enumerate(chunks):
        a = ch[0]["s"] - 0.05
        b = ch[-1]["e"] + 0.12
        if ci + 1 < len(chunks):
            b = min(b, chunks[ci + 1][0]["s"] - 0.06)   # không đè cụm sau
        txt = ""
        for j, w in enumerate(ch):
            nxt = ch[j + 1]["s"] if j + 1 < len(ch) else w["e"]
            cs = max(1, int(round((nxt - w["s"]) * 100)))
            word = w["w"].upper() if upper else w["w"]
            emph = any(k in w["w"].lower() for k in keys)
            pre = r"{\fscx118\fscy118}" if emph else ""
            post = r"{\fscx100\fscy100}" if emph else ""
            txt += f"{{{tag}{cs}}}{pre}{word}{post} "
        pop = r"{\fad(40,0)\t(0,90,\fscx106\fscy106)\t(90,180,\fscx100\fscy100)}" if kmode != "quet" else r"{\fad(60,0)}"
        lines.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Sub,,0,0,0,,{pop}{txt.strip()}")
    # thẻ mở
    mo = pick("the_mo", st.get("the_mo"))
    t_mo = st.get("chu_the_mo") or brand.upper()
    end_mo = min(3.2, sents[0]["e"] + 0.3)
    if mo == "bang_do":
        lines.append(f"Dialogue: 1,{ass_time(0.1)},{ass_time(end_mo)},Brand,,0,0,0,,{{\\fad(120,150)}}{t_mo}")
    elif mo == "bang_xanh":
        lines.append(f"Dialogue: 1,{ass_time(0.1)},{ass_time(end_mo)},BrandG,,0,0,0,,{{\\fad(120,150)}}{t_mo}")
    elif mo == "chu_lon_giua":
        lines.append(f"Dialogue: 1,{ass_time(0.0)},{ass_time(1.4)},Big,,0,0,0,,{{\\fad(0,200)\\t(0,250,\\fscx104\\fscy104)}}{t_mo}")
    elif mo == "gach_chan":
        lines.append(f"Dialogue: 1,{ass_time(0.1)},{ass_time(end_mo)},Brand,,0,0,0,,{{\\fad(120,150)\\move(540,{SAFE_TOP+40},540,{SAFE_TOP+60})}}{t_mo}")
    # thẻ chốt
    chot = pick("the_chot", st.get("the_chot"))
    d1 = st.get("chu_chot_1", "QUÀ TẶNG THEO ĐƠN"); d2 = st.get("chu_chot_2", "BẤM GIỎ HÀNG")
    style = {"khung_xanh": "Cta", "bang_do": "CtaR", "chu_lon": "Big", "the_trang": "CtaW"}[chot]
    eff = r"{\fad(180,0)\t(0,220,\fscx106\fscy106)\t(220,400,\fscx100\fscy100)}"
    lines.append(f"Dialogue: 2,{ass_time(cta_from)},{ass_time(total)},{style},,0,0,0,,{eff}{d1}\\N{d2}")
    # mũi tên chỉ giỏ hàng (góc trái dưới)
    arrow = "m 0 0 l 60 0 l 60 90 l 110 90 l 30 170 l -50 90 l 0 90"   # mũi tên chỉ xuống (vẽ vector)
    y0 = int(H * 0.70)
    lines.append(f"Dialogue: 2,{ass_time(cta_from + 0.3)},{ass_time(total)},Sub,,0,0,0,,"
                 rf"{{\an7\bord5\shad0\1c&H0000D7FF&\3c&H00000000&\fad(150,0)\move(95,{y0},95,{y0+40},0,400)\p1}}{arrow}{{\p0}}")
    return "\n".join(lines) + "\n", {"font": font, "phu_de": pstyle, "kieu_karaoke": kmode, "the_mo": mo, "the_chot": chot}


# ---------------------------------------------------------------- video
def motion_filter(kind, dur, rng):
    if kind == "hon_hop":
        kind = rng.choice(["zoom_vao", "zoom_ra", "lia_trai", "lia_phai", "dung"])
    z = 0.07
    if kind == "zoom_vao":
        sc = f"scale=w='trunc({W}*(1.04+{z}*t/{dur:.3f})/2)*2':h=-2:eval=frame"
    elif kind == "zoom_ra":
        sc = f"scale=w='trunc({W}*(1.04+{z}*(1-t/{dur:.3f}))/2)*2':h=-2:eval=frame"
    else:
        sc = f"scale={int(W*1.10)//2*2}:-2"
    if kind == "lia_trai":
        cr = f"crop={W}:{H}:x='(iw-{W})*(1-t/{dur:.3f})':y='(ih-{H})/2'"
    elif kind == "lia_phai":
        cr = f"crop={W}:{H}:x='(iw-{W})*t/{dur:.3f}':y='(ih-{H})/2'"
    else:
        cr = f"crop={W}:{H}:x='(iw-{W})/2':y='(ih-{H})/2'"
    return kind, f"{sc},{cr}"


def render(plan, voice, shots, kho, out_path, music=None):
    rng = random.Random(plan.get("seed", 0))
    st = plan["phong_cach"]
    sents = sentence_times(voice["text"], voice["words"])
    vmin = CFG["video"]["thoi_luong_min"]
    total = round(max(voice["dur"] + 0.6, vmin + 0.3), 2)
    segs = [dict(x) for x in plan["edl_segs"]] if plan.get("edl_segs") else choose_shots(plan, sents, total, shots, rng)   # bảng dựng của AI đạo diễn
    trans = pick("chuyen_canh", st.get("chuyen_canh"))
    mot = pick("chuyen_dong", st.get("chuyen_dong"))
    grade = MENU["mau"][pick("mau", st.get("mau"))] + ",eq=brightness=0.0"
    if "curves" in grade:
        grade = "eq=contrast=1.10:saturation=1.15:brightness=0.01"  # tránh khung tối
    td = 0.0 if trans == "cat" else 0.28
    cmd = ["ffmpeg", "-v", "error", "-y"]
    # chống reup: gán bố cục cho từng đoạn (toàn màn / ô trên trời / khung mờ / chia đôi / lưới 4)
    layouts = BC.chon_bo_cuc(segs, rng, st.get("nhip", "vua")) if not plan.get("khong_bo_cuc") else ["day"] * len(segs)
    layouts = [sg.get("bo_cuc") or L for sg, L in zip(segs, layouts)]
    used_phu = {(sg["shot"]["file"], int(sg["shot"]["tu"])) for sg in segs}
    fc, used_motion, nin, pops, acc0 = [], [], 0, [], 0.0
    seg_dir = Path(out_path).parent / f"_{Path(out_path).stem}_doan"; seg_dir.mkdir(parents=True, exist_ok=True)
    for i, sg in enumerate(segs):
        # dựng TỪNG đoạn ra file riêng (ít luồng giải mã cùng lúc → không hết RAM), rồi mới nối + chuyển cảnh
        extra = td if i < len(segs) - 1 else 0
        d = sg["dur"] + extra
        L = layouts[i]; opt = BC.tuy_chon(rng)
        scmd, k = ["ffmpeg", "-v", "error", "-y"], 0
        sh_ = sg["shot"]; con = float(sh_.get("den", sh_["tu"] + sh_["dai"])) - float(sg["src_start"])   # phần cảnh còn được dùng
        if 0.3 < con < d - 0.1:              # không đọc lố sang đoạn đã loại (lỗi rà soát #16): quay chậm ≤ 1,6 lần, thiếu nữa thì giữ khung cuối
            opt["cham"] = round(min(1.6, d / con), 3); doc = con
        else:
            doc = d + 0.05
        scmd += ["-threads", "2", "-ss", str(sg["src_start"]), "-t", f"{doc:.3f}", "-i", str(Path(kho) / sg["shot"]["file"])]
        main_idx = k; k += 1
        phu = [{"shot": ps, "src_start": round(min(max(ps["tu"], (ps["dep"][0] + ps["dep"][1]) / 2 - d / 2), max(ps["tu"], ps["den"] - d)), 2)}
               for ps in sg.get("phu_shots", [])][:BC.SO_PHU[L]]
        phu += BC.chon_phu(sg, BC.SO_PHU[L] - len(phu), shots, rng, used_phu)
        phu_idx = []
        for ph in phu:
            scmd += ["-threads", "2", "-ss", str(ph["src_start"]), "-t", f"{d + 0.05:.3f}", "-i", str(Path(kho) / ph["shot"]["file"])]
            phu_idx.append(k); k += 1
        mask_idx = []
        for (mw, mh) in BC.mask_sizes(L, opt):
            scmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d + 0.05:.3f}", "-i", str(BC.mask(mw, mh))]
            mask_idx.append(k); k += 1
        kind, mf = motion_filter(mot, d, rng)
        used_motion.append(kind)
        lines, times = BC.loc(i, L, d, main_idx, phu_idx, mask_idx, grade, mf, opt, sg["shot"], [ph["shot"] for ph in phu])
        clip = seg_dir / f"d{i:02d}.mp4"
        scmd += ["-filter_threads", "2", "-filter_complex", ";".join(lines), "-map", f"[v{i}]", "-t", f"{d:.3f}", "-an",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-threads", "4", str(clip)]
        subprocess.run(scmd, check=True)
        cmd += ["-threads", "1", "-i", str(clip)]   # nối nhiều đoạn: 1 luồng giải mã/đoạn để không hết RAM
        fc.append(f"[{nin}:v]setpts=PTS-STARTPTS,setsar=1,fps={FPS},tpad=stop_mode=clone:stop_duration=1,trim=duration={d:.3f},setpts=PTS-STARTPTS[v{i}]")
        nin += 1
        pops += [round(acc0 + t, 2) for t in times]
        sg["bo_cuc"] = L; sg["phu"] = [ph["shot"]["file"][:12] for ph in phu]; sg["opt"] = opt; sg["t0"] = acc0
        acc0 += sg["dur"]
    cmd += ["-i", voice["audio"]]
    vi_audio = nin
    if music:
        cmd += ["-ss", str(music["start"]), "-i", music["file"]]
    if len(segs) == 1:
        fc.append("[v0]null[vc]")
    elif td == 0:
        fc.append("".join(f"[v{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[vc]")
    else:
        prev, acc = "v0", segs[0]["dur"]
        for i in range(1, len(segs)):
            t = trans if trans != "hon_hop" else rng.choice(["fade", "slideleft", "slideup", "zoomin", "smoothleft"])
            outl = "vc" if i == len(segs) - 1 else f"x{i}"
            fc.append(f"[{prev}][v{i}]xfade=transition={t}:duration={td}:offset={acc:.3f}[{outl}]")
            prev, acc = outl, acc + segs[i]["dur"]
    if plan.get("khong_chu"):  # chỉ dựng nền; chữ do Remotion làm rồi ghép sau
        ass_meta = {}
        fc.append(f"[vc]tpad=stop_mode=clone:stop_duration=3,trim=duration={total}[vout]")
    else:
        ass_txt, ass_meta = build_ass(plan, sents, total, plan.get("ten_thuong_hieu", "NANO ĐỒNG TOÀN CẦU"), sents[-1]["s"] - 0.1)
        ass_file = Path(out_path).with_suffix(".ass")
        ass_file.write_text(ass_txt, encoding="utf-8")
        ap = str(ass_file).replace("\\", "/").replace(":", "\\:")
        fc.append(f"[vc]tpad=stop_mode=clone:stop_duration=3,trim=duration={total},subtitles='{ap}'[vout]")
    if music:
        mdb = CFG["nhac"]["thap_hon_giong_db"]
        fc.append(f"[{vi_audio+1}:a]atrim=0:{total},asetpts=PTS-STARTPTS,loudnorm=I=-14:TP=-2,volume=-{mdb}dB,"
                  f"afade=t=in:d=0.5,afade=t=out:st={total-1.2:.2f}:d=1.2[m]")
        fc.append(f"[{vi_audio}:a]apad=whole_dur={total},asplit=2[v][key]")
        fc.append("[m][key]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=300[md]")
        fc.append("[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89[aout]")
    else:
        fc.append(f"[{vi_audio}:a]apad=whole_dur={total}[aout]")
    enc = ["-preset", "veryfast", "-crf", "17"] if plan.get("khong_chu") else ["-preset", "medium", "-crf", "23", "-maxrate", "9M", "-bufsize", "18M"]
    cmd += ["-filter_threads", "2", "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]", "-t", str(total), "-threads", "4",
            "-c:v", "libx264", *enc, "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_path)]
    subprocess.run(cmd, check=True)
    frames = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                                 "stream=nb_read_packets", "-of", "csv=p=0", str(out_path)], capture_output=True, text=True).stdout.strip() or 0)
    if frames < (total - 0.2) * FPS:
        raise RuntimeError(f"hình ngắn hơn tiếng: {frames / FPS:.1f}s / {total}s")
    import shutil; shutil.rmtree(seg_dir, ignore_errors=True)
    cuts, acc = [], 0.0
    for s_ in segs[:-1]:
        acc += s_["dur"]; cuts.append(round(acc, 2))
    return {"thoi_luong": total, "chuyen_canh": trans, "chuyen_dong": mot, "mau": st.get("mau"), "cuts": cuts, "pops": pops,
            "bo_cuc": [s["bo_cuc"] for s in segs], "td": td,
            "doan": [{"t0": s["t0"], "t1": s["t0"] + s["dur"], "bo_cuc": s["bo_cuc"], "opt": s.get("opt"),
                      "nhan": (s["shot"].get("soat") or {}).get("nhan")} for s in segs],
            "canh": [f"{s['shot']['file'][:24]}@{s['src_start']}+{s['dur']:.1f}" for s in segs], **ass_meta}
