"""NHIỀU TÀI KHOẢN ChatGPT (Codex CLI) — song song với tài khoản Claude trong ai.py.
- Mỗi tài khoản = 1 thư mục CODEX_HOME riêng (tài khoản mặc định g1 = ~/.codex). Hub KHÔNG đọc auth.json/token.
- Trạng thái (đăng nhập, email, gói, hạn mức 5 giờ / 7 ngày, danh sách model) lấy qua `codex app-server` (JSON-RPC, thử nghiệm);
  lỗi thì lùi về `codex login status` (chỉ biết đăng nhập hay chưa, hạn mức = chưa rõ).
- Cache ở lich-su/tai-khoan-gpt.json (không chứa token). Cùng dạng five_hour/seven_day {pct 0..1, reset unix} như tai-khoan.json của Claude.
- Cấu hình: config "tai_khoan_gpt": [{"ma","ten","thu_muc"}], "tai_khoan_gpt_dung": "tu_dong" | mã tài khoản ghim.
  them()/bo() sửa dict config được truyền vào → server gọi luu_cfg(c) sau đó."""
import json, os, queue, re, shutil, subprocess, threading, time
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import DATA as HUB, cfg, ghi_json

_lock = threading.RLock()
_LOCK_DS = threading.Lock()           # them/bo không chạy chồng
_DANG_NHAP = {"ma": None, "pr": None}  # chỉ 1 phiên `codex login` cùng lúc (cổng localhost 1455)
_DANG_LAM_MOI = set()
CACHE_GIAY = 300
MAC_DINH = {"ma": "g1", "ten": "ChatGPT 1", "thu_muc": None}
STORE_FILE = 'cli_auth_credentials_store="file"'


def f_cache():
    return HUB / "lich-su" / "tai-khoan-gpt.json"


def ds_tk(c=None):
    """[{ma, ten, thu_muc|None}] — mặc định 1 tài khoản dùng thư mục chuẩn của Codex."""
    return (c if c is not None else cfg()).get("tai_khoan_gpt") or [dict(MAC_DINH)]


def _them_path(e):
    """App mở từ launcher có thể mang PATH cũ (thiếu npm/node của người dùng) → nối thư mục npm + nodejs để tìm thấy codex."""
    p = e.get("PATH") or e.get("Path") or ""
    co = {x.strip().rstrip("\\").lower() for x in p.split(";") if x.strip()}
    them = [d for d in (os.path.expandvars(r"%APPDATA%\npm"), os.path.expandvars(r"%ProgramFiles%\nodejs"))
            if os.path.isdir(d) and d.rstrip("\\").lower() not in co]
    if them:
        e.pop("Path", None)
        e["PATH"] = ";".join([p] + them if p else them)
    return e


