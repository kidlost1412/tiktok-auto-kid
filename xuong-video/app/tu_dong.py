"""TỰ ĐỘNG GIỮ KHO VIDEO (Kid 10/11/2026): app tự đếm video còn tồn (chưa đăng, chưa bị ❌) của từng sản phẩm;
gần hết (dưới mức tồn tối thiểu) thì tự làm thêm một lô, không vượt mức tối đa mỗi ngày.
Cài đặt trong config.json mục "tu_dong"; app phải đang mở. Hết hạn mức Claude → nghỉ 60 phút rồi thử lại."""
import datetime, json, sys, threading, time
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, ghi_json
LS = HUB / "lich-su"
sys.path.insert(0, str(CODE / "engine"))
from kho_chung import la_kho_chung   # noqa: E402  (kho cảnh dùng chung: không bán, không tự làm video)
TRANG_THAI = {"lan_kiem": None, "lan_kiem_toi": None, "nghi_den": None, "ly_do_nghi": None, "ghi": "Chưa bật"}
F_NGHI = LS / "tu-dong-nghi.json"              # bền qua lần khởi động lại app: giờ nghỉ, số lần lô lỗi liên tiếp, số lô tự động hôm nay
BACKOFF_PHUT = (10, 30, 60)                    # lô tự động lỗi (thoát khác 0 / ra 0 video): nghỉ 10 → 30 → 60 phút (lần sau nữa vẫn 60)
TOI_DA_LO_NGAY = 8                             # mặc định tối đa số lô TỰ ĐỘNG mỗi ngày (config tu_dong.toi_da_lo_ngay); chặn đốt token khi lỗi lặp
NGHI_SAU_DUNG_PHUT = 240                       # anh bấm DỪNG → tự động nghỉ 4 giờ (config tu_dong.nghi_sau_dung_phut) hoặc tới khi anh bấm chạy tay


_KHOA_NGHI = threading.RLock()


def _doc_nghi():
    try:
        return json.loads(F_NGHI.read_text(encoding="utf-8")) if F_NGHI.exists() else {}
    except Exception:
        return {}


def _luu_nghi(**kv):
    with _KHOA_NGHI:
        d = _doc_nghi(); d.update(kv)
        try:
            ghi_json(F_NGHI, d, indent=1)
        except OSError:
            pass


def _doc_sp(ma):
    """Trạng thái riêng của sản phẩm trong F_NGHI["sp"][ma]: nghi_den (giờ nghỉ), ly_do, loi_lien_tiep, ngay + so_lo (số lô tự động hôm nay)."""
    return (_doc_nghi().get("sp") or {}).get(ma) or {}


def _luu_sp(ma, **kv):
    with _KHOA_NGHI:
        d = _doc_nghi(); x = d.setdefault("sp", {}).setdefault(ma, {}); x.update(kv)
        try:
            ghi_json(F_NGHI, d, indent=1)
        except OSError:
            pass


def sp_nghi_den(ma):
    """Giờ (datetime) sản phẩm còn đang nghỉ (lô lỗi liên tiếp / anh bấm DỪNG sản phẩm này); None nếu không nghỉ."""
    try:
        t = _doc_sp(ma).get("nghi_den")
        return datetime.datetime.fromtimestamp(t) if t and t > time.time() else None
    except (TypeError, ValueError, OSError):
        return None


def _ds_vua_chay():
    """Các sản phẩm vòng tự động đã bật lô và chưa xét kết quả. TRANG_THAI["vua_chay"]: dict {mã: True} (cũ: 1 mã dạng chuỗi)."""
    v = TRANG_THAI.get("vua_chay")
    if not v:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


def _dat_vua_chay(ma, co):
    ds = {m: True for m in _ds_vua_chay()}
    if co:
        ds[ma] = True
    else:
        ds.pop(ma, None)
    TRANG_THAI["vua_chay"] = ds or None


