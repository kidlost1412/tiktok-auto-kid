"""Khâu dựng v2: FFmpeg dựng NỀN (cảnh, chuyển cảnh, chuyển động, màu, âm thanh) + Remotion dựng LỚP CHỮ trong suốt
(karaoke DT Phudu, thẻ mở/chốt, mũi tên, thanh tiến độ) → FFmpeg ghép.
chuan_bi(...) dựng nền + props cho 1 video; dung_lo(jobs) dựng lớp chữ cả lô bằng 1 lần đóng gói rồi ghép."""
import hashlib, json, os, random, re, shutil, subprocess
from pathlib import Path

from dung import render, sentence_times, MENU as MENU_NEN
from phu_de import chia_dong, cau_hinh as cau_hinh_phu_de, loc_phu_de
from cong_thuc import RECIPES, xep_khoi, chon_atmos, khung_tron, chot_qua, HEADER_QUA
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


def goi_gio_khi_mat_mui_ten(props, blocks, qua):
    """Chai chiếm chỗ nên bỏ mũi tên giỏ → thẻ chốt phải tự kêu bấm giỏ (dòng 1 quà, dòng 2 bấm giỏ)."""
    if props["arrow"].get("top") != -999:
        return
    goi = (qua or {}).get("dong2") or "BẤM GIỎ HÀNG"
    if blocks:
        loai, d = blocks[-1]["loai"], blocks[-1].setdefault("data", {})
        if loai == "nut_gio_hang":
            return
        hien = [d.get("tieu_de")] + list(d.get("cac_muc") or []) if loai == "bang_qua" else [d.get("dong1"), d.get("dong2")]   # chỉ chữ thật sự vẽ ra
        if "GIỎ" not in " ".join(map(str, hien)).upper():
            if loai == "bang_qua":
                d["tieu_de"] = goi
            else:
                if qua:
                    d["dong1"] = qua["dong1"]
                d.update(dong2=goi, text=goi)
    elif "GIỎ" not in (props["cta"]["line1"] + props["cta"]["line2"]).upper():
        props["cta"]["line2"] = goi[:24]


def _hook_sau_nguoi(base, work_dir, loi):
    """24/11 hook chữ khổng lồ: camera lùi ra 0,8 s đầu + chữ nằm SAU người (tách người → Remotion vẽ đè lên chữ). Lỗi → giữ như cũ."""
    if not (loi and loi.get("hook")):
        return
    try:
        import hook_sau_nguoi as HSN
        HSN.chay(base, work_dir, loi["hook"])
    except Exception as e:
        print(f"  ⚠ hook sau người lỗi: {e}")


def _chuyen_manh(base, info, loi, plan):
    """23/11 khung chữ theo lời: thay xfade mềm bằng chuyển cảnh MẠNH (whip/flash/glitch/zoom) ở vài nhát cắt đổi ý. Lỗi → giữ nền cắt thẳng."""
    try:
        import chuyen_canh_manh as CCM
        from chon_chuyen_manh import chon, SFX_TEN
        ks = loi["khoi"]
        doi_y = [b["f0"] / FPS for a, b in zip(ks, ks[1:]) if a.get("vai") != b.get("vai")]
        phu = [b["f0"] / FPS for b in ks]
        cuts = info.get("cuts", [])
        ch = chon(cuts, info["thoi_luong"], doi_y, phu, random.Random(f"{plan.get('seed', 0)}-ccm"))
        if not ch:
            return
        tmp = Path(base).with_name("base_manh.mp4")
        mid = Path(base).with_name("base_manh_hinh.mp4")
        CCM.ap(base, mid, ch)                  # ap() chỉ ra hình → ghép lại âm thanh của nền
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(mid), "-i", str(base), "-map", "0:v", "-map", "1:a?", "-c", "copy", str(tmp)], check=True)
        mid.unlink(missing_ok=True)
        os.replace(tmp, base)
        info["chuyen_manh"] = ",".join(f"{t}:{k}" for t, k, _ in ch)
        kc = {min(cuts, key=lambda c: abs(c - t)): k for t, k, _ in ch}
        info["_ccm_tung"] = [SFX_TEN.get(kc.get(c), "cat") for c in cuts]
    except Exception as e:
        print(f"  ⚠ chuyển cảnh mạnh lỗi: {e}")


