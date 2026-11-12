"""Khâu dựng: phương án dựng (JSON) + giọng có mốc từ → MP4 9:16.
Mọi lựa chọn phong cách nằm trong MENU; AI chọn tổ hợp khác nhau cho từng video."""
import random, re, subprocess
import bo_cuc as BC
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
CFG = cfg_hub()
W, H, FPS = CFG["video"]["w"], CFG["video"]["h"], CFG["video"]["fps"]

# ---------------------------------------------------------------- MENU
MENU = {
    "chuyen_canh": ["cat", "fade", "slideleft", "slideup", "zoomin", "smoothleft", "smoothup", "hon_hop"],
    "chuyen_dong": ["zoom_vao", "zoom_ra", "lia_trai", "lia_phai", "dung", "hon_hop"],
    "mau": {
        "tu_nhien": "eq=contrast=1.03:saturation=1.05",
        "tuoi": "eq=contrast=1.06:saturation=1.22:brightness=0.01",
        "am": "eq=contrast=1.05:saturation=1.12,colorbalance=rs=0.04:gs=0.01:bs=-0.04:rm=0.03:bm=-0.03",
        "tuong_phan": "curves=preset=medium_contrast,eq=saturation=1.12",
        "mat": "eq=contrast=1.04:saturation=1.08,colorbalance=bs=0.03:bm=0.02",
    },
    "nhip": ["vua", "nhanh"],
}


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
    vmin = plan.get("vmin") or CFG["video"]["thoi_luong_min"]   # độ dài đích theo sản phẩm (ekip ghi vào plan)
    total = round(max(voice["dur"] + 0.6, vmin + 0.3), 2)
    segs = [dict(x) for x in plan["edl_segs"]]   # bảng dựng của AI đạo diễn
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
    fc.append(f"[vc]tpad=stop_mode=clone:stop_duration=3,trim=duration={total}[vout]")   # chỉ dựng nền; chữ do Remotion làm rồi ghép sau
    if music:
        mdb = CFG["nhac"]["thap_hon_giong_db"]
        fc.append(f"[{vi_audio+1}:a]atrim=0:{total},asetpts=PTS-STARTPTS,loudnorm=I=-14:TP=-2,volume=-{mdb}dB,"
                  f"afade=t=in:d=0.5,afade=t=out:st={total-1.2:.2f}:d=1.2[m]")
        fc.append(f"[{vi_audio}:a]apad=whole_dur={total},asplit=2[v][key]")
        fc.append("[m][key]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=300[md]")
        fc.append("[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89[aout]")
    else:
        fc.append(f"[{vi_audio}:a]apad=whole_dur={total}[aout]")
    enc = ["-preset", "veryfast", "-crf", "17"]
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
            "canh": [f"{s['shot']['file'][:24]}@{s['src_start']}+{s['dur']:.1f}" for s in segs]}
