"""LUỒNG TIN TỨC THÌ (SSE) cho trang "Khu Tự Trị": hub đẩy tin khi có việc mới, trình duyệt khỏi hỏi dồn.

Một "bộ phát" trung tâm (class Phat) giữ phiên bản tăng dần + Condition. Các kết nối SSE chỉ CHỜ trên condition,
không ai tự quét đĩa. Một thread nền duy nhất ("canh") tính lại ảnh chụp {n, cho_duyet, chay} mỗi khi có gợi ý
(watchdog báo file đổi, hoặc nhịp dự phòng) và chỉ phát khi ảnh chụp THAY ĐỔI.

Nguồn gợi ý: sổ sự kiện su-kien.jsonl (engine chạy tiến trình khác nên canh file), danh-gia.json, dang-chay.lock,
và thư mục kho ra/ (video .mp4 mới). Có `watchdog` thì dùng ReadDirectoryChangesW (không poll); chưa cài thì
một nhịp nhẹ so mtime mỗi 2 giây (chỉ stat vài đường dẫn)."""
import json
import os
import threading
import time
from pathlib import Path

try:                                         # import có bảo vệ: thiếu watchdog vẫn chạy (rơi về so mtime)
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    CO_WATCHDOG = True
except Exception:                            # pragma: no cover - tuỳ môi trường
    FileSystemEventHandler = object
    Observer = None
    CO_WATCHDOG = False

TOI_DA_KET_NOI = 8
PING_GIAY = 15
GOP_GIAY = 0.3              # gộp nhiều thay đổi dồn dập thành 1 lần tính
NHIP_DU_PHONG = 2.0         # không có watchdog: so mtime mỗi 2 giây
NHIP_AN_TOAN = 5.0          # có watchdog: vẫn tính lại thưa (bắt việc không ghi file, vd lô tự thoát)
FILE_THEO_DOI = ("su-kien.jsonl", "danh-gia.json", "dang-chay.lock")


def n_cuoi(f):
    """Số thứ tự `n` của sự kiện cuối trong sổ (đọc đuôi file, rẻ). Không có / lỗi → 0."""
    try:
        f = Path(f)
        if not f.exists():
            return 0
        with open(f, "rb") as fh:
            size = fh.seek(0, os.SEEK_END)
            fh.seek(max(0, size - 8192))
            cuoi = fh.read().decode("utf-8", errors="replace").splitlines()
        for l in reversed(cuoi):
            try:
                e = json.loads(l)
            except Exception:
                continue
            if isinstance(e, dict):
                return int(e.get("n", 0))
    except Exception:
        pass
    return 0