def chuan_bi(plan, voice, shots, kho, work_dir, music=None):
    rng = random.Random(plan.get("seed", 0))
    st = plan["phong_cach"]
    work_dir = Path(work_dir); work_dir.mkdir(parents=True, exist_ok=True)
    base = work_dir / "base.mp4"
    cat_cung = st.get("khung_dung") == "chu_theo_loi"      # khung chữ theo lời: nền cắt thẳng, chuyển cảnh mạnh gắn sau (_chuyen_manh)
    info = render(dict(plan, khong_chu=True, **({"phong_cach": dict(st, chuyen_canh="cat")} if cat_cung else {})), voice, shots, kho, base, music)   # nền + âm thanh
    total = info["thoi_luong"]; dur_f = int(round(total * FPS))
    sents = sentence_times(voice["text"], voice["words"])
    keys = [k.lower() for k in st.get("nhan_tu", []) if k]
    words = [{"w": w["w"], "f0": int(round(w["s"] * FPS)), "f1": int(round(w["e"] * FPS)), "s": si,
              "emph": any(k in w["w"].lower() for k in keys)} for si, s in enumerate(sents) for w in s["words"]]
    cap = pick("phu_de", st.get("phu_de"), rng)
    big = False
    pd = cau_hinh_phu_de(CFG)                 # phụ đề nhỏ, tuỳ chọn: config["phu_de"] = {bat, co, y, tu_moi_dong}
    lines, by_ai = chia_dong(voice["text"], plan.get("dong"), voice["words"], keys, *pd["tu_moi_dong"])
    recipe = st.get("cong_thuc") if st.get("cong_thuc") in RECIPES else None
    segs = plan.get("edl_segs") or []
    st["_qua_canh"] = [x["qua_tu_khoa"] for sg in segs[-1:] for x in [sg["shot"]] + list(sg.get("phu_shots") or []) if x.get("qua_tu_khoa")]   # quà ở cảnh chốt → thẻ chốt cùng mức quà
    qua = chot_qua(st, voice["text"], rng)           # một mức quà thật cho cả video (None: hồ sơ không có quà → chữ dự phòng cũ)
    blocks, atmos = None, None
    if recipe:   # chặng 2: thư viện khối theo công thức dựng
        blocks, cta_f0 = xep_khoi(recipe, st.get("khoi"), sents, total, st, rng, plan.get("ten_thuong_hieu", ""), voice["words"])
        atmos = chon_atmos(recipe, rng, [int(c * FPS) for c in info.get("cuts", [])])
    else:
        cta_f0 = max(int(round((sents[-1]["s"] - 0.15) * FPS)), dur_f - 5 * FPS)
    khung = st.get("khung_dung") if st.get("khung_dung") in ("the_do_hoa", "chu_theo_loi") else "the_do_hoa"
    if khung == "chu_theo_loi":            # khung "chữ theo lời" (v10): không thẻ, không phụ đề chạy — lớp chữ theo lời thay cả hai
        blocks, lines, pd = None, [], dict(pd, bat=False)
    if not pd["bat"]:
        lines = []
    elif blocks:
        lines = loc_phu_de(lines, blocks)      # ẩn dòng phụ đề đang trùng chữ với khối đang hiện
    cy = CENTER_Y.get(st.get("vi_tri_phu_de"), pd["y"])      # đạo diễn nêu vị trí → theo đạo diễn; không thì theo config
    mau_nhan = st.get("mau_nhan") if st.get("mau_nhan") in ACCENT else "vang"
    props = {
        "blocks": blocks, "atmos": atmos,
        "duration_f": dur_f, "audio": "", "clips": [], "transition": {"kind": "cut", "dur_f": 0}, "words": words,
        "lines": lines,
        "cap": {"style": cap, "center_y": cy, "bat": pd["bat"], "co": pd["co"], "max_px": pd["co"],
                "upper": pick("viet_hoa", st.get("viet_hoa"), rng) == "co"},
        "caption": {"style": cap, "center_y": cy, "upper": pick("viet_hoa", st.get("viet_hoa"), rng) == "co", "group": 2 if big else rng.choice([3, 4])},
        "colors": {"accent": ACCENT[mau_nhan], "brand_red": "#D7262E", "brand_green": "#2E9E44", "text": "#FFFFFF"},
        "open_card": {"kind": pick("the_mo", st.get("the_mo"), rng), "text": (st.get("chu_the_mo") or plan.get("ten_thuong_hieu", ""))[:26],
                      "f1": min(int(round((sents[0]["e"] + 0.3) * FPS)), 100)},
        "cta": {"kind": pick("the_chot", st.get("the_chot"), rng), "line1": ((qua or {}).get("dong1") or st.get("chu_chot_1") or "QUÀ TẶNG THEO ĐƠN")[:26],
                "line2": (st.get("chu_chot_2") or (qua or {}).get("dong2") or "BẤM GIỎ HÀNG")[:24], "f0": cta_f0,
                "header": "🎁 " + (qua["header"] if qua else HEADER_QUA[0])},
        "arrow": {"f0": cta_f0 + 10, "label": st.get("nhan_mui_ten") or rng.choice(["GIỎ HÀNG", "BẤM VÀO ĐÂY", "ĐẶT NGAY"])},
        "progress_bar": st.get("thanh_tien_do") == "co",          # mặc định tắt: chỉ bật khi đạo diễn nêu
    }
    if blocks:
        gan_kieu_chu(blocks, random.Random(f"{plan.get('seed', 0)}-kieu"))     # rng riêng: không xáo các lựa chọn khác
    if blocks is None:
        del props["blocks"]
        if khung != "chu_theo_loi" or not atmos:
            del props["atmos"]
    doan = info.get("doan") or []
    loi = None
    if khung == "chu_theo_loi":
        import chu_theo_loi as CTL, tim_mat, ne_nhan as NN
        loi = CTL.tao_khoi(sents, keys, plan.get("ten_thuong_hieu", ""), total, random.Random(f"{plan.get('seed', 0)}-loi"),
                           do_mat=lambda a, b: tim_mat.tam_mat(base, a, max(0.3, b - a)), nhan_o=lambda a, b: NN.hop_trong(doan, a, b),
                           qua_txt=(qua or {}).get("dong1"), bang=st.get("loi_bang") if st.get("loi_bang") in CTL.BANG_MAU else None)
        props["loi"] = loi
        _chuyen_manh(base, info, loi, plan)
        _hook_sau_nguoi(base, work_dir, loi)       # sau chuyển cảnh mạnh: camera lùi + cắt người phải tính trên nền cuối cùng
    if blocks:                         # né nhãn chai: dời khối chữ / mũi tên giỏ hàng sang khoảng trống
        info["ne_nhan"] = dat_khoi(blocks, doan)
        info["khung_tron"] = khung_tron(doan, blocks)     # đoạn toàn màn trơ chữ (chỉ báo cho giám khảo/máy kiểm, không tự thêm chữ)
    tm = dat_mui_ten(cta_f0, dur_f, doan)
    if tm:
        props["arrow"]["top"] = tm
    if blocks:                         # khối chốt trên bố cục hai/ba cột: đặt lên dải trống phía trên các ô (không đè mặt người / chai trong ô)
        chot = blocks[-1]; t_ch = chot["f0"] / FPS + 0.2
        d_ch = next((d for d in doan if d["t0"] <= t_ch < d["t1"]), doan[-1] if doan else None)
        if d_ch and d_ch.get("bo_cuc") in ("chia_ngang", "ba_doc"):
            chot["top"] = 150
        if chot["loai"] == "nut_gio_hang":
            props["arrow"]["top"] = -999      # đã có nút giỏ hàng → không vẽ thêm mũi tên chồng lên
    goi_gio_khi_mat_mui_ten(props, blocks, qua)
    from viet_loi import bo_chet                       # 23/11 Kid: không bao giờ chữ "chết" trên hình (chữ khối, phụ đề, thẻ)
    props = json.loads(bo_chet(json.dumps(props, ensure_ascii=False)))
    if blocks:
        blocks[:] = props["blocks"]
    try:                               # chữ trên nền sáng/rối → lót nền tối (thử đen trắng, Kid 23/11)
        import do_nen, ne_nhan
        info["nen_toi"] = do_nen.gan_nen(base, props.get("lines"), props.get("cap"), props.get("blocks"), ne_nhan.CAO)
        print(f"  nền tối sau chữ: {info['nen_toi']} chỗ")
    except Exception as e:
        print(f"  ⚠ đo nền sau chữ lỗi: {e}")
    (work_dir / "props.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")   # LUÔN ghi (lỗi rà soát #1)
    if blocks:
        props["open_card"]["kind"] = blocks[0]["loai"]; props["cta"]["kind"] = blocks[-1]["loai"]
        info.update({"cong_thuc": recipe, "khoi": [b["loai"] for b in blocks], "sfx": st.get("sfx"),
                     "atmos": ",".join(k for k in ("vignette", "grain") if atmos[k]) + (",leak" if atmos["leaks"] else ""),
                     "blocks": [{"loai": b["loai"], "f0": b["f0"], "f1": b["f1"]} for b in blocks]})
    ev = []
    if blocks or loi:   # chặng 3: SFX khớp khối chữ + điểm cắt
        bl = CTL.lich_am(props["loi"]) if loi else [{"loai": b["loai"], "f0": b["f0"], "f1": b["f1"], "n": len((b.get("data") or {}).get("items") or []) or 3,
               "text": (b.get("data") or {}).get("text", ""), "am": b.get("am")} for b in blocks]
        tien_t = gio_xeng(words, bl[-1], random.Random(f"{plan.get('seed', 0)}-xeng"))
        if tien_t is not None:
            bl[-1]["tien_t"] = tien_t
        tr = info.get("chuyen_canh")
        tung = [tr if x else "cat" for x in info.get("tds") or []] if tr != "hon_hop" and info.get("tds") else None   # cắt thẳng thì không vút
        if info.get("_ccm_tung"):
            tung = info["_ccm_tung"]       # chuyển cảnh mạnh: chỉ nhát được chọn mới có tiếng
        ev = SFX.len_lich(st.get("sfx"), bl, info.get("cuts", []), total, rng, info.get("pops"), tr,
                          am_mo=st.get("am_mo"), lat_trang=[d["lat"] for d in (info.get("doan") or []) if d.get("lat")], chuyen_tung_cat=tung,
                          nhan=tu_nhan(words, keys), cau=[s["s"] for s in sents[1:]], dong=[l["f0"] / FPS for l in lines[1:]] if lines else None,
                          giong_t0=words[0]["s"] if words else None, loi_dau=sents[0]["text"] if sents else None)   # tiếng mở theo câu mở, không đè giọng
        info["sfx_lich"] = SFX.tom_tat(ev)
        print(f"    SFX {len(ev)} tiếng: {info['sfx_lich']}")
    info["punch"] = chon_punch(ev, total, sau=loi["hook"]["f1"] / FPS if loi and loi.get("hook") else 0)   # không giật zoom trong hook (lệch lớp người)
    info["khung_dung"] = khung
    if loi:
        info.update({"loi_bang_mau": loi["bang"], "loi_font": loi["font"], "loi_khoi": len(loi["khoi"]),
                     "loi_kieu": ",".join(x["mode"] for x in loi["khoi"]), "loi_qua": bool(loi.get("qua"))})
    info.update({"phu_de": cap, "the_mo": props["open_card"]["kind"], "the_chot": props["cta"]["kind"],
                 "mau_nhan": st.get("mau_nhan"), "font": "DT Phudu", "kieu_karaoke": f"remotion-{cap}",
                 "dong_phu_de": "AI chia" if by_ai else "tự chia", "so_dong": len(lines)})
    return {"props": str(work_dir / "props.json"), "frames": str(work_dir / "chu"), "base": str(base), "sfx": ev, "total": total,
            "punch": info["punch"]}, info


