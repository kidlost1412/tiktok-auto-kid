"""ĐIỀU PHỐI NHIỀU LÔ SẢN XUẤT CÙNG LÚC (app/server.py và app/tu_dong.py dùng chung).

- Mỗi sản phẩm một lô (khoá lich-su/dang-chay-<mã>.lock, xem engine/don_dep.py): khác sản phẩm chạy song song, cùng sản phẩm không bao giờ 2 lô.
- Số lô chạy cùng lúc tối đa do SỨC MÁY quyết (engine/suc_may.py: từ RAM, chỉnh được ở config "lo"). Hết chỗ (hoặc RAM trống dưới ngưỡng)
  thì lô mới vào HÀNG CHỜ (FIFO, lưu ở lich-su/hang-cho-lo.json nên khởi động lại app vẫn còn); luồng nền tự bật lô kế khi có chỗ.
- Lô đang chạy = tiến trình do app này bật (RUN) + lô còn sống theo file khoá (app phiên trước / cửa sổ lệnh / bản CLI cũ dang-chay.lock).
- Nhật ký từng lô: lich-su/lo/<mã>.txt (tiến độ đọc từ đây); nhat-ky.txt chung vẫn có, mỗi dòng kèm tiền tố "[<mã>] "."""
import datetime
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, ghi_json     # noqa: E402
import don_dep                                                         # noqa: E402
import suc_may                                                         # noqa: E402

RUN = {}                      # mã sản phẩm → {"proc", "bat_dau", "so_video", "log"}   (kể cả lô đã xong: proc.poll() != None)
_KHOA = threading.RLock()
NHIP_HANG_CHO_S = 5.0


def _ls():
    return HUB / "lich-su"


def f_hang():
    return _ls() / "hang-cho-lo.json"


def _an_toan(ma):
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(ma))


def f_log(ma):
    """Nhật ký riêng của lô sản phẩm `ma`."""
    return _ls() / "lo" / f"{_an_toan(ma)}.txt"


