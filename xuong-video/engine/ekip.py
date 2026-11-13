"""Ê-KÍP AI (Kid duyệt 10/11/2026): Biên kịch → Giọng → Đạo diễn (nhìn cảnh, lên bảng dựng) → Máy dựng → Giám khảo (xem, chấm, bắt sửa 1 lần).
Gọi từ sanxuat.py. Mỗi lời đọc → nhiều video, mỗi video một đạo diễn gu khác.
Hết hạn mức Claude → dừng gọn, giữ những video đã xong."""
import csv, datetime, json, math, os, random, re, shutil, subprocess, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ai import HetHanMuc, VIEC
from viet_loi import viet
from giong import tao_giong
from dao_dien import GU, dao_dien, segs_tu_bang, giam_khao, canh_qua, canh_them
from kho_chung import kho_them_cua, la_kho_chung
from dung_remotion import chuan_bi, dung_lo
from cong_thuc import chuan_hoa
from kiem_khung import scan
import su_kien as SK

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, khung_giay, kem, kem_ngay
CFG = cfg_hub()
COT = ["file", "goc", "giong", "gu_dao_dien", "cong_thuc", "diem_giam_khao", "lan_dung", "loi_giam_khao", "y_tuong", "bo_cuc", "khoi",
       "sfx", "nhac", "thoi_luong", "caption", "hashtag", "loi", "canh", "may_sua", "danh_gia_kid", "gop_y_kid", "luot_xem", "don"]


_khoa_sig = threading.Lock()
F_KHOA = HUB / "lich-su" / "dang-chay.lock"


def dang_co_lo():
    """Có lô đang chạy (từ app hay cửa sổ lệnh)? — dựa vào file khoá chứa PID còn sống."""
    if not F_KHOA.exists():
        return False
    try:
        pid = int(F_KHOA.read_text().split()[0])
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in r.stdout
    except Exception:
        return False