TU_CHOT = re.compile(r"^(giỏ|chốt|đặt|mua|đơn)$", re.I)


def gio_xeng(words, chot, rng, p=0.65):
    """23/11 Kid: tiếng xèng/tính tiền khi lời nói đúng từ chốt đơn (giỏ/chốt/đặt/mua/đơn) trong khối chốt — có lúc có, không video nào cũng xèng.
    → giây của từ chốt đầu tiên từ lúc khối chốt hiện, hoặc None. Khối nut_gio_hang đã có tiếng tính tiền riêng."""
    if chot.get("loai") == "nut_gio_hang" or rng.random() > p:
        return None
    w = next((w for w in words if w["f0"] >= chot["f0"] - 3 * FPS and TU_CHOT.match(w["w"].strip(".,!?…:;"))), None)
    return round(w["f0"] / FPS, 3) if w else None


# 23/11 Kid: "các kiểu text không cố định, không phải chỗ nào cũng vàng kim… cần đa dạng edit cao cấp, phù hợp nông dân".
# Mỗi khối chữ lớn tự bốc CÁCH TÔ + FONT riêng; luật: hai khối liền nhau không cùng cách tô, vàng kim ≤ 2 khối/video,
# số rè ≤ 1, cụm nhiều cỡ chỉ cho chữ đập (có chữ nhấn). Font: Phudu là chính, font khác xen vào, không lặp liền.
KIEU_THEO_LOAI = {"chu_so": ("kim", "re", "mau"), "hook_dap": ("kim", "o", "mau"), "chu_dap": ("cum", "kim", "o", "mau"),
                  "chu_tang": ("kim", "mau"), "chu_nghieng": ("o", "mau"), "chu_gach": ("mau",), "chu_mat_na": ("mau",)}
