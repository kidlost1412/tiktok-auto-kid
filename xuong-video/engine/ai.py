"""Gọi Claude CLI headless gọn nhẹ + NHIỀU TÀI KHOẢN (Kid 10/11/2026: 3 tài khoản, xem hạn mức từng cái, tự chuyển khi sắp hết).
goi(vai, prompt, anh=[...]) → (text, usage).
- Mỗi tài khoản là 1 thư mục cấu hình riêng (CLAUDE_CONFIG_DIR; tài khoản 1 = thư mục mặc định ~/.claude).
- Mỗi lần gọi dùng --output-format stream-json: CLI tự báo hạn mức chính thức (rate_limit_event: 5 giờ, 7 ngày, giờ reset)
  → ghi vào lich-su/tai-khoan.json, app hiển thị. Hub KHÔNG đọc file đăng nhập/token.
- Chọn tài khoản còn dư nhiều nhất; tài khoản hết hạn mức → đánh dấu tới giờ reset, tự chuyển sang tài khoản khác.
  Chỉ báo HetHanMuc khi MỌI tài khoản đều hết."""
import csv, datetime, json, os, queue, re, subprocess, threading, time
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, ghi_json
F_TK = HUB / "lich-su" / "tai-khoan.json"
_lock = threading.RLock()


def vai_he_thong(vai):
    """Vai ghi vào lời dặn HỆ THỐNG: mọi "đạo diễn <gu>" gộp thành "đạo diễn" để 4 gu cùng 1 system prompt (giữ prompt cache). Log/token vẫn dùng vai đầy đủ."""
    return "đạo diễn" if str(vai).startswith("đạo diễn") else vai


def he_thong(vai):
    """Lời dặn chung gửi mọi vai AI — mẫu prompt/he-thong.md (chỉnh được trong tab Prompt AI)."""
    import prompt_mau
    return prompt_mau.dien("he-thong", vai=vai_he_thong(vai))


NGUONG_DOI = 0.92      # dùng quá 92% cửa sổ 5 giờ / 7 ngày → ưu tiên tài khoản khác


VIEC = threading.local()      # ekip đặt VIEC.video = tên video trước khi gọi → token.csv biết lượt gọi thuộc video nào
# ekip đặt thêm VIEC.so (dict sổ token của video) + VIEC.pha (bước: dao_dien / giam_khao / sua_dao_dien / ...) → _ghi_so cộng từng lượt gọi vào đó


def _ghi_so(u, usd=0.0):
    """Cộng token 1 lượt gọi (kể cả lượt hỏng / đổi tài khoản: đã tốn thật) vào sổ của việc đang chạy trong luồng này; không có sổ → bỏ qua."""
    so = getattr(VIEC, "so", None)
    if not isinstance(so, dict):
        return
    m = so.setdefault(getattr(VIEC, "pha", None) or "khac", {"luot": 0, "vao": 0, "cache_tao": 0, "cache_doc": 0, "ra": 0, "usd": 0.0})
    m["luot"] += 1
    for k, src in (("vao", "input_tokens"), ("cache_tao", "cache_creation_input_tokens"), ("cache_doc", "cache_read_input_tokens"), ("ra", "output_tokens")):
        m[k] += int((u or {}).get(src) or 0)
    m["usd"] = round(m["usd"] + float(usd or 0), 4)


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


MA_LO = ""       # mã sản phẩm của lô đang chạy trong tiến trình này (ekip đặt) → token.csv ghi cột "lo" để tách chi phí từng lô chạy song song


def _ghi_trang_thai(ma, **kv):
    """Đọc-sửa-ghi tai-khoan.json: nhiều lô (nhiều tiến trình) + app cùng ghi → khoá file HĐH để không đè nhau (quá 5 s không lấy được khoá → ghi không khoá, như cũ)."""
    from su_kien import khoa_tep
    with _lock:
        try:
            with khoa_tep(F_TK, 5):
                return _ghi_trang_thai_khong_khoa(ma, **kv)
        except TimeoutError:
            return _ghi_trang_thai_khong_khoa(ma, **kv)


def _ghi_trang_thai_khong_khoa(ma, **kv):
    d = doc_trang_thai(); x = d.setdefault(ma, {}); x.update(kv)
    F_TK.parent.mkdir(exist_ok=True)
    ghi_json(F_TK, d, indent=1)