def tam_nghi(phut, ly_do, dem_loi=None, ma=None):
    """Đặt giờ nghỉ cho vòng tự động (nhớ cả khi app khởi động lại). ly_do hiện ở trạng thái cho anh thấy.
    ma=None: nghỉ CHUNG mọi sản phẩm (hết hạn mức Claude / anh bấm DỪNG tất cả); có mã: chỉ sản phẩm đó nghỉ (lô lỗi / anh bấm DỪNG sản phẩm đó)."""
    den = datetime.datetime.now() + datetime.timedelta(minutes=phut)
    if ma:
        kv = {"nghi_den": den.timestamp(), "ly_do": ly_do}
        if dem_loi is not None:
            kv["loi_lien_tiep"] = dem_loi
        _luu_sp(ma, **kv)
        TRANG_THAI["ghi"] = f"{ma}: {ly_do} — nghỉ tới {den:%H:%M}"
        return den
    TRANG_THAI["nghi_den"] = den; TRANG_THAI["ly_do_nghi"] = ly_do
    TRANG_THAI["ghi"] = f"{ly_do} — nghỉ tới {den:%H:%M}"
    kv = {"nghi_den": den.timestamp(), "ly_do": ly_do}
    if dem_loi is not None:
        kv["loi_lien_tiep"] = dem_loi
    _luu_nghi(**kv)
    return den


def huy_nghi(ma=None):
    """Anh bấm chạy tay → bỏ giờ nghỉ chung (kể cả sau DỪNG / hết hạn mức) và giờ nghỉ của sản phẩm vừa chạy (lô lỗi / DỪNG)."""
    TRANG_THAI["nghi_den"] = None; TRANG_THAI["ly_do_nghi"] = None
    if _doc_nghi().get("nghi_den"):
        _luu_nghi(nghi_den=None, ly_do=None, loi_lien_tiep=0)
    if ma and (_doc_sp(ma).get("nghi_den") or _doc_sp(ma).get("loi_lien_tiep")):
        _luu_sp(ma, nghi_den=None, ly_do=None, loi_lien_tiep=0)


def khi_bam_dung(phut=None, ma=None):
    """Gọi từ dung(): bấm DỪNG thì vòng tự động KHÔNG được bật lô mới ngay. ma: chỉ dừng sản phẩm đó → chỉ sản phẩm đó nghỉ; không mã: nghỉ chung."""
    if ma:
        _dat_vua_chay(ma, False)                   # lô bị kill không tính là "lô tự động lỗi"
    else:
        TRANG_THAI["vua_chay"] = None
    if phut is None:
        phut = int(cfg().get("tu_dong", {}).get("nghi_sau_dung_phut", NGHI_SAU_DUNG_PHUT))
    return tam_nghi(max(1, phut), "Anh vừa bấm DỪNG (bấm chạy lại để tiếp tục)", ma=ma)


def _nap_nghi():
    """Sau khi app khởi động lại: nạp lại giờ nghỉ chung đã lưu."""
    if TRANG_THAI["nghi_den"] is None:
        d = _doc_nghi()
        try:
            if d.get("nghi_den") and d["nghi_den"] > time.time():
                TRANG_THAI["nghi_den"] = datetime.datetime.fromtimestamp(d["nghi_den"]); TRANG_THAI["ly_do_nghi"] = d.get("ly_do")
        except (TypeError, ValueError, OSError):
            pass


def so_lo_hom_nay(ma=None):
    """Số lô TỰ ĐỘNG đã chạy hôm nay: của sản phẩm `ma` (trần mỗi ngày tính riêng từng sản phẩm); không mã: bộ đếm chung kiểu cũ."""
    d = _doc_sp(ma) if ma else _doc_nghi()
    return int(d.get("so_lo", 0)) if d.get("ngay") == datetime.date.today().isoformat() else 0


def ghi_nhan_lo(ma=None):
    kv = {"ngay": datetime.date.today().isoformat(), "so_lo": so_lo_hom_nay(ma) + 1}
    _luu_sp(ma, **kv) if ma else _luu_nghi(**kv)


def cfg():
    return cfg_hub()


def _doc(f, md):
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else md