FONT_THEO_LOAI = {"chu_so": ("mi", "un", "ph"), "hook_dap": ("ph", "pt", "un"), "chu_dap": ("ph", "mi", "un", "pt"),
                  "chu_tang": ("ph", "un", "pt"), "chu_nghieng": ("ph", "mi"), "chu_gach": ("ph", "pt"), "chu_mat_na": ("ph", "un")}
TRAN_KIEU = {"kim": 2, "re": 1}


def gan_kieu_chu(blocks, rng):
    dem, truoc_k, truoc_f = {}, None, None
    for b in blocks:
        ds = KIEU_THEO_LOAI.get(b.get("loai"))
        if not ds:
            continue
        con = [k for k in ds if dem.get(k, 0) < TRAN_KIEU.get(k, 99)] or ["o" if "o" in ds else "mau"]    # trần vàng kim/rè ưu tiên hơn luật không lặp
        ok = [k for k in con if k != truoc_k] or con
        b["kieu"] = rng.choice(ok)
        dem[b["kieu"]] = dem.get(b["kieu"], 0) + 1
        fs = FONT_THEO_LOAI[b["loai"]]
        fok = [f for f in fs if f == "ph" or f != truoc_f]
        b["font"] = "ph" if rng.random() < 0.4 and "ph" in fok else rng.choice(fok)
        truoc_k, truoc_f = b["kieu"], b["font"]
    return blocks


