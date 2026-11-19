"""TRỰC TIẾP cho trang "Khu Tự Trị": engine ghi các file nhỏ <DATA>/lich-su/truc-tiep/<vai>-<mã>.json — mỗi việc đang chạy một file —
để trang web thấy ĐÚNG dữ liệu thật đang về (câu Claude đang viết, điểm giám khảo, giọng đang thu...) thay vì tóm tắt sau cùng.

Dùng:
    with truc_tiep.viec("bien-kich", "Đang viết lời đọc", sp="Nano Đồng", buoc="Bài 0/5") as tt:
        tt.cap(buoc="Bài 1/5"); tt.them_dong("Chốt: Vườn cà phê cần phun"); tt.chu(delta_text); tt.nghi(delta_thinking)
Việc mở trong luồng nào thì là "việc hiện tại" của luồng đó (hien_tai()) — ai.goi() gắn chữ Claude đang stream vào đó; không có việc nào
thì ai.goi() tự mở một việc theo vai.

Quy tắc (hợp đồng tt-contract): chuỗi đã là tiếng người (không JSON thô/đường dẫn/khoá), ≤ 300 ký tự, dòng ≤ 200; ghi nguyên tử
(file tạm + os.replace), ≥ 1,2 s giữa hai lần ghi của cùng một việc (luôn ghi lúc bắt đầu và kết thúc); file quá 10 phút không cập nhật bị xoá;
việc xong giữ ~60 s rồi xoá. MỌI lỗi ghi file đều bị nuốt — không bao giờ làm hỏng việc sản xuất. Tắt hẳn bằng config "truc_tiep": false."""
import atexit, json, os, re, secrets, threading, time
from pathlib import Path

TEN_THU_MUC = "truc-tiep"
HAN_GIAY = 600.0          # quá ngần này không cập nhật → coi như chết, xoá
GIU_XONG_GIAY = 60.0      # việc xong giữ ngần này để giao diện kịp hiện đoạn kết
GIAN_CACH = 1.2           # tối thiểu giữa 2 lần ghi file của cùng 1 việc
NHIP_GIAY = 5.0           # việc dài không có chữ mới vẫn "đập tim": ghi lại cap_nhat mỗi ~5 s
TOI_DA_DONG = 8
DONG_TOI_DA = 200
CHUOI_TOI_DA = 300
SUY_NGHI_TOI_DA = 240
MIN_CAU = 12              # câu ngắn hơn ghép với câu sau cho đủ "dòng"

_THU_MUC = None           # để test đặt thư mục tạm (None → <DATA>/lich-su/truc-tiep)
_TL = threading.local()   # ngăn xếp việc đang mở của luồng này
_MO = set()               # mọi việc đang mở trong tiến trình (atexit đóng nốt)
_KHOA_MO = threading.Lock()
_don_cuoi = [0.0]


def thu_muc():
    if _THU_MUC:
        return Path(_THU_MUC)
    from duong_dan import DATA
    return Path(DATA) / "lich-su" / TEN_THU_MUC


def dang_bat():
    """Công tắc config "truc_tiep" (mặc định bật)."""
    try:
        from duong_dan import cfg_tho
        return bool(cfg_tho().get("truc_tiep", True))
    except Exception:
        return True


# ---------------------------------------------------------------- làm sạch chuỗi
_RE_DUONG_FILE = re.compile(r"[A-Za-z]:[\\/][^\s\"'<>|]+")
_RE_URL = re.compile(r"https?://\S+", re.I)
_RE_KHOA = re.compile(r"\b(?:sk|pk|key|tok)[-_][A-Za-z0-9_\-]{16,}")


def _an_toan(s):
    """Không để lọt đường dẫn máy / đường link / khoá vào dữ liệu hiện lên màn hình."""
    s = _RE_DUONG_FILE.sub("…", s)
    s = _RE_URL.sub("…", s)
    return _RE_KHOA.sub("…", s)


def _gon(s, toi_da=CHUOI_TOI_DA):
    s = _an_toan(re.sub(r"\s+", " ", str(s)).strip())
    return s if len(s) <= toi_da else s[:toi_da - 1].rsplit(" ", 1)[0].rstrip(",;:–- ") + "…"


