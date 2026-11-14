"""Ê-KÍP AI (Kid duyệt 10/11/2026): Biên kịch → Giọng → Đạo diễn (nhìn cảnh, lên bảng dựng) → Máy dựng → Giám khảo (xem, chấm, bắt sửa 1 lần).
Gọi từ sanxuat.py. Mỗi lời đọc → nhiều video, mỗi video một đạo diễn gu khác.
Hết hạn mức Claude → dừng gọn, giữ những video đã xong."""
import csv, datetime, json, math, os, random, re, shutil, subprocess, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ai import HetHanMuc, VIEC
from viet_loi import viet
from giong import tao_giong
from dao_dien import GU, dao_dien, segs_tu_bang, giam_khao, canh_qua, canh_them, ung_vien, ghi_lich_su_canh, id_canh_chinh, id_canh_phu
from dung import kiem_chop
from kho_chung import kho_them_cua, la_kho_chung
from dung_remotion import chuan_bi, dung_lo
from cong_thuc import chuan_hoa
from don_dep import khoa_con_song, lay_khoa_lo, nha_khoa_lo
from kiem_khung import scan
import su_kien as SK

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, khung_giay, kem, kem_ngay, pid_la_lo_sx, ghi_nguyen_tu
CFG = cfg_hub()
COT = ["file", "goc", "giong", "gu_dao_dien", "cong_thuc", "diem_giam_khao", "lan_dung", "loi_giam_khao", "y_tuong", "bo_cuc", "khoi",
       "sfx", "nhac", "thoi_luong", "caption", "hashtag", "loi", "canh", "may_sua", "danh_gia_kid", "gop_y_kid", "luot_xem", "don"]


_khoa_sig = threading.Lock()
F_KHOA = HUB / "lich-su" / "dang-chay.lock"


def dang_co_lo():
    """Có lô đang chạy (từ app hay cửa sổ lệnh)? — file khoá phải trỏ tới tiến trình python CÒN SỐNG và đúng giờ tạo tiến trình ghi lúc khoá
    (PID bị cấp lại cho một python khác, kể cả chính app, = khoá cũ)."""
    return khoa_con_song(F_KHOA) is not None