def _tim_codex():
    """Tìm codex theo nhiều đường (app chạy dưới launcher từng không thấy dù PATH có npm): PATH → thư mục npm của người dùng → `where`."""
    p = shutil.which("codex", path=_them_path(dict(os.environ))["PATH"])
    if p:
        return p
    goc = [os.environ.get("APPDATA"), os.path.join(os.environ.get("USERPROFILE") or "", "AppData", "Roaming"),
           str(Path.home() / "AppData" / "Roaming")]
    for g in filter(None, goc):
        for ten in ("codex.cmd", "codex.exe"):
            f = os.path.join(g, "npm", ten)
            if os.path.isfile(f):
                return f
    try:
        r = subprocess.run(["where", "codex"], capture_output=True, text=True, timeout=10,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for dong in r.stdout.splitlines():
            if dong.strip().lower().endswith((".cmd", ".exe")) and os.path.isfile(dong.strip()):
                return dong.strip()
    except Exception:
        pass
    return None


def codex_exe():
    p = cfg().get("duong_dan", {}).get("codex")
    p = p if p and os.path.isfile(p) else _tim_codex()
    if not p:
        raise RuntimeError("Không tìm thấy Codex CLI trên máy — mở PowerShell từ menu Start (không mở trong app Claude) rồi chạy: "
                           "npm install -g @openai/codex")
    return p


def env(tk):
    e = _them_path(dict(os.environ))
    if tk.get("thu_muc"):
        e["CODEX_HOME"] = str(Path(tk["thu_muc"]).resolve())
    else:
        e.pop("CODEX_HOME", None)
    return e


# ---------- cache ----------
def doc_trang_thai():
    try:
        f = f_cache()
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:
        return {}


def _ghi_khong_khoa(ma, kv):
    d = doc_trang_thai(); d.setdefault(ma, {}).update(kv)
    f_cache().parent.mkdir(parents=True, exist_ok=True)
    ghi_json(f_cache(), d, indent=1)


def ghi(ma, **kv):
    """Đọc-sửa-ghi tai-khoan-gpt.json (khoá file HĐH như ai._ghi_trang_thai)."""
    from su_kien import khoa_tep
    with _lock:
        try:
            with khoa_tep(f_cache(), 5):
                _ghi_khong_khoa(ma, kv)
        except TimeoutError:
            _ghi_khong_khoa(ma, kv)


def quen(ma):
    with _lock:
        d = doc_trang_thai()
        if d.pop(ma, None) is not None:
            ghi_json(f_cache(), d, indent=1)


# ---------- đọc trạng thái qua codex app-server ----------
def _cua_so(rl):
    """rateLimits.primary/secondary → (five_hour, seven_day) dạng {pct 0..1, reset unix}; theo windowDurationMins (300 / 10080), thiếu thì theo thứ tự."""
    def conv(w):
        if not isinstance(w, dict) or w.get("usedPercent") is None:
            return None
        return {"pct": max(0.0, float(w["usedPercent"]) / 100.0), "reset": int(w.get("resetsAt") or 0)}
    p, s = (rl or {}).get("primary"), (rl or {}).get("secondary")
    f5 = sd = None
    for w in (p, s):
        m = (w or {}).get("windowDurationMins")
        if m == 300 and f5 is None:
            f5 = conv(w)
        elif m == 10080 and sd is None:
            sd = conv(w)
    if f5 is None and sd is None:
        f5, sd = conv(p), conv(s)
    return f5, sd


def _models(res):
    out = []
    for m in (res or {}).get("data") or []:
        mid = m.get("id") or m.get("model")
        if not mid:
            continue
        out.append({"id": mid, "ten": m.get("displayName") or mid, "mac_dinh": bool(m.get("isDefault")), "an": bool(m.get("hidden")),
                    "effort": [e.get("reasoningEffort") for e in (m.get("supportedReasoningEfforts") or []) if e.get("reasoningEffort")],
                    "effort_mac_dinh": m.get("defaultReasoningEffort")})
    return out


def _app_server(tk, timeout):
    """Chạy `codex app-server`, hỏi account/read + rateLimits + model/list → {tên: result|None}; lỗi nặng → None."""
    pr = subprocess.Popen([codex_exe(), "app-server", "--listen", "stdio://"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", env=env(tk),
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    q = queue.Queue()

    def doc():
        try:
            for line in pr.stdout:
                q.put(line)
        except Exception:
            pass
        q.put(None)
    threading.Thread(target=doc, daemon=True).start()
    try:
        def gui(o):
            pr.stdin.write(json.dumps(o) + "\n"); pr.stdin.flush()
        gui({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "xuong-video", "title": "Xuong Video", "version": "1"}}})
        gui({"method": "initialized"})
        goi = {2: ("account", "account/read", {"refreshToken": False}), 3: ("limits", "account/rateLimits/read", {}), 4: ("models", "model/list", {})}
        for i, (_, m, p) in goi.items():
            gui({"id": i, "method": m, "params": p})
        kq, han, init = {}, time.time() + timeout, False
        while len(kq) < 3 and time.time() < han:
            try:
                line = q.get(timeout=max(0.05, min(1.0, han - time.time())))
            except queue.Empty:
                continue
            if line is None:
                break
            try:
                o = json.loads(line)
            except Exception:
                continue
            if not isinstance(o, dict) or "id" not in o:
                continue
            if o["id"] == 1:
                init = "result" in o
            elif o["id"] in goi:
                kq[goi[o["id"]][0]] = o.get("result") if "result" in o else None
        return kq if init or kq else None
    except Exception:
        return None
    finally:
        try:
            pr.kill()
        except Exception:
            pass


def _login_status(tk, timeout):
    r = subprocess.run([codex_exe(), "login", "status"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, env=env(tk), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode == 0


def trang_thai(tk, timeout=25):
    """Đọc trạng thái 1 tài khoản (không ghi cache). Hạn mức không biết → five_hour/seven_day = None."""
    t = {"dang_nhap": False, "email": None, "goi": None, "workspace": None, "five_hour": None, "seven_day": None, "het": False,
         "models": [], "cap_nhat": int(time.time()), "loi": None}
    kq = None
    try:
        kq = _app_server(tk, timeout)
    except Exception as e:
        t["loi"] = f"app-server: {e}"[:200]
    acc = (kq or {}).get("account") if kq else None
    lim = (kq or {}).get("limits") if kq else None
    if kq is not None and acc is not None and isinstance(acc.get("account"), dict):
        a = acc["account"]
        t.update(dang_nhap=True, email=a.get("email"), goi=a.get("planType"), workspace=a.get("workspaceName"))
    elif kq is not None and acc is not None and acc.get("account") is None and lim is None:
        t["dang_nhap"] = False                      # app-server chạy được, báo chưa có tài khoản
    else:
        try:                                         # app-server hỏng/thiếu → chỉ biết đăng nhập hay chưa
            t["dang_nhap"] = _login_status(tk, min(timeout, 20))
            t["loi"] = t["loi"] or "không đọc được hạn mức (app-server lỗi)"
        except Exception as e:
            t["loi"] = f"codex login status: {e}"[:200]
    if lim:
        rl = lim.get("rateLimits") or {}
        t["five_hour"], t["seven_day"] = _cua_so(rl)
        t["goi"] = t["goi"] or rl.get("planType")
        now = time.time()
        qua = any(w and w["pct"] >= 1.0 and w["reset"] > now for w in (t["five_hour"], t["seven_day"]))
        t["het"] = bool(rl.get("rateLimitReachedType")) or lim.get("ordinaryUsageAllowed") is False or qua
    t["models"] = _models((kq or {}).get("models")) if kq else []
    return t


def lam_moi(ma, timeout=25):
    """Đọc trạng thái mới của tài khoản `ma` và ghi cache. Giữ danh sách model cũ nếu lần này không đọc được."""
    tk = next((x for x in ds_tk() if x["ma"] == ma), None)
    if not tk:
        return {"loi": "không có tài khoản"}
    t = trang_thai(tk, timeout)
    cu = doc_trang_thai().get(ma, {})
    if not t["models"] and cu.get("models") and t["dang_nhap"]:
        t["models"] = cu["models"]
    kv = dict(t); kv["het_den"] = None
    if t["five_hour"] is None and t["seven_day"] is None and (cu.get("het_den") or 0) > time.time():
        kv["het"], kv["het_den"] = True, cu["het_den"]
    elif t["het"]:                                      # hết → khoá tới giờ mở lại gần nhất đã biết (hoặc giờ đã đánh dấu / +1 giờ)
        rs = [w["reset"] for w in (t["five_hour"], t["seven_day"]) if w and w["pct"] >= 1.0 and w["reset"] > time.time()]
        kv["het_den"] = max(rs) if rs else (cu.get("het_den") if (cu.get("het_den") or 0) > time.time() else time.time() + 3600)
    ghi(ma, **kv)
    return doc_trang_thai().get(ma, {})


def lam_moi_nen(ma, toi_thieu=CACHE_GIAY):
    """Làm mới hạn mức ở luồng nền, tối đa 1 lần / `toi_thieu` giây / tài khoản (gọi sau mỗi lượt codex exec)."""
    with _lock:
        if ma in _DANG_LAM_MOI or time.time() - (doc_trang_thai().get(ma, {}).get("cap_nhat") or 0) < toi_thieu:
            return False
        _DANG_LAM_MOI.add(ma)

    def chay():
        try:
            lam_moi(ma)
        except Exception:
            pass
        finally:
            with _lock:
                _DANG_LAM_MOI.discard(ma)
    threading.Thread(target=chay, daemon=True).start()
    return True


def ds(moi=False):
    """Mọi tài khoản + trạng thái: [{ma, ten, dang_nhap, email, goi, workspace, five_hour, seven_day, het, het_den, models, cap_nhat, loi}].
    Cache quá 5 phút (hoặc moi=True) → đọc lại song song."""
    tks, st = ds_tk(), doc_trang_thai()
    cu = [t["ma"] for t in tks if moi or time.time() - (st.get(t["ma"], {}).get("cap_nhat") or 0) > CACHE_GIAY]
    with _lock:
        cu = [m for m in cu if m not in _DANG_LAM_MOI]
        _DANG_LAM_MOI.update(cu)

    def chay(m):
        try:
            lam_moi(m)
        except Exception:
            pass
        finally:
            with _lock:
                _DANG_LAM_MOI.discard(m)
    ths = [threading.Thread(target=chay, args=(m,), daemon=True) for m in cu]
    for th in ths:
        th.start()
    for th in ths:
        th.join(40)
    st = doc_trang_thai(); out = []
    for t in tks:
        x = st.get(t["ma"], {})
        out.append({"ma": t["ma"], "ten": t.get("ten") or t["ma"], "dang_nhap": x.get("dang_nhap"), "email": x.get("email"), "goi": x.get("goi"),
                    "workspace": x.get("workspace"), "five_hour": x.get("five_hour"), "seven_day": x.get("seven_day"),
                    "het": bool(x.get("het")), "het_den": x.get("het_den"), "models": x.get("models") or [],
                    "cap_nhat": x.get("cap_nhat"), "loi": x.get("loi")})
    return out


# ---------- chọn tài khoản ----------
def chon(bo_qua=(), c=None):
    """Tài khoản dùng cho lượt gọi: ghim (tai_khoan_gpt_dung) nếu còn dùng được, không thì tài khoản đã đăng nhập, chưa hết, 5 giờ ít nhất (rồi 7 ngày).
    Chưa đọc trạng thái lần nào (không có cache) → coi là dùng được. Không còn tài khoản → ai.HetHanMuc."""
    import ai
    now = time.time(); st = doc_trang_thai(); c = c if c is not None else cfg()

    def ok(tk):
        x = st.get(tk["ma"], {})
        if tk["ma"] in bo_qua or x.get("dang_nhap") is False:
            return False
        if (x.get("het_den") or 0) > now:
            return False
        return True
    tks = ds_tk(c)
    ghim = c.get("tai_khoan_gpt_dung") or "tu_dong"
    if ghim != "tu_dong":
        tk = next((t for t in tks if t["ma"] == ghim), None)
        if tk and ok(tk):
            return tk

    def pct(x, w):
        o = x.get(w) or {}
        return 0.0 if (o.get("reset") or 0) < now else float(o.get("pct") or 0)
    ung = [(pct(st.get(t["ma"], {}), "five_hour"), pct(st.get(t["ma"], {}), "seven_day"), i, t) for i, t in enumerate(tks) if ok(t)]
    if not ung:
        raise ai.HetHanMuc("Mọi tài khoản ChatGPT đều đã hết hạn mức hoặc chưa đăng nhập")
    ung.sort(key=lambda z: z[:3])
    return ung[0][3]


def mark_het(ma, den=None):
    """Lượt gọi gặp giới hạn → khoá tài khoản tới `den` (unix giây; mặc định +1 giờ)."""
    ghi(ma, het=True, het_den=den or time.time() + 3600)


def mark_chua_dang_nhap(ma):
    ghi(ma, dang_nhap=False)


# ---------- thêm / bỏ / đăng nhập ----------
def them(c, ten):
    """Thêm tài khoản MỚI vào dict config `c` (cfg()): luôn thư mục trống tai-khoan-gpt/g<n>/ (không dùng lại thư mục cũ), có config.toml
    lưu đăng nhập dạng file. → mã tài khoản. Server phải gọi luu_cfg(c) ngay sau đó."""
    with _LOCK_DS:
        ds_ = c.setdefault("tai_khoan_gpt", [dict(MAC_DINH)])
        goc = HUB / "tai-khoan-gpt"
        n = 1
        cat = goc / "_da-bo"
        cu = [p.name for p in cat.iterdir()] if cat.is_dir() else []
        while any(t["ma"] == f"g{n}" for t in ds_) or (goc / f"g{n}").exists() or any(x.startswith(f"g{n}-") for x in cu):
            n += 1
        ma = f"g{n}"
        d = goc / ma; d.mkdir(parents=True, exist_ok=True)
        (d / "config.toml").write_text(STORE_FILE + "\n", encoding="utf-8")
        ds_.append({"ma": ma, "ten": (ten or f"ChatGPT {n}").strip()[:40], "thu_muc": str(d)})
    quen(ma)
    return ma


def bo(c, ma):
    """Bỏ tài khoản khỏi dict config `c`: cất thư mục vào tai-khoan-gpt/_da-bo/ (không xoá), quên cache; đang ghim tài khoản này → "tu_dong".
    → {"ok": True} hoặc {"ok": False, "loi": ...}. Server gọi luu_cfg(c) khi ok."""
    with _LOCK_DS:
        ds_ = c.get("tai_khoan_gpt") or [dict(MAC_DINH)]
        tk = next((t for t in ds_ if t["ma"] == ma), None)
        if not tk:
            return {"ok": False, "loi": "Không có tài khoản này"}
        if len(ds_) <= 1:
            return {"ok": False, "loi": "Phải còn ít nhất 1 tài khoản"}
        c["tai_khoan_gpt"] = [t for t in ds_ if t["ma"] != ma]
        if c.get("tai_khoan_gpt_dung") == ma:
            c["tai_khoan_gpt_dung"] = "tu_dong"
    goc = (HUB / "tai-khoan-gpt").resolve()
    tm = Path(tk["thu_muc"]).resolve() if tk.get("thu_muc") else None
    if tm and tm.parent == goc and tm.is_dir():          # chỉ cất thư mục hub tự tạo; ~/.codex của máy thì để yên
        cat = goc / "_da-bo" / f"{ma}-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            cat.parent.mkdir(parents=True, exist_ok=True); tm.rename(cat)
        except OSError:
            pass
    quen(ma)
    return {"ok": True}


def mo_dang_nhap(ma):
    """Mở cửa sổ console chạy `codex login` (đăng nhập trình duyệt, cổng 1455) đúng thư mục của tài khoản. Chỉ 1 phiên cùng lúc."""
    tk = next((t for t in ds_tk() if t["ma"] == ma), None)
    if not tk:
        return {"ok": False, "loi": "không có tài khoản"}
    with _lock:
        pr = _DANG_NHAP.get("pr")
        if pr is not None and pr.poll() is None:
            return {"ok": False, "loi": f"Đang có cửa sổ đăng nhập ChatGPT ({_DANG_NHAP['ma']}) — đăng nhập xong hoặc đóng nó rồi thử lại"}
        try:
            exe = codex_exe()
        except RuntimeError as e:
            return {"ok": False, "loi": str(e)}
        pr = subprocess.Popen(["cmd", "/k", exe, "login"], cwd=str(HUB), env=env(tk),
                              creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        _DANG_NHAP.update(ma=ma, pr=pr)
    return {"ok": True}
