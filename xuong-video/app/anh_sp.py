"""ẢNH SẢN PHẨM + DUYỆT THƯ MỤC (chỉ đọc) cho Xưởng Video.
- Ảnh lưu ở san-pham/<mã>/anh.jpg (hoặc .png/.webp), kèm anh.nguon.json ghi nguồn. Ưu tiên: (a) ảnh người dùng tải lên, (b) ẢNH THẬT trên TikTok Shop của sản phẩm đã gắn mã này (lấy từ app TikTok Auto), (c) khung hình từ video — chỉ là phương án cuối.
- Ảnh không có file nguồn (làm từ trước) được coi là khung hình từ video và sẽ được thay bằng ảnh Shop khi có.
- liet_ke_thu_muc: chỉ LIỆT KÊ ổ đĩa/thư mục con + đếm video, không bao giờ ghi/xoá gì."""
import base64, json, os, random, re, string, subprocess, sys, tempfile, threading, time
import urllib.request
from collections import Counter
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
SP = HUB / "san-pham"
EXT_ANH = (".jpg", ".jpeg", ".png", ".webp")
EXT_VIDEO = (".mp4", ".mov")
TOI_DA_BYTE = 8 * 1024 * 1024
_KHOA = threading.Lock()
_THAT_BAI = {}                                   # mã → lúc thử lấy ảnh tự động thất bại (đừng thử lại mỗi vài giây)
_CNW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def ma_hop_le(ma):
    return bool(re.fullmatch(r"[a-z0-9-]+", ma or ""))


def tim_anh(ma):
    if not ma_hop_le(ma):
        return None
    for e in EXT_ANH:
        f = SP / ma / ("anh" + e)
        if f.is_file():
            return f
    return None


def url_anh(ma):
    """Đường dẫn ảnh kèm số phiên bản (đổi ảnh là đổi số → trình duyệt tải lại)."""
    f = tim_anh(ma)
    try:
        v = int(f.stat().st_mtime) if f else 0
    except OSError:
        v = 0
    return f"/api/anh-sp/{ma}?v={v}"


def kho_cua(ma):
    try:
        sp = json.loads((SP / ma / "san-pham.json").read_text(encoding="utf-8"))
        return Path(sp["kho_video"]) if sp.get("kho_video") else None
    except Exception:
        return None


def ds_video_kho(kho, toi_da=400):
    out = []
    try:
        for g, dirnames, filenames in os.walk(kho, onerror=lambda e: None):
            dirnames[:] = sorted(n for n in dirnames if not n.startswith("_"))
            for n in sorted(filenames):
                if n.lower().endswith(EXT_VIDEO):
                    out.append(Path(g) / n)
                    if len(out) >= toi_da:
                        return out
    except OSError:
        pass
    return out


def _thoi_luong(v):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)],
                           capture_output=True, text=True, timeout=20, creationflags=_CNW)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _cat_khung(video, giay, out):
    """Cùng cách gọi ffmpeg như engine (lệnh 'ffmpeg' trong PATH). True nếu ra được file ảnh."""
    for t in (giay, 0.5):
        try:
            if os.path.exists(out):
                os.remove(out)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", "scale='min(480,iw)':-2", "-q:v", "3", str(out)],
                           capture_output=True, timeout=90, creationflags=_CNW)
        except Exception:
            pass
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return True
    return False


def _chon_khung(kho, ngau_nhien):
    vs = ds_video_kho(kho)
    if not vs:
        return None, 0
    v = random.choice(vs) if ngau_nhien else vs[0]
    d = _thoi_luong(v)
    t = (d * (random.uniform(0.15, 0.7) if ngau_nhien else 0.3)) if d > 1 else 1.0
    return v, t


def khung_xem_truoc(kho, ngau_nhien=True):
    """Cắt 1 khung từ video trong thư mục kho, trả bytes jpg (không lưu đâu cả)."""
    kho = Path(kho)
    if not kho.is_dir():
        return None
    v, t = _chon_khung(kho, ngau_nhien)
    if not v:
        return None
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "k.jpg")
        return Path(out).read_bytes() if _cat_khung(v, t, out) else None


