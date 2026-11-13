"""Khâu dựng v2: FFmpeg dựng NỀN (cảnh, chuyển cảnh, chuyển động, màu, âm thanh) + Remotion dựng LỚP CHỮ trong suốt
(karaoke DT Phudu, thẻ mở/chốt, mũi tên, thanh tiến độ) → FFmpeg ghép.
chuan_bi(...) dựng nền + props cho 1 video; dung_lo(jobs) dựng lớp chữ cả lô bằng 1 lần đóng gói rồi ghép."""
import json, os, random, shutil, subprocess
from pathlib import Path

from dung import render, sentence_times, MENU as MENU_NEN
from phu_de import chia_dong
from cong_thuc import RECIPES, xep_khoi, chon_atmos
import sfx as SFX
from lam_sach import lam_sach
from anh_bia import chon_bia
from ne_nhan import dat_khoi, dat_mui_ten

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
CFG = cfg_hub()
REMOTION = Path(CFG["duong_dan"]["remotion"])
FPS = 30

MENU_CHU = {
    "phu_de": ["to_dan", "mo_sang", "o_nhay", "gach_chay", "nhich_len", "hop_mo", "quet_mau", "vien_day"],
    "vi_tri_phu_de": ["thap", "vua", "cao"],
    "viet_hoa": ["co", "khong"],
    "mau_nhan": ["vang", "xanh_la", "cam", "do", "xanh_duong"],
    "the_mo": ["ribbon_do", "ribbon_xanh", "tem_xoay", "chu_lon", "thanh_tren", "khong"],
    "the_chot": ["the_qua", "hop_xanh", "hop_do", "nhan_vang"],
    "thanh_tien_do": ["co", "khong"],
}
# menu đầy đủ cho AI chọn
MENU = {**MENU_CHU, "chuyen_canh": MENU_NEN["chuyen_canh"], "chuyen_dong": MENU_NEN["chuyen_dong"],
        "mau": list(MENU_NEN["mau"]), "nhip": MENU_NEN["nhip"]}
ACCENT = {"vang": "#FFD400", "xanh_la": "#3DDC4A", "cam": "#FF8A00", "do": "#FF3B3B", "xanh_duong": "#29D3FF"}
CENTER_Y = {"thap": 1530, "vua": 1490, "cao": 1450}   # phụ đề đặt thấp, ngay trên vùng chữ TikTok ở đáy (~y 1600+)


def pick(key, val, rng):
    return val if val in MENU[key] else rng.choice(MENU[key])


