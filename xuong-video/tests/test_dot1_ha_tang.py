"""Đợt 1 hạ tầng: system prompt đạo diễn cố định, cổng số liệu hiệu quả cho đạo diễn, gom bài học lọc lỗi máy, lý do lỗi giọng, lý do thử lại cảnh.
KHÔNG gọi AI/mạng."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
GOC = Path(__file__).resolve().parents[1]
for p in (str(GOC / "engine"), str(GOC / "app")):
    if p not in sys.path:
        sys.path.insert(0, p)

import ai  # noqa: E402
import ekip  # noqa: E402
import hieu_qua  # noqa: E402
import hoc_canh  # noqa: E402
import su_kien  # noqa: E402


class HeThongDaoDien(unittest.TestCase):
    def test_bon_gu_cung_system_prompt(self):
        a, b = ai.he_thong("đạo diễn thuc-te"), ai.he_thong("đạo diễn lo-lung")
        self.assertEqual(a, b)
        self.assertEqual(a, ai.he_thong("đạo diễn"))
        self.assertNotEqual(a, ai.he_thong("biên kịch"))

    def test_gpt_dung_vai_gon_nhung_log_vai_day_du(self):
        gui, dong = {}, []

        class P:
            pid = 1
            def __init__(s, *a, **k): pass
            def communicate(s, full, timeout=None):
                gui["full"] = full
                return json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}) + "\n", ""

        with mock.patch.object(ai.subprocess, "Popen", P), \
                mock.patch.object(su_kien, "noi_them", lambda f, t, **k: dong.append(t)), \
                mock.patch.object(ai, "_ghi_so", lambda u: None):
            ai._goi_gpt("đạo diễn thuc-te", "đề bài")
        self.assertIn("(vai: đạo diễn) ===", gui["full"])
        self.assertNotIn("thuc-te", gui["full"])
        self.assertIn("đạo diễn thuc-te", dong[0])


class CongSoLieuDaoDien(unittest.TestCase):
    def _tom(self, n, v, cho="dao_dien"):
        # 4 video nhóm "a" view gấp 4, còn lại nhóm "b" view v → trung vị đúng v, có dòng gợi ý (a x tốt, b x kém)
        rows = [{"ma": "x", "xem24": 4 * v if i < 4 else v, "dao_dien": "a" if i < 4 else "b", "cau_mo": "m"} for i in range(n)]
        with mock.patch.object(hieu_qua, "_ban_ghi", return_value=(rows, rows)):
            return hieu_qua.tom_tat("x", cho)

    def test_so_video(self):
        self.assertEqual(self._tom(14, 500), "")
        self.assertTrue(self._tom(15, 500))

    def test_trung_vi(self):
        self.assertEqual(self._tom(20, 199), "")             # trung vị 199 < 200
        self.assertTrue(self._tom(20, 200))

    def test_bien_kich_khong_doi(self):
        self.assertTrue(self._tom(10, 50, "bien_kich"))        # biên kịch tự gác cổng ở viet_loi


class GomBaiHocLocLoiMay(unittest.TestCase):
    def test_loi_may_khong_tinh_nguong_va_khong_gui(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "lich-su").mkdir()
        may = "- Chữ đè lên nhãn chai ở giây 3 nên bị che"
        from kiem_may import la_loi_may
        self.assertTrue(la_loi_may(may))
        (tmp / "lich-su" / "bai-hoc-x.txt").write_text("\n".join([may] * 30 + [f"- bài học thật số {i}" for i in range(5)]), encoding="utf-8")
        (tmp / "lich-su" / "bai-hoc.txt").write_text(may + "\n- luật chung thật\n", encoding="utf-8")
        gui = []
        with mock.patch.object(ekip, "HUB", tmp), mock.patch("ai.goi", lambda *a, **k: gui.append(a[1]) or ("", {})):
            ekip.gom_bai_hoc("x", nguong=25)                  # 30 dòng máy + 5 thật: lọc rồi chỉ còn 5 ≤ 25 → không gọi AI
            self.assertEqual(gui, [])
            ekip.gom_bai_hoc("x", nguong=3)                   # 5 > 3 → gọi AI, prompt không có dòng lỗi máy
        self.assertEqual(len(gui), 1)
        self.assertNotIn("đè lên nhãn", gui[0])
        self.assertIn("bài học thật số 4", gui[0])
        self.assertIn("luật chung thật", gui[0])


class LyDoGiong(unittest.TestCase):
    def test_quota(self):
        class E(Exception):
            body = {"detail": {"status": "quota_exceeded", "message": "This request exceeds your quota. You have 1 credits remaining, while 10 credits are required"}}
        ly, het = ekip.ly_do_giong(E("headers: {...}"))
        self.assertTrue(het)
        self.assertIn("quota_exceeded", ly)
        self.assertIn("1 credits remaining", ly)

    def test_loi_khac(self):
        class E(Exception):
            body = {"detail": {"status": "voice_not_found", "message": "no such voice"}}
        self.assertEqual(ekip.ly_do_giong(E("x")), ("voice_not_found: no such voice", False))
        self.assertEqual(ekip.ly_do_giong(RuntimeError("hỏng")), ("hỏng", False))
        self.assertTrue(ekip.ly_do_giong(RuntimeError("quota hết"))[1])


class LyDoThuLaiCanh(unittest.TestCase):
    def test_moi_canh_kem_ly_do_rieng(self):
        # 2 video cùng sai cảnh số 1 (chỉ số gốc 0) với lý do khác nhau; lô lần 2 đánh số lại 1, 2
        viec = [{"src": "a.mp4", "canh": [{"so": 1, "tu": 0, "den": 2, "sai": "thiếu mô tả A"}]},
                {"src": "b.mp4", "canh": [{"so": 2, "tu": 1, "den": 3, "sai": "sai thẻ B"}, {"so": 3, "tu": 3, "den": 4, "sai": ""}]}]
        ds = hoc_canh.ctx_dien_phieu(viec, [], "ra.json")["ds_video"]
        self.assertIn("cảnh 1: từ giây 0 đến giây 2 (lần trước sai: thiếu mô tả A — sửa đúng chỗ này)", ds)
        self.assertIn("cảnh 2: từ giây 1 đến giây 3 (lần trước sai: sai thẻ B — sửa đúng chỗ này)", ds)
        self.assertIn("cảnh 3: từ giây 3 đến giây 4\n", ds + "\n")
        self.assertNotIn("thiếu mô tả A", ds.split("VIDEO 2")[1])




class LoiMayLopChuTest(unittest.TestCase):
    def test_bat_loi_lop_chu_khong_bat_chot_qua(self):
        import kiem_may as KM
        for x in ("khoảng thở: Hai khối chữ xuất hiện cùng lúc", "Tránh chữ sát hoặc đè nút giỏ hàng",
                  "tránh chữ trong 12% trên cùng", "5.8s dính chữ lạ", "Tránh gắn sticker “XOÀI TRỔ BÔNG”"):
            self.assertTrue(KM.la_loi_may(x), x)
        for x in ("Luôn chốt đủ quà Amino A6 và nút giỏ hàng cùng chai Bọ Trĩ Top One.",
                  "Luôn mở bằng chuyển động, câu móc cụ thể, trọn câu.", "nhãn rõ: Chai lọt góc khung"):
            self.assertFalse(KM.la_loi_may(x), x)




class PhuDeChamMepNhanTest(unittest.TestCase):
    def test_cham_mep_khong_bao_che_that_van_bao(self):
        import kiem_may as km
        sents = [{"s": 0.0, "e": 3.0, "text": "a"}, {"s": 3.0, "e": 6.0, "text": "b"}]
        def sg(nhan):
            return {"shot": {"id": "A", "file": "A.mp4", "vai_tro": ["chai_ro"], "soat": {"mat": 0, "nhan": nhan, "dep": 4}}, "dur": 6.0, "bo_cuc": "day", "cau": 1, "src_start": 0.0, "phu_shots": []}
        muc = lambda s: [x["muc"] for x in km.kiem([s], sents, co_qua=False)]
        self.assertNotIn("khong_che_nhan", muc(sg([0.3, 0.40, 0.7, 0.78])))   # phụ đề phủ ~15% mép dưới nhãn: ngưỡng cũ 10% báo, nay không
        self.assertIn("khong_che_nhan", muc(sg([0.3, 0.70, 0.7, 0.80])))


if __name__ == "__main__":
    unittest.main()