def segs_theo_luat(sents, total, shots, per, rng, y_canh=None):
    """MÁY TỰ DỰNG theo luật khi đạo diễn AI lỗi (không cần bảng dựng của AI) → danh sách đoạn cùng dạng với dao_dien.segs_tu_bang:
    {"shot","src_start","dur","bo_cuc","phu_shots","cau"}. Mỗi câu 1 cảnh đúng nhất chưa dùng (câu dài > 4 s: 2 cảnh), câu chốt ưu tiên cảnh chai rõ,
    ưu tiên cảnh đủ dài cho đoạn, bố cục luân phiên không lặp liền kề (cảnh có người nói → khung nhỏ). per: id cảnh ứng viên theo từng câu (dao_dien.ung_vien), có thể None."""
    from bo_cuc import SO_PHU, la_chai
    from soat_kho import bad, nguoi_noi
    from dao_dien import _diem_lien_quan, _bu_bo_cuc
    if not sents:
        raise ValueError("không có câu nào để dựng")
    pool = [s for s in shots if not str(s["id"]).startswith(("Q-", "V-")) and not bad(s)] or [s for s in shots if not bad(s)] or list(shots)
    if not pool:
        raise ValueError("kho không có cảnh nào")
    by = {s["id"]: s for s in pool}
    yc = y_canh or []
    bounds = []
    for k, s in enumerate(sents):                       # ranh giới câu: giống segs_tu_bang (phủ kín 0 → total)
        a = 0.0 if k == 0 else (sents[k - 1]["e"] + s["s"]) / 2
        b = total if k == len(sents) - 1 else (s["e"] + sents[k + 1]["s"]) / 2
        bounds.append((a, b))
    used, segs, rot = set(), [], ("khung_mo", "day_zoom", "khung_nho", "day_zoom")
    for k, (a, b) in enumerate(bounds):
        span = b - a
        n = max(1, min(2 if sents[k]["e"] - sents[k]["s"] > 4 else 1, int(span // 1.8)))      # mỗi cảnh ≥ 1,8 s
        dur = span / n
        goi = [by[i] for i in (per[k] if per and k < len(per) else []) if i in by]
        rest = sorted((s for s in pool if s not in goi), key=lambda s: -_diem_lien_quan(s, sents[k]["text"], yc[k] if k < len(yc) else "") - rng.random() * 0.5)
        cands = sorted(goi + rest, key=lambda s: (float(s.get("den", s["tu"] + s["dai"])) - float(s["tu"]) < dur - 1e-6, nguoi_noi(s)))   # đủ dài trước, người nói sau; giữ thứ tự liên quan
        for j in range(n):
            ds = [s for s in cands if s["id"] not in used] or [s for s in cands if not (segs and s["id"] == segs[-1]["shot"]["id"])] or cands     # kho nhỏ: dùng lại
            if k == len(sents) - 1 and j == n - 1:      # câu chốt PHẢI thấy chai
                chai = [s for s in ds if la_chai(s) and not nguoi_noi(s)] or [s for s in cands if la_chai(s) and not nguoi_noi(s)]
                ds = chai or ds
            sh = ds[0]; used.add(sh["id"])
            den = float(sh.get("den", sh["tu"] + sh["dai"])); dep = sh.get("dep") or [sh["tu"], den]
            mid = (dep[0] + dep[1]) / 2
            start = min(max(sh["tu"], mid - dur / 2), max(sh["tu"], den - dur))
            L = rot[len(segs) % len(rot)]
            if segs and L == segs[-1]["bo_cuc"]:
                L = "khung_mo" if L != "khung_mo" else "day_zoom"
            if nguoi_noi(sh):
                L = "khung_nho"
            segs.append({"shot": sh, "src_start": round(start, 2), "dur": round(dur, 3), "bo_cuc": L, "phu_shots": [], "cau": k})
    try:                                                # thêm chia khung / ô trời cho đỡ đơn điệu; lỗi thì giữ bản đơn giản
        import copy
        bak = copy.deepcopy(segs)
        try:
            segs, _ = _bu_bo_cuc(segs, shots, used)
        except Exception:
            segs = bak
    except Exception:
        pass
    for sg in segs:                                     # tự kiểm: máy dựng (dung.render) đọc đúng các khoá này
        if sg["bo_cuc"] not in SO_PHU or len(sg["phu_shots"]) != SO_PHU[sg["bo_cuc"]] or sg["dur"] <= 0:
            sg["bo_cuc"], sg["phu_shots"] = "khung_mo", []
    return segs


def segs_may_dung(voice, sc, sp, shots, tranh, rng):
    """Từ lời + giọng đã có → đoạn dựng theo luật, không gọi AI (dùng khi đạo diễn lỗi)."""
    from dung import sentence_times
    sents = sentence_times(voice["text"], voice["words"])
    total = round(max(voice["dur"] + 0.6, khung_giay(sp)[0] + 0.3), 2)           # khớp dao_dien.ctx_dao_dien / dung.render
    yc = sc.get("y_canh", [])
    try:
        per = ung_vien(sents, yc, shots, rng, tranh=tranh)[0]
    except Exception:
        per = None
    return segs_theo_luat(sents, total, shots, per, rng, yc)


def chay(ma_sp, so_video, log, music_pick, lam_lai=None):
    token = lay_khoa_lo(ma_sp, F_KHOA)     # tạo khoá độc quyền (O_EXCL): 2 lô cùng giây chỉ 1 lô qua
    if token is None:
        log("⛔ Đang có một lô khác chạy — không chạy chồng (đợi lô kia xong)."); return
    try:
        _chay(ma_sp, so_video, log, music_pick, lam_lai)
    finally:
        nha_khoa_lo(token, F_KHOA)


def _chay(ma_sp, so_video, log, music_pick, lam_lai=None):
    t_bat_dau = time.time()
    day = datetime.date.today().isoformat()
    out_dir = Path(CFG["duong_dan"]["ra"]) / day
    tam = out_dir / "_tam" / datetime.datetime.now().strftime("lo-%H%M%S")      # thư mục tạm riêng cho từng lô
    (out_dir / "_giong").mkdir(parents=True, exist_ok=True)
    sp = json.loads((HUB / "san-pham" / ma_sp / "san-pham.json").read_text(encoding="utf-8"))
    shots = json.loads((HUB / "san-pham" / ma_sp / "canh.json").read_text(encoding="utf-8"))
    for x in shots:                       # kho kiểu cũ (vd. Nano Đồng) thiếu "dep" → dùng cả đoạn
        x.setdefault("dep", [x["tu"], x.get("den", x["tu"] + x["dai"])])
        x.setdefault("den", x["tu"] + x["dai"]); x.setdefault("mo_ta", ""); x.setdefault("the", [])
    if not any(s.get("soat") for s in shots):
        log("  ⚠ kho chưa được AI soát bằng mắt — chạy: engine\\soat_kho.py " + ma_sp)
    # Kho phụ: lựa chọn "Dùng thêm cảnh từ kho khác" đã nhớ trong hồ sơ (sp["kho_them"]); chưa chọn → kho chung đánh dấu tron_mac_dinh (video-vuon).
    # Chỉ làm cảnh phụ, tối đa ~30% số cảnh mỗi video (dao_dien.gioi_han_kho_them). Kho chung không mượn kho khác.
    ds_them = [] if la_kho_chung(sp) else kho_them_cua(ma_sp, sp)
    chung = canh_them(ds_them)
    log("  kho phụ: " + (", ".join("%s (%d cảnh dùng được)" % (m, sum(1 for x in chung if x["kho_them"] == m)) for m in ds_them) if ds_them else "không dùng"))
    qua = canh_qua(ma_sp, CFG.get("kho_qua"))             # cảnh quà tặng thật từ kho sản phẩm khác
    if qua:
        log(f"  cảnh quà tặng thật: " + ", ".join(f"{k} ({len(v)})" for k, v in qua.items()))
    per = CFG["lo"]["video_moi_giong"]
    gu_keys = list(GU)
    ten_sp = sp.get("ten_ngan") or sp.get("ten_goi") or ma_sp
    SK.ghi("he-thong", "bat-dau-lo", f"Bắt đầu lô {ten_sp}", ma=ma_sp, ten=ten_sp, so_video=(len(lam_lai) if lam_lai else so_video), lam_lai=bool(lam_lai) or None)
    if lam_lai:                           # LÀM LẠI video anh không ưng: giữ lời + giọng cũ, đạo diễn dựng lại theo góp ý của anh
        log(f"BẮT ĐẦU LÀM LẠI (ê-kíp AI · {CFG['claude']['model']} {CFG['claude']['effort']}) {ma_sp}: {len(lam_lai)} video theo góp ý của anh")
        scripts = []
    else:
        log(f"BẮT ĐẦU (ê-kíp AI · {CFG['claude']['model']} {CFG['claude']['effort']}) {ma_sp}: {so_video} video ← "
            f"{math.ceil(so_video / per)} lời × {per} đạo diễn")
        SK.ghi("bien-kich", "bat-dau", "Đang viết lời đọc", so=math.ceil(so_video / per))
        try:
            scripts = viet(ma_sp, math.ceil(so_video / per), log)
        except HetHanMuc as e:
            SK.ghi("he-thong", "het-han-muc", "Hết hạn mức Claude khi viết lời")
            log(f"⛔ HẾT HẠN MỨC CLAUDE khi viết lời: {e}. Đổi tài khoản rồi chạy lại."); return
        log(f"Biên kịch xong: {len(scripts)} lời đạt kiểm")
        SK.ghi("bien-kich", "xong", f"Viết xong {len(scripts)} lời", so=len(scripts))
    sheet = kem_ngay(out_dir, "bang-ghi-ekip.csv", ghi=True)
    ghi_hang = lambda row: SK.noi_them(sheet, SK.dong_csv(row), ma_hoa="utf-8-sig", dau=SK.dong_csv(COT))     # Excel đang mở bảng → ghi tạm .cho-ghi, không làm sập lô
    sig_file = HUB / "lich-su" / f"chu-ky-{day}.txt"
    used_sigs = set(sig_file.read_text(encoding="utf-8").split()) if sig_file.exists() else set()
    da_dung_f = HUB / "lich-su" / f"canh-da-dung-{ma_sp}.txt"
    lo_dung = []                      # cảnh (chính + ô phụ) đã dùng trong lô này; lịch sử các ngày trước do dao_dien tự tính độ "mệt"

    # ---- giọng + danh sách việc. GIỌNG MUA "VỪA ĐỦ DÙNG": mỗi đợt (≈6 video = 6/per lời) mới thu giọng ngay trước khi đạo diễn dựng đợt đó,
    # và ngừng mua hẳn khi đã báo hết hạn mức Claude (trước đây mua giọng cả lô trước khi có đạo diễn nào chạy xong)
    tasks, n_gu = [], 0
    stamp0 = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    het_han = {"v": False}
    n_sc_dot = max(1, 6 // max(1, per))              # số lời mỗi đợt

    def co_tai_khoan():
        try:
            from ai import chon_tai_khoan
            return chon_tai_khoan() is not None       # chỉ đọc trạng thái tài khoản, không gọi AI
        except Exception:
            return True

    def lam_giong(i_sc):                 # giọng chạy song song 3 lời một lúc (trong 1 đợt)
        i, sc = i_sc
        vname = f"{ma_sp}-{sc['goc']}-{sc['giong']}-{stamp0}-{i:02d}"
        if het_han["v"]:
            return vname, None                       # đã hết hạn mức → không mua thêm giọng
        try:
            return vname, tao_giong(sc["text"], CFG["giong"]["danh_sach"][sc["giong"]], out_dir / "_giong", vname, doc=sp.get("doc_la"))
        except Exception as e:
            log(f"  giọng lỗi ({sc['goc']}): {type(e).__name__} {str(e)[:120]}")
            return vname, None

    def viec_tu_loi(i0, ds_sc):
        """Thu giọng cho các lời của 1 đợt rồi tạo việc dựng (mỗi lời × per đạo diễn)."""
        nonlocal n_gu
        SK.ghi("giong", "bat-dau", "Đang thu giọng", so=len(ds_sc))
        with ThreadPoolExecutor(3) as ex:
            gd = list(ex.map(lam_giong, [(i0 + j, sc) for j, sc in enumerate(ds_sc)]))
        moi = []
        for sc, (vname, voice) in zip(ds_sc, gd):
            if len(tasks) >= so_video:
                break
            if voice is None:
                continue
            if voice["dur"] > khung_giay(sp, CFG)[1] - 0.7:
                log(f"  bỏ {sc['goc']}: giọng {voice['dur']} s quá dài"); continue
            for j in range(per):
                if len(tasks) >= so_video:
                    break
                gu = gu_keys[(n_gu + random.randint(0, 99)) % len(gu_keys)] if j == 0 else gu_keys[(gu_keys.index(tasks[-1]["gu"]) + 1) % len(gu_keys)]
                n_gu += 1
                t = {"sc": sc, "voice": voice, "gu": gu, "rng": random.Random(f"{vname}-{j}"), "j": j,
                     "work": tam / f"{vname}-{j}", "vname": vname}
                tasks.append(t); moi.append(t)
            cau_moi = [x.strip() for x in re.split(r"(?<=[.!?])\s+", re.sub(r"\[[^\]]*\]", "", sc["text"]).strip()) if x.strip()]
            for ten_f in ("cau-da-dung.txt", f"cau-da-dung-{ma_sp}.txt"):     # chung (máy chống trùng) + riêng sản phẩm (gửi biên kịch)
                SK.noi_them(HUB / "lich-su" / ten_f, "".join(x + "\n" for x in cau_moi), giu_dong=4000, toi_da_byte=400_000)
        log(f"Giọng xong: {len(moi)} video cần dựng trong đợt này")
        SK.ghi("giong", "xong", f"Thu xong {sum(1 for _, v in gd if v)} giọng", so=sum(1 for _, v in gd if v))
        return moi
    for i, ll in enumerate(lam_lai or []):
        meta = ll.get("meta") or {}
        sc = meta.get("kich_ban") or {"goc": meta.get("goc") or "lam-lai", "giong": meta.get("giong") or "XuanLuong",
                                      "text": meta.get("loi_doc") or "", "captions": [meta.get("caption") or ""], "hashtag": meta.get("hashtag") or []}
        sc = {k2: v for k2, v in sc.items() if v is not None}; sc.setdefault("goc", "lam-lai"); sc.setdefault("giong", "XuanLuong")
        voice = None; gf = meta.get("giong_file")
        if gf and Path(gf).exists():
            voice = json.loads(Path(gf).read_text(encoding="utf-8"))
            if not Path(voice.get("audio", "")).exists():
                voice = None
        if voice is None and sc.get("text"):          # video cũ chưa ghi giong_file → tìm giọng cùng lời trong _giong của ngày đó
            sach = lambda x: re.sub(r"\W+", "", re.sub(r"\[[^\]]*\]", "", x or "")).lower()
            for gj in (Path(ll["file"]).parent / "_giong").glob("*.json"):
                try:
                    gv = json.loads(gj.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if sach(gv.get("text")) == sach(sc["text"]) and Path(gv.get("audio", "")).exists():
                    voice = gv; sc["text"] = gv["text"]; break
        vname = f"{ma_sp}-lamlai-{stamp0}-{i:02d}"
        if voice is None and sc.get("text"):        # giọng cũ đã dọn → đọc lại đúng lời cũ
            try:
                voice = tao_giong(sc["text"], CFG["giong"]["danh_sach"].get(sc["giong"], list(CFG["giong"]["danh_sach"].values())[0]),
                                  out_dir / "_giong", vname, doc=sp.get("doc_la"))
            except Exception as e:
                log(f"  giọng lỗi khi làm lại {ll['file']}: {str(e)[:120]}"); continue
        if voice is None:
            log(f"  bỏ làm lại {Path(ll['file']).name}: không còn lời đọc"); continue
        tasks.append({"sc": sc, "voice": voice, "gu": meta.get("dao_dien") if meta.get("dao_dien") in GU else random.choice(gu_keys),
                      "rng": random.Random(f"{ll['file']}-{time.time()}"), "j": 0, "work": tam / f"lamlai-{i}", "vname": vname,
                      "gop_y": "CHỦ HÀNG KHÔNG ƯNG BẢN TRƯỚC, GÓP Ý (bắt buộc làm theo): " + (ll.get("gop_y") or "dựng lại đẹp hơn, đa dạng hơn"),
                      "lam_lai_tu": str(ll["file"])})
    if lam_lai:
        log(f"Giọng xong (làm lại): {len(tasks)} video cần dựng")
    SK.ghi("he-thong", "ke-hoach", f"{len(lam_lai) if lam_lai else so_video} video cần dựng", so_video=len(lam_lai) if lam_lai else so_video)

    def len_bang(t, gop_y=""):
        """Đạo diễn → bảng dựng → kế hoạch cho máy dựng."""
        t["work"].mkdir(parents=True, exist_ok=True); t["hong"] = False; may_dung = False
        SK.ghi("dao-dien", "bat-dau", f"Đạo diễn {t['gu']} lên bảng dựng", video=f'{t["vname"]}-{t["j"]}', gu=t["gu"])
        try:
            VIEC.video = f'{t["vname"]}-{t["j"]}'            # token.csv biết lượt gọi này thuộc video nào
            edl, sents, total = dao_dien(ma_sp, sp, t["voice"], t["sc"], shots, t["gu"], t["work"], t["rng"], gop_y or t.get("gop_y", ""),
                                         tranh=lo_dung, qua=qua, chung=chung, anh_em=t.get("anh_em_ds"), used_sigs=used_sigs)
            segs, sua = segs_tu_bang(edl, sents, total, shots + [x for ds in qua.values() for x in ds] + chung)
            lo_dung.extend(id_canh_chinh(segs) + id_canh_phu(segs))    # video sau trong cùng lô cũng tránh các cảnh này
            (t["work"] / "bang-dung.json").write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
        except HetHanMuc:
            het_han["v"] = True; SK.ghi("he-thong", "het-han-muc", "Hết hạn mức Claude khi lên bảng dựng"); raise
        except Exception as e:
            log(f"  đạo diễn lỗi ({t['gu']}): {str(e)[:160]} → máy tự dựng theo luật")
            SK.ghi("dao-dien", "loi", f"Đạo diễn lỗi, máy tự dựng: {str(e)[:80]}", video=f'{t["vname"]}-{t["j"]}')
            edl, may_dung = {"gu": t["gu"], "ly_do": "máy tự dựng (đạo diễn lỗi)"}, True
            try:                              # phương án dự phòng THẬT: tự chọn cảnh theo luật từ chính các cảnh ứng viên (không cần AI), video vẫn ra
                segs = segs_may_dung(t["voice"], t["sc"], sp, shots, set(lo_dung) | set(t.get("anh_em_ds") or []), t["rng"])
                sua = ["đạo diễn lỗi"]
                lo_dung.extend(id_canh_chinh(segs) + id_canh_phu(segs))
            except Exception as e2:           # kho/giọng hỏng đến mức máy cũng không dựng nổi → chỉ video này bị bỏ, đợt vẫn chạy tiếp
                log(f"  máy tự dựng cũng lỗi ({t['gu']}): {type(e2).__name__} {str(e2)[:120]} → bỏ video này")
                SK.ghi("dao-dien", "loi", f"Máy tự dựng lỗi: {str(e2)[:80]}", video=f'{t["vname"]}-{t["j"]}')
                t["hong"] = True
                return t
        st = {kk: edl.get(kk) for kk in ("cong_thuc", "phu_de", "mau_nhan", "chuyen_canh", "chuyen_dong", "mau", "sfx", "nhac") if edl.get(kk)}
        st["khoi"] = [x for x in edl.get("khoi", []) if isinstance(x, dict)]
        st["nhan_tu"] = edl.get("nhan_tu") or t["sc"].get("nhan_tu", [])
        with _khoa_sig:                       # 3 luồng đạo diễn cùng sửa used_sigs (lỗi rà soát #11)
            if t["sc"].get("chu_mo"):
                st["chu_the_mo"] = t["sc"]["chu_mo"]      # chữ mở do biên kịch viết: dùng khi đạo diễn không tự đặt chữ móc câu
            st = chuan_hoa(st, t["rng"], used_sigs, tu_do=bool(segs) and not may_dung, dang=t["sc"].get("dang"), goc=t["sc"].get("goc"))      # máy tự dựng: cho xoay vòng công thức như thường
        st["_qua"] = sp.get("qua_tang", [])
        t.update(edl=edl, st=st, sua=sua)
        t["plan"] = {"seed": t["rng"].randint(1, 10**9), "phong_cach": st, "canh": t["sc"].get("canh", []), "dong": t["sc"].get("dong"),
                     "ten_thuong_hieu": (sp.get("ten_ngan") or sp["ten_goi"]).upper(), "edl_segs": segs,
                     "vmin": khung_giay(sp, CFG)[0]}
        SK.ghi("dao-dien", "xong", "Đã có bảng dựng", video=f'{t["vname"]}-{t["j"]}', gu=t["gu"])
        return t

    def dung_nen(t):
        SK.ghi("dung", "bat-dau", "Đang dựng nền", video=f'{t["vname"]}-{t["j"]}')
        music = music_pick(t["st"].get("nhac"), t["rng"])
        t["music"] = music
        tag = "MIXKIT" if music else "CHON-NHAC-TIKTOK"
        fname = f"{ma_sp}_{t['sc']['goc']}_{t['gu']}_{tag}_{datetime.datetime.now():%Y%m%d-%H%M%S}-{t['j'] + 1}.mp4"
        for lan in range(2):        # thiếu RAM → thử lại 1 lần (lúc đó luồng kia thường đã xong)
            try:
                job, info = chuan_bi(t["plan"], t["voice"], shots, sp["kho_video"], t["work"] / "dung", music)
                break
            except Exception as e:
                log(f"  dựng nền lỗi lần {lan + 1} {fname}: {str(e)[-120:]}")
                if lan == 1:
                    return t if t.get("job") else None   # dựng lại hỏng → giữ bản cũ
                time.sleep(20)
        t["fname"] = fname; job["out"] = str(out_dir / fname); t["job"] = job; t["info"] = info
        SK.ghi("dung", "xong", "Dựng nền xong", video=f'{t["vname"]}-{t["j"]}')
        return t

    def mot_vong(ds, gop=None):
        # đạo diễn thứ 2 của cùng lời đọc biết cảnh đạo diễn 1 đã chọn → tránh trùng, 2 bản khác hẳn nhau
        for luot in sorted({t["j"] for t in ds}):
            nhom = [t for t in ds if t["j"] == luot]
            for t in nhom:
                t["anh_em_ds"] = next(([sg["shot"]["id"] for sg in o["plan"]["edl_segs"]] for o in tasks
                                       if o is not t and o["vname"] == t["vname"] and o.get("plan") and o["plan"].get("edl_segs")), None)
            with ThreadPoolExecutor(3) as ex:
                list(ex.map(lambda t: len_bang(t, (gop or {}).get(id(t), "")), nhom))
        ds = [t for t in ds if not t.get("hong")]      # máy tự dựng cũng không nổi → bỏ riêng video đó
        with ThreadPoolExecutor(2) as ex:      # 2 luồng FFmpeg: máy 16 GB
            ds = [x for x in ex.map(dung_nen, ds) if x]
        moi = [t for t in ds if Path(t["job"]["base"]).exists()       # bản dựng lại hỏng: giữ nguyên bản cũ, không dựng chữ lại
               and not (t.get("_cu") and t["job"]["out"] == t["_cu"]["job"]["out"])]   # (không ghi đè file cũ)
        if moi:
            SK.ghi("dung", "bat-dau", f"Dựng lớp chữ {len(moi)} video", so=len(moi), buoc="chu")
        done = set(dung_lo([t["job"] for t in moi], tam / "_public", log)) if moi else set()
        if moi:
            SK.ghi("dung", "xong", f"Xong lớp chữ {len(done)}/{len(moi)}", so=len(done), buoc="chu")
        return [t for t in moi if t["job"]["out"] in done]

    made = 0
    het_msg = None
    tong_vd = len(lam_lai) if lam_lai else so_video

    def cac_dot():
        """Từng đợt ≤ 6 video (thấy tiến độ, không giữ quá nhiều RAM). Chế độ viết lời: thu giọng NGAY TRƯỚC mỗi đợt, không mua trước cả lô;
        đã báo hết hạn mức (hoặc mọi tài khoản đang hết hạn) → ngừng mua giọng, bỏ các lời còn lại."""
        if lam_lai:
            for i0 in range(0, len(tasks), 6):
                yield tasks[i0:i0 + 6]
            return
        for i0 in range(0, len(scripts), n_sc_dot):
            if het_msg or het_han["v"] or len(tasks) >= so_video:
                return
            if not co_tai_khoan():
                het_han["v"] = True
                log("⛔ Mọi tài khoản Claude đang hết hạn mức → ngừng mua giọng cho các lời còn lại (chưa tốn tiền giọng cho video không dựng được).")
                SK.ghi("he-thong", "het-han-muc", "Hết hạn mức: ngừng thu giọng")
                return
            moi = viec_tu_loi(i0, scripts[i0:i0 + n_sc_dot])
            for x in range(0, len(moi), 6):
                yield moi[x:x + 6]

    try:
      for n_dot, dot in enumerate(cac_dot(), 1):
        try:
            xong = mot_vong(dot)
            def cham(t):                     # giám khảo lỗi / hết hạn mức → vẫn giữ video, để trống điểm (lỗi rà soát #3)
                SK.ghi("giam-khao", "bat-dau", "Đang xem và chấm", video=f'{t["vname"]}-{t["j"]}')
                try:
                    VIEC.video = f'{t["vname"]}-{t["j"]}'
                    r = giam_khao(sp, t["job"]["out"], t["info"].get("_sents") or _sents(t), t["edl"], t["work"])
                except Exception as e:
                    r = {"diem": None, "dat": None, "loi": [f"chưa chấm: {type(e).__name__}"], "sua": ""}
                r["loi"] = [str(x) for x in (r.get("loi") or []) if x]
                return t, r
            with ThreadPoolExecutor(3) as ex:
                kq = list(ex.map(cham, xong))
            ghi_bai_hoc([x for _, r in kq for x in r["loi"] if not x.startswith("chưa chấm")], ma_sp)
            for t, r in kq:
                t["gk"] = r; t["lan"] = 1
                log(f"  giám khảo {t['fname']}: {r.get('diem')}/10 {'ĐẠT' if r.get('dat') else 'CHƯA ĐẠT'} {'; '.join((r.get('loi') or [])[:2])}")
                SK.ghi("giam-khao", "diem", "Chấm xong", video=f'{t["vname"]}-{t["j"]}', diem=r.get("diem"), dat=r.get("dat"),
                       file=t.get("fname"), loi=(r["loi"][0][:90] if r.get("loi") else None), lan=t.get("lan"))
            # Kid 10/11: KHÔNG dựng lại hàng loạt (50 video thành 100). Giám khảo chỉ chấm + ghi bài học cho lô sau.
            # Bật lại bằng config "dung_lai": true nếu cần.
            sua = [t for t, r in kq if not r.get("dat") and r.get("sua")] if CFG.get("dung_lai") else []
            if sua:
                log(f"  dựng lại {len(sua)} bản theo giám khảo…")
                SK.ghi("dung", "dung-lai", f"Dựng lại {len(sua)} bản", so=len(sua))
                cu = {t["job"]["out"]: t for t in sua}
                for t in sua:                        # nhớ bản cũ để so điểm
                    t["_cu"] = {"job": dict(t["job"]), "info": t["info"], "fname": t["fname"], "gk": t["gk"], "edl": t["edl"],
                                "plan": t["plan"], "music": t.get("music")}
                gop = {id(t): f"{t['gk'].get('sua')} | Lỗi: {'; '.join(t['gk'].get('loi', []))}" for t in sua}
                try:
                    lai = mot_vong(sua, gop)
                except BaseException:            # hết hạn mức / lỗi giữa chừng → mọi bản về nguyên trạng cũ
                    lai = []
                    for t in sua:
                        for k in ("job", "info", "fname", "gk", "edl", "plan", "music"):
                            t[k] = t["_cu"][k]
                        t["lan"] = 1
                    raise
                # Chỉ tính là "dựng lại xong" khi có file MỚI khác bản cũ. Bản nào dựng nền/lớp chữ hỏng → trả lại
                # nguyên trạng bản cũ (job/info/fname/...) để vòng dưới không cất nhầm video cũ vào _ban-chua-dat.
                lai = [t for t in lai if t["job"]["out"] != t["_cu"]["job"]["out"] and Path(t["job"]["out"]).exists()]
                id_lai = {id(t) for t in lai}
                for t in sua:
                    if id(t) not in id_lai:
                        log(f"  dựng lại hỏng {t['_cu']['fname']} → giữ bản cũ")
                        for k in ("job", "info", "fname", "gk", "edl", "plan", "music"):
                            t[k] = t["_cu"][k]
                        t["lan"] = 1
                def cham_lai(t):             # chấm lại lỗi / hết hạn mức → điểm trống → giữ bản cũ (đã chấm), cất bản mới
                    try:
                        return t, giam_khao(sp, t["job"]["out"], _sents(t), t["edl"], t["work"])
                    except Exception as e:
                        return t, {"diem": None, "dat": None, "loi": [f"chưa chấm: {type(e).__name__}"], "sua": ""}
                with ThreadPoolExecutor(3) as ex:
                    kq2 = list(ex.map(cham_lai, lai))
                for t, r in kq2:
                    cu_t = t.get("_cu") or {}
                    if (r.get("diem") or 0) < (cu_t.get("gk", {}).get("diem") or 0):   # bản dựng lại kém hơn → giữ bản cũ
                        log(f"  chấm lại {t['fname']}: {r.get('diem')}/10 < bản cũ {cu_t['gk'].get('diem')}/10 → giữ bản cũ")
                        (out_dir / "_ban-chua-dat").mkdir(exist_ok=True)
                        for duoi in (".mp4", ".jpg"):
                            moi = kem(t["job"]["out"], duoi) if duoi != ".mp4" else Path(t["job"]["out"])
                            if moi.exists():
                                shutil.move(str(moi), out_dir / "_ban-chua-dat" / moi.name)
                        for k in ("job", "info", "fname", "gk", "edl", "plan", "music"):
                            t[k] = cu_t[k]
                        t["lan"] = 1
                        continue
                    log(f"  chấm lại {t['fname']}: {r.get('diem')}/10")
                    t["gk"] = r; t["lan"] = 2
                for old in cu:              # bản cũ đã được thay bằng bản dựng lại → cất vào _ban-chua-dat để so
                    if Path(old).exists() and old not in {t["job"]["out"] for t in dot}:
                        (out_dir / "_ban-chua-dat").mkdir(exist_ok=True)
                        for duoi in (".mp4", ".jpg"):
                            fo = kem(old, duoi) if duoi != ".mp4" else Path(old)
                            if fo.exists():
                                shutil.move(str(fo), out_dir / "_ban-chua-dat" / fo.name)
        except HetHanMuc as e:
            het_msg = str(e)[:160]
            SK.ghi("he-thong", "het-han-muc", "Hết hạn mức Claude", chi_tiet=het_msg)
        except Exception as e:
            log(f"  ⚠ đợt {n_dot} gặp lỗi: {type(e).__name__}: {str(e)[-200:]} → bỏ qua đợt này, làm tiếp")
            SK.ghi("he-thong", "loi", f"Đợt {n_dot} gặp lỗi: {type(e).__name__}")
        for t in dot:
            if not t.get("job") or not Path(t["job"]["out"]).exists():
                continue
            t.setdefault("gk", {"diem": None, "loi": ["chưa chấm"]}); t.setdefault("lan", 1)
            try:                          # quét khung tối: lỗi quét không được làm sập lô
                bad = scan(t["job"]["out"])
            except Exception:
                bad = []
            try:                          # khung chớp trắng/đen sát điểm cắt
                chop = kiem_chop(t["job"]["out"], t["info"].get("cuts"))
            except Exception:
                chop = []
            if chop:
                t.setdefault("sua", []).append(f"khung chớp ({chop[0].get('loai')}) ở giây {chop[0].get('t')}")
            try:                          # lưu hồ sơ từng video: 1 video lỗi ghi file không kéo theo các video còn lại
                info, edl, gk = t["info"], t["edl"], t["gk"]
                row = [t["fname"], t["sc"]["goc"], t["sc"]["giong"], t["gu"], info.get("cong_thuc"), gk.get("diem"), t["lan"],
                       " | ".join(gk.get("loi", [])), edl.get("ly_do", ""), " ".join(info.get("bo_cuc", [])), " > ".join(info.get("khoi", [])),
                       info.get("sfx"), t["music"]["ten"] if t.get("music") else "CHỌN NHẠC TIKTOK", info.get("thoi_luong"),
                       cap_cua(t), " ".join(t["sc"].get("hashtag", [])), re.sub(r"\[[^\]]*\]\s*", "", t["sc"]["text"]),
                       " | ".join(info.get("canh", [])), "; ".join(t.get("sua", []) + ([f"khung {bad[0][1]} {bad[0][0]}s"] if bad else [])),
                       "", "", "", ""]
                ghi_hang(row)
                kem(t["job"]["out"], ".txt", ghi=True).write_text(
                    (cap_cua(t) + "\n" + " ".join(t["sc"].get("hashtag", []))).strip() + "\n", encoding="utf-8")
                meta = {"id": Path(t["job"]["out"]).stem, "ma": ma_sp, "quy_cach": t["sc"].get("quy_cach"), "goc": t["sc"]["goc"],
                        "dang": t["sc"].get("dang"), "mo": t["sc"].get("mo"), "chot": t["sc"].get("chot"), "vai": t["sc"].get("vai"), "giong": t["sc"]["giong"], "dao_dien": t["gu"], "cong_thuc": info.get("cong_thuc"),
                        "nhac": t["music"]["ten"] if t.get("music") else None, "diem": gk.get("diem"), "caption": cap_cua(t),
                        "hashtag": t["sc"].get("hashtag", []), "loi_doc": re.sub(r"\[[^\]]*\]\s*", "", t["sc"]["text"]),
                        "thoi_luong": info.get("thoi_luong"), "ngay_lam": day, "luc_lam": datetime.datetime.now().isoformat(timespec="seconds"),
                        "ma_viec": f'{t["vname"]}-{t["j"]}', "ky_tu_giong": t["voice"].get("ky_tu") or len(t["voice"].get("text", "")),
                        "giong_file": t["voice"].get("meta"), "dung_chung_giong": per,          # 1 giọng dùng cho `per` video
                        "kich_ban": {k: t["sc"].get(k) for k in ("goc", "giong", "text", "dong", "y_canh", "nhan_tu", "captions", "caption",
                                                                 "hashtag", "dang", "quy_cach", "mo", "than", "chot", "vai", "chu_mo")},
                        "lam_lai_tu": t.get("lam_lai_tu")}
                kem(t["job"]["out"], ".json", ghi=True).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")   # hồ sơ video (cổng TryPost đọc)
                SK.noi_them(da_dung_f, " ".join(sg["shot"]["id"] for sg in (t["plan"].get("edl_segs") or [])) + "\n", giu_dong=600, toi_da_byte=120_000)
                ghi_lich_su_canh(ma_sp, t["plan"].get("edl_segs") or [], f'{t["vname"]}-{t["j"]}')
                made += 1
                log(f"  [{made}/{tong_vd}] {t['fname']}  ({gk.get('diem')}/10)")
                SK.ghi("kho", "luu", f"Đã lưu video {made}/{tong_vd}", video=f'{t["vname"]}-{t["j"]}', so=made, tong=tong_vd, diem=gk.get("diem"),
                       file=t.get("fname"), ngay=day)
                if t.get("lam_lai_tu"):                       # bản anh không ưng → cất vào _ban-chua-dat (tự dọn sau 5 ngày)
                    cu = Path(t["lam_lai_tu"]); dich = cu.parent / "_ban-chua-dat"; dich.mkdir(exist_ok=True)
                    for duoi in (".mp4", ".jpg", ".json", ".txt"):
                        fo = cu if duoi == ".mp4" else kem(cu, duoi)
                        if fo.exists():
                            shutil.move(str(fo), str(dich / fo.name))
                    log(f"     ↳ thay cho {cu.name} (bản cũ cất vào _ban-chua-dat)")
            except Exception as e:
                log(f"  ⚠ lưu hồ sơ {t.get('fname')} lỗi: {type(e).__name__}: {str(e)[-160:]} → bỏ qua video này, làm tiếp")
                SK.ghi("he-thong", "loi", f"Lưu hồ sơ lỗi: {type(e).__name__}", video=f'{t["vname"]}-{t["j"]}')
        try:
            ghi_nguyen_tu(sig_file, "\n".join(sorted(used_sigs)))
        except OSError:
            pass
        if het_msg:
            log(f"⛔ HẾT HẠN MỨC CLAUDE (mọi tài khoản): {het_msg}. Đã xong {made} video, đã lưu đủ hồ sơ. Đăng nhập/đổi tài khoản rồi chạy tiếp.")
            break
    finally:
        SK.noi_them(sheet, "", ma_hoa="utf-8-sig")      # gộp các hàng còn nằm ở .cho-ghi (nếu Excel đã nhả file)
        shutil.rmtree(tam, ignore_errors=True)       # luôn dọn tạm, kể cả khi lỗi giữa chừng
    try:
        from don_dep import don
        don(log)
    except Exception:
        pass
    try:
        from duyet import tu_duyet
        tu_duyet(log)                                 # tự duyệt theo điểm (nếu anh bật)
    except Exception as e:
        log(f"  (tự duyệt lỗi: {str(e)[:80]})")
    try:
        SK.ghi("giam-khao", "hoc", "Gom bài học")
        gom_bai_hoc(ma_sp, log)
    except Exception as e:
        log(f"  (gom bài học lỗi: {str(e)[:80]})")
    try:
        bao_chi_phi(t_bat_dau, made, log, ma_sp)
    except Exception as e:
        log(f"  (tính chi phí lỗi: {str(e)[:80]})")
    SK.ghi("he-thong", "ket-thuc-lo", f"Xong {made} video", so=made, tong=len(tasks), phut=round((time.time() - t_bat_dau) / 60, 1))
    log(f"XONG: {made} video tại {out_dir} trong {round((time.time() - t_bat_dau) / 60, 1)} phút")


def _sents(t):
    from dung import sentence_times
    return sentence_times(t["voice"]["text"], t["voice"]["words"])


def ghi_bai_hoc(loi, ma_sp):
    """Lỗi giám khảo bắt được → sổ bài học RIÊNG của sản phẩm (bỏ mốc giây, bỏ trùng). Gom bài học tách phần chung sau."""
    f = HUB / "lich-su" / f"bai-hoc-{ma_sp}.txt"
    cu = set(f.read_text(encoding="utf-8").splitlines()) if f.exists() else set()
    moi = []
    for x in loi:
        x = re.sub(r"^[\d.,\s]*s?\s*(câu[^:]*:)?\s*", "", str(x)).strip(" -;:")
        if len(x) > 8 and f"- {x}" not in cu:
            moi.append(f"- {x}")
    if moi:
        SK.noi_them(f, "\n".join(moi) + "\n", giu_dong=600, toi_da_byte=100_000)


def cap_cua(t):
    """Mỗi video của cùng một lời đọc dùng 1 caption khác nhau."""
    caps = t["sc"].get("captions") or [t["sc"].get("caption", "")]
    return caps[t["j"] % len(caps)]


def ctx_gom(chung, dong):
    """Dữ liệu điền vào mẫu prompt/gom-bai-hoc.md."""
    nl = chr(10)
    return {"luat_chung": nl.join(chung) or "(chưa có)", "loi_san_pham": nl.join(dong)}


def tach_chung_rieng(txt):
    """Đọc câu trả lời 2 phần CHUNG:/RIENG: — chịu được bản đề bài cũ: tiêu đề in đậm/## , chữ thường, gạch đầu dòng '-', '*', '•', '–'."""
    phan, moi = None, {"CHUNG": [], "RIENG": []}
    for l in txt.splitlines():
        l = l.strip()
        h = re.sub(r"^[#*\s]+|[*\s]+$", "", l).upper().replace("Ê", "E")
        if re.fullmatch(r"CHUNG\s*:?\s*(\(.*\))?:?", h):
            phan = "CHUNG"
        elif re.fullmatch(r"RIENG\s*:?\s*(\(.*\))?:?", h):
            phan = "RIENG"
        elif phan and re.match(r"^[-*•–]\s+\S", l):
            moi[phan].append("- " + re.sub(r"^[-*•–]\s+", "", l))
    return moi


def gom_bai_hoc(ma_sp, log=print, nguong=25):
    """Sổ bài học RIÊNG của sản phẩm dài quá → AI gom thành 2 phần: luật CHUNG (đúng cho mọi sản phẩm, không nêu tên sản phẩm/cây)
    ghi vào bai-hoc.txt, và bài học RIÊNG (chỉ đúng với sản phẩm này) giữ ở bai-hoc-<mã>.txt. Đạo diễn đọc chung + riêng của đúng sản phẩm."""
    from ai import goi
    nl = chr(10)
    f = HUB / "lich-su" / f"bai-hoc-{ma_sp}.txt"
    fc = HUB / "lich-su" / "bai-hoc.txt"
    if not f.exists():
        return
    dong = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(dong) <= nguong:
        return
    chung = [l for l in fc.read_text(encoding="utf-8").splitlines() if l.strip()] if fc.exists() else []
    import prompt_mau
    p = prompt_mau.dien("gom-bai-hoc", **ctx_gom(chung, dong))
    txt, _ = goi("gom bài học", p, model="sonnet", effort="low")
    moi = tach_chung_rieng(txt)
    if len(moi["CHUNG"]) >= 3:
        if not moi["RIENG"]:             # AI không trả phần RIENG → KHÔNG đụng gì (trước đây xoá trắng bài học riêng của sản phẩm)
            log(f"  📚 Gom sổ bài học {ma_sp}: AI không trả phần riêng → giữ nguyên sổ cũ"); return
        for x in (fc, f):                 # bản lưu phòng hờ + ghi nguyên tử (mất điện giữa chừng không để file cụt)
            try:
                if x.exists():
                    shutil.copy2(x, x.with_name(x.name + ".bak"))
            except OSError:
                pass
        ghi_nguyen_tu(fc, nl.join(moi["CHUNG"][:15]) + nl)
        ghi_nguyen_tu(f, nl.join(moi["RIENG"][:10]) + nl)
        log(f"  📚 Gom sổ bài học {ma_sp}: {len(dong)} dòng → {len(moi['CHUNG'][:15])} luật chung + {len(moi['RIENG'][:10])} riêng")


def bao_chi_phi(t0, made, log, ma_sp=""):
    """Báo cáo cuối lô: lượt AI, token, token/video, thời gian/video, từng tài khoản + hạn mức hiện tại."""
    import csv as _csv
    from ai import doc_trang_thai, ds_tai_khoan
    f = HUB / "lich-su" / "token.csv"
    if not f.exists():
        return
    bd = datetime.datetime.fromtimestamp(t0)
    rows = []
    for x in _csv.DictReader(open(f, encoding="utf-8-sig")):
        try:
            if datetime.datetime.fromisoformat(x["luc"]) >= bd:
                rows.append(x)
        except Exception:
            pass
    tok = lambda r: int(r.get("vao") or 0) + int(r.get("vao_cache_tao") or 0) + int(r.get("vao_cache_doc") or 0) + int(r.get("ra") or 0)
    tong = sum(tok(r) for r in rows); usd = sum(float(r.get("usd_uoc") or 0) for r in rows)
    phut = (time.time() - t0) / 60
    log(f"💰 CHI PHÍ LÔ: {len(rows)} lượt AI · {tong:,} token (≈ {usd:.2f} USD quy đổi)".replace(",", ".") +
        (f" · {tong // max(1, made):,} token/video · {phut / max(1, made):.1f} phút/video".replace(",", ".") if made else ""))
    theo_vai = {}
    for r in rows:
        v = (r.get("vai") or "").split(" ")[0]
        theo_vai[v] = theo_vai.get(v, 0) + tok(r)
    log("   theo vai: " + " · ".join(f"{k} {v // 1000}k" for k, v in sorted(theo_vai.items(), key=lambda z: -z[1])))
    ky_tu = 0; fg = HUB / "lich-su" / "giong.csv"
    if fg.exists():
        for x in _csv.DictReader(open(fg, encoding="utf-8-sig")):
            try:
                if datetime.datetime.fromisoformat(x["luc"]) >= bd:
                    ky_tu += int(x["ky_tu"] or 0)
            except Exception:
                pass
    if ky_tu:
        log(f"   giọng ElevenLabs: {ky_tu:,} ký tự".replace(",", ".") + (f" (≈ {ky_tu // max(1, made)} ký tự/video, 1 giọng dùng chung nhiều video)" if made else ""))
    try:                                             # lưu lại để app hiện bảng các lô
        tk_dung = {}
        for r in rows:
            tk_dung[r.get("tai_khoan") or "tk1"] = tk_dung.get(r.get("tai_khoan") or "tk1", 0) + 1
        SK.noi_them(HUB / "lich-su" / "lo.jsonl", json.dumps(
            {"bat_dau": bd.isoformat(timespec="seconds"), "ket_thuc": datetime.datetime.now().isoformat(timespec="seconds"),
             "san_pham": ma_sp, "video": made, "luot_ai": len(rows), "token": tong,
             "token_vao": sum(int(r.get("vao") or 0) + int(r.get("vao_cache_tao") or 0) + int(r.get("vao_cache_doc") or 0) for r in rows),
             "token_ra": sum(int(r.get("ra") or 0) for r in rows), "usd_quy_doi": round(usd, 2),
             "ky_tu_giong": ky_tu, "phut": round(phut, 1), "theo_vai": theo_vai, "tai_khoan": tk_dung},
            ensure_ascii=False) + "\n", giu_dong=2000, toi_da_byte=400_000)
    except Exception:
        pass
    st = doc_trang_thai(); ten = {t["ma"]: t["ten"] for t in ds_tai_khoan()}
    for ma in sorted({r.get("tai_khoan") or "tk1" for r in rows}):
        x = st.get(ma, {}); n = sum(1 for r in rows if (r.get("tai_khoan") or "tk1") == ma)
        h5 = round(((x.get("five_hour") or {}).get("pct") or 0) * 100); h7 = round(((x.get("seven_day") or {}).get("pct") or 0) * 100)
        log(f"   {ten.get(ma, ma)}: {n} lượt · hiện đã dùng 5 giờ {h5}% · tuần {h7}%")