def dem(ma):
    """(tồn: video app TikTok Auto lấy đăng được, làm hôm nay).
    Tồn = ĐÚNG bộ lọc của cổng cong_trypost.ds_video(status="ung"): đã ✅ (ket_qua "dat") và chưa đăng (trang_thai != "da_dang").
    Bật "Tự duyệt theo điểm": chỉ tính video ✅. Tắt: tính thêm video chờ duyệt tay (chưa ✅/❌) để không làm thừa."""
    ra = Path(cfg()["duong_dan"]["ra"])
    dg = _doc(LS / "danh-gia.json", {}); tt = _doc(LS / "trypost.json", {})
    hom_nay = datetime.date.today().isoformat()
    ton = nay = 0
    tu_duyet_bat = bool((cfg().get("tu_duyet") or {}).get("bat"))
    for v in ra.glob(f"*/{ma}_*.mp4"):
        if v.parent.name.startswith("_") or v.name.endswith(".part.mp4"):
            continue
        if v.parent.name == hom_nay:
            nay += 1
        kq = (dg.get(v.name) or {}).get("ket_qua")
        if (tt.get(v.stem) or {}).get("trang_thai") == "da_dang" or kq == "bo":
            continue
        if kq == "dat" or (not tu_duyet_bat and not kq):   # tắt tự duyệt: video chờ anh duyệt tay vẫn tính tồn (khỏi làm thừa, tốn hạn mức)
            ton += 1
    return ton, nay


def san_sang(ma):
    """Đủ sự thật + quà + kho cảnh mới cho tự làm."""
    d = HUB / "san-pham" / ma
    sp = _doc(d / "san-pham.json", {})
    return bool(sp.get("su_that_duoc_noi") and sp.get("qua_tang") and (d / "canh.json").exists() and not la_kho_chung(sp))


def bao_cao():
    """Mọi sản phẩm (trừ kho cảnh dùng chung) đều hiện: video đã làm, còn tồn, làm hôm nay + cài đặt tự động (mặc định nếu chưa cài)."""
    c = cfg().get("tu_dong", {})
    sps = c.get("san_pham", {})
    ra = Path(cfg()["duong_dan"]["ra"])
    out = {}
    for d in sorted((HUB / "san-pham").iterdir()):
        f = d / "san-pham.json"
        if not f.exists():
            continue
        sp = _doc(f, {})
        if la_kho_chung(sp):
            continue
        ton, nay = dem(d.name)
        da_lam = len([v for v in ra.glob(f"*/{d.name}_*.mp4") if not v.parent.name.startswith("_") and not v.name.endswith(".part.mp4")])
        v = sps.get(d.name, {"bat": False, "ton_toi_thieu": 10, "toi_da_ngay": 30, "lo": 10})
        out[d.name] = dict(v, ten=sp.get("ten_goi", d.name), ton=ton, lam_hom_nay=nay, da_lam=da_lam)
    return {"bat": bool(c.get("bat")), "kiem_moi_phut": c.get("kiem_moi_phut", 15), "trang_thai": TRANG_THAI, "san_pham": out}


def _cau_noi(dang_chay, ma_thoat, cau):
    """Gom các hàm app cung cấp cho vòng tự động. Bản cũ (không truyền `cau`): coi như máy chỉ chạy 1 lô, nhật ký chung, dang_chay/ma_thoat không nhận mã."""
    cau = dict(cau or {})

    def dc(ma=None):
        try:
            return dang_chay(ma)
        except TypeError:
            return dang_chay()

    def mt(ma):
        if not ma_thoat:
            return None
        try:
            return ma_thoat(ma)
        except TypeError:
            return ma_thoat()

    def nk_chung(ma=None):
        f = LS / "nhat-ky.txt"
        tat = f.read_text(encoding="utf-8", errors="replace").splitlines() if f.exists() else []
        return tat[max([i for i, l in enumerate(tat) if "BẮT ĐẦU" in l] or [0]):]          # cả lô gần nhất (dòng ⛔ có thể không nằm cuối)
    cau.setdefault("dang_chay", dc)
    cau.setdefault("ma_thoat", mt)
    cau.setdefault("nhat_ky", nk_chung)
    cau.setdefault("so_dang_chay", lambda: 1 if dc() else 0)
    cau.setdefault("toi_da", lambda: 1)
    cau.setdefault("so_cho", lambda: 0)
    cau.setdefault("bo_hang", lambda ma: None)
    return cau