def doc_nguon(ma):
    """'upload' | 'shop' | 'video' (không có file nguồn = ảnh cũ cắt từ video) + thông tin kèm theo."""
    try:
        j = json.loads((SP / ma / "anh.nguon.json").read_text(encoding="utf-8"))
        if j.get("nguon") in ("upload", "shop", "video"):
            return j
    except Exception:
        pass
    return {"nguon": "video"}


def _dat_anh(ma, ext, data, nguon="video", them=None):
    d = SP / ma
    for e in EXT_ANH:                            # chỉ giữ 1 ảnh
        try:
            (d / ("anh" + e)).unlink()
        except OSError:
            pass
    f = d / ("anh" + ext)
    tmp = d / "anh.tmp"
    tmp.write_bytes(data)
    os.replace(tmp, f)
    try:
        (d / "anh.nguon.json").write_text(json.dumps({"nguon": nguon, **(them or {})}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return f


def tao_tu_video(ma, ngau_nhien=False):
    kho = kho_cua(ma)
    if not kho or not kho.is_dir():
        return None
    v, t = _chon_khung(kho, ngau_nhien)
    if not v:
        return None
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "k.jpg")
        if not _cat_khung(v, t, out):
            return None
        return _dat_anh(ma, ".jpg", Path(out).read_bytes(), "video")


def lay_anh(ma):
    """Ảnh của sản phẩm. Ưu tiên: ảnh tải lên > ảnh thật Shop > khung video (lười, có nhớ)."""
    f = tim_anh(ma)
    if not ma_hop_le(ma) or not (SP / ma / "san-pham.json").exists():
        return f
    if f and doc_nguon(ma)["nguon"] != "video":
        return f
    with _KHOA:
        f = tim_anh(ma)
        if f and doc_nguon(ma)["nguon"] != "video":
            return f
        g = _dat_tu_shop(ma, f)                  # lặng lẽ: TikTok Auto tắt thì thôi
        if g:
            return g
        if f:
            return f
        if time.time() - _THAT_BAI.get(ma, 0) < 120:
            return None
        try:
            f = tao_tu_video(ma)
        except Exception:
            f = None
        if not f:
            _THAT_BAI[ma] = time.time()
        return f


def luu_tai_len(ma, b64):
    """b64: base64 hoặc data URL. Kiểm đúng là ảnh (jpg/png/webp), ≤ 8 MB."""
    if not ma_hop_le(ma) or not (SP / ma / "san-pham.json").exists():
        return None, "Không có sản phẩm này"
    try:
        data = base64.b64decode(str(b64).split(",", 1)[-1], validate=False)
    except Exception:
        return None, "File ảnh không đọc được"
    if len(data) > TOI_DA_BYTE:
        return None, "Ảnh nặng quá (tối đa 8 MB)"
    if data[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        ext = ".png"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = ".webp"
    else:
        return None, "Chỉ nhận ảnh JPG, PNG hoặc WEBP"
    with _KHOA:
        _THAT_BAI.pop(ma, None)
        return _dat_anh(ma, ext, data, "upload"), None


# ---------------------------------------------------------------- duyệt thư mục (CHỈ ĐỌC)
_BO_QUA = {"$recycle.bin", "system volume information", "recovery", "config.msi", "$windows.~bt", "$windows.~ws"}


def _o_dia():
    out = []
    try:
        import ctypes
        k = ctypes.windll.kernel32
        mask = k.GetLogicalDrives()
        for i, c in enumerate(string.ascii_uppercase):
            if mask & (1 << i):
                goc = f"{c}:\\"
                if k.GetDriveTypeW(goc) not in (2, 3, 4):          # ổ rời / ổ cứng / ổ mạng; bỏ đĩa CD, RAM…
                    continue
                nhan = ctypes.create_unicode_buffer(261)
                ten = ""
                if k.GetVolumeInformationW(goc, nhan, 261, None, None, None, None, 0):
                    ten = nhan.value
                out.append({"ten": goc, "mo_ta": ten, "duong_dan": goc, "so_video": None})
    except Exception:
        out = [{"ten": f"{c}:\\", "mo_ta": "", "duong_dan": f"{c}:\\", "so_video": None}
               for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]
    return out


def _an(e):
    try:
        a = getattr(e.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(a & 0x2 or a & 0x4)                        # Hidden | System
    except OSError:
        return False


def _dem_video(p, tran=9999):
    n = 0
    try:
        with os.scandir(p) as it:
            for e in it:
                if e.name.lower().endswith(EXT_VIDEO):
                    try:
                        if e.is_file():
                            n += 1
                    except OSError:
                        pass
                    if n >= tran:
                        break
    except OSError:
        return None
    return n


def thu_muc_goi_y():
    """Thư mục cha hay gặp nhất của các kho video đang có (để mở trình chọn đúng chỗ)."""
    c = Counter()
    try:
        for f in SP.glob("*/san-pham.json"):
            try:
                k = json.loads(f.read_text(encoding="utf-8")).get("kho_video")
                if k and Path(k).parent.is_dir() and Path(k).parent != Path(k):
                    c[str(Path(k).parent)] += 1
            except Exception:
                pass
    except OSError:
        pass
    return c.most_common(1)[0][0] if c else None


def liet_ke_thu_muc(p=None):
    """p None → gợi ý (cha của các kho hiện có) hoặc danh sách ổ đĩa; p == '@' → danh sách ổ đĩa."""
    if p is None or str(p).strip() == "":
        p = thu_muc_goi_y() or "@"
    p = str(p).strip().strip('"')
    if p == "@":
        return {"ok": True, "duong_dan": "", "cha": None, "duong": [], "muc": _o_dia(), "la_o_dia": True, "so_video": None}
    if not re.match(r"^[A-Za-z]:[\\/]|^\\\\", p):
        p0 = thu_muc_goi_y() or "@"
        return liet_ke_thu_muc(p0) if p0 != p else {"ok": False, "loi": "Đường dẫn không hợp lệ."}
    cur = Path(os.path.normpath(p))
    if not cur.is_dir():
        # đường dẫn gõ sai/không còn → lùi lên thư mục cha gần nhất có thật
        for q in cur.parents:
            if q.is_dir():
                cur = q
                break
        else:
            return {"ok": False, "loi": "Không tìm thấy thư mục này.", "cha": "@", "duong": [], "muc": [], "duong_dan": str(cur)}
    muc, cat_bot = [], False
    t0 = time.time()
    try:
        with os.scandir(cur) as it:
            ents = []
            for e in it:
                try:
                    if e.is_dir() and e.name.lower() not in _BO_QUA and not _an(e):
                        ents.append(e)
                except OSError:
                    pass
    except PermissionError:
        return {"ok": False, "loi": "Không mở được thư mục này (không có quyền).", "duong_dan": str(cur),
                "cha": str(cur.parent) if cur.parent != cur else "@", "duong": _duong(cur), "muc": []}
    except OSError as e:
        return {"ok": False, "loi": "Không mở được thư mục này.", "duong_dan": str(cur),
                "cha": str(cur.parent) if cur.parent != cur else "@", "duong": _duong(cur), "muc": []}
    ents.sort(key=lambda e: e.name.lower())
    if len(ents) > 500:
        ents, cat_bot = ents[:500], True
    for e in ents:
        n = _dem_video(e.path) if time.time() - t0 < 4 else None       # quá lâu thì thôi không đếm tiếp
        muc.append({"ten": e.name, "duong_dan": e.path, "so_video": n})
    return {"ok": True, "duong_dan": str(cur), "cha": str(cur.parent) if cur.parent != cur else "@", "duong": _duong(cur),
            "muc": muc, "la_o_dia": False, "so_video": _dem_video(cur), "cat_bot": cat_bot}


def _duong(cur):
    chain = [q for q in reversed(cur.parents)] + [cur]
    return [{"ten": (str(q) if q.parent == q else q.name), "duong_dan": str(q)} for q in chain]


# ---------------------------------------------------------------- ẢNH THẬT TỪ TIKTOK SHOP (đọc từ app TikTok Auto)
_CC = HUB / "config.json"
_FEED = {"t": 0.0, "ds": None, "loi": 0.0}        # bộ nhớ đệm danh sách sản phẩm Shop (ds=None: chưa có)
_CACHE_ANH = HUB / "cache-shop-anh"
_DB_NEN = {"t": 0.0}
_SHOP_LOI = {}                                    # mã → lúc lấy ảnh Shop thất bại


def _cau_hinh():
    try:
        c = json.loads(_CC.read_text(encoding="utf-8"))
    except Exception:
        c = {}
    ta = c.get("tiktok_auto") or {}
    url = str(ta.get("url") or "http://127.0.0.1:8010").rstrip("/")
    return url, str((c.get("trypost") or {}).get("khoa") or "")


def _goi(duong, timeout=4, toi_da=8 * 1024 * 1024):
    """GET tới TikTok Auto kèm X-Key. Trả bytes; None nếu không kết nối được / bị từ chối (không ném lỗi)."""
    url, khoa = _cau_hinh()
    if not khoa:
        return None
    try:
        rq = urllib.request.Request(url + duong, headers={"X-Key": khoa, "Accept": "*/*"})
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            return r.read(toi_da + 1)[:toi_da]
    except Exception:
        return None


def ds_shop(lam_moi=False):
    """Sản phẩm TikTok Shop [{id, tieu_de, ten_ngan, gia, ma, anh_v, co_anh}], hoặc None khi TikTok Auto không trả lời.
    Nhớ 2 phút; lỗi thì không thử lại trong 20 giây (không làm chậm giao diện)."""
    now = time.time()
    if not lam_moi and _FEED["ds"] is not None and now - _FEED["t"] < 120:
        return _FEED["ds"]
    if not lam_moi and now - _FEED["loi"] < 20:
        return _FEED["ds"]
    raw = _goi("/api/xuong/shop-products", timeout=5, toi_da=4 * 1024 * 1024)
    try:
        d = json.loads(raw.decode("utf-8")) if raw else None
        items = d["items"] if d and d.get("ok") else None
    except Exception:
        items = None
    if items is None:
        _FEED["loi"] = now
        return _FEED["ds"]                         # giữ bản cũ nếu có
    ds = []
    for i in items:
        iu = str(i.get("image_url") or "")
        m = re.search(r"[?&]v=([0-9a-f]+)", iu)
        ds.append({"id": str(i.get("shop_product_id")), "tieu_de": str(i.get("title") or ""), "ten_ngan": str(i.get("short_name") or ""),
                   "gia": i.get("price"), "ma": list(i.get("linked_codes") or []), "anh_v": m.group(1) if m else "", "co_anh": bool(iu)})
    _FEED.update(t=now, ds=ds)
    return ds


def tim_shop(shop_id):
    return next((x for x in (ds_shop() or []) if x["id"] == str(shop_id)), None)


def _doan_duoi(data):
    if not data:
        return None
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def anh_shop_bytes(shop_id):
    """Ảnh thật của sản phẩm Shop (bytes, đuôi) — nhớ ở đĩa theo (id, phiên bản). (None, None) nếu chưa lấy được."""
    sid = str(shop_id)
    if not re.fullmatch(r"[0-9]{1,32}", sid):
        return None, None
    sp = tim_shop(sid)
    v = (sp or {}).get("anh_v") or "x"
    for e in (".jpg", ".png", ".webp"):
        f = _CACHE_ANH / f"{sid}-{v}{e}"
        if f.is_file():
            return f.read_bytes(), e
    if sp is None or not sp["co_anh"]:
        return None, None
    data = _goi(f"/api/xuong/shop-products/{sid}/image", timeout=15)
    ext = _doan_duoi(data)
    if not data or not ext:
        return None, None
    try:
        _CACHE_ANH.mkdir(exist_ok=True)
        for old in _CACHE_ANH.glob(f"{sid}-*"):
            try:
                old.unlink()
            except OSError:
                pass
        (_CACHE_ANH / f"{sid}-{v}{ext}").write_bytes(data)
    except OSError:
        pass
    return data, ext


def shop_id_cua(ma):
    """Sản phẩm Shop của mã này: ưu tiên mã đã chọn trong hub, sau đó mã đã gắn trong TikTok Auto."""
    try:
        sp = json.loads((SP / ma / "san-pham.json").read_text(encoding="utf-8"))
        if sp.get("shop_product_id"):
            return str(sp["shop_product_id"])
    except Exception:
        pass
    for x in ds_shop() or []:
        if ma in x["ma"]:
            return x["id"]
    return None


def dat_tu_shop(ma, shop_id):
    """Đặt ảnh thật của sản phẩm Shop làm ảnh của mã (ghi đè cả ảnh tải lên: chỉ gọi khi người dùng chủ động chọn). → (đường dẫn | None, lỗi)."""
    if not ma_hop_le(ma) or not (SP / ma / "san-pham.json").exists():
        return None, "Không có sản phẩm này"
    data, ext = anh_shop_bytes(shop_id)
    if not data:
        return None, "Không lấy được ảnh từ TikTok Shop (app TikTok Auto đang tắt hoặc sản phẩm chưa có ảnh)."
    v = (tim_shop(shop_id) or {}).get("anh_v", "")
    _THAT_BAI.pop(ma, None)
    return _dat_anh(ma, ext, data, "shop", {"shop_id": str(shop_id), "v": v}), None


def _dat_tu_shop(ma, hien_co):
    """Tự động: thay khung video / làm mới ảnh Shop khi có ảnh thật. Không bao giờ đụng ảnh tải lên. Trả đường dẫn ảnh mới (hoặc ảnh Shop hiện có), None nếu không làm được."""
    try:
        n = doc_nguon(ma)
        if hien_co and n["nguon"] == "upload":
            return None
        sid = shop_id_cua(ma)
        sp = tim_shop(sid) if sid else None
        if not sp:
            return None
        if hien_co and n["nguon"] == "shop" and n.get("shop_id") == sid and n.get("v") == sp["anh_v"]:
            return hien_co
        if hien_co and n["nguon"] == "video" and not (SP / ma / "anh.truoc-shop.jpg").exists():
            try:                                  # giữ 1 bản khung cũ phòng khi cần
                (SP / ma / "anh.truoc-shop.jpg").write_bytes(hien_co.read_bytes())
            except OSError:
                pass
        if time.time() - _SHOP_LOI.get(ma, 0) < 60:
            return None
        f, _ = dat_tu_shop(ma, sid)
        if not f:
            _SHOP_LOI[ma] = time.time()
        return f
    except Exception:
        return None


def dong_bo_nen():
    """Chạy nền (tối đa 5 phút/lần): thay ảnh khung-video bằng ảnh thật Shop, làm mới ảnh Shop đã đổi."""
    now = time.time()
    if now - _DB_NEN["t"] < 300:
        return
    _DB_NEN["t"] = now

    def chay():
        try:
            if ds_shop(lam_moi=True) is None:
                return
            for f in sorted(SP.glob("*/san-pham.json")):
                ma = f.parent.name
                with _KHOA:
                    if doc_nguon(ma)["nguon"] != "upload":
                        _dat_tu_shop(ma, tim_anh(ma))
        except Exception:
            pass
    threading.Thread(target=chay, daemon=True).start()