def _chi_tiet_sach(d):
    out = {}
    for k, v in (d or {}).items():
        k = str(k)[:40]
        if isinstance(v, bool) or v is None or isinstance(v, (int, float)):
            out[k] = v
        elif isinstance(v, str):
            out[k] = _gon(v, 120)
    return out


# ---------------------------------------------------------------- bóc "dòng người đọc được" từ chữ model đang stream
_RE_THE = re.compile(r"\[[^\]]*\]")
_RE_THE_DO = re.compile(r"\[[^\]]*$")
_RE_CAU = re.compile(r"[.!?…]+[\"')\]”’]*\s+")
_RE_DAU_DONG = re.compile(r"^\s*(?:[-*•–]+|\d+[.)])\s+")
_RE_DUONG = re.compile(r"^(?:[A-Za-z]:)?[\\/]|^~[\\/]|^\.{1,2}[\\/]")
_RE_BAT_DAU_JSON = re.compile(r"^\s*(?:\{|\[\s*[\[{\"])")


def la_van_xuoi(s):
    """Chuỗi có giống LỜI người đọc được không (không phải mã, đường dẫn, link, khoá snake_case, hex, hashtag...)."""
    s = (s or "").strip()
    if len(s) < MIN_CAU or s[0] in "{[<":
        return False
    if re.search(r"https?://|www\.", s, re.I) or _RE_DUONG.match(s):
        return False
    tu = s.split()
    if len(tu) < 2:
        return False
    chu = sum(1 for c in s if c.isalpha())
    if chu < 6 or chu / len(s) < 0.5:
        return False
    if all(w.startswith("#") for w in tu) or re.fullmatch(r"[0-9a-fA-F\- ]+", s):
        return False
    if sum(1 for w in tu if "_" in w or "/" in w) * 2 > len(tu):
        return False
    return True


def giai_ma(raw):
    """Nội dung chuỗi JSON (chưa có dấu ngoặc kép, còn nguyên \\-escape, có thể dở dang) → chữ thật. Escape dở ở cuối thì bỏ."""
    out, i, n = [], 0, len(raw)
    ma = {"n": "\n", "t": " ", "r": "", "b": "", "f": "", '"': '"', "\\": "\\", "/": "/"}
    while i < n:
        c = raw[i]
        if c != "\\":
            out.append(c); i += 1; continue
        if i + 1 >= n:
            break
        e = raw[i + 1]
        if e == "u":
            h = raw[i + 2:i + 6]
            if len(h) < 4:
                break
            try:
                cp = int(h, 16)
            except ValueError:
                out.append("�"); i += 6; continue
            if 0xD800 <= cp < 0xDC00:                       # cặp thay thế (emoji...)
                nua = raw[i + 6:i + 12]
                if len(nua) < 6 and "\\u".startswith(nua[:2]):
                    break                                    # nửa sau chưa tới (đang stream dở)
                try:
                    lo = int(nua[2:6], 16) if nua[:2] == "\\u" and len(nua) == 6 else -1
                except ValueError:
                    lo = -1
                if 0xDC00 <= lo < 0xE000:
                    out.append(chr(0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00))); i += 12; continue
                out.append("�"); i += 6; continue
            out.append(chr(cp)); i += 6; continue
        out.append(ma.get(e, e)); i += 2
    return "".join(out)


def _bo_the(s):
    """Bỏ thẻ [giọng ấm] của lời đọc (kể cả thẻ gõ dở ở cuối), gộp khoảng trắng."""
    s = _RE_THE_DO.sub("", _RE_THE.sub("", s))
    return re.sub(r"\s+", " ", s)


def _chia_dai(cau, toi_da=DONG_TOI_DA):
    """Câu dài hơn `toi_da` → cắt ở dấu phẩy/khoảng trắng gần nhất."""
    cau = cau.strip()
    while len(cau) > toi_da:
        i = max(cau.rfind(", ", 0, toi_da), cau.rfind("; ", 0, toi_da), cau.rfind(": ", 0, toi_da))
        if i < toi_da // 3:
            i = cau.rfind(" ", 0, toi_da)
        if i <= 0:
            i = toi_da
        yield cau[:i + 1].strip()
        cau = cau[i + 1:].strip()
    if cau:
        yield cau