def _xet_lo_da_xong(cau, now):
    """Xét kết quả các lô TỰ ĐỘNG đã chạy xong (đọc nhật ký RIÊNG của đúng lô đó): mọi tài khoản hết hạn mức → nghỉ chung tới giờ reset;
    lô lỗi / không ra video → CHỈ sản phẩm đó nghỉ lùi dần 10 → 30 → 60 phút; lô ổn → hết đếm lỗi của sản phẩm. Trả True nếu vừa đặt nghỉ chung."""
    nghi_chung = False
    for ma in _ds_vua_chay():
        if cau["dang_chay"](ma):
            continue
        nk = cau["nhat_ky"](ma)
        rc = cau["ma_thoat"](ma)                                  # mã thoát của lô vừa rồi (None = không rõ / chưa có)
        _dat_vua_chay(ma, False)
        dong_het = next((l for l in nk if "HẾT HẠN MỨC" in l), None)
        loi = any("XONG: 0 video" in l for l in nk) or rc not in (None, 0)
        if dong_het and dong_het != TRANG_THAI.get("da_nghi_vi"):      # mọi tài khoản đều hết → nghỉ tới giờ reset sớm nhất (1 lần cho mỗi lần báo)
            TRANG_THAI["da_nghi_vi"] = dong_het
            st = _doc(LS / "tai-khoan.json", {})
            resets = [v.get("het_den") for v in st.values() if v.get("het_den") and v["het_den"] > time.time()]
            TRANG_THAI["nghi_den"] = datetime.datetime.fromtimestamp(min(resets)) if resets else now + datetime.timedelta(minutes=60)
            TRANG_THAI["ly_do_nghi"] = None
            TRANG_THAI["ghi"] = f"Mọi tài khoản hết hạn mức — nghỉ tới {TRANG_THAI['nghi_den']:%H:%M}"
            nghi_chung = True
        elif loi:                                         # lô lỗi → nghỉ lùi dần (khỏi chạy lại mãi, đốt token) — riêng từng sản phẩm
            n = int(_doc_sp(ma).get("loi_lien_tiep", 0))
            tam_nghi(BACKOFF_PHUT[min(n, len(BACKOFF_PHUT) - 1)], f"Lô tự động lỗi/không ra video lần {n + 1} (xem nhật ký)", dem_loi=n + 1, ma=ma)
        elif _doc_sp(ma).get("loi_lien_tiep"):            # lô tự động vừa rồi ổn → hết đếm lỗi liên tiếp của sản phẩm
            _luu_sp(ma, loi_lien_tiep=0)
    return nghi_chung


