"""Sổ sự kiện có cấu trúc của xưởng (mỗi dòng 1 JSON) -> <DATA>/lich-su/su-kien.jsonl.
Trang "Khu Tự Trị" đọc sổ này để biết vai nào đang làm gì. Ghi lỗi KHÔNG BAO GIỜ làm hỏng việc sản xuất.

Mỗi sự kiện: n (số thứ tự tăng dần, dùng làm con trỏ `sau`), t (ISO giờ), vai, loai, video, msg, và các trường thêm (diem, dat, so...).
vai : he-thong | bien-kich | giong | dao-dien | dung | giam-khao | kho
loai: bat-dau-lo | bat-dau | xong | diem | dung-lai | luu | het-han-muc | loi | hoc | ket-thuc-lo"""
import datetime, json, os, threading, time
from pathlib import Path

GIU = 2000            # giữ tối đa ngần ấy dòng cuối
DU = 400              # vượt GIU + DU dòng mới cắt (đỡ ghi lại file liên tục)
BYTE = 400_000        # chỉ đếm dòng khi file lớn hơn mức này
_khoa = threading.Lock()
_cuoi = [0]


# ---------------------------------------------------------------- ghi sổ an toàn + khoá file giữa các tiến trình (dùng chung cho các file lịch sử)
_khoa_ghi = threading.Lock()
_khoa_luong = {}


def dong_csv(hang):
    """1 hàng CSV → chuỗi kết thúc \\r\\n (để đưa cho noi_them)."""
    import csv, io
    b = io.StringIO(); csv.writer(b).writerow(hang)
    return b.getvalue()


def _cat_dong(f, giu, toi_da_byte, ma_hoa, giu_dau):
    """File dài quá toi_da_byte → chỉ giữ `giu` dòng cuối (và dòng tiêu đề nếu giu_dau). Lỗi → bỏ qua, lần sau cắt tiếp."""
    try:
        if f.stat().st_size <= toi_da_byte:
            return
        ds = f.read_text(encoding="utf-8-sig", errors="replace").splitlines(keepends=True)
        dau = ds[:1] if giu_dau else []
        tam = f.with_name(f.name + ".cat.tmp")
        tam.write_text("".join(dau + ds[len(dau):][-giu:]), encoding=ma_hoa, newline="")
        os.replace(tam, f)
    except Exception:
        pass


def noi_them(f, noi_dung, ma_hoa="utf-8", dau=None, thu=4, doi=0.3, giu_dong=None, toi_da_byte=None):
    """Ghi NỐI `noi_dung` (chuỗi, tự kèm xuống dòng) vào file f — KHÔNG BAO GIỜ ném lỗi vào dây chuyền sản xuất.
    File đang bị khoá (Excel mở bảng, quét virus...) → thử lại `thu` lần cách nhau `doi` s, vẫn không được thì ghi tạm vào
    <tên>.cho-ghi và lần ghi thành công kế tiếp sẽ gộp file đó vào trước. dau: dòng tiêu đề khi file chưa có/trống (đặt trong khoá,
    không bị 2 luồng ghi trùng). giu_dong + toi_da_byte: file quá toi_da_byte → giữ giu_dong dòng cuối. Trả True nếu ghi thẳng được."""
    f = Path(f); cho = f.with_name(f.name + ".cho-ghi")
    if not noi_dung and not cho.exists():
        return True                                     # không có gì để ghi / gộp
    try:
        with _khoa_ghi:
            for lan in range(max(1, thu)):
                try:
                    f.parent.mkdir(parents=True, exist_ok=True)
                    moi = (not f.exists()) or f.stat().st_size == 0
                    ton = cho.read_bytes().decode("utf-8", errors="replace") if cho.exists() else ""
                    with open(f, "a", encoding=ma_hoa, newline="") as fh:
                        if moi and dau:
                            fh.write(dau)
                        fh.write(ton + noi_dung)
                    if ton:
                        try:
                            cho.unlink()
                        except OSError:
                            pass
                    if giu_dong and toi_da_byte:
                        _cat_dong(f, giu_dong, toi_da_byte, ma_hoa, bool(dau))
                    return True
                except OSError:
                    if lan < thu - 1:
                        time.sleep(doi)
    except Exception:
        pass
    try:
        with open(cho, "a", encoding="utf-8", newline="") as fh:
            fh.write(noi_dung)
    except Exception:
        pass
    return False


