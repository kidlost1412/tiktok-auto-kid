"""ai._goi_1 đọc stdout từng dòng (--include-partial-messages) để đẩy chữ Claude sang việc trực tiếp, mà kết quả/hạn chót/xoay tài khoản
vẫn y hệt cách cũ (communicate). KHÔNG gọi Claude thật: subprocess.Popen được thay bằng tiến trình giả có kịch bản."""
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

GOC = Path(__file__).resolve().parents[1]
for p in (str(GOC / "engine"), str(GOC / "app")):
    if p not in sys.path:
        sys.path.insert(0, p)

import ai  # noqa: E402
import truc_tiep as T  # noqa: E402


def ev(**k):
    return json.dumps(k, ensure_ascii=False) + "\n"


def delta(t):
    return ev(type="stream_event", event={"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": t}})


def nghi(t):
    return ev(type="stream_event", event={"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": t}})


KET_QUA = '[{"text":"Vườn cà phê cần phun. Nano Đồng đây nhé! Mua ngay"}]'
RL = {"status": "allowed", "unifiedWindows": {"five_hour": {"utilization": 0.31, "resetsAt": 1763500000, "status": "allowed"},
                                              "seven_day": {"utilization": 0.1, "resetsAt": 1763900000, "status": "allowed"}}}
KICH_BAN = [
    ev(type="system", subtype="init"),
    "dòng rác không phải JSON\n",
    nghi("Mình cân nhắc "), nghi("câu mở đầu"),
    delta('[{"text":"Vườn cà phê cần ph'), delta('un. Nano Đồng đ'), delta('ây nhé! Mua ngay"}]'),
    ev(type="rate_limit_event", rate_limit_info=RL),
    ev(type="assistant", message={"content": [{"type": "text", "text": KET_QUA}]}),
    ev(type="result", subtype="success", result=KET_QUA, is_error=False, usage={"input_tokens": 10, "output_tokens": 20}, total_cost_usd=0.1, num_turns=1),
]


class VaoGia:
    def __init__(self):
        self.data = ""
        self.dong = False

    def write(self, s):
        self.data += s

    def close(self):
        self.dong = True


class TienTrinhGia:
    """Giống subprocess.Popen(text=True): stdin/stdout/stderr, communicate() (cách cũ) và wait()/pid (cách mới).
    cho_o = (chỉ số dòng, sự_kiện_đã_tới, sự_kiện_cho_phép_đi_tiếp): dừng giữa luồng để test đọc file giữa chừng.
    treo=True: stdout chặn tới khi bị taskkill."""

    def __init__(self, dong, err="", rc=0, treo=False, cho_o=None, pid=4242):
        self.dong, self.err, self.rc, self.treo, self.cho_o, self.pid = dong, err, rc, treo, cho_o, pid
        self.stdin = VaoGia()
        self.stderr = io.StringIO(err)
        self.returncode = None
        self.chet = threading.Event()
        self.da_communicate = False
        self.stdout = self._doc()

    def _doc(self):
        for i, l in enumerate(self.dong):
            if self.cho_o and i == self.cho_o[0]:
                self.cho_o[1].set()
                self.cho_o[2].wait(10)
            yield l
        if self.treo:
            self.chet.wait(20)

    def communicate(self, inp=None, timeout=None):
        self.da_communicate = True
        self.stdin.write(inp or "")
        if self.treo:
            import subprocess
            if not self.chet.wait(timeout):
                raise subprocess.TimeoutExpired("claude", timeout)
        self.returncode = self.rc
        return "".join(self.dong), self.err

    def wait(self, timeout=None):
        if self.treo and not self.chet.is_set():
            import subprocess
            raise subprocess.TimeoutExpired("claude", timeout)
        self.returncode = 1 if self.chet.is_set() else self.rc
        return self.returncode


class GoiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.cu = (T._THU_MUC, T.GIAN_CACH)
        T._THU_MUC, T.GIAN_CACH = str(self.d / "truc-tiep"), 0.0
        self.live = True
        self.cmds, self.kills, self.trang_thai, self.ps = [], [], [], []
        self.pa = [
            mock.patch.object(ai, "cfg", lambda: {"duong_dan": {"claude": "claude-gia"}, "truc_tiep": self.live, "claude": {}}),
            mock.patch.object(ai, "he_thong", lambda vai: "he thong"),
            mock.patch.object(ai, "_ghi_trang_thai", lambda ma, **kv: self.trang_thai.append((ma, sorted(kv)))),
            mock.patch.object(ai.subprocess, "Popen", self._popen),
            mock.patch.object(ai.subprocess, "run", self._run),
            mock.patch.object(T, "dang_bat", lambda: self.live),
        ]
        for p in self.pa:
            p.start()
        self.tk = {"ma": "tk1", "ten": "T1", "thu_muc": None}

    def tearDown(self):
        for p in reversed(self.pa):
            p.stop()
        for t in list(T._MO):
            t.xong()
        T._THU_MUC, T.GIAN_CACH = self.cu
        self.tmp.cleanup()

    def _popen(self, cmd, **kw):
        self.cmds.append(cmd)
        return self.ps.pop(0)

    def _run(self, cmd, **kw):
        self.kills.append(cmd)
        for p in self.proc_treo:
            p.chet.set()
        return mock.Mock(returncode=0)
    proc_treo = ()

    def goi_1(self, tien_trinh, **kw):
        self.ps.append(tien_trinh)
        return ai._goi_1(self.tk, kw.pop("vai", "biên kịch"), kw.pop("prompt", "Viết lời"), kw.pop("anh", None), "opus", "high", kw.pop("timeout", 30), **kw)

    def doc(self, tt):
        return json.loads((self.d / "truc-tiep" / f"{tt.id}.json").read_text(encoding="utf-8"))

    # ---- hành vi giữ nguyên
    def test_ket_qua_y_het_cach_cu(self):
        self.live = False
        r0, k0, rl0 = self.goi_1(TienTrinhGia(KICH_BAN, err="canh bao"))
        self.live = True
        p = TienTrinhGia(KICH_BAN, err="canh bao")
        r1, k1, rl1 = self.goi_1(p)
        self.assertEqual((r1.stdout, r1.stderr, r1.returncode), (r0.stdout, r0.stderr, r0.returncode))
        self.assertEqual(r1.stdout, "".join(KICH_BAN))
        self.assertEqual(k1, k0)
        self.assertEqual(k1["result"], KET_QUA)
        self.assertEqual(rl1, rl0)
        self.assertEqual(rl1, RL)
        self.assertEqual(self.trang_thai, [("tk1", ["cap_nhat", "dang_nhap", "five_hour", "seven_day"])] * 2)    # xoay hạn mức: ghi như cũ
        self.assertFalse(p.da_communicate)                                                                        # cách mới không dùng communicate
        self.assertTrue(p.stdin.dong)

    def test_co_stream_chi_khi_bat_cong_tac(self):
        self.live = False
        self.goi_1(TienTrinhGia(KICH_BAN))
        self.live = True
        self.goi_1(TienTrinhGia(KICH_BAN))
        self.assertNotIn("--include-partial-messages", self.cmds[0])
        self.assertIn("--include-partial-messages", self.cmds[1])
        self.assertEqual(self.cmds[1][:6], ["claude-gia", "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages"])
        self.assertEqual(self.cmds[0][:5], ["claude-gia", "-p", "--output-format", "stream-json", "--verbose"])
        self.assertEqual(self.cmds[0][5:], [c for c in self.cmds[1][6:]])           # phần còn lại của lệnh giữ nguyên

    def test_cong_tac_tat_khong_ghi_file_va_dung_communicate(self):
        self.live = False
        p = TienTrinhGia(KICH_BAN)
        with T.viec("bien-kich", "x"):
            self.goi_1(p)
        self.assertTrue(p.da_communicate)
        self.assertEqual(p.stdin.data, "Viết lời")
        self.assertFalse((self.d / "truc-tiep").exists())

    def test_stdin_duoc_gui_day_du_ca_khi_anh_nhung(self):
        with mock.patch.object(ai, "_nap_anh", lambda a: ("image/jpeg", "QUJD")):
            p = TienTrinhGia(KICH_BAN)
            self.goi_1(p, anh=["a.jpg"], nhung=True)
        j = json.loads(p.stdin.data)
        self.assertEqual(j["message"]["content"][1]["source"]["data"], "QUJD")
        self.assertIn("--input-format", self.cmds[0])
        self.assertTrue(p.stdin.dong)

    def test_ma_loi_va_stderr_van_tra_ve(self):
        r, k, rl = self.goi_1(TienTrinhGia([ev(type="result", result="hỏng", is_error=True)], err="boom", rc=3))
        self.assertEqual((r.returncode, r.stderr), (3, "boom"))
        self.assertTrue(k["is_error"])
        self.assertIsNone(rl)

    def test_khong_co_result_lay_400_ky_tu_cuoi(self):
        r, k, rl = self.goi_1(TienTrinhGia(["không phải json\n"] * 100, rc=1))
        self.assertTrue(k["is_error"])
        self.assertEqual(len(k["result"]), 400)

    # ---- việc trực tiếp
    def test_giua_luong_dong_dang_go_suy_nghi_ky_tu(self):
        toi, di = threading.Event(), threading.Event()
        p = TienTrinhGia(KICH_BAN, cho_o=(6, toi, di))              # trước mảnh chữ thứ 3 ("ây nhé! Mua ngay")
        kq, loi = [], []

        def chay():
            try:
                with T.viec("bien-kich", "Đang viết lời đọc", sp="Nano Đồng") as tt:
                    kq.append(tt)
                    self.goi_1(p)
            except BaseException as e:                              # noqa: BLE001
                loi.append(e)
        th = threading.Thread(target=chay)
        th.start()
        self.assertTrue(toi.wait(5))
        time.sleep(0.15)
        x = self.doc(kq[0])
        self.assertEqual(x["dong"], ["Vườn cà phê cần phun."])      # câu xong đã vào dong khi chuỗi chưa hết
        self.assertEqual(x["dang_go"], "Nano Đồng đ")                # câu đang gõ dở
        self.assertEqual(x["suy_nghi"], "Mình cân nhắc câu mở đầu")
        self.assertEqual(x["ky_tu"], len('[{"text":"Vườn cà phê cần ph') + len("un. Nano Đồng đ"))
        self.assertEqual(x["chi_tiet"]["model"], "opus")
        self.assertFalse(x["xong"])
        di.set()
        th.join(10)
        self.assertEqual(loi, [])
        x = self.doc(kq[0])
        self.assertEqual(x["dong"], ["Vườn cà phê cần phun.", "Nano Đồng đây nhé!", "Mua ngay"])
        self.assertIsNone(x["dang_go"])
        self.assertTrue(x["xong"])
        self.assertEqual(x["ket_qua"], "ok")
        self.assertEqual(x["ky_tu"], len('[{"text":"Vườn cà phê cần ph') + len("un. Nano Đồng đ") + len('ây nhé! Mua ngay"}]'))

    def test_cli_cu_khong_co_stream_lay_chu_tu_result(self):
        cu = [ev(type="result", result=KET_QUA, is_error=False, usage={})]
        with T.viec("bien-kich", "x") as tt:
            self.goi_1(TienTrinhGia(cu))
        self.assertEqual(self.doc(tt)["dong"], ["Vườn cà phê cần phun.", "Nano Đồng đây nhé!", "Mua ngay"])

    def test_thu_lai_tai_khoan_khac_giu_dong_cu_va_chot_cau_do(self):
        with T.viec("bien-kich", "x") as tt:
            self.goi_1(TienTrinhGia([delta('[{"text":"Câu của lượt một chưa xong hẳn'), ev(type="result", result="", is_error=True)]))
            self.goi_1(TienTrinhGia([delta('[{"text":"Lượt hai viết câu khác hẳn nhé."}]'), ev(type="result", result="ok", is_error=False)]))
        x = self.doc(tt)
        self.assertEqual(x["dong"], ["Câu của lượt một chưa xong hẳn", "Lượt hai viết câu khác hẳn nhé."])

    def test_het_gio_giet_cay_va_nem_dung_loi_cu(self):
        p = TienTrinhGia(KICH_BAN[:6], treo=True)
        self.proc_treo = (p,)
        t0 = time.time()
        with T.viec("bien-kich", "x") as tt:
            with self.assertRaises(RuntimeError) as cm:
                self.goi_1(p, timeout=1, vai="biên kịch")
        self.assertEqual(str(cm.exception), "Claude quá 1s (biên kịch) — đã dừng")
        self.assertEqual(self.kills, [["taskkill", "/PID", "4242", "/T", "/F"]])
        self.assertLess(time.time() - t0, 8)
        x = self.doc(tt)
        self.assertEqual(x["ket_qua"], "ok")        # việc do người gọi mở: kết quả theo người gọi (ở đây with thoát bằng ngoại lệ đã bắt)
        self.assertEqual(x["dong"], ["Vườn cà phê cần phun.", "Nano Đồng đ"])   # chữ đã về trước khi hết giờ không mất (câu dở được chốt)

    def test_het_gio_cach_cu_van_nhu_truoc(self):
        self.live = False
        p = TienTrinhGia(KICH_BAN[:2], treo=True)
        self.proc_treo = (p,)
        with self.assertRaises(RuntimeError) as cm:
            self.goi_1(p, timeout=1)
        self.assertEqual(str(cm.exception), "Claude quá 1s (biên kịch) — đã dừng")
        self.assertEqual(self.kills, [["taskkill", "/PID", "4242", "/T", "/F"]])

    def test_nhip_tim_khi_chua_co_chu_moi(self):
        T.NHIP_GIAY = 0.2
        try:
            toi, di = threading.Event(), threading.Event()
            p = TienTrinhGia(KICH_BAN[:3], cho_o=(2, toi, di))
            kq = []

            def chay():
                with T.viec("giam-khao", "x") as tt:
                    kq.append(tt)
                    self.goi_1(p)
            th = threading.Thread(target=chay)
            th.start()
            toi.wait(5)
            time.sleep(1.6)                                         # hàng đợi trống ≥ 1 s: vòng đọc phải "đập tim" kèm số giây đã chờ
            x = self.doc(kq[0])
            self.assertGreaterEqual(x["chi_tiet"].get("giay", 0), 1)
            self.assertGreater(x["cap_nhat"], x["bat_dau"] + 1)
            di.set(); th.join(10)
        finally:
            T.NHIP_GIAY = 5.0


