"""Chặng 3 — hiệu ứng âm thanh (SFX) khớp hình.
Mỗi video có 1 mức: em / vua / soi_dong / mo_dau_am. SFX bám vào: khối chữ (Remotion), điểm cắt cảnh, câu mở, nút chốt.
len_lich(...) → danh sách sự kiện [{"file","t","db","dai"}]; tron_lenh(...) → phần filter FFmpeg trộn SFX dưới giọng.
Âm lượng: mỗi file được đưa đỉnh về 0 dBFS (đo 1 lần, lưu _do-dinh.json) rồi hạ theo mức → nghe đều tay giữa các file."""
import json, subprocess, re
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
CFG = cfg_hub()
ROOT = Path(CFG["duong_dan"].get("sfx") or (HUB / "tai-nguyen" / "sfx"))
FPS = 30

# Kho đã lọc: chỉ giữ âm hợp video bán hàng nông nghiệp (bỏ tiếng cười, la ó, violin buồn, "bruh"...)
KHO_MAC_DINH = {
    "vut_nhe":  ["whoosh/mixkit-1461-short-wind-swoosh.wav", "whoosh/mixkit-1471-cinematic-wind-swoosh.wav", "whoosh/mixkit-174-fast-sweep-transition.wav"],
    "vut_manh": ["whoosh/mixkit-1469-flying-fast-swoosh.wav", "whoosh/mixkit-1465-vacuum-swoosh-transition.wav", "whoosh/mixkit-174-fast-sweep-transition.wav"],
    "roi_phep": ["whoosh/mixkit-1516-magic-whip-swell.wav"],
    "dap":      ["impact/mixkit-2299-short-bass-hit.wav", "impact/mixkit-2303-futuristic-bass-hit.wav", "opener/bass-impact.mp3"],
    "no_lon":   ["opener/cinematic-boom-hq.mp3", "opener/vine-boom.mp3", "impact/mixkit-2782-epic-impact-afar-explosion.wav",
                 "opener/capcut-explosion.mp3", "impact/mixkit-1687-dramatic-metal-explosion-impact.wav"],
    "keo_len":  ["riser/mixkit-2669-short-sci-fi-swell.wav"],
    "bop":      ["ui/mixkit-1124-plastic-bubble-click.wav", "foley/mixkit-3000-liquid-bubble.wav", "ui/mixkit-1109-select-click.wav"],
    "go_phim":  ["ui/mixkit-1119-hard-typewriter-click.wav", "ui/mixkit-1125-typewriter-soft-click.wav"],
    "chup":     ["ui/mixkit-1133-camera-shutter-click.wav", "ui/mixkit-1440-classic-camera-click.wav"],
    "ting":     ["ding/mixkit-586-attention-bell-ding.wav", "ding/mixkit-3108-crystal-chime.wav", "opener/apple-pay-ding.mp3"],
    "lap_lanh": ["ding/mixkit-3060-sparkle-hybrid-transition.wav", "ding/mixkit-866-fairy-arcade-sparkle.wav"],
    "dung":     ["meme/mixkit-947-correct-answer-notification.wav", "meme/myinstants-correct-answer.mp3"],
    "sai":      ["meme/mixkit-950-game-show-wrong-answer-buzz.wav", "meme/myinstants-wrong-answer-buzzer.mp3"],
    "tien":     ["money/mixkit-1992-coin-win-notification.wav", "money/mixkit-1999-gold-coin-prize.wav", "money/mixkit-1993-clinking-coins.wav"],
    "tui_qua":  ["money/mixkit-1989-money-bag-drop.wav"],
    "vo_tay":   ["meme/mixkit-517-small-group-light-applause.wav"],
    "nen_vuon": ["ambience/mixkit-2464-morning-sound-in-a-garden.wav", "ambience/mixkit-1210-forest-birds-ambience.wav",
                 "ambience/mixkit-1238-windy-humming-forest-with-birds.wav"],
}
KHO = {k: list(v) for k, v in KHO_MAC_DINH.items()}
_KHO_XONG = False


def _dung_kho():
    """Kho thật dùng khi dựng = file kho mặc định còn tồn tại + file trong thư mục SFX người dùng thêm (xem kho_nhac.py)."""
    global KHO, _KHO_XONG
    if _KHO_XONG:
        return
    kho = {k: [r for r in v if (ROOT / r).exists()] for k, v in KHO_MAC_DINH.items()}
    try:
        import kho_nhac
        for f, nhoms in kho_nhac.sfx_phu():
            for g in nhoms:
                kho.setdefault(g, []).append(f)
    except Exception as e:
        print("  SFX thêm lỗi:", str(e)[:120])
    KHO, _KHO_XONG = kho, True


