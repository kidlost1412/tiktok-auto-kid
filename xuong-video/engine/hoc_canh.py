"""HỌC CẢNH (kiểu 2: máy đo, AI chỉ điền phiếu) bằng Google Antigravity (ứng dụng máy tính, đã đăng nhập sẵn) — không dùng khoá API.
MÁY cắt cảnh (cat_canh.py, OpenCV, không AI) → mốc giây, độ nét, độ rung. Antigravity xem TRỌN video (có tiếng) + các tờ ảnh đánh số rồi điền phiếu cố định
(phieu.py) cho đúng các cảnh máy đã cắt; hub kiểm phiếu chặt, cảnh sai được hỏi lại 1 lần, rồi ghi _mo-ta/<video>.mo-ta.json theo khung cũ + kieu=2.
Antigravity mở thì nó ghi %USERPROFILE%\\.gemini\\antigravity\\daemon\\hub_<cổng>.json {pid, httpPort, csrfToken…}. Hub gọi
language_server.exe agentapi (new-conversation) với 2 biến môi trường ANTIGRAVITY_LS_ADDRESS / ANTIGRAVITY_CSRF_TOKEN; AI GHI JSON ra 1 file tạm
trong <kho>/_tam/hoc-canh/<lô>/ và hub chờ file đó (ổn định 2 lần kiểm). Mỗi lô ≤ 24 cảnh (2 tờ ảnh) và ≤ 5 video. Mỗi lần chạy kiểm lại kho nên bấm lại là làm tiếp.
Trạng thái việc học + mã cuộc trò chuyện đang mở được ghi ở lich-su/hoc-canh-job.json: hub khởi động lại giữa chừng thì khoi_phuc() huỷ gọn việc dở.
agentapi không cho đọc trạng thái lỗi/hết lượt (metadata chỉ có cấu hình) → quá hạn chờ thì báo lỗi; 2 lô liền không có phiếu thì dừng cả việc."""
import collections.abc, contextvars, ctypes, hashlib, json, os, shutil, socket, subprocess, sys, threading, time, urllib.request, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kiem_mo_ta as km
import cat_canh
import phieu

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
import prompt_mau
import truc_tiep as TT        # "việc trực tiếp" cho trang Khu Tự Trị (chỉ ghi file nhỏ, nuốt mọi lỗi)
LS = HUB / "lich-su"
MODELS = {"gemini-4-hydrogen-high": "Gemini 4 Hydrogen · High (mặc định)", "gemini-4-argon-high": "Gemini 4 Argon · High", "gemini-3.8-flash-high": "Gemini 3.8 Flash · High",
          "gemini-3.8-flash-medium": "Gemini 3.8 Flash · Medium"}      # id thật của Antigravity (agentapi tự rơi về bậc flash nếu id không có)
MODEL_MAC_DINH = "gemini-4-hydrogen-high"
SONG_SONG_MAC_DINH = 2
HAN_MOI_VIDEO_S = 150      # hạn chờ của 1 lô = 150 giây × số video + 60 giây
HAN_THEM_S = 60
HAN_LO_TOI_DA_S = 2400     # tối đa 40 phút/lô
CHU_KY_S = 3
SO_CANH_LO = 24            # mỗi lô tối đa 24 cảnh (2 tờ ảnh 4×3) và 5 video
SO_VIDEO_LO = 5
MAX_CANH_VIDEO = 24        # video cắt ra nhiều hơn thì lấy 24 cảnh rải đều (để vừa 1 lô)
MSG_AGY_VO = "Antigravity đang mở nhưng chưa sẵn sàng — bấm Mở Antigravity và đợi vài giây."
MSG_AGY_CHUA_MO = "Antigravity chưa mở — bấm Mở Antigravity rồi Học cảnh lại."
TEN_TIEN_TRINH_AGY = ("language_server.exe", "antigravity.exe")


def _thu_muc_he_thong(csidl, dflt):
    """Thư mục người dùng theo Windows (không phụ thuộc biến môi trường — app chạy dưới launcher có thể thiếu USERPROFILE/LOCALAPPDATA)."""
    try:
        buf = ctypes.create_unicode_buffer(520)
        if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) == 0 and buf.value:
            return Path(buf.value)
    except Exception:
        pass
    return Path(dflt)


NHA = _thu_muc_he_thong(0x28, Path.home())                                        # CSIDL_PROFILE
LOCAL = _thu_muc_he_thong(0x1c, Path.home() / "AppData" / "Local")                # CSIDL_LOCAL_APPDATA
DAEMON_DIR = NHA / ".gemini" / "antigravity" / "daemon"
AGY_EXE = LOCAL / "Programs" / "antigravity" / "Antigravity.exe"
LS_EXE = LOCAL / "Programs" / "antigravity" / "resources" / "bin" / "language_server.exe"
NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ChuaMo(Exception):
    pass


class LoiTam(Exception):
    pass


class Huy(Exception):
    """Anh bấm Dừng: bỏ việc đang làm ngay."""


# Mỗi SẢN PHẨM đang học có 1 "run": sự kiện "huy" + các cuộc trò chuyện Antigravity đã mở + tiến trình agentapi (để Dừng thật sự huỷ được đúng việc của sản phẩm đó)
# và 1 job (tiến độ). Nhiều sản phẩm học cùng lúc → mỗi sản phẩm 1 run/1 job riêng; luồng của sản phẩm nào biết run của nó qua biến ngữ cảnh _CUR.
_RUNS = {}                 # khoá sản phẩm (str(ma)) → run
_JOBS = {}                 # khoá sản phẩm → job (dict tiến độ)
_ULTIMA = [None]           # khoá của việc bắt đầu gần nhất (JOB/_RUN dạng cũ trỏ vào đây)
_RUN_LOCK = threading.Lock()
_CUR = contextvars.ContextVar("hoc_canh_run", default=None)


def _run_moi(khoa, kho, job):
    return {"huy": threading.Event(), "conv": set(), "proc": set(), "kho": str(kho), "ma": khoa, "job": job}


_RUN0 = _run_moi("", "", None)       # run "rỗng" cho luồng không thuộc việc học nào (không ai đặt huy)


def _run_hien():
    """Run của luồng hiện tại (luồng học / luồng con được sao ngữ cảnh); không thuộc việc nào → run rỗng."""
    return _CUR.get() or _RUN0


class _VaoRun:
    """_RUN dạng cũ (dict): trỏ vào run của luồng hiện tại."""
    def __getitem__(self, k): return _run_hien()[k]
    def get(self, k, d=None): return _run_hien().get(k, d)


_RUN = _VaoRun()
GRACE_DUNG_S = 3          # đang gửi việc cho Antigravity mà bấm Dừng: chờ tối đa chừng này giây lấy mã cuộc trò chuyện để huỷ, quá thì giết tiến trình


def _giet_cay(pid):
    """Giết cả cây tiến trình (Windows: taskkill /T /F). Không bao giờ ném lỗi."""
    try:
        subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True, timeout=10, creationflags=NO_WIN)
    except Exception:
        try:
            os.kill(int(pid), 9)
        except Exception:
            pass


# ----------------------------------------------------------------------------------------------- Antigravity: trạng thái / mở / gọi
def _ten_anh(pid):
    """Tên file chương trình (chữ thường) của tiến trình `pid`; "" nếu không đọc được."""
    try:
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.restype = ctypes.c_void_p
        k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        k.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
        k.CloseHandle.argtypes = [ctypes.c_void_p]
        h = k.OpenProcess(0x1000, 0, int(pid))                      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1040); n = ctypes.c_ulong(1040)
            return os.path.basename(buf.value).lower() if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ""
        finally:
            k.CloseHandle(h)
    except Exception:
        return ""


def _song(pid):
    """Tiến trình còn sống VÀ đúng là Antigravity (language_server.exe / Antigravity.exe) — số PID cũ trong hub_*.json có thể đã bị Windows cấp cho chương trình khác."""
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, 0, int(pid))
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == 259 and _ten_anh(pid) in TEN_TIEN_TRINH_AGY          # STILL_ACTIVE
    except Exception:
        return False


def _cong_mo(port, han=0.5):
    """Cổng http của Antigravity có đang nhận kết nối không (127.0.0.1)."""
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=han):
            return True
    except Exception:
        return False


_HUB_NHO = {"t": 0.0, "h": None}