class GoiMoViecTest(unittest.TestCase):
    """ai.goi(): chưa có việc nào thì tự mở theo vai; ekip đã mở thì dùng việc đó."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.cu = (T._THU_MUC, T.GIAN_CACH, ai.HUB)
        T._THU_MUC, T.GIAN_CACH = str(self.d / "truc-tiep"), 0.0
        ai.HUB = self.d
        self.live = True
        self.thay = None
        self.pa = [
            mock.patch.object(ai, "cfg", lambda: {"duong_dan": {"claude": "c"}, "truc_tiep": self.live, "claude": {}}),
            mock.patch.object(ai, "chon_tai_khoan", lambda bo_qua=(): {"ma": "tk1", "ten": "T1", "thu_muc": None}),
            mock.patch.object(ai, "_goi_1", self._goi_1_gia),
            mock.patch.object(T, "dang_bat", lambda: self.live),
        ]
        for p in self.pa:
            p.start()

    def tearDown(self):
        for p in reversed(self.pa):
            p.stop()
        T._THU_MUC, T.GIAN_CACH, ai.HUB = self.cu
        self.tmp.cleanup()

    def _goi_1_gia(self, tk, vai, prompt, anh, model, effort, timeout, nhung=False):
        tt = T.hien_tai()
        self.thay = (tt.d["vai"], tt.d["viec"], tt.d["video"]) if tt else None
        if self.loi:
            raise RuntimeError("hỏng")
        r = mock.Mock(returncode=0, stderr="")
        return r, {"result": "xong rồi", "usage": {}}, None

    loi = False

    def cac_viec(self):
        return [json.loads(f.read_text(encoding="utf-8")) for f in (self.d / "truc-tiep").glob("*.json")] if (self.d / "truc-tiep").exists() else []

    def test_tu_mo_theo_vai(self):
        ai.VIEC.video = "nano-dong-2"
        try:
            self.assertEqual(ai.goi("đạo diễn XuanLuong", "x")[0], "xong rồi")
        finally:
            ai.VIEC.video = ""
        self.assertEqual(self.thay, ("dao-dien", "Đang hỏi Claude: lên bảng dựng", "nano-dong-2"))
        ds = self.cac_viec()
        self.assertEqual(len(ds), 1)
        self.assertTrue(ds[0]["xong"])
        self.assertEqual(ds[0]["ket_qua"], "ok")
        self.assertIsNone(T.hien_tai())

    def test_loi_thi_ket_qua_loi_va_loi_van_ra(self):
        self.loi = True
        try:
            with self.assertRaises(RuntimeError):
                ai.goi("giám khảo", "x")
        finally:
            self.loi = False
        ds = self.cac_viec()
        self.assertEqual((ds[0]["vai"], ds[0]["ket_qua"], ds[0]["xong"]), ("giam-khao", "loi", True))

    def test_dung_viec_cua_nguoi_goi_khong_mo_them(self):
        with T.viec("bien-kich", "Đang viết lời đọc", sp="Nano Đồng"):
            ai.goi("biên kịch", "x")
        self.assertEqual(self.thay[:2], ("bien-kich", "Đang viết lời đọc"))
        self.assertEqual(len(self.cac_viec()), 1)

    def test_cong_tac_tat_khong_mo_viec(self):
        self.live = False
        ai.goi("biên kịch", "x")
        self.assertIsNone(self.thay)
        self.assertEqual(self.cac_viec(), [])


if __name__ == "__main__":
    unittest.main()
