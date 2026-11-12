"""TỰ ĐỘNG GIỮ KHO VIDEO (Kid 10/11/2026): app tự đếm video còn tồn (chưa đăng, chưa bị ❌) của từng sản phẩm;
gần hết (dưới mức tồn tối thiểu) thì tự làm thêm một lô, không vượt mức tối đa mỗi ngày.
Cài đặt trong config.json mục "tu_dong"; app phải đang mở. Hết hạn mức Claude → nghỉ 60 phút rồi thử lại."""
import datetime, json, sys, threading, time
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
LS = HUB / "lich-su"
sys.path.insert(0, str(CODE / "engine"))
from kho_chung import la_kho_chung   # noqa: E402  (kho cảnh dùng chung: không bán, không tự làm video)
TRANG_THAI = {"lan_kiem": None, "lan_kiem_toi": None, "nghi_den": None, "ghi": "Chưa bật"}


def cfg():
    return cfg_hub()


def _doc(f, md):
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else md


def dem(ma):
    """(tồn: video chưa đăng & chưa ❌, làm hôm nay)."""
    ra = Path(cfg()["duong_dan"]["ra"])
    dg = _doc(LS / "danh-gia.json", {}); tt = _doc(LS / "trypost.json", {})
    hom_nay = datetime.date.today().isoformat()
    ton = nay = 0
    for v in ra.glob(f"*/{ma}_*.mp4"):
        if v.parent.name.startswith("_"):
            continue
        if v.parent.name == hom_nay:
            nay += 1
        if (tt.get(v.stem) or {}).get("trang_thai") == "da_dang" or (dg.get(v.name) or {}).get("ket_qua") == "bo":
            continue
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
        da_lam = len([v for v in ra.glob(f"*/{d.name}_*.mp4") if not v.parent.name.startswith("_")])
        v = sps.get(d.name, {"bat": False, "ton_toi_thieu": 10, "toi_da_ngay": 30, "lo": 10})
        out[d.name] = dict(v, ten=sp.get("ten_goi", d.name), ton=ton, lam_hom_nay=nay, da_lam=da_lam)
    return {"bat": bool(c.get("bat")), "kiem_moi_phut": c.get("kiem_moi_phut", 15), "trang_thai": TRANG_THAI, "san_pham": out}


def _vong(dang_chay, chay, log_file):
    while True:
        try:
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
                TRANG_THAI["ghi"] = f"Hết hạn mức Claude — nghỉ tới {TRANG_THAI['nghi_den']:%H:%M} (đổi tài khoản để chạy ngay)"
            elif dang_chay():
                TRANG_THAI["ghi"] = "Đang có lô chạy — chờ xong"
            else:
                tat = (LS / "nhat-ky.txt").read_text(encoding="utf-8", errors="replace").splitlines() if (LS / "nhat-ky.txt").exists() else []
                bd = max([i for i, l in enumerate(tat) if "BẮT ĐẦU" in l] or [0])
                nk = tat[bd:]                                  # cả lô gần nhất (dòng ⛔ có thể không nằm cuối)
                lo_tu_dong_loi = TRANG_THAI.get("vua_chay") and any("XONG: 0 video" in l for l in nk)
                dong_het = next((l for l in nk if "HẾT HẠN MỨC" in l), None)
                if dong_het and dong_het != TRANG_THAI.get("da_nghi_vi"):      # mọi tài khoản đều hết → nghỉ tới giờ reset sớm nhất (1 lần cho mỗi lần báo)
                    TRANG_THAI["da_nghi_vi"] = dong_het
                    st = _doc(LS / "tai-khoan.json", {})
                    resets = [v.get("het_den") for v in st.values() if v.get("het_den") and v["het_den"] > time.time()]
                    TRANG_THAI["nghi_den"] = datetime.datetime.fromtimestamp(min(resets)) if resets else now + datetime.timedelta(minutes=60)
                    TRANG_THAI["ghi"] = f"Mọi tài khoản hết hạn mức — nghỉ tới {TRANG_THAI['nghi_den']:%H:%M}"
                elif lo_tu_dong_loi:                            # lô tự động vừa rồi không ra video nào → nghỉ 60 phút, khỏi đốt token
                    TRANG_THAI["vua_chay"] = None
                    TRANG_THAI["nghi_den"] = now + datetime.timedelta(minutes=60)
                    TRANG_THAI["ghi"] = f"Lô tự động vừa rồi không ra video (xem nhật ký) — nghỉ tới {TRANG_THAI['nghi_den']:%H:%M}"
                else:
                    TRANG_THAI["nghi_den"] = None
                    viec, ung = None, []
                    for ma, v in c.get("san_pham", {}).items():
                        if not v.get("bat", True) or not san_sang(ma):
                            continue
                        ton, nay = dem(ma)
                        toi_thieu = int(v.get("ton_toi_thieu", 10)); con_ngay = int(v.get("toi_da_ngay", 30)) - nay
                        if ton < toi_thieu and con_ngay > 0:
                            ung.append((ton / max(1, toi_thieu), ma, max(1, min(int(v.get("lo", 10)), con_ngay)), ton))
                    if ung:                                      # ưu tiên sản phẩm thiếu tồn nhiều nhất
                        _, ma, n, ton = sorted(ung)[0]; viec = (ma, n, ton)
                    if viec:
                        ma, n, ton = viec
                        r = chay(ma, n); TRANG_THAI["vua_chay"] = ma if r.get("ok") else None
                        TRANG_THAI["ghi"] = f"{now:%H:%M} tự làm {n} video {ma} (tồn còn {ton})" if r.get("ok") else f"Không chạy được: {r.get('loi')}"
                        with open(log_file, "a", encoding="utf-8") as f:
                            f.write(f"[{now:%H:%M:%S}] 🤖 TỰ ĐỘNG: {ma} tồn {ton} < mức tối thiểu → làm {n} video\n")
                    else:
                        TRANG_THAI["ghi"] = "Kho đủ — chưa cần làm thêm"
        except Exception as e:
            TRANG_THAI["ghi"] = f"Lỗi tự động: {str(e)[:120]}"
            phut = 15
        time.sleep(phut * 60)


def bat_dau(dang_chay, chay):
    threading.Thread(target=_vong, args=(dang_chay, chay, LS / "nhat-ky.txt"), daemon=True).start()