class TrichDong:
    """Nhận từng mảnh chữ model (delta) → dòng đầy đủ (lấy bằng lay_moi()) + câu đang gõ (`dang_go`).
    · Chữ JSON (kịch bản, bảng dựng, kết luận giám khảo): chỉ lấy GIÁ TRỊ chuỗi giống lời (bỏ khoá, mã, đường dẫn, số); chuỗi dài tách theo câu,
      câu xong chuyển vào dong NGAY khi gặp dấu chấm chứ không đợi hết chuỗi; chuỗi đang gõ dở = dang_go.
    · Chữ thường (không phải JSON): tách theo dòng + câu. Dòng nào bắt đầu bằng { hoặc [" thì từ đó chuyển sang đọc JSON (kể cả khi bọc ```json).
    Không bao giờ ném lỗi."""

    def __init__(self):
        self.ky_tu = 0
        self.dang_go = None
        self._moi = []
        self._modo = "van"
        self._linh = ""
        self._stack = []           # [loại 'o'|'a', đang chờ khoá?]
        self._tc = False           # đang ở trong chuỗi
        self._thoat = False
        self._raw = []
        self._khoa = False         # chuỗi đang đọc là khoá của đối tượng
        self._reset_chuoi()

    def _reset_chuoi(self):
        self._da = 0
        self._ok = False
        self._so_cau = 0

    def lay_moi(self):
        m, self._moi = self._moi, []
        return m

    def _them(self, cau):
        for c in _chia_dai(cau):
            c = _gon(c, DONG_TOI_DA)
            if c:
                self._moi.append(c)
                self._so_cau += 1

    def _xu_ly(self, T, hoan_tat):
        """T = chữ (đã giải mã, bỏ thẻ) của 1 chuỗi/dòng; hoan_tat = chuỗi đã đóng."""
        if not self._ok:
            if not la_van_xuoi(T):
                self.dang_go = None
                if hoan_tat:
                    self._reset_chuoi()
                return
            self._ok = True
        phan, pos = T[self._da:], 0
        for m in _RE_CAU.finditer(phan):
            cau = phan[pos:m.end()].strip()
            if len(cau) >= MIN_CAU:
                self._them(cau); pos = m.end()
        self._da += pos
        con = T[self._da:].strip()
        if hoan_tat:
            if con and (self._so_cau > 0 or la_van_xuoi(con)) and any(c.isalpha() for c in con):
                self._them(con)
            self.dang_go = None
            self._reset_chuoi()
        else:
            if len(con) > DONG_TOI_DA:
                con = con[-DONG_TOI_DA:]
                con = con.split(" ", 1)[1] if " " in con else con
            self.dang_go = _gon(con, DONG_TOI_DA) or None

    # ---- chữ thường
    def _dong_van(self):
        return _RE_DAU_DONG.sub("", self._linh.lstrip().lstrip("*#_` ")).rstrip("\r\n").rstrip("*_` ") if self._linh.strip() else ""

    def _van(self, p):
        i = p.find("\n")
        seg = p if i < 0 else p[:i + 1]
        rest = p[len(seg):]
        self._linh += seg
        if _RE_BAT_DAU_JSON.match(self._linh):
            txt, self._linh = self._linh.lstrip(), ""
            self._reset_chuoi(); self.dang_go = None
            self._modo = "json"
            return txt + rest
        self._xu_ly(_bo_the(self._dong_van()), seg.endswith("\n"))
        if seg.endswith("\n"):
            self._linh = ""
        return rest

    # ---- chữ JSON
    def _ket_chuoi(self):
        raw = "".join(self._raw)
        self._raw = []
        self._tc = False
        if self._khoa:
            self._khoa = False
            if self._stack:
                self._stack[-1][1] = False
            return
        self._xu_ly(_bo_the(giai_ma(raw)), True)

    def _json(self, p):
        for k, ch in enumerate(p):
            if self._tc:
                if self._thoat:
                    self._thoat = False; self._raw.append(ch)
                elif ch == "\\":
                    self._thoat = True; self._raw.append(ch)
                elif ch == '"':
                    self._ket_chuoi()
                else:
                    self._raw.append(ch)
                continue
            if ch == '"':
                self._tc = True; self._raw = []
                self._khoa = bool(self._stack and self._stack[-1][0] == "o" and self._stack[-1][1])
                self._reset_chuoi()
            elif ch in "{[":
                self._stack.append(["o" if ch == "{" else "a", ch == "{"])
            elif ch in "}]":
                if self._stack:
                    self._stack.pop()
                if not self._stack:                              # hết khối JSON: chữ sau đó (nếu còn) là chữ thường
                    self._modo = "van"; self._linh = ""; self._reset_chuoi()
                    return p[k + 1:]
            elif ch == ",":
                if self._stack and self._stack[-1][0] == "o":
                    self._stack[-1][1] = True
            elif ch == ":":
                if self._stack and self._stack[-1][0] == "o":
                    self._stack[-1][1] = False
        if self._tc and not self._khoa:                          # chuỗi giá trị đang gõ dở
            self._xu_ly(_bo_the(giai_ma("".join(self._raw))), False)
        elif not self._tc:
            self.dang_go = None
        return ""

    def them(self, delta):
        try:
            delta = str(delta or "")
            self.ky_tu += len(delta)
            p = delta
            while p:
                p = self._json(p) if self._modo == "json" else self._van(p)
        except Exception:
            pass

    def het(self):
        """Hết luồng: chuỗi/dòng đang gõ dở coi như đã xong (không để mất câu cuối)."""
        try:
            if self._modo == "json":
                if self._tc and not self._khoa:
                    self._xu_ly(_bo_the(giai_ma("".join(self._raw))), True)
                self._tc = False; self._raw = []; self._khoa = False
            elif self._linh.strip():
                self._xu_ly(_bo_the(self._dong_van()), True)
            self._linh = ""
            self.dang_go = None
        except Exception:
            pass