def _popen(cmd, **kw):
    """Chạy lô TÁCH khỏi job của tiến trình cha (launcher khởi động lại app thì lô đang làm KHÔNG chết theo). Job không cho tách → chạy bình thường."""
    co = kw.pop("creationflags", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.Popen(cmd, creationflags=co | 0x01000000, **kw)      # CREATE_BREAKAWAY_FROM_JOB
    except OSError:
        return subprocess.Popen(cmd, creationflags=co, **kw)


def spawn_mac_dinh(ma, so, lam_lai_f=None):
    """Bật tiến trình engine/sanxuat.py cho 1 lô. Trả Popen."""
    c = cfg_hub()
    cmd = [c["duong_dan"]["python"], "-X", "utf8", str(CODE / "engine" / "sanxuat.py"), ma] + (["--lam-lai", str(lam_lai_f)] if lam_lai_f else [str(so)])
    _ls().mkdir(parents=True, exist_ok=True)
    log = open(_ls() / "app-chay.log", "a", encoding="utf-8")
    try:
        return _popen(cmd, cwd=str(HUB), stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    finally:
        log.close()                               # tiến trình con đã giữ bản riêng của file nhật ký


# ---------------------------------------------------------------- lô đang chạy
def lo_dang_chay():
    """[{"ma","pid","bat_dau","so_video","proc","tu_app"}] mọi lô ĐANG chạy: tiến trình app bật (còn sống) + lô còn sống theo file khoá
    (app phiên trước, cửa sổ lệnh, khoá kiểu cũ). Không xoá gì."""
    out = {}
    with _KHOA:
        for ma, r in list(RUN.items()):
            p = r.get("proc")
            if p is not None and p.poll() is None:
                out[ma] = {"ma": ma, "pid": p.pid, "bat_dau": r.get("bat_dau"), "so_video": r.get("so_video") or 0, "proc": p, "tu_app": True}
    try:
        khoa = don_dep.cac_khoa_con_song()
    except Exception:
        khoa = []
    for d in khoa:
        ma = d.get("ma") or ""
        if ma in out:
            out[ma]["pid"] = d["pid"]
            continue
        out[ma] = {"ma": ma, "pid": d["pid"], "bat_dau": d.get("t0"), "so_video": 0, "proc": None, "tu_app": False}
    return list(out.values())


def dang_chay(ma=None):
    """ma=None: có BẤT KỲ lô nào đang chạy? Có mã: lô của đúng sản phẩm đó đang chạy?"""
    ds = lo_dang_chay()
    return any(r["ma"] == ma for r in ds) if ma else bool(ds)


def pid_lo(ma=None):
    """PID lô đang chạy (của sản phẩm `ma`, hoặc lô bất kỳ nếu không nêu mã); None nếu không có."""
    for r in lo_dang_chay():
        if not ma or r["ma"] == ma:
            return r["pid"]
    return None


def ma_thoat(ma):
    """Mã thoát của lô `ma` do app bật (None = chưa xong / không rõ)."""
    r = RUN.get(ma)
    return r["proc"].poll() if r and r.get("proc") is not None else None


def lo_gan_nhat():
    """Mã sản phẩm của lô bắt đầu gần nhất (đang chạy trước, không có thì lô app bật gần nhất); None nếu chưa có."""
    ds = [r for r in lo_dang_chay() if r.get("bat_dau")]
    if ds:
        return max(ds, key=lambda r: r["bat_dau"])["ma"]
    return max(RUN, key=lambda m: RUN[m].get("bat_dau") or 0) if RUN else None


# ---------------------------------------------------------------- nhật ký + tiến độ từng lô
def nhat_ky_lo(ma=None):
    """Các dòng nhật ký của lần chạy gần nhất (từ dòng BẮT ĐẦU cuối). Có mã: đọc nhật ký RIÊNG của lô; chưa có file riêng (lô bản cũ) → nhật ký chung."""
    f = f_log(ma) if ma else None
    if not f or not f.exists():
        f = _ls() / "nhat-ky.txt"
    if not f.exists():
        return []
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    idx = max([i for i, l in enumerate(lines) if "BẮT ĐẦU" in l] or [0])
    return lines[idx:][-400:]


def tien_do(lines, so_video=0):
    done, total, het = 0, 0, None
    for l in lines:
        m = re.search(r"\[(\d+)/(\d+)\]", l)
        if m:
            done, total = int(m.group(1)), int(m.group(2))
        m2 = re.search(r"BẮT ĐẦU.*?: (\d+) video", l)
        if m2:
            total = total or int(m2.group(1))
        if "HẾT HẠN MỨC" in l:
            het = l
    return {"xong": done, "tong": total or so_video, "het_han_muc": het, "da_xong": any("XONG:" in l for l in lines)}


def ten_sp(ma):
    try:
        sp = json.loads((HUB / "san-pham" / ma / "san-pham.json").read_text(encoding="utf-8"))
        return sp.get("ten_ngan") or sp.get("ten_goi") or ma
    except Exception:
        return ma


def tom_tat_cac_lo():
    """[{ma, ten, so_video, tien_do, bat_dau, dang_chay}] — lô đang chạy trước, rồi các lô app đã bật và vừa xong."""
    out, thay = [], set()
    for r in sorted(lo_dang_chay(), key=lambda r: r.get("bat_dau") or 0):
        td = tien_do(nhat_ky_lo(r["ma"]), r["so_video"])
        out.append({"ma": r["ma"], "ten": ten_sp(r["ma"]), "so_video": td["tong"] or r["so_video"], "tien_do": td, "bat_dau": r["bat_dau"], "dang_chay": True})
        thay.add(r["ma"])
    for ma, r in sorted(RUN.items(), key=lambda kv: kv[1].get("bat_dau") or 0):
        if ma in thay:
            continue
        td = tien_do(nhat_ky_lo(ma), r.get("so_video") or 0)
        out.append({"ma": ma, "ten": ten_sp(ma), "so_video": td["tong"] or r.get("so_video") or 0, "tien_do": td, "bat_dau": r.get("bat_dau"), "dang_chay": False})
    return out


# ---------------------------------------------------------------- hàng chờ (bền)
def hang_cho():
    """[{"ma","so","lam_lai"|None,"luc"}] theo thứ tự vào hàng (cũ nhất trước)."""
    try:
        d = json.loads(f_hang().read_text(encoding="utf-8")) if f_hang().exists() else []
        return [x for x in d if isinstance(x, dict) and x.get("ma")]
    except Exception:
        return []


def _luu_hang(ds):
    try:
        ghi_json(f_hang(), ds, indent=1)
    except OSError:
        pass


def xep_hang(ma, so, lam_lai_f=None):
    """Thêm vào cuối hàng chờ → vị trí (1 = kế tiếp). Đã có sản phẩm này trong hàng → None."""
    with _KHOA:
        ds = hang_cho()
        if any(x["ma"] == ma for x in ds):
            return None
        ds.append({"ma": ma, "so": int(so), "lam_lai": str(lam_lai_f) if lam_lai_f else None, "luc": time.time()})
        _luu_hang(ds)
        return len(ds)


def bo_hang(ma):
    """Bỏ sản phẩm khỏi hàng chờ → True nếu có."""
    with _KHOA:
        ds = hang_cho()
        con = [x for x in ds if x["ma"] != ma]
        if len(con) == len(ds):
            return False
        _luu_hang(con)
        return True


def vi_tri_hang(ma):
    for i, x in enumerate(hang_cho(), 1):
        if x["ma"] == ma:
            return i
    return None


# ---------------------------------------------------------------- bật lô / chờ chỗ
def con_cho(suc=None, so_dang=None):
    """(được bật thêm 1 lô?, lý do nếu không). Đủ N lô → không. Đã có lô khác chạy mà RAM trống < ngưỡng → không (lô đầu tiên luôn được)."""
    suc = suc or suc_may.suc_may()
    n = len(lo_dang_chay()) if so_dang is None else so_dang
    if n >= suc["lo_toi_da"]:
        return False, f"máy đang chạy {n}/{suc['lo_toi_da']} lô"
    if n >= 1 and suc["ram_trong_gb"] < suc_may.RAM_TRONG_BAT_DAU_LO_GB:
        return False, f"RAM trống chỉ {suc['ram_trong_gb']} GB (cần ≥ {suc_may.RAM_TRONG_BAT_DAU_LO_GB} GB)"
    return True, ""


def khoi_dong(ma, so, lam_lai_f=None, spawn=None):
    """Bật NGAY 1 lô (đã kiểm chỗ). Xoá nhật ký riêng cũ để tiến độ chỉ tính lô này. Trả thông tin RUN."""
    spawn = spawn or spawn_mac_dinh
    try:
        f = f_log(ma); f.parent.mkdir(parents=True, exist_ok=True); f.write_text("", encoding="utf-8")
    except OSError:
        pass
    proc = spawn(ma, so, lam_lai_f)
    with _KHOA:
        RUN[ma] = {"proc": proc, "bat_dau": time.time(), "so_video": int(so), "log": str(f_log(ma))}
    return RUN[ma]


def yeu_cau(ma, so, lam_lai_f=None, spawn=None):
    """Xin chạy 1 lô cho sản phẩm `ma`. → {"ok": False, "loi"} nếu CHÍNH sản phẩm này đang chạy / đang chờ;
    {"ok": True} nếu bật ngay; {"ok": True, "cho": vị trí} nếu phải xếp hàng (hết chỗ theo sức máy)."""
    with _KHOA:
        if dang_chay(ma):
            return {"ok": False, "loi": "Sản phẩm này đang có một lô chạy rồi (mỗi sản phẩm chỉ một lô một lúc)."}
        vt = xep_hang(ma, so, lam_lai_f)
        if vt is None:
            return {"ok": False, "loi": "Sản phẩm này đã nằm trong hàng chờ."}
        kich_hoat(spawn)
        vt = vi_tri_hang(ma)
        return {"ok": True} if vt is None else {"ok": True, "cho": vt}


def kich_hoat(spawn=None, log=print):
    """Bật các lô trong hàng chờ khi còn chỗ (FIFO; sản phẩm đang chạy thì để yên trong hàng). Trả danh sách mã vừa bật."""
    bat = []
    with _KHOA:
        for it in hang_cho():
            if dang_chay(it["ma"]):
                continue
            ok, _ = con_cho()
            if not ok:
                break
            bo_hang(it["ma"])
            try:
                khoi_dong(it["ma"], it["so"], it.get("lam_lai"), spawn)
                bat.append(it["ma"])
            except Exception as e:
                try:
                    log(f"Không bật được lô {it['ma']}: {type(e).__name__} {str(e)[:120]}")
                except Exception:
                    pass
    return bat


_LUONG = {"t": None}


def bat_dau_hang_cho(spawn=None, nhip=NHIP_HANG_CHO_S):
    """Luồng nền: mỗi vài giây bật lô kế trong hàng chờ nếu đã có chỗ. Gọi 1 lần lúc app khởi động (queue đọc lại từ file nên không mất)."""
    if _LUONG["t"] and _LUONG["t"].is_alive():
        return _LUONG["t"]

    def vong():
        while True:
            try:
                if hang_cho():
                    kich_hoat(spawn)
            except Exception:
                pass
            time.sleep(nhip)
    _LUONG["t"] = threading.Thread(target=vong, daemon=True, name="hang-cho-lo")
    _LUONG["t"].start()
    return _LUONG["t"]


# ---------------------------------------------------------------- dừng
def _giet(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


def _ghi_dung(ma):
    try:
        from su_kien import noi_them
        dong = f"[{datetime.datetime.now():%H:%M:%S}] ⏹ Anh đã bấm DỪNG. Video đã xong vẫn giữ nguyên.\n"
        noi_them(f_log(ma), dong, giu_dong=3000, toi_da_byte=400_000)
        noi_them(_ls() / "nhat-ky.txt", dong.replace("] ⏹", f"] [{ma}] ⏹", 1), giu_dong=8000, toi_da_byte=1_500_000)
    except Exception:
        pass


def dung_mot(ma, giet=None):
    """Dừng lô của sản phẩm `ma` (hoặc bỏ khỏi hàng chờ). → {"ok": True, "con_chay": True?, "huy_hang": True?}"""
    giet = giet or _giet
    huy = bo_hang(ma)
    pid = pid_lo(ma)
    if not pid:
        return {"ok": True, "huy_hang": True} if huy else {"ok": True}
    giet(pid)
    _ghi_dung(ma)
    for _ in range(20):                    # chờ tiến trình thật sự tắt rồi mới xoá khoá (lô bị kill -F không kịp tự xoá)
        if not _con_song(ma, pid):
            break
        time.sleep(0.25)
    else:
        return {"ok": True, "con_chay": True}          # vẫn chưa tắt → giữ khoá
    for ma_k, f in don_dep.cac_f_khoa():              # xoá khoá của lô vừa dừng (khoá riêng; hoặc khoá kiểu cũ ghi đúng mã này)
        d = don_dep.doc_khoa(f)
        if ma_k == ma or (ma_k is None and d and d.get("ma") == ma):
            don_dep.nha_khoa_lo(None, f)
    return {"ok": True}


def _con_song(ma, pid):
    with _KHOA:
        p = (RUN.get(ma) or {}).get("proc")
    if p is not None and p.pid == pid:
        return p.poll() is None
    from duong_dan import pid_la_lo_sx
    return pid_la_lo_sx(pid)


def dung_tat_ca(giet=None):
    """Xoá cả hàng chờ rồi dừng mọi lô đang chạy."""
    with _KHOA:
        _luu_hang([])
    con = False
    for r in lo_dang_chay():
        kq = dung_mot(r["ma"], giet)
        con = con or bool(kq.get("con_chay"))
    return {"ok": True, "con_chay": True} if con else {"ok": True}
