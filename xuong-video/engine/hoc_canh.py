"""HỌC CẢNH TỰ ĐỘNG bằng Google Antigravity (ứng dụng máy tính, đã đăng nhập sẵn) — không dùng khoá API.
Antigravity mở thì nó ghi %USERPROFILE%\\.gemini\\antigravity\\daemon\\hub_<cổng>.json {pid, httpPort, csrfToken…}. Hub gọi
language_server.exe agentapi (new-conversation) với 2 biến môi trường ANTIGRAVITY_LS_ADDRESS / ANTIGRAVITY_CSRF_TOKEN, dặn "tác tử" xem video
ở đường dẫn tuyệt đối rồi GHI JSON ra 1 file tạm; hub chờ file đó (ổn định 2 lần kiểm) → kiem_mo_ta chuẩn hoá/kiểm → ghi đúng chỗ kho_canh.py đọc
(_mo-ta/<thư mục con>/<video>.mo-ta.json). Chạy tối đa `hoc_canh.song_song` video cùng lúc (mặc định 2). Mỗi lần chạy kiểm lại kho nên bấm lại là làm tiếp.
agentapi không cho đọc trạng thái lỗi/hết lượt (metadata chỉ có cấu hình) → quá hạn chờ thì báo lỗi video; 2 video liền quá hạn thì dừng cả lô."""
import ctypes, hashlib, json, os, shutil, subprocess, sys, threading, time, urllib.request, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kiem_mo_ta as km

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
import prompt_mau
LS = HUB / "lich-su"
MODELS = {"flash": "Flash (mặc định)", "pro": "Pro", "flash_lite": "Flash Lite"}
MODEL_MAC_DINH = "flash"
SONG_SONG_MAC_DINH = 2
HAN_MOI_VIDEO_S = 240      # hạn chờ của 1 lô = 4 phút × số video
HAN_LO_TOI_DA_S = 2400     # tối đa 40 phút/lô
CHU_KY_S = 3


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


# Mỗi lần học có 1 sự kiện "huy" + danh sách cuộc trò chuyện Antigravity đã mở (để Dừng thật sự huỷ được việc đang chạy ở Antigravity).
_RUN = {"huy": threading.Event(), "conv": set(), "proc": set()}
_RUN_LOCK = threading.Lock()
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
def _song(pid):
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, 0, int(pid))
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == 259          # STILL_ACTIVE
    except Exception:
        return False