def env_tk(tk):
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
        env.pop(k, None)                       # không để khoá API ghi đè gói đăng ký
    # CLI ghi cache 1 giờ (giá ×2 đầu vào) cho cả đề bài, mà đề bài mỗi lượt khác đuôi nên không lượt nào đọc lại (đo 14–22/11: 0 token đọc) → tắt
    env["DISABLE_PROMPT_CACHING"] = "1"
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
        if tk and co_dinh not in bo_qua and not (x.get("het_den") and x["het_den"] > now) and x.get("dang_nhap") is not False and not x.get("bi_chan"):
            return tk
        if not c.get("tu_chuyen", True):
            return None                                  # anh chọn cố định + không cho tự chuyển → dừng, báo anh chọn tài khoản khác
    for tk in ds_tai_khoan():
        if tk["ma"] in bo_qua:
            continue
        x = st.get(tk["ma"], {})
        if x.get("het_den") and x["het_den"] > now:
            continue
        if x.get("dang_nhap") is False or x.get("bi_chan"):
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


_RE_BI_CHAN = re.compile(r"organization has disabled|disabled claude subscription access|ask your admin to enable", re.I)   # gói bị tổ chức tắt quyền dùng Claude Code


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


def _nap_live(tt, line):
    """1 dòng stream-json của CLI → chữ/suy nghĩ đang về → việc trực tiếp (truc_tiep). Trả True nếu là mảnh chữ. Không bao giờ ném lỗi."""
    try:
        if '"stream_event"' not in line:
            return False
        ev = json.loads(line)
        if ev.get("type") != "stream_event":
            return False
        d = (ev.get("event") or {}).get("delta") or {}
        k = d.get("type")
        if k == "text_delta":
            tt.chu(d.get("text") or ""); return True
        if k == "thinking_delta":
            tt.nghi(d.get("thinking") or "")
    except Exception:
        pass
    return False


def _doc_luong(pr, stdin, timeout, vai, model):
    """Thay pr.communicate(stdin, timeout): gửi stdin + đọc stdout TỪNG DÒNG (luồng riêng) để đẩy chữ Claude đang viết sang trang Khu Tự Trị,
    luồng khác gom stderr. Cùng ngữ nghĩa hạn chót: quá `timeout` giây (cả lúc chờ tiến trình thoát) → taskkill cả cây, ném đúng lỗi cũ.
    → (toàn bộ stdout, stderr) y hệt communicate."""
    import truc_tiep as TT
    tt = TT.hien_tai()
    hang, dong, loi = queue.Queue(), [], []

    def doc_out():
        try:
            for line in pr.stdout:
                hang.put(line)
        except Exception:
            pass
        finally:
            hang.put(None)

    def doc_err():
        try:
            loi.append(pr.stderr.read() or "")
        except Exception:
            pass

    def ghi_in():
        try:
            pr.stdin.write(stdin)
        except Exception:
            pass
        finally:
            try:
                pr.stdin.close()
            except Exception:
                pass
    ts = [threading.Thread(target=f, daemon=True) for f in (doc_out, doc_err, ghi_in)]
    for t in ts:
        t.start()

    def het_gio():
        subprocess.run(["taskkill", "/PID", str(pr.pid), "/T", "/F"], capture_output=True)     # tắt CẢ cây tiến trình (node), không để chạy ngầm tốn hạn mức
        try:
            pr.wait(10)
        except Exception:
            pass
        for t in ts:
            t.join(5)
        if tt is not None:
            tt.het_chu()
        raise RuntimeError(f"Claude quá {timeout}s ({vai}) — đã dừng")
    t0 = time.monotonic(); han = t0 + timeout
    if tt is not None:
        tt.reset_chu(); tt.cap(chi_tiet={"model": model})
    co_chu = False
    while True:
        con = han - time.monotonic()
        if con <= 0:
            het_gio()
        try:
            line = hang.get(timeout=min(1.0, con))
        except queue.Empty:
            if tt is not None:
                tt.nhip(giay=round(time.monotonic() - t0))        # chưa có chữ mới: vẫn báo "còn đang làm" + số giây đã chờ
            continue
        if line is None:
            break
        dong.append(line)
        if tt is not None and _nap_live(tt, line):
            co_chu = True
    try:
        pr.wait(timeout=max(1.0, han - time.monotonic()))
    except subprocess.TimeoutExpired:
        het_gio()
    for t in ts[1:]:
        t.join(5)
    out = "".join(dong)
    if tt is not None:
        if not co_chu:                                           # CLI cũ không có --include-partial-messages: lấy chữ cuối cùng
            for line in reversed(dong):
                if '"type":"result"' in line.replace(" ", ""):
                    try:
                        tt.chu(str(json.loads(line).get("result") or ""))
                    except Exception:
                        pass
                    break
        tt.het_chu(); tt.cap(chi_tiet={"giay": round(time.monotonic() - t0)})
    return out, "".join(loi)


