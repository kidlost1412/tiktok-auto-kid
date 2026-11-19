"""Việc trực tiếp cho Khu Tự Trị (engine/truc_tiep.py): bóc dòng người đọc được từ chữ model đang stream, file việc (ghi nguyên tử, giãn cách,
dọn hạn), công tắc tắt, việc hiện tại theo luồng."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
for p in (str(GOC / "engine"), str(GOC / "app")):
    if p not in sys.path:
        sys.path.insert(0, p)

import truc_tiep as T  # noqa: E402


def trich(s, buoc=1):
    """Đưa s vào bộ bóc từng mảnh `buoc` ký tự → (các dòng xong theo thứ tự, bộ bóc)."""
    e, ra = T.TrichDong(), []
    for i in range(0, len(s), buoc):
        e.them(s[i:i + buoc])
        ra += e.lay_moi()
    return ra, e


KICH_BAN = ('```json\n[{"goc":"cong-dung","text":"[giọng ấm] Vườn cà phê cần phun. Nano Đồng đây nhé! Mua ngay hôm nay để nhận quà tặng kèm rất to.",'
            '"hashtag":["#nano","#chongsau"],"caption":["Chống sâu hiệu quả sau 3 ngày"],"id":"abc_def_ghi_jkl_mno",'
            '"hook_thu":[{"text":"Cây héo vì sâu, anh biết chưa","diem":8}],"url":"http://x.com/a b c d e f g","duong":"C:\\\\Users\\\\Admin\\\\kho\\\\a b c.mp4"}]\n```\n'
            'Hy vọng giúp ích cho anh nhé.')


class TrichDongTest(unittest.TestCase):
    def test_json_bo_khoa_ma_duong_dan_link_hashtag_con_loi_va_cau(self):
        mong = ["Vườn cà phê cần phun.", "Nano Đồng đây nhé!", "Mua ngay hôm nay để nhận quà tặng kèm rất to.",
                "Chống sâu hiệu quả sau 3 ngày", "Cây héo vì sâu, anh biết chưa", "Hy vọng giúp ích cho anh nhé."]
        for buoc in (1, 2, 5, 11, 1000):                     # chia mảnh kiểu nào cũng ra đúng một kết quả (kể cả cắt giữa chuỗi / giữa escape)
            ra, e = trich(KICH_BAN, buoc)
            e.het(); ra += e.lay_moi()
            self.assertEqual(ra, mong, f"buoc={buoc}")
            self.assertEqual(e.ky_tu, len(KICH_BAN))

    def test_dang_go_la_chuoi_dang_go_do_va_cau_xong_vao_dong_ngay(self):
        e = T.TrichDong()
        e.them('[{"text":"Vườn cà phê cần phun. Nano Đồng đ')
        self.assertEqual(e.lay_moi(), ["Vườn cà phê cần phun."])       # câu xong chuyển vào dong trước khi hết chuỗi
        self.assertEqual(e.dang_go, "Nano Đồng đ")
        e.them('ây nhé! Mua ngay')
        self.assertEqual(e.lay_moi(), ["Nano Đồng đây nhé!"])
        self.assertEqual(e.dang_go, "Mua ngay")
        e.them('."}]')
        self.assertEqual(e.lay_moi(), ["Mua ngay."])
        self.assertIsNone(e.dang_go)

    def test_khoa_dang_go_do_khong_thanh_dang_go(self):
        e = T.TrichDong()
        e.them('{"hook_thu_cua_bien_kich_rat_dai_dong')
        self.assertIsNone(e.dang_go)
        self.assertEqual(e.lay_moi(), [])

    def test_escape_unicode_cap_thay_the_xuong_dong(self):
        ra, e = trich('{"t":"Xin chào \\"anh\\" \\u00f4ng \\ud83d\\ude00 nhé.\\nCảm ơn nhiều lắm."}', 3)
        self.assertEqual(ra, ['Xin chào "anh" ông 😀 nhé.', "Cảm ơn nhiều lắm."])
        e2 = T.TrichDong()                                  # cặp thay thế bị cắt đôi giữa hai mảnh: chưa ra chữ rác
        e2.them('{"t":"Xin chào bạn \\ud83d')
        self.assertNotIn("\ud83d", e2.dang_go or "")
        e2.them('\\ude00 nhé"}')
        self.assertEqual(e2.lay_moi(), ["Xin chào bạn 😀 nhé"])

    def test_chu_thuong_theo_dong_va_cau(self):
        ra, e = trich("Đây là kết quả của anh:\n- Dòng thứ nhất khá là dài nè.\n2. Dòng hai cũng khá dài nhé\nxin", 4)
        self.assertEqual(ra, ["Đây là kết quả của anh:", "Dòng thứ nhất khá là dài nè.", "Dòng hai cũng khá dài nhé"])
        self.assertIsNone(e.dang_go)                         # "xin" ngắn hơn 12 ký tự: chưa đáng hiện
        ra, e = trich("Một câu mở đầu thôi nhé. Câu thứ hai đang gõ", 6)
        self.assertEqual(ra, ["Một câu mở đầu thôi nhé."])
        self.assertEqual(e.dang_go, "Câu thứ hai đang gõ")
        e.het()
        self.assertEqual(e.lay_moi(), ["Câu thứ hai đang gõ"])

    def test_chu_thuong_roi_json_bo_ca_dau_rao(self):
        ra, e = trich('Dưới đây là kết quả anh cần:\n{"text": "Nano Đồng chống sâu cực nhanh.", "id": "a_b_c_d_e_f"}\nCảm ơn anh đã đợi nhé.', 7)
        e.het(); ra += e.lay_moi()
        self.assertEqual(ra, ["Dưới đây là kết quả anh cần:", "Nano Đồng chống sâu cực nhanh.", "Cảm ơn anh đã đợi nhé."])

    def test_the_trong_chu_thuong_khong_bi_nham_voi_json(self):
        ra, e = trich("[giọng ấm] Xin chào anh nhé, hôm nay có quà.\n", 5)
        self.assertEqual(ra, ["Xin chào anh nhé, hôm nay có quà."])

    def test_cau_dai_bi_chia_duoi_200(self):
        dai = ", ".join(["một đoạn khá dài của câu nói"] * 12) + "."
        ra, e = trich(json.dumps({"text": dai}, ensure_ascii=False), 50)
        e.het(); ra += e.lay_moi()
        self.assertGreaterEqual(len(ra), 2)
        self.assertTrue(all(len(x) <= 200 for x in ra))

    def test_la_van_xuoi(self):
        for x in ("Vườn cà phê cần phun", "Giá chỉ 99k, mua 2 tặng 1"):
            self.assertTrue(T.la_van_xuoi(x), x)
        for x in ("cong_thuc_chuyen_canh", "a1b2c3d4e5f6a7b8", "https://x.com/a b c d e f", "C:\\Users\\a\\b c d e f.mp4", "ngan", "#nano #chongsau #kho",
                  "12345 67890 12345", "tc01_goc_dd_x a_b_c_d_e", "{\"a\": 1, \"b\": 2}"):
            self.assertFalse(T.la_van_xuoi(x), x)


class DongHoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cu = (T._THU_MUC, T.GIAN_CACH, T.NHIP_GIAY)
        T._THU_MUC = self.tmp.name
        T.GIAN_CACH = 0.0
        T._don_cuoi[0] = 0.0
        self.d = Path(self.tmp.name)

    def tearDown(self):
        T._THU_MUC, T.GIAN_CACH, T.NHIP_GIAY = self.cu
        for t in list(T._MO):
            t.xong()
        self.tmp.cleanup()

    def doc(self, t):
        return json.loads((self.d / f"{t.id}.json").read_text(encoding="utf-8"))

    def test_vong_doi_va_khoa_hop_dong(self):
        with T.viec("bien-kich", "Đang viết lời đọc", sp="Nano Đồng", buoc="Bài 0/5") as tt:
            x = self.doc(tt)
            self.assertEqual(x["vai"], "bien-kich")
            self.assertEqual(x["nguon"], "hub")
            self.assertRegex(x["id"], r"^bien-kich-[0-9a-f]{6}$")
            self.assertFalse(x["xong"])
            self.assertIsNone(x["ket_qua"])
            self.assertEqual((x["sp"], x["buoc"], x["viec"]), ("Nano Đồng", "Bài 0/5", "Đang viết lời đọc"))
            for k in ("id", "nguon", "vai", "viec", "sp", "video", "kenh", "bat_dau", "cap_nhat", "xong", "ket_qua", "ky_tu", "dong", "dang_go",
                      "suy_nghi", "tien_do", "buoc", "chi_tiet"):
                self.assertIn(k, x)
            tt.cap(buoc="Bài 1/5", tien_do=0.2, chi_tiet={"diem": 8}, video="nano-dong-2")
            tt.chu(KICH_BAN[:100])
            tt.nghi("Mình đang cân nhắc   câu\nmở đầu")
            x = self.doc(tt)
            self.assertEqual((x["buoc"], x["tien_do"], x["video"], x["chi_tiet"]), ("Bài 1/5", 0.2, "nano-dong-2", {"diem": 8}))
            self.assertEqual(x["dong"], ["Vườn cà phê cần phun.", "Nano Đồng đây nhé!"])
            self.assertEqual(x["ky_tu"], 100)
            self.assertEqual(x["suy_nghi"], "Mình đang cân nhắc câu mở đầu")
            self.assertIsNotNone(x["dang_go"])
        x = self.doc(tt)
        self.assertTrue(x["xong"])
        self.assertEqual(x["ket_qua"], "ok")
        self.assertIsNone(x["dang_go"])
        self.assertFalse(list(self.d.glob("*.tmp")))            # ghi nguyên tử: không để lại file tạm

    def test_ngoai_le_ra_khoi_with_la_loi_va_khong_bi_nuot(self):
        with self.assertRaises(ValueError):
            with T.viec("dao-dien", "x") as tt:
                raise ValueError("hỏng")
        self.assertEqual(self.doc(tt)["ket_qua"], "loi")
        with T.viec("dao-dien", "y") as t2:
            t2.ket("loi")
        self.assertEqual(self.doc(t2)["ket_qua"], "loi")

    def test_dong_toi_da_8_moi_dong_toi_da_200_khong_trung_lien_tiep(self):
        with T.viec("giong", "Đang thu giọng") as tt:
            for i in range(12):
                tt.them_dong(f"Câu số {i}")
            tt.them_dong("Câu số 11")
            tt.them_dong("x" * 500)
            x = self.doc(tt)
            self.assertEqual(len(x["dong"]), 8)
            self.assertEqual(x["dong"][-2], "Câu số 11")
            self.assertLessEqual(len(x["dong"][-1]), 200)
            tt.cap(dong=[f"d{i}" for i in range(20)])
            self.assertEqual(self.doc(tt)["dong"], [f"d{i}" for i in range(12, 20)])

    def test_chuoi_dai_chi_tiet_va_duong_dan_duoc_lam_sach(self):
        with T.viec("he-thong", "a" * 400, video="v" * 300) as tt:
            tt.cap(chi_tiet={"giay": 3.5, "ten": "n" * 300, "lung_tung": {"a": 1}, "ok": True})
            tt.them_dong("Xem C:\\Users\\Admin\\kho\\a.mp4 và https://x.com/abc?k=1 nhé")
            tt.nghi("đọc file C:\\Users\\Admin\\x.txt rồi")
            x = self.doc(tt)
            self.assertLessEqual(len(x["viec"]), 300)
            self.assertLessEqual(len(x["video"]), 120)
            self.assertEqual(set(x["chi_tiet"]), {"giay", "ten", "ok"})
            self.assertLessEqual(len(x["chi_tiet"]["ten"]), 120)
            self.assertNotIn("Users", json.dumps(x, ensure_ascii=False))
            self.assertNotIn("x.com", json.dumps(x, ensure_ascii=False))

    def test_suy_nghi_toi_da_240(self):
        with T.viec("giam-khao", "x") as tt:
            for _ in range(30):
                tt.nghi("một đoạn suy nghĩ khá dài của model ")
            s = self.doc(tt)["suy_nghi"]
            self.assertLessEqual(len(s), 240)
            self.assertTrue(s.endswith("model"))

    def test_giu_cach_toi_thieu_va_khong_rot_ban_cap_nhat_cuoi(self):
        T.GIAN_CACH = 0.4
        with T.viec("kho", "x") as tt:
            ghi0 = self.doc(tt)["cap_nhat"]
            tt.cap(buoc="B1")
            tt.cap(buoc="B2")
            tt.cap(buoc="B3")
            self.assertEqual(self.doc(tt)["cap_nhat"], ghi0)    # chưa đủ 0,4 s → chưa ghi lại
            het = time.time() + 3
            while time.time() < het and self.doc(tt)["buoc"] != "B3":
                time.sleep(0.05)
            self.assertEqual(self.doc(tt)["buoc"], "B3")        # bản cuối được ghi bù (hẹn giờ), không rớt
            self.assertGreaterEqual(self.doc(tt)["cap_nhat"] - ghi0, 0.35)
        self.assertTrue(self.doc(tt)["xong"])                   # kết thúc luôn ghi ngay

    def test_nhip_chi_ghi_sau_nhip_giay(self):
        T.NHIP_GIAY = 0.3
        with T.viec("giam-khao", "x") as tt:
            c0 = self.doc(tt)["cap_nhat"]
            tt.nhip(giay=1)
            self.assertEqual(self.doc(tt)["cap_nhat"], c0)
            time.sleep(0.35)
            tt.nhip(giay=2)
            x = self.doc(tt)
            self.assertGreater(x["cap_nhat"], c0)
            self.assertEqual(x["chi_tiet"]["giay"], 2)

    def test_hien_tai_theo_luong_va_long_nhau(self):
        self.assertIsNone(T.hien_tai())
        with T.viec("bien-kich", "a") as a:
            self.assertIs(T.hien_tai(), a)
            ngoai = []
            th = threading.Thread(target=lambda: ngoai.append(T.hien_tai()))
            th.start(); th.join()
            self.assertEqual(ngoai, [None])                      # luồng khác không thấy
            with T.viec("dao-dien", "b") as b:
                self.assertIs(T.hien_tai(), b)
            self.assertIs(T.hien_tai(), a)
            k = T.viec("kho", "c").mo(hien_tai=False)            # việc không làm "hiện tại" (thủ kho)
            self.assertIs(T.hien_tai(), a)
            k.xong()
        self.assertIsNone(T.hien_tai())

    def test_viec_do_luong_khac_dong_van_dung_duoc(self):
        v = T.viec("giong", "x").mo()
        th = threading.Thread(target=v.xong); th.start(); th.join()
        self.assertIsNone(T.hien_tai())                          # đã xong ở luồng khác → không còn là việc hiện tại
        self.assertTrue(self.doc(v)["xong"])

    def test_doc_tat_ca_het_han_xong_va_don_dep(self):
        now = time.time()

        def tao(ten, **kw):
            x = {"id": ten, "vai": "dung", "nguon": "hub", "viec": "x", "cap_nhat": now, "xong": False}
            x.update(kw)
            (self.d / f"{ten}.json").write_text(json.dumps(x), encoding="utf-8")
            if "tuoi_file" in kw:
                os.utime(self.d / f"{ten}.json", (now - kw["tuoi_file"], now - kw["tuoi_file"]))
            return self.d / f"{ten}.json"
        tao("moi", cap_nhat=now - 5)
        tao("cu-11p", cap_nhat=now - 660, tuoi_file=660)
        tao("xong-moi", cap_nhat=now - 20, xong=True, ket_qua="ok")
        tao("xong-cu", cap_nhat=now - 90, xong=True, ket_qua="ok", tuoi_file=90)
        tao("moi-hon", cap_nhat=now - 1)
        (self.d / "hong.json").write_text("{không phải json", encoding="utf-8")
        (self.d / "khac.txt").write_text("x", encoding="utf-8")
        ds = T.doc_tat_ca(now, self.d, xoa=False)
        self.assertEqual([x["id"] for x in ds], ["moi-hon", "moi", "xong-moi"])      # mới cập nhật nhất trước
        self.assertEqual(T.cap_nhat_toi_da(now, self.d), now - 1)
        self.assertTrue((self.d / "cu-11p.json").exists())                          # xoa=False: chưa dọn
        T._don_cuoi[0] = 0.0
        T.doc_tat_ca(now, self.d)
        self.assertFalse((self.d / "cu-11p.json").exists())
        self.assertFalse((self.d / "xong-cu.json").exists())
        self.assertTrue((self.d / "xong-moi.json").exists())
        self.assertTrue((self.d / "moi.json").exists())
        self.assertEqual(T.cap_nhat_toi_da(now, self.d / "khong-co"), 0.0)

    def test_cong_tac_tat_khong_ghi_gi(self):
        cu = T.dang_bat
        T.dang_bat = lambda: False
        try:
            with T.viec("bien-kich", "x") as tt:
                tt.cap(buoc="a"); tt.chu("Một câu rất dài để thử nhé."); tt.nghi("x"); tt.them_dong("y"); tt.nhip(giay=1); tt.ket("loi")
                self.assertIsNone(T.hien_tai())
        finally:
            T.dang_bat = cu
        self.assertFalse(list(self.d.glob("*")))

    def test_loi_ghi_file_bi_nuot(self):
        T._THU_MUC = str(self.d / "file-chan")
        (self.d / "file-chan").write_text("x", encoding="utf-8")        # thư mục đích là một file → mkdir hỏng
        with T.viec("kho", "x") as tt:
            tt.cap(buoc="a"); tt.chu("Một câu rất dài để thử nhé."); tt.xong()
        self.assertEqual(T.doc_tat_ca(), [])

    def test_mo_ta_vai(self):
        self.assertEqual(T.mo_ta_vai("biên kịch")[0], "bien-kich")
        self.assertEqual(T.mo_ta_vai("đạo diễn XuanLuong")[0], "dao-dien")
        self.assertEqual(T.mo_ta_vai("giám khảo")[0], "giam-khao")
        self.assertEqual(T.mo_ta_vai("gom bài học")[0], "giam-khao")
        self.assertEqual(T.mo_ta_vai("đọc nhãn")[0], "doc-nhan")
        self.assertEqual(T.mo_ta_vai("soát kho cảnh")[0], "soat-kho")
        v, viec = T.mo_ta_vai("kiểm hạn mức")
        self.assertEqual(v, "he-thong")
        self.assertTrue(viec.startswith("Đang hỏi Claude"))

    def test_nhieu_luong_cung_ghi_moi_viec_mot_file(self):
        def chay(i):
            with T.viec("dao-dien", f"Việc {i}", video=f"v{i}") as tt:
                for k in range(20):
                    tt.them_dong(f"Dòng {k} của việc {i}")
        ts = [threading.Thread(target=chay, args=(i,)) for i in range(6)]
        [t.start() for t in ts]; [t.join() for t in ts]
        ds = T.doc_tat_ca(xoa=False)
        self.assertEqual(len(ds), 6)
        self.assertEqual(len({x["id"] for x in ds}), 6)
        self.assertTrue(all(x["xong"] and x["dong"][-1].startswith("Dòng 19") for x in ds))


if __name__ == "__main__":
    unittest.main()
