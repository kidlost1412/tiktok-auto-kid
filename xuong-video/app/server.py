"""XƯỞNG VIDEO — app giao diện cho hub (chạy trên máy, mở bằng trình duyệt: http://127.0.0.1:8765).
Không cần cài thêm gì (chỉ dùng thư viện có sẵn của Python). Chạy bởi TikTok Auto (TikTokAuto.exe, dịch vụ xuong-video) và nhúng ở /xuong."""
import csv, datetime, json, mimetypes, os, re, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
import anh_sp

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, kem, kem_ngay, don_kem_cu, glob_kem
WEB = Path(__file__).resolve().parent / "web"
PORT = int(os.environ.get("XUONG_PORT") or 8765)
LS = HUB / "lich-su"
RUN = {"proc": None, "bat_dau": None, "san_pham": None, "so_video": 0}
BAT_DAU_APP = time.time()
_auth = {"t": 0, "v": None}


def cfg():
    return cfg_hub()


def luu_cfg(c):
    c = dict(c); c["duong_dan"] = cfg_tho().get("duong_dan", {})        # không ghi đường dẫn đã giải ra file
    (HUB / "config.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")


NHAC_TAI = {"dang": False, "ghi": "", "da": 0, "tong": 0, "loi": None, "xong": False}


def nhac_trang_thai():
    sys.path.insert(0, str(CODE / "engine"))
    import kho_nhac
    c = cfg().get("nhac") or {}
    nguon = []
    for i, n in enumerate(c.get("nguon") or []):
        d = str(n.get("duong_dan", ""))
        ok = os.path.isdir(d)
        nguon.append({"i": i, "duong_dan": d, "loai": n.get("loai"), "bat": bool(n.get("bat", True)), "ton_tai": ok,
                      "so_file": kho_nhac.dem_am(d) if ok else 0})
    return {"ok": True, "mac_dinh": kho_nhac.trang_thai_mac_dinh(), "nguon": nguon,
            "co_link": bool((c.get("goi_mac_dinh_url") or "").strip()), "tai": dict(NHAC_TAI)}


def nhac_nguon_sua(b):
    c = cfg(); n = c.setdefault("nhac", {}); ds = n.setdefault("nguon", [])
    if "them" in b:
        t = b["them"] or {}; d = os.path.normpath(str(t.get("duong_dan", "")).strip().strip('"')); loai = t.get("loai")
        if loai not in ("nhac", "sfx") or not re.match(r"^[A-Za-z]:[\\/]|^\\\\", d) or not os.path.isdir(d):
            return {"ok": False, "loi": "Thư mục không hợp lệ."}
        if any(os.path.normcase(x.get("duong_dan", "")) == os.path.normcase(d) and x.get("loai") == loai for x in ds):
            return {"ok": False, "loi": "Thư mục này đã có trong danh sách."}
        ds.append({"duong_dan": d, "loai": loai, "bat": True})
    elif "xoa" in b and isinstance(b["xoa"], int) and 0 <= b["xoa"] < len(ds):
        ds.pop(b["xoa"])
    elif "bat" in b and isinstance(b["bat"], int) and 0 <= b["bat"] < len(ds):
        ds[b["bat"]]["bat"] = bool(b.get("gia_tri"))
    else:
        return {"ok": False, "loi": "Yêu cầu không hợp lệ."}
    luu_cfg(c)
    return {"ok": True}


def nhac_tai_bat_dau():
    if NHAC_TAI["dang"]:
        return {"ok": False, "loi": "Đang tải rồi."}
    if not ((cfg().get("nhac") or {}).get("goi_mac_dinh_url") or "").strip():
        return {"ok": False, "loi": "Chưa có gói nhạc tải sẵn. Thêm thư mục nhạc của anh ở mục bên dưới."}
    NHAC_TAI.update(dang=True, ghi="Bắt đầu…", da=0, tong=0, loi=None, xong=False)

    def cb(d):
        NHAC_TAI.update(ghi=d.get("ghi", ""), da=d.get("da", 0), tong=d.get("tong", 0))

    def lam():
        try:
            sys.path.insert(0, str(CODE / "engine"))
            import kho_nhac
            kho_nhac.tai_goi(cb=cb)
            NHAC_TAI["xong"] = True
        except Exception as e:
            NHAC_TAI["loi"] = str(e)[:200]
        finally:
            NHAC_TAI["dang"] = False
    threading.Thread(target=lam, daemon=True).start()
    return {"ok": True}


def ra_dir():
    return Path(cfg()["duong_dan"]["ra"])


# ---- Khoá ElevenLabs (giọng đọc): kiểm trước khi chạy lô, nhập/lưu ở tab Cài đặt (không bao giờ trả nguyên khoá ra giao diện) ----
KHOA_GIONG = "ELEVENLABS_API_KEY"


def _env_hub():
    return Path(cfg()["duong_dan"].get("env_file") or (HUB / ".env"))


def _doc_khoa(f):
    try:
        for l in Path(f).read_text(encoding="utf-8-sig").splitlines():
            k, _, v = l.partition("=")
            if k.strip() == KHOA_GIONG:
                return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def _khoa_hien_tai():
    return _doc_khoa(_env_hub()) or _doc_khoa(CODE.parent / ".env")


def co_khoa_giong():
    try:
        sys.path.insert(0, str(CODE / "engine"))
        from giong import co_khoa_giong as _ck      # engine (agent khác thêm); chưa có / thiếu thư viện → kiểm tại chỗ
        return bool(_ck())
    except Exception:
        return bool(_khoa_hien_tai())


def khoa_giong_trang_thai():
    k = _khoa_hien_tai()
    return {"ok": True, "co": bool(k), "cuoi": k[-4:] if len(k) >= 8 else ""}


def khoa_giong_luu(k):
    k = str(k or "").strip().strip('"').strip("'")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{16,200}", k):
        return {"ok": False, "loi": "Khoá không hợp lệ (dán đúng khoá API ElevenLabs, không có dấu cách)."}
    f = _env_hub(); f.parent.mkdir(parents=True, exist_ok=True)
    try:
        dong = f.read_text(encoding="utf-8-sig").splitlines() if f.exists() else []
    except OSError:
        dong = []
    moi, da = [], False
    for l in dong:
        if l.partition("=")[0].strip() == KHOA_GIONG:
            if not da:
                moi.append(f"{KHOA_GIONG}={k}"); da = True
            continue
        moi.append(l)
    if not da:
        moi.append(f"{KHOA_GIONG}={k}")
    f.write_bytes(("\n".join(moi) + "\n").encode("utf-8"))      # UTF-8 không BOM, giữ các dòng khác
    os.environ.pop(KHOA_GIONG, None)                                # lần chạy sau đọc lại từ file
    return khoa_giong_trang_thai()


NHUNG_MAC_DINH = ["http://localhost:8010", "http://127.0.0.1:8010"]     # TikTok Auto nhúng app này (iframe)