def chuan_bi(plan, voice, shots, kho, work_dir, music=None):
    rng = random.Random(plan.get("seed", 0))
    st = plan["phong_cach"]
    work_dir = Path(work_dir); work_dir.mkdir(parents=True, exist_ok=True)
    base = work_dir / "base.mp4"
    info = render(dict(plan, khong_chu=True), voice, shots, kho, base, music)   # nền + âm thanh
    total = info["thoi_luong"]; dur_f = int(round(total * FPS))
    sents = sentence_times(voice["text"], voice["words"])
    keys = [k.lower() for k in st.get("nhan_tu", []) if k]
    words = [{"w": w["w"], "f0": int(round(w["s"] * FPS)), "f1": int(round(w["e"] * FPS)), "s": si,
              "emph": any(k in w["w"].lower() for k in keys)} for si, s in enumerate(sents) for w in s["words"]]
    cap = pick("phu_de", st.get("phu_de"), rng)
    big = False
    lines, by_ai = chia_dong(voice["text"], plan.get("dong"), voice["words"], keys)
    recipe = st.get("cong_thuc") if st.get("cong_thuc") in RECIPES else None
    blocks, atmos = None, None
    if recipe:   # chặng 2: thư viện khối theo công thức dựng
        blocks, cta_f0 = xep_khoi(recipe, st.get("khoi"), sents, total, st, rng, plan.get("ten_thuong_hieu", ""))
        atmos = chon_atmos(recipe, rng, [int(c * FPS) for c in info.get("cuts", [])])
    else:
        cta_f0 = max(int(round((sents[-1]["s"] - 0.15) * FPS)), dur_f - 5 * FPS)
    props = {
        "blocks": blocks, "atmos": atmos,
        "duration_f": dur_f, "audio": "", "clips": [], "transition": {"kind": "cut", "dur_f": 0}, "words": words,
        "lines": lines,
        "cap": {"style": cap, "center_y": CENTER_Y[pick("vi_tri_phu_de", st.get("vi_tri_phu_de"), rng)],
                "upper": pick("viet_hoa", st.get("viet_hoa"), rng) == "co", "max_px": rng.choice([54, 58, 62])},
        "caption": {"style": cap, "center_y": CENTER_Y[pick("vi_tri_phu_de", st.get("vi_tri_phu_de"), rng)],
                    "upper": pick("viet_hoa", st.get("viet_hoa"), rng) == "co", "group": 2 if big else rng.choice([3, 4])},
        "colors": {"accent": ACCENT[pick("mau_nhan", st.get("mau_nhan"), rng)], "brand_red": "#D7262E", "brand_green": "#2E9E44", "text": "#FFFFFF"},
        "open_card": {"kind": pick("the_mo", st.get("the_mo"), rng), "text": (st.get("chu_the_mo") or plan.get("ten_thuong_hieu", ""))[:26],
                      "f1": min(int(round((sents[0]["e"] + 0.3) * FPS)), 100)},
        "cta": {"kind": pick("the_chot", st.get("the_chot"), rng), "line1": (st.get("chu_chot_1") or "QUÀ TẶNG THEO ĐƠN")[:26],
                "line2": (st.get("chu_chot_2") or "BẤM GIỎ HÀNG")[:24], "f0": cta_f0},
        "arrow": {"f0": cta_f0 + 10, "label": rng.choice(["GIỎ HÀNG", "BẤM VÀO ĐÂY", "ĐẶT NGAY"])},
        "progress_bar": pick("thanh_tien_do", st.get("thanh_tien_do"), rng) == "co",
    }
    if blocks is None:
        del props["blocks"], props["atmos"]
    doan = info.get("doan") or []
    if blocks:                         # né nhãn chai: dời khối chữ / mũi tên giỏ hàng sang khoảng trống
        info["ne_nhan"] = dat_khoi(blocks, doan)
    tm = dat_mui_ten(cta_f0, dur_f, doan)
    if tm:
        props["arrow"]["top"] = tm
    (work_dir / "props.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")   # LUÔN ghi (lỗi rà soát #1)
    if blocks:
        props["open_card"]["kind"] = blocks[0]["loai"]; props["cta"]["kind"] = blocks[-1]["loai"]
        info.update({"cong_thuc": recipe, "khoi": [b["loai"] for b in blocks], "sfx": st.get("sfx"),
                     "atmos": ",".join(k for k in ("vignette", "grain") if atmos[k]) + (",leak" if atmos["leaks"] else ""),
                     "blocks": [{"loai": b["loai"], "f0": b["f0"], "f1": b["f1"]} for b in blocks]})
    ev = []
    if blocks:   # chặng 3: SFX khớp khối chữ + điểm cắt
        bl = [{"loai": b["loai"], "f0": b["f0"], "f1": b["f1"], "n": len((b.get("data") or {}).get("items") or []) or 3,
               "text": (b.get("data") or {}).get("text", "")} for b in blocks]
        ev = SFX.len_lich(st.get("sfx"), bl, info.get("cuts", []), total, rng, info.get("pops"), info.get("chuyen_canh"))
        info["sfx_lich"] = SFX.tom_tat(ev)
    info.update({"phu_de": cap, "the_mo": props["open_card"]["kind"], "the_chot": props["cta"]["kind"],
                 "mau_nhan": st.get("mau_nhan"), "font": "DT Phudu", "kieu_karaoke": f"remotion-{cap}",
                 "dong_phu_de": "AI chia" if by_ai else "tự chia", "so_dong": len(lines)})
    return {"props": str(work_dir / "props.json"), "frames": str(work_dir / "chu"), "base": str(base), "sfx": ev, "total": total}, info


