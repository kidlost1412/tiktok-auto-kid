"""Gọi Claude CLI headless gọn nhẹ + NHIỀU TÀI KHOẢN (Kid 10/11/2026: 3 tài khoản, xem hạn mức từng cái, tự chuyển khi sắp hết).
goi(vai, prompt, anh=[...]) → (text, usage).
- Mỗi tài khoản là 1 thư mục cấu hình riêng (CLAUDE_CONFIG_DIR; tài khoản 1 = thư mục mặc định ~/.claude).
- Mỗi lần gọi dùng --output-format stream-json: CLI tự báo hạn mức chính thức (rate_limit_event: 5 giờ, 7 ngày, giờ reset)
  → ghi vào lich-su/tai-khoan.json, app hiển thị. Hub KHÔNG đọc file đăng nhập/token.
- Chọn tài khoản còn dư nhiều nhất; tài khoản hết hạn mức → đánh dấu tới giờ reset, tự chuyển sang tài khoản khác.
  Chỉ báo HetHanMuc khi MỌI tài khoản đều hết."""
import csv, datetime, json, os, re, subprocess, threading, time
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, ghi_json
F_TK = HUB / "lich-su" / "tai-khoan.json"
_lock = threading.RLock()


def he_thong(vai):
    """Lời dặn chung gửi mọi vai AI — mẫu prompt/he-thong.md (chỉnh được trong tab Prompt AI)."""
    import prompt_mau
    return prompt_mau.dien("he-thong", vai=vai)


NGUONG_DOI = 0.92      # dùng quá 92% cửa sổ 5 giờ / 7 ngày → ưu tiên tài khoản khác


VIEC = threading.local()      # ekip đặt VIEC.video = tên video trước khi gọi → token.csv biết lượt gọi thuộc video nào


class HetHanMuc(RuntimeError):
    pass


def cfg():
    return cfg_hub()


def ds_tai_khoan():
    """[{ma, ten, thu_muc|None}] — mặc định 1 tài khoản dùng thư mục chuẩn của CLI."""
    return cfg().get("tai_khoan") or [{"ma": "tk1", "ten": "Tài khoản 1", "thu_muc": None}]


def doc_trang_thai():
    try:
        return json.loads(F_TK.read_text(encoding="utf-8")) if F_TK.exists() else {}
    except Exception:
        return {}


def _ghi_trang_thai(ma, **kv):
    with _lock:
        d = doc_trang_thai(); x = d.setdefault(ma, {}); x.update(kv)
        F_TK.parent.mkdir(exist_ok=True)
        ghi_json(F_TK, d, indent=1)


def env_tk(tk):
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
        env.pop(k, None)                       # không để khoá API ghi đè gói đăng ký
    if tk.get("thu_muc"):
        env["CLAUDE_CONFIG_DIR"] = str(Path(tk["thu_muc"]).resolve())
    else:
        env.pop("CLAUDE_CONFIG_DIR", None)
    return env


def chon_tai_khoan(bo_qua=()):
    """Anh chọn tài khoản cố định (config tai_khoan_dung) → dùng đúng tài khoản đó; hết thì tự chuyển nếu bật tu_chuyen.
    Để 'tu_dong' → tài khoản còn dư nhiều nhất, bỏ tài khoản đang hết hạn mức (chưa tới giờ reset)."""
    now = time.time(); st = doc_trang_thai(); ung = []
    c = cfg(); co_dinh = c.get("tai_khoan_dung", "tu_dong")
    if co_dinh and co_dinh != "tu_dong":
        tk = next((t for t in ds_tai_khoan() if t["ma"] == co_dinh), None)
        x = st.get(co_dinh, {})
        if tk and co_dinh not in bo_qua and not (x.get("het_den") and x["het_den"] > now) and x.get("dang_nhap") is not False:
            return tk
        if not c.get("tu_chuyen", True):
            return None                                  # anh chọn cố định + không cho tự chuyển → dừng, báo anh chọn tài khoản khác
    for tk in ds_tai_khoan():
        if tk["ma"] in bo_qua:
            continue
        x = st.get(tk["ma"], {})
        if x.get("het_den") and x["het_den"] > now:
            continue
        if x.get("dang_nhap") is False:
            continue
        def pct(w):
            o = x.get(w) or {}
            return 0.0 if (o.get("reset") or 0) < now else float(o.get("pct") or 0)   # quá giờ reset → coi như mới
        dung = max(pct("five_hour"), pct("seven_day"))
        ung.append((dung >= NGUONG_DOI, dung, tk))
    if not ung:
        return None
    ung.sort(key=lambda z: (z[0], z[1]))
    return ung[0][2]


