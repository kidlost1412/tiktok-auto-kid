"""SỨC MÁY: máy này chạy được mấy lô sản xuất cùng lúc, và mấy khâu dựng nặng (FFmpeg / Remotion) cùng một lúc.

Hai con số, tính từ RAM (chỉnh các hằng số ngay dưới đây nếu máy khách khác):
  khe_dung K = số "khe dựng" TOÀN MÁY (khâu dựng FFmpeg hoặc Remotion của MỌI lô chung nhau K khe) = clamp(floor((RAM − RESERVE_GB) / RENDER_GB), 1, TRAN_KHE)
  lo_toi_da N = số lô chạy song song tối đa = clamp(K + 1, 1, TRAN_LO)   (khâu Claude / giọng chỉ chờ mạng, không tốn RAM; chỉ khâu dựng mới nặng)
Cấu hình đè (config.json): "lo": {"song_song": "tu_dong" | số, "khe_dung": "tu_dong" | số}.

Khe dựng là file khoá lich-su/khe-dung/khe-<i>.lock (cùng cách khoá + kiểm tiến trình còn sống như khoá lô, xem don_dep): lô nào chết giữa chừng
thì khe của nó tự được thu hồi. Một lô luôn được khe đầu tiên khi chưa ai giữ khe (không bao giờ kẹt); các khe sau chỉ cấp khi RAM trống còn đủ.

Trong 1 khe, 1 lô dựng bao nhiêu video FFmpeg song song: xem song_song_ffmpeg() (RAM < 20 GB → 1, còn lại 2)."""
import ctypes
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from duong_dan import DATA as HUB, cfg_tho                      # noqa: E402

# ---- hằng số chỉnh được -------------------------------------------------------------------------------------------------
RENDER_GB = 3.0               # 1 khe dựng ăn khoảng ngần này RAM (đo cả lô: đỉnh 3,2 GB ở bước ghép FFmpeg cuối, ~1,8 GB lúc Remotion)
RESERVE_GB = 8.0              # phần RAM chừa cho Windows + app + trình duyệt + các chương trình khác của người dùng
TRAN_KHE = 4                  # tối đa bao nhiêu khe dựng
TRAN_LO = 4                   # tối đa bao nhiêu lô cùng lúc
RAM_CAN_THEM_GB = 0.5         # cấp thêm 1 khe (khi đã có khe đang bị giữ) cần RAM trống ≥ RENDER_GB + ngần này
RAM_TRONG_BAT_DAU_LO_GB = 3.0     # bắt đầu 1 lô mới (khi đã có lô khác đang chạy) cần RAM trống ≥ ngần này
NGUONG_FFMPEG_2_GB = 12.0     # RAM tổng < ngưỡng này → mỗi khe 1 video FFmpeg; đo 14/11 trên máy 16 GB: 2 video song song đỉnh 3,2 GB = RENDER_GB
NHIP_CHO_KHE_S = 3.0          # nhịp thử lại khi chờ khe
CHO_KHE_TOI_DA_S = 3600       # chờ khe quá lâu (khe bị giữ quá 1 giờ liền) → cứ dựng, không để lô kẹt vô hạn


def _kep(x, lo, hi):
    return max(lo, min(hi, x))