class khoa_tep:
    """Khoá HĐH (msvcrt.locking / flock trên file <f>.lock) + khoá luồng: đọc-sửa-ghi file dùng chung giữa NHIỀU TIẾN TRÌNH
    (app + lô sản xuất) không đè nhau. `with khoa_tep(f, cho=10):` — quá `cho` giây chưa lấy được → TimeoutError."""
    def __init__(self, f, cho=10.0):
        f = Path(f); self.lf = f.with_name(f.name + ".lock"); self.cho = cho; self.fd = None; self.lk = None

    def _os(self, khoa):
        if os.name == "nt":
            import msvcrt
            os.lseek(self.fd, 0, 0); msvcrt.locking(self.fd, msvcrt.LK_NBLCK if khoa else msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.fd, (fcntl.LOCK_EX | fcntl.LOCK_NB) if khoa else fcntl.LOCK_UN)

    def __enter__(self):
        het = time.time() + self.cho
        with _khoa_ghi:
            self.lk = _khoa_luong.setdefault(str(self.lf), threading.RLock())
        if not self.lk.acquire(timeout=self.cho):
            raise TimeoutError(f"không lấy được khoá {self.lf.name}")
        try:
            self.lf.parent.mkdir(parents=True, exist_ok=True)
            self.fd = os.open(str(self.lf), os.O_RDWR | os.O_CREAT)
            if os.fstat(self.fd).st_size == 0:
                os.write(self.fd, b"0")
            while True:
                try:
                    self._os(True); break
                except OSError:
                    if time.time() > het:
                        raise TimeoutError(f"không lấy được khoá {self.lf.name}")
                    time.sleep(0.05)
        except BaseException:
            self._nha()
            raise
        return self

    def _nha(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
        if self.lk is not None:
            self.lk.release(); self.lk = None

    def __exit__(self, *a):
        if self.fd is not None:
            try:
                self._os(False)
            except OSError:
                pass
        self._nha()


def _file():
    from duong_dan import DATA
    return Path(DATA) / "lich-su" / "su-kien.jsonl"


def _cat(f):
    ds = f.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(ds) <= GIU + DU:
        return
    tam = f.with_name(f.name + ".tmp")
    tam.write_text("\n".join(ds[-GIU:]) + "\n", encoding="utf-8")
    os.replace(tam, f)


def ghi(vai, loai, msg="", video=None, f=None, **them):
    """Ghi 1 sự kiện. Nuốt mọi lỗi."""
    try:
        f = Path(f) if f else _file()
        with _khoa:
            n = max(_cuoi[0] + 1, time.time_ns() // 1000)
            _cuoi[0] = n
            ev = {"n": n, "t": datetime.datetime.now().isoformat(timespec="seconds"), "vai": vai, "loai": loai}
            if video:
                ev["video"] = str(video)
            if msg:
                ev["msg"] = str(msg)[:200]
            ev.update({k: v for k, v in them.items() if v is not None})
            f.parent.mkdir(parents=True, exist_ok=True)
            with open(f, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
            if f.stat().st_size > BYTE:           # kiểm kích thước rẻ trước khi đếm dòng
                _cat(f)
    except Exception:
        pass


def doc(sau=0, toi_da=300, f=None):
    """Sự kiện có n > sau (tối đa `toi_da` cái cuối). Không bao giờ ném lỗi."""
    try:
        f = Path(f) if f else _file()
        if not f.exists():
            return []
        out = []
        for l in f.read_text(encoding="utf-8", errors="replace").splitlines()[-GIU:]:
            try:
                e = json.loads(l)
            except Exception:
                continue
            if isinstance(e, dict) and int(e.get("n", 0)) > int(sau or 0):
                out.append(e)
        return out[-toi_da:]
    except Exception:
        return []