MAX_BYTE_ANH = 3_500_000      # ảnh > 3.5MB (hoặc cạnh > 7900px) → nén lại JPEG trước khi gửi
MAX_CANH_ANH = 7900
_MIME = ((b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"), (b"RIFF", "image/webp"))


class LoiNhungAnh(RuntimeError):
    """Không gửi ảnh nhúng thẳng được → goi() lùi về cách cũ (công cụ Read)."""


def _nap_anh(path):
    """→ (media_type, base64) cho 1 ảnh; nén/thu nhỏ trong bộ nhớ nếu quá lớn. Không bao giờ phóng to."""
    import base64, io
    try:
        raw = Path(path).read_bytes()
        mime = next((m for sig, m in _MIME if raw.startswith(sig) and (m != "image/webp" or raw[8:12] == b"WEBP")), None)
        if mime is None or len(raw) > MAX_BYTE_ANH:
            from PIL import Image
            im = Image.open(io.BytesIO(raw)); im.load()
            if mime is None or max(im.size) > MAX_CANH_ANH or len(raw) > MAX_BYTE_ANH:
                if im.mode not in ("RGB", "L"):
                    nen = Image.new("RGB", im.size, (255, 255, 255))
                    im = im.convert("RGBA"); nen.paste(im, mask=im.split()[3]); im = nen
                elif im.mode == "L":
                    im = im.convert("RGB")
                k = min(1.0, MAX_CANH_ANH / max(im.size))
                while True:
                    cur = im if k >= 1.0 else im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
                    buf = io.BytesIO(); cur.save(buf, "JPEG", quality=88, optimize=True)
                    if buf.tell() <= MAX_BYTE_ANH or k < 0.2:
                        break
                    k *= 0.85
                raw, mime = buf.getvalue(), "image/jpeg"
        return mime, base64.b64encode(raw).decode("ascii")
    except Exception as e:
        raise LoiNhungAnh(f"không nạp được ảnh {Path(path).name}: {e}")


def _goi_1(tk, vai, prompt, anh, model, effort, timeout, nhung=False):
    """nhung=True: ảnh gửi THẲNG trong 1 tin nhắn (stream-json, không công cụ → đúng 1 lượt). nhung=False: cách cũ (Read)."""
    claude = cfg()["duong_dan"]["claude"]
    cmd = [claude, "-p", "--output-format", "stream-json", "--verbose", "--model", model, "--effort", effort,
           "--strict-mcp-config", "--no-chrome", "--no-session-persistence", "--system-prompt", he_thong(vai)]
    stdin = prompt
    if anh and nhung:
        khoi = [{"type": "text", "text": prompt}]
        for a in anh:
            mime, b64 = _nap_anh(a)
            khoi.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}})
        stdin = json.dumps({"type": "user", "message": {"role": "user", "content": khoi}}, ensure_ascii=False) + "\n"
        cmd += ["--input-format", "stream-json", "--tools", ""]
    elif anh:
        cmd += ["--tools", "Read", "--allowedTools", "Read"]
        for d in sorted({str(Path(a).parent) for a in anh}):
            cmd += ["--add-dir", d]
    else:
        cmd += ["--tools", ""]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                          errors="replace", cwd=str(HUB), env=env_tk(tk))
    try:
        out, err = pr.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired:                # quá giờ → tắt CẢ cây tiến trình (node), không để chạy ngầm tốn hạn mức
        subprocess.run(["taskkill", "/PID", str(pr.pid), "/T", "/F"], capture_output=True)
        pr.communicate()
        raise RuntimeError(f"Claude quá {timeout}s ({vai}) — đã dừng")
    r = subprocess.CompletedProcess(cmd, pr.returncode, out, err)
    ket, rl = {}, None
    for line in r.stdout.splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("type") == "rate_limit_event":
            rl = ev.get("rate_limit_info") or {}
        elif ev.get("type") == "result":
            ket = ev
    if rl:                                        # hạn mức chính thức CLI báo về
        w = rl.get("unifiedWindows") or {}
        kv = {k: {"pct": round(float((w.get(k) or {}).get("utilization") or 0), 4), "reset": (w.get(k) or {}).get("resetsAt"),
                  "trang_thai": (w.get(k) or {}).get("status")} for k in ("five_hour", "seven_day") if k in w}
        kv["cap_nhat"] = time.time(); kv["dang_nhap"] = True
        if rl.get("status") == "rejected":
            kv["het_den"] = rl.get("resetsAt") or (time.time() + 3600)
        _ghi_trang_thai(tk["ma"], **kv)
    if not ket:
        ket = {"result": (r.stdout or "")[-400:], "is_error": True}
    return r, ket, rl


