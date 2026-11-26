"""Kho cảnh kiểu 3 (phiếu v3.1): kiểm phiếu, luật cấm chung, khóa cũ đúng nghĩa, nạp kho sau cờ, giữ id theo IoU, bộ đếm id bền,
bảng nối id cho lịch sử, bản chụp + quay lui. Không gọi AI. Chạy:  python -m unittest tests.test_kho_v3 -v"""
import copy, json, os, sys, tempfile, unittest
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="xv-v3-")
os.environ.setdefault("XUONG_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import phieu_v3 as p3  # noqa: E402
import kho_canh as kc  # noqa: E402
import dao_dien as dd  # noqa: E402
import soat_kho  # noqa: E402


def _doan(tu, den, **k):
    d = {"tu": tu, "den": den, "hinh": "Tay cầm chai TC01", "viec": [{"ma": "cam_xem", "vat": "v1", "dich": None}],
         "vat_thay": [{"id": "v1", "mat": "truoc", "ten_doc": "TC 01", "so_luong": 1}], "cay": None, "dau_hieu": [], "sinh_vat": [],
         "so_sanh": None, "dich_thay": "", "nguoi": {"kieu": "tay", "mat_ro": False, "noi_vao_may": False}, "loi": [], "chu_dan": [],
         "gia_qua": {"chu_dan": [], "tren_vat": [], "loi": []}, "nguon": "quay_that",
         "khung": {"co_canh": "can", "chu_the_o": "giua", "net": 3, "rung": False, "toi": False, "dep": 3}}
    d.update(k)
    return d


def _video(doan, bo_qua=(), vat=None):
    return {"tom_tat": "hình cho thấy chai", "kieu_video": "huong_dan", "bo_qua": list(bo_qua), "doan": doan,
            "vat": vat or [{"id": "v1", "loai": "chai", "chu_doc": "TC 01", "la": "sp_chinh"},
                           {"id": "v2", "loai": "can", "chu_doc": "ĐẠM CÁ", "la": "sp_khac:Đạm cá"}]}


class KiemPhieuV3Test(unittest.TestCase):
    def test_hop_le(self):
        self.assertEqual(p3.kiem_video(_video([_doan(0, 4), _doan(4, 9.1)]), 9.0), [])

    def test_v3_vat_la_khong_phai_id(self):
        v = _video([_doan(0, 4, viec=[{"ma": "lat_la", "vat": "la", "dich": "mat_duoi_la"}])])
        self.assertEqual(p3.kiem_video(v, 4), [])

    def test_v3_id_ngoai_video_va_id_trung(self):
        v = _video([_doan(0, 4, vat_thay=[{"id": "v9", "mat": "truoc", "ten_doc": None, "so_luong": 1}])])
        self.assertTrue(any("v9" in e for e in p3.kiem_video(v, 4)))
        v = _video([_doan(0, 4)], vat=[{"id": "v1", "loai": "chai", "chu_doc": None, "la": "sp_chinh"}] * 2)
        self.assertTrue(any("trùng" in e for e in p3.kiem_video(v, 4)))

    def test_v3_doan_chong_che_lo_hong(self):
        self.assertTrue(any("hở" in e for e in p3.kiem_video(_video([_doan(0, 4), _doan(5, 9)]), 9)))
        self.assertTrue(any("chồng" in e for e in p3.kiem_video(_video([_doan(0, 5), _doan(4, 9)]), 9)))
        self.assertTrue(any("hở cuối" in e for e in p3.kiem_video(_video([_doan(0, 4)]), 9)))
        self.assertEqual(p3.kiem_video(_video([_doan(0.2, 4), _doan(4.25, 9)], bo_qua=[]), 9.2), [])     # trong dung sai mép

    def test_v3_moc_loi_gia_tai_ngoai_doan(self):
        v = _video([_doan(0, 4, loi=[{"tu": 3, "den": 6, "chu_de": "gia", "tom": "giá 100k"}])])
        self.assertTrue(any("lời" in e for e in p3.kiem_video(v, 4)))
        v = _video([_doan(0, 4, dau_hieu=[{"ma": "la_vang", "tai": 7}])])
        self.assertTrue(any("tai" in e for e in p3.kiem_video(v, 4)))

    def test_enum_quyet_dinh_cam_la_bi_bac(self):
        v = _video([_doan(0, 4, chu_dan=[{"noi_dung": "-25%", "loai": "giam_gia", "vi_tri": "tren", "che_chu_the": False}])])
        self.assertTrue(p3.kiem_video(v, 4))
        v = _video([_doan(0, 4, viec=[{"ma": "khac:nhúng cành", "vat": "canh", "dich": None}])])
        self.assertEqual(p3.kiem_video(v, 4), [])                         # enum mở khác: giữ

    def test_null_khac_mang_rong(self):
        v = _video([_doan(0, 4, loi=None)])
        self.assertEqual(p3.kiem_video(v, 4), [])
        self.assertIsNone(p3.mo_ta(v, "a.mp4", 4)["nghe_duoc"])
        self.assertFalse(p3.mo_ta(_video([_doan(0, 4)]), "a.mp4", 4)["nghe_duoc"])


class CamTest(unittest.TestCase):
    vat = _video([])["vat"]

    def test_gia_in_trich_null_cam_gia_chi_noi_duoc(self):
        hinh = _doan(0, 4, gia_qua={"chu_dan": [{"tu": 1, "den": 2, "trich": None}], "tren_vat": [], "loi": []})
        noi = _doan(0, 4, gia_qua={"chu_dan": [], "tren_vat": [], "loi": [{"tu": 1, "den": 2, "trich": "100k"}]})
        self.assertIn("gia_qua", p3.cam(hinh, self.vat))
        self.assertEqual(p3.cam(noi, self.vat), [])

    def test_ten_phu_sp_chinh_va_sp_khac_doc_duoc(self):
        self.assertEqual(p3.cam(_doan(0, 4), self.vat), [])
        khac = _doan(0, 4, vat_thay=[{"id": "v2", "mat": "truoc", "ten_doc": "ĐẠM CÁ", "so_luong": 1}])
        self.assertIn("sp_khac", p3.cam(khac, self.vat))
        mo = _doan(0, 4, vat_thay=[{"id": "v2", "mat": "truoc", "ten_doc": None, "so_luong": 1}])
        self.assertEqual(p3.cam(mo, self.vat), [])

    def test_chu_che_chi_cam_khi_khong_quay_that(self):
        cd = [{"noi_dung": "x", "loai": "tieu_de", "vi_tri": "giua", "che_chu_the": True}]
        self.assertEqual(p3.cam(_doan(0, 4, chu_dan=cd), self.vat), [])
        self.assertIn("chu_che", p3.cam(_doan(0, 4, chu_dan=cd, nguon="ghep"), self.vat))

    def test_bad_va_canh_bad_dung_chung_cam(self):
        import viet_loi
        s = {"cam": ["gia_qua"], "soat": {"mat": 0, "chu_muc": 0, "dep": 5}}
        self.assertTrue(soat_kho.bad(s)); self.assertTrue(viet_loi._canh_bad(s))
        s["cam"] = []
        self.assertFalse(soat_kho.bad(s)); self.assertFalse(viet_loi._canh_bad(s))


class KhoaCuTest(unittest.TestCase):
    vat = _video([])["vat"]

    def test_khoa_cu_dung_nghia(self):
        x = p3.shot_cu(_doan(2, 8, loi=[{"tu": 2, "den": 4, "chu_de": "cong_dung", "tom": "ra rễ nhanh"}]), self.vat)
        self.assertEqual(x["dep"], [3.0, 7.0])                              # cặp giây
        self.assertIsInstance(x["soat"]["dep"], int)
        self.assertEqual(x["noi"], "ra rễ nhanh")                           # chuỗi
        self.assertIn("chai_ro", x["vai_tro"]); self.assertEqual(x["loai"], "chai_ro")
        self.assertEqual(x["soat"]["mat"], 0)                               # chỉ thấy tay
        self.assertTrue(x["nhan_can_hop"]); self.assertIsNone(x["soat"]["nhan"])

    def test_rot_la_pha_rot_va_noi_vao_may(self):
        r = p3.shot_cu(_doan(0, 4, viec=[{"ma": "rot", "vat": "v1", "dich": "binh_phun"}]), self.vat)
        self.assertIn("pha_rot", r["vai_tro"])
        n = p3.shot_cu(_doan(0, 4, viec=[{"ma": "noi_vao_may", "vat": None, "dich": None}, {"ma": "cam_xem", "vat": "v1", "dich": None}],
                             nguoi={"kieu": "dung_noi", "mat_ro": True, "noi_vao_may": True}), self.vat)
        self.assertEqual(n["loai"], "nguoi_noi"); self.assertEqual(n["soat"]["mat"], 2); self.assertTrue(n["noi_ghi"])

    def test_cay_tieu_doi_ten_cu(self):
        x = p3.shot_cu(_doan(0, 4, cay={"ten": "tieu", "bo_phan": ["la"], "giai_doan": None}), self.vat)
        self.assertEqual(x["cay"], ["ho_tieu"])


class NapKhoV3Test(unittest.TestCase):
    def setUp(self):
        self.hub = Path(tempfile.mkdtemp(dir=TMP)); self.kho = Path(tempfile.mkdtemp(dir=TMP))
        self._hub, self._dhub = kc.HUB, dd.HUB
        kc.HUB = dd.HUB = self.hub
        self.sp = self.hub / "san-pham" / "tc"; self.sp.mkdir(parents=True)
        (self.kho / "_mo-ta").mkdir()
        for n in ("a.mp4", "b.mp4"):
            (self.kho / n).write_bytes(b"x")
        self._sp({"kho_v3": False})
        for n, cq in (("a.mp4", [(0, 3.0), (3.0, 7.0)]), ("b.mp4", [(0, 5.0)])):     # mô tả cũ kiểu 1
            (self.kho / "_mo-ta" / f"{n}.mo-ta.json").write_text(json.dumps({"video": n, "cay_trong": [], "canh_quay": [
                {"tu_s": a, "den_s": b, "diem": 4, "hinh": "vườn", "the": []} for a, b in cq]}), encoding="utf-8")

    def tearDown(self):
        kc.HUB, dd.HUB = self._hub, self._dhub

    def _sp(self, them):
        d = {"ten_goi": "TC01", "kho_video": str(self.kho)}
        d.update(them)
        (self.sp / "san-pham.json").write_text(json.dumps(d), encoding="utf-8")

    def _v3(self, n, doan, dai):
        v = _video(doan)
        (self.kho / "_mo-ta" / f"{n}{p3.DUOI}").write_text(json.dumps(p3.mo_ta(v, n, dai), ensure_ascii=False), encoding="utf-8")

    def _canh(self):
        return json.loads((self.sp / "canh.json").read_text(encoding="utf-8"))

    def test_co_tat_y_nhu_cu(self):
        kc.nap("tc")
        self._v3("a.mp4", [_doan(0, 3.1), _doan(3.1, 7)], 7)
        kc.nap("tc")
        self.assertTrue(all("kieu" not in x for x in self._canh()))
        self.assertFalse((self.sp / "_ban-chup").exists())

    def test_nap_uu_tien_v3_giu_id_va_bo_dem(self):
        cu = {(x["file"], x["tu"]): x["id"] for x in kc.nap("tc")[0]}
        self._sp({"kho_v3": True})
        self._v3("a.mp4", [_doan(0, 3.1), _doan(3.1, 4.5), _doan(4.5, 5.8), _doan(5.8, 7)], 7)
        kc.nap("tc")
        c = self._canh()
        a = sorted([x for x in c if x["file"] == "a.mp4"], key=lambda x: x["tu"])
        self.assertTrue(all(x["kieu"] == 3 for x in a)); self.assertEqual(len(a), 4)
        self.assertEqual(a[0]["id"], cu[("a.mp4", 0.3)])                     # IoU cao → giữ id
        self.assertNotIn(a[2]["id"], cu.values())                           # đoạn mới → id mới
        self.assertEqual([x["id"] for x in c if x["file"] == "b.mp4"], [cu[("b.mp4", 0.3)]])   # video không có v3: giữ nguyên
        noi = json.loads((self.sp / "canh-id-noi.json").read_text(encoding="utf-8"))
        self.assertEqual(noi[cu[("a.mp4", 3.0)]], [a[1]["id"], a[2]["id"], a[3]["id"]])  # cảnh cũ 3–7 tách thành 3
        self.assertTrue(list((self.sp / "_ban-chup").iterdir()))

    def test_nap_hai_lan_khong_doi_id_va_bang_noi(self):
        kc.nap("tc"); self._sp({"kho_v3": True})
        self._v3("a.mp4", [_doan(0, 3.1), _doan(3.1, 4.5), _doan(4.5, 5.8), _doan(5.8, 7)], 7)
        kc.nap("tc"); c1 = self._canh(); n1 = (self.sp / "canh-id-noi.json").read_text(encoding="utf-8")
        kc.nap("tc")
        self.assertEqual([x["id"] for x in self._canh()], [x["id"] for x in c1])
        self.assertEqual((self.sp / "canh-id-noi.json").read_text(encoding="utf-8"), n1)

    def test_khong_tai_cap_id_da_xoa(self):
        kc.nap("tc"); self._sp({"kho_v3": True})
        self._v3("a.mp4", [_doan(0, 3.1), _doan(3.1, 4.5), _doan(4.5, 5.8), _doan(5.8, 7)], 7)
        kc.nap("tc"); ids1 = {x["id"] for x in self._canh()}
        self._v3("a.mp4", [_doan(0, 7)], 7)                                  # học lại gộp → bỏ bớt id
        kc.nap("tc")
        self._v3("a.mp4", [_doan(0, 1.5), _doan(1.5, 4), _doan(4, 7)], 7)
        kc.nap("tc")
        bo = ids1 - {x["id"] for x in self._canh()}
        moi = {x["id"] for x in self._canh()} - ids1
        self.assertFalse(bo & moi)
        self.assertTrue(all(int(i) > max(int(j) for j in ids1) for i in moi))

    def test_canh_cam_khong_vao_kho(self):
        kc.nap("tc"); self._sp({"kho_v3": True})
        gia = {"chu_dan": [{"tu": 3.5, "den": 4.5, "trich": None}], "tren_vat": [], "loi": []}
        self._v3("a.mp4", [_doan(0, 3.1), _doan(3.1, 5, gia_qua=gia), _doan(5, 7)], 7)
        s, _k = kc.nap("tc")
        a = [x for x in s if x["file"] == "a.mp4"]
        self.assertEqual(len(a), 2)
        self.assertFalse(any(3.1 < x["tu"] < 5 for x in a))

    def test_phieu_v3_hong_dung_mo_ta_cu(self):
        kc.nap("tc"); self._sp({"kho_v3": True})
        self._v3("a.mp4", [_doan(0, 3.1), _doan(4, 7)], 7)                   # hở 3,1–4
        s, _k = kc.nap("tc")
        self.assertTrue(all(x.get("kieu") != 3 for x in s))

    def test_toan_bo_qua_khong_con_canh(self):
        kc.nap("tc"); self._sp({"kho_v3": True})
        self._v3("b.mp4", [], 5)
        p = self.kho / "_mo-ta" / f"b.mp4{p3.DUOI}"
        d = json.loads(p.read_text(encoding="utf-8")); d["phieu_v3"]["bo_qua"] = [{"tu": 0, "den": 5, "ly_do": "den"}]
        p.write_text(json.dumps(d), encoding="utf-8")
        kc.nap("tc")
        self.assertEqual([x for x in self._canh() if x["file"] == "b.mp4"], [])

    def test_lich_su_noi_id_giu_ngay_phu_mo_chot(self):
        cu = {(x["file"], x["tu"]): x["id"] for x in kc.nap("tc")[0]}
        old = cu[("a.mp4", 3.0)]
        ls_dir = self.hub / "lich-su"; ls_dir.mkdir()
        (ls_dir / "canh-da-dung-tc.jsonl").write_text(json.dumps({"ngay": "2026-11-20", "ids": [old, cu[("b.mp4", 0.3)]], "phu": [old]}) + "\n",
                                                      encoding="utf-8")
        (ls_dir / "canh-da-dung-tc.txt").write_text(f"{old} Q-0001\n" + f"{old} {cu[('b.mp4', 0.3)]}\n", encoding="utf-8")
        self._sp({"kho_v3": True})
        self._v3("a.mp4", [_doan(0, 3.1), _doan(3.1, 4.5), _doan(4.5, 5.8), _doan(5.8, 7)], 7)
        kc.nap("tc")
        moi = sorted([x for x in self._canh() if x["file"] == "a.mp4"], key=lambda x: x["tu"])
        ls = dd.doc_lich_su("tc", self.hub)
        self.assertEqual(ls[0]["ids"], [moi[1]["id"], moi[2]["id"], moi[3]["id"], "Q-0001"])          # Q- giữ nguyên, thứ tự giữ
        self.assertEqual(str(ls[1]["ngay"]), "2026-11-20")
        self.assertEqual(ls[1]["phu"], [moi[1]["id"], moi[2]["id"], moi[3]["id"]])
        met = dd.tinh_met(ls, today=__import__("datetime").date(2026, 11, 21))
        self.assertGreater(met.get(moi[1]["id"], 0), 0)

    def test_rollback_sau_khi_da_dung_canh_moi(self):
        c0 = [x["id"] for x in kc.nap("tc")[0]]
        self._sp({"kho_v3": True})
        self._v3("a.mp4", [_doan(0, 3.1), _doan(3.1, 4.5), _doan(4.5, 5.8), _doan(5.8, 7)], 7)
        kc.nap("tc")
        self.assertTrue((self.sp / "canh-id-noi.json").exists())
        for _ in range(12):                                                  # nạp nhiều lần: bản chụp trước kiểu 3 vẫn còn
            kc.nap("tc")
        kc.quay_lui("tc")
        self.assertFalse((self.sp / "canh-id-noi.json").exists())            # bảng nối của kiểu 3 bỏ theo
        self.assertFalse(json.loads((self.sp / "san-pham.json").read_text(encoding="utf-8"))["kho_v3"])
        self.assertEqual([x["id"] for x in self._canh()], c0)
        kc.nap("tc")                                                         # nạp lại sau quay lui: về mô tả cũ, id cũ
        self.assertEqual(sorted(x["id"] for x in self._canh()), sorted(c0))


class PhongChaiChuaDinhViTest(unittest.TestCase):
    def test_co_chai_thieu_hop_khong_phong(self):
        import random, bo_cuc
        for i in range(20):
            o = bo_cuc.tuy_chon(random.Random(i), {"nhan_can_hop": True, "soat": {"nhan": None}})
            self.assertEqual(o["punch"], 0.0)
        self.assertTrue(any(bo_cuc.tuy_chon(random.Random(i), {"soat": {"nhan": None}})["punch"] > 0 for i in range(5)))   # kho cũ: như trước


class KhungNhanV3Test(NapKhoV3Test):
    """Phiếu v3 không có tọa độ nhãn → soát kho bù RIÊNG trường nhan, không thay các trường phiếu đã ghi."""
    def setUp(self):
        super().setUp()
        self._shub = soat_kho.HUB; soat_kho.HUB = self.hub

    def tearDown(self):
        soat_kho.HUB = self._shub
        super().tearDown()

    def _soat(self, tra):
        from unittest import mock
        from PIL import Image
        (self.sp / "_khung").mkdir(exist_ok=True)
        for x in self._canh():
            Image.new("RGB", (27, 48)).save(self.sp / "_khung" / f"{x['id']}.jpg")
        with mock.patch.object(soat_kho, "goi", side_effect=lambda *a, **k: (json.dumps(tra(a[1])), {})), \
                mock.patch.object(soat_kho, "dung_prompt", side_effect=lambda sp, ids: " ".join(ids)), mock.patch.object(sys, "argv", ["x"]):
            soat_kho.soat("tc")

    def test_co_chai_thieu_hop_chi_bu_nhan(self):
        kc.nap("tc"); self._sp({"kho_v3": True})
        self._v3("a.mp4", [_doan(0, 3.1, nguoi={"kieu": "dung_noi", "mat_ro": True, "noi_vao_may": True},
                                 viec=[{"ma": "noi_vao_may", "vat": None, "dich": None}]), _doan(3.1, 7, vat_thay=[])], 7)
        kc.nap("tc")
        hoi = []
        self._soat(lambda p: hoi.append(p) or [{"id": i, "mat": 0, "chu_muc": 2, "hang_khac": True, "dep": 1, "nhan": [0.2, 0.2, 0.6, 0.8], "ghi": "x"}
                                              for i in p.split()])
        c = {x["id"]: x for x in self._canh()}
        a = sorted([x for x in c.values() if x["file"] == "a.mp4"], key=lambda x: x["tu"])
        self.assertEqual(a[0]["soat"]["mat"], 2); self.assertEqual(a[0]["soat"]["chu_muc"], 0)      # phiếu giữ nguyên
        self.assertTrue(a[0]["nhan_da_tim"]); self.assertLess(a[0]["soat"]["nhan"][0], 0.2)       # đã nới mép
        self.assertNotIn(a[1]["id"], " ".join(hoi))                                                # không thấy SP → không hỏi
        kc.nap("tc")                                                                               # nạp lại: giữ khung nhãn
        a2 = {x["id"]: x for x in self._canh()}[a[0]["id"]]
        self.assertEqual(a2["soat"]["nhan"], a[0]["soat"]["nhan"])
        hoi.clear(); self._soat(lambda p: hoi.append(p) or [])
        self.assertNotIn(a[0]["id"], " ".join(hoi))                                                # không hỏi lại

    def test_tim_khong_thay_nhan_la_null_da_tim(self):
        kc.nap("tc"); self._sp({"kho_v3": True})
        self._v3("a.mp4", [_doan(0, 7)], 7)
        kc.nap("tc")
        self._soat(lambda p: [{"id": i, "nhan": None} for i in p.split()])
        x = [x for x in self._canh() if x["file"] == "a.mp4"][0]
        self.assertIsNone(x["soat"]["nhan"]); self.assertTrue(x["nhan_da_tim"])


class RaSoatChatGPTTest(NapKhoV3Test):
    """Lỗi bản rà 26/11 (ChatGPT) — mỗi test một lỗi đã sửa."""
    def _bat(self, doan, dai=7, bo_qua=()):
        kc.nap("tc"); self._sp({"kho_v3": True})
        v = _video(doan, bo_qua)
        (self.kho / "_mo-ta" / f"a.mp4{p3.DUOI}").write_text(json.dumps(p3.mo_ta(v, "a.mp4", dai), ensure_ascii=False), encoding="utf-8")
        return kc.nap("tc")[0]

    def test_cat_mep_chong_doan_cam(self):
        gia = {"chu_dan": [{"tu": 3.2, "den": 4.5, "trich": None}], "tren_vat": [], "loi": []}
        s = self._bat([_doan(0, 3.2), _doan(3.0, 5, gia_qua=gia), _doan(5, 7)])
        a = sorted([x for x in s if x["file"] == "a.mp4"], key=lambda x: x["tu"])
        self.assertEqual(len(a), 2)
        self.assertLessEqual(a[0]["den"], 3.0)                             # 0,2 s có giá ở mép bị cắt
        self.assertLessEqual(a[0]["dep"][1], a[0]["den"])

    def test_cat_mep_bo_qua(self):
        s = self._bat([_doan(0, 4.2), _doan(6, 7)], bo_qua=[{"tu": 4.0, "den": 6, "ly_do": "màn hình đen"}])
        self.assertLessEqual(min(x["den"] for x in s if x["file"] == "a.mp4" and x["tu"] < 1), 4.0)

    def test_kenh_gia_chua_kiem_la_cam(self):
        x = _doan(0, 4, gia_qua={"chu_dan": [], "tren_vat": None, "loi": []})
        self.assertIn("gia_qua", p3.cam(x, _video([])["vat"]))

    def test_tat_co_bo_canh_v3_va_bang_noi(self):
        c0 = sorted(x["id"] for x in kc.nap("tc")[0])
        self._sp({"kho_v3": True})
        self._v3("a.mp4", [_doan(0, 3.1), _doan(3.1, 4.5), _doan(4.5, 5.8), _doan(5.8, 7)], 7)
        kc.nap("tc"); ids_v3 = {x["id"] for x in self._canh() if x.get("kieu") == 3}
        self._sp({"kho_v3": False})                                          # tắt công tắc trên app (không quay lui)
        kc.nap("tc")
        c = self._canh()
        self.assertFalse(any(x.get("kieu") == 3 for x in c))
        self.assertFalse((self.sp / "canh-id-noi.json").exists())
        self.assertEqual(len([x for x in c if x["file"] == "a.mp4"]), 2)      # mô tả cũ nạp lại
        self.assertFalse({x["id"] for x in c} & ids_v3 - set(c0))           # id mới không trùng id kiểu 3 đã cấp

    def test_bo_dem_khong_lui_khi_id_cao_nhat_bi_bo(self):
        kc.nap("tc")
        cao = max(int(x["id"]) for x in self._canh())
        self._sp({"kho_v3": True})
        gia = {"chu_dan": [{"tu": 4, "den": 5, "trich": None}], "tren_vat": [], "loi": []}
        self._v3("b.mp4", [_doan(0, 5, gia_qua=gia)], 5)                    # cảnh id cao nhất (b.mp4) bị cấm → bỏ
        kc.nap("tc")
        self.assertGreaterEqual(json.loads((self.sp / "canh-id.json").read_text(encoding="utf-8"))["cuoi"], cao)

    def test_quay_lui_ve_ban_truoc_lan_bat_gan_nhat(self):
        kc.nap("tc"); self._sp({"kho_v3": True})
        self._v3("a.mp4", [_doan(0, 3.1), _doan(3.1, 7)], 7)
        kc.nap("tc"); kc.quay_lui("tc"); kc.nap("tc")
        (self.kho / "c.mp4").write_bytes(b"x")                              # thêm video giữa hai lần bật
        (self.kho / "_mo-ta" / "c.mp4.mo-ta.json").write_text(json.dumps({"video": "c.mp4", "cay_trong": [], "canh_quay": [
            {"tu_s": 0, "den_s": 4, "diem": 4, "hinh": "vườn", "the": []}]}), encoding="utf-8")
        kc.nap("tc"); truoc = [x["id"] for x in self._canh()]
        self._sp({"kho_v3": True}); kc.nap("tc")
        kc.quay_lui("tc")
        self.assertEqual([x["id"] for x in self._canh()], truoc)            # có c.mp4: bản trước lần bật THỨ HAI

    def test_quay_lui_kho_trong_truoc_khi_bat(self):
        self._sp({"kho_v3": True})
        self._v3("a.mp4", [_doan(0, 3.1), _doan(3.1, 7)], 7)
        kc.nap("tc")
        kc.quay_lui("tc")
        self.assertFalse((self.sp / "canh.json").exists())                  # về đúng trạng thái trước: chưa có kho

    def test_hoa_thuong_ten_file(self):
        kc.nap("tc"); self._sp({"kho_v3": True})
        v = _video([_doan(0, 3.1), _doan(3.1, 7)])
        (self.kho / "_mo-ta" / f"A.MP4{p3.DUOI}").write_text(json.dumps(p3.mo_ta(v, "A.MP4", 7), ensure_ascii=False), encoding="utf-8")
        if not (self.kho / "A.MP4").exists():
            self.skipTest("hệ tệp phân biệt hoa/thường")
        kc.nap("tc")
        a = [x for x in self._canh() if x["file"].casefold() == "a.mp4"]
        self.assertTrue(a and all(x.get("kieu") == 3 for x in a))           # cảnh cũ "a.mp4" không sống sót song song

    def test_noi_id_giu_thu_tu_va_lap(self):
        f = self.sp / "canh-id-noi.json"
        f.write_text(json.dumps({"0009": ["0100", "0101"]}), encoding="utf-8")
        ls = dd._noi_id([{"ngay": None, "ids": ["A", "B", "A"], "phu": []}, {"ngay": None, "ids": ["0009", "C", "0009"], "phu": []}], f)
        self.assertEqual(ls[0]["ids"], ["A", "B", "A"])                     # chốt vẫn là A
        self.assertEqual(ls[1]["ids"], ["0100", "0101", "C"])

    def test_kho_phu_khong_muon_canh_co_chai(self):
        import kho_chung
        old = kho_chung.SP; kho_chung.SP = self.hub / "san-pham"
        try:
            self._sp({"kho_v3": True})
            self._v3("a.mp4", [_doan(0, 3.1), _doan(3.1, 7)], 7)
            kc.nap("tc")
            c = self._canh()
            for x in c:
                x["soat"] = {**(x.get("soat") or {}), "nhan": None, "mat": 0, "chu_muc": 0}; x["vai_tro"] = ["vuon"]
            c[0]["nhan_can_hop"] = False                                     # đối chứng: cảnh không thấy chai vẫn cho mượn
            (self.sp / "canh.json").write_text(json.dumps(c), encoding="utf-8")
            self.assertEqual([x["id"] for x in kho_chung.canh_pool("tc")], ["V-" + c[0]["id"]])
        finally:
            kho_chung.SP = old


if __name__ == "__main__":
    unittest.main()
