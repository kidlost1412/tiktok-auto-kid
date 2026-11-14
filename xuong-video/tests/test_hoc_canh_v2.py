"""Học cảnh kiểu 2 (máy đo, AI điền phiếu): kiểm phiếu, điểm đẹp do máy tính, mô tả kiểu 2 qua kiem_mo_ta/kho_canh, vòng học với runner GIẢ
(đủ phiếu / 1 cảnh sai hỏi lại / dừng giữa chừng / học lại), khôi phục sau khởi động lại, nhận Antigravity không bị PID cũ đánh lừa, máy cắt cảnh.
Không gọi Antigravity thật. Chạy:  python -m unittest discover -s xuong-video/tests -v"""
import json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp(prefix="xv-v2-")
os.environ.setdefault("XUONG_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hoc_canh as hc  # noqa: E402
import kiem_mo_ta as km  # noqa: E402
import phieu as ph  # noqa: E402
import _gia_phieu as gia  # noqa: E402


def _tmp():
    return Path(tempfile.mkdtemp(prefix="t-", dir=TMP))


def _canh(**k):
    c = {"so": 1, "loai": "ket_qua", "co_canh": "trung", "mat": 0, "chu_chen": 0, "hang_khac": False, "nhan_doc": "", "nhan": None, "loi": "", "ta": "Tay vạch tán lá", "dang_noi_ve": ""}
    c.update(k)
    return c


def _form(canh, video=None):
    return {"video": video or [{"thu_tu": 1, "nghe_duoc": True, "tom_tat": "Tóm tắt", "cay_trong": "ớt", "loi_hay": ["Câu hay."]}], "canh": canh}


class KiemPhieuTest(unittest.TestCase):
    def test_hop_le(self):
        ok, loi = ph.kiem_phieu(_form([_canh(so=1), _canh(so=2, loai="chai_ro", co_canh="can", mat=2, nhan_doc="Nano Đồng", nhan=[0.2, 0.2, 0.6, 0.8])]), 1, [1, 2])
        self.assertEqual(loi, []); self.assertEqual(sorted(ok), [1, 2])
        self.assertEqual(ok[2]["loai"], "chai_ro"); self.assertEqual(ok[2]["nhan_doc"], "Nano Đồng"); self.assertEqual(ok[1]["loi"], "")

    def test_moi_kieu_sai(self):
        sai = {"loai la": _canh(loai="bay_la"), "co_canh la": _canh(co_canh="xa"), "mat 3": _canh(mat=3), "mat chu": _canh(mat="nhieu"), "chu_chen 5": _canh(chu_chen=5),
               "hang_khac la": _canh(hang_khac="co le"), "nhan 3 so": _canh(nhan=[0.1, 0.2, 0.3]), "nhan ngoai khoang": _canh(nhan=[0.1, 0.2, 1.4, 0.9]),
               "nhan nguoc x": _canh(nhan=[0.6, 0.2, 0.3, 0.9]), "nhan nguoc y": _canh(nhan=[0.1, 0.9, 0.5, 0.2]), "nhan chu": _canh(nhan=["a", "b", "c", "d"]),
               "ta rong": _canh(ta="  "), "mat bool": _canh(mat=True)}
        for ten, c in sai.items():
            ok, loi = ph.kiem_phieu(_form([c]), 1, [1])
            self.assertEqual(ok, {}, ten); self.assertEqual([n for n, _ in loi], [1], ten); self.assertTrue(loi[0][1], ten)

    def test_thieu_canh_va_phieu_hong(self):
        ok, loi = ph.kiem_phieu(_form([_canh(so=1)]), 1, [1, 2, 3])
        self.assertEqual(sorted(ok), [1]); self.assertEqual([n for n, _ in loi], [2, 3]); self.assertIn("thiếu", loi[0][1])
        ok, loi = ph.kiem_phieu("không phải json", 1, [1, 2])
        self.assertEqual(ok, {}); self.assertEqual([n for n, _ in loi], [1, 2])
        ok, loi = ph.kiem_phieu({"video": []}, 1, [1])
        self.assertEqual(ok, {}); self.assertEqual(len(loi), 1)

    def test_doc_de_tinh(self):
        txt = "Đây là kết quả:\n```json\n" + json.dumps(_form([_canh(so="1", mat="2", chu_chen=1.0, hang_khac="false", dep=1, them="x", nhan="null"),
                                                              _canh(so=2.0, hang_khac="true", nhan="[0.1,0.2,0.5,0.6]")]), ensure_ascii=False) + "\n```\nXong."
        ok, loi = ph.kiem_phieu(txt, 1, [1, 2])
        self.assertEqual(loi, [], loi)
        self.assertEqual((ok[1]["mat"], ok[1]["chu_chen"], ok[1]["hang_khac"], ok[1]["nhan"]), (2, 1, False, None))
        self.assertTrue(ok[2]["hang_khac"]); self.assertEqual(len(ok[2]["nhan"]), 4)
        self.assertNotIn("dep", ok[1]); self.assertNotIn("them", ok[1])                       # trường thừa bỏ qua; AI không chấm điểm
        c = _canh(); del c["loi"], c["dang_noi_ve"], c["nhan"], c["nhan_doc"]                   # trường phụ vắng mặt → mặc định
        ok, loi = ph.kiem_phieu(_form([c]), 1, [1])
        self.assertEqual(loi, []); self.assertEqual((ok[1]["loi"], ok[1]["nhan"]), ("", None))
        ok, loi = ph.kiem_phieu([_canh(so=1)], 1, [1])                                          # mảng trần cũng nhận
        self.assertEqual(loi, [])

    def test_nho_khung_nhan_va_cat_chu(self):
        ok, _ = ph.kiem_phieu(_form([_canh(nhan=[0.2, 0.3, 0.6, 0.7])]), 1, [1])
        x0, y0, x1, y1 = ok[1]["nhan"]
        self.assertEqual((x0, y0, x1, y1), (0.176, 0.276, 0.624, 0.724))                      # nới 6% cạnh khung mỗi phía
        ok, _ = ph.kiem_phieu(_form([_canh(nhan=[0.0, 0.0, 1.0, 1.0])]), 1, [1])
        self.assertEqual(ok[1]["nhan"], [0.0, 0.0, 1.0, 1.0])                                  # kẹp trong 0–1
        ok, _ = ph.kiem_phieu(_form([_canh(nhan=[0.0, 0.54, 0.07, 0.61])]), 1, [1])
        self.assertEqual(ok[1]["nhan"][0], 0.0); self.assertGreater(ok[1]["nhan"][2], 0.07)
        ok, _ = ph.kiem_phieu(_form([_canh(ta="a" * 300, dang_noi_ve="b" * 200, loi="c" * 200, nhan_doc="d" * 200)]), 1, [1])
        self.assertEqual((len(ok[1]["ta"]), len(ok[1]["dang_noi_ve"]), len(ok[1]["loi"])), (120, 80, 60))
        v = ph.doc_phieu_video(_form([_canh()], [{"thu_tu": 1, "nghe_duoc": "true", "tom_tat": "t", "cay_trong": "ớt", "loi_hay": ["x" * 400, "y", "z"]}]), 2)
        self.assertEqual(len(v[1]["loi_hay"]), 2); self.assertEqual(len(v[1]["loi_hay"][0]), 220); self.assertTrue(v[1]["nghe_duoc"])
        self.assertEqual(v[2], {"nghe_duoc": False, "tom_tat": "", "cay_trong": "", "loi_hay": []})      # video thiếu → mặc định, không ném lỗi

    def test_cay_tu_chu(self):
        self.assertEqual(ph.cay_tu_chu("ớt"), ["ot"]); self.assertEqual(ph.cay_tu_chu("Cà phê, hồ tiêu"), ["ca_phe", "ho_tieu"])
        self.assertEqual(ph.cay_tu_chu(""), ["khong_ro"]); self.assertEqual(ph.cay_tu_chu("lúa nước"), ["cay_khac"])
        self.assertEqual(ph.cay_tu_chu("hot"), ["cay_khac"])                                   # "ot" trong "hot" không tính


class DepMayTest(unittest.TestCase):
    def test_bang_diem(self):
        d = ph.dep_may
        self.assertEqual(d(1.0, "em"), 5); self.assertEqual(d(1.5, "em"), 5)
        self.assertEqual(d(1.2, "rung"), 5)                      # độ rung không tính vào điểm
        self.assertEqual(d(0.7, "em"), 4); self.assertEqual(d(0.69, "em"), 3); self.assertEqual(d(0.4, "em"), 3)
        self.assertEqual(d(0.39, "em"), 2)
        self.assertEqual(d(1.5, "em", "rung"), 3)               # có khuyết điểm → tối đa 3 dù nét
        self.assertEqual(d(0.8, "em", "  "), 4)                  # khuyết điểm toàn khoảng trắng = không có
        self.assertEqual(d(1.5, "em", "", 2), 1); self.assertEqual(d(1.5, "em", "", 0, True), 1)       # 1 chỉ khi chữ chèn nhiều / hàng khác
        self.assertEqual(d(0.1, "rung", "mờ"), 2)
        for net in (0.0, 0.3, 0.5, 0.9, 1.2, 3.0):
            for cd in ("em", "rung"):
                for loi in ("", "x"):
                    self.assertGreaterEqual(d(net, cd, loi), 2)


def _mo_ta_mau(rel="v0.mp4", dai=40.0, canh=None, **thong_tin):
    may = [{"tu": 2.0, "den": 6.0, "net": 1.2, "chuyen_dong": "em"}, {"tu": 8.5, "den": 12.5, "net": 0.5, "chuyen_dong": "rung"},
           {"tu": 20.0, "den": 24.0, "net": 0.9, "chuyen_dong": "em"}, {"tu": 30.0, "den": 34.0, "net": 1.1, "chuyen_dong": "em"}]
    canh = canh or [_canh(so=1, loai="chai_ro", co_canh="can", nhan_doc="Nano Đồng", nhan=[0.2, 0.2, 0.6, 0.8], ta="Tay cầm chai Nano Đồng xoay mặt trước"),
                    _canh(so=2, loai="nguoi_noi", co_canh="trung", mat=2, ta="Anh nông dân nhìn máy nói chuyện", dang_noi_ve="bọ trĩ làm xoăn đọt ớt"),
                    _canh(so=3, loai="phun_tuoi", co_canh="toan", loi="rung", ta="Phun thuốc lên luống ớt", chu_chen=1),
                    _canh(so=4, loai="kho_hang", co_canh="toan", hang_khac=True, nhan_doc="NANO LÂN", nhan=[0.1, 0.1, 0.9, 0.9], ta="Kệ hàng nhiều chai khác")]
    ok, loi = ph.kiem_phieu(_form(canh), 1, [c["so"] for c in canh])
    assert not loi, loi
    tt = dict({"nghe_duoc": True, "tom_tat": "Anh Nguyên giới thiệu Nano Đồng ở vườn cà phê", "cay_trong": "cà phê", "loi_hay": ["Câu hay một."]}, **thong_tin)
    return ph.mo_ta_tu_phieu(rel, dai, may[:len(canh)], [ok[c["so"]] for c in canh], tt, "gemini-4-hydrogen-high", "2026-11-14T10:00:00")


class MoTaKieu2Test(unittest.TestCase):
    def test_noi_dung_mo_ta(self):
        d = _mo_ta_mau()
        self.assertEqual((d["kieu"], d["model"], d["hoc_luc"], d["nghe_duoc"]), (2, "gemini-4-hydrogen-high", "2026-11-14T10:00:00", True))
        self.assertEqual(d["cay_trong"], ["ca_phe"]); self.assertEqual(d["loi_hay"], ["Câu hay một."]); self.assertEqual(d["loi_noi_tom_tat"], d["tom_tat"])
        c = d["canh_quay"]
        self.assertEqual((c[0]["tu_s"], c[0]["den_s"], c[0]["khung_dep_nhat"]), (2.0, 6.0, [2.0, 6.0]))
        self.assertEqual((c[0]["co_canh"], c[0]["may_quay"], c[0]["san_pham"], c[0]["chu_chen_san"], c[0]["diem"], c[0]["chac_chan"]),
                         ("can_canh", "dung_yen", "doc_ro: Nano Đồng", "khong", 5, "cao"))
        self.assertEqual(c[0]["hinh"], "Tay cầm chai Nano Đồng xoay mặt trước"); self.assertIn("cam_chai", c[0]["the"]); self.assertIn("nhan_doc_ro", c[0]["the"])
        self.assertEqual(c[1]["may_quay"], "rung_tay"); self.assertEqual(c[1]["the"], ["nguoi_noi_vao_may"]); self.assertEqual(c[1]["san_pham"], "khong_co")
        self.assertEqual((c[2]["chu_chen_san"], c[2]["diem"]), ("co", 3))                       # có lỗi "rung" → tối đa 3
        self.assertEqual(c[3]["diem"], 1)                                                       # hàng khác → 1
        self.assertEqual(sorted(c[0]["phieu"]), sorted(["loai", "mat", "chu_chen", "hang_khac", "nhan", "loi", "dang_noi_ve", "net", "chuyen_dong"]))
        self.assertEqual([(s["ten_tren_nhan"], s["la_san_pham_khac"]) for s in d["san_pham_thay"]], [("Nano Đồng", False), ("NANO LÂN", True)])
        d2 = _mo_ta_mau(nghe_duoc=False)
        self.assertEqual(d2["loi_noi_tom_tat"], "không nghe được")
        d3 = _mo_ta_mau(loi_hay=[], tom_tat="Anh giới thiệu",)
        self.assertNotEqual(d3["loi_noi_tom_tat"], "không nghe được")
        d4 = _mo_ta_mau(canh=[_canh(so=1), _canh(so=2)], loi_hay=[])
        self.assertEqual(d4["loi_noi_tom_tat"], "không có lời")                                 # nghe được nhưng không ai nói
        d5 = _mo_ta_mau(canh=[_canh(so=1, nhan=[0.1, 0.1, 0.5, 0.5])])
        self.assertEqual(d5["canh_quay"][0]["san_pham"], "thay_khong_doc_ro")

    def test_kiem_mo_ta_khong_sua_kieu_2(self):
        d = _mo_ta_mau()
        obj, ghi, cb = km.chuan_hoa_noi_dung(json.loads(json.dumps(d)), 40.0, "v0.mp4", la_obj=True)
        self.assertEqual(obj, d, ghi)
        for k in ("kieu", "model", "hoc_luc", "loi_hay", "nghe_duoc"):
            self.assertEqual(obj[k], d[k])
        self.assertTrue(all("phieu" in c for c in obj["canh_quay"]))
        # cả kho: kiem_kho --sua phải thấy "đúng sẵn", không ghi lại file, không tạo _goc-kiem
        kho = _tmp(); (kho / "v0.mp4").write_bytes(b"x")
        mt = kho / "_mo-ta" / "v0.mp4.mo-ta.json"; mt.parent.mkdir()
        mt.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        truoc = mt.read_bytes()
        rep = km.kiem_kho(kho, sua=True, do_dai=lambda p: self.fail("không cần đo lại độ dài"))
        self.assertEqual((rep["da_dung"], rep["da_sua"], rep["hong"], rep["thieu_mo_ta"]), (1, [], [], []))
        self.assertEqual(mt.read_bytes(), truoc); self.assertFalse((mt.parent / "_goc-kiem").exists())


class KhoCanhKieu2Test(unittest.TestCase):
    def setUp(self):
        import kho_canh as kc
        self.kc = kc
        self.hub = _tmp(); self.kho = _tmp(); self._hub = kc.HUB; kc.HUB = self.hub
        (self.hub / "san-pham" / "t1").mkdir(parents=True)
        (self.hub / "san-pham" / "t1" / "san-pham.json").write_text(json.dumps({"kho_video": str(self.kho), "ten_goi": "Thử"}), encoding="utf-8")
        for r in ("v0.mp4", "v1.mp4"):
            (self.kho / r).write_bytes(b"x")
        (self.kho / "_mo-ta").mkdir()

    def tearDown(self):
        self.kc.HUB = self._hub

    def _ghi(self, rel, obj):
        km.ghi_mo_ta(self.kho / "_mo-ta" / (rel + ".mo-ta.json"), obj)

    def test_vai_tro_va_soat_tu_phieu(self):
        self._ghi("v0.mp4", _mo_ta_mau("v0.mp4"))
        shots, _ = self.kc.nap("t1")
        theo = {round(s["tu"], 1): s for s in shots}
        self.assertEqual(sorted(theo), [2.0, 8.5, 20.0])                       # cảnh hàng khác (30s) bị bỏ như kiểu cũ
        chai, noi, phun = theo[2.0], theo[8.5], theo[20.0]
        self.assertIn("chai_ro", chai["vai_tro"]); self.assertEqual(chai["co_canh"], "can_canh"); self.assertEqual(chai["loai"], "chai_ro")
        self.assertEqual(chai["soat"], {"mat": 0, "chu_muc": 0, "hang_khac": False, "dep": 5, "nhan": chai["soat"]["nhan"], "ghi": "Tay cầm chai Nano Đồng xoay mặt trước"})
        self.assertEqual(len(chai["soat"]["nhan"]), 4)
        self.assertIn("phun", phun["vai_tro"]); self.assertEqual(phun["soat"]["chu_muc"], 1); self.assertEqual(phun["soat"]["dep"], 3)
        self.assertEqual(noi["noi"], "bọ trĩ làm xoăn đọt ớt"); self.assertTrue(noi["noi_ghi"]); self.assertEqual(noi["soat"]["mat"], 2)
        import soat_kho
        self.assertTrue(soat_kho.nguoi_noi(noi)); self.assertFalse(soat_kho.nguoi_noi(chai))
        self.assertEqual(noi["vai_tro"], [])                                    # loại nguoi_noi → không vai trò riêng
        self.assertTrue(all(s["kieu"] == 2 for s in shots))
        # soat_kho chỉ soát cảnh CHƯA có soat → không còn gì để soát
        can = [s["id"] for s in shots if "soat" not in s]
        self.assertEqual(can, [])

    def test_mat_2_hoac_loai_nguoi_noi_la_nguoi_noi(self):
        canh = [_canh(so=1, loai="nguoi_noi", mat=1), _canh(so=2, loai="ket_qua", mat=2), _canh(so=3, loai="ket_qua", mat=0)]
        self._ghi("v0.mp4", _mo_ta_mau("v0.mp4", canh=canh))
        shots, _ = self.kc.nap("t1")
        import soat_kho
        self.assertEqual([soat_kho.nguoi_noi(s) for s in sorted(shots, key=lambda s: s["tu"])], [True, True, False])
        self.assertEqual([s["noi_ghi"] for s in sorted(shots, key=lambda s: s["tu"])], [True, True, False])

    def test_hoc_lai_thay_canh_cu_va_cap_id_moi(self):
        cu = {"video": "v1.mp4", "thoi_luong_s": 40.0, "tom_tat": "x", "nguoi": "", "boi_canh": "", "cay_trong": ["ot"], "loi_noi_tom_tat": "", "san_pham_thay": [],
              "canh_quay": [{"tu_s": 3.0, "den_s": 8.0, "khung_dep_nhat": [3.0, 7.0], "hinh": "cảnh cũ cầm chai", "co_canh": "trung", "may_quay": "dung_yen",
                             "san_pham": "khong_co", "chu_chen_san": "khong", "the": ["cam_chai"], "diem": 4, "chac_chan": "cao"}], "van_de": [], "dung_lam_bang_chung": True}
        self._ghi("v1.mp4", cu)
        s1, _ = self.kc.nap("t1")
        self.assertEqual([s["id"] for s in s1], ["0000"]); self.assertNotIn("kieu", s1[0])
        # học lại kiểu 2: mô tả mới ghi đè
        self._ghi("v1.mp4", _mo_ta_mau("v1.mp4"))
        s2, _ = self.kc.nap("t1")
        self.assertTrue(all(s["kieu"] == 2 for s in s2), "cảnh kiểu cũ của video đã học lại phải bị thay")
        self.assertFalse(any(s["mo_ta"] == "cảnh cũ cầm chai" for s in s2))
        self.assertEqual(sorted(s["id"] for s in s2), ["0001", "0002", "0003"])        # id mới nối tiếp, id cũ 0000 không dùng lại
        s3, _ = self.kc.nap("t1")                                                      # chạy lại: id ổn định
        self.assertEqual(sorted((s["id"], s["tu"]) for s in s3), sorted((s["id"], s["tu"]) for s in s2))


class HocKhoV2Test(unittest.TestCase):
    def setUp(self):
        self.hub = _tmp(); self._ls, self._hub = hc.LS, hc.HUB; hc.LS = self.hub / "lich-su"; hc.HUB = self.hub
        hc.JOB.update(dang_chay=False, dung=False, dang_dung=False, canh_bao="", trang_thai="nghi", thong_bao="", loi=[], xong=0, tong=0)
        self.kho = _tmp()
        self._cfg = hc.doc_cau_hinh; hc.doc_cau_hinh = lambda: {}
        self._ck, hc.CHU_KY_S = hc.CHU_KY_S, 0.02
        for ten, gt in (("_goi_ls", lambda *a, **k: None), ("_agy_exe_chay", lambda: False)):      # không bao giờ chạm Antigravity / tiến trình thật
            p = mock.patch.object(hc, ten, gt); p.start(); self.addCleanup(p.stop)

    def tearDown(self):
        hc.LS, hc.HUB = self._ls, self._hub; hc.doc_cau_hinh = self._cfg; hc.CHU_KY_S = self._ck

    def _videos(self, n):
        for i in range(n):
            (self.kho / f"v{i}.mp4").write_bytes(b"x")

    def _chay(self, runner, cat=None, **kw):
        a = dict(runner=runner, do_dai=lambda p: 40.0, kiem_mo=lambda: True, project=False, ten="t", cat=cat or gia.cat_gia(3), to_anh=gia.to_anh_gia)
        a.update(kw)
        return hc.hoc_kho(str(self.kho), **a)

    def _mo_ta(self, rel):
        return json.loads((self.kho / "_mo-ta" / f"{rel}.mo-ta.json").read_text(encoding="utf-8"))

    def test_duong_di_tot(self):
        self._videos(2); log = []
        r = self._chay(gia.runner_gia(log))
        self.assertEqual((r["da_hoc"], r["canh"], r["loi"], r["tat_ca_xong"]), (2, 6, [], True), r)
        self.assertEqual(len(log), 1)                                                   # 2 video × 3 cảnh = 1 lô
        self.assertEqual(log[0]["model"], "gemini-4-hydrogen-high")
        self.assertEqual(log[0]["kw"]["han"], 150 * 2 + 60)
        self.assertIn("Có 2 video", log[0]["prompt"]); self.assertIn("đánh số 1 đến 6", log[0]["prompt"]); self.assertIn("cảnh 6: từ giây", log[0]["prompt"])
        self.assertIn("to-1.jpg", log[0]["prompt"]); self.assertIn("phieu.json", log[0]["prompt"])
        d = self._mo_ta("v0.mp4")
        self.assertEqual((d["kieu"], d["model"], len(d["canh_quay"])), (2, "gemini-4-hydrogen-high", 3))
        self.assertEqual(d["canh_quay"][0]["hinh"], "Cảnh số 1 tay vạch tán lá xanh"); self.assertEqual(d["canh_quay"][0]["diem"], 5)
        self.assertEqual(self._mo_ta("v1.mp4")["canh_quay"][0]["hinh"], "Cảnh số 4 tay vạch tán lá xanh")          # số cảnh đánh liên tục trong lô
        self.assertEqual(d["cay_trong"], ["ot"]); self.assertEqual(d["loi_hay"], ["Câu hay số một."])
        self.assertEqual(hc.JOB["trang_thai"], "xong"); self.assertEqual(hc.JOB["thong_bao"], "Học xong 2 video (6 cảnh).")
        self.assertEqual((hc.JOB["giai_doan"], hc.JOB["model"], hc.JOB["canh_tong"], hc.JOB["xong"], hc.JOB["tong"]), ("", "gemini-4-hydrogen-high", 6, 2, 2))
        self.assertFalse((self.kho / "_tam" / "hoc-canh").exists())
        tt = json.loads((hc.LS / "hoc-canh-job.json").read_text(encoding="utf-8"))
        self.assertFalse(tt["job"]["dang_chay"]); self.assertEqual(tt["conv"], [])
        rep = km.kiem_kho(self.kho, sua=False, do_dai=lambda p: 40.0)
        self.assertEqual((rep["da_dung"], rep["da_sua"], rep["thieu_mo_ta"]), (2, [], []))
        r2 = self._chay(gia.runner_gia(log))                                           # chạy lại: không còn gì để học
        self.assertEqual((r2["da_hoc"], len(log)), (0, 1)); self.assertEqual(hc.JOB["thong_bao"], "Kho đã đủ mô tả.")

    def test_chia_lo_theo_video_va_canh(self):
        self._videos(7); log = []
        self._chay(gia.runner_gia(log), song_song=1)
        self.assertEqual([int(re.search(r"Có (\d+) video", x["prompt"]).group(1)) for x in log], [5, 2])           # ≤ 5 video/lô
        shutil.rmtree(self.kho / "_mo-ta"); log.clear()
        self._chay(gia.runner_gia(log), cat=gia.cat_gia(10), song_song=1)                  # 7 video × 10 cảnh: ≤ 24 cảnh/lô → 2 video/lô
        self.assertEqual([int(re.search(r"Có (\d+) video", x["prompt"]).group(1)) for x in log], [2, 2, 2, 1])
        self.assertTrue(all(int(re.search(r"đánh số 1 đến (\d+)", x["prompt"]).group(1)) <= 24 for x in log))
        # video cắt ra 30 cảnh → chỉ lấy 24 rải đều
        shutil.rmtree(self.kho / "_mo-ta"); log.clear()
        for i in range(1, 7):
            (self.kho / f"v{i}.mp4").unlink()
        self._chay(gia.runner_gia(log), cat=gia.cat_gia(30))
        self.assertEqual(len(self._mo_ta("v0.mp4")["canh_quay"]), 24); self.assertEqual(len(log), 1)

    def test_mot_canh_sai_duoc_hoi_lai_1_lan(self):
        self._videos(2); log = []
        r = self._chay(gia.runner_gia(log, hong_theo_lan={1: {2}}))                    # lần 1 sai cảnh số 2 (video 1)
        self.assertEqual(len(log), 2, [x["tieu_de"] for x in log])
        self.assertIn("Có 1 video", log[1]["prompt"]); self.assertIn("đánh số 1 đến 1", log[1]["prompt"]); self.assertIn("làm lại", log[1]["tieu_de"])
        self.assertIn("v0.mp4", log[1]["prompt"]); self.assertNotIn("v1.mp4", log[1]["prompt"])
        self.assertEqual((r["da_hoc"], r["canh"], r["loi"]), (2, 6, []))
        self.assertEqual(len(self._mo_ta("v0.mp4")["canh_quay"]), 3)
        self.assertEqual(hc.JOB["loi"], [])

    def test_van_sai_sau_khi_hoi_lai_giu_canh_dung(self):
        self._videos(2); log = []
        r = self._chay(gia.runner_gia(log, hong_theo_lan={1: {2}, 2: {1}}))            # lần hỏi lại vẫn sai
        self.assertEqual(len(log), 2)
        self.assertEqual(len(self._mo_ta("v0.mp4")["canh_quay"]), 2)                    # giữ 2 cảnh đúng
        self.assertEqual(len(self._mo_ta("v1.mp4")["canh_quay"]), 3)
        self.assertEqual(r["loi"], ["v0.mp4"]); self.assertEqual(len(hc.JOB["loi"]), 1)
        self.assertIn("2/3 cảnh", hc.JOB["loi"][0]["loi"]); self.assertIn("loai", hc.JOB["loi"][0]["loi"])
        self.assertIn("1 video có lỗi", hc.JOB["thong_bao"])

    def test_khong_co_phieu_2_lo_lien_thi_dung(self):
        self._videos(3); log = []

        def runner(model, prompt, outs, td, khi_co, **kw):
            log.append(1); return []                                                   # Antigravity không ghi gì
        with mock.patch.object(hc, "doc_cau_hinh", lambda: {"lo": 1}):
            r = self._chay(runner, song_song=1)
        self.assertEqual(len(log), 2); self.assertEqual(hc.JOB["trang_thai"], "het_luot"); self.assertFalse(r["tat_ca_xong"])
        self.assertIn("Đã học 0 video (giữ nguyên), còn 3 video chưa học.", hc.JOB["thong_bao"])
        self.assertFalse(list((self.kho / "_mo-ta").rglob("*.mo-ta.json")) if (self.kho / "_mo-ta").exists() else [])

    def test_video_qua_ngan(self):
        self._videos(2); log = []
        cat = lambda p: {"dai": 1.0, "vet_cat": [], "canh": []} if p.endswith("v0.mp4") else gia.cat_gia(2)(p)
        r = self._chay(gia.runner_gia(log), cat=cat)
        self.assertEqual((r["da_hoc"], r["loi"]), (1, ["v0.mp4"]))
        self.assertEqual(hc.JOB["loi"][0]["loi"], "Video quá ngắn hoặc không đọc được")
        self.assertEqual(hc.JOB["xong"], 2); self.assertIn("Có 1 video", log[0]["prompt"])

    def test_dung_giua_chung_giu_video_da_hoc(self):
        self._videos(2); log = []
        def truoc(lan, prompt):
            if lan == 2:
                self.assertTrue(hc.dung()["dang_dung"]); return False
        huy_goi = []
        with mock.patch.object(hc, "doc_cau_hinh", lambda: {"lo": 1}), mock.patch.object(hc, "huy_cuoc_tro_chuyen", huy_goi.append):
            r = self._chay(gia.runner_gia(log, truoc=truoc), song_song=1)
        self.assertEqual(len(log), 2); self.assertFalse(r["tat_ca_xong"])
        self.assertEqual(hc.JOB["trang_thai"], "dung"); self.assertEqual(hc.JOB["thong_bao"], "Đã dừng. Đã học 1 video (giữ nguyên), còn 1 video chưa học.")
        self.assertTrue((self.kho / "_mo-ta" / "v0.mp4.mo-ta.json").exists()); self.assertFalse((self.kho / "_mo-ta" / "v1.mp4.mo-ta.json").exists())
        self.assertFalse((self.kho / "_tam" / "hoc-canh").exists()); self.assertFalse(hc.JOB["dang_chay"])
        # bấm Học cảnh lại: chỉ học video còn lại
        log2 = []
        r2 = self._chay(gia.runner_gia(log2))
        self.assertEqual(r2["da_hoc"], 1); self.assertNotIn("v0.mp4", log2[0]["prompt"]); self.assertIn("v1.mp4", log2[0]["prompt"])

    def test_dung_that_khi_dang_cho_runner_chay_lo(self):
        """Dừng khi chay_lo đang chờ file: huỷ cuộc trò chuyện, không để lại file, JOB 'dung' (luồng cũ vẫn đúng với phiếu)."""
        self._videos(1); bat_dau = threading.Event(); huy_goi = []

        def gui(model, prompt, td, project=None):
            bat_dau.set(); return "cid-x"
        runner = lambda *a, **k: hc.chay_lo(*a, gui=gui, **k)
        kq = {}
        with mock.patch.object(hc, "huy_cuoc_tro_chuyen", huy_goi.append):
            th = threading.Thread(target=lambda: kq.update(self._chay(runner)))
            th.start(); self.assertTrue(bat_dau.wait(10))
            self.assertTrue(hc.dung()["dang_dung"]); th.join(8)
        self.assertFalse(th.is_alive()); self.assertIn("cid-x", huy_goi)
        self.assertEqual(hc.JOB["trang_thai"], "dung"); self.assertTrue(hc.JOB["thong_bao"].startswith("Đã dừng. Đã học 0 video"))
        self.assertFalse((self.kho / "_tam" / "hoc-canh").exists())

    def test_hoc_lai_kieu_cu(self):
        self._videos(2); log = []
        cu = {"video": "v0.mp4", "thoi_luong_s": 40.0, "tom_tat": "mô tả cũ", "nguoi": "", "boi_canh": "", "cay_trong": ["ot"], "loi_noi_tom_tat": "", "san_pham_thay": [],
              "canh_quay": [{"tu_s": 3.0, "den_s": 8.0, "khung_dep_nhat": [3.0, 7.0], "hinh": "cảnh cũ", "co_canh": "trung", "may_quay": "dung_yen", "san_pham": "khong_co",
                             "chu_chen_san": "khong", "the": [], "diem": 4, "chac_chan": "cao"}], "van_de": [], "dung_lam_bang_chung": True}
        md = self.kho / "_mo-ta" / "v0.mp4.mo-ta.json"; md.parent.mkdir(); md.write_text(json.dumps(cu, ensure_ascii=False, indent=2), encoding="utf-8")
        r = self._chay(gia.runner_gia(log))                                            # không lai: mô tả cũ vẫn dùng được, chỉ học video thiếu
        self.assertEqual(r["da_hoc"], 1); self.assertIn("v1.mp4", log[0]["prompt"]); self.assertNotIn("v0.mp4", log[0]["prompt"])
        self.assertEqual(json.loads(md.read_text(encoding="utf-8"))["tom_tat"], "mô tả cũ")
        self.assertFalse((self.kho / "_mo-ta" / "_cu").exists())
        # có sẵn 1 bản sao lưu → không bị đè
        cu_f = self.kho / "_mo-ta" / "_cu" / "v0.mp4.mo-ta.json"; cu_f.parent.mkdir(); cu_f.write_text("BAN-SAO-CU-NHAT", encoding="utf-8")
        log.clear()
        (hc.LS).mkdir(parents=True, exist_ok=True)
        r = self._chay(gia.runner_gia(log), lai=True)
        self.assertEqual(r["da_hoc"], 1); self.assertIn("v0.mp4", log[0]["prompt"]); self.assertNotIn("v1.mp4", log[0]["prompt"])      # v1 đã là kiểu 2
        self.assertEqual(self._mo_ta("v0.mp4")["kieu"], 2); self.assertEqual(cu_f.read_text(encoding="utf-8"), "BAN-SAO-CU-NHAT")

    def test_lai_sao_luu_1_lan_va_cat_so_canh_da_dung(self):
        hub_sp = self.hub / "san-pham" / "t1"; hub_sp.mkdir(parents=True)
        (hub_sp / "san-pham.json").write_text(json.dumps({"kho_video": str(self.kho), "ten_goi": "Nano Đồng", "nhan_cung_san_pham": ["Bọ Trĩ Top One"]}), encoding="utf-8")
        self._videos(1); log = []
        cu = {"video": "v0.mp4", "thoi_luong_s": 40.0, "tom_tat": "mô tả cũ", "nguoi": "", "boi_canh": "", "cay_trong": ["ot"], "loi_noi_tom_tat": "", "san_pham_thay": [],
              "canh_quay": [{"tu_s": 3.0, "den_s": 8.0, "khung_dep_nhat": [3.0, 7.0], "hinh": "cảnh cũ", "co_canh": "trung", "may_quay": "dung_yen", "san_pham": "khong_co",
                             "chu_chen_san": "khong", "the": [], "diem": 4, "chac_chan": "cao"}], "van_de": [], "dung_lam_bang_chung": True}
        md = self.kho / "_mo-ta" / "v0.mp4.mo-ta.json"; md.parent.mkdir(); md.write_text(json.dumps(cu, ensure_ascii=False, indent=2), encoding="utf-8")
        goc = md.read_bytes()
        (hc.LS).mkdir(parents=True); (hc.LS / "canh-da-dung-t1.txt").write_text("0001 0002", encoding="utf-8")
        with mock.patch.object(hc.km, "_kho_cua", lambda ma: self.kho):
            r = hc.hoc_kho("t1", runner=gia.runner_gia(log), do_dai=lambda p: 40.0, kiem_mo=lambda: True, project=False, cat=gia.cat_gia(3), to_anh=gia.to_anh_gia, lai=True)
        self.assertEqual(r["da_hoc"], 1, r)
        self.assertEqual((self.kho / "_mo-ta" / "_cu" / "v0.mp4.mo-ta.json").read_bytes(), goc)
        self.assertIn("Nano Đồng; Bọ Trĩ Top One", log[0]["prompt"])                    # tên sản phẩm của chủ hàng để biết "hàng khác"
        self.assertFalse((hc.LS / "canh-da-dung-t1.txt").exists())
        luu = list(hc.LS.glob("canh-da-dung-t1.cu-*.txt")); self.assertEqual(len(luu), 1); self.assertEqual(luu[0].read_text(encoding="utf-8"), "0001 0002")
        # học lại KHÔNG kèm lai: không cất sổ cảnh đã dùng
        (hc.LS / "canh-da-dung-t1.txt").write_text("0009", encoding="utf-8")
        with mock.patch.object(hc.km, "_kho_cua", lambda ma: self.kho):
            hc.hoc_kho("t1", runner=gia.runner_gia(log), do_dai=lambda p: 40.0, kiem_mo=lambda: True, project=False, cat=gia.cat_gia(3), to_anh=gia.to_anh_gia, lai=True)
        self.assertTrue((hc.LS / "canh-da-dung-t1.txt").exists())                          # đã kiểu 2 hết → không có gì học lại → giữ sổ

    def test_chi_hoc_lai_dung_video_chon(self):
        self._videos(3); log = []
        self._chay(gia.runner_gia(log))                                                # học đủ 3 video (kiểu 2)
        cu = {"video": "v1.mp4", "thoi_luong_s": 40.0, "tom_tat": "mô tả cũ", "canh_quay": [{"tu_s": 3.0, "den_s": 8.0, "hinh": "cảnh cũ", "co_canh": "trung", "diem": 4}]}
        md = self.kho / "_mo-ta" / "v1.mp4.mo-ta.json"; goc = json.dumps(cu, ensure_ascii=False)
        md.write_text(goc, encoding="utf-8")                                           # v1 quay về kiểu cũ
        log.clear()
        r = self._chay(gia.runner_gia(log), chi=["v0.mp4", "v1.mp4", "khong-co.mp4"])
        self.assertEqual((r["da_hoc"], r["tat_ca_xong"]), (2, True), r)
        self.assertIn("v0.mp4", log[0]["prompt"]); self.assertIn("v1.mp4", log[0]["prompt"]); self.assertNotIn("v2.mp4", log[0]["prompt"])
        self.assertEqual((hc.JOB["tong"], hc.JOB["xong"]), (2, 2))
        self.assertEqual(self._mo_ta("v1.mp4")["kieu"], 2)
        self.assertEqual(json.loads((self.kho / "_mo-ta" / "_cu" / "v1.mp4.mo-ta.json").read_text(encoding="utf-8"))["tom_tat"], "mô tả cũ")     # bản cũ được cất
        self.assertFalse((self.kho / "_mo-ta" / "_cu" / "v0.mp4.mo-ta.json").exists())                             # video đã kiểu 2: không cất vào _cu
        log.clear()
        r = self._chay(gia.runner_gia(log), chi=["khong-co.mp4"])                      # không video nào hợp lệ → không có gì để học
        self.assertEqual((r["da_hoc"], len(log)), (0, 0)); self.assertEqual(hc.JOB["thong_bao"], "Kho đã đủ mô tả.")

    def test_chi_hoc_video_chua_co_mo_ta(self):
        self._videos(2); log = []
        r = self._chay(gia.runner_gia(log), chi=["v1.mp4"])
        self.assertEqual(r["da_hoc"], 1); self.assertNotIn("v0.mp4", log[0]["prompt"]); self.assertFalse((self.kho / "_mo-ta" / "v0.mp4.mo-ta.json").exists())

    def test_nhan_du_phieu_thi_bao_antigravity_dung_cuoc_tro_chuyen(self):
        ra = self.kho / "_tam" / "o.json"; da_huy = []

        def gui(model, prompt, td):
            ra.parent.mkdir(parents=True, exist_ok=True); ra.write_text('{"ok": 1}', encoding="utf-8")
            return "cid-9"
        got = []
        xong = hc.chay_lo("m", "p", [ra], "t", lambda f, t: got.append(t), gui=gui, huy=threading.Event(), huy_cuoc=da_huy.append, ngu=lambda g: None)
        self.assertEqual((len(xong), got, da_huy), (1, ['{"ok": 1}'], ["cid-9"]))
        self.assertEqual(hc._RUN["conv"] - {"cid-9"}, hc._RUN["conv"])               # đã bỏ khỏi danh sách đang chạy

    def test_model_va_mo_antigravity_khong_mo(self):
        self._videos(1); log = []
        r = self._chay(gia.runner_gia(log), kiem_mo=lambda: False)
        self.assertEqual(hc.JOB["trang_thai"], "can_mo"); self.assertEqual(log, [])
        self.assertIn("Antigravity", hc.JOB["thong_bao"]); self.assertIn("còn 1 video chưa học", hc.JOB["thong_bao"])
        for cu in ("flash", "pro", "flash_lite", "gemini-2.5-pro", "", None):
            with mock.patch.object(hc, "doc_cau_hinh", lambda cu=cu: {"model": cu}):
                self.assertEqual(hc.doc_model(), "gemini-4-hydrogen-high", cu)
        with mock.patch.object(hc, "doc_cau_hinh", lambda: {"model": "gemini-3.8-flash-medium"}):
            self.assertEqual(hc.doc_model(), "gemini-3.8-flash-medium")
        self.assertEqual(list(hc.MODELS)[0], "gemini-4-hydrogen-high"); self.assertEqual(len(hc.MODELS), 3)
        self._videos(1)
        r = self._chay(gia.runner_gia(log), model="flash")
        self.assertEqual(log[-1]["model"], "gemini-4-hydrogen-high")                        # cấu hình cũ → mặc định


class KhoiPhucTest(unittest.TestCase):
    def setUp(self):
        self.hub = _tmp(); self._ls = hc.LS; hc.LS = self.hub / "lich-su"
        hc.JOB.update(dang_chay=False, trang_thai="nghi", thong_bao="", dung=False)
        with hc._RUN_LOCK:
            hc._RUN["conv"].clear()
        p = mock.patch.object(hc, "_goi_ls", lambda *a, **k: None); p.start(); self.addCleanup(p.stop)

    def tearDown(self):
        hc.LS = self._ls

    def test_khong_co_file_hoac_khong_dang_chay(self):
        self.assertIsNone(hc.khoi_phuc())
        hc.LS.mkdir(parents=True)
        (hc.LS / "hoc-canh-job.json").write_text(json.dumps({"job": {"dang_chay": False, "trang_thai": "xong"}, "conv": ["c9"], "kho": ""}), encoding="utf-8")
        with mock.patch.object(hc, "huy_cuoc_tro_chuyen", lambda c: self.fail("không được huỷ khi không có việc dở")):
            self.assertIsNone(hc.khoi_phuc())
        (hc.LS / "hoc-canh-job.json").write_text("rác {", encoding="utf-8")
        self.assertIsNone(hc.khoi_phuc())

    def test_khoi_dong_lai_giua_luc_hoc(self):
        kho = _tmp(); (kho / "v0.mp4").write_bytes(b"x")
        luu = {}

        def runner(model, prompt, outs, td, khi_co, **kw):
            with hc._RUN_LOCK:
                hc._RUN["conv"].add("cid-dang-chay")
            hc._luu()
            luu["file"] = (hc.LS / "hoc-canh-job.json").read_text(encoding="utf-8")        # ảnh chụp lúc "hub bị tắt giữa chừng"
            return gia.runner_gia([])(model, prompt, outs, td, khi_co, **kw)
        hc.hoc_kho(str(kho), runner=runner, do_dai=lambda p: 40.0, kiem_mo=lambda: True, project=False, ten="t", cat=gia.cat_gia(2), to_anh=gia.to_anh_gia)
        snap = json.loads(luu["file"])
        tam = kho / "_tam" / "hoc-canh" / "01-abc"; tam.mkdir(parents=True); (tam / "to-1.jpg").write_bytes(b"j")
        self.assertTrue(snap["job"]["dang_chay"]); self.assertEqual(snap["conv"], ["cid-dang-chay"]); self.assertEqual(snap["job"]["giai_doan"], "hoc")
        # mô phỏng khởi động lại: file cũ còn đó, JOB trong bộ nhớ trống, thư mục tạm còn sót
        (hc.LS / "hoc-canh-job.json").write_text(luu["file"], encoding="utf-8")
        hc.JOB.update(dang_chay=False, trang_thai="nghi", thong_bao="", giai_doan="")
        huy = []
        with mock.patch.object(hc, "huy_cuoc_tro_chuyen", huy.append):
            n = hc.khoi_phuc()
        self.assertEqual((n, huy), (1, ["cid-dang-chay"]))
        self.assertFalse((kho / "_tam" / "hoc-canh").exists())
        self.assertEqual((hc.JOB["trang_thai"], hc.JOB["dang_chay"], hc.JOB["dung"]), ("dung", False, True))
        self.assertEqual(hc.JOB["thong_bao"], "Xưởng vừa khởi động lại giữa lúc học — đã dừng gọn việc dở. Bấm Học cảnh để làm tiếp (video đã học được giữ).")
        self.assertTrue(snap["job"]["ma"] == hc.JOB["ma"])
        now = json.loads((hc.LS / "hoc-canh-job.json").read_text(encoding="utf-8"))
        self.assertFalse(now["job"]["dang_chay"]); self.assertEqual(now["conv"], [])
        with mock.patch.object(hc, "huy_cuoc_tro_chuyen", lambda c: self.fail("chỉ khôi phục 1 lần")):
            self.assertIsNone(hc.khoi_phuc())

    def test_dang_hoc_that_thi_khong_dung_vao(self):
        hc.LS.mkdir(parents=True)
        (hc.LS / "hoc-canh-job.json").write_text(json.dumps({"job": {"dang_chay": True}, "conv": ["c1"], "kho": ""}), encoding="utf-8")
        hc.JOB["dang_chay"] = True
        try:
            with mock.patch.object(hc, "huy_cuoc_tro_chuyen", lambda c: self.fail("đang học thật")):
                self.assertIsNone(hc.khoi_phuc())
        finally:
            hc.JOB["dang_chay"] = False


class NhanAntigravityTest(unittest.TestCase):
    def setUp(self):
        self.d = _tmp(); self._dm = hc.DAEMON_DIR; hc.DAEMON_DIR = self.d

    def tearDown(self):
        hc.DAEMON_DIR = self._dm

    def _hub(self, ten, pid, port, tuoi):
        f = self.d / ten
        f.write_text(json.dumps({"pid": pid, "httpPort": port, "csrfToken": "tok" + str(pid), "lsVersion": "1.0"}), encoding="utf-8")
        t = time.time() - tuoi; os.utime(f, (t, t))

    def test_tep_cu_pid_chet_hoac_cong_dong(self):
        self._hub("hub_5001.json", 111, 5001, 0)                          # mới nhất nhưng PID đã chết / bị cấp cho chương trình khác
        self.assertIsNone(hc.tim_hub(song=lambda pid: False, cong=lambda p: True))
        self._hub("hub_5002.json", 222, 5002, 10)
        self.assertIsNone(hc.tim_hub(song=lambda pid: pid == 222, cong=lambda p: p == 9999))      # PID đúng nhưng cổng không nhận kết nối
        h = hc.tim_hub(song=lambda pid: pid == 222, cong=lambda p: p == 5002)                    # tệp cũ hơn nhưng còn sống thật → dùng
        self.assertEqual((h["pid"], h["httpPort"]), (222, 5002))
        self._hub("hub_5003.json", 333, 5003, 20)
        h = hc.tim_hub(song=lambda pid: True, cong=lambda p: True)
        self.assertEqual(h["pid"], 111)                                                           # cả ba đều "sống" → lấy tệp mới nhất
        (self.d / "hub_5004.json").write_text("không phải json", encoding="utf-8")
        self.assertIsNotNone(hc.tim_hub(song=lambda pid: True, cong=lambda p: True))

    def test_pid_that_cua_chuong_trinh_khac_khong_phai_antigravity(self):
        ten = hc._ten_anh(os.getpid())
        self.assertTrue(ten.endswith(".exe"), ten)
        self.assertFalse(hc._song(os.getpid()))                           # tiến trình python đang sống nhưng không phải Antigravity
        self.assertFalse(hc._song(0)); self.assertFalse(hc._song("không"))

    def test_cong_mo(self):
        so = socket.socket(); so.bind(("127.0.0.1", 0)); so.listen(1); cong = so.getsockname()[1]
        try:
            self.assertTrue(hc._cong_mo(cong))
        finally:
            so.close()
        self.assertFalse(hc._cong_mo(cong, han=0.3))

    def test_nho_ket_qua_3_giay(self):
        self._hub("hub_5001.json", 111, 5001, 0)
        goi = []
        with mock.patch.object(hc, "_song", lambda pid: goi.append(pid) or True), mock.patch.object(hc, "_cong_mo", lambda p: True):
            hc._HUB_NHO.update(t=0.0, h=None)
            self.assertTrue(hc.tim_hub()); self.assertTrue(hc.tim_hub()); self.assertTrue(hc.trang_thai_agy()["mo"])
            self.assertEqual(goi, [111])                                       # 3 lần hỏi, chỉ kiểm tiến trình 1 lần
            hc._HUB_NHO["t"] -= 5
            hc.tim_hub(); self.assertEqual(goi, [111, 111])
        hc._HUB_NHO.update(t=0.0, h=None)

    def test_trang_thai_vo_va_mo_antigravity(self):
        with mock.patch.object(hc, "tim_hub", lambda *a, **k: None), mock.patch.object(hc, "_agy_exe_chay", lambda: True):
            self.assertEqual(hc.trang_thai_agy(), {"mo": False, "phien_ban": None, "vo": True})
            self.assertIn("đang mở nhưng chưa sẵn sàng", hc._msg_chua_mo())
            exe = self.d / "Antigravity.exe"; exe.write_bytes(b"x"); goi = []
            with mock.patch.object(hc, "AGY_EXE", exe), mock.patch.object(hc.subprocess, "Popen", lambda *a, **k: goi.append(a)):
                r = hc.mo_antigravity()
            self.assertTrue(r["ok"] and r["vo"]); self.assertEqual(len(goi), 1)           # exe đang chạy mà dịch vụ chưa lên: vẫn gọi mở
        with mock.patch.object(hc, "tim_hub", lambda *a, **k: None), mock.patch.object(hc, "_agy_exe_chay", lambda: False):
            self.assertEqual(hc.trang_thai_agy()["vo"], False); self.assertEqual(hc._msg_chua_mo(), hc.MSG_AGY_CHUA_MO)
        with mock.patch.object(hc, "tim_hub", lambda *a, **k: {"pid": 1, "httpPort": 2, "csrfToken": "t", "lsVersion": "9"}):
            self.assertEqual(hc.trang_thai_agy(), {"mo": True, "phien_ban": "9", "vo": False})
            self.assertEqual(hc.mo_antigravity(), {"ok": True, "da_mo": True})


class KetQuaKhoTest(unittest.TestCase):
    def test_ket_qua_theo_video_va_loai(self):
        kho = _tmp()
        for r in ("a.mp4", "b.mp4", "c.mp4"):
            (kho / r).write_bytes(b"x")
        (kho / "_mo-ta").mkdir()
        km.ghi_mo_ta(kho / "_mo-ta" / "a.mp4.mo-ta.json", _mo_ta_mau("a.mp4"))
        cu = {"video": "b.mp4", "thoi_luong_s": 40.0, "tom_tat": "cũ", "canh_quay": [{"tu_s": 1.0, "den_s": 5.0, "hinh": "cũ", "diem": 3, "co_canh": "trung"}]}
        km.ghi_mo_ta(kho / "_mo-ta" / "b.mp4.mo-ta.json", cu)
        r = hc.ket_qua_kho(kho)
        self.assertEqual(r["tong"], {"video_tong": 3, "kieu2": 1, "kieu1": 1, "chua_hoc": 1, "canh_tong": 5})
        self.assertEqual([v["kieu"] for v in r["video"]], [2, 1, 0])
        a = r["video"][0]
        self.assertEqual((a["model"], a["hoc_luc"], a["loi_hay"]), ("gemini-4-hydrogen-high", "2026-11-14T10:00:00", ["Câu hay một."]))
        self.assertEqual(sorted(a["canh"][0]), sorted(["tu", "den", "loai", "co_canh", "ta", "noi", "loi", "dep", "mat", "chu_chen", "hang_khac"]))
        self.assertEqual(r["theo_loai"]["chai_ro"], 1); self.assertEqual(r["theo_loai"]["re_goc"], 0); self.assertEqual(len(r["theo_loai"]), 12)
        self.assertIsNone(r["video"][1]["canh"][0]["loai"])


class DaoDienKieu2Test(unittest.TestCase):
    def test_dong_ds_va_diem_lien_quan(self):
        import dao_dien as dd
        s2 = {"id": "0001", "kieu": 2, "vai_tro": ["chai_ro"], "co_canh": "can_canh", "mo_ta": "Tay cầm chai Nano Đồng xoay mặt trước " + "x" * 100, "noi": "bọ trĩ làm xoăn đọt ớt",
              "soat": {"mat": 0, "ghi": "ghi ngắn", "dep": 5}, "dai": 4.0, "the": []}
        d = dd.dong_ds("0001", s2).split(" | ")
        self.assertEqual(d[0], "0001"); self.assertEqual(d[1], "chai_ro"); self.assertEqual(d[2], "can_canh")
        self.assertTrue(d[3].startswith("Tay cầm chai Nano Đồng")); self.assertEqual(len(d[3]), 90)
        self.assertEqual(d[4], "nói: bọ trĩ làm xoăn đọt ớt"); self.assertEqual(d[5], "4.0")
        s2n = dict(s2, soat={"mat": 2, "ghi": "g", "dep": 3})
        self.assertIn("NGƯỜI NÓI", dd.dong_ds("0001", s2n))
        cu = {"id": "0002", "vai_tro": ["vuon"], "co_canh": None, "mo_ta": "mô tả dài của cảnh kiểu cũ " * 5, "soat": {"mat": 0, "ghi": "ghi cũ", "dep": 3}, "dai": 3.5, "noi": "bỏ qua"}
        self.assertEqual(dd.dong_ds("0002", cu), "0002 | vuon | ghi cũ | 3.5")                  # cảnh cũ: không cột cỡ cảnh khi chưa biết, giữ soat.ghi, không có "nói"
        cu2 = dict(cu, soat={"mat": 0, "dep": 3}, co_canh="toan")
        self.assertEqual(dd.dong_ds("0002", cu2), "0002 | vuon | toan | " + cu["mo_ta"][:60] + " | 3.5")
        self.assertTrue(dd.COT_DS.startswith("Cột: id | vai trò | cỡ cảnh | mô tả | nói:"))
        a = dd._diem_lien_quan({"soat": {"ghi": "x", "dep": 3}, "mo_ta": "", "the": [], "vai_tro": []}, "cây xoăn đọt", "")
        b = dd._diem_lien_quan({"soat": {"ghi": "x", "dep": 3}, "mo_ta": "", "the": [], "vai_tro": [], "noi": "bọ trĩ làm xoăn đọt"}, "cây xoăn đọt", "")
        self.assertGreater(b, a)


class MayCatCanhTest(unittest.TestCase):
    def _video(self, path):
        import cv2, numpy as np
        w, h, fps = 96, 160, 10
        vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        if not vw.isOpened():
            self.skipTest("máy này không có codec mp4v")
        rng = np.random.RandomState(7)
        tex1 = rng.randint(0, 40, (h, w, 3)).astype(np.int16); tex2 = rng.randint(0, 40, (h, w, 3)).astype(np.int16)
        for i in range(60):
            base = np.zeros((h, w, 3), np.int16)
            if i < 30:
                base[:] = (40, 170, 50); base += tex1; base[::16] = (255, 255, 255)
            else:
                base[:] = (40, 40, 200); base += tex2; base[:, ::16] = (0, 0, 0)
            vw.write(np.clip(base, 0, 255).astype(np.uint8))
        vw.release()
        if not Path(path).exists() or Path(path).stat().st_size < 500:
            self.skipTest("không ghi được video thử")

    def test_cat_gan_moc_va_lap_lai(self):
        import cat_canh
        v = _tmp() / "thu.mp4"; self._video(v)
        a = cat_canh.cat(v); b = cat_canh.cat(v)
        self.assertEqual(a, b)                                                             # cùng video luôn cùng kết quả
        if a["dai"] < 5.0:
            self.skipTest("codec đọc lại không đủ khung")
        self.assertTrue(any(abs(x - 3.0) < 0.5 for x in a["vet_cat"]), a["vet_cat"])      # vết cắt gần ranh giới 3 giây
        self.assertGreaterEqual(len(a["canh"]), 2)
        for c in a["canh"]:
            self.assertIn(c["chuyen_dong"], ("em", "rung")); self.assertGreater(c["den"], c["tu"])
            self.assertFalse(c["tu"] < 3.0 < c["den"], c)                                   # không cảnh nào vắt qua chỗ cắt
        files = cat_canh.to_anh([(1, str(v), a["canh"][0]["giua"]), (2, str(v), a["canh"][-1]["giua"])], str(v.parent / "to"))
        self.assertEqual(len(files), 1); self.assertTrue(files[0].exists()); self.assertTrue(files[0].name.endswith("-1.jpg"))

    def test_chuyen_dong_chi_con_em_va_rung(self):
        import cat_canh
        self.assertEqual(cat_canh._chuyen_dong([(0.0, 0.0)] * 6)[0], "em")
        self.assertEqual(cat_canh._chuyen_dong([(1.0, 0.0)] * 6)[0], "em")                  # lia đều → vẫn là máy êm
        self.assertEqual(cat_canh._chuyen_dong([None, None, None, (0.0, 0.0)])[0], "rung")   # quá nửa không đo được
        self.assertEqual(cat_canh._chuyen_dong([(5.0, 5.0), (-5.0, -5.0)] * 3)[0], "rung")   # giật mạnh
        self.assertEqual(cat_canh._chuyen_dong([])[0], "em")



class KhungHinhTest(unittest.TestCase):
    """Đường dẫn xem trước 1 khung hình: chỉ nhận video có trong kho của sản phẩm."""
    def test_khung_chi_trong_kho(self):
        import numpy as np
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
        import server as sv
        import cv2
        kho = _tmp(); (kho / "sub").mkdir(); (kho / "_tam").mkdir()
        mp4 = kho / "sub" / "a.mp4"
        w = cv2.VideoWriter(str(mp4), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 96))
        for i in range(30):
            w.write(np.full((96, 64, 3), 40 + i, np.uint8))
        w.release()
        (kho / "_tam" / "b.mp4").write_bytes(b"x")
        goi = []
        with mock.patch.object(hc.km, "_kho_cua", lambda ma: kho):
            b = sv.hoc_canh_khung("t1", "sub/a.mp4", "1")
            self.assertTrue(b and b[:2] == bytes([0xFF, 0xD8]))                          # JPEG
            self.assertIs(sv.hoc_canh_khung("t1", "sub/a.mp4", 1), b)                  # lần 2 lấy từ bộ nhớ đệm
            for sai in ("../x.mp4", "_tam/b.mp4", "sub/khong.mp4", "", "sub\..\..\a.mp4", str(mp4)):
                self.assertIsNone(sv.hoc_canh_khung("t1", sai, 0), sai)
            self.assertIsNone(sv.hoc_canh_khung("t1", "sub/a.mp4", "abc"))


if __name__ == "__main__":
    unittest.main()