# ---------------------------------------------------------------- file
def _ghi_tep(f, obj):
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tam = f.with_name(f.name + ".tmp")
        with open(tam, "w", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str))
        for _ in range(5):                                       # Windows: đúng lúc bên đọc đang mở file → thử lại ngắn
            try:
                os.replace(tam, f)
                return True
            except PermissionError:
                time.sleep(0.02)
        tam.unlink()
    except Exception:
        pass
    return False


def _doc_tep(f):
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and d.get("id") and d.get("vai") else None
    except Exception:
        return None


def don_cu(bay_gio=None, thu=None, cach=0.0):
    """Xoá file quá hạn: không cập nhật > 10 phút, hoặc việc xong > 60 s. `cach` > 0: bỏ qua nếu vừa dọn trong ngần ấy giây."""
    try:
        now = bay_gio or time.time()
        if cach and now - _don_cuoi[0] < cach:
            return
        _don_cuoi[0] = now
        d = Path(thu) if thu else thu_muc()
        if not d.is_dir():
            return
        for f in d.iterdir():
            try:
                if f.name.endswith(".tmp"):
                    if now - f.stat().st_mtime > 3600:
                        f.unlink()
                    continue
                if not f.name.endswith(".json"):
                    continue
                tuoi = now - f.stat().st_mtime
                if tuoi <= GIU_XONG_GIAY:
                    continue
                x = _doc_tep(f)
                if x is None or tuoi > HAN_GIAY or (x.get("xong") and now - float(x.get("cap_nhat") or 0) > GIU_XONG_GIAY):
                    f.unlink()
            except OSError:
                pass
    except Exception:
        pass


