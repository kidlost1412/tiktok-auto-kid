"""Thử Học cảnh: dừng thật, làn riêng không chặn làm video, thiết lập tự duyệt (Project Turbo). Không cần Antigravity thật.
Chạy:  python -m unittest discover -s xuong-video/tests -v   (đặt XUONG_DATA = thư mục tạm, test tự đặt)."""
import json, os, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="xv-test-")
os.environ.setdefault("XUONG_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import hoc_canh as hc  # noqa: E402
import kiem_mo_ta as km  # noqa: E402


def _kho(n=1):
    kho = Path(tempfile.mkdtemp(prefix="kho-", dir=TMP))
    for i in range(n):
        (kho / f"v{i}.mp4").write_bytes(b"x")
    return kho


class HocCanhTest(unittest.TestCase):
    def setUp(self):
        hc.JOB.update(dang_chay=False, dung=False, dang_dung=False, canh_bao="", trang_thai="nghi")
        self._chn = km.chuan_hoa_noi_dung
        km.chuan_hoa_noi_dung = lambda text, dai, rel: ({"a": 1}, [], [])       # bỏ kiểm định dạng: chỉ thử luồng

    def tearDown(self):
        km.chuan_hoa_noi_dung = self._chn

    # ---- dừng thật
    def test_chay_lo_dung_huy_cuoc_va_don_file(self):
        huy = threading.Event(); da_huy = []; ra = Path(_kho()) / "_tam" / "o.json"

        def gui(model, prompt, td):
            return "cid-1"
        threading.Timer(0.3, huy.set).start()
        t = time.time()
        xong = hc.chay_lo("flash", "p", [ra], "t", lambda *a: self.fail("không được ghi sau Dừng"), gui=gui, huy=huy, huy_cuoc=da_huy.append)
        self.assertLess(time.time() - t, 2.5)
        self.assertEqual(xong, []); self.assertEqual(da_huy, ["cid-1"]); self.assertFalse(ra.exists())

    def test_hoc_kho_dung_giua_chung_roi_hoc_lai(self):
        kho = _kho(2); huy_goi = []
        bat_dau = threading.Event()
        orig = hc.huy_cuoc_tro_chuyen
        hc.huy_cuoc_tro_chuyen = huy_goi.append

        def gui(model, prompt, td, project=None):
            bat_dau.set(); return "cid-x"
        runner = lambda *a, **k: hc.chay_lo(*a, gui=gui, **k)
        try:
            kq = {}
            th = threading.Thread(target=lambda: kq.update(hc.hoc_kho(str(kho), runner=runner, do_dai=lambda p: 5.0, kiem_mo=lambda: True,
                                                                         project=False, ten="t")))
            th.start(); self.assertTrue(bat_dau.wait(10))
            t = time.time(); self.assertTrue(hc.dung()["dang_dung"])
            self.assertTrue(hc.JOB["dang_dung"])
            th.join(8); self.assertFalse(th.is_alive()); self.assertLess(time.time() - t, 5)
            self.assertFalse(hc.JOB["dang_chay"]); self.assertEqual(hc.JOB["trang_thai"], "dung"); self.assertIn("cid-x", huy_goi)
            self.assertFalse(list((kho / "_mo-ta").rglob("*.mo-ta.json")) if (kho / "_mo-ta").exists() else [])   # không để lại kết quả dở
            self.assertFalse((kho / "_tam" / "hoc-canh").exists())
        finally:
            hc.huy_cuoc_tro_chuyen = orig
        # video đã dừng học lại được
        def gui2(model, prompt, td, project=None):
            for f in (kho / "_tam" / "hoc-canh").parent.rglob("*"):
                pass
            import re
            for m in re.finditer(r"GHI JSON vào file: '([^']+)'", prompt):
                Path(m.group(1)).write_text("{}", encoding="utf-8")
            return "cid-y"
        hc.CHU_KY_S, ck = 0.05, hc.CHU_KY_S
        try:
            r = hc.hoc_kho(str(kho), runner=lambda *a, **k: hc.chay_lo(*a, gui=gui2, ngu=lambda s: time.sleep(0.05), **k),
                           do_dai=lambda p: 5.0, kiem_mo=lambda: True, project=False, ten="t")
        finally:
            hc.CHU_KY_S = ck
        self.assertEqual(r["da_hoc"], 2, r)

    # ---- làn riêng: không chặn sản xuất; đang sản xuất thì nhường (1 lô một lúc)
    def test_nhuong_may_khi_dang_san_xuat(self):
        kho = _kho(4); dang = {"n": 0, "max": 0}; kl = threading.Lock()

        def runner(model, prompt, outs, td, khi_co, **k):
            with kl:
                dang["n"] += 1; dang["max"] = max(dang["max"], dang["n"])
            time.sleep(0.3)
            with kl:
                dang["n"] -= 1
            return list(outs)
        old = hc.doc_cau_hinh
        hc.doc_cau_hinh = lambda: {"lo": 1}
        try:
            r = hc.hoc_kho(str(kho), runner=runner, do_dai=lambda p: 5.0, kiem_mo=lambda: True, project=False, ten="t", song_song=2, ban_san_xuat=lambda: True)
        finally:
            hc.doc_cau_hinh = old
        self.assertEqual(dang["max"], 1)
        self.assertNotEqual(hc.JOB["trang_thai"], "loi")

    def test_khong_nhuong_khi_ranh(self):
        kho = _kho(4); dang = {"n": 0, "max": 0}; kl = threading.Lock()

        def runner(model, prompt, outs, td, khi_co, **k):
            with kl:
                dang["n"] += 1; dang["max"] = max(dang["max"], dang["n"])
            time.sleep(0.3)
            with kl:
                dang["n"] -= 1
            return list(outs)
        old = hc.doc_cau_hinh
        hc.doc_cau_hinh = lambda: {"lo": 1}
        try:
            hc.hoc_kho(str(kho), runner=runner, do_dai=lambda p: 5.0, kiem_mo=lambda: True, project=False, ten="t", song_song=2)
        finally:
            hc.doc_cau_hinh = old
        self.assertEqual(dang["max"], 2)

    # ---- tự duyệt: Project riêng chỉ cho thư mục kho
    def test_thiet_lap_quyen(self):
        d = Path(tempfile.mkdtemp(dir=TMP)); khac = d / "khac.json"; khac.write_text("giu-nguyen")
        old = hc.PROJECT_DIR; hc.PROJECT_DIR = d
        try:
            kho = _kho()
            self.assertFalse(hc.trang_thai_quyen(kho)["ok"])
            r = hc.thiet_lap_quyen(kho); self.assertTrue(r["ok"], r)
            self.assertTrue(hc.trang_thai_quyen(kho)["ok"])
            j = json.loads((d / (r["id"] + ".json")).read_text(encoding="utf-8"))
            self.assertEqual(j["settings"]["permissionPreset"], "AGENT_PERMISSION_PRESET_TURBO")
            self.assertEqual(len(j["projectResources"]["resources"]), 1)
            self.assertTrue(j["projectResources"]["resources"][0]["folderUri"].startswith("file:///"))
            self.assertEqual(hc.thiet_lap_quyen(kho)["id"], r["id"])                 # lặp lại: cùng id
            self.assertEqual(khac.read_text(), "giu-nguyen"); self.assertEqual(len(list(d.glob("*.json"))), 2)
            old_c = hc.doc_cau_hinh; hc.doc_cau_hinh = lambda: {}
            try:
                self.assertEqual(hc.tim_project(kho), r["id"])
            finally:
                hc.doc_cau_hinh = old_c
        finally:
            hc.PROJECT_DIR = old

    @unittest.skipUnless(os.name == "nt", "taskkill chỉ có ở Windows")
    def test_giet_cay_tien_trinh(self):
        code = "import subprocess,sys,time;c=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);print(c.pid,flush=True);time.sleep(60)"
        p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        con = int(p.stdout.readline())
        t = time.time(); hc._giet_cay(p.pid)
        self.assertLess(time.time() - t, 5); self.assertIsNotNone(p.wait(5))
        time.sleep(0.5); self.assertFalse(hc._song(con))


if __name__ == "__main__":
    unittest.main()
