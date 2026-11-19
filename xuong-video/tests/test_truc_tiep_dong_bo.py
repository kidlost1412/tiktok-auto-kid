"""Việc trực tiếp được mở đúng chỗ trong dây chuyền (ekip, viết lời, Học cảnh) với đồ giả — không gọi AI / ElevenLabs / ffmpeg / Antigravity thật.
Mượn sẵn bộ đồ giả của test_ben_bi / test_bien_kich_moi / test_hoc_canh_v2."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_ben_bi as BB  # noqa: E402
import test_bien_kich_moi as BK  # noqa: E402
import test_hoc_canh_v2 as V2  # noqa: E402
import truc_tiep as T  # noqa: E402
from ai import HetHanMuc  # noqa: E402


class Nen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name) / "truc-tiep"
        self.cu = (T._THU_MUC, T.GIAN_CACH)
        T._THU_MUC, T.GIAN_CACH = str(self.d), 0.0

    def tearDown(self):
        for t in list(T._MO):
            t.xong()
        T._THU_MUC, T.GIAN_CACH = self.cu
        self.tmp.cleanup()

    def viec(self):
        return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(self.d.glob("*.json"))] if self.d.exists() else []

    def theo_vai(self):
        out = {}
        for x in self.viec():
            out.setdefault(x["vai"], []).append(x)
        return out


class EkipTest(Nen):
    def _chay(self, dao_dien):
        with tempfile.TemporaryDirectory() as td:
            return BB._dung_ekip(td, so_video=2, so_loi=1, dao_dien=dao_dien, tao_giong=lambda text, vid, out, ten, doc=None: BB.giong_gia())

    def test_moi_vai_co_viec_that_va_deu_xong(self):
        def dd(*a, **k):
            raise ValueError("AI không trả JSON hợp lệ")           # đạo diễn lỗi → máy tự dựng theo luật (vẫn ra video)
        self._chay(dd)
        v = self.theo_vai()
        self.assertEqual(set(v), {"bien-kich", "giong", "dao-dien", "dung", "giam-khao", "kho"})
        self.assertTrue(all(x["xong"] and x["nguon"] == "hub" and x["sp"] == "SP Thử" for x in self.viec()))
        bk = v["bien-kich"][0]
        self.assertEqual((bk["viec"], bk["buoc"], bk["ket_qua"]), ("Đang viết lời đọc", "Bài 1/1", "ok"))
        g = v["giong"][0]
        self.assertEqual(g["buoc"], "Giọng 1/1")
        self.assertEqual(g["dong"], ["Một hai ba bốn.", "Năm sáu bảy tám chín mười mười một.", "Chín mười."])      # đúng câu đang đọc thành tiếng
        self.assertEqual(g["chi_tiet"]["giay"], 9.0)
        dd_ = v["dao-dien"]
        self.assertEqual(len(dd_), 2)                                   # 2 đạo diễn / lời
        self.assertTrue(all(x["video"] and x["viec"] == "Đã có bảng dựng" for x in dd_))
        self.assertTrue(all(x["chi_tiet"]["may_tu_dung"] is True and x["chi_tiet"]["so_canh"] > 0 for x in dd_))
        self.assertTrue(any("máy tự dựng" in l for l in dd_[0]["dong"]))
        dung = {x["buoc"].split(" ")[0]: x for x in v["dung"]}
        self.assertEqual(len(v["dung"]), 3)                             # 2 video dựng nền + 1 việc lớp chữ
        chu = next(x for x in v["dung"] if x["buoc"].startswith("Lớp chữ"))
        self.assertEqual(chu["buoc"], "Lớp chữ 2/2")
        self.assertEqual(chu["tien_do"], 1.0)
        self.assertEqual(sum(1 for x in v["dung"] if x["buoc"] == "Dựng nền"), 2)
        gk = v["giam-khao"]
        self.assertEqual(len(gk), 2)
        self.assertEqual(gk[0]["chi_tiet"]["diem"], 7)
        self.assertEqual(gk[0]["dong"][0], "Điểm 7/10 — ĐẠT")
        kho = v["kho"][0]
        self.assertEqual((kho["buoc"], kho["tien_do"]), ("Video 2/2", 1.0))
        self.assertEqual(kho["dong"], ["Đã cất video 1/2 — điểm 7/10", "Đã cất video 2/2 — điểm 7/10"])

    def test_het_han_muc_o_dao_dien_la_loi(self):
        def dd(*a, **k):
            raise HetHanMuc("hết")
        self._chay(dd)
        v = self.theo_vai()
        self.assertTrue(v["dao-dien"])
        self.assertTrue(all(x["xong"] and x["ket_qua"] == "loi" for x in v["dao-dien"]))
        self.assertNotIn("kho", v)                                       # không video nào để cất
        self.assertEqual(T.hien_tai(), None)                             # không để lại "việc hiện tại" ma


class VietLoiTest(Nen):
    def test_chot_bai_va_loai_bai_vao_dong_cua_viec_dang_mo(self):
        b = BK.VietTest("test_viet_hai_ban_loai_mot_goi_lai")
        b.setUp()
        try:
            b.canh([{"id": "1", "vai_tro": ["chai_ro"], "cay": ["ca_phe"], "soat": {"mat": 0, "dep": 4}}])
            b.mo_ta("a.mp4", loi=["Mình làm vườn mấy chục năm rồi mới thấy cái này chạy thật sự đó anh em ơi."])
            tot, xau = BK.kich_ban(1, b.sp, u=True), BK.kich_ban(2, b.sp, u=True, gh="Bấm vào đó nhé.")
            with T.viec("bien-kich", "Đang viết lời đọc", buoc="Bài 0/2") as tt:
                ra, _ = b.chay([[tot, xau], [BK.kich_ban(3, b.sp, u=True)]])
            self.assertEqual(len(ra), 2)
            x = json.loads((self.d / f"{tt.id}.json").read_text(encoding="utf-8"))
            self.assertEqual(x["buoc"], "Bài 2/2")
            self.assertEqual(x["tien_do"], 1.0)
            self.assertEqual(x["dong"][0].split(":")[0], "Chốt bài 1/2")
            self.assertIn("Loại 1 bài: không nhắc giỏ hàng", x["dong"])
            self.assertEqual(x["dong"][-1].split(":")[0], "Chốt bài 2/2")
            for l in x["dong"]:
                if l.startswith("Chốt bài"):
                    self.assertGreater(len(l.split(":", 1)[1].strip()), 10)       # có câu mở đầu thật
        finally:
            b.tearDown()

    def test_khong_co_viec_mo_thi_viet_van_chay_binh_thuong(self):
        b = BK.VietTest("test_viet_hai_ban_loai_mot_goi_lai")
        b.setUp()
        try:
            b.canh([{"id": "1", "vai_tro": ["chai_ro"], "cay": ["ca_phe"], "soat": {"mat": 0, "dep": 4}}])
            b.mo_ta("a.mp4", loi=["Mình làm vườn mấy chục năm rồi mới thấy cái này chạy thật sự đó anh em ơi."])
            ra, _ = b.chay([[BK.kich_ban(1, b.sp, u=True), BK.kich_ban(2, b.sp, u=True)]])
            self.assertEqual(len(ra), 2)
            self.assertEqual(self.viec(), [])
        finally:
            b.tearDown()


class HocCanhTest(Nen):
    def test_lo_hoc_canh_co_viec_that(self):
        b = V2.HocKhoV2Test("test_duong_di_tot")
        b.setUp()
        try:
            b._videos(2)
            log = []
            r = b._chay(V2.gia.runner_gia(log))
            self.assertEqual(r["da_hoc"], 2)
        finally:
            b.tearDown(); b.doCleanups()
        v = self.theo_vai()["hoc-canh"]
        self.assertEqual(len(v), 1)
        x = v[0]
        self.assertTrue(x["xong"])
        self.assertEqual((x["ket_qua"], x["buoc"], x["sp"]), ("ok", "Lô 1/1", "t"))
        self.assertEqual(x["viec"], "Đã nhận phiếu lô 1/1")
        self.assertEqual((x["chi_tiet"]["canh"], x["chi_tiet"]["video"], x["chi_tiet"]["canh_dat"], x["chi_tiet"]["canh_loi"]), (6, 2, 6, 0))
        self.assertEqual(x["dong"], ["Phiếu hợp lệ 6/6 cảnh"])
        self.assertEqual(x["video"], "v0.mp4, v1.mp4")


if __name__ == "__main__":
    unittest.main()