def _vong(dang_chay, chay, log_file, ma_thoat=None, cau=None):
    cau = _cau_noi(dang_chay, ma_thoat, cau)
    while True:
        try:
            _nap_nghi()
            c = cfg().get("tu_dong", {})
            phut = max(5, int(c.get("kiem_moi_phut", 15)))
            now = datetime.datetime.now()
            TRANG_THAI["lan_kiem"] = now.strftime("%H:%M")
            TRANG_THAI["lan_kiem_toi"] = (now + datetime.timedelta(minutes=phut)).strftime("%H:%M")
            try:                                         # tự duyệt theo điểm cho video mới (nếu anh bật)
                import sys as _sys; _sys.path.insert(0, str(CODE / "engine"))
                from duyet import tu_duyet
                tu_duyet(lambda *_: None)
            except Exception:
                pass
            if not c.get("bat"):
                TRANG_THAI["ghi"] = "Đang tắt"
            elif TRANG_THAI["nghi_den"] and now < TRANG_THAI["nghi_den"]:
                TRANG_THAI["ghi"] = (f"{TRANG_THAI['ly_do_nghi']} — nghỉ tới {TRANG_THAI['nghi_den']:%H:%M}" if TRANG_THAI.get("ly_do_nghi")
                                     else f"Hết hạn mức Claude — nghỉ tới {TRANG_THAI['nghi_den']:%H:%M} (đổi tài khoản để chạy ngay)")
            elif _xet_lo_da_xong(cau, now):
                pass                                     # vừa đặt nghỉ chung (hết hạn mức) → lượt này không bật lô mới
            else:
                TRANG_THAI["nghi_den"] = None; TRANG_THAI["ly_do_nghi"] = None
                dang, toi_da = int(cau["so_dang_chay"]()), max(1, int(cau["toi_da"]()))
                if dang >= toi_da or cau["so_cho"]() > 0:        # máy đã đủ lô (theo sức máy) hoặc đang có lô xếp hàng chờ: không thêm
                    TRANG_THAI["ghi"] = "Đang có lô chạy — chờ xong" if toi_da <= 1 else f"Đang chạy {dang}/{toi_da} lô — chờ có chỗ"
                else:
                    ung, tran, nghi = [], [], []
                    toi_da_lo = int(c.get("toi_da_lo_ngay", TOI_DA_LO_NGAY))
                    for ma, v in c.get("san_pham", {}).items():
                        if not v.get("bat", True) or not san_sang(ma) or cau["dang_chay"](ma):          # sản phẩm đang chạy: không bao giờ chạy 2 lô cùng lúc
                            continue
                        den = sp_nghi_den(ma)
                        if den:
                            nghi.append(f"{ma} nghỉ tới {den:%H:%M}"); continue
                        ton, nay = dem(ma)
                        toi_thieu = int(v.get("ton_toi_thieu", 10)); con_ngay = int(v.get("toi_da_ngay", 30)) - nay
                        if ton < toi_thieu and con_ngay > 0:
                            if so_lo_hom_nay(ma) >= toi_da_lo:       # trần số lô tự động/ngày của từng sản phẩm (chặn vòng lặp lỗi đốt token)
                                tran.append(ma); continue
                            ung.append((ton / max(1, toi_thieu), ma, max(1, min(int(v.get("lo", 10)), con_ngay)), ton))
                    bat = []
                    for _, ma, n, ton in sorted(ung):                # ưu tiên sản phẩm thiếu tồn nhiều nhất; còn chỗ thì bật thêm sản phẩm khác
                        if dang >= toi_da:
                            break
                        r = chay(ma, n)
                        if r.get("ok") and r.get("cho"):             # hết chỗ bất ngờ (RAM) → rút khỏi hàng chờ, vòng sau thử lại
                            cau["bo_hang"](ma)
                            TRANG_THAI["ghi"] = f"Máy chưa đủ chỗ cho {ma} — thử lại sau"
                            break
                        if r.get("ok"):
                            dang += 1; bat.append((ma, n, ton))
                            _dat_vua_chay(ma, True); ghi_nhan_lo(ma)
                            with open(log_file, "a", encoding="utf-8") as f:
                                f.write(f"[{now:%H:%M:%S}] 🤖 TỰ ĐỘNG: {ma} tồn {ton} < mức tối thiểu → làm {n} video\n")
                        else:
                            TRANG_THAI["ghi"] = f"Không chạy được: {r.get('loi')}"
                    if bat:
                        TRANG_THAI["ghi"] = f"{now:%H:%M} tự làm " + "; ".join(f"{n} video {ma} (tồn còn {ton})" for ma, n, ton in bat)
                    elif tran and not ung:
                        TRANG_THAI["ghi"] = f"Đã chạy đủ {toi_da_lo} lô tự động hôm nay ({', '.join(tran)}) — chờ sang ngày mai (hoặc anh bấm chạy tay)"
                    elif not ung:
                        TRANG_THAI["ghi"] = ("Kho đủ — chưa cần làm thêm" if not nghi else "Sản phẩm đang nghỉ: " + "; ".join(nghi))
        except Exception as e:
            TRANG_THAI["ghi"] = f"Lỗi tự động: {str(e)[:120]}"
            phut = 15
        time.sleep(phut * 60)


def bat_dau(dang_chay, chay, ma_thoat=None, cau=None):
    """dang_chay(ma=None) → bool; chay(ma, n) → dict; ma_thoat(ma) → mã thoát lô vừa rồi của sản phẩm; cau: {so_dang_chay, toi_da, nhat_ky(ma), so_cho, bo_hang(ma)}."""
    threading.Thread(target=_vong, args=(dang_chay, chay, LS / "nhat-ky.txt", ma_thoat, cau), daemon=True).start()
