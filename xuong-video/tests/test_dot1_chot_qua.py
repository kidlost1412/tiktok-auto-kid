"""Đợt 1 chốt quà: thẻ chốt luôn là MỘT mức quà thật (đổi chữ/kiểu theo video), cùng quà ở cảnh + máy kiểm, đoạn chốt giữ cảnh quà,
khối so_dem chỉ nhận số (kèm đơn vị) có trong sự thật sản phẩm, bảng CT_HOP theo khoá THAN mới. Không AI/mạng/ffmpeg."""
import os, random, re, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-chotqua-"))
ENG = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENG))

import cong_thuc as CT  # noqa: E402
import dao_dien as DD  # noqa: E402
import kiem_may as km  # noqa: E402

QUA = ["Mua 1 can tặng 1 gói kali bo trị giá 30k", "Mua 2 can tặng 1 chai TC01 trị giá 120k", "Mua 5 can tặng 1 can 5 lít đạm cá"]
FPS = 30


def lieu(n=44, dt=0.42):
    words = [{"w": f"t{i}", "s": round(i * dt, 3), "e": round(i * dt + dt * 0.9, 3)} for i in range(n)]
    sents = []
    for k in range(0, n, 8):
        ws = words[k:k + 8]
        sents.append({"s": ws[0]["s"], "e": ws[-1]["e"], "words": ws})
    return words, sents, round(n * dt + 0.6, 2)


def xep(khoi=None, st=None, seed=3, recipe="danh_sach"):
    words, sents, total = lieu()
    st = {} if st is None else st
    return CT.xep_khoi(recipe, khoi, sents, total, st, random.Random(seed), "BỌ TRĨ TOP ONE", words)[0], st


class ChonQuaTest(unittest.TestCase):
    def test_loi_nhac_muc_nao_chon_muc_do(self):
        st = {"_qua": list(QUA)}
        self.assertEqual(CT.chon_qua(st, "Hôm nay mua hai can tặng chai TC01 nha bà con", random.Random(1)), QUA[1])
        self.assertEqual(st["_qua_chon"], QUA[1])
        st = {"_qua": list(QUA)}
        self.assertEqual(CT.chon_qua(st, "mua 1 can tặng gói kali bo", random.Random(9)), QUA[0])

    def test_khong_nhac_bat_mot_lan_va_dung_lai(self):
        st = {"_qua": list(QUA)}
        a = CT.chon_qua(st, "Bấm giỏ hàng ngay", random.Random(4))
        self.assertIn(a, QUA)
        for s in range(10):                                   # mọi bước sau cùng một lựa chọn, bất kể rng/lời
            self.assertEqual(CT.chon_qua(st, "mua 5 can tặng can 5 lít đạm cá", random.Random(s)), a)

    def test_theo_canh_qua_o_doan_chot(self):
        st = {"_qua": list(QUA), "_qua_canh": ["TC01"]}
        self.assertEqual(CT.chon_qua(st, "", random.Random(2)), QUA[1])

    def test_khong_co_qua(self):
        self.assertEqual(CT.chon_qua({"_qua": []}, "mua 2 can", random.Random(1)), "")
        self.assertIsNone(CT.chot_qua({}, "", random.Random(1)))


class DongQuaTest(unittest.TestCase):
    def test_giu_dieu_kien_va_mon_qua(self):
        for s in range(30):
            d = CT.dong_qua(QUA[1], random.Random(s))
            self.assertLessEqual(len(d), 26)
            self.assertIn("CHAI TC01", d); self.assertIn("2", d)

    def test_nhieu_cach_noi(self):
        ds = {CT.dong_qua(QUA[1], random.Random(s)) for s in range(40)}
        self.assertGreaterEqual(len(ds), 2)
        self.assertIn("MUA 2 CAN TẶNG 1 CHAI TC01", ds)      # bỏ giá trị cho vừa 26; còn đủ chỗ thì giữ "1 "

    def test_qua_dai_bi_cat_van_giu_mon(self):
        e = "Mua 10 can tặng 1 chai TC01 phun sương cao cấp trị giá 500k"
        for s in range(30):
            d = CT.dong_qua(e, random.Random(s))
            self.assertLessEqual(len(d), 26); self.assertIn("TC01", d)

    def test_qua_khong_co_dieu_kien_mua(self):
        self.assertEqual(CT.dong_qua("Tặng 1 túi hạt giống", random.Random(1)), "TẶNG 1 TÚI HẠT GIỐNG")


