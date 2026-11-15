"""Thử Học cảnh NHIỀU SẢN PHẨM CÙNG LÚC: chạy song song, Dừng đúng 1 sản phẩm, 1 sản phẩm không học 2 lần, hàng chờ, khôi phục nhiều việc dở.
Dùng runner/cat/to_anh giả (xem _gia_phieu.py) — không gọi Antigravity thật."""
import json, os, sys, tempfile, threading, time, unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp(prefix="xv-test-")
os.environ.setdefault("XUONG_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hoc_canh as hc  # noqa: E402
import _gia_phieu as gia  # noqa: E402


def _kho(tag, n=1):
    k = Path(tempfile.mkdtemp(prefix=f"kho{tag}-", dir=TMP))
    for i in range(n):
        (k / f"v{i}.mp4").write_bytes(b"x")
    return k


def _doi(dk, han=10):
    t = time.time()
    while time.time() - t < han:
        if dk():
            return True
        time.sleep(0.02)
    return False


class NhieuSanPhamTest(unittest.TestCase):
    def setUp(self):
        self.hub = Path(tempfile.mkdtemp(prefix="hub-", dir=TMP)); self._ls = hc.LS; hc.LS = self.hub / "lich-su"
        hc._JOBS.clear(); hc._RUNS.clear(); hc._HANG.clear(); hc._DANG.clear()
        self.cfg = {}
        for ten, gt in (("doc_cau_hinh", lambda: self.cfg), ("_goi_ls", lambda *a, **k: None), ("_agy_exe_chay", lambda: False)):
            p = mock.patch.object(hc, ten, gt); p.start(); self.addCleanup(p.stop)
        p = mock.patch.object(hc, "CHU_KY_S", 0.02); p.start(); self.addCleanup(p.stop)
        self.luong = []
        self.addCleanup(self._don)

    def _don(self):
        hc.dung()
        for t in self.luong:
            t.join(10)
        hc.LS = self._ls

    def _hoc(self, kho, runner, **kw):
        """Chạy hoc_kho của 1 sản phẩm ở luồng nền; → (luồng, dict kết quả)."""
        kq = {}
        a = dict(runner=runner, do_dai=lambda p: 40.0, kiem_mo=lambda: True, project=False, ten="t", cat=gia.cat_gia(2), to_anh=gia.to_anh_gia)
        a.update(kw)
        t = threading.Thread(target=lambda: kq.update(hc.hoc_kho(str(kho), **a)), daemon=True); t.start(); self.luong.append(t)
        return t, kq

    def test_hai_san_pham_chay_cung_luc(self):
        ka, kb = _kho("A"), _kho("B"); log = []
        bar = threading.Barrier(2, timeout=10)                  # cả hai runner phải ở trong runner CÙNG LÚC mới qua được

        def runner(model, prompt, outs, td, khi_co, **kw):
            bar.wait()
            return gia.runner_gia(log)(model, prompt, outs, td, khi_co, **kw)
        ta, ra = self._hoc(ka, runner); tb, rb = self._hoc(kb, runner)
        ta.join(15); tb.join(15)
        self.assertEqual((ra.get("da_hoc"), rb.get("da_hoc")), (1, 1), (ra, rb))
        self.assertEqual(len(log), 2)
        self.assertEqual((hc.job(str(ka))["trang_thai"], hc.job(str(kb))["trang_thai"]), ("xong", "xong"))
        self.assertEqual(sorted(hc.tat_ca_job()), sorted([str(ka), str(kb)])); self.assertEqual(hc.dang_hoc(), [])
        self.assertTrue((ka / "_mo-ta" / "v0.mp4.mo-ta.json").exists() and (kb / "_mo-ta" / "v0.mp4.mo-ta.json").exists())

    def test_dung_a_khong_dung_b(self):
        ka, kb = _kho("A"), _kho("B"); huy_goi = []; cho_b = {}

        def gui(model, prompt, td, project=None):
            ra = gia.ra_tu_prompt(prompt)
            if str(ka) in prompt:
                return "cid-A"
            cho_b["prompt"], cho_b["ra"] = prompt, ra            # B chưa có phiếu tới khi test thả
            return "cid-B"
        runner = lambda *a, **k: hc.chay_lo(*a, gui=gui, **k)
        with mock.patch.object(hc, "huy_cuoc_tro_chuyen", huy_goi.append):
            ta, ra = self._hoc(ka, runner); tb, rb = self._hoc(kb, runner)
            self.assertTrue(_doi(lambda: set(hc._RUNS.get(str(ka), {}).get("conv", ())) == {"cid-A"} and set(hc._RUNS.get(str(kb), {}).get("conv", ())) == {"cid-B"}))
            self.assertTrue(hc.dung(str(ka))["dang_dung"])
            ta.join(10); self.assertFalse(ta.is_alive())
            self.assertEqual(hc.job(str(ka))["trang_thai"], "dung")
            self.assertEqual(set(huy_goi), {"cid-A"})                                  # chỉ huỷ cuộc trò chuyện của A
            self.assertTrue(hc.job(str(kb))["dang_chay"]); self.assertFalse(hc._RUNS[str(kb)]["huy"].is_set()); self.assertFalse(hc.job(str(kb))["dang_dung"])
            self.assertEqual(hc.dang_hoc(), [str(kb)])
            cho_b["ra"].parent.mkdir(parents=True, exist_ok=True)                    # thả B: phiếu về → B vẫn học xong bình thường
            cho_b["ra"].write_text(json.dumps(gia.phieu_tu_prompt(cho_b["prompt"]), ensure_ascii=False), encoding="utf-8")
            tb.join(10); self.assertFalse(tb.is_alive())
        self.assertEqual(rb["da_hoc"], 1); self.assertEqual(hc.job(str(kb))["trang_thai"], "xong"); self.assertEqual(ra["da_hoc"], 0)

    def test_cung_san_pham_hai_lan_bi_tu_choi(self):
        ka = _kho("A"); cong = threading.Event(); vao = threading.Event()

        def runner(model, prompt, outs, td, khi_co, **kw):
            vao.set(); cong.wait(10)
            return gia.runner_gia([])(model, prompt, outs, td, khi_co, **kw)
        ta, ra = self._hoc(ka, runner); self.assertTrue(vao.wait(10))
        self.assertEqual(hc.hoc_kho(str(ka)), {"ok": False, "loi": "Đang học rồi."})
        self.assertEqual(hc.bat_dau_nen(str(ka)), {"ok": False, "loi": "Đang học rồi."})
        kb = _kho("B")
        self.assertEqual(hc.job(str(kb))["dang_chay"], False)                       # sản phẩm khác không bị ảnh hưởng
        cong.set(); ta.join(10)
        self.assertEqual(ra["da_hoc"], 1)
        t2, r2 = self._hoc(ka, gia.runner_gia([])); t2.join(10)                      # học xong rồi thì bấm lại được
        self.assertTrue(r2["ok"])

    def test_hang_cho_tu_chay_khi_het_cho(self):
        self.cfg.update(toi_da_sp=1)
        ka, kb, kc = _kho("A"), _kho("B"), _kho("C"); cong = threading.Event(); vao = threading.Event(); thu_tu = []

        def runner(model, prompt, outs, td, khi_co, **kw):
            thu_tu.append("A" if str(ka) in prompt else "B" if str(kb) in prompt else "C"); vao.set(); cong.wait(10)
            return gia.runner_gia([])(model, prompt, outs, td, khi_co, **kw)
        ta, ra = self._hoc(ka, runner); self.assertTrue(vao.wait(10))
        tb, rb = self._hoc(kb, runner)
        self.assertTrue(_doi(lambda: hc.job(str(kb)).get("cho") == 1))
        tc, rc = self._hoc(kc, runner)
        self.assertTrue(_doi(lambda: hc.job(str(kc)).get("cho") == 2))
        self.assertIn("xếp thứ 1", hc.job(str(kb))["thong_bao"]); self.assertTrue(hc.job(str(kb))["dang_chay"])
        self.assertEqual(hc.hoc_kho(str(kb)), {"ok": False, "loi": "Đang học rồi."})        # đang chờ cũng tính là đang học
        self.assertEqual(thu_tu, ["A"])                                                  # B, C chưa chạy
        cong.set()
        for t in (ta, tb, tc):
            t.join(15)
        self.assertEqual(thu_tu, ["A", "B", "C"])                                         # đúng thứ tự xếp hàng
        self.assertEqual((ra["da_hoc"], rb["da_hoc"], rc["da_hoc"]), (1, 1, 1))
        self.assertEqual(hc.job(str(kb))["cho"], 0); self.assertEqual((list(hc._HANG), set(hc._DANG)), ([], set()))

    def test_dung_san_pham_dang_cho_hang(self):
        self.cfg.update(toi_da_sp=1)
        ka, kb = _kho("A"), _kho("B"); cong = threading.Event(); vao = threading.Event(); goi = []

        def runner(model, prompt, outs, td, khi_co, **kw):
            goi.append(prompt); vao.set(); cong.wait(10)
            return gia.runner_gia([])(model, prompt, outs, td, khi_co, **kw)
        ta, ra = self._hoc(ka, runner); self.assertTrue(vao.wait(10))
        tb, rb = self._hoc(kb, runner); self.assertTrue(_doi(lambda: hc.job(str(kb)).get("cho") == 1))
        hc.dung(str(kb)); tb.join(10)
        self.assertFalse(tb.is_alive()); self.assertEqual(hc.job(str(kb))["trang_thai"], "dung"); self.assertEqual(rb["da_hoc"], 0)
        self.assertTrue(hc.job(str(ka))["dang_chay"]); self.assertEqual(len(goi), 1)       # A không bị đụng tới
        cong.set(); ta.join(10); self.assertEqual(ra["da_hoc"], 1)

    def test_dung_het_dung_moi_san_pham(self):
        ka, kb = _kho("A"), _kho("B"); vao = threading.Barrier(3, timeout=10)

        def runner(model, prompt, outs, td, khi_co, **kw):
            vao.wait(); hc._run_hien()["huy"].wait(10)
            return []
        ta, _ = self._hoc(ka, runner); tb, _ = self._hoc(kb, runner); vao.wait()
        self.assertEqual(hc.dung()["so"], 2)
        ta.join(10); tb.join(10)
        self.assertEqual((hc.job(str(ka))["trang_thai"], hc.job(str(kb))["trang_thai"]), ("dung", "dung"))

    def test_luu_nhieu_luong_van_la_json_hop_le(self):
        for k in ("a", "b", "c"):
            hc._JOBS[k] = dict(hc._job_rong(), ma=k)
        ths = [threading.Thread(target=lambda: [hc._luu() for _ in range(30)]) for _ in range(6)]
        [t.start() for t in ths]; [t.join(20) for t in ths]
        d = json.loads((hc.LS / "hoc-canh-job.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(d["jobs"]), ["a", "b", "c"]); self.assertEqual([f.name for f in hc.LS.glob("*.tmp")], [])

    def test_khoi_phuc_hai_san_pham_dang_do(self):
        k1, k2, k3 = _kho("A"), _kho("B"), _kho("C")
        for k in (k1, k2):
            (k / "_tam" / "hoc-canh" / "01-x").mkdir(parents=True); (k / "_tam" / "hoc-canh" / "01-x" / "to-1.jpg").write_bytes(b"j")
        hc.LS.mkdir(parents=True)
        jb = lambda ma, **kw: dict(hc._job_rong(), ma=ma, dang_chay=True, trang_thai="dang_chay", giai_doan="hoc", **kw)
        (hc.LS / "hoc-canh-job.json").write_text(json.dumps({"jobs": {
            str(k1): {"job": jb(str(k1)), "conv": ["c1", "c2"], "kho": str(k1)},
            str(k2): {"job": jb(str(k2)), "conv": ["c3"], "kho": str(k2)},
            str(k3): {"job": dict(hc._job_rong(), ma=str(k3), trang_thai="xong"), "conv": [], "kho": str(k3)}}, "luc": 1}), encoding="utf-8")
        huy = []
        with mock.patch.object(hc, "huy_cuoc_tro_chuyen", huy.append):
            n = hc.khoi_phuc()
        self.assertEqual((n, sorted(huy)), (3, ["c1", "c2", "c3"]))
        for k in (k1, k2):
            self.assertFalse((k / "_tam" / "hoc-canh").exists())
            j = hc.job(str(k)); self.assertEqual((j["trang_thai"], j["dang_chay"], j["dung"], j["thong_bao"]), ("dung", False, True, hc.MSG_KHOI_PHUC))
        self.assertEqual(hc.job(str(k3))["trang_thai"], "nghi")                              # việc đã xong thì không đụng
        now = json.loads((hc.LS / "hoc-canh-job.json").read_text(encoding="utf-8"))["jobs"]
        self.assertTrue(all(not e["job"]["dang_chay"] and e["conv"] == [] for e in now.values()))
        with mock.patch.object(hc, "huy_cuoc_tro_chuyen", lambda c: self.fail("chỉ khôi phục 1 lần")):
            self.assertIsNone(hc.khoi_phuc())


if __name__ == "__main__":
    unittest.main()