class Phat:
    """Bộ phát trung tâm. `tinh()` trả dict ảnh chụp; `theo_doi` = danh sách đường dẫn để canh (file hoặc thư mục);
    `loc_kho(path)` cho biết đường dẫn trong kho ra/ có đáng kể không; `bam()` được gọi khi có gợi ý (vd vô hiệu đệm)."""

    def __init__(self, tinh, thu_muc_ra=None, thu_muc_ls=None, bam=None, dung_watchdog=True, toi_da=TOI_DA_KET_NOI):
        self.tinh = tinh
        self.ra = Path(thu_muc_ra) if thu_muc_ra else None
        self.ls = Path(thu_muc_ls) if thu_muc_ls else None
        self.bam = bam
        self.dung_watchdog = dung_watchdog and CO_WATCHDOG
        self.toi_da = toi_da
        self.cond = threading.Condition()
        self.ver = 0
        self.anh = None
        self._dang = 0
        self._ban = threading.Event()        # có gợi ý chờ xử lý
        self._dung = threading.Event()
        self._obs = None
        self._thread = None
        self._mtime = None

    # ---- kết nối SSE
    def vao(self):
        """Xin 1 chỗ cho kết nối SSE mới. Hết chỗ → False."""
        with self.cond:
            if self._dang >= self.toi_da:
                return False
            self._dang += 1
            return True

    def ra_khoi(self):
        with self.cond:
            self._dang = max(0, self._dang - 1)

    @property
    def so_ket_noi(self):
        return self._dang

    def hien_tai(self):
        with self.cond:
            return self.ver, self.anh

    def cho(self, da_thay, timeout=PING_GIAY):
        """Chờ phiên bản mới hơn `da_thay`; hết `timeout` mà chưa có → trả (da_thay, None) để gửi ping."""
        with self.cond:
            self.cond.wait_for(lambda: self.ver != da_thay or self._dung.is_set(), timeout)
            if self.ver != da_thay:
                return self.ver, self.anh
            return da_thay, None

    # ---- phát
    def _tinh_va_phat(self):
        try:
            anh = self.tinh()
        except Exception:
            return False
        with self.cond:
            if anh == self.anh:
                return False
            self.anh = anh
            self.ver += 1
            self.cond.notify_all()
        return True

    def goi_y(self):
        """Có thể có thay đổi (watchdog / ghi trong tiến trình hub gọi cái này)."""
        if self.bam:
            try:
                self.bam()
            except Exception:
                pass
        self._ban.set()

    # ---- canh
    def _chu_ky_mtime(self):
        """Dự phòng khi không có watchdog: chỉ stat vài đường dẫn."""
        ds = []
        if self.ls:
            for t in FILE_THEO_DOI:
                p = self.ls / t
                try:
                    st = p.stat()
                    ds.append((t, st.st_mtime_ns, st.st_size))
                except OSError:
                    ds.append((t, 0, 0))
        if self.ra:
            try:
                ds.append(("ra", tuple(sorted((x.name, x.stat().st_mtime_ns) for x in self.ra.iterdir() if x.is_dir()))))
            except OSError:
                ds.append(("ra", ()))
        return tuple(ds)

    def _vong(self):
        self._tinh_va_phat()
        self._mtime = self._chu_ky_mtime()
        nhip = NHIP_AN_TOAN if self._obs else NHIP_DU_PHONG
        while not self._dung.is_set():
            co = self._ban.wait(nhip)
            if self._dung.is_set():
                break
            if co:
                self._dung.wait(GOP_GIAY)    # gộp các thay đổi dồn dập
                self._ban.clear()
                self._tinh_va_phat()
                continue
            if self._obs is None:            # không có watchdog: nhịp này là lúc so mtime
                m = self._chu_ky_mtime()
                if m != self._mtime:
                    self._mtime = m
                    if self.bam:
                        try:
                            self.bam()
                        except Exception:
                            pass
                    self._tinh_va_phat()
            else:                            # có watchdog: nhịp an toàn, tính lại thưa
                self._tinh_va_phat()

    def _bat_watchdog(self):
        phat = self

        class Nghe(FileSystemEventHandler):
            def __init__(self, loai):
                self.loai = loai

            def on_any_event(self, ev):
                try:
                    ds = [getattr(ev, "src_path", ""), getattr(ev, "dest_path", "")]
                    ds = [os.fsdecode(d) for d in ds if d]
                    if self.loai == "ls":
                        ok = any(Path(d).name in FILE_THEO_DOI for d in ds)
                    else:
                        ok = ev.is_directory or any(d.lower().endswith(".mp4") and not d.lower().endswith(".part.mp4") for d in ds)
                    if ok:
                        phat.goi_y()
                except Exception:
                    pass

        obs = Observer()
        n = 0
        if self.ls and self.ls.exists():
            obs.schedule(Nghe("ls"), str(self.ls), recursive=False); n += 1
        if self.ra and self.ra.exists():
            obs.schedule(Nghe("ra"), str(self.ra), recursive=True); n += 1
        if not n:
            return None
        obs.daemon = True
        obs.start()
        return obs

    def bat_dau(self):
        if self._thread:
            return
        if self.dung_watchdog:
            try:
                self._obs = self._bat_watchdog()
            except Exception:
                self._obs = None
        self._thread = threading.Thread(target=self._vong, daemon=True, name="luong-canh")
        self._thread.start()

    def dung(self):
        self._dung.set()
        self._ban.set()
        with self.cond:
            self.cond.notify_all()
        if self._obs:
            try:
                self._obs.stop()
            except Exception:
                pass


def khung_sse(anh):
    """Một bản tin `event: doi` dạng SSE."""
    return ("event: doi\ndata: " + json.dumps(anh, ensure_ascii=False) + "\n\n").encode("utf-8")


PING = b": ping\n\n"