def tu_nhan(words, keys):
    """Mốc các cụm từ nhấn (nhan_tu, có thể nhiều chữ như "hai ngày công") trong lời: trả [{"t","w"}] ở chữ đầu mỗi lần khớp."""
    sach = [w["w"].lower().strip(".,!?…:;\"'") for w in words]
    out = []
    for k in keys:
        kk = k.split()
        for i in range(len(sach) - len(kk) + 1):
            if sach[i:i + len(kk)] == kk:
                out.append({"t": words[i]["f0"] / FPS, "w": " ".join(w["w"] for w in words[i:i + len(kk)])})
    return sorted(out, key=lambda x: x["t"])


PUNCH_VAI =("foley", "hit", "money", "bell", "alert", "scratch")


def chon_punch(ev, total, toi_da=5, cach=2.5, sau=0.0):
    """Nhát zoom giật (kiểu kol-vip2 Kid duyệt): đúng lúc tiếng nhấn mạnh (flash, giỏ hàng, kết quả…) của khối chữ, ≤ 5, cách nhau ≥ 2,5 s."""
    ung = sorted((x for x in ev or [] if x.get("vai") in PUNCH_VAI and x.get("uu", 9) <= 1 and max(0.4, sau) < x["t_neo"] < total - 0.8),
                 key=lambda x: (x["uu"], x["t_neo"]))
    out = []
    for x in ung:
        if len(out) < toi_da and all(abs(x["t_neo"] - t) >= cach for t in out):
            out.append(round(x["t_neo"], 2))
    return sorted(out)


def loc_punch(ts, A=0.08):
    """Bộ lọc FFmpeg phóng nhanh +8 % trong 0,08 s rồi nhả dần 0,5 s quanh mỗi mốc (khung 1080×1920 giữ nguyên)."""
    if not ts:
        return "null"
    env = "+".join(f"if(between(it,{t:.2f},{t + 0.08:.2f}),(it-{t:.2f})/0.08,if(between(it,{t + 0.08:.2f},{t + 0.6:.2f}),1-(it-{t + 0.08:.2f})/0.52,0))"
                   for t in ts)
    return f"zoompan=z='1+{A}*({env})':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps={FPS}"


class RemotionQuaGio(RuntimeError):
    """Remotion/node chạy quá hạn → đã diệt cả cây tiến trình."""


def han_remotion(tong_giay_video):
    """Hạn chót cho cả lượt dựng lớp chữ: config remotion_han_co_so (mặc định 300 s) + remotion_han_moi_giay (mặc định 20 s) × tổng giây video."""
    return float(CFG.get("remotion_han_co_so", 300)) + float(CFG.get("remotion_han_moi_giay", 20)) * float(tong_giay_video)