def doc_ram_gb():
    """(RAM tổng GB, RAM còn trống GB). Windows: GlobalMemoryStatusEx; HĐH khác: sysconf; không đọc được → (16.0, 8.0)."""
    try:
        if os.name == "nt":
            class MEM(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MEM(); m.dwLength = ctypes.sizeof(MEM)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return m.ullTotalPhys / 2 ** 30, m.ullAvailPhys / 2 ** 30
        else:
            tong = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            trong = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES")
            return tong / 2 ** 30, trong / 2 ** 30
    except Exception:
        pass
    return 16.0, 8.0


def ram_trong_gb():
    return doc_ram_gb()[1]


def _so(v, mac_dinh, lo=1, hi=8):
    """Giá trị cấu hình: "tu_dong"/trống/sai → mac_dinh; số → kẹp trong [lo, hi]."""
    if v in (None, "", "tu_dong"):
        return mac_dinh
    try:
        return _kep(int(v), lo, hi)
    except (TypeError, ValueError):
        return mac_dinh


def suc_may(ram_gb=None, ram_trong=None, cau_hinh=None):
    """→ {"ram_gb": tổng, "ram_trong_gb": còn trống, "lo_toi_da": N, "khe_dung": K}. Tham số chỉ để test (ram_gb/ram_trong: GB; cau_hinh: dict "lo")."""
    tong, trong = doc_ram_gb()
    tong = tong if ram_gb is None else float(ram_gb)
    trong = trong if ram_trong is None else float(ram_trong)
    if cau_hinh is None:
        try:
            cau_hinh = cfg_tho().get("lo") or {}
        except Exception:
            cau_hinh = {}
    k_tu_dong = _kep(int((tong - RESERVE_GB) // RENDER_GB), 1, TRAN_KHE)
    k = _so(cau_hinh.get("khe_dung"), k_tu_dong)
    n = _so(cau_hinh.get("song_song"), _kep(k + 1, 1, TRAN_LO))
    return {"ram_gb": round(tong, 1), "ram_trong_gb": round(trong, 1), "lo_toi_da": n, "khe_dung": k}


def song_song_ffmpeg(ram_gb=None):
    """Số video FFmpeg 1 lô dựng song song trong khe của nó: RAM < 20 GB → 1, ngược lại 2 (trước đây luôn 2 cho máy 16 GB chạy 1 lô)."""
    tong = doc_ram_gb()[0] if ram_gb is None else float(ram_gb)
    return 1 if tong < NGUONG_FFMPEG_2_GB else 2


# ---------------------------------------------------------------- khe dựng (semaphore giữa các tiến trình)
def thu_muc_khe():
    return HUB / "lich-su" / "khe-dung"


def _f_khe(i):
    return thu_muc_khe() / f"khe-{i}.lock"


def khe_dang_giu():
    """[{"pid","ma","f"}] các khe đang bị lô CÒN SỐNG giữ (khe của tiến trình đã chết không tính)."""
    from don_dep import khoa_con_song
    out = []
    try:
        fs = sorted(thu_muc_khe().glob("khe-*.lock"))
    except OSError:
        return out
    for f in fs:
        if f.name.endswith(".lock.lock"):              # file phụ của khoa_tep
            continue
        d = khoa_con_song(f)
        if d:
            out.append(dict(d, f=f))
    return out


def lay_khe(ma, k=None, ram_trong=None):
    """Thử lấy 1 khe NGAY (không chờ). → (token, file khe) hoặc None. Khe đã có người giữ thì thôi; khe cũ (người giữ chết) tự được thu hồi.
    Đã có khe khác đang bị giữ mà RAM trống < RENDER_GB + RAM_CAN_THEM_GB → không cấp (khe đầu tiên luôn cấp)."""
    from don_dep import lay_khoa_lo
    k = suc_may()["khe_dung"] if k is None else k
    if khe_dang_giu():
        trong = ram_trong_gb() if ram_trong is None else float(ram_trong)
        if trong < RENDER_GB + RAM_CAN_THEM_GB:
            return None
    for i in range(k):
        tok = lay_khoa_lo(ma, _f_khe(i))
        if tok:
            return tok, _f_khe(i)
    return None


def nha_khe(tt):
    from don_dep import nha_khoa_lo
    if tt:
        nha_khoa_lo(tt[0], tt[1])


class khe_dung:
    """`with khe_dung(ma, log, "FFmpeg"):` — chờ tới khi lấy được 1 trong K khe dựng của máy rồi mới chạy khâu nặng; nhả khi ra khỏi khối.
    Khi phải chờ: ghi 1 lần "⏳ Chờ khe dựng (máy đang dựng N lô)"."""
    def __init__(self, ma, log=None, buoc="", k=None, nhip=NHIP_CHO_KHE_S, cho_toi_da=CHO_KHE_TOI_DA_S):
        self.ma, self.log, self.buoc, self.k, self.nhip, self.cho_toi_da, self.tt = ma, log or (lambda *_: None), buoc, k, nhip, cho_toi_da, None

    def __enter__(self):
        het = time.time() + self.cho_toi_da; da_bao = False
        while True:
            try:
                self.tt = lay_khe(self.ma, self.k)
            except Exception as e:                      # khoá hỏng bất thường: không để lô kẹt vì cơ chế điều phối
                self.log(f"  (khe dựng lỗi: {type(e).__name__} {str(e)[:80]} → cứ dựng)")
                return self
            if self.tt:
                if da_bao:
                    self.log(f"  ▶ Đã có khe dựng ({self.buoc})")
                return self
            if time.time() > het:
                self.log("  ⚠ Chờ khe dựng quá lâu → cứ dựng (khe bị giữ liền hơn 1 giờ)")
                return self
            if not da_bao:
                da_bao = True
                self.log(f"⏳ Chờ khe dựng (máy đang dựng {max(1, len({d['pid'] for d in khe_dang_giu()}))} lô)")
            time.sleep(self.nhip + random.random() * 0.5)

    def __exit__(self, *a):
        nha_khe(self.tt); self.tt = None