def _popen(cmd, **kw):
    """Chạy lô/chuẩn bị kho TÁCH khỏi job của tiến trình cha: launcher (TikTokAuto.exe) khởi động lại app thì lô đang làm
    KHÔNG chết theo. Job không cho tách → chạy bình thường."""
    co = kw.pop("creationflags", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.Popen(cmd, creationflags=co | 0x01000000, **kw)      # CREATE_BREAKAWAY_FROM_JOB
    except OSError:
        return subprocess.Popen(cmd, creationflags=co, **kw)


def pid_lo():
    """PID lô đang chạy theo file khoá (kể cả lô của phiên app trước), None nếu không có."""
    k = LS / "dang-chay.lock"
    try:
        pid = int(k.read_text().split()[0])
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return pid if str(pid) in r.stdout else None
    except Exception:
        return None


def dang_chay():
    p = RUN["proc"]
    if p and p.poll() is None:
        return True
    k = LS / "dang-chay.lock"                 # lô chạy từ cửa sổ lệnh (sanxuat.ps1) cũng tính
    if k.exists():
        try:
            pid = int(k.read_text().split()[0])
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
            return str(pid) in r.stdout
        except Exception:
            return False
    return False


def auth(force=False):
    if not force and _auth["v"] and time.time() - _auth["t"] < 60:
        return _auth["v"]
    try:
        r = subprocess.run([cfg()["duong_dan"]["claude"], "auth", "status", "--json"], capture_output=True, text=True,
                           encoding="utf-8", timeout=40)
        d = json.loads(r.stdout)
        v = {k: d.get(k) for k in ("loggedIn", "email", "subscriptionType", "planTier", "orgName", "authMethod")}
    except Exception as e:
        v = {"loggedIn": False, "loi": str(e)[:120]}
    _auth.update(t=time.time(), v=v)
    return v


def nhat_ky_lo():
    """Các dòng nhật ký của lần chạy gần nhất."""
    f = LS / "nhat-ky.txt"
    if not f.exists():
        return []
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    idx = max([i for i, l in enumerate(lines) if "BẮT ĐẦU" in l] or [0])
    return lines[idx:][-400:]


def tien_do(lines):
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
    return {"xong": done, "tong": total or RUN["so_video"], "het_han_muc": het, "da_xong": any("XONG:" in l for l in lines)}


def moc_dem():
    """Mốc bắt đầu đếm 'Hôm nay' (anh bấm Đếm lại) — không sớm hơn 0 giờ hôm nay."""
    hom_nay = datetime.datetime.combine(datetime.date.today(), datetime.time())
    f = LS / "moc-dem.txt"
    try:
        m = datetime.datetime.fromisoformat(f.read_text(encoding="utf-8").strip()) if f.exists() else hom_nay
    except Exception:
        m = hom_nay
    return max(m, hom_nay)


def token_hom_nay():
    m = moc_dem()
    video = sum(1 for v in ra_dir().glob(f"{datetime.date.today().isoformat()}/*.mp4")
                if datetime.datetime.fromtimestamp(v.stat().st_mtime) >= m)
    f = LS / "token.csv"
    if not f.exists():
        return {"luot": 0, "token": 0, "usd": 0, "video": video, "moc": m.strftime("%H:%M")}
    r = []
    for x in csv.DictReader(open(f, encoding="utf-8-sig")):
        try:
            if datetime.datetime.fromisoformat(x["luc"]) >= m:
                r.append(x)
        except Exception:
            pass
    tok = sum(int(x["vao"] or 0) + int(x["vao_cache_tao"] or 0) + int(x["vao_cache_doc"] or 0) + int(x["ra"] or 0) for x in r)
    ky_tu = 0; fg = LS / "giong.csv"
    if fg.exists():
        for x in csv.DictReader(open(fg, encoding="utf-8-sig")):
            try:
                if datetime.datetime.fromisoformat(x["luc"]) >= m:
                    ky_tu += int(x["ky_tu"] or 0)
            except Exception:
                pass
    return {"luot": len(r), "token": tok, "usd": round(sum(float(x["usd_uoc"] or 0) for x in r), 2), "video": video,
            "moc": m.strftime("%H:%M"), "ky_tu": ky_tu, "token_ra": sum(int(x["ra"] or 0) for x in r)}


_DEM = {}


def dem_canh(f):
    """Số cảnh trong canh.json — nhớ theo thời điểm sửa file, không đọc lại mỗi 3 giây."""
    if not f.exists():
        return 0
    k = (str(f), f.stat().st_mtime)
    if k not in _DEM:
        _DEM[k] = len(json.loads(f.read_text(encoding="utf-8")))
    return _DEM[k]


def san_pham_ds():
    sys.path.insert(0, str(CODE / "engine"))
    from kho_chung import la_kho_chung, kho_them_cua, dem_dung_duoc
    anh_sp.dong_bo_nen()                       # nền: thay khung-video bằng ảnh thật TikTok Shop (nếu TikTok Auto đang mở)
    out = []
    for d in sorted((HUB / "san-pham").iterdir()):
        f = d / "san-pham.json"
        if f.exists():
            sp = json.loads(f.read_text(encoding="utf-8"))
            canh = d / "canh.json"
            n = dem_canh(canh)
            chung = la_kho_chung(sp)
            if chung:             # kho cảnh dùng chung: không bán → không có "thiếu", không làm video cho nó
                out.append({"ma": d.name, "ten": sp.get("ten_goi", d.name), "so_canh": n, "san_sang": False, "thieu": [], "loai": "kho-chung",
                            "so_dung_duoc": dem_dung_duoc(d.name), "tron_mac_dinh": bool(sp.get("tron_mac_dinh")), "anh": anh_sp.url_anh(d.name)})
                continue
            thieu = [t for t, ok in (("sự thật sản phẩm", sp.get("su_that_duoc_noi")), ("quà tặng", sp.get("qua_tang")),
                                     ("kho cảnh", n > 0),
                                     # tên Shop dài nguyên văn → AI không đọc trọn → mọi lời bị loại "thiếu tên thương hiệu"
                                     ("tên gọi ngắn khi đọc", len((sp.get("ten_ngan") or sp.get("ten_goi") or "").split()) <= 6)) if not ok]
            out.append({"ma": d.name, "ten": sp.get("ten_goi", d.name), "so_canh": n, "san_sang": not thieu, "thieu": thieu, "loai": "ban", "so_dung_duoc": dem_dung_duoc(d.name),
                        "kho_them": kho_them_cua(d.name, sp), "anh": anh_sp.url_anh(d.name),
                        "ten_ngan": sp.get("ten_ngan") or "", "thoi_luong": sp.get("thoi_luong")})
    return out


def thoi_luong_mac_dinh():
    v = cfg().get("video") or {}
    try:
        return [float(v.get("thoi_luong_min", 20)), float(v.get("thoi_luong_max", 25))]
    except (TypeError, ValueError):
        return [20.0, 25.0]


def kiem_thoi_luong(g):
    """giay = [min, max]: số, 10 <= min, max <= 60, max-min >= 3. Trả (list|None, lỗi|None)."""
    try:
        if not isinstance(g, (list, tuple)) or len(g) != 2 or any(isinstance(x, bool) for x in g):
            raise ValueError
        a, b = float(g[0]), float(g[1])
    except (TypeError, ValueError):
        return None, "Độ dài video không hợp lệ (cần 2 số: ít nhất – nhiều nhất, tính bằng giây)."
    if not (a == a and b == b) or a < 10 or b > 60 or b - a < 3:
        return None, "Độ dài video phải từ 10 đến 60 giây, và khoảng cách giữa 2 số ít nhất 3 giây."
    f = lambda x: int(x) if x == int(x) else round(x, 1)
    return [f(a), f(b)], None


def doc_la_tu_text(t, toi_da=10):
    """'MIG 38 = Mích ba mươi tám' mỗi dòng (hoặc ngăn bằng ;) → {viết: đọc}. Bỏ dòng trống/thiếu vế, mỗi vế ≤ 60 ký tự."""
    out = {}
    for dong in re.split(r"[\r\n;]+", str(t or "")):
        k, _, v = dong.partition("=")
        k, v = " ".join(k.split()), " ".join(v.split())
        if k and v and len(k) <= 60 and len(v) <= 60 and k not in out:
            out[k] = v
        if len(out) >= toi_da:
            break
    return out


# ---- Giọng đọc: danh sách giong.danh_sach trong config.json + chọn từ tài khoản ElevenLabs (không bao giờ trả khoá ra giao diện) ----
def _giong_ds():
    d = (cfg().get("giong") or {}).get("danh_sach") or {}
    return {str(k): str(v) for k, v in d.items() if str(k) and str(v)}


def giong_trang_thai():
    return {"ok": True, "co_khoa": bool(_khoa_hien_tai()),
            "ds": [{"ten": k, "id": v, "id_ngan": (v[:4] + "…" + v[-4:]) if len(v) > 10 else v} for k, v in _giong_ds().items()]}


def _el_client():
    sys.path.insert(0, str(CODE / "engine"))
    from giong import client
    return client()


def _voice_dict(v):
    lb = getattr(v, "labels", None) or {}
    return {"id": getattr(v, "voice_id", "") or "", "ten": getattr(v, "name", "") or "", "loai": getattr(v, "category", "") or "",
            "gioi_tinh": str(lb.get("gender") or ""), "giong_vung": str(lb.get("accent") or ""), "do_tuoi": str(lb.get("age") or ""),
            "nghe_thu": getattr(v, "preview_url", "") or ""}


def giong_tai_khoan():
    if not _khoa_hien_tai():
        return {"ok": False, "loi": "Chưa có khoá ElevenLabs. Dán khoá ở mục \"Khoá ElevenLabs\" rồi Lưu."}
    try:
        c = _el_client()
        try:
            r = c.voices.search(page_size=100)
            ds = list(getattr(r, "voices", None) or [])
        except Exception:
            r = c.voices.get_all()
            ds = list(getattr(r, "voices", None) or [])
        return {"ok": True, "ds": [_voice_dict(v) for v in ds if getattr(v, "voice_id", None)]}
    except Exception as e:
        return {"ok": False, "loi": f"Không lấy được danh sách giọng ({type(e).__name__}). Kiểm tra khoá ElevenLabs và mạng."}


def giong_mau(vid):
    """Link nghe thử của 1 giọng ĐANG DÙNG (chỉ nhận id nằm trong danh sách, không nhận id tuỳ ý)."""
    if vid not in _giong_ds().values():
        return {"ok": False, "loi": "Giọng này không có trong danh sách đang dùng."}
    if not _khoa_hien_tai():
        return {"ok": False, "loi": "Chưa có khoá ElevenLabs."}
    try:
        url = getattr(_el_client().voices.get(vid), "preview_url", "") or ""
    except Exception:
        return {"ok": False, "loi": "Không lấy được bản nghe thử của giọng này."}
    return {"ok": bool(url), "nghe_thu": url, "loi": None if url else "Giọng này chưa có bản nghe thử."}


def _khoa_ten_giong(ten, da_co):
    import unicodedata
    t = unicodedata.normalize("NFD", str(ten or "").replace("đ", "d").replace("Đ", "D"))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", t) if w)[:26] or "Giong"
    if len(t) < 2:
        t += "X"
    k, i = t, 2
    while k in da_co:
        k = f"{t[:26]}{i}"; i += 1
    return k


def giong_luu(b):
    """b: {"ds": {ten: id}} ghi đè cả danh sách (≥1) · hoặc {"them": {"id", "ten"?}} (kiểm id) · hoặc {"xoa": ten}."""
    c = cfg(); g = c.setdefault("giong", {})
    ds = dict(_giong_ds())
    if isinstance(b.get("ds"), dict):
        moi = {}
        for k, v in b["ds"].items():
            if re.fullmatch(r"[A-Za-z0-9_]{2,30}", str(k)) and re.fullmatch(r"[A-Za-z0-9]{10,40}", str(v)):
                moi[str(k)] = str(v)
        ds = moi
    elif isinstance(b.get("them"), dict):
        vid = str(b["them"].get("id") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9]{10,40}", vid):
            return {"ok": False, "loi": "Voice ID không đúng (thường là 20 ký tự chữ và số)."}
        if vid in ds.values():
            return {"ok": False, "loi": "Giọng này đã có trong danh sách đang dùng."}
        ten = str(b["them"].get("ten") or "").strip()
        if not ten or b["them"].get("kiem"):
            if not _khoa_hien_tai():
                return {"ok": False, "loi": "Chưa có khoá ElevenLabs. Dán khoá ở mục \"Khoá ElevenLabs\" rồi Lưu."}
            try:
                v = _el_client().voices.get(vid)
                ten = ten or getattr(v, "name", "") or ""
            except Exception:
                return {"ok": False, "loi": "Không tìm thấy giọng này trong tài khoản của anh. Với giọng lấy từ Thư viện giọng (Voice Library), anh vào elevenlabs.io, bấm \"Add to My Voices\" cho giọng đó trước, rồi thử lại."}
        ds[_khoa_ten_giong(ten, ds)] = vid
    elif isinstance(b.get("xoa"), str):
        ds.pop(b["xoa"], None)
    else:
        return {"ok": False, "loi": "Yêu cầu không hợp lệ."}
    if not ds:
        return {"ok": False, "loi": "Phải giữ lại ít nhất 1 giọng."}
    g["danh_sach"] = ds
    luu_cfg(c)
    return giong_trang_thai()


KHO_JOB = {}


def slug(t):
    import unicodedata
    t = unicodedata.normalize("NFD", t.replace("đ", "d").replace("Đ", "D"))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:30] or "sp"