def dung_lo(jobs, public_dir, log=print):
    """jobs: [{"props","frames","base","out"}] → Remotion dựng lớp chữ cả lô, FFmpeg ghép. Trả về danh sách file xong."""
    public_dir = Path(public_dir); public_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REMOTION / "public" / "DTPhudu-Black.otf", public_dir / "DTPhudu-Black.otf")
    jf = public_dir / "_jobs.json"
    jf.write_text(json.dumps([{"props": j["props"], "frames": j["frames"]} for j in jobs], ensure_ascii=False), encoding="utf-8")
    p = subprocess.Popen(["node", "scripts/render_hub.mjs", str(jf), str(public_dir)], cwd=str(REMOTION),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    ok_frames = set(); la = []
    for line in p.stdout:
        line = line.strip()
        if not line.startswith("{"):
            la.append(line); la = la[-6:]                  # giữ vài dòng lỗi không phải JSON để báo khi node chết
            continue
        if line.startswith("{"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if "ok" in r:
                ok_frames.add(r["ok"])
            log(f"    lớp chữ: {r.get('s', '')} s {'OK' if 'ok' in r else r}")
    p.wait()
    if p.returncode not in (0, None) and la:
        log(f"    lớp chữ: node lỗi (mã {p.returncode}): {' | '.join(la)[-300:]}")

    def ghep_an_toan(j):        # 1 video ghép lỗi không làm hỏng cả đợt (lỗi rà soát #3)
        try:
            return ghep(j)
        except Exception as e:
            log(f"    ghép lỗi {Path(j['out']).name}: {str(e)[-200:]}")
            return None

    def ghep(j):
        first = sorted(Path(j["frames"]).glob("f*.png"))[0].stem      # vd f000 → đệm 3 chữ số
        pat = f"f%0{len(first) - 1}d.png"
        am = Path(j["frames"]).parent / "am.m4a"
        SFX.tron_am(j["base"], j.get("sfx") or [], am, j.get("total", 30))
        out = Path(j["out"]); part = out.with_name(out.stem + ".part.mp4")      # ghi ra file tạm .part.mp4 rồi mới đổi tên: crash không để lại .mp4 cụt trông như đã xong
        try:
          subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", j["base"], "-framerate", str(FPS), "-i", str(Path(j["frames"]) / pat), "-i", str(am),
                        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto:shortest=0,format=yuv420p[v]", "-map", "[v]", "-map", "2:a",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", "9M", "-bufsize", "18M", "-threads", "4",
                        "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(part)], check=True)
          lam_sach(part)
          os.replace(part, out)
        except BaseException:
            for x in (part, part.with_name(part.stem + ".__sach.mp4")):
                try: x.unlink()
                except OSError: pass
            raise
        # (lam_sach đã chạy trên file .part: bỏ metadata lộ nguồn/công cụ — mã TikTok gốc, encoder, SEI x264)
        try:                                                          # ảnh bìa: khung đẹp nhất, ưu tiên lúc chữ câu mở đang hiện
            pr = json.loads(Path(j["props"]).read_text(encoding="utf-8"))
            b0 = (pr.get("blocks") or [None])[0]
            chon_bia(j["out"], uu_tien=(b0["f0"] / FPS, b0["f1"] / FPS) if b0 else None)
        except Exception:
            pass
        shutil.rmtree(Path(j["frames"]).parent, ignore_errors=True)   # dọn file tạm
        return j["out"]

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:   # 2: máy 16 GB, 3 từng hết RAM khi mở nhiều app
        return [o for o in ex.map(ghep_an_toan, [j for j in jobs if j["frames"] in ok_frames]) if o]