def diet_cay(p):
    """Diệt tiến trình + mọi tiến trình con (node bật Chrome). Windows: taskkill /T /F."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, timeout=30)
        else:
            p.kill()
    except Exception:
        pass
    try:
        p.kill()
    except Exception:
        pass


def _dong_ong(p):
    try:
        p.stdout.close()
    except Exception:
        pass


def chay_node(cmd, cwd, han_s, ok_frames, log=print):
    """Chạy node, đọc từng dòng JSON tiến độ ở luồng riêng; quá han_s giây → diệt cả cây tiến trình và ném RemotionQuaGio (tiếng Việt).
    ok_frames (set) được điền dần: caller biết video nào đã xong trước lúc treo."""
    import threading
    p = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    la = []

    def doc():
        for line in p.stdout:
            line = line.strip()
            if not line.startswith("{"):
                la.append(line); del la[:-6]               # giữ vài dòng lỗi không phải JSON để báo khi node chết
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if "ok" in r:
                ok_frames.add(r["ok"])
            log(f"    lớp chữ: {r.get('s', '')} s {'OK' if 'ok' in r else r}")
    th = threading.Thread(target=doc, daemon=True); th.start()
    th.join(han_s)
    if th.is_alive():
        diet_cay(p)
        th.join(10)
        _dong_ong(p)
        raise RemotionQuaGio(f"Dựng lớp chữ (Remotion) quá {int(han_s)} giây không xong — đã dừng tiến trình, các video chưa xong lớp chữ bị bỏ.")
    p.wait()
    _dong_ong(p)
    if p.returncode not in (0, None) and la:
        log(f"    lớp chữ: node lỗi (mã {p.returncode}): {' | '.join(la)[-300:]}")


def _dua_nguoi_hook(j, public_dir):
    """Chuỗi PNG người của hook: chép vào public_dir/nguoi_<mã> và ghi lại props.loi.hook.nguoi.dir thành tên tương đối cho staticFile. Lỗi → bỏ lớp người (chữ ở trước)."""
    pp = Path(j["props"])
    try:
        pr = json.loads(pp.read_text(encoding="utf-8")); h = (pr.get("loi") or {}).get("hook") or {}
        ng = h.get("nguoi")
        if not ng:
            return
        ten = "nguoi_" + hashlib.md5(str(pp.resolve()).encode()).hexdigest()[:8]
        try:
            shutil.copytree(ng["dir"], public_dir / ten, dirs_exist_ok=True)
            ng["dir"] = ten
        except Exception:
            h.pop("nguoi", None); h.pop("top", None)
            raise
        finally:
            pp.write_text(json.dumps(pr, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"  ⚠ chép lớp người hook lỗi: {e}")


def dung_lo(jobs, public_dir, log=print):
    """jobs: [{"props","frames","base","out"}] → Remotion dựng lớp chữ cả lô, FFmpeg ghép. Trả về danh sách file xong."""
    public_dir = Path(public_dir); public_dir.mkdir(parents=True, exist_ok=True)
    for ten in ("DTPhudu-Black.otf", "Montserrat-BlackItalic.ttf", "Unbounded-VF.ttf", "PaytoneOne-Regular.ttf", "BeVietnamPro-Medium.ttf",
                "BeVietnamPro-Bold.ttf", "Anton-Regular.ttf"):
        if (REMOTION / "public" / ten).exists():                  # bản cài cũ chưa có font mới thì Remotion rơi về font mặc định, không sập
            shutil.copy2(REMOTION / "public" / ten, public_dir / ten)
    for j in jobs:
        _dua_nguoi_hook(j, public_dir)
    jf = public_dir / "_jobs.json"
    jf.write_text(json.dumps([{"props": j["props"], "frames": j["frames"]} for j in jobs], ensure_ascii=False), encoding="utf-8")
    han = han_remotion(sum(float(j.get("total") or 30) for j in jobs))
    ok_frames = set()
    try:
        chay_node(["node", "scripts/render_hub.mjs", str(jf), str(public_dir)], REMOTION, han, ok_frames, log)
    except RemotionQuaGio as e:        # treo → đã diệt node; video nào đã ra đủ lớp chữ vẫn ghép tiếp, video còn lại bị bỏ (lô sau làm bù)
        log(f"    ⚠ {e} Còn {len(ok_frames)}/{len(jobs)} video có lớp chữ.")

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
                        "-filter_complex", f"[0:v]{loc_punch(j.get('punch'))}[nen];[nen][1:v]overlay=0:0:format=auto:shortest=0,format=yuv420p[v]",
                        "-map", "[v]", "-map", "2:a",
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