def tim_hub(song=None, cong=None):
    """→ dict {pid, httpPort, csrfToken, lsVersion} của Antigravity đang mở, hoặc None. File hub_*.json mới nhất chỉ tính khi PID còn sống, đúng là
    Antigravity VÀ cổng http nhận kết nối. Kết quả có (mặc định) nhớ 3 giây để hỏi trạng thái liên tục không tốn. song/cong: hàm kiểm thay thế khi thử (không nhớ tạm)."""
    mac_dinh = song is None and cong is None
    if mac_dinh and _HUB_NHO["h"] and time.time() - _HUB_NHO["t"] < 3:
        return _HUB_NHO["h"]
    song, cong = song or _song, cong or _cong_mo
    tim = None
    try:
        fs = sorted(DAEMON_DIR.glob("hub_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    except Exception:
        fs = []
    for f in fs:
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            if j.get("httpPort") and j.get("csrfToken") and song(j.get("pid")) and cong(j.get("httpPort")):
                tim = j
                break
        except Exception:
            continue
    if mac_dinh:
        _HUB_NHO.update(t=time.time(), h=tim)
    return tim


_AGY_EXE = {"t": 0.0, "v": False}


def _agy_exe_chay():
    """Antigravity.exe có đang chạy (dù dịch vụ chưa sẵn sàng) không — dò tên tiến trình bằng tasklist, nhớ 5 giây."""
    if time.time() - _AGY_EXE["t"] < 5:
        return _AGY_EXE["v"]
    v = False
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Antigravity.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=5,
                           creationflags=NO_WIN, errors="replace")
        v = "antigravity.exe" in (r.stdout or "").lower()
    except Exception:
        v = False
    _AGY_EXE.update(t=time.time(), v=v)
    return v


def trang_thai_agy():
    """{mo, phien_ban, vo} — mo: dịch vụ Antigravity sẵn sàng; vo: Antigravity.exe đang chạy nhưng dịch vụ chưa lên (mới mở / đang kẹt). Không gọi mô hình."""
    h = tim_hub()
    return {"mo": bool(h), "phien_ban": (h or {}).get("lsVersion"), "vo": False if h else _agy_exe_chay()}


def _msg_chua_mo():
    return MSG_AGY_VO if _agy_exe_chay() else MSG_AGY_CHUA_MO


def mo_antigravity():
    """Mở Antigravity tách rời hub (đóng hub không tắt nó). Antigravity.exe đang chạy mà dịch vụ chưa lên thì vẫn gọi mở (nó tự đưa bản đang chạy lên)."""
    if tim_hub():
        return {"ok": True, "da_mo": True}
    if not AGY_EXE.exists():
        return {"ok": False, "loi": "Không thấy Antigravity ở máy này."}
    vo = _agy_exe_chay()
    try:
        subprocess.Popen([str(AGY_EXE)], close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=0x00000008 | 0x00000200)          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    except Exception as e:
        return {"ok": False, "loi": str(e)[:150]}
    return {"ok": True, "vo": vo}


def _agentapi(*args, timeout=60, project=None):
    h = tim_hub()
    if not h:
        raise ChuaMo(_msg_chua_mo())
    if not LS_EXE.exists():
        raise ChuaMo("Không thấy language_server.exe của Antigravity.")
    run = _run_hien(); huy = run["huy"]
    if huy.is_set():
        raise Huy()
    env = dict(os.environ, ANTIGRAVITY_LS_ADDRESS=f"127.0.0.1:{h['httpPort']}", ANTIGRAVITY_CSRF_TOKEN=str(h["csrfToken"]))
    if project:
        env["ANTIGRAVITY_PROJECT_ID"] = str(project)       # cuộc trò chuyện nằm trong "Project" (mục Projects ở thanh trái) có id này
    p = subprocess.Popen([str(LS_EXE), "agentapi", *args], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", errors="replace", creationflags=NO_WIN)
    with _RUN_LOCK:
        run["proc"].add(p)
    t0 = time.time(); t_huy = None
    try:
        while True:
            try:
                out, err = p.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if huy.is_set():
                    t_huy = t_huy or time.time()
                    if time.time() - t_huy >= GRACE_DUNG_S:          # quá thời gian chờ: giết cả cây tiến trình
                        _giet_cay(p.pid)
                        raise Huy()
                if time.time() - t0 > timeout:
                    _giet_cay(p.pid)
                    raise LoiTam(f"Antigravity không trả lời trong {timeout} giây.")
    finally:
        with _RUN_LOCK:
            run["proc"].discard(p)
        if p.poll() is None:
            _giet_cay(p.pid)
    return p.returncode, (out or ""), (err or "").replace(str(h["csrfToken"]), "***")


def _goi_ls(method, body, timeout=5):
    """Gọi thẳng máy chủ ngôn ngữ của Antigravity (Connect-RPC JSON, cùng cổng + csrf mà agentapi dùng). → dict hoặc None nếu lỗi."""
    h = tim_hub()
    if not h:
        return None
    try:
        rq = urllib.request.Request(f"http://127.0.0.1:{h['httpPort']}/exa.language_server_pb.LanguageServerService/{method}",
                                    data=json.dumps(body).encode(), method="POST",
                                    headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1", "x-codeium-csrf-token": str(h["csrfToken"])})
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace") or "{}")
    except Exception:
        return None


def huy_cuoc_tro_chuyen(cid):
    """Bảo Antigravity DỪNG cuộc trò chuyện `cid` (cả các tác tử con + lệnh nền). Cố gắng hết sức, không ném lỗi. → True nếu có gọi được."""
    if not cid:
        return False
    a = _goi_ls("ForceStopCascadeTree", {"conversationId": str(cid)})
    b = _goi_ls("CancelCascadeInvocation", {"cascadeId": str(cid), "killBackgroundTasks": True})
    return a is not None or b is not None


def _dir_cuoc_tro_chuyen():
    return NHA / ".gemini" / "antigravity"


def _xoa_file_cuoc(cid):
    """Cách dự phòng khi Antigravity đã đóng: xoá ĐÚNG file của cuộc `cid` (conversations/<cid>.db và brain/<cid>), không đụng gì khác. → True nếu còn sót gì đó đã xoá."""
    import re
    if not re.fullmatch(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", str(cid or "")):
        return False
    g = _dir_cuoc_tro_chuyen(); da = False
    for f in (g / "conversations" / f"{cid}.db", g / "conversations" / f"{cid}.db-wal", g / "conversations" / f"{cid}.db-shm"):
        try:
            f.unlink(); da = True
        except OSError:
            pass
    try:
        b = g / "brain" / str(cid)
        if b.is_dir():
            shutil.rmtree(b); da = True
    except OSError:
        pass
    return da


def xoa_cuoc_tro_chuyen(cid):
    """XOÁ hẳn cuộc trò chuyện `cid` khỏi Antigravity (để không chất đống chat). Dừng nó trước, rồi gọi RPC DeleteCascadeTrajectory {cascadeId}
    (đã thử thật: xoá luôn conversations/<cid>.db và brain/<cid>). RPC không gọi được mà Antigravity đã đóng thì xoá file của đúng cuộc đó.
    Cố gắng hết sức, KHÔNG ném lỗi. → True nếu đã xoá/gọi xoá được."""
    if not cid:
        return False
    try:
        try:
            huy_cuoc_tro_chuyen(cid)
        except Exception:
            pass
        for lan in range(2):
            if _goi_ls("DeleteCascadeTrajectory", {"cascadeId": str(cid)}, timeout=10) is not None:
                return True
            if tim_hub() is None:
                return _xoa_file_cuoc(cid)
            time.sleep(1)
    except Exception:
        pass
    return False


# --- Dọn bù chat của app còn sót trong Antigravity -----------------------------------------------------------------------------
# Xoá ngay sau mỗi lần hỏi có thể trượt (Antigravity bận / đóng giữa chừng, gửi việc lỗi trước khi có mã chat, chat có từ trước bản
# biết tự xoá) → chat nằm lại mãi. Dọn bù: CHỈ những chat thuộc Project do chính hub tạo (id = uuid5 của thư mục, xem
# id_project_hoc_canh) — không bao giờ đụng chat của chủ máy — đã im lặng quá DON_SAU_S. Xoá bằng RPC (gỡ khỏi danh sách bên trái).
DON_SAU_S = 30 * 60          # chat của app im lặng quá chừng này mới dọn bù (lô Học cảnh dài vẫn cập nhật liên tục)
DON_CACH_S = 10 * 60
TIEU_DE_APP = "Xưởng Video · "    # tiêu đề chat Học cảnh do hub đặt (xem chạy lô)         # dọn bù nền tối đa 1 lần / chừng này giây
_DON = {"t": 0.0, "dang": False}
_DON_LOCK = threading.Lock()


def project_cua_app():
    """Tập id Project do hub tạo: file %USERPROFILE%\\.gemini\\config\\projects\\<id>.json có id = uuid5 của một thư mục làm việc của nó."""
    ids = set()
    try:
        files = list(PROJECT_DIR.glob("*.json"))
    except OSError:
        return ids
    for f in files:
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            for res in ((j.get("projectResources") or {}).get("resources") or []):
                u = res.get("folderUri") if isinstance(res, dict) else None
                if u and j.get("id") == str(uuid.uuid5(uuid.NAMESPACE_URL, "xuong-video-hoc-canh:" + _uri_thanh_duong_dan(u))):
                    ids.add(j["id"])
        except Exception:
            pass
    return ids


def _thoi_diem(v):
    """'2026-11-16 09:18:30.9547956+00:00' (Antigravity ghi 7 chữ số lẻ) → datetime có múi giờ, hoặc None."""
    import datetime as _dt, re
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?", str(v or ""))
    if not m:
        return None
    tz = m.group(4) or "+00:00"
    tz = "+00:00" if tz == "Z" else (tz if ":" in tz else tz[:3] + ":" + tz[3:])
    try:
        return _dt.datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}.{(m.group(3) or '0')[:6].ljust(6, '0')}{tz}")
    except ValueError:
        return None


def chat_sot(bay_gio=None, du_lieu=None, ids=None):
    """[mã chat] của app đã im lặng quá DON_SAU_S và không còn chạy. Chỉ ĐỌC conversation_summaries.db (mở chế độ chỉ đọc).
    Của app = nằm trong Project do hub tạo, HOẶC tiêu đề bắt đầu bằng TIEU_DE_APP (Học cảnh khi không có Project riêng)."""
    import datetime as _dt, sqlite3
    ids = project_cua_app() if ids is None else ids
    f = Path(du_lieu) if du_lieu else NHA / ".gemini" / "antigravity" / "conversation_summaries.db"
    if not f.is_file():
        return []
    try:
        c = sqlite3.connect(f"file:{f.as_posix()}?mode=ro", uri=True, timeout=2)
        try:
            rows = c.execute("select conversation_id, project_id, last_modified_time, not_fully_idle, title from conversation_summaries").fetchall()
        finally:
            c.close()
    except Exception:
        return []
    han = (bay_gio or _dt.datetime.now(_dt.timezone.utc)) - _dt.timedelta(seconds=DON_SAU_S)
    with _RUN_LOCK:
        dang = {c for r in _RUNS.values() for c in r.get("conv", ())} if isinstance(_RUNS, dict) else set()
    out = []
    for cid, pid, m, ban, tieu_de in rows:
        t = _thoi_diem(m)
        cua_app = pid in ids or str(tieu_de or "").startswith(TIEU_DE_APP)
        if cid and cua_app and not ban and cid not in dang and t is not None and t < han:
            out.append(str(cid))
    return out


def don_chat_sot(toi_da=300):
    """Xoá các chat sót của app (RPC). Antigravity đóng thì để lần sau (xoá file khi đóng không gỡ được khỏi danh sách). → số chat đã xoá."""
    if not tim_hub():
        return 0
    n = 0
    for cid in chat_sot()[:toi_da]:
        if _goi_ls("DeleteCascadeTrajectory", {"cascadeId": cid}, timeout=10) is not None:
            n += 1
    return n


def don_chat_sot_nen(cach_s=DON_CACH_S):
    """Chạy don_chat_sot ở luồng nền, tối đa 1 lần / cach_s giây. → True nếu đã bắt đầu một lượt."""
    with _DON_LOCK:
        if _DON["dang"] or time.time() - _DON["t"] < cach_s:
            return False
        _DON.update(dang=True, t=time.time())

    def chay():
        try:
            n = don_chat_sot()
            if n:
                print(f"Antigravity: đã dọn {n} cuộc trò chuyện cũ của app còn sót.")
        except Exception as e:
            print("Dọn chat Antigravity còn sót bị lỗi:", e)
        finally:
            _DON["dang"] = False
    threading.Thread(target=chay, daemon=True, name="don-chat-agy").start()
    return True


def gui_hoi(model, prompt, tieu_de, project=None):
    """Mở 1 cuộc trò chuyện mới ở Antigravity → conversationId."""
    rc, out, err = _agentapi("new-conversation", f"--model={model}", f"--title={tieu_de}", prompt, project=project)
    try:
        cid = json.loads(out)["response"]["newConversation"]["conversationId"]
    except Exception:
        raise LoiTam("Antigravity không nhận việc: " + ((err or out).strip().splitlines() or [f"mã {rc}"])[-1][:150])
    if project:
        _kiem_project_nhan(cid, project)
    return cid


def _kiem_project_nhan(cid, project):
    """Antigravity có xếp cuộc trò chuyện vào đúng Project (nơi đã bật tự duyệt) không? Không thì báo anh đóng/mở lại Antigravity 1 lần."""
    try:
        rc, o, e = _agentapi("get-conversation-metadata", cid, timeout=15)
        pid = json.loads(o)["response"]["conversationMetadata"]["metadata"].get("projectId")
    except Exception:
        return
    if pid != project:
        _job_hien()["canh_bao"] = ("Antigravity chưa nhận Project tự duyệt của Xưởng Video nên có thể còn hỏi \"Accept\". "
                           "Đóng hẳn Antigravity rồi mở lại một lần, sau đó bấm Học cảnh tiếp.")


# ----------------------------------------------------------------------------------------------- Project của Antigravity
# Chat có metadata {projectId, workspaceUris}; đặt biến ANTIGRAVITY_PROJECT_ID khi gọi new-conversation thì chat vào đúng Project đó.
# Hub không tạo Project mới: tìm Project mà thư mục làm việc là thư mục kho hoặc thư mục cha của kho (lấy từ các chat cũ), không có thì thôi.
_PROJ = {"t": 0, "map": {}}


def _uri_thanh_duong_dan(u):
    from urllib.parse import unquote
    u = unquote(str(u))
    if u.startswith("file:///"):
        u = u[8:]
    return os.path.normcase(os.path.normpath(u.replace("/", os.sep)))


def danh_sach_project(toi_da=80):
    """{thư mục làm việc (chuẩn hoá) → projectId} đọc từ metadata các chat gần nhất. Lưu tạm 10 phút."""
    if time.time() - _PROJ["t"] < 600 and _PROJ["map"]:
        return _PROJ["map"]
    mp = {}
    try:
        d = NHA / ".gemini" / "antigravity" / "conversations"
        ids = sorted({f.name.split(".")[0] for f in d.glob("*.db")}, key=lambda i: (d / (i + ".db")).stat().st_mtime, reverse=True)[:toi_da]

        def doc(i):
            try:
                rc, o, e = _agentapi("get-conversation-metadata", i, timeout=30)
                m = json.loads(o)["response"]["conversationMetadata"]["metadata"]
                return m.get("projectId") or "", m.get("workspaceUris") or []
            except Exception:
                return "", []
        cx = [contextvars.copy_context() for _ in ids]                 # luồng con biết run của sản phẩm (Dừng giết được tiến trình)
        with ThreadPoolExecutor(max_workers=4) as ex:
            for pid, ws in ex.map(lambda a: a[0].run(doc, a[1]), zip(cx, ids)):
                if pid and pid != "outside-of-project" and ws:
                    for u in ws:
                        mp.setdefault(_uri_thanh_duong_dan(u), pid)
    except ChuaMo:
        return _PROJ["map"]
    except Exception:
        pass
    _PROJ.update(t=time.time(), map=mp)
    return mp


# --- Project riêng của Học cảnh: bật "Turbo" (tự duyệt) CHỈ cho thư mục kho này --------------------------------------------------
# Cuộc trò chuyện không nằm trong Project nào bị xếp vào "Outside of Project" (mặc định: hỏi duyệt mọi thứ) → Antigravity hiện nút Accept.
# Antigravity lưu mỗi Project ở %USERPROFILE%\.gemini\config\projects\<id>.json. Hub tạo ĐÚNG 1 file như vậy cho kho (id cố định theo đường dẫn kho,
# không đụng file/Project nào khác, không đổi cài đặt chung của Antigravity) với thư mục làm việc = thư mục kho và quyền Turbo.
PROJECT_DIR = NHA / ".gemini" / "config" / "projects"
QUYEN_TURBO = {"permissionPreset": "AGENT_PERMISSION_PRESET_TURBO", "autoExecutionPolicy": "CASCADE_COMMANDS_AUTO_EXECUTION_EAGER",
               "artifactReviewMode": "ARTIFACT_REVIEW_MODE_TURBO", "fileAccessPolicy": "AGENT_SETTING_POLICY_ALLOW", "sandboxMode": False}


def _chuan_kho(kho):
    return os.path.normcase(os.path.normpath(str(Path(kho).resolve())))


def _uri_kho(kho):
    from urllib.parse import quote
    p = str(Path(kho).resolve()).replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = p[0].lower() + p[1:]
    return "file:///" + quote(p, safe="/")


def id_project_hoc_canh(kho):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "xuong-video-hoc-canh:" + _chuan_kho(kho)))


def _file_project(kho):
    return PROJECT_DIR / (id_project_hoc_canh(kho) + ".json")


def trang_thai_quyen(kho):
    """{ok, id, thu_muc, bat: tự thiết lập có bật không} — ok = file Project đã có, trỏ đúng kho và đủ quyền Turbo."""
    pid = id_project_hoc_canh(kho)
    kq = {"ok": False, "id": pid, "thu_muc": str(kho), "bat": bool(doc_cau_hinh().get("tu_duyet", True))}
    try:
        j = json.loads(_file_project(kho).read_text(encoding="utf-8"))
        uris = [r.get("folderUri") for r in ((j.get("projectResources") or {}).get("resources") or [])]
        st = j.get("settings") or {}
        kq["ok"] = j.get("id") == pid and _uri_kho(kho) in uris and all(st.get(k) == v for k, v in QUYEN_TURBO.items())
    except Exception:
        pass
    return kq


def thiet_lap_quyen(kho):
    """Tạo/sửa file Project của kho (chỉ file này). Ghi nguyên tử (.tmp rồi thay). → {ok, id, loi?}."""
    pid = id_project_hoc_canh(kho)
    try:
        f = _file_project(kho)
        f.parent.mkdir(parents=True, exist_ok=True)
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(j, dict):
                j = {}
        except Exception:
            j = {}
        uri = _uri_kho(kho)
        res = [r for r in ((j.get("projectResources") or {}).get("resources") or []) if isinstance(r, dict) and r.get("folderUri") != uri]
        j.update(id=pid, name="Xưởng Video · Học cảnh · " + Path(kho).name[:40], projectResources={"resources": [{"folderUri": uri}] + res},
                 permissionGrants={"v2Migrated": True}, isWorkspaceOnly=False)
        st = j.get("settings") if isinstance(j.get("settings"), dict) else {}
        st.update(QUYEN_TURBO)
        j["settings"] = st
        tmp = f.with_name(f.name + ".tmp")
        tmp.write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(f)
        return {"ok": True, "id": pid}
    except Exception as e:
        return {"ok": False, "id": pid, "loi": f"Không ghi được cài đặt Antigravity: {str(e)[:120]}"}


def tim_project(kho):
    """projectId cho kho. Cấu hình hoc_canh.project: 'none' (tắt) | <id> | 'auto' (mặc định).
    'auto': dùng Project riêng của Học cảnh (tự tạo, bật Turbo — tắt bằng hoc_canh.tu_duyet=false); lỗi/tắt thì Project có thư mục làm việc là kho hoặc cha của kho."""
    c = str(doc_cau_hinh().get("project") or "auto")
    if c == "none":
        return None
    if c != "auto":
        return c
    if doc_cau_hinh().get("tu_duyet", True):
        if trang_thai_quyen(kho)["ok"] or thiet_lap_quyen(kho)["ok"]:
            return id_project_hoc_canh(kho)
    k = _chuan_kho(kho)
    tot = None
    for ws, pid in danh_sach_project().items():
        if (k == ws or k.startswith(ws.rstrip(os.sep) + os.sep)) and (tot is None or len(ws) > len(tot[0])):
            tot = (ws, pid)
    return tot[1] if tot else None


# ----------------------------------------------------------------------------------------------- lời nhắc (cả lô)
def ctx_loi_nhac(viec):
    """Dữ liệu điền vào mẫu prompt/hoc-canh.md. viec: [{rel, dai, src (tuyệt đối), ra (tuyệt đối), ghi_chu?}]."""
    md = prompt_mau.doc("mo-ta-gemini")[0]
    a = md.find("Bối cảnh:"); b = md.find("Làm lần lượt"); q = md.find("Quy tắc:")
    boi_canh = md[a:b].strip() if a >= 0 and b > a else ""
    quy_tac = md[q:].strip() if q >= 0 else md
    ds = []
    for i, v in enumerate(viec, 1):
        s = (f"{i}. Video: '{v['src']}' — dài {v['dai']:.2f} giây → thoi_luong_s = {v['dai']:.2f}, mọi tu_s/den_s nằm trong 0–{v['dai']:.2f}; "
             f"trường \"video\" = \"{v['rel']}\"; GHI JSON vào file: '{v['ra']}'")
        if v.get("ghi_chu"):
            s += f" (lần trước chưa đạt: {v['ghi_chu']} — làm lại cho đúng, ghi đè file)"
        ds.append(s)
    return {"so_video": len(viec), "boi_canh": boi_canh, "ds_video": "\n".join(ds), "quy_tac": quy_tac}


def loi_nhac_lo(viec):
    """Lời nhắc gửi Antigravity cho cả lô (mẫu prompt/hoc-canh.md — hướng dẫn nêu 1 lần, rồi danh sách video + file đầu ra từng video)."""
    return prompt_mau.dien("hoc-canh", **ctx_loi_nhac(viec))


# ----------------------------------------------------------------------------------------------- 1 cuộc trò chuyện = 1 lô: gửi + chờ từng file (có thể thay bằng giả khi thử)
def chay_lo(model, prompt, outs, tieu_de, khi_co, han=None, gui=gui_hoi, ngu=None, project=None, han_moi_video=HAN_MOI_VIDEO_S,
            huy=None, huy_cuoc=None, xoa_cuoc=None):
    """Gửi 1 lần cho Antigravity rồi chờ MỖI file trong `outs` xuất hiện và ổn định (kích thước không đổi 2 lần kiểm liền).
    Mỗi file xong thì gọi khi_co(path, nội dung chữ) ngay. Quá hạn (= han_moi_video × số video, tối đa HAN_LO_TOI_DA_S) thì thôi.
    Anh bấm Dừng (`huy` được đặt) → huỷ ngay cuộc trò chuyện ở Antigravity, xoá file đầu ra dở dang, trả về phần đã xong. Quá hạn cũng huỷ.
    → danh sách path đã nhận được."""
    run = _run_hien()
    huy = huy or run["huy"]
    xoa_cuoc = xoa_cuoc or (xoa_cuoc_tro_chuyen if (huy_cuoc is None and gui is gui_hoi) else None)     # thử với gui/huy giả thì không xoá chat thật
    huy_cuoc = huy_cuoc or huy_cuoc_tro_chuyen
    ngu = ngu or (lambda giay: huy.wait(giay))
    outs = [Path(o) for o in outs]
    han = han or min(HAN_LO_TOI_DA_S, han_moi_video * len(outs))

    def don():
        for o in outs:
            for f in (o, o.with_name(o.name + ".tmp")):
                try:
                    f.unlink()
                except OSError:
                    pass
    don()
    outs[0].parent.mkdir(parents=True, exist_ok=True)
    if huy.is_set():
        return []
    cid = gui(model, prompt, tieu_de, project) if project else gui(model, prompt, tieu_de)
    if cid:
        with _RUN_LOCK:
            run["conv"].add(cid)
        _luu()
    cu = {o: -1 for o in outs}; on = {o: 0 for o in outs}; xong = []
    t = 0
    try:
        while t <= han and len(xong) < len(outs) and not huy.is_set():
            ngu(CHU_KY_S); t += CHU_KY_S
            TT.nhip(giay=int(t))                              # việc trực tiếp (nếu luồng này có): vẫn "đang chờ Antigravity" + số giây đã chờ thật
            if huy.is_set():
                break
            for o in outs:
                if o in xong:
                    continue
                try:
                    n = o.stat().st_size
                except OSError:
                    n = -1
                if n > 0:
                    on[o] = on[o] + 1 if n == cu[o] else 0
                    if on[o] >= 2:
                        if huy.is_set():
                            break
                        xong.append(o)
                        khi_co(o, o.read_text(encoding="utf-8", errors="replace"))
                else:
                    on[o] = 0
                cu[o] = n
    finally:
        if len(xong) < len(outs):                            # dừng / quá hạn: Antigravity còn đang làm thì huỷ, rồi dọn file dở
            if cid:
                huy_cuoc(cid)
            don()
        elif cid:                                            # nhận đủ phiếu rồi: bảo Antigravity dừng cuộc trò chuyện này để không còn gì chạy ngầm
            try:
                huy_cuoc(cid)
            except Exception:
                pass
        if cid:
            if xoa_cuoc:                                     # xong việc (đủ hay thiếu): xoá chat để Antigravity không chất đống
                try:
                    xoa_cuoc(cid)
                except Exception:
                    pass
            with _RUN_LOCK:
                run["conv"].discard(cid)
            _luu()
        if xoa_cuoc is xoa_cuoc_tro_chuyen:                  # việc thật: dọn bù chat cũ của app còn sót (nền, tối đa 10 phút/lần)
            don_chat_sot_nen()
    return xong


def hoi_mot_lan(model, prompt, out_file, han=120, project=None, gui=gui_hoi, huy_cuoc=None, ngu=None, huy=None, tieu_de="Giám khảo", xoa_cuoc=None):
    """Hỏi Antigravity MỘT câu rồi chờ 1 file kết quả (JSON do AI ghi ra `out_file`) — dùng cho tiến trình KHÔNG thuộc việc học nào (vd. lô sản xuất
    chấm video). KHÔNG đụng job/run của Học cảnh và KHÔNG ghi hoc-canh-job.json (file đó của tiến trình hub). Chờ file có chữ và ổn định 2 lần kiểm
    liền (kích thước không đổi). Luôn huỷ rồi XOÁ cuộc trò chuyện sau khi xong/lỗi/quá hạn (xoa_cuoc_tro_chuyen) và xoá file kết quả. → nội dung chữ của file.
    Lỗi: ChuaMo (Antigravity chưa mở), LoiTam (không nhận việc / quá hạn `han` giây), Huy (`huy` được đặt)."""
    huy = huy or threading.Event()
    xoa_cuoc = xoa_cuoc or (xoa_cuoc_tro_chuyen if (huy_cuoc is None and gui is gui_hoi) else None)
    huy_cuoc = huy_cuoc or huy_cuoc_tro_chuyen
    ngu = ngu or (lambda giay: huy.wait(giay))
    out = Path(out_file)
    tam = out.with_name(out.name + ".tmp")

    def don():
        for f in (out, tam):
            try:
                f.unlink()
            except OSError:
                pass
    don()
    out.parent.mkdir(parents=True, exist_ok=True)
    if huy.is_set():
        raise Huy()
    cid = None
    try:
        cid = gui(chuan_model(model), prompt, tieu_de, project) if project else gui(chuan_model(model), prompt, tieu_de)
        cu, on, t = -1, 0, 0.0
        TT.cap_hien_tai(buoc="Antigravity đang xem và chấm")
        while t <= han:
            ngu(CHU_KY_S); t += CHU_KY_S
            TT.nhip(giay=int(t))                              # việc trực tiếp của giám khảo (ekip mở sẵn): số giây đã chờ Antigravity
            if huy.is_set():
                raise Huy()
            try:
                n = out.stat().st_size
            except OSError:
                n = -1
            if n > 0:
                on = on + 1 if n == cu else 0
                if on >= 2:
                    return out.read_text(encoding="utf-8", errors="replace")
            else:
                on = 0
            cu = n
        raise LoiTam(f"Antigravity không trả kết quả trong {han} giây.")
    finally:
        if cid:
            try:
                huy_cuoc(cid)
            except Exception:
                pass
            if xoa_cuoc:                                     # chấm xong / lỗi / quá hạn: xoá hẳn chat, lỗi xoá không làm hỏng việc chấm
                try:
                    xoa_cuoc(cid)
                except Exception:
                    pass
        if xoa_cuoc is xoa_cuoc_tro_chuyen:                  # việc thật: dọn bù chat cũ của app còn sót (nền, tối đa 10 phút/lần)
            don_chat_sot_nen()
        don()


# ----------------------------------------------------------------------------------------------- lời nhắc điền phiếu (cả lô)
def ctx_dien_phieu(viec, to, ra, ten_sp=""):
    """Dữ liệu điền vào mẫu prompt/dien-phieu.md. viec: [{rel, src (tuyệt đối), dai, canh: [{so, tu, den}]}]; to: các file tờ ảnh; ra: file kết quả."""
    ds, n = [], 0
    for i, v in enumerate(viec, 1):
        ds.append(f"VIDEO {i}: {v['src']}")
        for c in v["canh"]:
            sai = f" (lần trước sai: {c['sai']} — sửa đúng chỗ này)" if c.get("sai") else ""
            ds.append(f"   cảnh {c['so']}: từ giây {c['tu']} đến giây {c['den']}{sai}")
        n += len(v["canh"])
    return {"so_video": len(viec), "so_canh": n, "ds_video": "\n".join(ds), "ds_to": "\n".join(f"- {t}" for t in to), "ra": str(ra),
            "ten_sp": ten_sp or "sản phẩm của chủ hàng"}


def loi_nhac_phieu(viec, to, ra, ten_sp=""):
    return prompt_mau.dien("dien-phieu", **ctx_dien_phieu(viec, to, ra, ten_sp))


# ----------------------------------------------------------------------------------------------- tiến độ + trạng thái lưu bền
def _job_rong():
    return {"dang_chay": False, "ma": None, "tong": 0, "xong": 0, "hien_tai": "", "loi": [], "trang_thai": "nghi", "thong_bao": "",
            "bat_dau": None, "dung": False, "dang_dung": False, "canh_bao": "", "giai_doan": "", "model": "", "canh_tong": 0, "canh_xong": 0, "cho": 0}


_JOB_RONG = _job_rong()          # job khi chưa có sản phẩm nào học
_LOCK = threading.Lock()         # bảo vệ kiểm tra "sản phẩm này đang học chưa" + tạo job/run
_LUU_LOCK = threading.Lock()
FILE_JOB = "hoc-canh-job.json"
MSG_KHOI_PHUC = "Xưởng vừa khởi động lại giữa lúc học — sẽ tự học tiếp khi Antigravity sẵn sàng (video đã học được giữ)."
MSG_KHOI_PHUC_TAY = "Xưởng vừa khởi động lại giữa lúc học — chưa tự học tiếp được ({ly_do}). Bấm Học cảnh để làm tiếp (video đã học được giữ)."
TIEP_CHO_S = 15                  # bật lại hub: chờ chừng này giây cho app ổn định rồi mới tự học tiếp
TIEP_HAN_S = 30 * 60             # chờ Antigravity mở tối đa chừng này; quá thì thôi, để anh bấm tay
CAN_TIEP = []                    # [(mã sản phẩm, {"lai", "chi"})] khoi_phuc() tìm thấy đang học dở → tu_hoc_tiep_nen() học tiếp
TOI_DA_SP_MAC_DINH = 3           # số sản phẩm học cùng lúc tối đa (hoc_canh.toi_da_sp); dư thì xếp hàng
_SLOT = threading.Condition()
_HANG = []                       # khoá các sản phẩm đang chờ lượt (FIFO)
_DANG = set()                    # khoá các sản phẩm đang giữ 1 lượt chạy


def _khoa(ma):
    return str(ma)


def _job_hien():
    """Job của luồng hiện tại (luồng học); không thì job của việc bắt đầu gần nhất; chưa có thì job rỗng."""
    r = _CUR.get()
    if r is not None and r.get("job") is not None:
        return r["job"]
    return _JOBS.get(_ULTIMA[0]) or _JOB_RONG


def job(ma=None):
    """Job (dict sống) của sản phẩm `ma`; ma=None → việc bắt đầu gần nhất. Chưa có → job rỗng (không đăng ký)."""
    if ma is None:
        return _job_hien()
    return _JOBS.get(_khoa(ma)) or _job_rong()


class _VaoJob(collections.abc.MutableMapping):
    """JOB dạng cũ (dict): trỏ vào job hiện tại (xem _job_hien). Việc mới nên dùng job(ma) / tat_ca_job()."""
    def __getitem__(self, k): return _job_hien()[k]
    def __setitem__(self, k, v): _job_hien()[k] = v
    def __delitem__(self, k): del _job_hien()[k]
    def __iter__(self): return iter(list(_job_hien()))
    def __len__(self): return len(_job_hien())


JOB = _VaoJob()


def tat_ca_job():
    """{khoá sản phẩm: bản sao job} của mọi sản phẩm đã học/đang học từ lúc hub chạy."""
    with _RUN_LOCK:
        return {k: dict(j, loi=list(j.get("loi") or [])) for k, j in _JOBS.items()}


def dang_hoc():
    """Khoá các sản phẩm đang học hoặc đang chờ lượt."""
    with _RUN_LOCK:
        return [k for k, j in _JOBS.items() if j.get("dang_chay")]


def _luu():
    """Ghi lich-su/hoc-canh-job.json (nguyên tử, dưới khoá vì nhiều luồng ghi): {"jobs": {khoá sản phẩm: {job, conv: mã các cuộc trò chuyện Antigravity đang mở, kho}}}
    — để khởi động lại hub vẫn huỷ được việc dở của MỌI sản phẩm. Không bao giờ ném lỗi."""
    try:
        with _LUU_LOCK:
            with _RUN_LOCK:
                jobs = {}
                for k, j in _JOBS.items():
                    r = _RUNS.get(k) or {}
                    jobs[k] = {"job": dict(j, loi=list(j.get("loi") or [])), "conv": sorted(r.get("conv") or ()), "kho": str(r.get("kho") or ""),
                               "tiep": r.get("tiep")}
            f = LS / FILE_JOB
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.with_name(f.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps({"jobs": jobs, "luc": time.time()}, ensure_ascii=False), encoding="utf-8")
            tmp.replace(f)
    except Exception:
        pass


def cap_nhat(**kw):
    """Cập nhật job hiện tại + lưu bền."""
    _job_hien().update(**kw)
    _luu()


def khoi_phuc():
    """Gọi 1 lần lúc hub khởi động. File trạng thái còn ghi sản phẩm nào "đang học" mà tiến trình này không học gì = hub vừa bị tắt giữa chừng → với MỖI sản phẩm dở:
    huỷ các cuộc trò chuyện Antigravity còn mở, dọn <kho>/_tam/hoc-canh, đặt job về "dung" kèm lời nhắn. → tổng số cuộc trò chuyện đã huỷ, hoặc None nếu không có gì để dọn."""
    with _RUN_LOCK:
        if any(j.get("dang_chay") for j in list(_JOBS.values()) + [_JOB_RONG]):
            return None
    try:
        d = json.loads((LS / FILE_JOB).read_text(encoding="utf-8"))
    except Exception:
        return None
    muc = d.get("jobs") if isinstance(d, dict) and isinstance(d.get("jobs"), dict) else {"": d} if isinstance(d, dict) else {}      # dạng cũ: 1 job
    tong, co = 0, False
    for k, e in muc.items():
        jb = (e or {}).get("job") if isinstance(e, dict) else None
        if not isinstance(jb, dict) or not (jb.get("dang_chay") or jb.get("trang_thai") == "dang_chay"):
            continue
        co = True
        conv = [str(c) for c in (e.get("conv") or []) if c]
        for c in conv:
            huy_cuoc_tro_chuyen(c)
        tong += len(conv)
        if e.get("kho"):
            shutil.rmtree(Path(e["kho"]) / "_tam" / "hoc-canh", ignore_errors=True)
        khoa = _khoa(jb.get("ma") or k or e.get("kho") or "")
        nj = dict(_job_rong(), **jb)
        nj.update(dang_chay=False, dung=True, dang_dung=False, trang_thai="dung", thong_bao=MSG_KHOI_PHUC, hien_tai="", giai_doan="", cho=0)
        with _RUN_LOCK:
            _JOBS[khoa] = nj; _ULTIMA[0] = khoa
        tiep = e.get("tiep") if isinstance(e.get("tiep"), dict) else {}
        if jb.get("ma") or k:
            CAN_TIEP.append((str(jb.get("ma") or k), {"lai": bool(tiep.get("lai")), "chi": tiep.get("chi") or None}))
    if not co:
        return None
    _luu()
    return tong


def tu_hoc_tiep(bat_dau, ngu=time.sleep, kiem_mo=None, cho_s=None, han_s=None):
    """Học tiếp các sản phẩm khoi_phuc() thấy đang học dở (hub bị tắt giữa chừng: cập nhật app, tắt máy…). Video đã học được giữ nên chỉ làm phần còn lại.
    Chờ Antigravity mở (tối đa han_s); sản phẩm anh đã tự bấm học/dừng trong lúc chờ thì thôi không đụng. bat_dau(ma, lai, chi) → {"ok", "loi", "can"}.
    Tắt bằng hoc_canh.tu_hoc_tiep = false trong config. → [mã đã học tiếp]."""
    if doc_cau_hinh().get("tu_hoc_tiep") is False:
        for ma, _ in CAN_TIEP:
            job(ma).update(thong_bao=MSG_KHOI_PHUC_TAY.format(ly_do="đang tắt tự học tiếp"))
        CAN_TIEP.clear(); _luu()
        return []
    kiem_mo = kiem_mo or (lambda: trang_thai_agy()["mo"])
    cho_s = TIEP_CHO_S if cho_s is None else cho_s
    han_s = TIEP_HAN_S if han_s is None else han_s
    ngu(cho_s)
    con = list(CAN_TIEP); CAN_TIEP.clear(); da = []; t = 0
    while con:
        if kiem_mo():
            sau, moi = [], []
            for ma, tiep in con:
                j = job(ma)
                if j.get("dang_chay") or j.get("thong_bao") != MSG_KHOI_PHUC:      # anh đã tự bấm học / việc khác đã ghi đè → để yên
                    continue
                kq = bat_dau(ma, tiep.get("lai"), tiep.get("chi")) or {}
                if kq.get("ok"):
                    da.append(ma); moi.append(ma); print(f"Học cảnh: tự học tiếp {ma} sau khi Xưởng khởi động lại.")
                elif kq.get("can") == "mo":
                    sau.append((ma, tiep))
                else:
                    job(ma).update(thong_bao=MSG_KHOI_PHUC_TAY.format(ly_do=str(kq.get("loi") or "lỗi lạ")[:120])); _luu()
            con = sau
            if moi:
                ngu(3)
                for ma in moi:                                                     # luồng học chết ngay (vd. hồ sơ sản phẩm hỏng) → đừng để câu "sẽ tự học tiếp" treo mãi
                    j = job(ma)
                    if not j.get("dang_chay") and j.get("thong_bao") == MSG_KHOI_PHUC:
                        j.update(thong_bao=MSG_KHOI_PHUC_TAY.format(ly_do="không bắt đầu được")); _luu()
            if not con:
                break
        if t >= han_s:
            for ma, _ in con:
                if job(ma).get("thong_bao") == MSG_KHOI_PHUC:
                    job(ma).update(thong_bao=MSG_KHOI_PHUC_TAY.format(ly_do="Antigravity chưa mở"))
            _luu()
            break
        ngu(10); t += 10
    return da


def tu_hoc_tiep_nen(bat_dau):
    """Chạy tu_hoc_tiep ở luồng nền (lúc hub khởi động). Không có gì dở thì thôi."""
    if not CAN_TIEP:
        return False
    def chay():
        try:
            tu_hoc_tiep(bat_dau)
        except Exception as e:
            print("Tự học tiếp học cảnh bị lỗi:", e)
    threading.Thread(target=chay, daemon=True, name="hoc-canh-tiep").start()
    return True


def doc_cau_hinh():
    try:
        return cfg_hub().get("hoc_canh", {})
    except Exception:
        return {}


def doc_toi_da_sp():
    """Số sản phẩm học cùng lúc tối đa (hoc_canh.toi_da_sp, 1–10, mặc định 3)."""
    try:
        return max(1, min(10, int(doc_cau_hinh().get("toi_da_sp") or TOI_DA_SP_MAC_DINH)))
    except Exception:
        return TOI_DA_SP_MAC_DINH


def _cho_luot(khoa, run):
    """Xếp hàng FIFO lấy 1 lượt chạy (tối đa hoc_canh.toi_da_sp sản phẩm cùng lúc). → True khi tới lượt, False nếu bấm Dừng lúc đang chờ."""
    huy, jb = run["huy"], run["job"]
    with _SLOT:
        _HANG.append(khoa)
        try:
            while True:
                if huy.is_set():
                    return False
                if _HANG[0] == khoa and len(_DANG) < doc_toi_da_sp():
                    _HANG.pop(0); _DANG.add(khoa); jb.update(cho=0)
                    _SLOT.notify_all()
                    return True
                vt = _HANG.index(khoa) + 1
                jb.update(cho=vt, thong_bao=f"Đang chờ tới lượt (xếp thứ {vt}) — đang có {len(_DANG)} sản phẩm học…")
                _SLOT.wait(0.5)
        finally:
            if khoa in _HANG:
                _HANG.remove(khoa)
                _SLOT.notify_all()


def _nha_luot(khoa):
    with _SLOT:
        _DANG.discard(khoa)
        _SLOT.notify_all()


def chuan_model(m):
    """Giá trị lạ/cũ (flash, pro, flash_lite, gemini-… đã bỏ) → model mặc định."""
    return m if m in MODELS else MODEL_MAC_DINH


def doc_model():
    return chuan_model(str(doc_cau_hinh().get("model") or ""))


def doc_song_song():
    try:
        return max(1, min(4, int(doc_cau_hinh().get("song_song") or SONG_SONG_MAC_DINH)))
    except Exception:
        return SONG_SONG_MAC_DINH


def co_lo(so_viec=0):
    """Số video tối đa mỗi cuộc trò chuyện: hoc_canh.lo nếu đặt (1–5); không thì 5."""
    try:
        v = int(doc_cau_hinh().get("lo") or 0)
    except Exception:
        v = 0
    return max(1, min(SO_VIDEO_LO, v)) if v else SO_VIDEO_LO


def ten_san_pham(ma):
    try:
        d = json.loads((HUB / "san-pham" / str(ma) / "san-pham.json").read_text(encoding="utf-8"))
        return str(d.get("ten_ngan") or d.get("ten_goi") or ma)[:40]
    except Exception:
        return str(ma)[:40]


def ten_sp_cho_phieu(ma):
    """Tên sản phẩm của chủ hàng để AI biết thế nào là "hàng khác" (hang_khac)."""
    try:
        d = json.loads((HUB / "san-pham" / str(ma) / "san-pham.json").read_text(encoding="utf-8"))
        ten = [str(d.get("ten_goi") or "").strip()] + [str(x).strip() for x in d.get("nhan_cung_san_pham", [])]
        ten = [t for t in ten if t]
        if ten:
            return "; ".join(dict.fromkeys(ten))
    except Exception:
        pass
    return "sản phẩm của chủ hàng"


def _ghi_ket_qua(kho, rel, file_cu, obj):
    md = kho / "_mo-ta" / Path(rel).parent / (Path(rel).name + ".mo-ta.json")
    md.parent.mkdir(parents=True, exist_ok=True)
    goc = None
    if file_cu and (kho / "_mo-ta" / file_cu).exists():
        md = kho / "_mo-ta" / file_cu
        goc = md.read_bytes()
    if goc is None and md.exists():                      # file hỏng cùng tên → giữ bản gốc trước khi thay
        goc = md.read_bytes()
    km.ghi_mo_ta(md, obj, goc)


def sao_luu_cu(kho, file_cu):
    """Chép mô tả kiểu cũ sang _mo-ta/_cu/<cùng đường dẫn> TRƯỚC khi học lại đè lên. Chỉ chép 1 lần (không đè bản sao đã có). → True nếu có chép."""
    if not file_cu:
        return False
    src = kho / "_mo-ta" / file_cu
    dst = kho / "_mo-ta" / "_cu" / file_cu
    if not src.exists() or dst.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def doc_mo_ta_kho(kho):
    """{video (đường dẫn tương đối): (kieu, file mô tả tương đối _mo-ta, nội dung)} — kieu 2 = đã học bằng phiếu, 1 = mô tả kiểu cũ. Video chưa có mô tả không có mặt.
    Một video có nhiều file mô tả: kiểu 2 thắng. Chỉ đọc."""
    kq = {}
    videos = km.liet_ke_video(kho)
    for mt in km.liet_ke_mo_ta(kho):
        try:
            d = json.loads(km._doc_byte(mt)[0].decode("utf-8-sig", errors="replace"))
        except Exception:
            try:
                d = km.doc_json_long(km._doc_byte(mt)[0])[0]
            except Exception:
                continue
        try:
            d = km._boc_goi(d, [])
        except Exception:
            pass
        rel, _ = km._video_cua_file(kho, mt, d, videos)
        if rel is None:
            continue
        k = 2 if isinstance(d, dict) and d.get("kieu") == 2 else 1
        f = mt.relative_to(kho / "_mo-ta").as_posix()
        if rel not in kq or (k == 2 and kq[rel][0] != 2):
            kq[rel] = (k, f, d if isinstance(d, dict) else {})
    return kq


def kieu_kho(kho):
    """{video: (kieu, file mô tả)} — như doc_mo_ta_kho nhưng không kèm nội dung."""
    return {r: (k, f) for r, (k, f, _d) in doc_mo_ta_kho(kho).items()}


def ket_qua_kho(kho):
    """Kết quả học của cả kho để giao diện xem (chỉ đọc): từng video {video, kieu 0|1|2, hoc_luc, model, tom_tat, loi_hay, canh[…]}, tổng số, và số cảnh theo loại
    (đủ 12 loại, loại chưa có = 0 → biết kho còn thiếu kiểu cảnh nào)."""
    mo = doc_mo_ta_kho(kho)
    ra, theo_loai = [], {l: 0 for l in phieu.LOAI}
    tong = {"video_tong": 0, "kieu2": 0, "kieu1": 0, "chua_hoc": 0, "canh_tong": 0}
    for rel in sorted(km.liet_ke_video(kho)):
        tong["video_tong"] += 1
        k, _f, d = mo.get(rel, (0, None, {}))
        v = {"video": rel, "kieu": k, "hoc_luc": d.get("hoc_luc"), "model": d.get("model"), "tom_tat": d.get("tom_tat") or "",
             "loi_hay": list(d.get("loi_hay") or []), "canh": []}
        for c in (d.get("canh_quay") or []) if isinstance(d.get("canh_quay"), list) else []:
            if not isinstance(c, dict):
                continue
            p = c.get("phieu") if isinstance(c.get("phieu"), dict) else {}
            loai = p.get("loai") if k == 2 else None
            v["canh"].append({"tu": c.get("tu_s"), "den": c.get("den_s"), "loai": loai, "co_canh": c.get("co_canh"), "ta": c.get("hinh") or "",
                              "noi": p.get("dang_noi_ve") or "", "loi": p.get("loi") or "", "dep": c.get("diem"), "mat": p.get("mat"),
                              "chu_chen": p.get("chu_chen"), "hang_khac": p.get("hang_khac")})
            if loai in theo_loai:
                theo_loai[loai] += 1
        tong["kieu2" if k == 2 else "kieu1" if k == 1 else "chua_hoc"] += 1
        tong["canh_tong"] += len(v["canh"])
        ra.append(v)
    return {"video": ra, "tong": tong, "theo_loai": theo_loai}



def chia_lo(muc, toi_da_video=None):
    """muc: [(video, [chỉ số cảnh])] → các lô: mỗi lô ≤ SO_CANH_LO cảnh và ≤ toi_da_video video (giữ thứ tự)."""
    tv = toi_da_video or SO_VIDEO_LO
    cac, hien, n = [], [], 0
    for v, idxs in muc:
        if hien and (len(hien) >= tv or n + len(idxs) > SO_CANH_LO):
            cac.append(hien); hien, n = [], 0
        hien.append((v, idxs)); n += len(idxs)
    if hien:
        cac.append(hien)
    return cac


def _rai_deu(canh, toi_da):
    """Chọn `toi_da` cảnh rải đều (giữ thứ tự) khi video cắt ra quá nhiều."""
    if len(canh) <= toi_da:
        return list(canh)
    return [canh[round(i * (len(canh) - 1) / (toi_da - 1))] for i in range(toi_da)]


# ----------------------------------------------------------------------------------------------- vòng học
def hoc_kho(ma_hoac_kho, model=None, runner=chay_lo, do_dai=km.do_dai_video, khi_xong=None, song_song=None, kiem_mo=None, project=False, ten=None,
            ban_san_xuat=None, lai=False, cat=None, to_anh=None, chi=None):
    """Học mọi video chưa có mô tả/hỏng của kho (lai=True: cả video còn mô tả kiểu cũ → học lại theo kiểu mới). Chạy đồng bộ (gọi trong luồng nền).
    1) MÁY cắt cảnh từng video (cat_canh.cat); 2) gộp thành lô ≤ 24 cảnh/≤ 5 video, mỗi lô 1 cuộc trò chuyện Antigravity điền phiếu; 3) kiểm phiếu chặt, cảnh sai
    được hỏi lại 1 lần trong lô riêng; 4) ghi _mo-ta/<video>.mo-ta.json kiểu 2. Video xong thì giữ nguyên dù việc bị dừng giữa chừng.
    khi_xong(ket_qua) chạy khi học xong TRỌN VẸN. project=False: không đặt Project (thử máy giả); None/True: tự tìm Project theo kho.
    chi=[đường dẫn video tương đối]: chỉ học lại ĐÚNG các video này (dù đang kiểu nào; kiểu cũ được sao lưu như lai), bỏ qua phần còn lại của kho.
    ban_san_xuat(): True khi hub đang làm video → chỉ chạy 1 lô một lúc (nhường máy). cat/to_anh: thay thế khi thử (mặc định cat_canh.cat / cat_canh.to_anh)."""
    kho = km._kho_cua(ma_hoac_kho) if not Path(str(ma_hoac_kho)).is_absolute() else Path(ma_hoac_kho)
    ma = None if Path(str(ma_hoac_kho)).is_absolute() else str(ma_hoac_kho)
    model = chuan_model(model or doc_model())
    song_song = song_song or doc_song_song()
    kiem_mo = kiem_mo or (lambda: trang_thai_agy()["mo"])
    ten = ten or ten_san_pham(ma_hoac_kho)
    ban_san_xuat = ban_san_xuat or (lambda: False)
    cat = cat or cat_canh.cat
    to_anh = to_anh or cat_canh.to_anh
    khoa = _khoa(ma_hoac_kho)
    with _LOCK:
        if (_JOBS.get(khoa) or {}).get("dang_chay"):
            return {"ok": False, "loi": "Đang học rồi."}
        job = dict(_job_rong(), ma=khoa, dang_chay=True, trang_thai="dang_chay", thong_bao="Đang kiểm kho…", bat_dau=time.time(), giai_doan="cat", model=model)
        run = _run_moi(khoa, kho, job); huy = run["huy"]
        run["tiep"] = {"lai": bool(lai), "chi": [str(x) for x in chi] if chi else None} if ma else None     # hub tắt giữa chừng → bật lại tự học tiếp đúng kiểu này
        with _RUN_LOCK:
            _RUNS[khoa] = run; _JOBS[khoa] = job; _ULTIMA[0] = khoa
    tok = _CUR.set(run)                                   # luồng này (và các luồng con được sao ngữ cảnh) thuộc việc học của sản phẩm này
    _luu()

    def cap(**kw):
        job.update(**kw); _luu()
    kq = {"ok": True, "da_hoc": 0, "loi": [], "tat_ca_xong": False, "chi_tiet": [], "lo": 0, "project": None, "canh": 0, "model": model}
    st = {"qua_han_lien": 0, "dung_vi": None, "lo_dang": 0, "kieu1_ghi": 0}
    kl = threading.Lock()
    dang = {}                     # tên video đang xem → số lô
    cac_video = []

    def xong_video(v_hoac_rel, ok, giay, loi=None, canh=0):
        rel = v_hoac_rel["rel"] if isinstance(v_hoac_rel, dict) else v_hoac_rel
        with kl:
            if isinstance(v_hoac_rel, dict):
                v_hoac_rel["xong"] = True
            job["xong"] += 1
            kq["chi_tiet"].append({"video": rel, "ok": ok, "giay": giay, "canh": canh})
            if ok:
                kq["da_hoc"] += 1; kq["canh"] += canh; job["canh_xong"] += canh
            if loi:
                job["loi"].append({"video": rel, "loi": str(loi)[:240]}); kq["loi"].append(rel)
        _luu()

    def ghi_video(v):
        """Ghi mô tả kiểu 2 từ các cảnh đã có phiếu hợp lệ. → số cảnh đã ghi."""
        dd = sorted(v["kq"])
        obj = phieu.mo_ta_tu_phieu(v["rel"], v["dai"], [v["canh"][i] for i in dd], [v["kq"][i] for i in dd], v.get("info") or {}, model)
        obj, _g, _cb = km.chuan_hoa_noi_dung(obj, v["dai"], v["rel"], la_obj=True)
        if v.get("kieu_cu") == 1:
            sao_luu_cu(kho, v.get("file_cu"))
        _ghi_ket_qua(kho, v["rel"], v.get("file_cu"), obj)
        if v.get("kieu_cu") == 1:
            with kl:
                st["kieu1_ghi"] += 1
        return len(dd)

    def ket_thuc_video(v, cuoi):
        """Video đủ phiếu → ghi + xong. cuoi=True (đã hỏi lại rồi): thiếu cảnh vẫn ghi phần đã có và báo lỗi các cảnh còn lại."""
        if v.get("xong"):
            return
        giay = round(time.time() - v["t0"])
        thieu = [i for i in range(len(v["canh"])) if i not in v["kq"]]
        if not thieu:
            try:
                xong_video(v, True, giay, canh=ghi_video(v))
            except Exception as e:
                xong_video(v, False, giay, f"Không ghi được mô tả: {type(e).__name__} {str(e)[:150]}")
            return
        if not cuoi:
            return
        ly = next((v["loi_canh"][i] for i in thieu if i in v["loi_canh"]), "Antigravity không ghi phiếu cho video này")
        if v["kq"]:
            try:
                n = ghi_video(v)
                xong_video(v, True, giay, f"Mới học {n}/{len(v['canh'])} cảnh (cảnh thứ {', '.join(str(i + 1) for i in thieu)} lỗi: {ly})", canh=n)
            except Exception as e:
                xong_video(v, False, giay, f"Không ghi được mô tả: {type(e).__name__} {str(e)[:150]}")
        else:
            xong_video(v, False, giay, ly + " — bấm Học cảnh để thử lại.")

    def chay_mot_lo(lo, so, tong_lo, pj, lan):
        """lo: [(video, [chỉ số cảnh cần điền])]. Gửi 1 cuộc trò chuyện, kiểm phiếu, ghi các video đủ cảnh. Cảnh sai ghi lý do để hỏi lại (lan 1)."""
        while True:                                     # đang làm video thì chỉ chạy 1 lô một lúc (nhường máy)
            with kl:
                if huy.is_set() or st["dung_vi"]:
                    return
                if not (st["lo_dang"] >= 1 and ban_san_xuat()):
                    st["lo_dang"] += 1
                    for v, _ in lo:
                        dang[Path(v["rel"]).name] = so
                    job.update(hien_tai=", ".join(dang))
                    break
            huy.wait(2)
        try:
            if not kiem_mo():
                raise ChuaMo(_msg_chua_mo())
            id_lo = f"{so:02d}{'' if lan == 1 else 'b'}-" + hashlib.sha1("|".join(v["rel"] for v, _ in lo).encode("utf-8")).hexdigest()[:6]
            thu_muc = kho / "_tam" / "hoc-canh" / id_lo
            thu_muc.mkdir(parents=True, exist_ok=True)
            dem, phang, viec, vao_anh = 0, [], [], []
            for v, idxs in lo:                         # đánh số cảnh 1..n trong lô
                cs = []
                for i in idxs:
                    dem += 1; c = v["canh"][i]
                    phang.append((dem, v, i)); cs.append({"so": dem, "tu": c["tu"], "den": c["den"], "sai": str(v["loi_canh"].get(i) or "") if lan > 1 else ""})   # lần 2: kèm lý do lần 1 (khoá theo video + chỉ số cảnh gốc, vì lô đánh số lại)
                    vao_anh.append((dem, str((kho / v["rel"]).resolve()), c["giua"]))
                viec.append({"rel": v["rel"], "src": str((kho / v["rel"]).resolve()), "dai": v["dai"], "canh": cs})
            to = to_anh(vao_anh, str(thu_muc / "to"))
            ra = (thu_muc / "phieu.json").resolve()
            ket = {}

            def khi_co(f, text):
                if not huy.is_set():
                    ket["text"] = text
            tieu_de = f"Xưởng Video · {ten} · lô {so}/{tong_lo}" + ("" if lan == 1 else " (làm lại cảnh lỗi)")
            kw = {"project": pj} if pj else {}
            han = min(HAN_LO_TOI_DA_S, HAN_MOI_VIDEO_S * len(lo) + HAN_THEM_S)
            with TT.viec("hoc-canh", f"Antigravity đang điền phiếu lô {so}/{tong_lo}" + ("" if lan == 1 else " (làm lại cảnh lỗi)"), sp=ten,
                         buoc=f"Lô {so}/{tong_lo}", video=", ".join(Path(v["rel"]).name for v, _ in lo)) as tt_hc:
                tt_hc.cap(chi_tiet={"canh": dem, "video": len(lo), "han_s": int(han)})
                nhan = runner(model, loi_nhac_phieu(viec, to, ra, ten_sp), [ra], tieu_de, khi_co, han=han, **kw)
                if huy.is_set():
                    return
                text = ket.get("text")
                if text is None and nhan and ra.exists():
                    text = ra.read_text(encoding="utf-8", errors="replace")
                ly_chung = None
                if text is None:
                    ly_chung = "Antigravity không ghi phiếu (có thể hết lượt model hoặc video khó đọc)"
                    ok, hong, info = {}, [], {}
                    tt_hc.ket("loi"); tt_hc.cap(viec="Antigravity không ghi phiếu"); tt_hc.them_dong(ly_chung)
                else:
                    ok, hong = phieu.kiem_phieu(text, len(lo), [n for n, _, _ in phang])
                    info = phieu.doc_phieu_video(text, len(lo))
                    tt_hc.cap(viec=f"Đã nhận phiếu lô {so}/{tong_lo}", tien_do=1.0, chi_tiet={"canh_dat": len(ok), "canh_loi": len(phang) - len(ok)})
                    tt_hc.them_dong(f"Phiếu hợp lệ {len(ok)}/{len(phang)} cảnh", *[str(x) for x in list(dict(hong).values())[:2]])
            ly = dict(hong)
            for n, v, i in phang:
                if n in ok:
                    v["kq"][i] = ok[n]; v["loi_canh"].pop(i, None)
                else:
                    v["loi_canh"][i] = ly_chung or ly.get(n, "phiếu thiếu")
            for k, (v, _) in enumerate(lo, 1):
                inf = info.get(k)
                if inf and (not v.get("info") or not v["info"].get("tom_tat")):
                    v["info"] = inf
            with kl:
                st["qua_han_lien"] = st["qua_han_lien"] + 1 if (text is None and lan == 1) else 0
                if st["qua_han_lien"] >= 2:
                    st["dung_vi"] = ("het_luot", "Antigravity không trả lời 2 lô liền (có thể hết lượt model) — đợi một lúc rồi bấm Học cảnh làm tiếp (video đã học được giữ).")
            for v, _ in lo:
                ket_thuc_video(v, lan == 2)
        except Huy:
            pass
        except ChuaMo as e:
            with kl:
                st["dung_vi"] = ("can_mo", str(e))
        except Exception as e:                                          # lỗi 1 lô không được làm sập cả kho
            m = str(e)[:200] if isinstance(e, LoiTam) else f"{type(e).__name__}: {str(e)[:160]}"
            for v, idxs in lo:
                for i in idxs:
                    if i not in v["kq"]:
                        v["loi_canh"][i] = m
                ket_thuc_video(v, lan == 2)
        finally:
            with kl:
                st["lo_dang"] -= 1
                for v, _ in lo:
                    dang.pop(Path(v["rel"]).name, None)
                job.update(hien_tai=", ".join(dang))

    def chay_cac_lo(muc, lan, pj):
        cac = chia_lo(muc, co_lo())
        kq["lo"] += len(cac)
        with ThreadPoolExecutor(max_workers=song_song) as ex:
            fs = [ex.submit(contextvars.copy_context().run, chay_mot_lo, c, i + 1, len(cac), pj, lan) for i, c in enumerate(cac)]
            for f in fs:
                f.result()

    ten_sp = ten_sp_cho_phieu(ma) if ma else "sản phẩm của chủ hàng"
    try:
        if not _cho_luot(khoa, run):                                        # xếp hàng nếu đang có đủ sản phẩm học cùng lúc
            raise Huy()
        cap(thong_bao="Đang kiểm kho…", giai_doan="cat")
        def _td(i, n, ten_f):
            if huy.is_set():
                raise Huy()
        rep = km.kiem_kho(kho, sua=True, do_dai=do_dai, tien_do=_td)         # chuẩn hoá cái đã có + biết video nào thiếu/hỏng
        viec = [(x["video"] if isinstance(x, dict) else x, None, 0) for x in rep["thieu_mo_ta"]]
        viec += [(h["video"], h["file"], 0) for h in rep["hong"] if h.get("video")]
        if chi is not None:                                                  # học lại đúng các video được chọn
            ton = km.liet_ke_video(kho); cu = kieu_kho(kho); hong = {h["video"]: h["file"] for h in rep["hong"] if h.get("video")}
            viec = []
            for r in dict.fromkeys(str(x).replace("\\", "/") for x in chi):
                if r in ton:
                    k, f = cu.get(r) or (0, hong.get(r))
                    viec.append((r, f, 1 if k == 1 else 0))
        elif lai:                                                            # học lại mọi video chưa phải kiểu 2
            co = {r for r, _f, _k in viec}
            viec += [(r, f, 1) for r, (k, f) in sorted(kieu_kho(kho).items()) if k != 2 and r not in co]
        cap(tong=len(viec), thong_bao="Đang cắt cảnh bằng máy…" if viec else "Đang kiểm kho…")
        if viec and not kiem_mo():
            st["dung_vi"] = ("can_mo", _msg_chua_mo())
        elif viec:
            def cat_mot(it):
                if huy.is_set():
                    return it, None
                try:
                    return it, cat(str(kho / it[0]))
                except Exception:
                    return it, {}
            with ThreadPoolExecutor(max_workers=max(1, min(4, os.cpu_count() or 2))) as ex:
                for k, (it, r) in enumerate(ex.map(cat_mot, viec), 1):
                    if huy.is_set():
                        raise Huy()
                    rel, fc, kc = it
                    canh = _rai_deu((r or {}).get("canh") or [], MAX_CANH_VIDEO)
                    if not canh:
                        xong_video(rel, False, 0, "Video quá ngắn hoặc không đọc được")
                        continue
                    cac_video.append({"rel": rel, "file_cu": fc, "kieu_cu": kc, "dai": float((r or {}).get("dai") or 0) or max(c["den"] for c in canh),
                                      "canh": canh, "kq": {}, "loi_canh": {}, "info": None, "t0": time.time(), "xong": False})
                    cap(thong_bao=f"Đang cắt cảnh bằng máy… {k}/{len(viec)} video", canh_tong=sum(len(x["canh"]) for x in cac_video))
            if not cac_video:
                pass
            else:
                cap(giai_doan="hoc", thong_bao=f"Antigravity đang điền phiếu {job['canh_tong']} cảnh của {len(cac_video)} video…")
                pj = tim_project(kho) if project is not False else None
                kq["project"] = pj
                chay_cac_lo([(v, list(range(len(v["canh"])))) for v in cac_video], 1, pj)
                con = [(v, [i for i in range(len(v["canh"])) if i not in v["kq"]]) for v in cac_video if not v["xong"]]
                if con and not st["dung_vi"] and not huy.is_set():
                    cap(thong_bao=f"Hỏi lại {sum(len(i) for _, i in con)} cảnh chưa đạt…")
                    chay_cac_lo(con, 2, pj)
        cap(giai_doan="ghi")
        if lai and ma and st["kieu1_ghi"] and not st["dung_vi"] and not huy.is_set():
            _cat_lich_su_canh(ma)
        con_lai = len(viec) - kq["da_hoc"]
        if st["dung_vi"]:
            cap(trang_thai=st["dung_vi"][0], thong_bao=f"{st['dung_vi'][1]} Đã học {kq['da_hoc']} video (giữ nguyên), còn {con_lai} video chưa học.")
        elif huy.is_set() and job["xong"] < len(viec):
            cap(trang_thai="dung", thong_bao=f"Đã dừng. Đã học {kq['da_hoc']} video (giữ nguyên), còn {con_lai} video chưa học.")
        else:
            kq["tat_ca_xong"] = True
            cap(trang_thai="xong", thong_bao="Kho đã đủ mô tả." if not viec else
                     (f"Học xong {kq['da_hoc']} video ({kq['canh']} cảnh)" if kq["da_hoc"] else "Chưa học được video nào") +
                     (f", {len(kq['loi'])} video có lỗi" if kq["loi"] else "") + ".")
    except Huy:
        cap(trang_thai="dung", thong_bao=f"Đã dừng. Đã học {kq['da_hoc']} video (giữ nguyên), còn {max(0, job['tong'] - kq['da_hoc'])} video chưa học.")
    except Exception as e:
        cap(trang_thai="loi", thong_bao=f"Lỗi: {str(e)[:200]}"); kq.update(ok=False, tat_ca_xong=False)
    finally:
        _nha_luot(khoa)
        with _RUN_LOCK:
            con_cuoc = list(run["conv"]); run["conv"].clear()
        if huy.is_set():
            for c in con_cuoc:                                  # còn cuộc trò chuyện nào chưa huỷ thì huỷ nốt
                huy_cuoc_tro_chuyen(c)
        shutil.rmtree(kho / "_tam" / "hoc-canh", ignore_errors=True)
        cap(dang_chay=False, dang_dung=False, hien_tai="", giai_doan="", cho=0)
        with _RUN_LOCK:
            if _RUNS.get(khoa) is run:
                del _RUNS[khoa]
        _CUR.reset(tok)
    if kq.get("tat_ca_xong") and khi_xong:
        try:
            khi_xong(kq)
        except Exception as e:
            cap(thong_bao=job["thong_bao"] + f" (không tự chuẩn bị kho được: {str(e)[:80]})")
    return kq


def _cat_lich_su_canh(ma):
    """Học lại kiểu mới làm mã cảnh của các video đã học lại đổi (id mới được cấp tiếp, id cũ không bao giờ dùng lại) → cất sổ cảnh đã dùng sang canh-da-dung-<ma>.cu-<ngày>.txt."""
    f = LS / f"canh-da-dung-{ma}.txt"
    try:
        if not f.is_file() or not f.read_text(encoding="utf-8").strip():
            return None
        import datetime
        dst = f.with_name(f"canh-da-dung-{ma}.cu-{datetime.date.today():%Y%m%d}.txt")
        n = 1
        while dst.exists():
            dst = f.with_name(f"canh-da-dung-{ma}.cu-{datetime.date.today():%Y%m%d}-{n}.txt"); n += 1
        f.replace(dst)
        return dst
    except Exception:
        return None


def bat_dau_nen(ma, khi_xong=None, **kw):
    """Bắt đầu học ở luồng nền (mỗi sản phẩm 1 việc; nhiều sản phẩm học cùng lúc được). kw: lai=True → học lại cả video còn mô tả kiểu cũ."""
    khoa = _khoa(ma)
    if (_JOBS.get(khoa) or {}).get("dang_chay"):
        return {"ok": False, "loi": "Đang học rồi."}
    kw.setdefault("project", None)
    t = threading.Thread(target=hoc_kho, args=(ma,), kwargs=dict(khi_xong=khi_xong, **kw), daemon=True)
    t.start()
    for _ in range(50):                                          # chờ luồng nhận việc (để trả lời API thấy ngay "đang chạy")
        if (_JOBS.get(khoa) or {}).get("dang_chay"):
            break
        time.sleep(0.02)
    return {"ok": True}


def dung(ma=None):
    """Dừng THẬT: đặt cờ huỷ (các luồng thôi chờ trong ≤1 giây), huỷ ngay các cuộc trò chuyện Antigravity đang làm, giết tiến trình agentapi
    đang treo. ma=None → dừng TẤT CẢ sản phẩm (hub tắt / tương thích cũ); có ma → chỉ sản phẩm đó. Giao diện hiện 'Đang dừng…' (job.dang_dung)
    tới khi luồng học thoát hẳn (dang_chay=False)."""
    with _RUN_LOCK:
        cac = [(k, r) for k, r in _RUNS.items() if (ma is None or k == _khoa(ma)) and (_JOBS.get(k) or {}).get("dang_chay")]
    if not cac:
        return {"ok": True, "dang_dung": False}
    for k, r in cac:
        r["job"].update(dung=True, dang_dung=True, thong_bao="Đang dừng…")
        r["huy"].set()
        with _RUN_LOCK:
            convs = list(r["conv"])

        def lam(convs=convs):
            for c in convs:
                huy_cuoc_tro_chuyen(c)
        if convs:
            threading.Thread(target=lam, daemon=True, name="hoc-canh-huy").start()
    _luu()
    return {"ok": True, "dang_dung": True, "so": len(cac)}


def dung_het():
    """Dừng mọi sản phẩm đang học (hub tắt)."""
    return dung(None)
