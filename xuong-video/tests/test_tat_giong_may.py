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
        self.co(loi("Trễ một cữ… mất trái. Để yên vài tuần… công cả năm… theo trái rụng hết. Can ở giỏ hàng nha."), "dấu '…'")
        self.assertEqual(loi("Trễ một lần xịt thôi… là mất nguyên lứa trái non. Đất chai thì rễ khó ăn lắm bà con. Can ở giỏ hàng nha."), [])   # dùng đúng chỗ thì được

    def test_tu_hoi_tu_dap(self):
        e = loi("Đất chai thì rễ khó ăn. Khách hay hỏi: rau mới trồng, phun được chưa? Được. Đợi bảy ngày rồi phun nha bà con.")
        self.co(e, "Khách hỏi"); self.co(e, "tự đáp cụt")
        self.co(loi("Đoán thử coi, thứ gì từ chợ cá mà cây lại cần? Khách hay hỏi xịt lúc ra bông được không? Được, vì nó chống rụng bông. Can ở giỏ hàng."), "tự đáp")

    def test_hoi_ep_chon(self):
        self.co(loi("Cây gồng trái mà đói thì buông trái. Giữ trái, hay nhặt trái rụng? Can ở giỏ hàng."), "ép chọn")
        self.assertEqual(loi("Cây gồng trái mà đói thì buông trái. Vườn nhà mình đang ra sao rồi? Can ở giỏ hàng."), [])

    def test_cau_cut(self):
        self.co(loi("Pha đậm tay đâu phải là thương cây. Ít mà đủ. Một can pha được ba nghìn lít nước. Thử trước đã. Giỏ hàng có sẵn."), "câu cụt")
        self.co(loi("Pha đậm tay đâu phải là thương cây. Một can pha được ba nghìn lít. Trưa nắng thì nghỉ. Giỏ hàng có sẵn."), "câu cụt")
        self.assertEqual(loi("Pha đậm tay đâu phải là thương cây. Một can pha được ba nghìn lít nước, xịt chiều mát là được. Giỏ hàng có sẵn."), [])
        self.assertEqual(loi("Đốm lá lan nhanh. Phun sớm thì đỡ mất hạt lắm. Lấy ở giỏ hàng."), [])   # câu mở/câu chốt ngắn được phép

    def test_xung_ho(self):
        self.co(loi("Năm ngoái tôi tiếc một chai thuốc mà mất đợt tiêu. Can ở giỏ hàng."), "xưng hô")
        self.co(loi("Vườn bạn đang vàng lá phải không? Can ở giỏ hàng."), "xưng hô")
        self.co(loi("Anh chị nhớ xịt chiều mát cho cây ăn. Can ở giỏ hàng."), "xưng hô")
        self.co(loi("Bà con nghe nè. Bà con xịt chiều mát thì cây ăn. Bà con lấy ở giỏ hàng."), "bà con")
        self.assertEqual(loi("Ông chú này chửi em một trận, bạn hàng em lấy hai can rồi. Bà con xịt chiều mát cho cây ăn. Can ở giỏ hàng các bác."), [])
        self.co(loi("Mấy bữa nay các bác hỏi hoài. Các bác xịt chiều mát cho cây ăn. Can ở giỏ hàng các bác."), "\"các bác\"")

    def test_khong_mo_bang_tieng_goi(self):
        self.co(loi("Các bác ơi, cả xóm trồng cải mua lại chai này! Xịt chiều mát cho cây ăn. Can ở giỏ hàng."), "tiếng gọi")
        self.co(loi("Bà con đoán thử coi, can này xịt được mấy bình? Xịt chiều mát cho cây ăn. Can ở giỏ hàng."), "tiếng gọi")
        self.assertEqual(loi("Xịt thuốc càng nhiều… vườn lại càng hay bệnh. Xịt chiều mát cho cây ăn nha các bác. Can ở giỏ hàng."), [])

    def test_goc_qua_tang_phai_noi_qua(self):
        t = "Luống ớt này tháng trước còn rụng bông, giờ kín trái rồi. Phun chiều mát mười ngày một lượt. Can nằm sẵn ở giỏ hàng nha."
        self.co(loi(t, goc="qua-tang"), "quà tặng")
        self.assertEqual(loi(t + " Lấy can đợt này được tặng gói kali bo.", goc="qua-tang"), [])
        self.assertEqual(loi(t, goc="qua-tang", sp={"qua_tang": []}), [])     # sản phẩm không có quà thì thôi


    def test_ke_le_doc_nhan(self):
        self.co(loi("Sầu riêng đang rụng bông nhiều. Đọc nhãn ta thấy có ghi chống rụng hoa rụng quả non. Lấy ở giỏ hàng."), "kể lể")
        self.co(loi("Sầu riêng đang rụng bông nhiều. Nhìn trên nhãn em thấy ghi chống rụng trái non. Lấy ở giỏ hàng."), "kể lể")
        # thông tin trên nhãn, liều, hoạt chất thì được nói
        self.assertEqual(loi("Sầu riêng đang rụng bông nhiều thì bà con xịt cái này. Nhãn ghi chống rụng hoa rụng quả non, hai mươi lăm mi li một bình. Lấy ở giỏ hàng."), [])

    def test_luat_rieng_ten_trong_may_giay_dau(self):
        sp = {"luat_rieng": ['Tên "Nano Đồng Toàn Cầu" (hoặc "chai Nano Đồng này") trong 5 giây đầu.', "Không nói lá xanh."]}
        muon = "Ruộng lúa hay mất vì đúng một lượt phun chậm. Phun Nano Đồng ngay lúc vừa chớm, vì nó trừ được đạo ôn, khô vằn, cháy bìa lá. Nano Đồng Toàn Cầu có ở giỏ hàng."
        self.co(loi(muon, sp=sp), "5 giây đầu")
        self.assertEqual(loi("Thứ làm mai mất điểm, ít ai nói ra. Chai Nano Đồng này rửa sạch rêu trên thân mai. Giỏ hàng có sẵn.", sp=sp), [])
        self.assertEqual(loi(muon, sp={"luat_rieng": ["Không nói giá."]}), [])          # luật không nói giây đầu thì thôi


if __name__ == "__main__":
    unittest.main()
