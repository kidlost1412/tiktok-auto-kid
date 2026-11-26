"""Bộ lọc ứng viên kiểu 3 (engine/loc_v3.py) + móc CHẠY BÓNG trong dao_dien/ekip: luật cứng, điểm 0–100, nhãn theo câu, ngưỡng, mệt, đa dạng theo file,
câu bị bỏ mốc giọng, y_hinh thiếu, và chạy bóng không đổi lựa chọn. Cảnh kiểu 3 dựng tay, không gọi AI. Chạy:  python -m unittest tests.test_loc_v3 -v"""
import copy, json, os, random, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp(prefix="xv-locv3-")
os.environ.setdefault("XUONG_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import phieu_v3 as p3  # noqa: E402
import loc_v3 as L  # noqa: E402
import dao_dien as dd  # noqa: E402

VAT = [{"id": "v1", "loai": "chai", "chu_doc": "TC 01", "la": "sp_chinh"}, {"id": "v2", "loai": "can", "chu_doc": "ĐẠM CÁ", "la": "sp_khac:Đạm cá"},
       {"id": "v3", "loai": "xo", "chu_doc": None, "la": "dung_cu"}, {"id": "v4", "loai": "phuy", "chu_doc": None, "la": "dung_cu"}]


def doan(tu=0, den=4, **k):
    d = {"tu": tu, "den": den, "hinh": "Tay cầm chai TC01 xoay nhãn", "viec": [{"ma": "cam_xem", "vat": "v1", "dich": None}],
         "vat_thay": [{"id": "v1", "mat": "truoc", "ten_doc": "TC 01", "so_luong": 1}], "cay": None, "dau_hieu": [], "sinh_vat": [],
         "so_sanh": None, "dich_thay": "", "nguoi": {"kieu": "tay", "mat_ro": False, "noi_vao_may": False}, "loi": [], "chu_dan": [],
         "gia_qua": {"chu_dan": [], "tren_vat": [], "loi": []}, "nguon": "quay_that",
         "khung": {"co_canh": "can", "chu_the_o": "giua", "net": 3, "rung": False, "toi": False, "dep": 3}}
    d.update(k)
    return d


def canh(sid, file="a.mp4", d=None, vat=None, **k):
    """Cảnh dạng app (kho_canh.nap): kieu 3 + v3 + vat + khóa cũ từ phieu_v3.shot_cu."""
    d = d or doan()
    vat = VAT if vat is None else vat
    dung = {x.get("id") for x in d.get("vat_thay") or []} | {x.get("vat") for x in d.get("viec") or []}
    s = {"id": sid, "file": file, "tu": d["tu"], "den": d["den"], "dai": d["den"] - d["tu"], "kieu": 3, **p3.shot_cu(d, vat), "v3": d,
         "vat": [x for x in vat if x.get("id") in dung]}
    s.update(k)
    return s


def req(**k):
    y = {"muc": "truc_tiep", "viec": [], "dich": [], "cay": [], "bo_phan": [], "dau_hieu": [], "can_sp": "khong", "can_nguoi_noi": None, "tu_khoa": [], "giay": 3.0}
    y.update(k)
    return y


def ids(kq, i=0):
    return [m["id"] for m in kq[i] if "id" in m]


class CamTest(unittest.TestCase):
    def test_gia_in_trich_null_cam(self):
        gia = canh("gia", d=doan(gia_qua={"chu_dan": [{"tu": 0, "den": 3, "trich": None}], "tren_vat": [], "loi": []}))      # giá hiện trên hình, số mờ (trich null)
        tem = canh("tem", d=doan(gia_qua={"chu_dan": [], "tren_vat": [{"tu": 1, "den": 3}], "loi": []}))
        qua = canh("qua", d=doan(chu_dan=[{"noi_dung": "tặng 1 chai", "loai": "qua_km", "vi_tri": "tren", "che_chu_the": False}]))
        loi_gia = canh("noi", d=doan(gia_qua={"chu_dan": [], "tren_vat": [], "loi": [{"tu": 0, "den": 3, "trich": "hai trăm nghìn"}]}))   # giá chỉ NÓI: dùng được (tắt tiếng gốc)
        gia_gia = canh("gia-xoa-cam", d=doan(gia_qua={"chu_dan": [{"tu": 0, "den": 3, "trich": None}], "tren_vat": [], "loi": []}), cam=[])       # kho ghi cam rỗng nhưng phiếu có giá
        tay_cam = canh("tay-cam", cam=["gia_qua"])
        cu = {"id": "cu", "file": "a.mp4", "tu": 0, "den": 4, "dai": 4, "mo_ta": "chai", "soat": {"dep": 3}}                                # không phải kiểu 3
        kieu2 = canh("k2", kieu=2)
        sach = canh("sach")
        kq = L.ung_vien_v3([{"text": "Cầm chai lên xem nhãn."}], [req(viec=["cam_xem"], can_sp="thay")], [""], [gia, tem, qua, loi_gia, gia_gia, tay_cam, cu, kieu2, sach])
        got = set(ids(kq))
        self.assertEqual(got, {"noi", "sach"})
        self.assertTrue({"gia", "tem", "qua", "gia-xoa-cam", "tay-cam", "cu"}.isdisjoint(got))
        self.assertNotIn("k2", got)                            # kieu=2 không có v3 → bị loại

    def test_ten_phu_sp_chinh_va_sp_khac_doc_duoc(self):
        sai = canh("sai", d=doan(vat_thay=[{"id": "v1", "mat": "truoc", "ten_doc": "TC 01", "so_luong": 1}, {"id": "v2", "mat": "truoc", "ten_doc": "ĐẠM CÁ", "so_luong": 1}]))
        phu_mo = canh("phu-mo", file="b.mp4", d=doan(vat_thay=[{"id": "v1", "mat": "truoc", "ten_doc": "TC 01", "so_luong": 1}, {"id": "v2", "mat": "khong_ro", "ten_doc": None, "so_luong": 1}]))
        chi_chinh = canh("chinh", file="c.mp4")
        self.assertTrue(sai["cam"] and not phu_mo["cam"] and not chi_chinh["cam"])
        sai2 = dict(sai, cam=[])                                # cam của kho bị xóa nhầm: bộ lọc tự tính lại từ phiếu gốc
        y = req(viec=["cam_xem"], can_sp="doc_ten", tu_khoa=["chai TC01"])
        kq = L.ung_vien_v3([{"text": "Chai TC 01 đây."}], [y], [""], [sai, sai2, phu_mo, chi_chinh])
        self.assertEqual(set(ids(kq)), {"phu-mo", "chinh"})    # tên sp_khac đọc được → loại; sp_khac chỉ thấy (không đọc) → vẫn dùng
        self.assertTrue(all(m["nhan"] == "dung" for m in kq[0]))

    def test_doc_ten_phai_doc_duoc_ten_sp_chinh_moi_dung(self):
        mo = canh("mo", d=doan(vat_thay=[{"id": "v1", "mat": "truoc", "ten_doc": None, "so_luong": 1}]))     # thấy chai, không đọc được tên
        doc = canh("doc", file="b.mp4")
        y = req(viec=["cam_xem"], can_sp="doc_ten", tu_khoa=["chai"])
        nhan = {m["id"]: m["nhan"] for m in L.ung_vien_v3([{"text": "Chai TC 01."}], [y], [""], [mo, doc], nguong=(60, 10))[0] if "id" in m}
        self.assertEqual(nhan["doc"], "dung")
        self.assertEqual(nhan.get("mo", "minh_hoa"), "minh_hoa")


class DiemTest(unittest.TestCase):
    def test_dich_cua_viec_phu_khong_khop_viec_chinh(self):
        va = lambda ma, vat, dich: {"ma": ma, "vat": vat, "dich": dich}
        y = L.yeu_cau("Rót vào phuy.", req(viec=["rot"], dich=["phuy"], tu_khoa=["rót"]), "Rót thuốc vào phuy")
        sp_dung = canh("dung", d=doan(viec=[va("rot", "v1", "phuy")]))
        sp_sai = canh("sai", d=doan(viec=[va("rot", "v1", "xo"), va("mo_nap", "v1", "phuy")]))      # đích "phuy" nằm ở việc PHỤ, việc chính rót vào xô
        sp_trung = canh("trung", d=doan(viec=[va("rot", "v1", None)]))                             # chưa biết đích: không cộng, không phạt
        sp_phu = canh("phu", d=doan(viec=[va("cam_xem", "v1", "phuy"), va("rot", "v1", "xo")]))     # đích phuy của việc cầm; rót vào xô
        dt = L.dac_trung([sp_dung, sp_sai, sp_trung, sp_phu])
        d = {k: L.diem(y, dt[k]) for k in dt}
        self.assertEqual(d["dung"], d["trung"])                  # khớp đích: +0,2 nhưng việc đã 1,0 → trần 1
        self.assertLess(d["sai"], d["trung"])
        self.assertLess(d["phu"], d["trung"])
        self.assertIn("sai đích ×0.7", L._cham(y, dt["sai"])[1]["he_so"])
        self.assertNotIn("sai đích ×0.7", L._cham(y, dt["trung"])[1]["he_so"])
        # cộng 0,2 chỉ khi việc đã khớp ở mức dưới 1 (việc đòi nằm ở vị trí phụ) và đích của CHÍNH việc đó khớp
        y2 = L.yeu_cau("Mở nắp.", req(viec=["rot"], dich=["phuy"]), "")
        a = L._cham(y2, L.dac_trung([canh("a", d=doan(viec=[va("cam_xem", "v1", None), va("rot", "v1", "phuy")]))])["a"])[0]
        b = L._cham(y2, L.dac_trung([canh("b", d=doan(viec=[va("cam_xem", "v1", "phuy"), va("rot", "v1", None)]))])["b"])[0]
        self.assertGreater(a, b)

    def test_diem_khong_vuot_100(self):
        d = doan(0, 9, hinh="Rót thuốc vào phuy rễ trắng lá vàng chai TC01", viec=[{"ma": "rot", "vat": "v1", "dich": "phuy"}],
                 cay={"ten": "ca_phe", "bo_phan": ["re", "la"], "giai_doan": "cay_con"}, dau_hieu=[{"ma": "la_vang", "tai": 2}],
                 nguoi={"kieu": "ngoi_noi", "mat_ro": True, "noi_vao_may": True})
        f = L.dac_trung([canh("tot", d=d)])["tot"]
        y = L.yeu_cau("Rót thuốc vào phuy.", req(viec=["rot"], dich=["phuy"], cay=["ca_phe"], bo_phan=["re"], dau_hieu=["la_vang"], can_sp="doc_ten", can_nguoi_noi=True,
                                                 tu_khoa=["rót", "phuy", "rễ trắng", "chai"], giay=3), "Rót thuốc vào phuy rễ trắng lá vàng chai TC01")
        s, info = L._cham(y, f)
        self.assertLessEqual(s, 100.0); self.assertGreater(s, 80)
        self.assertTrue(all(0 <= v <= 1 for v in info["tp"].values()), info["tp"])
        for net in (1, 2, 3):                                    # mọi mức nét: hệ số ≤ 1
            dd_ = copy.deepcopy(d); dd_["khung"]["net"] = net
            self.assertLessEqual(L._cham(y, L.dac_trung([canh("n", d=dd_)])["n"])[0], 100.0)

    def test_loai_cay_giu_hau_to(self):
        xoai = canh("xoai", d=doan(cay={"ten": "cay_an_trai:xoai", "bo_phan": ["trai"], "giai_doan": "ra_trai"}))
        tl = canh("tl", file="b.mp4", d=doan(cay={"ten": "cay_an_trai:thanh_long", "bo_phan": ["trai"], "giai_doan": "ra_trai"}))
        ho = canh("ho", file="c.mp4", d=doan(cay={"ten": "cay_an_trai", "bo_phan": ["trai"], "giai_doan": "ra_trai"}))        # chỉ biết họ
        ca = canh("ca", file="d.mp4", d=doan(cay={"ten": "ca_phe", "bo_phan": ["la"], "giai_doan": "truong_thanh"}))
        xx = L.dac_trung([xoai, tl, ho, ca])
        self.assertEqual(xx["xoai"]["cay"], "cay_an_trai:xoai")
        kq = L.ung_vien_v3([{"text": "Xoài ra trái đều."}], [req(cay=["cay_an_trai:xoai"], bo_phan=["trai"])], [""], [xoai, tl, ho, ca], nguong=(70, 20))
        got = {m["id"]: m for m in kq[0]}
        self.assertIn("xoai", got); self.assertNotIn("tl", got); self.assertNotIn("ca", got)     # sai loài → loại cứng
        self.assertEqual(got["xoai"]["nhan"], "dung")
        self.assertEqual(got.get("ho", {"nhan": "minh_hoa"})["nhan"], "minh_hoa")                # mới biết họ → không bao giờ ĐÚNG
        kq2 = L.ung_vien_v3([{"text": "Cây ăn trái ra hoa."}], [req(cay=["cay_an_trai"])], [""], [xoai, tl, ho, ca], nguong=(70, 5))
        self.assertTrue({"xoai", "tl", "ho"} <= set(ids(kq2)))                                    # câu chỉ họ: mọi loài trong họ đều hợp


class ChonTest(unittest.TestCase):
    def _gia(self, bang):
        return mock.patch.object(L, "_cham", lambda r, f: (bang[f["id"]], {"tp": {}, "he_so": [], "thieu_bb": []}))

    def test_nguong_49_50_69_70_va_met(self):
        bang = {"d49": 49.0, "d50": 50.0, "d69": 69.0, "d70": 70.0}
        shots = [canh(k, file=k + ".mp4") for k in bang]
        s = [{"text": "Rót thuốc vào bình."}]; y = [req(viec=["rot"], tu_khoa=["rót"])]
        with self._gia(bang):
            kq = L.ung_vien_v3(s, y, [""], shots)
            self.assertEqual([(m["id"], m["nhan"]) for m in kq[0]], [("d70", "dung"), ("d69", "minh_hoa"), ("d50", "minh_hoa")])    # 49 dưới sàn
            # mệt chỉ đổi thứ tự, không đổi điểm/nhãn, không kéo d49 lên, không làm rơi cảnh đã đạt
            kq = L.ung_vien_v3(s, y, [""], shots, met={"d70": 5, "d49": 0})
            self.assertEqual([m["id"] for m in kq[0]], ["d69", "d70", "d50"])
            self.assertEqual({m["id"]: (m["diem"], m["nhan"]) for m in kq[0]}["d70"], (70.0, "dung"))
            kq = L.ung_vien_v3(s, y, [""], shots, met={"d70": 100, "d69": 100, "d50": 100})
            self.assertEqual(set(ids(kq)), {"d70", "d69", "d50"})
            self.assertNotIn("d49", ids(kq))
            kq = L.ung_vien_v3(s, y, [""], shots, nguong=(80, 60))                                           # ngưỡng cấu hình khác
            self.assertEqual([(m["id"], m["nhan"]) for m in kq[0]], [("d70", "minh_hoa"), ("d69", "minh_hoa")])
            kq = L.ung_vien_v3(s, y, [""], shots, nguong=(40, 60))                                           # cấu hình sai → 70/50
            self.assertEqual([m["id"] for m in kq[0]], ["d70", "d69", "d50"])
            kq = L.ung_vien_v3(s, y, [""], shots, k=2)
            self.assertEqual(len(kq[0]), 2)

    def test_cau_thieu_co_muc_thieu_ro_rang(self):
        shots = [canh("a", d=doan(hinh="Chai TC01"))]
        kq = L.ung_vien_v3([{"text": "Rễ cà phê bung trắng."}], [req(viec=["cam_re"], cay=["ca_phe"], bo_phan=["re"], tu_khoa=["rễ trắng"])], [""], shots)
        self.assertEqual(len(kq[0]), 1)
        self.assertTrue(kq[0][0]["thieu"]); self.assertNotIn("id", kq[0][0])
        self.assertEqual(L.ung_vien_v3([{"text": "x"}], [req()], [""], [])[0][0]["thieu"], True)         # kho rỗng

    def test_y_hinh_rong_cau_vi_von_khong_bao_dung(self):
        cau, yc = "Mỗi ngày chỉ tốn bằng một ly cà phê thôi.", "Ly cà phê đặt trên bàn gỗ"
        ca_phe = canh("cp", d=doan(hinh="Cây cà phê xanh tốt trong vườn, ly cà phê trên bàn", viec=[{"ma": "khong", "vat": None, "dich": None}],
                                   cay={"ten": "ca_phe", "bo_phan": ["ca_cay"], "giai_doan": "truong_thanh"}))
        chai = canh("chai", file="b.mp4")
        for yh in (None, {}, [], [None], [{}], [{"viec": []}], "x"):
            kq = L.ung_vien_v3([{"text": cau}], yh, [yc], [ca_phe, chai], nguong=(70, 5))
            self.assertFalse(any(m.get("nhan") == "dung" for m in kq[0]), (yh, kq))
        r = L.yeu_cau(cau, {}, yc)
        self.assertTrue(r["suy"]); self.assertEqual(r["cay"], [])                  # "ly cà phê" là đồ uống, không phải cây
        r = L.yeu_cau("Phun thuốc lên lá ớt.", None, "Người phun bình lên lá ớt")
        self.assertEqual((r["suy"], r["cay"], r["viec"][:1]), (True, ["ot"], ["phun"]))
        # câu cụ thể + cảnh khớp hoàn toàn: dựng suy vẫn chỉ được MINH HỌA
        phun = canh("phun", d=doan(hinh="Người phun bình lên lá ớt", viec=[{"ma": "phun", "vat": "v3", "dich": None}], vat_thay=[], cay={"ten": "ot", "bo_phan": ["la"], "giai_doan": "truong_thanh"}))
        kq = L.ung_vien_v3([{"text": "Phun thuốc lên lá ớt."}], None, ["Người phun bình lên lá ớt"], [phun], nguong=(70, 30))
        self.assertEqual([(m["id"], m["nhan"]) for m in kq[0]], [("phun", "minh_hoa")])
        self.assertEqual(L.ung_vien_v3([{"text": "Phun thuốc lên lá ớt."}], [req(viec=["phun"], cay=["ot"], bo_phan=["la"], tu_khoa=["phun bình"])], [""], [phun])[0][0]["nhan"], "dung")
        # phủ định: "đừng phun" không đòi hình phun từ câu
        self.assertEqual(L.yeu_cau("Đừng phun thuốc bừa bãi.", None, "")["viec"], [])
        # cây nối tiếp: câu về bộ phận cây vừa nhắc
        self.assertEqual(L.yeu_cau("Rễ bung trắng.", None, "", cay_truoc=("ca_phe",))["cay"], ["ca_phe"])

    def test_hai_doan_moi_file_hoa_diem_co_seed(self):
        bang = {f"a{i}": 80.0 for i in range(4)} | {"b0": 80.0, "b1": 60.0}
        shots = [canh(k, file="a.mp4" if k.startswith("a") else "b.mp4") for k in bang]
        s = [{"text": "Rót thuốc vào bình."}]; y = [req(viec=["rot"])]
        with mock.patch.object(L, "_cham", lambda r, f: (bang[f["id"]], {"tp": {}, "he_so": [], "thieu_bb": []})):
            cac = set()
            for seed in range(20):
                kq = ids(L.ung_vien_v3(s, y, [""], shots, seed=seed))
                self.assertEqual(kq, ids(L.ung_vien_v3(s, y, [""], shots, seed=seed)))           # cùng seed → cùng kết quả
                self.assertEqual(sum(1 for i in kq if i.startswith("a")), 2)                     # ≤ 2 đoạn / file nguồn
                self.assertEqual(sum(1 for i in kq if i.startswith("b")), 2)
                self.assertIn("b0", kq)
                cac.add(tuple(i for i in kq if i.startswith("a")))
            self.assertGreater(len(cac), 1)                                                      # seed khác → hòa điểm ra cặp khác nhau
            kq = ids(L.ung_vien_v3(s, y, [""], shots, k=3))
            self.assertEqual(len(kq), 3)

    def test_nhan_theo_cau(self):
        chai = canh("chai")
        c1 = {"text": "Chai TC 01 đây."}; c2 = {"text": "Nhà nào cũng có một chai."}
        y = [req(viec=["cam_xem"], can_sp="doc_ten", tu_khoa=["chai"]), req(muc="minh_hoa", viec=["cam_xem"], can_sp="doc_ten", tu_khoa=["chai"])]
        kq = L.ung_vien_v3([c1, c2], y, ["", ""], [chai], nguong=(70, 20))
        self.assertEqual((kq[0][0]["id"], kq[0][0]["nhan"]), ("chai", "dung"))
        self.assertEqual((kq[1][0]["id"], kq[1][0]["nhan"]), ("chai", "minh_hoa"))              # cùng cảnh: ĐÚNG ở câu 0, chỉ MINH HỌA ở câu 1
        self.assertEqual(kq[0][0]["diem"], kq[1][0]["diem"])
        # nhãn không lẫn qua mệt
        kq = L.ung_vien_v3([c1, c2], y, ["", ""], [chai], nguong=(70, 20), met={"chai": 9})
        self.assertEqual([kq[0][0]["nhan"], kq[1][0]["nhan"]], ["dung", "minh_hoa"])

    def test_cau_bi_bo_moc_giong_khong_lech_y_hinh(self):
        text = "Ớt vàng lá nhiều. Câu giữa bị bỏ mốc giọng. Sầu riêng ra trái đều."
        sents = [{"text": "Ớt vàng lá nhiều.", "s": 0, "e": 1}, {"text": "Sầu riêng ra trái đều.", "s": 2, "e": 3}]
        self.assertEqual(dd.chi_so_goc(text, sents), [0, 2])                                   # dóng theo câu gốc, không nén
        with self.assertRaises(ValueError):
            dd.chi_so_goc(text, [{"text": "Câu lạ."}])
        ot = canh("ot", file="o.mp4", d=doan(hinh="Lá ớt vàng", cay={"ten": "ot", "bo_phan": ["la"], "giai_doan": "truong_thanh"}))
        cp = canh("cp", file="c.mp4", d=doan(hinh="Cây cà phê", cay={"ten": "ca_phe", "bo_phan": ["la"], "giai_doan": "truong_thanh"}))
        sr = canh("sr", file="s.mp4", d=doan(hinh="Sầu riêng ra trái", cay={"ten": "sau_rieng", "bo_phan": ["trai"], "giai_doan": "ra_trai"}))
        yh = [req(cay=["ot"], bo_phan=["la"]), req(cay=["ca_phe"], bo_phan=["la"]), req(cay=["sau_rieng"], bo_phan=["trai"])]           # y_hinh theo 3 câu GỐC
        kq = L.ung_vien_v3([dict(s, i=i) for s, i in zip(sents, dd.chi_so_goc(text, sents))], yh, ["", "", ""], [ot, cp, sr], nguong=(70, 20))
        self.assertEqual(set(kq), {0, 2})
        self.assertEqual(ids(kq, 0), ["ot"]); self.assertEqual(ids(kq, 2), ["sr"])             # nén mảng sẽ lấy y_hinh[1] (cà phê) cho câu sầu riêng
        nen = L.ung_vien_v3(sents, yh, ["", "", ""], [ot, cp, sr], nguong=(70, 20))             # đối chứng: không có "i" thì tra theo vị trí → lệch
        self.assertEqual(ids(nen, 1), ["cp"])

    def test_nguong_cau_hinh_sai_quay_ve_mac_dinh(self):
        for xau in ((40, 60), (101, 50), (70, 70), ("a", 50), (70, -1), (None, None), (float("nan"), 1), (True, 50), None, 5, (80,)):
            self.assertEqual(L.chuan_nguong(xau), (70, 50), xau)
        self.assertEqual(L.chuan_nguong((80, 60)), (80, 60)); self.assertEqual(L.chuan_nguong((100, 0)), (100, 0))
        cfg = lambda c: mock.patch.object(dd, "cfg_hub", lambda: {"dao_dien": c})
        with cfg({"loc_v3_dung": 40, "loc_v3_minh_hoa": 60}):
            self.assertEqual(dd.nguong_loc_v3(), (70, 50))
        with cfg({"loc_v3_dung": "cao", "loc_v3_minh_hoa": 55}):
            self.assertEqual(dd.nguong_loc_v3(), (70, 50))
        with cfg({"loc_v3_dung": 85, "loc_v3_minh_hoa": 55}):
            self.assertEqual(dd.nguong_loc_v3(), (85, 55))
        with cfg({"loc_v3_dung": 90}):
            self.assertEqual(dd.nguong_loc_v3(), (90, 50))
        with cfg({"loc_v3_minh_hoa": 75}):                                                       # chỉ đặt sàn 75 ≥ mặc định 70 → cặp sai → cả hai về mặc định
            self.assertEqual(dd.nguong_loc_v3(), (70, 50))
        with mock.patch.object(dd, "cfg_hub", lambda: 1 / 0):
            self.assertEqual(dd.nguong_loc_v3(), (70, 50))
        with mock.patch.object(dd, "cfg_hub", lambda: {}):
            self.assertEqual(dd.nguong_loc_v3(), (70, 50))

    def test_dac_trung_mot_lan_va_cache(self):
        a = canh("a"); b = canh("a", file="khac.mp4")                                           # id trùng: chỉ tính cái đầu
        dt = L.dac_trung([a, b])
        self.assertEqual(list(dt), ["a"]); self.assertEqual(dt["a"]["file"], "a.mp4")
        with mock.patch.object(L, "_dac_trung_mot", side_effect=AssertionError("tính lại")):
            self.assertIs(L.dac_trung([a], dt), dt)                                              # đã có trong cache → không tính lại
            L.ung_vien_v3([{"text": "Chai."}], [req(viec=["cam_xem"])], [""], [a], dt=dt)
        f = L.dac_trung([canh("s", d=doan(chu_dan=[{"noi_dung": "mẹo", "loai": "phu_de", "che_chu_the": True}], nguoi={"kieu": "ngoi_noi", "mat_ro": True, "noi_vao_may": True}))])["s"]
        self.assertTrue(f["chu"] and f["chu_che"] and f["noi_vao_may"] and f["sp_doc"] and f["sp_thay"])
        self.assertIn("chai", f["tok"]); self.assertNotIn("TC", f["tok"])


# ---------------------------------------------------------------- chạy bóng trong đạo diễn / ekip
def _loi(n=4):
    cau = ["Rót thuốc vào bình phun.", "Chai TC 01 rõ nhãn.", "Ớt vàng lá hồi phục.", "Đặt hàng ngay hôm nay."][:n]
    words, t = [], 0.0
    for c in cau:
        for w in c.split():
            words.append({"w": w, "s": round(t, 2), "e": round(t + 0.3, 2)}); t += 0.35
    return {"text": " ".join(cau), "words": words, "dur": round(t, 2)}, cau


def _kho_bong():
    d = doan
    return [canh("0000", "a.mp4", d(0, 4, hinh="Rót thuốc vào bình phun", viec=[{"ma": "rot", "vat": "v1", "dich": "binh_phun"}])),
            canh("0001", "b.mp4", d(0, 4)),
            canh("0002", "c.mp4", d(0, 4, hinh="Lá ớt vàng", viec=[{"ma": "di_xem", "vat": None, "dich": None}], vat_thay=[], cay={"ten": "ot", "bo_phan": ["la"], "giai_doan": "truong_thanh"},
                                dau_hieu=[{"ma": "la_vang", "tai": 1}])),
            canh("0003", "d.mp4", d(0, 4, hinh="Vườn ớt xanh", viec=[{"ma": "di_xem", "vat": None, "dich": None}], vat_thay=[], cay={"ten": "ot", "bo_phan": ["ca_vuon"], "giai_doan": "truong_thanh"})),
            canh("0004", "e.mp4", d(0, 4, hinh="Giá 100k trên chai", gia_qua={"chu_dan": [{"tu": 0, "den": 2, "trich": None}], "tren_vat": [], "loi": []}))]     # cảnh cấm


class BongTest(unittest.TestCase):
    def _chay(self, kho_v3, y_hinh="co"):
        voice, cau = _loi()
        sc = {"y_canh": ["Bình phun", "Chai rõ nhãn", "Lá ớt vàng", "Chai"], "y_hinh": [req(viec=["rot"], dich=["binh_phun"], tu_khoa=["bình phun"]), req(can_sp="doc_ten", viec=["cam_xem"]),
                                                                                      req(cay=["ot"], dau_hieu=["la_vang"]), {}] if y_hinh == "co" else None}
        sp = {"ten_goi": "TC 01", "kho_v3": kho_v3} if kho_v3 is not None else {"ten_goi": "TC 01"}
        rng, boi = random.Random(7), {}
        ctx, sents, total, idl = dd.ctx_dao_dien("tbong", sp, voice, sc, copy.deepcopy(_kho_bong()), "tvc_cao_cap", rng, ra_boi=boi)
        return ctx, sents, idl, boi, rng.random()

    def test_bong_khong_doi_lua_chon(self):
        tat = self._chay(False)
        bat = self._chay(True)
        self.assertEqual(tat[0]["goi_y"], bat[0]["goi_y"]); self.assertEqual(tat[0]["ds"], bat[0]["ds"]); self.assertEqual(tat[2], bat[2])   # ứng viên giữ nguyên
        self.assertEqual(tat[4], bat[4])                                                        # bộ sinh số ngẫu nhiên của video không bị tiêu thụ thêm
        self.assertNotIn("bong_v3", tat[3]); self.assertNotIn("bong_v3", self._chay(None)[3])   # kho_v3 tắt/thiếu → không làm thêm gì
        self.assertEqual(tat[3].keys() | {"bong_v3"}, bat[3].keys())
        b = bat[3]["bong_v3"]
        self.assertNotIn("loi", b)
        per = json.loads(bat[0]["goi_y"])
        self.assertEqual([c["i"] for c in b["cau"]], [0, 1, 2, 3])
        for j, c in enumerate(b["cau"]):
            self.assertEqual(c["cu"], per[str(j)])                                              # ứng viên cũ ghi đúng như đạo diễn nhận
        c0, c3 = b["cau"][0], b["cau"][3]
        self.assertEqual(c0["moi"][0]["id"], "0000"); self.assertEqual(c0["moi"][0]["nhan"], "dung")
        self.assertNotIn("0004", {m["id"] for c in b["cau"] for m in c["moi"]})                # cảnh giá trên hình không bao giờ lọt
        self.assertTrue(c3["co_y_hinh"] is False and all(m["nhan"] == "minh_hoa" for m in c3["moi"]))   # {} → dựng suy → không ĐÚNG
        self.assertEqual(b["nguong"], {"dung": 70, "minh_hoa": 50})
        self.assertGreaterEqual(b["ms"], 0); self.assertEqual(b["kho"], {"tong": 5, "kieu3_dung_duoc": 4})
        json.dumps(b, ensure_ascii=False)
        # ghi file cạnh video: _kem/<tên>.bong-loc-v3.json; tắt → không có file
        mp4 = Path(tempfile.mkdtemp(prefix="xv-bong-")) / "video-01.mp4"
        f = dd.ghi_bong_v3(b, mp4)
        self.assertEqual(f, mp4.parent / "_kem" / "video-01.bong-loc-v3.json")
        self.assertEqual(json.loads(f.read_text(encoding="utf-8"))["cau"][0]["moi"][0]["id"], "0000")
        mp4b = Path(tempfile.mkdtemp(prefix="xv-bong-")) / "video-02.mp4"
        self.assertIsNone(dd.ghi_bong_v3(tat[3].get("bong_v3"), mp4b))
        self.assertFalse((mp4b.parent / "_kem").exists())

    def test_bong_thieu_y_hinh_va_loi_khong_lam_hong_job(self):
        self.assertEqual(self._chay(True, y_hinh=None)[0]["goi_y"], self._chay(False, y_hinh=None)[0]["goi_y"])
        b = self._chay(True, y_hinh=None)[3]["bong_v3"]
        self.assertTrue(all(c["co_y_hinh"] is False for c in b["cau"]))
        with mock.patch.object(L, "bong", side_effect=RuntimeError("hỏng")):                     # lỗi trong bộ lọc mới → job vẫn chạy, lựa chọn không đổi
            hong = self._chay(True)
        self.assertIn("RuntimeError", hong[3]["bong_v3"]["loi"])
        self.assertEqual(hong[0]["goi_y"], self._chay(False)[0]["goi_y"])
        bi_chan = Path(tempfile.mkdtemp(prefix="xv-bong-")) / "tep"
        bi_chan.write_text("x")
        self.assertIsNone(dd.ghi_bong_v3({"ban": 1}, bi_chan / "v.mp4"))                         # không ghi được → nuốt lỗi


if __name__ == "__main__":
    unittest.main()
