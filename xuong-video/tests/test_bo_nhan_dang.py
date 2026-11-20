"""Góc "thương hiệu / nhận dạng chai" bị bỏ hẳn: không giao góc đó, không gửi mô tả bao bì cho biên kịch, máy kiểm loại câu tả nhãn."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import viet_loi as vl  # noqa: E402


class BoNhanDangTest(unittest.TestCase):
    def test_goc_bi_bo_khong_duoc_giao(self):
        sp = {"goc_ban": [{"ma": "rua-vuon"}, {"ma": "thuong-hieu"}, {"ma": "nhan-dien-chai"}, {"ma": "qua-tang"}]}
        self.assertEqual(vl.goc_ban(sp), ["rua-vuon", "qua-tang"])
        self.assertNotIn("thuong-hieu", vl.goc_ban({}))
        self.assertEqual(vl.goc_ban({"goc_ban": [{"ma": "thuong-hieu"}]}), vl.GOC_MAC_DINH)

    def test_kieu_than_nhan_dang_da_bo(self):
        self.assertNotIn("soi_nhan", vl.THAN)
        self.assertNotIn("khang_dinh", vl.THAN)

    def test_ho_so_gui_bien_kich_bo_mo_ta_bao_bi(self):
        sp = {"ten_goi": "X", "nhan_dien_chai": "Chai trắng, nắp đỏ", "kho_video": "k",
              "su_that_duoc_noi": ["Mặt trước nhãn: chữ đỏ. Chỉ nhắc khi cần chỉ cách nhận đúng hàng.", "Mặt trước nhãn: tem Chính hãng",
                                   "Mặt trước nhãn, thành phần: Flonicamid 3%", "Pha 1 nắp 1 bình 16 lít"]}
        a = vl.sp_cho_bien_kich(sp)
        self.assertNotIn("nhan_dien_chai", a)
        self.assertNotIn("kho_video", a)
        self.assertEqual(a["su_that_duoc_noi"], ["Mặt trước nhãn, thành phần: Flonicamid 3%", "Pha 1 nắp 1 bình 16 lít"])
        self.assertIn("nhan_dien_chai", sp)          # hồ sơ gốc không bị sửa (đạo diễn vẫn dùng)

    def test_may_kiem_bat_cau_ta_nhan(self):
        bat = ["nano đồng nhãn trắng, chữ đỏ", "chai nắp xanh lá", "các bác coi đúng nhãn", "thiếu tem chính hãng là bỏ", "nhận đúng chai nha"]
        tha = ["mở ra coi đúng hàng rồi mới trả tiền", "lá xanh mướt, trái đỏ au", "pha một nắp một bình", "chữ in trên nhãn ghi hai mươi phần trăm"]
        for t in bat:
            self.assertIsNotNone(vl._RE_NHAN_DANG.search(t), t)
        for t in tha:
            self.assertIsNone(vl._RE_NHAN_DANG.search(t), t)


if __name__ == "__main__":
    unittest.main()