def goi(vai, prompt, anh=None, model=None, effort=None, timeout=1200):
    cl = cfg().get("claude", {})
    model = model or cl.get("model", "opus"); effort = effort or cl.get("effort", "high")
    prompt_goc = prompt
    nhung = bool(anh) and cfg().get("anh_nhung", True)          # mặc định gửi ảnh nhúng thẳng (1 lượt); anh_nhung=false → cách cũ
    if anh and nhung:
        prompt = prompt_goc + "\n\nẢnh đính kèm theo thứ tự: " + " ".join(f"{i}) {Path(str(a)).name}" for i, a in enumerate(anh, 1))
    elif anh:
        prompt = prompt_goc + "\n\nẢNH CẦN XEM (dùng công cụ Read mở TỪNG ảnh trước khi trả lời):\n" + "\n".join(str(a) for a in anh)
    da_thu = []
    while True:
        tk = chon_tai_khoan(bo_qua=da_thu)
        if tk is None:
            raise HetHanMuc("Mọi tài khoản Claude đều đã hết hạn mức hoặc chưa đăng nhập" + (f" (đã thử: {', '.join(da_thu)})" if da_thu else ""))
        t0 = datetime.datetime.now()
        try:
            r, d, rl = _goi_1(tk, vai, prompt, anh, model, effort, timeout, nhung)
            if nhung and (r.returncode != 0 or d.get("is_error")) and re.search(
                    r"input[- ]format|image|too large|exceed|stream-json|unexpected|invalid.*(message|content)",
                    (d.get("result") or "") + " " + (r.stderr or ""), re.I) and not re.search(r"hit your .*limit|usage limit|limit reached|login|oauth", (d.get("result") or "") + (r.stderr or ""), re.I):
                raise LoiNhungAnh(((d.get("result") or r.stderr or "")[:200]).replace("\n", " "))
        except LoiNhungAnh as e:                                # lùi về cách cũ cho lần gọi này
            print(f"[ai] gửi ảnh nhúng lỗi ({vai}): {e} → dùng công cụ Read", flush=True)
            nhung = False
            prompt = prompt_goc + "\n\nẢNH CẦN XEM (dùng công cụ Read mở TỪNG ảnh trước khi trả lời):\n" + "\n".join(str(a) for a in anh)
            r, d, rl = _goi_1(tk, vai, prompt, anh, model, effort, timeout, False)
        res = d.get("result") or ""
        u = d.get("usage") or {}
        with _lock:
            f = HUB / "lich-su" / "token.csv"; f.parent.mkdir(exist_ok=True)
            new = not f.exists()
            with open(f, "a", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh)
                if new:
                    w.writerow(["luc", "vai", "model", "effort", "giay", "vao", "vao_cache_tao", "vao_cache_doc", "ra", "usd_uoc", "luot", "so_anh", "tai_khoan", "video"])
                w.writerow([t0.strftime("%Y-%m-%d %H:%M:%S"), vai, model, effort, round((datetime.datetime.now() - t0).total_seconds(), 1),
                            u.get("input_tokens", 0), u.get("cache_creation_input_tokens", 0), u.get("cache_read_input_tokens", 0),
                            u.get("output_tokens", 0), d.get("total_cost_usd", 0), d.get("num_turns", 0), len(anh or []), tk["ma"],
                            getattr(VIEC, "video", "")])
        txt = res + " " + (r.stderr or "")
        if (rl and rl.get("status") == "rejected") or re.search(r"hit your .*limit|usage limit|limit reached", txt, re.I):
            if not (rl and rl.get("status") == "rejected"):
                _ghi_trang_thai(tk["ma"], het_den=time.time() + 3600)
            da_thu.append(tk["ma"]); continue              # hết hạn mức → thử tài khoản khác
        if re.search(r"login expired|please run /login|not logged in|oauth token revoked|invalid api key", txt, re.I):
            _ghi_trang_thai(tk["ma"], dang_nhap=False)
            da_thu.append(tk["ma"]); continue              # mất đăng nhập → báo app, thử tài khoản khác
        if r.returncode != 0 or d.get("is_error"):
            raise RuntimeError(f"Claude lỗi ({vai}, {tk['ma']}): {(res or r.stderr)[:300]}")
        return res, u


def kiem_han_muc(ma):
    """Gọi 1 câu rất ngắn (Sonnet, suy nghĩ thấp) bằng đúng tài khoản để lấy hạn mức mới nhất."""
    tk = next((t for t in ds_tai_khoan() if t["ma"] == ma), None)
    if not tk:
        return {"loi": "không có tài khoản"}
    r, d, rl = _goi_1(tk, "kiểm hạn mức", "Trả đúng chữ: OK", None, "sonnet", "low", 120)
    txt = (d.get("result") or "") + " " + (r.stderr or "")
    if re.search(r"login expired|please run /login|not logged in|oauth token revoked", txt, re.I):
        _ghi_trang_thai(ma, dang_nhap=False)
    return doc_trang_thai().get(ma, {})


def lay_json(text):
    """Lấy khối JSON (mảng hoặc đối tượng) đầu tiên trong câu trả lời."""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = m.group(1) if m else text
    i_mang, i_dt = body.find("["), body.find("{")
    thu_tu = (r"\{.*\}", r"\[.*\]") if i_dt != -1 and (i_mang == -1 or i_dt < i_mang) else (r"\[.*\]", r"\{.*\}")
    for pat in thu_tu:   # lấy kiểu JSON xuất hiện TRƯỚC (đối tượng có mảng bên trong không bị hiểu nhầm thành mảng)
        mm = re.search(pat, body, re.S)
        if mm:
            try:
                return json.loads(mm.group(0))
            except Exception:
                continue
    raise ValueError("AI không trả JSON hợp lệ: " + text[:200])
