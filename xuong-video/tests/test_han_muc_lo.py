"""Chi phí lô: tách đúng từng lô khi token.csv còn tiêu đề cũ (thiếu cột "lo"); hạn mức trước → sau lô; ElevenLabs đọc từ API (giả lập)."""
import json, os, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-hanmuc-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import ekip  # noqa: E402
import giong  # noqa: E402

DAU_CU = "luc,vai,model,effort,giay,vao,vao_cache_tao,vao_cache_doc,ra,usd_uoc,luot,so_anh,tai_khoan,video\n"


class TachLoTest(unittest.TestCase):
    def test_tieu_de_cu_van_tach_dung_lo(self):
        ls = ekip.HUB / "lich-su"; ls.mkdir(parents=True, exist_ok=True)
        (ls / "lo.jsonl").unlink(missing_ok=True)
        luc = time.strftime("%Y-%m-%d %H:%M:%S")
        dong = lambda lo: f"{luc},đạo diễn,opus,medium,1,100,0,0,10,0.1,1,0,tk3,v,{lo}\n"
        (ls / "token.csv").write_text(DAU_CU + dong("a") * 2 + dong("b") * 5, encoding="utf-8-sig")
        with mock.patch.object(ekip, "anh_han_muc", return_value={}):
            ekip.bao_chi_phi(time.time() - 60, 2, lambda *_: None, "a")
        d = json.loads((ls / "lo.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(d["luot_ai"], 2); self.assertEqual(d["token"], 220)


class HaoHanMucTest(unittest.TestCase):
    def test_truoc_sau(self):
        t = {"tk3": {"h5": 10, "tuan": 40}, "_eleven": {"dung": 1000, "gioi_han": 100000}}
        s = {"tk3": {"h5": 31, "tuan": 43}, "tk1": {"h5": 5, "tuan": 5}, "_eleven": {"dung": 5000, "gioi_han": 100000}}
        h = ekip.hao_han_muc(t, s, {"tk3": 21})
        self.assertEqual(h["tk3"], {"h5": [10, 31], "tuan": [40, 43]})
        self.assertNotIn("tk1", h); self.assertEqual(h["_eleven"], [1000, 5000, 100000])

    def test_cua_so_qua_reset_la_0(self):
        st = {"tk1": {"five_hour": {"pct": 0.8, "reset": time.time() - 10}, "seven_day": {"pct": 0.5, "reset": time.time() + 999}}}
        with mock.patch("ai.doc_trang_thai", return_value=st), mock.patch("ai.doc_han_muc_nhanh", return_value=None):
            a = ekip.anh_han_muc(eleven=False)
        self.assertEqual(a["tk1"], {"h5": 0, "tuan": 50})


class DocNhanhTest(unittest.TestCase):
    def test_doc_va_ghi_trang_thai(self):
        import ai
        d = Path(tempfile.mkdtemp()); (d / ".credentials.json").write_text(json.dumps(
            {"claudeAiOauth": {"accessToken": "x", "expiresAt": (time.time() + 3600) * 1000}}), encoding="utf-8")
        tra = json.dumps({"five_hour": {"utilization": 6.0, "resets_at": "2026-11-27T14:40:00+00:00"},
                          "seven_day": {"utilization": 95.0, "resets_at": "2026-11-27T20:00:00+00:00"}}).encode()
        f_tk = d / "tk.json"
        with mock.patch.object(ai, "ds_tai_khoan", return_value=[{"ma": "tk9", "ten": "t", "thu_muc": str(d)}]), \
                mock.patch.object(ai, "F_TK", f_tk), mock.patch("urllib.request.urlopen", return_value=mock.Mock(read=lambda: tra)):
            x = ai.doc_han_muc_nhanh("tk9")
        self.assertEqual((x["five_hour"]["pct"], x["seven_day"]["pct"]), (0.06, 0.95))
        self.assertGreater(x["five_hour"]["reset"], 1.7e9)

    def test_phien_het_han_khong_goi_mang(self):
        import ai
        d = Path(tempfile.mkdtemp()); (d / ".credentials.json").write_text(json.dumps(
            {"claudeAiOauth": {"accessToken": "x", "expiresAt": (time.time() - 10) * 1000}}), encoding="utf-8")
        with mock.patch.object(ai, "ds_tai_khoan", return_value=[{"ma": "tk9", "ten": "t", "thu_muc": str(d)}]), \
                mock.patch("urllib.request.urlopen", side_effect=AssertionError("không được gọi mạng")):
            self.assertIsNone(ai.doc_han_muc_nhanh("tk9"))


class HanMucGiongTest(unittest.TestCase):
    def test_doc_tu_api(self):
        sub = mock.Mock(character_count=1200, character_limit=100000, next_character_count_reset_unix=1, tier="creator")
        c = mock.Mock(); c.user.subscription.get.return_value = sub
        with mock.patch.object(giong, "client", return_value=c):
            h = giong.han_muc_giong()
        self.assertEqual((h["dung"], h["con"], h["goi"]), (1200, 98800, "creator"))

    def test_loi_khong_nem(self):
        with mock.patch.object(giong, "client", side_effect=RuntimeError("401 missing_permissions")):
            self.assertIn("quyền", giong.han_muc_giong()["loi"])


if __name__ == "__main__":
    unittest.main()
