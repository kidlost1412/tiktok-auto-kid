"""CỔNG CHO APP TIKTOK AUTO — hợp đồng giữa hub và app đăng TikTok (tiktok-auto).
(Tên "trypost" trong đường dẫn /trypost/... và tên file là tên cũ, giữ nguyên để không vỡ hợp đồng với app.)
Chạy cùng hub (mở hub là có), mặc định chỉ nghe 127.0.0.1:<cong> (app chạy cùng máy). Mọi yêu cầu cần header X-Key.
  GET  /trypost/videos?status=ung|tat_ca|da_dang|loi     danh sách video (mặc định: anh ✅ và CHƯA đăng)
  POST /trypost/videos/{id}/da-dang  {kenh, tiktok_id, link, luc}   → không trả video này nữa
  POST /trypost/videos/{id}/loi      {ly_do}                        → hiện trên app cho anh Kid
  POST /trypost/so-lieu              {id, kenh, luot_xem_24h, luot_xem_72h, thich, binh_luan, chia_se, don, luc}
GIỮ CHỖ (nhiều bản app dùng chung kho, không đăng trùng):
  GET  /trypost/videos?status=ung&may=<mã>   chỉ video chưa ai giữ hoặc chính máy đó giữ (mỗi video có trường giu_boi)
  POST /trypost/videos/{id}/giu  {may, kenh, han?}  → 200 {ok, giu_boi} | 409 {ok:false, giu_boi} (máy khác đang giữ). Gọi lại = gia hạn.
  POST /trypost/videos/{id}/nha  {may}              → bỏ giữ (chỉ máy đang giữ). da-dang / loi tự xoá giữ chỗ.
  han: ISO giờ hết hạn (quá hạn = coi như nhả). Không gửi = giữ tới khi nhả / da-dang / loi.
TẢI FILE (máy khác không đọc được ổ P:):
  GET  /trypost/videos/{id}/file      mp4, hỗ trợ Range
  GET  /trypost/videos/{id}/anh-bia   jpg
config.trypost.nghe_lan: false (mặc định) = chỉ 127.0.0.1; true = nghe 0.0.0.0 (chỉ bật khi app chạy trên máy khác trong LAN).
Đường dẫn file trả về là TƯƠNG ĐỐI trong hub, dấu /."""
import csv, datetime, hashlib, json, re, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, kem, KEM, ghi_json
LS = HUB / "lich-su"
_lock = threading.RLock()


def cfg():
    return cfg_hub()


def _doc(f, mac_dinh):
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else mac_dinh


def trang_thai_dang():
    return _doc(LS / "trypost.json", {})


def _ghi_trang_thai(vid, obj):
    with _lock:
        d = trang_thai_dang()
        if (d.get(vid) or {}).get("trang_thai") == "da_dang" and obj.get("trang_thai") != "da_dang":
            return False                      # video ĐÃ đăng thì không bao giờ bị hạ xuống "loi" (tránh đăng trùng)
        d[vid] = obj
        ghi_json(LS / "trypost.json", d, indent=1)
    return True


F_GIU = LS / "trypost-giu.json"


def ds_giu():
    """{id: {may, kenh, han, luc}} — bỏ giữ chỗ đã quá hạn."""
    d = _doc(F_GIU, {}); now = datetime.datetime.now(); out = {}
    for k, v in d.items():
        try:
            if v.get("han") and datetime.datetime.fromisoformat(str(v["han"])[:19]) < now:
                continue
        except Exception:
            pass
        out[k] = v
    return out


def _ghi_giu(d):
    ghi_json(F_GIU, d, indent=1)


def giu(vid, may, kenh=None, han=None):
    with _lock:
        d = ds_giu(); cu = d.get(vid)
        if cu and cu.get("may") != may:
            return False, cu.get("may")
        d[vid] = {"may": may, "kenh": kenh, "han": han, "luc": datetime.datetime.now().isoformat(timespec="seconds")}
        _ghi_giu(d)
        return True, may


def nha(vid, may=None):
    with _lock:
        d = ds_giu(); cu = d.get(vid)
        if not cu:
            return True, None
        if may and cu.get("may") != may:
            return False, cu.get("may")
        d.pop(vid, None); _ghi_giu(d)
        return True, None


def _sha256(p):
    cache_f = LS / "sha256.json"
    cache = _doc(cache_f, {})
    st = p.stat(); k = f"{p.name}|{st.st_size}|{int(st.st_mtime)}"
    if k not in cache:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        cache[k] = h.hexdigest()
        with _lock:                           # đọc lại + gộp rồi ghi nguyên tử (luồng khác có thể vừa thêm khoá)
            moi = _doc(cache_f, {}); moi.update(cache)
            ghi_json(cache_f, moi, indent=0)
    return cache[k]