def tim_hub():
    """→ dict {pid, httpPort, csrfToken, lsVersion} của Antigravity đang mở (file hub_*.json mới nhất có tiến trình còn sống), hoặc None."""
    try:
        fs = sorted(DAEMON_DIR.glob("hub_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    except Exception:
        return None
    for f in fs:
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            if j.get("httpPort") and j.get("csrfToken") and _song(j.get("pid")):
                return j
        except Exception:
            continue
    return None


def trang_thai_agy():
    """{mo, phien_ban} — chỉ đọc file + kiểm tiến trình, không gọi mô hình."""
    h = tim_hub()
    return {"mo": bool(h), "phien_ban": (h or {}).get("lsVersion")}


def mo_antigravity():
    """Mở Antigravity tách rời hub (đóng hub không tắt nó)."""
    if tim_hub():
        return {"ok": True, "da_mo": True}
    if not AGY_EXE.exists():
        return {"ok": False, "loi": "Không thấy Antigravity ở máy này."}
    try:
        subprocess.Popen([str(AGY_EXE)], close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=0x00000008 | 0x00000200)          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    except Exception as e:
        return {"ok": False, "loi": str(e)[:150]}
    return {"ok": True}


def _agentapi(*args, timeout=60, project=None):
    h = tim_hub()
    if not h:
        raise ChuaMo("Antigravity chưa mở — bấm Mở Antigravity rồi Học cảnh lại.")
    if not LS_EXE.exists():
        raise ChuaMo("Không thấy language_server.exe của Antigravity.")
    huy = _RUN["huy"]
    if huy.is_set():
        raise Huy()
    env = dict(os.environ, ANTIGRAVITY_LS_ADDRESS=f"127.0.0.1:{h['httpPort']}", ANTIGRAVITY_CSRF_TOKEN=str(h["csrfToken"]))
    if project:
        env["ANTIGRAVITY_PROJECT_ID"] = str(project)       # cuộc trò chuyện nằm trong "Project" (mục Projects ở thanh trái) có id này
    p = subprocess.Popen([str(LS_EXE), "agentapi", *args], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", errors="replace", creationflags=NO_WIN)
    with _RUN_LOCK:
        _RUN["proc"].add(p)
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
            _RUN["proc"].discard(p)
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
        JOB["canh_bao"] = ("Antigravity chưa nhận Project tự duyệt của Xưởng Video nên có thể còn hỏi \"Accept\". "
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
        with ThreadPoolExecutor(max_workers=4) as ex:
            for pid, ws in ex.map(doc, ids):
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
            huy=None, huy_cuoc=None):
    """Gửi 1 lần cho Antigravity rồi chờ MỖI file trong `outs` xuất hiện và ổn định (kích thước không đổi 2 lần kiểm liền).
    Mỗi file xong thì gọi khi_co(path, nội dung chữ) ngay. Quá hạn (= han_moi_video × số video, tối đa HAN_LO_TOI_DA_S) thì thôi.
    Anh bấm Dừng (`huy` được đặt) → huỷ ngay cuộc trò chuyện ở Antigravity, xoá file đầu ra dở dang, trả về phần đã xong. Quá hạn cũng huỷ.
    → danh sách path đã nhận được."""
    huy = huy or _RUN["huy"]
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
            _RUN["conv"].add(cid)
    cu = {o: -1 for o in outs}; on = {o: 0 for o in outs}; xong = []
    t = 0
    try:
        while t <= han and len(xong) < len(outs) and not huy.is_set():
            ngu(CHU_KY_S); t += CHU_KY_S
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
        if cid:
            with _RUN_LOCK:
                _RUN["conv"].discard(cid)
    return xong


# ----------------------------------------------------------------------------------------------- tiến độ + vòng học
JOB = {"dang_chay": False, "ma": None, "tong": 0, "xong": 0, "hien_tai": "", "loi": [], "trang_thai": "nghi", "thong_bao": "",
       "bat_dau": None, "dung": False, "dang_dung": False, "canh_bao": ""}
_LOCK = threading.Lock()


def doc_cau_hinh():
    try:
        return cfg_hub().get("hoc_canh", {})
    except Exception:
        return {}


def doc_model():
    m = str(doc_cau_hinh().get("model") or "")
    return m if m in MODELS else MODEL_MAC_DINH          # giá trị cũ (gemini-*) → flash


def doc_song_song():
    try:
        return max(1, min(4, int(doc_cau_hinh().get("song_song") or SONG_SONG_MAC_DINH)))
    except Exception:
        return SONG_SONG_MAC_DINH


def co_lo(so_viec):
    """Số video mỗi cuộc trò chuyện: hoc_canh.lo nếu đặt; không thì 5 (kho ≤ 30 video cần học) hoặc 10 (nhiều hơn)."""
    try:
        v = int(doc_cau_hinh().get("lo") or 0)
    except Exception:
        v = 0
    return max(1, min(20, v)) if v else (5 if so_viec <= 30 else 10)


def ten_san_pham(ma):
    try:
        d = json.loads((HUB / "san-pham" / str(ma) / "san-pham.json").read_text(encoding="utf-8"))
        return str(d.get("ten_ngan") or d.get("ten_goi") or ma)[:40]
    except Exception:
        return str(ma)[:40]


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


def hoc_kho(ma_hoac_kho, model=None, runner=chay_lo, do_dai=km.do_dai_video, khi_xong=None, song_song=None, kiem_mo=None, project=False, ten=None,
            ban_san_xuat=None):
    """Học mọi video chưa có mô tả/hỏng của kho, gộp theo lô (mỗi lô 1 cuộc trò chuyện Antigravity). Chạy đồng bộ (gọi trong luồng nền).
    Video chưa đạt sau lô được học lại 1 lần trong lô nhỏ riêng. khi_xong(ket_qua) chạy khi học xong TRỌN VẸN.
    project=False: không đặt Project (thử máy giả); None/True: tự tìm Project theo kho.
    ban_san_xuat(): True khi hub đang làm video → Học cảnh chỉ chạy 1 lô một lúc (nhường máy), hết bận thì chạy đủ song_song lô. Học cảnh KHÔNG chặn làm video."""
    kho = km._kho_cua(ma_hoac_kho) if not Path(str(ma_hoac_kho)).is_absolute() else Path(ma_hoac_kho)
    model = model or doc_model()
    song_song = song_song or doc_song_song()
    kiem_mo = kiem_mo or (lambda: trang_thai_agy()["mo"])
    ten = ten or ten_san_pham(ma_hoac_kho)
    ban_san_xuat = ban_san_xuat or (lambda: False)
    with _LOCK:
        if JOB["dang_chay"]:
            return {"ok": False, "loi": "Đang học rồi."}
        huy = threading.Event()
        with _RUN_LOCK:
            _RUN.update(huy=huy, conv=set())
        JOB.update(dang_chay=True, ma=str(ma_hoac_kho), tong=0, xong=0, hien_tai="", loi=[], trang_thai="dang_chay", thong_bao="Đang kiểm kho…",
                   bat_dau=time.time(), dung=False, dang_dung=False, canh_bao="")
    kq = {"ok": True, "da_hoc": 0, "loi": [], "tat_ca_xong": False, "chi_tiet": [], "lo": 0, "project": None}
    st = {"qua_han_lien": 0, "dung_vi": None, "lo_dang": 0}
    kl = threading.Lock()
    dang = {}                     # tên video đang xem → số lô

    def xong_video(rel, ok, giay, loi=None):
        with kl:
            JOB["xong"] += 1
            kq["chi_tiet"].append({"video": rel, "ok": ok, "giay": giay})
            if ok:
                kq["da_hoc"] += 1
            else:
                JOB["loi"].append({"video": rel, "loi": str(loi)[:200]}); kq["loi"].append(rel)

    def chay_mot_lo(ds, so, tong_lo, pj, lan):
        """ds: [{rel, file_cu, dai, ghi_chu}] → trả danh sách video chưa đạt [{..., ghi_chu}] (lan 1) hoặc ghi lỗi cuối (lan 2)."""
        while True:                                     # đang làm video thì chỉ chạy 1 lô một lúc (nhường máy)
            with kl:
                if huy.is_set() or st["dung_vi"]:
                    return list(ds) if lan == 1 else []
                if not (st["lo_dang"] >= 1 and ban_san_xuat()):
                    st["lo_dang"] += 1
                    for v in ds:
                        dang[Path(v["rel"]).name] = so
                    JOB.update(hien_tai=", ".join(dang))
                    break
            huy.wait(2)
        t0 = time.time()
        sau = []
        try:
            if not kiem_mo():
                raise ChuaMo("Antigravity chưa mở — bấm Mở Antigravity rồi Học cảnh lại.")
            tam = kho / "_tam" / "hoc-canh"
            viec = []
            for v in ds:
                h = hashlib.sha1(v["rel"].encode("utf-8")).hexdigest()[:10]
                ra = (tam / f"{h}{'' if lan == 1 else '-2'}.json").resolve()
                src = (kho / v["rel"]).resolve()
                viec.append(dict(v, src=str(src), ra=str(ra)))
            theo_ra = {Path(v["ra"]): v for v in viec}
            ket = {}

            def khi_co(ra, text):
                v = theo_ra[Path(ra)]
                if huy.is_set():
                    return
                try:
                    obj, _g, _cb = km.chuan_hoa_noi_dung(text, v["dai"], v["rel"])
                    obj["video"] = v["rel"]
                    _ghi_ket_qua(kho, v["rel"], v.get("file_cu"), obj)
                    ket[v["rel"]] = True
                    with kl:
                        dang.pop(Path(v["rel"]).name, None); JOB.update(hien_tai=", ".join(dang))
                    xong_video(v["rel"], True, round(time.time() - t0))
                except km.Hong as e:
                    ket[v["rel"]] = "JSON không dùng được: " + str(e)[:200]
                except Exception as e:
                    ket[v["rel"]] = f"{type(e).__name__}: {str(e)[:160]}"
            tieu_de = f"Xưởng Video · {ten} · lô {so}/{tong_lo}" + ("" if lan == 1 else " (làm lại)")
            kw = {"project": pj} if pj else {}
            nhan = runner(model, loi_nhac_lo(viec), [Path(v["ra"]) for v in viec], tieu_de, khi_co, **kw)
            for v in viec:
                if ket.get(v["rel"]) is True:
                    continue
                if lan == 1:
                    sau.append(dict(v, ghi_chu=ket.get(v["rel"]) if isinstance(ket.get(v["rel"]), str) else None))
                else:
                    xong_video(v["rel"], False, round(time.time() - t0), ket.get(v["rel"]) if isinstance(ket.get(v["rel"]), str) else
                               "Antigravity không ghi kết quả cho video này (có thể hết lượt model hoặc video khó đọc) — bấm Học cảnh để thử lại.")
            with kl:
                st["qua_han_lien"] = st["qua_han_lien"] + 1 if (not nhan and lan == 1 and not huy.is_set()) else 0
                if st["qua_han_lien"] >= 2:
                    st["dung_vi"] = ("het_luot", "Antigravity không trả lời 2 lô liền (có thể hết lượt model) — đợi một lúc rồi bấm Học cảnh làm tiếp (tiến độ đã giữ).")
        except Huy:
            sau = list(ds) if lan == 1 else []
        except ChuaMo as e:
            with kl:
                st["dung_vi"] = ("can_mo", str(e))
            sau = list(ds) if lan == 1 else []
        except Exception as e:                                          # lỗi 1 lô không được làm sập cả kho
            m = str(e)[:200] if isinstance(e, LoiTam) else f"{type(e).__name__}: {str(e)[:160]}"
            if lan == 1:
                sau = [dict(v, ghi_chu=None) for v in ds]
            else:
                for v in ds:
                    xong_video(v["rel"], False, round(time.time() - t0), m)
        finally:
            with kl:
                st["lo_dang"] -= 1
                for v in ds:
                    dang.pop(Path(v["rel"]).name, None)
                JOB.update(hien_tai=", ".join(dang))
        return sau

    def chay_cac_lo(dsv, lan, pj):
        lo = co_lo(len(dsv)) if lan == 1 else max(1, min(3, co_lo(len(dsv))))
        cac = [dsv[i:i + lo] for i in range(0, len(dsv), lo)]
        kq["lo"] += len(cac)
        con = []
        with ThreadPoolExecutor(max_workers=song_song) as ex:
            fs = [ex.submit(chay_mot_lo, c, i + 1, len(cac), pj, lan) for i, c in enumerate(cac)]
            for f in fs:
                con += f.result()
        return con

    try:
        def _td(i, n, ten_f):
            if huy.is_set():
                raise Huy()
        rep = km.kiem_kho(kho, sua=True, do_dai=do_dai, tien_do=_td)         # chuẩn hoá cái đã có + biết video nào thiếu/hỏng
        viec = [(x["video"] if isinstance(x, dict) else x, None) for x in rep["thieu_mo_ta"]]
        viec += [(h["video"], h["file"]) for h in rep["hong"] if h.get("video")]
        JOB.update(tong=len(viec), thong_bao="Đang học cảnh…")
        if viec and not kiem_mo():
            st["dung_vi"] = ("can_mo", "Antigravity chưa mở — bấm Mở Antigravity rồi Học cảnh lại.")
        elif viec:
            ds = []
            for rel, fc in viec:
                if huy.is_set():
                    raise Huy()
                d = do_dai(kho / rel)
                if not d:
                    xong_video(rel, False, 0, "Không đo được độ dài video (file hỏng?).")
                else:
                    ds.append({"rel": rel, "file_cu": fc, "dai": d})
            pj = tim_project(kho) if project is not False else None
            kq["project"] = pj
            con = chay_cac_lo(ds, 1, pj)
            if con and not st["dung_vi"] and not huy.is_set():
                JOB.update(thong_bao=f"Làm lại {len(con)} video chưa đạt…")
                chay_cac_lo(con, 2, pj)
        if st["dung_vi"]:
            JOB.update(trang_thai=st["dung_vi"][0], thong_bao=st["dung_vi"][1])
        elif huy.is_set() and JOB["xong"] < len(viec):
            JOB.update(trang_thai="dung", thong_bao="Đã dừng — bấm Học cảnh để làm tiếp.")
        else:
            kq["tat_ca_xong"] = True
            JOB.update(trang_thai="xong", thong_bao="Kho đã đủ mô tả." if not viec else f"Học xong {kq['da_hoc']} video" +
                       (f", {len(kq['loi'])} video lỗi" if kq["loi"] else "") + ".")
    except Huy:
        JOB.update(trang_thai="dung", thong_bao="Đã dừng — bấm Học cảnh để làm tiếp.")
    except Exception as e:
        JOB.update(trang_thai="loi", thong_bao=f"Lỗi: {str(e)[:200]}"); kq.update(ok=False, tat_ca_xong=False)
    finally:
        with _RUN_LOCK:
            con_cuoc = list(_RUN["conv"]); _RUN["conv"].clear()
        if huy.is_set():
            for c in con_cuoc:                                  # còn cuộc trò chuyện nào chưa huỷ thì huỷ nốt
                huy_cuoc_tro_chuyen(c)
        shutil.rmtree(kho / "_tam" / "hoc-canh", ignore_errors=True)
        JOB.update(dang_chay=False, dang_dung=False, hien_tai="")
    if kq.get("tat_ca_xong") and khi_xong:
        try:
            khi_xong(kq)
        except Exception as e:
            JOB["thong_bao"] += f" (không tự chuẩn bị kho được: {str(e)[:80]})"
    return kq


def bat_dau_nen(ma, khi_xong=None, **kw):
    """Bắt đầu học ở luồng nền (mỗi lần 1 việc)."""
    if JOB["dang_chay"]:
        return {"ok": False, "loi": "Đang học rồi."}
    kw.setdefault("project", None)
    t = threading.Thread(target=hoc_kho, args=(ma,), kwargs=dict(khi_xong=khi_xong, **kw), daemon=True)
    t.start()
    for _ in range(50):                                          # chờ luồng nhận việc (để trả lời API thấy ngay "đang chạy")
        if JOB["dang_chay"]:
            break
        time.sleep(0.02)
    return {"ok": True}


def dung():
    """Dừng THẬT: đặt cờ huỷ (các luồng thôi chờ trong ≤1 giây), huỷ ngay các cuộc trò chuyện Antigravity đang làm, giết tiến trình agentapi
    đang treo. Giao diện hiện 'Đang dừng…' (JOB.dang_dung) tới khi luồng học thoát hẳn (dang_chay=False)."""
    if not JOB["dang_chay"]:
        return {"ok": True, "dang_dung": False}
    huy = _RUN["huy"]
    JOB.update(dung=True, dang_dung=True, thong_bao="Đang dừng…")
    huy.set()
    with _RUN_LOCK:
        cac = list(_RUN["conv"])

    def lam():
        for c in cac:
            huy_cuoc_tro_chuyen(c)
    if cac:
        threading.Thread(target=lam, daemon=True, name="hoc-canh-huy").start()
    return {"ok": True, "dang_dung": True}