def _goi_1(tk, vai, prompt, anh, model, effort, timeout, nhung=False):
    """nhung=True: ảnh gửi THẲNG trong 1 tin nhắn (stream-json, không công cụ → đúng 1 lượt). nhung=False: cách cũ (Read)."""
    c = cfg()
    claude = c["duong_dan"]["claude"]
    live = bool(c.get("truc_tiep", True))           # trang Khu Tự Trị xem chữ Claude đang viết (truc_tiep.py); False → cách cũ, không ghi gì
    cmd = [claude, "-p", "--output-format", "stream-json", "--verbose"] + (["--include-partial-messages"] if live else []) + \
          ["--model", model, "--effort", effort,
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
    if live:
        out, err = _doc_luong(pr, stdin, timeout, vai, model)
    else:
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
    """Gọi Claude. Chữ Claude đang viết được đẩy vào "việc trực tiếp" của luồng gọi (ekip/viết lời mở sẵn); chưa có việc nào thì tự mở 1 việc theo vai."""
    import truc_tiep as TT
    if TT.hien_tai() is not None or not cfg().get("truc_tiep", True):
        return _goi(vai, prompt, anh, model, effort, timeout)
    v, viec = TT.mo_ta_vai(vai)
    with TT.viec(v, viec, video=getattr(VIEC, "video", "") or None):
        return _goi(vai, prompt, anh, model, effort, timeout)


def nao_ai():
    """Bộ não AI của mọi vai đang gọi Claude: "claude" (mặc định) hoặc "gpt" (ChatGPT qua Codex CLI). Biến môi trường XUONG_AI (thử 1 lô) > config "ai_nao"."""
    v = (os.environ.get("XUONG_AI") or cfg().get("ai_nao") or "claude").strip().lower()
    return "gpt" if v in ("gpt", "chatgpt", "codex", "openai") else "claude"


def _goi_gpt(vai, prompt, anh=None, effort=None, timeout=1200):
    """Gọi ChatGPT qua `codex exec` (đăng nhập ChatGPT sẵn của máy): cùng lời dặn hệ thống + đề bài + ảnh (-i). Không công cụ, không ghi file.
    config "gpt": {"model": "gpt-6.2-sol", "effort": "high"}; effort vai truyền vào (vd. "low" cho gom bài học) được giữ. → (text, usage kiểu Claude)."""
    import shutil, tempfile
    import truc_tiep as TT
    g = cfg().get("gpt") or {}
    model = str(g.get("model") or "gpt-6.2-sol")
    effort = str(effort if effort in ("low", "medium", "high", "xhigh", "max") and effort != "high" else (g.get("effort") or "high"))
    codex = cfg().get("duong_dan", {}).get("codex") or shutil.which("codex") or "codex"
    full = (f"=== LỜI DẶN HỆ THỐNG (vai: {vai_he_thong(vai)}) ===\n{he_thong(vai)}\n\n=== ĐỀ BÀI ===\n{prompt}\n\n"
            + (("Ảnh đính kèm theo thứ tự: " + " ".join(f"{i}) {Path(str(a)).name}" for i, a in enumerate(anh, 1)) + "\n\n") if anh else "")
            + "Trả lời thẳng bằng nội dung đề bài yêu cầu. Không dùng công cụ, không chạy lệnh, không đọc/ghi file.\n")
    t0 = datetime.datetime.now()
    with tempfile.TemporaryDirectory(prefix="xv-gpt-") as td:
        cmd = [codex, "exec", "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-c", "notify=[]", "--skip-git-repo-check",
               "-s", "read-only", "--ephemeral", "--json", "-C", td]
        for a in anh or []:
            cmd += ["-i", str(a)]
        cmd.append("-")
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                              errors="replace", cwd=td)
        try:
            out, err = pr.communicate(full, timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(pr.pid), "/T", "/F"], capture_output=True)
            pr.communicate()
            raise RuntimeError(f"ChatGPT quá {timeout}s ({vai}) — đã dừng")
    msg, u, loi = "", {}, ""
    tt = TT.hien_tai()
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        it, k = ev.get("item") or {}, ev.get("type")
        if k == "item.completed" and it.get("type") == "agent_message":
            msg = it.get("text") or msg
            if tt is not None:
                try:
                    tt.chu(msg)
                except Exception:
                    pass
        elif k == "turn.completed":
            u = ev.get("usage") or {}
        elif k in ("error", "turn.failed"):
            loi = str(ev.get("message") or (ev.get("error") or {}).get("message") or line)[:300]
    usage = {"input_tokens": max(0, int(u.get("input_tokens") or 0) - int(u.get("cached_input_tokens") or 0)), "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": int(u.get("cached_input_tokens") or 0), "output_tokens": int(u.get("output_tokens") or 0),
             "reasoning_output_tokens": int(u.get("reasoning_output_tokens") or 0)}
    import su_kien as _sk
    _sk.noi_them(HUB / "lich-su" / "token.csv", _sk.dong_csv([
        t0.strftime("%Y-%m-%d %H:%M:%S"), vai, model, effort, round((datetime.datetime.now() - t0).total_seconds(), 1),
        usage["input_tokens"], 0, usage["cache_read_input_tokens"], usage["output_tokens"], 0, 1, len(anh or []), "chatgpt",
        getattr(VIEC, "video", ""), MA_LO]), ma_hoa="utf-8-sig",
        dau=_sk.dong_csv(["luc", "vai", "model", "effort", "giay", "vao", "vao_cache_tao", "vao_cache_doc", "ra", "usd_uoc", "luot", "so_anh", "tai_khoan", "video", "lo"]))
    _ghi_so(usage)
    txt = loi + " " + (err or "")[-500:]
    if not msg and re.search(r"usage limit|rate limit|limit reached|quota|too many requests", txt, re.I):
        raise HetHanMuc("ChatGPT đã hết hạn mức: " + loi[:200])
    if not msg and re.search(r"login|not logged in|unauthorized|401|auth", txt, re.I):
        raise HetHanMuc("ChatGPT chưa đăng nhập (mở Codex/ChatGPT đăng nhập lại): " + loi[:200])
    if not msg:
        raise RuntimeError(f"ChatGPT lỗi ({vai}): {(loi or err or out)[-300:]}")
    return msg, usage