def tao_san_pham(b):
    ten = (b.get("ten") or "").strip()
    if not ten:
        return {"ok": False, "loi": "Thiếu tên sản phẩm"}
    ma = b.get("ma") or slug(ten)
    d = HUB / "san-pham" / ma; d.mkdir(parents=True, exist_ok=True)
    f = d / "san-pham.json"
    sp = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    sp.update({"ma": ma, "ten_goi": ten, "ten_ngan": b.get("ten_ngan") or sp.get("ten_ngan") or ten})
    if b.get("loai") == "kho-chung":          # kho cảnh dùng chung: không bán, chỉ cho sản phẩm khác mượn cảnh
        sp["loai"] = "kho-chung"; sp.pop("chi_la_kho_canh", None)
    if b.get("kho"):
        sp["kho_video"] = b["kho"].strip().strip('"')
    shop_id = str(b.get("shop_id") or "").strip()
    if re.fullmatch(r"[0-9]{1,32}", shop_id) and sp.get("loai") != "kho-chung":
        sp["shop_product_id"] = shop_id           # nhớ sản phẩm Shop đã chọn (để gắn giỏ hàng trong TikTok Auto)
    if b.get("doc_la"):
        dl = doc_la_tu_text(b["doc_la"])
        if dl:
            sp["doc_la"] = dl
    if sp.get("loai") == "kho-chung":
        for k, mac_dinh in (("su_that_duoc_noi", []), ("qua_tang", []), ("khong_duoc_noi", []), ("goc_ban", []), ("loai_tru", {"file": [], "doan": []})):
            sp.setdefault(k, mac_dinh)
        f.write_text(json.dumps(sp, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "ma": ma}
    for k, mac_dinh in (("su_that_duoc_noi", []), ("qua_tang", []), ("khong_duoc_noi", ["Giá tiền, giá trị quà.", "'chữa khỏi', cam kết 100%, 'số 1', 'nhất', 'duy nhất'."]),
                        ("goc_ban", []), ("loai_tru", {"file": [], "doan": []})):
        sp.setdefault(k, mac_dinh)
    f.write_text(json.dumps(sp, ensure_ascii=False, indent=1), encoding="utf-8")
    out = {"ok": True, "ma": ma}
    if sp.get("shop_product_id") and b.get("anh_shop", True):
        g, err = anh_sp.dat_tu_shop(ma, sp["shop_product_id"])     # ảnh thật của sản phẩm Shop đã chọn
        if not g:
            out["canh_bao"] = err
    return out


def kho_trang_thai(ma):
    d = HUB / "san-pham" / ma
    sp = json.loads((d / "san-pham.json").read_text(encoding="utf-8")) if (d / "san-pham.json").exists() else {}
    kho = Path(sp.get("kho_video", "")) if sp.get("kho_video") else None
    canh = json.loads((d / "canh.json").read_text(encoding="utf-8")) if (d / "canh.json").exists() else []
    so_video = 0
    if kho and kho.exists():
        for _g, dirnames, filenames in os.walk(kho, onerror=lambda e: None):
            dirnames[:] = [n for n in dirnames if n not in ("_tam", "_mo-ta")]
            so_video += sum(1 for n in filenames if n.lower().endswith((".mp4", ".mov", ".mkv", ".webm")))
    so_mo_ta = len({x.name.replace(".mo-ta.json", "").lower().removesuffix(".mp4") for x in (kho / "_mo-ta").rglob("*.mo-ta.json") if not any(q.startswith("_") for q in x.relative_to(kho / "_mo-ta").parts[:-1])})         if kho and (kho / "_mo-ta").exists() else 0          # đếm theo tên video (bỏ bản trùng ở thư mục con / sao lưu)
    j = KHO_JOB.get(ma)
    log = (LS / f"kho-{ma}.log")
    dong = log.read_text(encoding="utf-8", errors="replace").splitlines() if log.exists() else []
    moc = [l.strip() for l in dong if l.startswith("##")]
    buoc = 4 if moc and moc[-1] == "##XONG" else (int(moc[-1][7]) if moc and re.fullmatch(r"##BUOC [1-3]/3", moc[-1]) else 0)
    return {"buoc": buoc, "kho": sp.get("kho_video", ""), "kho_ton_tai": bool(kho and kho.exists()), "so_video": so_video, "so_mo_ta": so_mo_ta,
            "so_canh": len(canh), "so_soat": sum(1 for x in canh if x.get("soat")), "dang_chay": bool(j and j.poll() is None),
            "log": [l for l in dong if not l.startswith("##")][-8:]}


def lenh_gemini(ma):
    """Lệnh dán cho Gemini để nó xem từng video trong kho và ghi mô tả từng cảnh (đúng mẫu hub đang đọc)."""
    sp = json.loads((HUB / "san-pham" / ma / "san-pham.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(CODE / "engine"))
    import prompt_mau                               # mẫu lệnh chỉnh được ở tab Prompt AI; đường dẫn trỏ bản Mô tả video đang dùng (bản sửa nếu có)
    return prompt_mau.dien("lenh-gemini", kho_video=sp.get("kho_video", "<thư mục kho>"),
                           duong_dan_mo_ta=str(prompt_mau.duong_dan_hieu_luc("mo-ta-gemini")))


def _pm():
    sys.path.insert(0, str(CODE / "engine"))
    import prompt_mau
    return prompt_mau


def prompt_ds():
    """Tab Prompt AI: danh sách vai + nội dung đang dùng."""
    pm = _pm(); out = []
    for k, v in pm.VAI.items():
        text, sua = pm.doc(k)
        out.append({"ten": k, "ten_hien_thi": v["ten"], "mo_ta": v["mo_ta"], "bien": v["bien"], "bat_buoc": v["bat_buoc"],
                    "la_ban_sua": sua, "text": text, "loai": "tai_lieu" if v["file"].startswith("luat/") else "de_bai"})
    return out


def prompt_mac_dinh(ten):
    pm = _pm()
    if ten not in pm.VAI:
        return {"ok": False, "loi": "Không có đề bài này."}
    return {"ok": True, "text": pm.mac_dinh(ten)}


def prompt_ban_cu(ten):
    pm = _pm()
    if ten not in pm.VAI:
        return {"ok": False, "loi": "Không có đề bài này."}
    return {"ok": True, "ds": pm.ds_ban_cu(ten)}


def prompt_luu(ten, text):
    pm = _pm()
    if ten not in pm.VAI:
        return {"ok": False, "loi": "Không có đề bài này."}
    if not isinstance(text, str) or not text.strip():
        return {"ok": False, "loi": "Đề bài đang trống — hãy nhập nội dung hoặc bấm \"Khôi phục mặc định\"."}
    kq = pm.kiem(ten, text)
    if kq["thieu"]:
        return {"ok": False, "loi": "Thiếu chỗ điền bắt buộc: " + ", ".join("{{" + b + "}}" for b in kq["thieu"])
                + ". Máy cần các chỗ này để gửi dữ liệu sản phẩm cho AI — hãy thêm lại rồi lưu."}
    pm.luu(ten, text)
    canh_bao = ["{{" + b + "}} không phải chỗ điền hợp lệ của vai này — máy sẽ gửi nguyên chữ đó cho AI." for b in kq["la"]]
    return {"ok": True, "canh_bao": canh_bao, "la_ban_sua": pm.doc(ten)[1]}


def prompt_khoi_phuc(ten):
    pm = _pm()
    if ten not in pm.VAI:
        return {"ok": False, "loi": "Không có đề bài này."}
    pm.khoi_phuc(ten)
    return {"ok": True, "text": pm.mac_dinh(ten)}


def prompt_xem_thu(ten, ma_sp, text=None):
    pm = _pm()
    if ten not in pm.VAI:
        return {"ok": False, "loi": "Không có đề bài này."}
    if text is not None and not isinstance(text, str):
        text = None
    try:
        r = pm.xem_thu(ten, ma_sp, text)
    except Exception as e:
        return {"ok": False, "loi": "Không dựng thử được: " + str(e)[:200]}
    r["ok"] = not r.get("thieu_du_lieu")
    if not r["ok"]:
        r["loi"] = (r.get("canh_bao") or ["Chưa có dữ liệu để xem thử."])[-1]
    return r


def chuan_bi_kho(ma):
    j = KHO_JOB.get(ma)
    if j and j.poll() is None:
        return {"ok": False, "loi": "Đang chuẩn bị kho rồi."}
    c = cfg(); py = c["duong_dan"]["python"]; eng = CODE / "engine"
    log = LS / f"kho-{ma}.log"
    cmd = (f'echo ##BUOC 1/3&& "{py}" -X utf8 "{eng / "kiem_mo_ta.py"}" {ma} --sua && echo ##BUOC 2/3&& "{py}" -X utf8 "{eng / "kho_canh.py"}" {ma} && '
           f'echo ##BUOC 3/3&& "{py}" -X utf8 "{eng / "soat_kho.py"}" {ma} && echo ##XONG')   # kiểm định dạng mô tả → nạp cảnh → AI soát (##: mốc tiến độ cho giao diện)
    KHO_JOB[ma] = _popen(cmd, shell=True, cwd=str(eng), stdout=open(log, "w", encoding="utf-8"), stderr=subprocess.STDOUT,
                         env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return {"ok": True}


# ---- Kiểm định dạng mô tả + Học cảnh bằng Antigravity ----
sys.path.insert(0, str(CODE / "engine"))
KD = {}                      # mã sản phẩm → {"dang_chay", "bao_cao"}


def kiem_dinh(ma, sua):
    if not (HUB / "san-pham" / ma / "san-pham.json").exists():
        return {"ok": False, "loi": "Không có sản phẩm này."}
    if (KD.get(ma) or {}).get("dang_chay"):
        return {"ok": False, "loi": "Đang kiểm rồi."}
    KD[ma] = {"dang_chay": True, "bao_cao": None, "xong": 0, "tong": 0}

    def lam():
        try:
            import kiem_mo_ta
            def td(i, n, ten): KD[ma].update(xong=i, tong=n)
            r = kiem_mo_ta.kiem_kho(ma, sua=bool(sua), tien_do=td)
            r["tom_tat"] = kiem_mo_ta.tom_tat(r)
            for k, gh in (("da_sua", 60), ("hong", 60), ("thieu_mo_ta", 60), ("mo_coi", 40), ("trung", 40), ("canh_bao", 40)):
                r["so_" + k] = len(r[k]); r[k] = r[k][:gh]        # báo cáo gọn cho giao diện
            KD[ma]["bao_cao"] = r
        except Exception as e:
            KD[ma]["bao_cao"] = {"loi": str(e)[:200]}
        finally:
            KD[ma]["dang_chay"] = False
    threading.Thread(target=lam, daemon=True).start()
    return {"ok": True}


def hoc_canh_trang_thai(ma):
    import hoc_canh
    j = dict(hoc_canh.JOB)
    try:
        quyen = hoc_canh.trang_thai_quyen(hoc_canh.km._kho_cua(ma))
    except Exception:
        quyen = None
    return {"agy": hoc_canh.trang_thai_agy(), "model": hoc_canh.doc_model(),
            "models": [{"v": k, "t": t} for k, t in hoc_canh.MODELS.items()],
            "job": j if j.get("ma") == ma else None, "job_khac": bool(j.get("dang_chay") and j.get("ma") != ma),
            "dang_chay_lo": bool(dang_chay()), "quyen": quyen}


def hoc_canh_quyen(ma):
    """Bấm 'Bật tự duyệt': tạo Project riêng (chỉ thư mục kho này) có quyền Turbo trong cài đặt Antigravity."""
    import hoc_canh
    try:
        kho = hoc_canh.km._kho_cua(ma)
    except Exception:
        return {"ok": False, "loi": "Sản phẩm này chưa có thư mục kho video."}
    r = hoc_canh.thiet_lap_quyen(kho)
    if r.get("ok"):
        r["thu_muc"] = str(kho)
    return r


def _chuan_bi_kho_sau_hoc(ma):
    """Học cảnh xong thì chuẩn bị kho; nếu hub đang làm video thì ĐỢI lô xong rồi mới chạy (tránh 2 việc nặng + Claude cùng lúc)."""
    if not dang_chay():
        return chuan_bi_kho(ma)

    def doi():
        for _ in range(2880):                                   # tối đa ~8 giờ, 10 giây một lần
            time.sleep(10)
            if not dang_chay():
                chuan_bi_kho(ma)
                return
    threading.Thread(target=doi, daemon=True, name="chuan-bi-kho-sau-hoc").start()
    return {"ok": True, "doi": True}


def hoc_canh_bat_dau(ma):
    import hoc_canh
    k = KHO_JOB.get(ma)
    if k and k.poll() is None:
        return {"ok": False, "loi": "Đang chuẩn bị kho."}
    if not hoc_canh.trang_thai_agy()["mo"]:
        return {"ok": False, "loi": "Antigravity chưa mở — bấm Mở Antigravity.", "can": "mo"}
    if hoc_canh.JOB.get("dang_chay"):
        return {"ok": False, "loi": "Đang học rồi."}
    # Học cảnh là làn riêng: KHÔNG chặn làm video (và ngược lại). Đang làm video thì học nhường máy: chỉ 1 lô một lúc.
    return hoc_canh.bat_dau_nen(ma, khi_xong=lambda kq: _chuan_bi_kho_sau_hoc(ma), ban_san_xuat=dang_chay)


_TQ = {"t": 0, "v": None}


def tong_quan(moi=False):
    """Mỗi sản phẩm: video gốc trong kho, số cảnh, video đã làm, video còn tồn (chưa đăng, chưa ❌)."""
    if not moi and _TQ["v"] and time.time() - _TQ["t"] < 60:
        return _TQ["v"]
    from tu_dong import dem
    out = []
    for p in san_pham_ds():
        k = kho_trang_thai(p["ma"])
        ton, nay = dem(p["ma"])
        da_lam = len([v for v in ra_dir().glob(f"*/{p['ma']}_*.mp4") if not v.parent.name.startswith("_")])
        out.append(dict(p, video_kho=k["so_video"], mo_ta=k["so_mo_ta"], da_lam=da_lam, ton=ton, lam_hom_nay=nay))
    _TQ.update(t=time.time(), v=out)
    return out


def xoa_san_pham(ma):
    """Bỏ hồ sơ sản phẩm (hồ sơ + kho cảnh đã nạp) vào Thùng rác — KHÔNG đụng video gốc, KHÔNG xoá video đã làm."""
    d = HUB / "san-pham" / ma
    if not d.exists() or not re.fullmatch(r"[a-z0-9-]+", ma):
        return {"ok": False, "loi": "Không có sản phẩm này"}
    c = cfg()
    dung_lam_qua = [k for k, v in (c.get("kho_qua") or {}).items() if v == ma]
    ps = ("Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory('"
          + str(d).replace("'", "''") + "','OnlyErrorDialogs','SendToRecycleBin')")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    if d.exists():
        return {"ok": False, "loi": "Không xoá được: " + (r.stderr or "")[:150]}
    c.get("tu_dong", {}).get("san_pham", {}).pop(ma, None)
    for k in dung_lam_qua:
        c["kho_qua"].pop(k, None)
    luu_cfg(c); _TQ["t"] = 0
    return {"ok": True, "bo_canh_qua": dung_lam_qua}


_AUTH_TK = {}


def tai_khoan_ds(moi=False):
    """Mọi tài khoản: email/đăng nhập (claude auth status theo thư mục riêng) + hạn mức 5 giờ / 7 ngày CLI báo về."""
    sys.path.insert(0, str(CODE / "engine"))
    import ai
    st = ai.doc_trang_thai(); out = []
    for tk in ai.ds_tai_khoan():
        a = _AUTH_TK.get(tk["ma"])
        if moi or not a or time.time() - a["t"] > 300:
            try:
                r = subprocess.run([cfg()["duong_dan"]["claude"], "auth", "status", "--json"], capture_output=True, text=True,
                                   encoding="utf-8", timeout=40, env=ai.env_tk(tk))
                d = json.loads(r.stdout)
                a = {"t": time.time(), "dang_nhap": bool(d.get("loggedIn")), "email": d.get("email"), "goi": d.get("subscriptionType")}
            except Exception:
                a = {"t": time.time(), "dang_nhap": False, "email": None, "goi": None}
            _AUTH_TK[tk["ma"]] = a
            if a["dang_nhap"] and st.get(tk["ma"], {}).get("dang_nhap") is False:
                ai._ghi_trang_thai(tk["ma"], dang_nhap=True); st = ai.doc_trang_thai()   # đã đăng nhập lại → dùng được ngay
        x = st.get(tk["ma"], {})
        out.append({"ma": tk["ma"], "ten": tk["ten"], "dang_nhap": a["dang_nhap"], "email": a["email"], "goi": a["goi"],
                    "five_hour": x.get("five_hour"), "seven_day": x.get("seven_day"), "het_den": x.get("het_den"), "cap_nhat": x.get("cap_nhat")})
    return out


def tai_khoan_dang_nhap(ma):
    sys.path.insert(0, str(CODE / "engine"))
    import ai
    tk = next((t for t in ai.ds_tai_khoan() if t["ma"] == ma), None)
    if not tk:
        return {"ok": False, "loi": "không có tài khoản"}
    subprocess.Popen(["cmd", "/k", cfg()["duong_dan"]["claude"], "/login"], cwd=str(HUB), env=ai.env_tk(tk),
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    _AUTH_TK.pop(ma, None)
    return {"ok": True}


def tai_khoan_them(ten):
    c = cfg(); ds = c.setdefault("tai_khoan", [{"ma": "tk1", "ten": "Tài khoản 1", "thu_muc": None}])
    n = 1
    while any(t["ma"] == f"tk{n}" for t in ds):
        n += 1
    d = HUB / "tai-khoan" / f"tk{n}"; d.mkdir(parents=True, exist_ok=True)
    ds.append({"ma": f"tk{n}", "ten": (ten or f"Tài khoản {n}").strip()[:40], "thu_muc": str(d)})
    luu_cfg(c)
    return {"ok": True, "ma": f"tk{n}"}


def tai_khoan_bo(ma):
    """Bỏ tài khoản khỏi danh sách hub dùng (không xoá thư mục đăng nhập)."""
    c = cfg(); ds = c.get("tai_khoan") or []
    if len(ds) <= 1:
        return {"ok": False, "loi": "Phải còn ít nhất 1 tài khoản"}
    c["tai_khoan"] = [t for t in ds if t["ma"] != ma]; luu_cfg(c)
    return {"ok": True}


def ds_lo(n=30):
    f = LS / "lo.jsonl"
    if not f.exists():
        return []
    out = []
    for l in f.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return list(reversed(out))


def token_video(ma_viec):
    """Token đạo diễn + giám khảo dành riêng cho 1 video (biên kịch dùng chung không tính vào)."""
    f = LS / "token.csv"
    if not ma_viec or not f.exists():
        return None
    return _token_map(f).get(ma_viec) or None


_TOKEN_MAP = {"k": None, "d": {}}


def _token_map(f):
    """{mã việc: tổng token} — đọc token.csv một lần, nhớ theo (thời điểm sửa, cỡ file) để liệt kê nhiều video không đọc lại từng lần."""
    st = f.stat(); k = (st.st_mtime_ns, st.st_size)
    if _TOKEN_MAP["k"] != k:
        d = {}
        for x in csv.DictReader(open(f, encoding="utf-8-sig")):
            try:
                d[x.get("video")] = d.get(x.get("video"), 0) + sum(int(x.get(c) or 0) for c in ("vao", "vao_cache_tao", "vao_cache_doc", "ra"))
            except ValueError:
                pass
        _TOKEN_MAP["d"], _TOKEN_MAP["k"] = d, k
    return _TOKEN_MAP["d"]


def lam_lai(ds):
    """ds: [{file, gop_y}] → chạy nền 'làm lại theo góp ý' (gom theo sản phẩm, mỗi lần 1 sản phẩm)."""
    if dang_chay():
        return {"ok": False, "loi": "Hub đang chạy một lô khác — đợi xong rồi làm lại."}
    viec = []
    for x in ds:
        v = (ra_dir() / x.get("file", "")).resolve()
        if not v.is_relative_to(ra_dir().resolve()) or not v.exists() or v.suffix != ".mp4":
            continue
        fm = kem(v, ".json")
        meta = json.loads(fm.read_text(encoding="utf-8")) if fm.exists() else {}
        viec.append({"file": str(v), "gop_y": str(x.get("gop_y", ""))[:500], "meta": meta, "ma": meta.get("ma") or v.name.split("_")[0]})
    if not viec:
        return {"ok": False, "loi": "Không tìm thấy video cần làm lại"}
    ma = viec[0]["ma"]; cung = [x for x in viec if x["ma"] == ma]
    fj = LS / f"lam-lai-{int(time.time())}.json"
    fj.write_text(json.dumps(cung, ensure_ascii=False), encoding="utf-8")
    c = cfg(); log = open(LS / "app-chay.log", "a", encoding="utf-8")
    RUN["proc"] = _popen([c["duong_dan"]["python"], "-X", "utf8", str(CODE / "engine" / "sanxuat.py"), ma, "--lam-lai", str(fj)],
                         cwd=str(HUB), stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    log.close(); RUN.update(bat_dau=time.time(), san_pham=ma, so_video=len(cung))
    con = len(viec) - len(cung)
    return {"ok": True, "so": len(cung), "con_lai": con}


def danh_gia_f():
    return LS / "danh-gia.json"


def doc_danh_gia():
    f = danh_gia_f()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


TAT_CA = "tat-ca"          # giá trị "Tất cả ngày" của ô chọn ngày trong Kho video


def video_ngay(ngay):
    """Video của 1 ngày (YYYY-MM-DD) — hoặc ngay == "tat-ca": mọi ngày, mới nhất trước. Mỗi video mang sẵn ngày + đường dẫn riêng."""
    if ngay == TAT_CA:
        d = ra_dir()
        ngays = sorted([x.name for x in d.iterdir() if x.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", x.name)], reverse=True) if d.exists() else []
        dg = doc_danh_gia()
        tp = json.loads((LS / "trypost.json").read_text(encoding="utf-8")) if (LS / "trypost.json").exists() else {}
        out = []
        for n in ngays:
            out += _video_mot_ngay(n, dg, tp)
        return out
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ngay or ""):
        return []
    return _video_mot_ngay(ngay, doc_danh_gia(), json.loads((LS / "trypost.json").read_text(encoding="utf-8")) if (LS / "trypost.json").exists() else {})


def _video_mot_ngay(ngay, dg, tp):
    d = ra_dir() / ngay
    if not d.exists():
        return []
    rows = {}
    for sheet in ("bang-ghi-ekip.csv", "bang-ghi-v2.csv", "bang-ghi.csv"):
        f = kem_ngay(d, sheet)
        if f.exists():
            for r in csv.DictReader(open(f, encoding="utf-8-sig")):
                rows.setdefault(r.get("file"), r)
    out = []
    for v in sorted(d.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
        r = rows.get(v.name, {})
        cap = kem(v, ".txt")
        parts = v.stem.split("_")
        bia = kem(v, ".jpg")
        dang = tp.get(v.stem, {})
        out.append({"ngay": ngay, "dang": dang, "file": v.name, "url": f"/file?p={ngay}/{v.name}", "bia": f"/file?p={ngay}/{bia.relative_to(d).as_posix()}" if bia.exists() else "", "san_pham": parts[0] if parts else "",
                    "goc": r.get("goc") or (parts[1] if len(parts) > 1 else ""), "gu": r.get("gu_dao_dien", ""),
                    "diem": r.get("diem_giam_khao", ""), "loi_gk": r.get("loi_giam_khao", ""), "y_tuong": r.get("y_tuong", ""),
                    "cong_thuc": r.get("cong_thuc", ""), "nhac": r.get("nhac", ""), "loi": r.get("loi", ""),
                    "caption": cap.read_text(encoding="utf-8") if cap.exists() else (r.get("caption", "") + "\n" + r.get("hashtag", "")).strip(),
                    "danh_gia": dg.get(v.name, {}), "luc": datetime.datetime.fromtimestamp(v.stat().st_mtime).strftime("%H:%M")})
        fm = kem(v, ".json")
        m = json.loads(fm.read_text(encoding="utf-8")) if fm.exists() else {}
        out[-1].update({"diem": out[-1]["diem"] or (m.get("diem") if m.get("diem") is not None else ""),
                        "thoi_luong": m.get("thoi_luong"), "ky_tu_giong": m.get("ky_tu_giong"), "dung_chung_giong": m.get("dung_chung_giong"),
                        "token": token_video(m.get("ma_viec")), "lam_lai_tu": Path(m["lam_lai_tu"]).name if m.get("lam_lai_tu") else "",
                        "duong_dan": f"{ngay}/{v.name}", "dang_bai": (m.get("kich_ban") or {}).get("dang") or m.get("dang") or ""})
    return out


def chay(sp, so, kho_them=None, giay=None):
    """kho_them: danh sách mã kho phụ anh chọn ("Dùng thêm cảnh từ kho khác"); None = giữ lựa chọn đã nhớ (tự động dùng cái này).
    Lựa chọn được ghi vào hồ sơ sản phẩm (kho_them) — engine đọc từ đó, lần sau/tự động dùng lại."""
    if dang_chay():
        return {"ok": False, "loi": "Hub đang chạy một lô khác."}
    if not co_khoa_giong():                  # kiểm TRƯỚC khi chạy: thiếu khoá giọng thì lô hỏng giữa chừng, phí hạn mức Claude
        return {"ok": False, "loi": "Chưa có khoá ElevenLabs (giọng đọc). Vào tab Cài đặt → mục \"Khoá ElevenLabs\" dán khoá rồi Lưu, sau đó chạy lại."}
    from tu_dong import san_sang
    if not san_sang(sp):
        return {"ok": False, "loi": "Sản phẩm chưa đủ hồ sơ (sự thật / quà tặng / kho cảnh) — vào tab Sản phẩm để bổ sung."}
    if giay is not None:                     # độ dài video anh chọn: nhớ vào hồ sơ sản phẩm (engine đọc sp["thoi_luong"], tự động dùng lại)
        gv, loi = kiem_thoi_luong(giay)
        if loi:
            return {"ok": False, "loi": loi}
        f = HUB / "san-pham" / sp / "san-pham.json"
        hs = json.loads(f.read_text(encoding="utf-8"))
        if hs.get("thoi_luong") != gv:
            hs["thoi_luong"] = gv
            f.write_text(json.dumps(hs, ensure_ascii=False, indent=1), encoding="utf-8")
    if kho_them is not None:
        sys.path.insert(0, str(CODE / "engine"))
        f = HUB / "san-pham" / sp / "san-pham.json"
        hs = json.loads(f.read_text(encoding="utf-8"))
        ok = [m for m in dict.fromkeys(kho_them) if isinstance(m, str) and m != sp and re.fullmatch(r"[a-z0-9-]+", m)
              and (HUB / "san-pham" / m / "canh.json").exists()]
        if hs.get("kho_them") != ok:
            hs["kho_them"] = ok
            f.write_text(json.dumps(hs, ensure_ascii=False, indent=1), encoding="utf-8")
    c = cfg()
    log = open(LS / "app-chay.log", "a", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    RUN["proc"] = _popen([c["duong_dan"]["python"], "-X", "utf8", str(CODE / "engine" / "sanxuat.py"), sp, str(so)],
                         cwd=str(HUB), stdout=log, stderr=subprocess.STDOUT, env=env)
    log.close()                                   # tiến trình con đã giữ bản riêng của file nhật ký
    RUN.update(bat_dau=time.time(), san_pham=sp, so_video=so)
    return {"ok": True}


def luu_kho_them(ma, ds):
    if not re.fullmatch(r"[a-z0-9-]+", ma or "") or not (HUB / "san-pham" / ma / "san-pham.json").exists():
        return {"ok": False, "loi": "Không có sản phẩm này"}
    f = HUB / "san-pham" / ma / "san-pham.json"
    hs = json.loads(f.read_text(encoding="utf-8"))
    ok = [m for m in dict.fromkeys(ds) if isinstance(m, str) and m != ma and re.fullmatch(r"[a-z0-9-]+", m) and (HUB / "san-pham" / m / "canh.json").exists()]
    hs["kho_them"] = ok
    f.write_text(json.dumps(hs, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "kho_them": ok}


def dung():
    p = RUN["proc"]
    pid = p.pid if (p and p.poll() is None) else pid_lo()      # lô của phiên app trước (app đã khởi động lại) cũng dừng được
    if pid:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        with open(LS / "nhat-ky.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%H:%M:%S}] ⏹ Anh đã bấm DỪNG. Video đã xong vẫn giữ nguyên.\n")
    return {"ok": True}


_KHOA_DG = threading.Lock()


def danh_gia(body):
  with _KHOA_DG:                              # bấm ✅/❌ liên tiếp không làm mất đánh giá (lỗi rà soát #11)
    dg = doc_danh_gia()
    f = body["file"]
    dg[f] = {"ket_qua": body.get("ket_qua"), "gop_y": body.get("gop_y", "").strip(), "luc": datetime.datetime.now().isoformat(timespec="minutes")}
    danh_gia_f().write_text(json.dumps(dg, ensure_ascii=False, indent=1), encoding="utf-8")
    gy = body.get("gop_y", "").strip()
    if gy:      # góp ý → sổ gu: biên kịch, đạo diễn, giám khảo đều đọc
        nhan = "ƯNG" if body.get("ket_qua") == "dat" else "KHÔNG ƯNG"
        parts = f.split("_")
        hs = {}
        try:
            for jf in glob_kem(Path(cfg()["duong_dan"]["ra"]), f"{Path(f).stem}.json"):
                hs = json.loads(jf.read_text(encoding="utf-8")); break
        except Exception:
            hs = {}
        parts = [hs.get("ma") or parts[0], hs.get("goc") or (parts[1] if len(parts) > 1 else ""), hs.get("dao_dien") or (parts[2] if len(parts) > 2 else "")]
        with open(LS / "so-gu.md", "a", encoding="utf-8") as fh:
            fh.write(f"- [{datetime.date.today():%d/%m}] Kid {nhan} ({parts[0]}, góc {parts[1] if len(parts) > 1 else ''}, "
                     f"đạo diễn {parts[2] if len(parts) > 2 else ''}): {gy}\n")
    return {"ok": True}


def mo_dang_nhap():
    c = cfg()
    subprocess.Popen(["cmd", "/k", c["duong_dan"]["claude"], "/login"], cwd=str(HUB),
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    _auth["t"] = 0
    return {"ok": True}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        # chỉ cho nhúng (iframe) từ chính app + TikTok Auto (config "nhung_tu"); trang lạ không nhúng được (chống clickjacking)
        try:
            ds = cfg().get("nhung_tu", NHUNG_MAC_DINH)
        except Exception:
            ds = NHUNG_MAC_DINH
        self.send_header("Content-Security-Policy", "frame-ancestors 'self' " + " ".join(ds))
        super().end_headers()

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _file(self, path):
        if not path.exists() or not path.is_file():
            self.send_error(404); return
        size = path.stat().st_size
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        a, b = 0, size - 1
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                a = int(m.group(1) or 0); b = int(m.group(2)) if m.group(2) else size - 1
            self.send_response(206); self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") else ""))
        if ctype.startswith("text/html"):
            self.send_header("Cache-Control", "no-store")   # luôn tải giao diện mới nhất (khỏi phải Ctrl+F5)
        self.send_header("Accept-Ranges", "bytes"); self.send_header("Content-Length", str(b - a + 1)); self.end_headers()
        with open(path, "rb") as f:
            f.seek(a); left = b - a + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk); left -= len(chunk)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                pass

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path in ("/health", "/api/health"):           # cho launcher TikTokAuto.exe giám sát
            p = RUN["proc"]
            return self._json({"ok": True, "app": "xuong-video", "pid": os.getpid(), "cong": PORT,
                               "cong_trypost": cfg().get("trypost", {}).get("cong"), "bat_dau_app": BAT_DAU_APP,
                               "dang_chay_lo": bool(dang_chay()), "pid_lo": (p.pid if p and p.poll() is None else pid_lo()),
                               "san_pham_lo": RUN.get("san_pham")})
        if u.path in ("/", "/index.html"):
            return self._file(WEB / "index.html")
        if u.path.startswith("/web/"):
            p = (WEB / unquote(u.path[5:])).resolve()
            return self._file(p) if p.is_relative_to(WEB.resolve()) else self.send_error(403)
        if u.path == "/file":      # chỉ phục vụ file trong thư mục ra/
            p = (ra_dir() / unquote(q.get("p", [""])[0])).resolve()
            return self._file(p) if p.is_relative_to(ra_dir().resolve()) else self.send_error(403)
        if u.path == "/api/trang-thai":
            lines = nhat_ky_lo(); c = cfg()
            nk = LS / "nhat-ky.txt"
            td = tien_do(lines)
            ngoai = (not dang_chay()) and bool(lines) and not td["da_xong"] and not td["het_han_muc"] \
                and nk.exists() and time.time() - nk.stat().st_mtime < 240 and not any("DỪNG" in l for l in lines[-2:])
            return self._json({"dang_chay": dang_chay() or ngoai, "chay_ngoai_app": ngoai, "bat_dau": RUN["bat_dau"], "tien_do": td,
                               "nhat_ky": lines[-120:], "claude": c.get("claude", {}), "san_pham": san_pham_ds(), "thoi_luong_mac_dinh": thoi_luong_mac_dinh(),
                               "token": token_hom_nay(),
                               "tai_khoan_dung": c.get("tai_khoan_dung", "tu_dong"), "tu_duyet": c.get("tu_duyet", {"bat": False, "dat_tu": 7, "bo_duoi": 0}), "tu_chuyen": c.get("tu_chuyen", True), "video_moi_giong": c["lo"]["video_moi_giong"]})
        if u.path == "/api/su-kien":           # trang "Xưởng nhỏ": sự kiện sản xuất mới + trạng thái hiện tại (chỉ đọc)
            sys.path.insert(0, str(CODE / "engine"))
            import su_kien
            try:
                sau = int(q.get("sau", ["0"])[0] or 0)
            except ValueError:
                sau = 0
            try:
                toi_da = max(1, min(1500, int(q.get("max", ["300"])[0] or 300)))
            except ValueError:
                toi_da = 300
            lines = nhat_ky_lo(); td = tien_do(lines); chay = bool(dang_chay())
            ma_sp, ten_sp = RUN.get("san_pham"), None
            try:
                k = LS / "dang-chay.lock"
                if not ma_sp and k.exists():
                    cot = k.read_text().split(None, 1); ma_sp = cot[1].strip() if len(cot) > 1 else None
                if ma_sp:
                    ten_sp = next((p.get("ten_ngan") or p.get("ten") for p in san_pham_ds() if p.get("ma") == ma_sp), None)
            except Exception:
                pass
            return self._json({"ok": True, "dang_chay": chay, "tien_do": td, "san_pham": {"ma": ma_sp, "ten": ten_sp or ma_sp},
                               "su_kien": su_kien.doc(sau, toi_da), "bay_gio": time.time()})
        if u.path == "/api/tai-khoan-ds":
            return self._json(tai_khoan_ds("moi" in parse_qs(u.query)))
        if u.path == "/api/tai-khoan":
            return self._json(auth(force="moi" in q))
        if u.path == "/api/ngay":
            d = ra_dir()
            ds = sorted([x.name for x in d.iterdir() if x.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", x.name)], reverse=True) if d.exists() else []
            return self._json(ds)
        if u.path == "/api/video":
            return self._json(video_ngay(q.get("ngay", [datetime.date.today().isoformat()])[0]))
        if u.path.startswith("/api/lenh-gemini/"):
            return self._json({"lenh": lenh_gemini(u.path.split("/")[-1])})
        if u.path.startswith("/api/hoc-canh/"):
            try:
                return self._json(hoc_canh_trang_thai(u.path.split("/")[-1]))
            except Exception as e:
                return self._json({"loi": str(e)[:200]})
        if u.path.startswith("/api/kiem-dinh/"):
            return self._json(KD.get(u.path.split("/")[-1]) or {"dang_chay": False, "bao_cao": None})
        if u.path.startswith("/api/kho/"):
            return self._json(kho_trang_thai(u.path.split("/")[-1]))
        if u.path.startswith("/api/san-pham/"):
            f = HUB / "san-pham" / u.path.split("/")[-1] / "san-pham.json"
            return self._json(json.loads(f.read_text(encoding="utf-8")) if f.exists() else {})
        if u.path == "/api/thu-muc":        # trình chọn thư mục: CHỈ LIỆT KÊ (không ghi/xoá gì), chỉ nhận Host của chính app
            if (self.headers.get("Host") or "").lower() not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
                return self._json({"ok": False, "loi": "Yêu cầu không hợp lệ"}, 403)
            return self._json(anh_sp.liet_ke_thu_muc(q["p"][0] if "p" in q else None))
        if u.path == "/api/nhac":
            return self._json(nhac_trang_thai())
        if u.path == "/api/khoa-giong":
            return self._json(khoa_giong_trang_thai())
        if u.path == "/api/giong":
            return self._json(giong_trang_thai())
        if u.path == "/api/giong-mau":
            return self._json(giong_mau(q.get("id", [""])[0]))
        if u.path == "/api/giong-tai-khoan":
            return self._json(giong_tai_khoan())
        if u.path == "/api/hieu-qua":         # số liệu thật TikTok → AI (engine/hieu_qua.py)
            sys.path.insert(0, str(CODE / "engine"))
            try:
                from hieu_qua import bao_cao
                return self._json({"ok": True, **bao_cao(q.get("ma", [""])[0])})
            except Exception as e:
                return self._json({"ok": False, "loi": f"{type(e).__name__}: {e}"})
        if u.path == "/api/shop-sp":          # sản phẩm TikTok Shop (từ app TikTok Auto) để chọn khi thêm sản phẩm
            ds = anh_sp.ds_shop("moi" in q)
            return self._json({"ok": ds is not None, "ds": [{"id": x["id"], "tieu_de": x["tieu_de"], "ten_ngan": x["ten_ngan"], "gia": x["gia"], "ma": x["ma"],
                                                          "anh": f"/api/shop-anh/{x['id']}?v={x['anh_v']}" if x["co_anh"] else None} for x in ds or []],
                               "loi": None if ds is not None else "Chưa kết nối được TikTok Auto (đang tắt?). Bật app rồi bấm Tải lại."})
        if u.path.startswith("/api/shop-anh/"):
            data, ext = anh_sp.anh_shop_bytes(u.path.split("/")[-1])
            if not data:
                return self._json({"ok": False, "loi": "chưa có ảnh"}, 404)
            self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type("x" + ext)[0] or "image/jpeg")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        if u.path.startswith("/api/anh-sp/"):
            f = anh_sp.lay_anh(u.path.split("/")[-1])
            if not f:
                return self._json({"ok": False, "loi": "chưa có ảnh"}, 404)
            b = f.read_bytes()
            self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type(str(f))[0] or "image/jpeg")
            self.send_header("Cache-Control", "public, max-age=31536000, immutable" if "v" in q else "no-cache")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if u.path == "/api/tong-quan":
            return self._json(tong_quan("moi" in parse_qs(u.query)))
        if u.path == "/api/lo":
            return self._json(ds_lo())
        if u.path == "/api/tu-dong":
            from tu_dong import bao_cao
            return self._json(bao_cao())
        if u.path == "/api/trypost":
            t = cfg().get("trypost", {})
            return self._json({"cong": t.get("cong"), "dia_chi": f"http://127.0.0.1:{t.get('cong')}", "bat": bool(t.get("khoa"))})
        if u.path == "/api/o-dia":
            sys.path.insert(0, str(CODE / "engine"))
            from don_dep import dung_luong
            return self._json(dung_luong())
        if u.path == "/api/prompt":
            return self._json(prompt_ds())
        if u.path == "/api/prompt/mac-dinh":
            return self._json(prompt_mac_dinh(q.get("ten", [""])[0]))
        if u.path == "/api/prompt/ban-cu":
            return self._json(prompt_ban_cu(q.get("ten", [""])[0]))
        if u.path == "/api/so-gu":
            f = LS / "so-gu.md"; bh = LS / "bai-hoc.txt"
            return self._json({"so_gu": f.read_text(encoding="utf-8") if f.exists() else "",
                               "bai_hoc": bh.read_text(encoding="utf-8") if bh.exists() else ""})
        self.send_error(404)

    def _hop_le(self):
        """Chỉ nhận lệnh từ chính giao diện app: đúng Host, đúng Origin (nếu có), gửi JSON (chặn trang web lạ — lỗi rà soát #17)."""
        host = (self.headers.get("Host") or "").lower()
        if host not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
            return False
        org = self.headers.get("Origin")
        if org and org.lower() not in (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"):
            return False
        return "application/json" in (self.headers.get("Content-Type") or "").lower()

    def do_POST(self):
        if not self._hop_le():
            return self._json({"ok": False, "loi": "Yêu cầu không hợp lệ"}, 403)
        u = urlparse(self.path); b = self._body()
        if u.path == "/api/chay":
            return self._json(chay(b["san_pham"], max(1, min(200, int(b.get("so_video", 4)))), b.get("kho_them") if isinstance(b.get("kho_them"), list) else None,
                                    b.get("giay") if "giay" in b else None))
        if u.path.startswith("/api/xoa-san-pham/"):
            return self._json(xoa_san_pham(u.path.split("/")[-1]))
        if u.path == "/api/lam-lai":
            return self._json(lam_lai(b.get("ds") or []))
        if u.path == "/api/kho-them":           # nhớ lựa chọn "Dùng thêm cảnh từ kho khác" cho 1 sản phẩm (tự động cũng dùng)
            return self._json(luu_kho_them(b.get("san_pham", ""), b.get("kho_them") or []))
        if u.path == "/api/tu-duyet":
            c = cfg(); td = c.setdefault("tu_duyet", {"bat": False, "dat_tu": 7, "bo_duoi": 0})
            for k in ("bat",):
                if k in b: td[k] = bool(b[k])
            for k in ("dat_tu", "bo_duoi"):
                if k in b: td[k] = max(0, min(10, float(b[k])))
            luu_cfg(c)
            n = 0
            if b.get("ap_dung") and td.get("bat"):
                sys.path.insert(0, str(CODE / "engine")); from duyet import tu_duyet
                n = tu_duyet(lambda *_: None)
            return self._json({"ok": True, "da_duyet": n, "tu_duyet": td})
        if u.path == "/api/dem-lai":
            (LS / "moc-dem.txt").write_text(datetime.datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
            return self._json({"ok": True})
        if u.path == "/api/san-pham-moi":
            return self._json(tao_san_pham(b))
        if u.path == "/api/anh-khung":          # cắt thử 1 khung từ video trong thư mục kho (chưa lưu) → trả ảnh để xem
            kho = str(b.get("kho") or "").strip().strip('"')
            im = anh_sp.khung_xem_truoc(kho) if kho else None
            if not im:
                return self._json({"ok": False, "loi": "Không lấy được ảnh: thư mục chưa đúng hoặc chưa có video (.mp4/.mov)."})
            import base64
            return self._json({"ok": True, "data": "data:image/jpeg;base64," + base64.b64encode(im).decode()})
        if u.path.startswith("/api/anh-sp/"):
            ma = u.path.split("/")[-1]
            if not anh_sp.ma_hop_le(ma) or not (HUB / "san-pham" / ma / "san-pham.json").exists():
                return self._json({"ok": False, "loi": "Không có sản phẩm này"}, 404)
            if b.get("tu_shop"):
                f, err = anh_sp.dat_tu_shop(ma, str(b["tu_shop"]))
                if f:
                    sj = HUB / "san-pham" / ma / "san-pham.json"
                    sp = json.loads(sj.read_text(encoding="utf-8")); sp["shop_product_id"] = str(b["tu_shop"])
                    sj.write_text(json.dumps(sp, ensure_ascii=False, indent=1), encoding="utf-8")
            elif b.get("tu_video"):
                f = anh_sp.tao_tu_video(ma, ngau_nhien=True)
                err = None if f else "Không lấy được ảnh: chưa có thư mục kho hoặc chưa có video (.mp4/.mov) trong đó."
            else:
                f, err = anh_sp.luu_tai_len(ma, b.get("data", ""))
            _TQ["t"] = 0
            return self._json({"ok": True, "url": anh_sp.url_anh(ma)} if f else {"ok": False, "loi": err})
        if u.path.startswith("/api/doc-nhan/"):
            sys.path.insert(0, str(CODE / "engine"))
            try:
                from doc_nhan import doc
                return self._json(doc(u.path.split("/")[-1]))
            except Exception as e:
                return self._json({"loi": str(e)[:200]})
        if u.path.startswith("/api/hoc-canh/"):
            return self._json(hoc_canh_bat_dau(u.path.split("/")[-1]))
        if u.path == "/api/hoc-canh-dung":
            import hoc_canh; return self._json(hoc_canh.dung())
        if u.path.startswith("/api/hoc-canh-quyen/"):
            return self._json(hoc_canh_quyen(u.path.split("/")[-1]))
        if u.path == "/api/agy-mo":
            import hoc_canh; return self._json(hoc_canh.mo_antigravity())
        if u.path == "/api/hoc-canh-model":
            import hoc_canh
            m = str(b.get("model", "")).strip()
            if m not in hoc_canh.MODELS:
                return self._json({"ok": False, "loi": "Model không hợp lệ."})
            c = cfg(); hc = c.setdefault("hoc_canh", {}); hc["model"] = m; hc.pop("muc", None)
            luu_cfg(c); return self._json({"ok": True})
        if u.path.startswith("/api/kiem-dinh/"):
            return self._json(kiem_dinh(u.path.split("/")[-1], bool(b.get("sua"))))
        if u.path.startswith("/api/chuan-bi-kho/"):
            return self._json(chuan_bi_kho(u.path.split("/")[-1]))
        if u.path == "/api/dung":
            return self._json(dung())
        if u.path == "/api/danh-gia":
            return self._json(danh_gia(b))
        if u.path.startswith("/api/tai-khoan-dang-nhap/"):
            return self._json(tai_khoan_dang_nhap(u.path.split("/")[-1]))
        if u.path == "/api/tai-khoan-them":
            return self._json(tai_khoan_them(b.get("ten", "")))
        if u.path.startswith("/api/tai-khoan-bo/"):
            return self._json(tai_khoan_bo(u.path.split("/")[-1]))
        if u.path.startswith("/api/tai-khoan-kiem/"):
            sys.path.insert(0, str(CODE / "engine"))
            import ai
            try:
                with _KIEM_LOCK:                 # không chạy 2 lần kiểm cùng lúc
                    return self._json({"ok": True, "trang_thai": ai.kiem_han_muc(u.path.split("/")[-1])})
            except Exception as e:
                return self._json({"ok": False, "loi": str(e)[:200]})
        if u.path == "/api/dang-nhap":
            return self._json(mo_dang_nhap())
        if u.path == "/api/nhac-nguon":
            return self._json(nhac_nguon_sua(b))
        if u.path == "/api/khoa-giong":
            return self._json(khoa_giong_luu(b.get("khoa")))
        if u.path == "/api/giong":
            return self._json(giong_luu(b))
        if u.path == "/api/nhac-tai":
            return self._json(nhac_tai_bat_dau())
        if u.path == "/api/mo-thu-muc":
            d = ra_dir() / b.get("ngay", "")
            subprocess.Popen(["explorer", str(d if d.exists() else ra_dir())]); return self._json({"ok": True})
        if u.path == "/api/cai-dat":
            c = cfg()
            if b.get("model") in ("opus", "sonnet"):
                c.setdefault("claude", {})["model"] = b["model"]
            if b.get("effort") in ("low", "medium", "high"):
                c.setdefault("claude", {})["effort"] = b["effort"]
            if "tai_khoan_dung" in b:
                c["tai_khoan_dung"] = str(b["tai_khoan_dung"])
            if "tu_chuyen" in b:
                c["tu_chuyen"] = bool(b["tu_chuyen"])
            if b.get("video_moi_giong") in (1, 2, 3):
                c["lo"]["video_moi_giong"] = b["video_moi_giong"]
            luu_cfg(c); return self._json({"ok": True})
        if u.path.startswith("/api/san-pham/"):
            ma = u.path.split("/")[-1]
            f = HUB / "san-pham" / ma / "san-pham.json"
            if not f.exists():
                return self._json({"ok": False, "loi": "không có sản phẩm"}, 404)
            sp = json.loads(f.read_text(encoding="utf-8"))
            if b.get("kho"):
                sp["kho_video"] = b["kho"].strip().strip('"')
            if "tron_mac_dinh" in b:
                sp["tron_mac_dinh"] = bool(b["tron_mac_dinh"])
            if re.fullmatch(r"[0-9]{1,32}", str(b.get("shop_product_id") or "")):
                sp["shop_product_id"] = str(b["shop_product_id"])
            if "ten_gio" in b:
                sp["ten_gio"] = str(b["ten_gio"]).strip().upper()[:30]   # tên sản phẩm trên giỏ hàng TikTok (app TikTok Auto dùng)
            if str(b.get("ten_ngan") or "").strip():                       # tên gọi ngắn AI đọc trong video (bắt buộc có trong lời)
                sp["ten_ngan"] = " ".join(str(b["ten_ngan"]).split())[:40]
            if "doc_la" in b:                                               # cách đọc tên cho giọng đọc: {chữ viết: cách đọc}; rỗng → bỏ khoá
                dl = doc_la_tu_text(b["doc_la"]) if isinstance(b["doc_la"], str) else {}
                if dl:
                    sp["doc_la"] = dl
                else:
                    sp.pop("doc_la", None)
            for k in ("qua_tang", "khong_duoc_noi", "su_that_duoc_noi"):
                if isinstance(b.get(k), list):
                    sp[k] = [x.strip() for x in b[k] if str(x).strip()]
            f.write_text(json.dumps(sp, ensure_ascii=False, indent=1), encoding="utf-8")
            return self._json({"ok": True})
        if u.path == "/api/tu-dong":
            c = cfg(); td = c.setdefault("tu_dong", {"bat": False, "kiem_moi_phut": 15, "san_pham": {}})
            if "bat" in b:
                td["bat"] = bool(b["bat"])
            if b.get("kiem_moi_phut"):
                td["kiem_moi_phut"] = max(5, int(b["kiem_moi_phut"]))
            for ma, v in (b.get("san_pham") or {}).items():
                td["san_pham"][ma] = {"bat": bool(v.get("bat", True)), "ton_toi_thieu": max(0, int(v.get("ton_toi_thieu", 10))),
                                      "toi_da_ngay": max(0, int(v.get("toi_da_ngay", 30))), "lo": max(1, min(50, int(v.get("lo", 10))))}
            luu_cfg(c); return self._json({"ok": True})
        if u.path == "/api/prompt":
            return self._json(prompt_luu(b.get("ten", ""), b.get("text")))
        if u.path == "/api/prompt/khoi-phuc":
            return self._json(prompt_khoi_phuc(b.get("ten", "")))
        if u.path == "/api/prompt/xem-thu":
            return self._json(prompt_xem_thu(b.get("ten", ""), b.get("ma_sp", ""), b.get("text")))
        if u.path == "/api/so-gu":
            (LS / "so-gu.md").write_text(b.get("so_gu", ""), encoding="utf-8"); return self._json({"ok": True})
        self.send_error(404)


KIEM_HAN_MUC_GIAY = 7 * 60
_KIEM_LOCK = threading.Lock()


def _cua_so_dang_mo(x):
    """Tài khoản có cửa sổ 5 giờ ĐANG chạy (reset ở tương lai và đã dùng > 0) → đáng tự kiểm.
    Chưa biết / đã quá giờ reset / dùng 0% → bỏ qua (nút "Kiểm hạn mức" vẫn kiểm tay được)."""
    fh = x.get("five_hour") or {}
    try:
        return float(fh.get("reset") or 0) > time.time() and float(fh.get("pct") or 0) > 0
    except (TypeError, ValueError):
        return False


def _vong_kiem_han_muc():
    """Nền: mỗi ~7 phút kiểm hạn mức từng tài khoản (tuần tự, mỗi lần 1 câu rất ngắn). Lô đang chạy → bỏ qua (lô tự cập nhật hạn mức)."""
    time.sleep(45)                                   # chờ app lên xong rồi mới kiểm lần đầu
    while True:
        try:
            if not dang_chay() and _KIEM_LOCK.acquire(blocking=False):
                try:
                    sys.path.insert(0, str(CODE / "engine"))
                    import ai
                    st = ai.doc_trang_thai()
                    for tk in list(ai.ds_tai_khoan()):
                        if dang_chay():
                            break
                        if not _cua_so_dang_mo(st.get(tk["ma"]) or {}):
                            continue                 # cửa sổ 5 giờ đã reset / chưa dùng: gọi lúc này = mở cửa sổ mới vô ích
                        try:
                            ai.kiem_han_muc(tk["ma"])
                        except Exception as e:
                            print(f"[{datetime.datetime.now():%H:%M:%S}] Kiểm hạn mức {tk.get('ma')} lỗi: {str(e)[:120]}")
                finally:
                    _KIEM_LOCK.release()
        except Exception as e:
            try:
                print("Vòng kiểm hạn mức lỗi:", str(e)[:120])
            except Exception:
                pass
        time.sleep(KIEM_HAN_MUC_GIAY)


def main():
    """Tuỳ chọn: --khong-mo (không tự mở trình duyệt — dùng khi chạy dưới launcher), --log <file> (ghi nhật ký app ra file)."""
    from duong_dan import khoi_tao
    khoi_tao()                                   # thư mục dữ liệu trống → tạo từ mau/
    LS.mkdir(exist_ok=True)
    if "--log" in sys.argv:
        i = sys.argv.index("--log")
        if i + 1 < len(sys.argv):
            f_log = LS / "app.log" if sys.argv[i + 1] == "auto" else Path(sys.argv[i + 1])
            f_log.parent.mkdir(parents=True, exist_ok=True)
            fh = open(f_log, "a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = fh
    import socket
    with socket.socket() as so:                  # app đã mở rồi → không chạy bản thứ hai
        if so.connect_ex(("127.0.0.1", PORT)) == 0:
            print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] Xưởng Video đã đang mở ở cổng {PORT} — không mở bản thứ hai.")
            if "--khong-mo" not in sys.argv:
                webbrowser.open(f"http://127.0.0.1:{PORT}")
            sys.exit(3)                          # mã 3 = đã có bản khác đang chạy (launcher: đừng khởi động lại liên tục)
    ThreadingHTTPServer.allow_reuse_address = False
    try:                                   # mở app là tự dọn file tạm cũ
        sys.path.insert(0, str(CODE / "engine"))
        from don_dep import don
        don()
    except Exception:
        pass
    try:                                   # gom json/jpg/txt/csv cũ trong ra/<ngày>/ vào _kem/ (bỏ qua khi đang có lô chạy)
        nk = LS / "nhat-ky.txt"
        lo_chay = dang_chay() or (nk.exists() and time.time() - nk.stat().st_mtime < 240)
        kq = don_kem_cu(ra_dir(), dang_chay=lo_chay)
        print(f"[kem] chuyển {kq['da_chuyen']} file vào _kem ({kq['ngay']} ngày, bỏ qua {kq['bo_qua']})" + (" — đang có lô chạy nên chưa làm" if lo_chay else ""))
    except Exception as e:
        print("Không gom được file kèm:", e)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    try:                                   # tự động giữ kho video
        from tu_dong import bat_dau
        bat_dau(dang_chay, chay)
    except Exception as e:
        print("Không bật được tự động:", e)
    threading.Thread(target=_vong_kiem_han_muc, daemon=True, name="kiem-han-muc").start()
    try:                                   # cổng cho app TikTok Auto — cần X-Key, chỉ nghe loopback
        from cong_trypost import chay_nen
        if chay_nen():
            print(f"Cổng app TikTok Auto: 127.0.0.1:{cfg().get('trypost', {}).get('cong', 8766)}")
    except Exception as e:
        print("Không mở được cổng app TikTok Auto:", e)
    if "--khong-mo" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] Xưởng Video đang chạy: http://127.0.0.1:{PORT}  (đóng cửa sổ này = tắt app)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:                # Ctrl+C / CTRL_BREAK → tắt êm; lô đang chạy (tiến trình riêng) vẫn làm tiếp
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
