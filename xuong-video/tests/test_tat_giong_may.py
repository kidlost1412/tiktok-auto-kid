"""Máy bắt tật giọng máy trong lời đọc (viet_loi.tat_giong_may). Mẫu lấy từ kịch bản thật ngày 16/11. KHÔNG gọi AI."""
import os, re, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import viet_loi as vl  # noqa: E402

SP = {"qua_tang": ["Mua 1 can tặng 1 gói kali bo"]}


def loi(text, goc="cong-dung", sp=SP):
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    return vl.tat_giong_may({"goc": goc}, sp, text, sents)


class TatGiongMayTest(unittest.TestCase):
    def co(self, errs, chu):
        self.assertTrue(any(chu in e for e in errs), errs)

    def test_ba_cham(self):
        self.co(loi("Trễ một cữ phun… mất trái. Để yên vài tuần… công cả năm theo trái rụng. Can ở giỏ hàng nha."), "dấu '…'")
        self.assertEqual(loi("Bóp thử nắm đất coi… có tơi không? Đất chai thì rễ khó ăn lắm. Can ở giỏ hàng nha."), [])

    def test_tu_hoi_tu_dap(self):
        e = loi("Đất chai thì rễ khó ăn. Khách hay hỏi: rau mới trồng, phun được chưa? Được. Đợi bảy ngày rồi phun nha bà con.")
        self.co(e, "Khách hỏi"); self.co(e, "tự đáp cụt")

    def test_hoi_ep_chon(self):
        self.co(loi("Cây gồng trái mà đói thì buông trái. Giữ trái, hay nhặt trái rụng? Can ở giỏ hàng."), "ép chọn")
        self.assertEqual(loi("Cây gồng trái mà đói thì buông trái. Vườn nhà mình đang ra sao rồi? Can ở giỏ hàng."), [])

    def test_cau_cut(self):
        self.co(loi("Pha đậm tay đâu phải là thương cây. Ít mà đủ. Một can pha được ba nghìn lít nước. Thử trước đã. Giỏ hàng có sẵn."), "câu cụt")
        self.assertEqual(loi("Pha đậm tay đâu phải là thương cây. Một can pha được ba nghìn lít. Phun chiều mát. Giỏ hàng có sẵn."), [])  # một câu dặn ngắn là tự nhiên
        self.assertEqual(loi("Đốm lá lan nhanh. Phun sớm thì đỡ mất hạt lắm. Lấy ở giỏ hàng."), [])   # câu mở/câu chốt ngắn được phép

    def test_goc_qua_tang_phai_noi_qua(self):
        t = "Luống ớt này tháng trước còn rụng bông, giờ kín trái rồi. Phun chiều mát mười ngày một lượt. Can nằm sẵn ở giỏ hàng nha."
        self.co(loi(t, goc="qua-tang"), "quà tặng")
        self.assertEqual(loi(t + " Lấy can đợt này được tặng gói kali bo.", goc="qua-tang"), [])
        self.assertEqual(loi(t, goc="qua-tang", sp={"qua_tang": []}), [])     # sản phẩm không có quà thì thôi


if __name__ == "__main__":
    unittest.main()