def _goi(vai, prompt, anh=None, model=None, effort=None, timeout=1200):
    if nao_ai() == "gpt":
        return _goi_gpt(vai, prompt, anh, effort, timeout)
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
        import su_kien as _sk              # nhiều lô cùng ghi token.csv: noi_them = khoá file HĐH + dòng tiêu đề đặt trong khoá (không ghi trùng / không ném lỗi)
        _sk.noi_them(HUB / "lich-su" / "token.csv", _sk.dong_csv([
            t0.strftime("%Y-%m-%d %H:%M:%S"), vai, model, effort, round((datetime.datetime.now() - t0).total_seconds(), 1),
            u.get("input_tokens", 0), u.get("cache_creation_input_tokens", 0), u.get("cache_read_input_tokens", 0),
            u.get("output_tokens", 0), d.get("total_cost_usd", 0), d.get("num_turns", 0), len(anh or []), tk["ma"],
            getattr(VIEC, "video", ""), MA_LO]), ma_hoa="utf-8-sig",
            dau=_sk.dong_csv(["luc", "vai", "model", "effort", "giay", "vao", "vao_cache_tao", "vao_cache_doc", "ra", "usd_uoc", "luot", "so_anh", "tai_khoan", "video", "lo"]))
        _ghi_so(u, d.get("total_cost_usd", 0))
        txt = res + " " + (r.stderr or "")
        if (rl and rl.get("status") == "rejected") or re.search(r"hit your .*limit|usage limit|limit reached", txt, re.I):
            if not (rl and rl.get("status") == "rejected"):
                _ghi_trang_thai(tk["ma"], het_den=time.time() + 3600)
            da_thu.append(tk["ma"]); continue              # hết hạn mức → thử tài khoản khác
        if re.search(r"login expired|please run /login|not logged in|oauth token revoked|invalid api key", txt, re.I):
            _ghi_trang_thai(tk["ma"], dang_nhap=False)
            da_thu.append(tk["ma"]); continue              # mất đăng nhập → báo app, thử tài khoản khác
        if _RE_BI_CHAN.search(txt):
            _ghi_trang_thai(tk["ma"], bi_chan=True)
            print(f"[ai] tài khoản {tk['ma']} bị tắt quyền dùng Claude Code → thử tài khoản khác", flush=True)
            da_thu.append(tk["ma"]); continue              # gói bị tổ chức tắt quyền → bỏ qua tới khi kiểm lại thấy dùng được
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
    elif _RE_BI_CHAN.search(txt):
        _ghi_trang_thai(ma, bi_chan=True)
    elif r.returncode == 0 and not d.get("is_error"):
        _ghi_trang_thai(ma, bi_chan=False)                  # kiểm lại thấy dùng được → bỏ cờ bị chặn
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