def chay(ma_sp, so_video, log, music_pick, lam_lai=None):
    if dang_co_lo():
        log("⛔ Đang có một lô khác chạy — không chạy chồng (đợi lô kia xong)."); return
    F_KHOA.parent.mkdir(exist_ok=True); F_KHOA.write_text(f"{os.getpid()} {ma_sp}")
    try:
        _chay(ma_sp, so_video, log, music_pick, lam_lai)
    finally:
        F_KHOA.unlink(missing_ok=True)


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
    new = not sheet.exists()
    fsheet = open(sheet, "a", newline="", encoding="utf-8-sig"); w = csv.writer(fsheet)
    if new:
        w.writerow(COT)
    sig_file = HUB / "lich-su" / f"chu-ky-{day}.txt"
    used_sigs = set(sig_file.read_text(encoding="utf-8").split()) if sig_file.exists() else set()
    da_dung_f = HUB / "lich-su" / f"canh-da-dung-{ma_sp}.txt"
    da_dung = da_dung_f.read_text(encoding="utf-8").split()[-180:] if da_dung_f.exists() else []

    # ---- giọng + danh sách việc
    tasks, k = [], 0
    stamp0 = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    def lam_giong(i_sc):                 # giọng chạy song song 3 lời một lúc
        i, sc = i_sc
        vname = f"{ma_sp}-{sc['goc']}-{sc['giong']}-{stamp0}-{i:02d}"
        try:
            return vname, tao_giong(sc["text"], CFG["giong"]["danh_sach"][sc["giong"]], out_dir / "_giong", vname, doc=sp.get("doc_la"))
        except Exception as e:
            log(f"  giọng lỗi ({sc['goc']}): {type(e).__name__} {str(e)[:120]}")
            return vname, None
    if scripts:
        SK.ghi("giong", "bat-dau", "Đang thu giọng", so=len(scripts))
    with ThreadPoolExecutor(3) as ex:
        giong_ds = list(ex.map(lam_giong, enumerate(scripts)))
    for sc, (vname, voice) in zip(scripts, giong_ds):
        if len(tasks) >= so_video:
            break
        if voice is None:
            continue
        if voice["dur"] > khung_giay(sp, CFG)[1] - 0.7:
            log(f"  bỏ {sc['goc']}: giọng {voice['dur']} s quá dài"); continue
        for j in range(per):
            if len(tasks) >= so_video:
                break
            gu = gu_keys[(k + random.randint(0, 99)) % len(gu_keys)] if j == 0 else gu_keys[(gu_keys.index(tasks[-1]["gu"]) + 1) % len(gu_keys)]
            k += 1
            tasks.append({"sc": sc, "voice": voice, "gu": gu, "rng": random.Random(f"{vname}-{j}"), "j": j,
                          "work": tam / f"{vname}-{j}", "vname": vname})
        cau_moi = [x.strip() for x in re.split(r"(?<=[.!?])\s+", re.sub(r"\[[^\]]*\]", "", sc["text"]).strip()) if x.strip()]
        for ten_f in ("cau-da-dung.txt", f"cau-da-dung-{ma_sp}.txt"):     # chung (máy chống trùng) + riêng sản phẩm (gửi biên kịch)
            with open(HUB / "lich-su" / ten_f, "a", encoding="utf-8") as f:
                f.write("".join(x + "\n" for x in cau_moi))
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
    log(f"Giọng xong: {len(tasks)} video cần dựng")
    if scripts:
        SK.ghi("giong", "xong", f"Thu xong {sum(1 for _, v in giong_ds if v)} giọng", so=sum(1 for _, v in giong_ds if v))
    SK.ghi("he-thong", "ke-hoach", f"{len(tasks)} video cần dựng", so_video=len(tasks))

    het_han = {"v": False}

    def len_bang(t, gop_y=""):
        """Đạo diễn → bảng dựng → kế hoạch cho máy dựng."""
        t["work"].mkdir(parents=True, exist_ok=True)
        SK.ghi("dao-dien", "bat-dau", f"Đạo diễn {t['gu']} lên bảng dựng", video=f'{t["vname"]}-{t["j"]}', gu=t["gu"])
        try:
            VIEC.video = f'{t["vname"]}-{t["j"]}'            # token.csv biết lượt gọi này thuộc video nào
            edl, sents, total = dao_dien(ma_sp, sp, t["voice"], t["sc"], shots, t["gu"], t["work"], t["rng"], gop_y or t.get("gop_y", ""),
                                         tranh=set(da_dung) | t.get("tranh_anh_em", set()), qua=qua, chung=chung)
            segs, sua = segs_tu_bang(edl, sents, total, shots + [x for ds in qua.values() for x in ds] + chung)
            da_dung.extend(sg["shot"]["id"] for sg in segs)    # video sau trong cùng lô cũng tránh các cảnh này
            (t["work"] / "bang-dung.json").write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
        except HetHanMuc:
            het_han["v"] = True; SK.ghi("he-thong", "het-han-muc", "Hết hạn mức Claude khi lên bảng dựng"); raise
        except Exception as e:
            log(f"  đạo diễn lỗi ({t['gu']}): {str(e)[:160]} → máy tự dựng theo luật")
            SK.ghi("dao-dien", "loi", f"Đạo diễn lỗi, máy tự dựng: {str(e)[:80]}", video=f'{t["vname"]}-{t["j"]}')
            edl, segs, sua = {"gu": t["gu"], "ly_do": "máy tự dựng (đạo diễn lỗi)"}, None, ["đạo diễn lỗi"]
        st = {kk: edl.get(kk) for kk in ("cong_thuc", "phu_de", "mau_nhan", "chuyen_canh", "chuyen_dong", "mau", "sfx", "nhac") if edl.get(kk)}
        st["khoi"] = [x for x in edl.get("khoi", []) if isinstance(x, dict)]
        st["nhan_tu"] = edl.get("nhan_tu") or t["sc"].get("nhan_tu", [])
        with _khoa_sig:                       # 3 luồng đạo diễn cùng sửa used_sigs (lỗi rà soát #11)
            st = chuan_hoa(st, t["rng"], used_sigs, tu_do=bool(segs))
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
                t["tranh_anh_em"] = {sg["shot"]["id"] for o in tasks if o is not t and o["vname"] == t["vname"] and o.get("plan")
                                     for sg in (o["plan"].get("edl_segs") or [])}
            with ThreadPoolExecutor(3) as ex:
                list(ex.map(lambda t: len_bang(t, (gop or {}).get(id(t), "")), nhom))
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
    try:
      for i in range(0, len(tasks), 6):     # mỗi đợt 6 video để thấy tiến độ và không giữ quá nhiều RAM
        dot = tasks[i:i + 6]
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
            log(f"  ⚠ đợt {i // 6 + 1} gặp lỗi: {type(e).__name__}: {str(e)[-200:]} → bỏ qua đợt này, làm tiếp")
            SK.ghi("he-thong", "loi", f"Đợt {i // 6 + 1} gặp lỗi: {type(e).__name__}")
        for t in dot:
            if not t.get("job") or not Path(t["job"]["out"]).exists():
                continue
            t.setdefault("gk", {"diem": None, "loi": ["chưa chấm"]}); t.setdefault("lan", 1)
            bad = scan(t["job"]["out"])
            info, edl, gk = t["info"], t["edl"], t["gk"]
            row = [t["fname"], t["sc"]["goc"], t["sc"]["giong"], t["gu"], info.get("cong_thuc"), gk.get("diem"), t["lan"],
                   " | ".join(gk.get("loi", [])), edl.get("ly_do", ""), " ".join(info.get("bo_cuc", [])), " > ".join(info.get("khoi", [])),
                   info.get("sfx"), t["music"]["ten"] if t.get("music") else "CHỌN NHẠC TIKTOK", info.get("thoi_luong"),
                   cap_cua(t), " ".join(t["sc"].get("hashtag", [])), re.sub(r"\[[^\]]*\]\s*", "", t["sc"]["text"]),
                   " | ".join(info.get("canh", [])), "; ".join(t.get("sua", []) + ([f"khung {bad[0][1]} {bad[0][0]}s"] if bad else [])),
                   "", "", "", ""]
            w.writerow(row); fsheet.flush()
            kem(t["job"]["out"], ".txt", ghi=True).write_text(
                (cap_cua(t) + "\n" + " ".join(t["sc"].get("hashtag", []))).strip() + "\n", encoding="utf-8")
            meta = {"id": Path(t["job"]["out"]).stem, "ma": ma_sp, "quy_cach": t["sc"].get("quy_cach"), "goc": t["sc"]["goc"],
                    "dang": t["sc"].get("dang"), "giong": t["sc"]["giong"], "dao_dien": t["gu"], "cong_thuc": info.get("cong_thuc"),
                    "nhac": t["music"]["ten"] if t.get("music") else None, "diem": gk.get("diem"), "caption": cap_cua(t),
                    "hashtag": t["sc"].get("hashtag", []), "loi_doc": re.sub(r"\[[^\]]*\]\s*", "", t["sc"]["text"]),
                    "thoi_luong": info.get("thoi_luong"), "ngay_lam": day, "luc_lam": datetime.datetime.now().isoformat(timespec="seconds"),
                    "ma_viec": f'{t["vname"]}-{t["j"]}', "ky_tu_giong": t["voice"].get("ky_tu") or len(t["voice"].get("text", "")),
                    "giong_file": t["voice"].get("meta"), "dung_chung_giong": per,          # 1 giọng dùng cho `per` video
                    "kich_ban": {k: t["sc"].get(k) for k in ("goc", "giong", "text", "dong", "y_canh", "nhan_tu", "captions", "caption",
                                                             "hashtag", "dang", "quy_cach")},
                    "lam_lai_tu": t.get("lam_lai_tu")}
            kem(t["job"]["out"], ".json", ghi=True).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")   # hồ sơ video (cổng TryPost đọc)
            with open(da_dung_f, "a", encoding="utf-8") as f:
                f.write(" ".join(sg["shot"]["id"] for sg in (t["plan"].get("edl_segs") or [])) + "\n")
            made += 1
            log(f"  [{made}/{len(tasks)}] {t['fname']}  ({gk.get('diem')}/10)")
            SK.ghi("kho", "luu", f"Đã lưu video {made}/{len(tasks)}", video=f'{t["vname"]}-{t["j"]}', so=made, tong=len(tasks), diem=gk.get("diem"),
                   file=t.get("fname"), ngay=day)
            if t.get("lam_lai_tu"):                       # bản anh không ưng → cất vào _ban-chua-dat (tự dọn sau 5 ngày)
                cu = Path(t["lam_lai_tu"]); dich = cu.parent / "_ban-chua-dat"; dich.mkdir(exist_ok=True)
                for duoi in (".mp4", ".jpg", ".json", ".txt"):
                    fo = cu if duoi == ".mp4" else kem(cu, duoi)
                    if fo.exists():
                        shutil.move(str(fo), str(dich / fo.name))
                log(f"     ↳ thay cho {cu.name} (bản cũ cất vào _ban-chua-dat)")
        sig_file.write_text("\n".join(sorted(used_sigs)), encoding="utf-8")
        if het_msg:
            log(f"⛔ HẾT HẠN MỨC CLAUDE (mọi tài khoản): {het_msg}. Đã xong {made} video, đã lưu đủ hồ sơ. Đăng nhập/đổi tài khoản rồi chạy tiếp.")
            break
    finally:
        fsheet.close()                    # luôn đóng bảng ghi + dọn tạm, kể cả khi lỗi giữa chừng
        shutil.rmtree(tam, ignore_errors=True)
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
        with open(f, "a", encoding="utf-8") as fh:
            fh.write("\n".join(moi) + "\n")


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
        fc.write_text(nl.join(moi["CHUNG"][:15]) + nl, encoding="utf-8")
        f.write_text(nl.join(moi["RIENG"][:10]) + (nl if moi["RIENG"] else ""), encoding="utf-8")
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
        with open(HUB / "lich-su" / "lo.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"bat_dau": bd.isoformat(timespec="seconds"), "ket_thuc": datetime.datetime.now().isoformat(timespec="seconds"),
                                 "san_pham": ma_sp, "video": made, "luot_ai": len(rows), "token": tong,
                                 "token_vao": sum(int(r.get("vao") or 0) + int(r.get("vao_cache_tao") or 0) + int(r.get("vao_cache_doc") or 0) for r in rows),
                                 "token_ra": sum(int(r.get("ra") or 0) for r in rows), "usd_quy_doi": round(usd, 2),
                                 "ky_tu_giong": ky_tu, "phut": round(phut, 1), "theo_vai": theo_vai, "tai_khoan": tk_dung},
                                ensure_ascii=False) + "\n")
    except Exception:
        pass
    st = doc_trang_thai(); ten = {t["ma"]: t["ten"] for t in ds_tai_khoan()}
    for ma in sorted({r.get("tai_khoan") or "tk1" for r in rows}):
        x = st.get(ma, {}); n = sum(1 for r in rows if (r.get("tai_khoan") or "tk1") == ma)
        h5 = round(((x.get("five_hour") or {}).get("pct") or 0) * 100); h7 = round(((x.get("seven_day") or {}).get("pct") or 0) * 100)
        log(f"   {ten.get(ma, ma)}: {n} lượt · hiện đã dùng 5 giờ {h5}% · tuần {h7}%")