def _ten_gio(sp, quy_cach):
    tg = sp.get("ten_gio") or ""
    if isinstance(tg, dict):
        tg = tg.get(quy_cach or "", "") or tg.get("", "")
    return str(tg).upper()[:30]


def ds_video(status="ung", may=None):
    ra = Path(cfg()["duong_dan"]["ra"])
    dg = _doc(LS / "danh-gia.json", {})
    tt = trang_thai_dang(); dgiu = ds_giu()
    sps = {}
    out = []
    for v in sorted(ra.glob("*/*.mp4")):
        if v.parent.name.startswith("_") or v.name.endswith(".part.mp4"):      # .part.mp4 = file đang ghi dở, chưa phải video xong
            continue
        vid = v.stem
        meta = _doc(kem(v, ".json"), {})
        ung = (dg.get(v.name) or {}).get("ket_qua") == "dat"
        t = tt.get(vid, {})
        if status == "ung" and not (ung and t.get("trang_thai") != "da_dang"):
            continue
        if status in ("da_dang", "loi") and t.get("trang_thai") != status:
            continue
        gb = (dgiu.get(vid) or {}).get("may")
        if status == "ung" and may and gb and gb != may:      # máy khác đang giữ → không đưa cho máy này
            continue
        ma = meta.get("ma") or vid.split("_")[0]
        if ma not in sps:
            f = HUB / "san-pham" / ma / "san-pham.json"
            sps[ma] = _doc(f, {})
        f_txt = kem(v, ".txt")
        txt = f_txt.read_text(encoding="utf-8").splitlines() if f_txt.exists() else []
        bia = kem(v, ".jpg")
        out.append({
            "id": vid, "file": v.relative_to(HUB).as_posix(), "sha256": _sha256(v), "ma": ma,
            "quy_cach": meta.get("quy_cach"), "caption": meta.get("caption") or (txt[0] if txt else ""),
            "hashtag": meta.get("hashtag") or (txt[1].split() if len(txt) > 1 else []),
            "ten_gio": _ten_gio(sps[ma], meta.get("quy_cach")),
            "anh_bia": bia.relative_to(HUB).as_posix() if bia.exists() else None,
            "goc": meta.get("goc"), "giong": meta.get("giong"), "nhac": meta.get("nhac"), "diem": meta.get("diem"),
            "ngay_lam": meta.get("ngay_lam") or v.parent.name, "thoi_luong": meta.get("thoi_luong"),
            "anh_ung": ung, "trang_thai_dang": t.get("trang_thai"), "giu_boi": gb,
            "url_file": f"/trypost/videos/{vid}/file", "url_anh_bia": f"/trypost/videos/{vid}/anh-bia" if bia.exists() else None,
            "kich_thuoc": v.stat().st_size,
        })
    return out


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _ok_khoa(self):
        if self.headers.get("X-Key") != cfg().get("trypost", {}).get("khoa"):
            self._json({"loi": "sai hoặc thiếu X-Key"}, 401); return False
        return True

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _tim(self, vid, duoi):
        if not re.fullmatch(r"[\w.\-]+", vid) or ".." in vid:
            return None
        ra = Path(cfg()["duong_dan"]["ra"]).resolve()
        for f in list(ra.glob(f"*/{vid}{duoi}")) + ([] if duoi == ".mp4" else list(ra.glob(f"*/{KEM}/{vid}{duoi}"))):
            f = f.resolve()
            ngay = f.parent.parent if f.parent.name == KEM else f.parent
            if not ngay.name.startswith("_") and ra in f.parents and f.is_file():
                return f
        return None

    def _gui_file(self, f, loai):
        n = f.stat().st_size; a, b = 0, n - 1; code = 200
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", (self.headers.get("Range") or "").strip())
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else n - 1
            else:
                a = max(0, n - int(m.group(2)))
            b = min(b, n - 1)
            if a > b:
                self.send_response(416); self.send_header("Content-Range", f"bytes */{n}"); self.end_headers(); return
            code = 206
        self.send_response(code); self.send_header("Content-Type", loai); self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(b - a + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {a}-{b}/{n}")
        self.end_headers()
        with open(f, "rb") as fh:
            fh.seek(a); con = b - a + 1
            while con > 0:
                ch = fh.read(min(1 << 20, con))
                if not ch:
                    break
                try:
                    self.wfile.write(ch)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return
                con -= len(ch)

    def do_GET(self):
        if not self._ok_khoa():
            return
        u = urlparse(self.path); parts = [unquote(x) for x in u.path.strip("/").split("/")]
        if u.path == "/trypost/videos":
            q = parse_qs(u.query)
            return self._json({"videos": ds_video(q.get("status", ["ung"])[0], (q.get("may") or [None])[0])})
        if len(parts) == 4 and parts[:2] == ["trypost", "videos"] and parts[3] in ("file", "anh-bia"):
            f = self._tim(parts[2], ".mp4" if parts[3] == "file" else ".jpg")
            if not f:
                return self._json({"ok": False, "loi": "không có file này"}, 404)
            return self._gui_file(f, "video/mp4" if parts[3] == "file" else "image/jpeg")
        if len(parts) == 4 and parts[:2] == ["trypost", "san-pham"] and parts[3] == "anh":     # ảnh sản phẩm (chỉ đọc; chưa có thì hub tự lấy từ video)
            import anh_sp
            f = anh_sp.lay_anh(parts[2])
            if not f:
                return self._json({"ok": False, "loi": "sản phẩm chưa có ảnh"}, 404)
            return self._gui_file(f, {".png": "image/png", ".webp": "image/webp"}.get(f.suffix.lower(), "image/jpeg"))
        if u.path == "/trypost/ping":
            return self._json({"ok": True, "hub": "xuong-video"})
        self._json({"loi": "không có đường này"}, 404)

    def do_POST(self):
        if not self._ok_khoa():
            return
        u = urlparse(self.path); b = self._body(); parts = [unquote(x) for x in u.path.strip("/").split("/")]
        now = datetime.datetime.now().isoformat(timespec="seconds")
        if len(parts) == 4 and parts[:2] == ["trypost", "videos"] and parts[3] in ("da-dang", "loi", "giu", "nha"):
            vid = parts[2]
            if not re.fullmatch(r"[\w.\-]+", vid) or ".." in vid:     # chặn id lạ (../, *, ký tự đường dẫn)
                return self._json({"ok": False, "loi": "id không hợp lệ"}, 400)
            if not any(Path(cfg()["duong_dan"]["ra"]).glob(f"*/{vid}.mp4")):
                return self._json({"ok": False, "loi": "không có video này"}, 404)
            if parts[3] in ("giu", "nha"):
                may = str(b.get("may") or "").strip()[:60]
                if not may:
                    return self._json({"loi": "thiếu may (mã bản app)"}, 400)
                if parts[3] == "giu":
                    if (trang_thai_dang().get(vid) or {}).get("trang_thai") == "da_dang":
                        return self._json({"ok": False, "loi": "video đã đăng", "giu_boi": None}, 409)
                    han = b.get("han")
                    if han:
                        try:
                            datetime.datetime.fromisoformat(str(han)[:19])
                        except Exception:
                            return self._json({"loi": "han không đúng ISO"}, 400)
                    ok, ai = giu(vid, may, b.get("kenh"), han)
                else:
                    ok, ai = nha(vid, may)
                return self._json({"ok": ok, "giu_boi": ai}, 200 if ok else 409)
            nha(vid)                                         # da-dang / loi → xoá giữ chỗ
            if parts[3] == "da-dang":
                _ghi_trang_thai(vid, {"trang_thai": "da_dang", "kenh": b.get("kenh"), "tiktok_id": b.get("tiktok_id"),
                                      "link": b.get("link"), "luc": b.get("luc") or now, "luc_nhan": now})   # hub dọn theo luc_nhan (giờ máy hub)
            else:
                _ghi_trang_thai(vid, {"trang_thai": "loi", "ly_do": str(b.get("ly_do", ""))[:300], "luc": now})
            return self._json({"ok": True})
        if parts == ["trypost", "so-lieu"]:
            f = LS / "so-lieu.csv"; cot = ["luc_nhan", "id", "kenh", "luot_xem_24h", "luot_xem_72h", "thich", "binh_luan", "chia_se", "don", "luc"]
            with _lock:
                moi = not f.exists()
                with open(f, "a", newline="", encoding="utf-8-sig") as fh:
                    w = csv.writer(fh)
                    if moi:
                        w.writerow(cot)
                    w.writerow([now] + [b.get(k, "") for k in cot[1:]])
            return self._json({"ok": True})
        self._json({"loi": "không có đường này"}, 404)


def chay_nen():
    c = cfg().get("trypost", {})
    if not c.get("khoa"):
        return None
    ThreadingHTTPServer.allow_reuse_address = False
    srv = ThreadingHTTPServer(("0.0.0.0" if c.get("nghe_lan", False) else "127.0.0.1", int(c.get("cong", 8766))), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