class TheChotTest(unittest.TestCase):
    def chot(self, st, seed=3, khoi=None):
        bl, st = xep(khoi, st, seed)
        return bl[-1], st

    def test_loi_im_van_co_qua_that(self):
        c, st = self.chot({"_qua": list(QUA)})
        self.assertIn(c["loai"], CT.CHOT_QUA)
        self.assertNotEqual(c["loai"], "nut_gio_hang")
        thanh = " ".join(str(v) for v in c["data"].values()).upper()
        if c["loai"] == "bang_qua":
            self.assertEqual(c["data"]["cac_muc"], QUA)
        else:
            _, tu = CT._muc_qua(st["_qua_chon"])
            self.assertTrue(any(w.upper() in thanh for w in tu), thanh)          # có tên món quà thật của mức đã chọn

    def test_lenh_nhac_muc_quà(self):
        words, sents, total = lieu()
        for s in sents:
            s["text"] = "hôm nay mua hai can tặng chai TC01"
        st = {"_qua": list(QUA)}
        bl = CT.xep_khoi("danh_sach", None, sents, total, st, random.Random(5), "X", words)[0]
        self.assertEqual(st["_qua_chon"], QUA[1])
        if bl[-1]["loai"] != "bang_qua":
            self.assertIn("TC01", bl[-1]["data"]["dong1"])

    def test_nhieu_hat_giong_khac_cach_noi_hoac_kieu(self):
        kieu, dong1 = set(), set()
        for s in range(40):
            c, _ = self.chot({"_qua": [QUA[1]]}, seed=s)
            kieu.add(c["loai"]); dong1.add(c["data"]["dong1"])
        self.assertGreaterEqual(len(kieu), 2); self.assertGreaterEqual(len(dong1), 2)
        self.assertLessEqual(kieu, set(CT.CHOT_QUA))

    def test_dao_dien_chot_khong_chu_qua_van_dien_dong1(self):
        k = [{"loai": "nut_gio_hang", "du_lieu": {"text": "BẤM GIỎ HÀNG"}}]
        c, st = self.chot({"_qua": [QUA[1]]}, khoi=k)
        self.assertEqual(c["loai"], "nut_gio_hang")                          # giữ kiểu đạo diễn chọn
        self.assertIn("TC01", c["data"]["dong1"])

    def test_khong_co_qua_giu_chu_cu(self):
        c, _ = self.chot({}, seed=1)
        self.assertEqual(c["data"]["dong1"], "QUÀ TẶNG THEO ĐƠN")

    def test_header_tren_cua_dung_remotion(self):
        qua = CT.chot_qua({"_qua": list(QUA)}, "", random.Random(1))
        self.assertIn(qua["header"], CT.HEADER_QUA)
        self.assertGreaterEqual(len(set(CT.chot_qua({"_qua": list(QUA)}, "", random.Random(s))["header"] for s in range(30))), 2)
        tsx = (ENG.parent / "remotion" / "src" / "hub" / "HubVideo.tsx").read_text(encoding="utf-8")
        self.assertIn("c.header ??", tsx)


# ---------------------------------------------------------------- cảnh quà: ứng viên, đoạn chốt, máy kiểm
def canh(i, vai=("chai_ro",), **kw):
    s = {"id": i, "file": f"{i}.mp4", "tu": 0.0, "den": 6.0, "dai": 6.0, "dep": [1.0, 5.0], "vai_tro": list(vai), "mo_ta": f"cảnh {i}",
         "soat": {"dep": 4, "mat": 0, "chu_muc": 0, "nhan": None}}
    s.update(kw)
    return s


def kho(n=24):
    vai = [["chai_ro"], ["phun"], ["vuon"], ["re"]]
    return [canh(f"{i + 1:03d}", vai[i % 4]) for i in range(n)]


CAU = ["Chai này pha rất dễ", "Phun lên lá vườn buổi sáng", "Rễ trắng ra nhiều", "Vườn xanh tốt hơn", "Đặt chai trong giỏ hàng ngay"]


def sents(n=5):
    return [{"text": CAU[k % len(CAU)], "s": k * 3.0, "e": k * 3.0 + 2.8} for k in range(n)]


def qua_kho():
    return {"tc01": [canh(f"Q-sp2-{j}", ("chai_ro", "qua_tang"), qua_tu_khoa="tc01") for j in range(4)]}


