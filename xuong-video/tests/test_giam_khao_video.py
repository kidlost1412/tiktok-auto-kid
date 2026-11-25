"""Giám khảo đưa Gemini cả VIDEO thật (mp4 có tiếng) và XOÁ chat Antigravity sau mỗi lần hỏi. Dùng runner/gui/RPC giả, KHÔNG gọi Antigravity thật."""
import json, os, re, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp(prefix="xv-gkv-")
os.environ.setdefault("XUONG_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import dao_dien as dd  # noqa: E402
import hoc_canh as hc  # noqa: E402
import kiem_may as km  # noqa: E402
from PIL import Image  # noqa: E402

CID = "e50a7ddd-2ea1-441b-a962-dacff23d616e"


def muc_ai():
    return {"muc": [{"id": k, "dat": True, "ly_do": "", "giay": None} for k in km.TEN_MUC], "loi": [], "sua": ""}


class VideoChoGeminiTest(unittest.TestCase):
    SP = {"ten_goi": "Đạm cá", "ten_ngan": "Đạm cá", "qua_tang": []}
    SENTS = [{"s": 0.0, "e": 3.0, "text": "Mở đầu"}]

    def setUp(self):
        self.hub = Path(tempfile.mkdtemp(prefix="hub-", dir=TMP)); self.work = Path(tempfile.mkdtemp(prefix="work-", dir=TMP))
        self.cfg = {"giam_khao": {"may": "gemini", "model": "m"}}
        for ten, v in (("HUB", self.hub),):
            p = mock.patch.object(dd, ten, v); p.start(); self.addCleanup(p.stop)
        p = mock.patch.object(dd, "cfg_hub", lambda: self.cfg); p.start(); self.addCleanup(p.stop)

        def anh_gia(video, sents, out, blocks=None):
            Image.new("RGB", (60, 60), "gray").save(out)
            return out, []
        p = mock.patch.object(dd, "to_ban_dung", anh_gia); p.start(); self.addCleanup(p.stop)
        self.claude = []

        def goi_gia(vai, prompt, anh=None, **kw):
            self.claude.append({"prompt": prompt, "anh": anh})
            return json.dumps(muc_ai()), {}
        p = mock.patch.object(dd, "goi", goi_gia); p.start(); self.addCleanup(p.stop)
        dd._GK_DA_BAO.clear()
        self.video = Path(tempfile.mkdtemp(prefix="vid-", dir=TMP)) / "out.mp4"
        self.video.write_bytes(b"\x00\x00\x00\x18ftypmp42FAKE")

    def cham(self, **kw):
        return dd.giam_khao(self.SP, str(self.video), self.SENTS, {"cong_thuc": "c", "gu": "g", "khoi": []}, self.work, **kw)

    def test_gemini_nhan_video_va_don_sau_khi_xong(self):
        thay = {}

        def runner(model, prompt, out_file, han=120, **kw):
            m = re.search(r"VIDEO THẬT[^\n]*: (\S+\.mp4)", prompt)
            thay["prompt"] = prompt
            thay["mp4"] = Path(m.group(1)) if m else None
            thay["ton_tai"] = bool(m) and thay["mp4"].is_file()
            thay["giong"] = bool(m) and thay["mp4"].read_bytes() == self.video.read_bytes()
            Path(out_file).write_text(json.dumps(muc_ai()), encoding="utf-8")
            return Path(out_file).read_text(encoding="utf-8")
        kq = self.cham(runner=runner)
        self.assertEqual(kq["nguon"], "gemini"); self.assertEqual(self.claude, [])
        self.assertTrue(thay["ton_tai"] and thay["giong"])                         # lúc hỏi, mp4 nằm cạnh ảnh trong lich-su/_giam-khao
        self.assertEqual(thay["mp4"].parent, self.hub / "lich-su" / "_giam-khao")
        self.assertIn("NGHE", thay["prompt"]); self.assertIn("nhạc", thay["prompt"]); self.assertIn("Tờ ảnh".upper(), thay["prompt"].upper())
        self.assertFalse(thay["mp4"].exists())                                     # xong là xoá
        self.assertEqual(list((self.hub / "lich-su" / "_giam-khao").iterdir()), [])
        self.assertTrue(self.video.is_file())                                      # video gốc còn nguyên

    def test_don_mp4_ca_khi_runner_loi(self):
        thay = {}

        def hong(model, prompt, out_file, **kw):
            thay["mp4"] = Path(re.search(r"VIDEO THẬT[^\n]*: (\S+\.mp4)", prompt).group(1))
            raise hc.LoiTam("quá hạn")
        kq = self.cham(runner=hong)
        self.assertIsNone(kq["diem"]); self.assertEqual(self.claude, [])           # không rơi sang Claude (Kid 25/11)
        self.assertFalse(thay["mp4"].exists()); self.assertEqual(list((self.hub / "lich-su" / "_giam-khao").iterdir()), [])

    def test_khong_co_file_video_thi_nhu_cu(self):
        thay = {}

        def runner(model, prompt, out_file, **kw):
            thay["p"] = prompt
            Path(out_file).write_text(json.dumps(muc_ai()), encoding="utf-8")
            return Path(out_file).read_text(encoding="utf-8")
        self.video.unlink()
        self.assertEqual(self.cham(runner=runner)["nguon"], "gemini")
        self.assertNotIn("VIDEO THẬT", thay["p"])


class XoaChatTest(unittest.TestCase):
    def test_hoi_mot_lan_xoa_chat_khi_thanh_cong(self):
        out = Path(tempfile.mkdtemp(prefix="hml-", dir=TMP)) / "kq.json"
        log = []

        def ngu(giay):
            out.write_text('{"a": 1}', encoding="utf-8")
        hc.hoi_mot_lan("m", "hoi", out, han=30, gui=lambda *a: CID, huy_cuoc=log.append, ngu=ngu, xoa_cuoc=lambda c: log.append(("xoa", c)))
        self.assertEqual(log, [CID, ("xoa", CID)])                                   # dừng rồi xoá

    def test_hoi_mot_lan_xoa_chat_khi_het_gio(self):
        out = Path(tempfile.mkdtemp(prefix="hml-", dir=TMP)) / "kq.json"
        xoa = []
        with self.assertRaises(hc.LoiTam):
            hc.hoi_mot_lan("m", "hoi", out, han=7, gui=lambda *a: CID, huy_cuoc=lambda c: None, ngu=lambda g: None, xoa_cuoc=xoa.append)
        self.assertEqual(xoa, [CID])

    def test_hoi_mot_lan_xoa_chat_khi_huy(self):
        out = Path(tempfile.mkdtemp(prefix="hml-", dir=TMP)) / "kq.json"
        import threading
        huy = threading.Event(); xoa = []

        def ngu(g):
            huy.set()
        with self.assertRaises(hc.Huy):
            hc.hoi_mot_lan("m", "hoi", out, han=30, gui=lambda *a: CID, huy_cuoc=lambda c: None, ngu=ngu, huy=huy, xoa_cuoc=xoa.append)
        self.assertEqual(xoa, [CID])

    def test_khong_gui_duoc_thi_khong_xoa(self):
        out = Path(tempfile.mkdtemp(prefix="hml-", dir=TMP)) / "kq.json"
        xoa = []

        def gui(*a):
            raise hc.ChuaMo("chưa mở")
        with self.assertRaises(hc.ChuaMo):
            hc.hoi_mot_lan("m", "hoi", out, han=7, gui=gui, huy_cuoc=lambda c: None, ngu=lambda g: None, xoa_cuoc=xoa.append)
        self.assertEqual(xoa, [])

    def test_xoa_loi_khong_lam_hong_viec_cham(self):
        out = Path(tempfile.mkdtemp(prefix="hml-", dir=TMP)) / "kq.json"

        def ngu(giay):
            out.write_text('{"a": 1}', encoding="utf-8")

        def xoa_hong(c):
            raise RuntimeError("không xoá được")
        txt = hc.hoi_mot_lan("m", "hoi", out, han=30, gui=lambda *a: CID, huy_cuoc=lambda c: None, ngu=ngu, xoa_cuoc=xoa_hong)
        self.assertEqual(json.loads(txt), {"a": 1}); self.assertFalse(out.exists())
        with self.assertRaises(hc.LoiTam):                                          # lỗi gốc vẫn là lỗi gốc, không bị lỗi xoá che
            hc.hoi_mot_lan("m", "hoi", out, han=7, gui=lambda *a: CID, huy_cuoc=lambda c: None, ngu=lambda g: None, xoa_cuoc=xoa_hong)

    def test_chay_lo_xoa_chat(self):
        ra = Path(tempfile.mkdtemp(prefix="lo-", dir=TMP)) / "a.json"
        xoa = []

        def ngu(g):
            ra.write_text("{}", encoding="utf-8")
        with mock.patch.object(hc, "_luu", lambda: None):
            hc.chay_lo("m", "p", [ra], "t", lambda *a: None, gui=lambda *a: CID, huy_cuoc=lambda c: None, ngu=ngu, xoa_cuoc=xoa.append)
            self.assertEqual(xoa, [CID])
            xoa.clear()
            ra2 = ra.with_name("b.json")
            hc.chay_lo("m", "p", [ra2], "t", lambda *a: None, gui=lambda *a: CID, huy_cuoc=lambda c: None, ngu=lambda g: None, xoa_cuoc=xoa.append, han=7)
            self.assertEqual(xoa, [CID])                                            # quá hạn cũng xoá

    def test_xoa_cuoc_tro_chuyen_goi_rpc_dung(self):
        goi = []

        def ls(method, body, timeout=5):
            goi.append((method, body)); return {}
        with mock.patch.object(hc, "_goi_ls", ls):
            self.assertTrue(hc.xoa_cuoc_tro_chuyen(CID))
        self.assertIn(("DeleteCascadeTrajectory", {"cascadeId": CID}), goi)
        self.assertEqual(goi[-1][0], "DeleteCascadeTrajectory")                      # dừng trước, xoá sau
        self.assertFalse(hc.xoa_cuoc_tro_chuyen(None))

    def test_xoa_cuoc_tro_chuyen_khong_nem_loi(self):
        with mock.patch.object(hc, "_goi_ls", side_effect=RuntimeError("boom")):
            self.assertFalse(hc.xoa_cuoc_tro_chuyen(CID))

    def test_du_phong_xoa_file_dung_cuoc_khi_antigravity_dong(self):
        nha = Path(tempfile.mkdtemp(prefix="agy-", dir=TMP)); g = nha / "conversations"; b = nha / "brain"
        g.mkdir(); b.mkdir()
        khac = "11111111-2222-3333-4444-555555555555"
        for c in (CID, khac):
            (g / f"{c}.db").write_text("x"); (b / c).mkdir(); (b / c / "f.txt").write_text("y")
        with mock.patch.object(hc, "_dir_cuoc_tro_chuyen", lambda: nha), mock.patch.object(hc, "_goi_ls", lambda *a, **k: None), \
                mock.patch.object(hc, "tim_hub", lambda *a, **k: None):
            self.assertTrue(hc.xoa_cuoc_tro_chuyen(CID))
            self.assertFalse((g / f"{CID}.db").exists()); self.assertFalse((b / CID).exists())
            self.assertTrue((g / f"{khac}.db").exists() and (b / khac).exists())     # cuộc khác còn nguyên
            self.assertFalse(hc._xoa_file_cuoc("../../x")); self.assertFalse(hc.xoa_cuoc_tro_chuyen("*"))

    def test_hub_con_song_ma_rpc_loi_thi_khong_xoa_file(self):
        nha = Path(tempfile.mkdtemp(prefix="agy-", dir=TMP)); g = nha / "conversations"; g.mkdir()
        (g / f"{CID}.db").write_text("x")
        with mock.patch.object(hc, "_dir_cuoc_tro_chuyen", lambda: nha), mock.patch.object(hc, "_goi_ls", lambda *a, **k: None), \
                mock.patch.object(hc, "tim_hub", lambda *a, **k: {"httpPort": 1, "csrfToken": "t"}):
            self.assertFalse(hc.xoa_cuoc_tro_chuyen(CID))
            self.assertTrue((g / f"{CID}.db").exists())                              # file đang được Antigravity dùng: không đụng


if __name__ == "__main__":
    unittest.main()