def doc_tat_ca(bay_gio=None, thu=None, xoa=True):
    """Các việc còn "sống" (cap_nhat trong 10 phút; việc xong trong 60 s), mới cập nhật nhất trước. Không bao giờ ném lỗi."""
    out = []
    try:
        now = bay_gio or time.time()
        d = Path(thu) if thu else thu_muc()
        if not d.is_dir():
            return out
        if xoa:
            don_cu(now, d, cach=30.0)
        for f in d.glob("*.json"):
            x = _doc_tep(f)
            if x is None:
                continue
            cn = float(x.get("cap_nhat") or 0)
            if now - cn > HAN_GIAY or (x.get("xong") and now - cn > GIU_XONG_GIAY):
                continue
            out.append(x)
        out.sort(key=lambda z: -float(z.get("cap_nhat") or 0))
    except Exception:
        pass
    return out


def cap_nhat_toi_da(bay_gio=None, thu=None):
    """Số `tt` của ảnh chụp luồng: cap_nhat lớn nhất trong các việc còn sống (0 nếu không có)."""
    try:
        return max((float(x.get("cap_nhat") or 0) for x in doc_tat_ca(bay_gio, thu, xoa=False)), default=0.0)
    except Exception:
        return 0.0


# ---------------------------------------------------------------- một việc đang chạy
class Viec:
    def __init__(self, vai, viec, sp=None, video=None, buoc=None, kenh=None, tien_do=None, chi_tiet=None, bat=None):
        self.bat = dang_bat() if bat is None else bat
        vai = str(vai)
        self.id = f"{vai}-{secrets.token_hex(3)}"
        self._lock = threading.RLock()
        self._ext = TrichDong()
        self._ky_tu_truoc = 0
        self._nghi = ""
        self._lan_ghi = 0.0
        self._hen = None
        self._mo = False
        self._ket = None
        self._dong = []
        now = time.time()
        self.d = {"id": self.id, "nguon": "hub", "vai": vai, "viec": _gon(viec), "sp": _gon(sp) if sp else None,
                  "video": _gon(video, 120) if video else None, "kenh": _gon(kenh, 80) if kenh else None,
                  "bat_dau": now, "cap_nhat": now, "xong": False, "ket_qua": None, "ky_tu": None, "dong": [], "dang_go": None,
                  "suy_nghi": None, "tien_do": None, "buoc": _gon(buoc, 80) if buoc else None, "chi_tiet": _chi_tiet_sach(chi_tiet) or None}
        if tien_do is not None:
            try:
                self.d["tien_do"] = max(0.0, min(1.0, round(float(tien_do), 3)))
            except (TypeError, ValueError):
                pass

    # ---- vòng đời
    def mo(self, hien_tai=True):
        """Mở việc (ghi file ngay). hien_tai=False: không làm "việc hiện tại" của luồng (ai.goi sẽ không gắn chữ vào đây)."""
        if self._mo or not self.bat:
            return self
        self._mo = True
        with _KHOA_MO:
            _MO.add(self)
        if hien_tai:
            st = getattr(_TL, "ngan", None)
            if st is None:
                st = _TL.ngan = []
            st.append(self)
        self._ghi(ep=True)
        return self

    def xong(self, ket_qua=None):
        """Kết thúc: xong=True + ket_qua ('ok' mặc định, hoặc ket() đã đặt)."""
        if not self.bat:
            return
        with self._lock:
            if self.d["xong"] or not self._mo:
                return
            self._het_chu()
            self.d["xong"] = True
            self.d["ket_qua"] = ket_qua or self._ket or "ok"
            self.d["dang_go"] = None
            self._huy_hen()
        self._ghi(ep=True)
        with _KHOA_MO:
            _MO.discard(self)
        st = getattr(_TL, "ngan", None)
        if st and self in st:
            st.remove(self)
        self._mo = False
        don_cu(cach=30.0)

    def ket(self, ket_qua):
        """Đặt kết quả sẽ ghi lúc thoát khối with ('ok' | 'loi')."""
        self._ket = ket_qua

    def __enter__(self):
        return self.mo()

    def __exit__(self, et, ev, tb):
        try:
            self.xong("loi" if et is not None else None)
        except Exception:
            pass
        return False

    # ---- cập nhật
    def cap(self, **kw):
        if not self.bat:
            return self
        with self._lock:
            for k, v in kw.items():
                if k == "chi_tiet":
                    c = dict(self.d.get("chi_tiet") or {}); c.update(_chi_tiet_sach(v)); self.d["chi_tiet"] = c or None
                elif k == "dong":
                    self._dong = [_gon(x, DONG_TOI_DA) for x in (v or []) if str(x).strip()][-TOI_DA_DONG:]
                elif k in ("viec", "sp", "kenh", "buoc", "video", "dang_go"):
                    self.d[k] = _gon(v, 120 if k in ("video", "kenh", "buoc") else CHUOI_TOI_DA) if v not in (None, "") else None
                elif k == "tien_do":
                    try:
                        self.d[k] = None if v is None else max(0.0, min(1.0, round(float(v), 3)))
                    except (TypeError, ValueError):
                        pass
                elif k in ("ky_tu", "ket_qua"):
                    self.d[k] = v
                else:                                           # số liệu thật lặt vặt → chi_tiet
                    c = dict(self.d.get("chi_tiet") or {}); c.update(_chi_tiet_sach({k: v})); self.d["chi_tiet"] = c or None
        self._ghi()
        return self

    def go(self, text):
        """Câu đang gõ dở (None = không)."""
        return self.cap(dang_go=text)

    def _day_dong(self, c):
        c = _gon(c, DONG_TOI_DA)
        if c and (not self._dong or self._dong[-1] != c):
            self._dong.append(c)
            del self._dong[:-TOI_DA_DONG]

    def them_dong(self, *cac):
        if not self.bat:
            return self
        with self._lock:
            for c in cac:
                self._day_dong(c)
        self._ghi()
        return self

    def chu(self, delta):
        """Mảnh chữ model vừa stream về."""
        if not self.bat or not delta:
            return
        with self._lock:
            self._ext.them(delta)
            for c in self._ext.lay_moi():
                self._day_dong(c)
            self.d["dang_go"] = self._ext.dang_go
            self.d["ky_tu"] = self._ky_tu_truoc + self._ext.ky_tu
        self._ghi()

    def nghi(self, delta):
        """Mảnh suy nghĩ (nếu luồng có)."""
        if not self.bat or not delta:
            return
        with self._lock:
            s = re.sub(r"\s+", " ", self._nghi + str(delta))
            if len(s) > SUY_NGHI_TOI_DA:
                s = s[-SUY_NGHI_TOI_DA:]
                s = s.split(" ", 1)[1] if " " in s else s
            self._nghi = s
            self.d["suy_nghi"] = _an_toan(s.strip()) or None
        self._ghi()

    def _het_chu(self):
        self._ext.het()
        for c in self._ext.lay_moi():
            self._day_dong(c)
        self.d["dang_go"] = None
        self._ky_tu_truoc += self._ext.ky_tu
        self._ext = TrichDong()
        if self._ky_tu_truoc:
            self.d["ky_tu"] = self._ky_tu_truoc

    def reset_chu(self):
        """Bắt đầu một lượt stream mới (gọi lại Claude): câu dở của lượt trước được chốt, dong giữ nguyên."""
        if not self.bat:
            return
        with self._lock:
            self._het_chu()
            self._nghi = ""
            self.d["suy_nghi"] = None
        self._ghi()

    def het_chu(self):
        """Hết một lượt stream."""
        if not self.bat:
            return
        with self._lock:
            self._het_chu()
        self._ghi()

    def nhip(self, **chi_tiet):
        """Đập tim: việc dài không có gì mới → vẫn ghi lại cap_nhat mỗi ~5 s (kèm số liệu thật như số giây đã chạy)."""
        if not self.bat or self.d["xong"]:
            return
        with self._lock:
            if chi_tiet:
                c = dict(self.d.get("chi_tiet") or {}); c.update(_chi_tiet_sach(chi_tiet)); self.d["chi_tiet"] = c
            if time.time() - self._lan_ghi < NHIP_GIAY:
                return
        self._ghi(ep=True)

    # ---- ghi
    def _huy_hen(self):
        if self._hen is not None:
            try:
                self._hen.cancel()
            except Exception:
                pass
            self._hen = None

    def _hen_ghi(self):
        with self._lock:
            self._hen = None
            if not self.d["xong"]:
                self._ghi()

    def _ghi(self, ep=False):
        """Ghi file nếu đủ GIAN_CACH kể từ lần ghi trước; chưa đủ → hẹn một lần ghi bù (không rớt bản cập nhật cuối)."""
        if not self.bat:
            return
        try:
            with self._lock:
                if not self._mo:
                    return
                now = time.time()
                if not ep and now - self._lan_ghi < GIAN_CACH:
                    if self._hen is None:
                        self._hen = threading.Timer(max(0.05, GIAN_CACH - (now - self._lan_ghi)), self._hen_ghi)
                        self._hen.daemon = True
                        self._hen.start()
                    return
                self._huy_hen()
                self._lan_ghi = now
                self.d["cap_nhat"] = now
                x = dict(self.d)
                x["dong"] = list(self._dong)
                _ghi_tep(thu_muc() / f"{self.id}.json", x)
        except Exception:
            pass