class CanhQuaTest(unittest.TestCase):
    def test_cau_chot_luon_co_ung_vien_qua(self):
        s = sents()
        per, chon, _ = DD.chon_ung_vien("t1", s, [""] * 5, kho(), random.Random(1), qua=qua_kho(), hub=Path(tempfile.mkdtemp()))
        self.assertTrue(any(str(i).startswith("Q-") for i in per[-1]))      # câu chốt không nhắc quà vẫn có Q-
        self.assertFalse(any(str(i).startswith("Q-") for p in per[:-1] for i in p))   # câu giữa không nhắc quà thì không

    def test_loi_nhac_mon_nao_chi_mon_do(self):
        s = sents(); s[1]["text"] = "Hôm nay tặng kèm chai tc01"
        q = qua_kho(); q["kali"] = [canh(f"Q-sp3-{j}", ("chai_ro", "qua_tang"), qua_tu_khoa="kali") for j in range(3)]
        per, _, _ = DD.chon_ung_vien("t1", s, [""] * 5, kho(), random.Random(1), qua=q, hub=Path(tempfile.mkdtemp()))
        self.assertTrue(all("kali" not in str(i) and "sp3" not in str(i) for p in per for i in p))
        self.assertTrue(any("sp2" in str(i) for i in per[-1]))

    def _segs(self, chinh_chot, bo_cuc="day", phu=None):
        shots = kho() + qua_kho()["tc01"]
        doan = [{"cau": k, "canh": [{"id": f"{k + 1:03d}" if k % 4 else f"{k + 2:03d}", "bo_cuc": "day"}]} for k in range(4)]
        ct = {"id": chinh_chot, "bo_cuc": bo_cuc}
        if phu:
            ct["phu"] = phu
        doan.append({"cau": 4, "canh": [ct]})
        return DD.segs_tu_bang({"doan": doan}, sents(), 15.3, shots)[0]

    def test_chot_chinh_la_canh_qua_thi_chai_chinh_va_qua_o_phu(self):
        segs = self._segs("Q-sp2-0")
        cuoi = segs[-1]
        self.assertFalse(str(cuoi["shot"]["id"]).startswith("Q-"))
        self.assertTrue(DD.la_chai(cuoi["shot"]))
        self.assertEqual([p["id"] for p in cuoi["phu_shots"]], ["Q-sp2-0"])
        self.assertGreaterEqual(DD.BC.so_phu_toi_da(cuoi["bo_cuc"]), 1)
        self.assertNotIn(cuoi["bo_cuc"], ("pip_troi", "pip_giua"))
        self.assertNotIn("chot_qua", {x["muc"] for x in km.kiem(segs, sents(), co_qua=True, co_canh_qua=True)})
        self.assertNotIn("chot_chai", {x["muc"] for x in km.kiem(segs, sents(), co_qua=True, co_canh_qua=True)})

    def test_quà_o_phu_cung_duoc_giu(self):
        segs = self._segs("005", bo_cuc="khung_mo", phu=None)
        segs2 = self._segs("Q-sp2-1", bo_cuc="pip_troi")
        self.assertEqual([p["id"] for p in segs2[-1]["phu_shots"]], ["Q-sp2-1"])
        self.assertFalse(segs[-1]["phu_shots"] and str(segs[-1]["phu_shots"][0]["id"]).startswith("Q-"))

    def test_may_kiem_ap_dung_ca_khi_loi_im(self):
        s = sents()                                       # câu chốt "Đặt chai trong giỏ hàng ngay": không nhắc quà
        shots = kho()
        segs = [{"shot": shots[0], "dur": 3.0, "bo_cuc": "day", "cau": 3, "src_start": 0, "phu_shots": []},
                {"shot": shots[4], "dur": 3.0, "bo_cuc": "day", "cau": 4, "src_start": 0, "phu_shots": []}]
        co = lambda **k: {x["muc"] for x in km.kiem(segs, s, **k)}
        self.assertIn("chot_qua", co(co_qua=True, co_canh_qua=True))          # kho có cảnh quà mà đoạn chốt không có → lỗi, dù lời im
        self.assertNotIn("chot_qua", co(co_qua=True, co_canh_qua=False))      # kho không có cảnh quà + lời im → không phạt
        self.assertNotIn("chot_qua", co(co_qua=False, co_canh_qua=True))      # sản phẩm không tặng quà
        segs[-1]["phu_shots"] = [qua_kho()["tc01"][0]]
        self.assertNotIn("chot_qua", co(co_qua=True, co_canh_qua=True))

    def test_chai_qua_khong_tinh_la_chai_san_pham(self):
        q = qua_kho()["tc01"][0]
        segs = [{"shot": q, "dur": 3.0, "bo_cuc": "day", "cau": 4, "src_start": 0, "phu_shots": []}]
        self.assertIn("chot_chai", {x["muc"] for x in km.kiem(segs, sents(), co_qua=True, co_canh_qua=True)})

    def test_cau_hoi_giam_khao_khong_cho_phep_bo_qua_vi_im(self):
        hoi = dict((m[0], m[1]) for m in km.MUC)["chot_qua"]
        self.assertIn("DÙ lời đọc im", hoi)


