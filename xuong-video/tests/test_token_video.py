"""Sổ token từng video: ai._ghi_so cộng từng lượt gọi vào đúng bước; ekip.so_token_video tách lần đầu / vòng sửa, chia đều token biên kịch. KHÔNG gọi AI."""
import os, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
GOC = Path(__file__).resolve().parents[1]
for p in (str(GOC / "app"), str(GOC / "engine")):
    if p not in sys.path:
        sys.path.insert(0, p)
import ai  # noqa: E402
import ekip  # noqa: E402

U = {"input_tokens": 100, "cache_creation_input_tokens": 2000, "cache_read_input_tokens": 30000, "output_tokens": 400}


class SoToken(unittest.TestCase):
    def tearDown(self):
        ai.VIEC.so = None; ai.VIEC.pha = None

    def test_khong_co_so_thi_bo_qua(self):
        ai.VIEC.so = None
        ai._ghi_so(U, 0.5)                                   # không lỗi, không ghi gì

    def test_cong_dung_buoc(self):
        so = {}
        ai.VIEC.so, ai.VIEC.pha = so, "dao_dien"
        ai._ghi_so(U, 0.25); ai._ghi_so(U, 0.25)
        ai.VIEC.pha = "giam_khao"
        ai._ghi_so({"input_tokens": 5, "output_tokens": 7})
        self.assertEqual(so["dao_dien"], {"luot": 2, "vao": 200, "cache_tao": 4000, "cache_doc": 60000, "ra": 800, "usd": 0.5})
        self.assertEqual(so["giam_khao"]["luot"], 1); self.assertEqual(so["giam_khao"]["ra"], 7)

    def test_lan_dau_va_vong_sua(self):
        m = lambda n: {"luot": 1, "vao": n, "cache_tao": 0, "cache_doc": 0, "ra": 0, "usd": 0.1}
        so = {"dao_dien": m(1000), "giam_khao": m(500), "sua_dao_dien": m(900), "sua_giam_khao": m(400)}
        bk = {"viet_loi": {"luot": 2, "vao": 6000, "cache_tao": 0, "cache_doc": 0, "ra": 1200, "usd": 0.6}}
        r = ekip.so_token_video(so, bk, n_loi=3, per=2)       # 6 video chia token biên kịch
        self.assertEqual(r["pha"]["viet_loi_chia"]["vao"], 1000); self.assertEqual(r["pha"]["viet_loi_chia"]["ra"], 200)
        self.assertEqual(r["token_lan_dau"], 1000 + 200 + 1000 + 500)
        self.assertEqual(r["token_sua"], 1300)
        self.assertEqual(r["token_tong"], r["token_lan_dau"] + r["token_sua"])
        self.assertEqual(r["sua"]["luot"], 2)
        self.assertAlmostEqual(r["tong"]["usd"], 0.1 * 4 + 0.1, places=4)

    def test_khong_so(self):
        r = ekip.so_token_video(None, {}, 0, 2)
        self.assertEqual(r["token_tong"], 0); self.assertEqual(r["sua"]["luot"], 0)


if __name__ == "__main__":
    unittest.main()