class _Khong:
    """Việc rỗng (công tắc tắt): mọi lời gọi là no-op."""
    bat = False
    id = ""
    d = {}

    def __getattr__(self, ten):
        return lambda *a, **k: self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def viec(vai, viec_text, **kw):
    """Tạo (chưa mở) một việc; dùng `with` hoặc .mo()/.xong(). Công tắc tắt → đối tượng rỗng."""
    try:
        if not dang_bat():
            return _Khong()
        return Viec(vai, viec_text, **kw)
    except Exception:
        return _Khong()


def hien_tai():
    """Việc đang mở gần nhất của LUỒNG này (None nếu không có)."""
    st = getattr(_TL, "ngan", None)
    while st and st[-1].d.get("xong"):          # việc đã được luồng khác đóng
        st.pop()
    return st[-1] if st else None


def cap_hien_tai(**kw):
    """tt.cap(**kw) cho việc hiện tại của luồng (nếu có). Không bao giờ ném lỗi."""
    try:
        t = hien_tai()
        if t is not None:
            t.cap(**kw)
    except Exception:
        pass


def nhip(**chi_tiet):
    """Đập tim cho việc hiện tại của luồng (nếu có). Không bao giờ ném lỗi."""
    try:
        t = hien_tai()
        if t is not None:
            t.nhip(**chi_tiet)
    except Exception:
        pass