# ---------------------------------------------------------------- so_dem
class SoDemTest(unittest.TestCase):
    ST = {"_so_that": ["Một chai pha được 200 lít nước", "Giảm 20% công phun", "Mỗi nắp 1,12 ml", "Phun được 15.000 lít mỗi ha"], "_qua": [QUA[1]]}

    def khoi(self, so, don_vi, st=None, loai="so_dem"):
        bl, _ = xep([{"loai": loai, "tu": 12, "den": 16, "du_lieu": {"nhan_trai": "1 CHAI", "so": so, "don_vi": don_vi}}], dict(st if st is not None else self.ST), recipe="con_so")
        return [b for b in bl if b["loai"] in ("so_dem", "chu_so")]

    def test_dung_so_va_don_vi(self):
        b = self.khoi(200, "LÍT")
        self.assertEqual(len(b), 1); self.assertEqual((b[0]["loai"], b[0]["data"]["so"]), ("so_dem", 200))
        self.assertEqual(self.khoi(20, "%")[0]["loai"], "so_dem")

    def test_dung_so_sai_don_vi_bi_bo(self):
        self.assertEqual(self.khoi(20, "LÍT"), [])                      # 20% ≠ 20 lít
        self.assertEqual(self.khoi(200, "%"), [])
        self.assertEqual(self.khoi(300, "LÍT"), [])                     # số cũ trong tập chung nhưng không có trong sự thật SP này

    def test_dau_cham_nhom_nghin(self):
        b = self.khoi("15.000", "LÍT")
        self.assertEqual(b[0]["data"]["so"], 15000)

    def test_thap_phan_khong_thanh_112(self):
        self.assertIsNone(CT.clean_data("so_dem", {"so": "1,12", "don_vi": "ML"}, CT.so_cho_phep(self.ST)))
        b = self.khoi("1,12", "ML")                                      # đúng sự thật nhưng không phải số nguyên → chữ số to tĩnh
        self.assertEqual((b[0]["loai"], b[0]["data"]["so"]), ("chu_so", "1,12"))
        self.assertEqual(self.khoi("1,12", "LÍT"), [])                   # sai đơn vị → bỏ hẳn
        self.assertEqual(self.khoi(112, "ML"), [])

    def test_so_trong_qua_cung_hop_le(self):
        self.assertEqual(self.khoi(120, "K")[0]["data"]["so"], 120)      # "trị giá 120k"
        self.assertEqual(self.khoi(2, "CAN")[0]["data"]["so"], 2)
        self.assertEqual(self.khoi(1, "")[0]["data"]["so"], 1)           # thiếu đơn vị: chỉ cần số có trong sự thật

    def test_ma_san_pham_khong_thanh_so(self):
        self.assertEqual(self.khoi(1, "CAN", st={"_qua": ["Tặng 1 chai TC01"]}), [])      # "TC01" không sinh số 01 kèm đơn vị CAN

    def test_khong_co_du_kien_thi_dung_tap_cu(self):
        self.assertEqual(self.khoi(15000, "LÍT", st={})[0]["data"]["so"], 15000)
        self.assertEqual(self.khoi(777, "LÍT", st={}), [])


# ---------------------------------------------------------------- CT_HOP + nhạc chết
class CtHopTest(unittest.TestCase):
    def test_khoa_moi_cua_than(self):
        for k in ("van_de_giai_phap", "ba_sai_lam", "so_sanh", "go_ngai", "phep_tinh", "tung_buoc", "khach_hoi", "dau_hieu", "vi_sao"):
            ds = CT.ct_hop(k)
            self.assertTrue(ds and set(ds) <= set(CT.RECIPES), k)
        self.assertEqual(CT.ct_hop("go_ngai")[0], "so_sanh")
        self.assertIn("ke_chuyen", CT.ct_hop("vi_sao"))

    def test_khoa_cu_van_chay_va_khoa_la_thi_tat_ca(self):
        self.assertEqual(CT.ct_hop("truoc_sau")[0], "so_sanh")
        self.assertEqual(CT.ct_hop("khoa_khong_co"), list(CT.RECIPES))
        self.assertEqual(CT.ct_hop(None), list(CT.RECIPES))

    def test_goc_qua_tang_them_qua_tang(self):
        self.assertIn("qua_tang", CT.ct_hop("so_sanh", "qua-tang"))
        self.assertEqual(CT.ct_hop(None, "qua-tang"), ["qua_tang"])
        self.assertNotIn("qua_tang", CT.ct_hop("so_sanh", "tiet-kiem"))




if __name__ == "__main__":
    unittest.main()