# mức → (đỉnh dBFS khối chữ, đỉnh dBFS tiếng vút chuyển cảnh, tỉ lệ chuyển cảnh có vút).
# Kid 10/11: SFX phải to rõ, có chủ đích kiểu edit viral — không nền chim, không rải "bóp" vô cớ. Mức "em" cũ bị chê → đổi thành "gon".
MUC = {
    "gon":       (-8, -12, 0.6),
    "vua":       (-6, -10, 0.8),
    "soi_dong":  (-4, -8, 1.0),
    "mo_dau_am": (-6, -10, 0.8),
}
ALIAS = {"em": "gon"}
KHOANG = 0.32     # 2 tiếng khác nhóm cách nhau tối thiểu (s) để không lổn nhổn


def _do_dinh():
    """Đo đỉnh (max_volume) từng file 1 lần, lưu cache."""
    _dung_kho()
    f = ROOT / "_do-dinh.json"
    cache = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    changed = False
    for files in KHO.values():
        for rel in files:
            if rel in cache:
                continue
            r = subprocess.run(["ffmpeg", "-v", "info", "-t", "30", "-i", str(ROOT / rel), "-af", "volumedetect", "-f", "null", "-"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            m = re.search(r"max_volume:\s*(-?[\d.]+) dB", r.stderr)
            cache[rel] = float(m.group(1)) if m else 0.0
            changed = True
    if changed:
        try:
            ROOT.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        except OSError:
            pass
    return cache


DINH = None


def _ev(rng, nhom, t, db, dai=1.4, muc="vua", uu=2):
    return {"nhom": nhom, "file": rng.choice(KHO[nhom]) if KHO.get(nhom) else None, "t": round(max(0.0, t), 3), "db": db, "dai": dai, "uu": uu}


def _khoi(b, rng, db, muc):
    """Âm cho từng khối chữ, canh đúng nhịp hoạt hình trong Blocks.tsx."""
    L, t0, d = b["loai"], b["f0"] / FPS, (b["f1"] - b["f0"]) / FPS
    e = lambda nhom, dt=0.0, ddb=0, dai=1.4: _ev(rng, nhom, t0 + dt, db + ddb, dai, muc)
    if L == "hook_dap":
        return [e("dap", 0.02, 2)]
    if L == "hook_tung_tu":
        return [e("vut_manh", 0.0, -3, 1.0), e("bop", 0.25, -2, 0.5)]
    if L == "hook_go_may":
        return [e("vut_nhe", -0.05, -4, 0.8), e("go_phim", 0.12, -3, 0.35), e("go_phim", 0.34, -4, 0.35)]
    if L in ("hook_mat_na", "hook_bang", "lower_third", "dai_chay", "mui_ten_chi"):
        return [e(rng.choice(["vut_nhe", "vut_manh"]), -0.05, -2, 1.2)]
    if L == "hook_tem":
        return [e("chup", 0.1, 0, 0.6), e("dap", 0.12, -4)]
    if L == "hook_hoi":
        return [e("bop", 0.05, 0, 0.6)]
    if L == "checklist":
        gap = max(6, int(d * FPS * 0.7 / max(1, b.get("n", 3)))) / FPS
        return [e("vut_nhe", 0.0, -5, 0.9)] + [e("dung" if k == b.get("n", 3) - 1 else "bop", (4 / FPS) + k * gap, -3, 0.9)
                                             for k in range(min(4, b.get("n", 3)))]
    if L == "so_dem":
        return [e("bop", 0.1, -2, 0.5), e("ting", 26 / FPS, -1, 1.2)]
    if L == "so_sanh":
        return [e("sai", 0.1, -5, 0.8), e("dung", 0.4, -2, 1.1)]
    if L == "vong_tron":
        return [e("roi_phep", 0.0, -3, 1.3)]
    if L in ("nhan_dan", "bong_chu"):
        return [e("bop" if L == "nhan_dan" else "dap", 0.05, 0, 0.8), e("lap_lanh", 0.15, -6, 1.0)]
    if L == "da_quang":
        return [e("vut_nhe", 0.05, -4, 0.9)]
    if L == "canh_bao":
        return [e("ting", 0.05, -2, 1.2)]
    if L == "hop_qua":
        out = [e("tui_qua", 6 / FPS, 0, 1.2), e("lap_lanh", 8 / FPS, -3, 1.3)]
        if muc == "soi_dong":
            out.append(e("vo_tay", 10 / FPS, -8, 2.0))
        return out
    if L == "bang_qua":
        return [e("vut_manh", 0.0, -3, 1.0), e("tien", 0.3, -2, 1.5)]
    if L == "nut_gio_hang":
        return [e("bop", 0.05, 0, 0.5), e("ting", 0.3, -2, 1.3)]
    if L == "the_qua":
        return [e("lap_lanh", 0.05, -1, 1.3)]
    return [e("bop", 0.05, -2, 0.6)]


def len_lich(muc, blocks, cuts, total, rng, pops=None, trans="fade"):
    """Lịch SFX có chủ đích: câu mở → nhấn; chuyển cảnh trượt/zoom → vút đúng lúc chuyển; ô hình bật ra → pop;
    khối chữ → âm theo hoạt hình; chốt → ting/tiền. Ưu tiên: mở/chốt > khối > ô hình > chuyển cảnh, không chồng nhau."""
    global DINH
    if DINH is None:
        DINH = _do_dinh()
    muc = ALIAS.get(muc, muc)
    muc = muc if muc in MUC else "vua"
    db_k, db_c, p_cut = MUC[muc]
    ev = []
    if muc == "mo_dau_am":                       # mở đầu ầm: 1 tiếng nổ trầm ngay khung đầu
        ev.append(_ev(rng, "no_lon", 0.0, -1, 2.0, muc, uu=0))
    for i, b in enumerate(blocks or []):
        uu = 0 if i in (0, len(blocks) - 1) else 1
        for x in _khoi(b, rng, db_k, muc):
            if i == 0 and muc == "mo_dau_am" and x["t"] < 0.6:
                continue                         # đã có tiếng nổ mở đầu
            x["uu"] = uu; ev.append(x)
    if muc in ("soi_dong", "vua") and blocks and blocks[-1]["f0"] / FPS > 5:   # kéo lên dồn vào chốt
        t_cta = blocks[-1]["f0"] / FPS
        ev.append({**_ev(rng, "keo_len", t_cta - 1.5, db_k - 4, 1.5, muc, uu=1), "fade_in": 1.0})
    for t in pops or []:                          # ô hình bật vào
        ev.append(_ev(rng, "bop", t - 0.02, db_k - 2, 0.5, muc, uu=2))
    for c in cuts or []:                          # vút đúng điểm chuyển (bắt đầu trước ~0,2 s để đỉnh rơi vào giữa chuyển cảnh)
        if c < total - 1.0 and (trans != "cat" or rng.random() < 0.5) and rng.random() < p_cut:
            ev.append(_ev(rng, "vut_manh" if muc == "soi_dong" or rng.random() < 0.5 else "vut_nhe", c - 0.2, db_c, 0.8, muc, uu=3))
    ev = [x for x in ev if x["file"]]             # nhóm nào chưa có file nào (kho chưa cài, chưa thêm) thì bỏ tiếng đó
    keep = []                                     # lọc chồng: giữ tiếng ưu tiên cao, bỏ tiếng thấp hơn nằm sát
    for x in sorted(ev, key=lambda x: (x["uu"], x["t"])):
        if x["uu"] >= 2 and any(abs(x["t"] - y["t"]) < KHOANG for y in keep):
            continue
        keep.append(x)
    for x in keep:                                # đưa đỉnh mỗi file về 0 dBFS rồi đặt đúng mức
        x["gain"] = round(x["db"] - DINH.get(x["file"], 0.0), 2)
    return sorted(keep, key=lambda x: x["t"])


def tom_tat(ev):
    return ", ".join(f"{x['nhom']}@{x['t']:.1f}" for x in ev)


def tron_lenh(ev, first_input, voice_label, out_label, total):
    """Trả (đối số -i, các đoạn filter) để trộn SFX vào nhãn âm [voice_label] → [out_label]."""
    args, fc, labels = [], [], []
    for k, x in enumerate(ev):
        idx = first_input + k
        if x.get("start"):
            args += ["-ss", str(x["start"])]
        args += ["-i", str(ROOT / x["file"])]
        ms = int(x["t"] * 1000)
        dai = min(x["dai"], total - x["t"])
        fin = f"afade=t=in:d={x['fade_in']}," if x.get("fade_in") else ""
        fc.append(f"[{idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:{dai:.3f},asetpts=PTS-STARTPTS,{fin}"
                  f"afade=t=out:st={max(0.0, dai - 0.25):.3f}:d=0.25,volume={x['gain']}dB,adelay={ms}|{ms}[s{k}]")
        labels.append(f"[s{k}]")
    if not ev:
        fc.append(f"[{voice_label}]anull[{out_label}]")
        return args, fc
    fc.append(f"[{voice_label}]aformat=sample_rates=44100:channel_layouts=stereo[vv]")
    fc.append(f"[vv]{''.join(labels)}amix=inputs={len(ev) + 1}:duration=first:normalize=0,alimiter=limit=0.84[{out_label}]")
    return args, fc


def tron_am(base, ev, out_audio, total):
    """Trộn SFX vào tiếng của video nền → 1 file âm riêng (tách khỏi bước ghép hình để FFmpeg nhẹ, không sập)."""
    a_args, a_fc = tron_lenh(ev, 1, "0:a", "a", total)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(base), *a_args, "-filter_complex", ";".join(a_fc), "-map", "[a]",
                    "-c:a", "aac", "-b:a", "192k", str(out_audio)], check=True)
    return out_audio