# ---------------------------------------------------------------- vai Claude (ai.goi) → vai hợp đồng
def mo_ta_vai(vai):
    """Tên vai gọi Claude ('biên kịch', 'đạo diễn xxx', 'giám khảo', 'đọc nhãn', 'soát kho cảnh', 'gom bài học'...) → (vai hợp đồng, câu 'viec')."""
    v = str(vai or "").strip().lower()
    if v.startswith("biên kịch"):
        return "bien-kich", "Đang hỏi Claude: viết lời đọc"
    if v.startswith("đạo diễn"):
        return "dao-dien", "Đang hỏi Claude: lên bảng dựng"
    if v.startswith("giám khảo"):
        return "giam-khao", "Đang hỏi Claude: xem và chấm video"
    if v.startswith("gom bài học"):
        return "giam-khao", "Đang hỏi Claude: gom bài học"
    if v.startswith("đọc nhãn"):
        return "doc-nhan", "Đang hỏi Claude: đọc nhãn sản phẩm"
    if v.startswith("soát kho"):
        return "soat-kho", "Đang hỏi Claude: soát kho cảnh"
    return "he-thong", "Đang hỏi Claude: " + (str(vai or "").strip() or "việc nền")


def _dong_het():
    """Thoát tiến trình: việc nào còn mở thì đóng nốt (lô bị dừng giữa chừng không để lại việc 'đang chạy' ma)."""
    with _KHOA_MO:
        ds = list(_MO)
    for t in ds:
        try:
            t.xong("loi")
        except Exception:
            pass


atexit.register(_dong_het)
