"""Bản nhẹ cho học cảnh kiểu 3 (video > 90 MB: Antigravity không đọc nổi). Runner GIẢ — không gọi Antigravity/Gemini.
ffmpeg thật chỉ chạy trên clip tổng hợp vài giây trong thư mục tạm."""
import json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_hoc_canh_v3 import Nen, gia, hc, p3, km  # noqa: E402
import ban_nhe as BN  # noqa: E402


class BanNheTest(unittest.TestCase):
    def test_cac_khuc_va_bitrate(self):
        self.assertEqual(BN.cac_khuc(400), [(0.0, 400.0)])
        k = BN.cac_khuc(1500)                                   # 25 phút → 3 khúc đều 500 s, liền nhau
        self.assertEqual(len(k), 3)
        self.assertAlmostEqual(sum(d for _a, d in k), 1500, places=2)
        self.assertEqual([a for a, _d in k], [0.0, 500.0, 1000.0])
        self.assertEqual(BN.bitrate(60), 1200); self.assertEqual(BN.bitrate(10 ** 5), 350)
        self.assertLess((BN.bitrate(900) + 48) * 900 / 8 / 1024, 95)          # 15 phút vẫn < 95 MiB

    def test_ghep_doi_gio_va_id(self):
        f1 = gia.form_v3(10.0, 2); f2 = gia.form_v3(8.0, 2)
        f2["vat"] = [dict(x) for x in f2["vat"]]
        f2["vat"][0]["la"] = "sp_khac:Thuốc X"                   # cùng id nhưng là vật khác → phải đổi id
        cu = f2["vat"][0]["id"]
        g = BN.ghep([(f1, 0.0), (f2, 10.0)])
        self.assertEqual(p3.kiem_video(g, 18.0), [])
        self.assertEqual(g["doan"][-1]["den"], 18.0)
        self.assertIn(f"{cu}_k2", [x["id"] for x in g["vat"]])
        self.assertEqual(f1["doan"][0]["tu"], 0)                  # không sửa phiếu gốc

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "cần ffmpeg")
    def test_lam_ban_nhe_that(self):
        d = Path(tempfile.mkdtemp(prefix="bn-"))
        self.addCleanup(shutil.rmtree, d, True)
        src = d / "goc.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:duration=7",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=7", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(src)], check=True)
        with mock.patch.object(BN, "TRAN_MOT_KHUC_S", 4), mock.patch.object(BN, "KHUC_S", 3):
            ra = BN.lam(src, 7.0, d / "nhe", km.do_dai_video)
            self.assertEqual(len(ra), 3)
            for c in ra:
                self.assertLessEqual(abs(km.do_dai_video(c["src"]) - c["dai"]), BN.LECH_S)
                h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height", "-of", "csv=p=0", c["src"]],
                                   capture_output=True, text=True).stdout.strip()
                self.assertEqual(h, "720")
            t = Path(ra[0]["src"]).stat().st_mtime
            self.assertEqual(BN.lam(src, 7.0, d / "nhe", km.do_dai_video), ra)          # lần hỏi lại: dùng lại, không nén lại
            self.assertEqual(Path(ra[0]["src"]).stat().st_mtime, t)


class HocBanNheTest(Nen):
    def test_video_nang_hoc_qua_ban_nhe_va_ghep_khuc(self):
        (self.kho / "nhe.mp4").write_bytes(b"x"); (self.kho / "nang.mp4").write_bytes(b"x"); (self.kho / "dai.mp4").write_bytes(b"x")
        log, goi = [], []
        dai_cua = lambda p: 1500.0 if Path(p).name == "dai.mp4" else 40.0

        def lam(src, dai, thu_muc, do_dai):
            goi.append(Path(src).name)
            Path(thu_muc).mkdir(parents=True, exist_ok=True)
            return [{"src": str(Path(thu_muc) / f"{Path(src).stem}-k{i}.mp4"), "lech": a, "dai": d} for i, (a, d) in enumerate(BN.cac_khuc(dai), 1)]
        with mock.patch.object(BN, "can_nhe", lambda p: Path(p).name != "nhe.mp4"), mock.patch.object(BN, "lam", lam):
            r = self._chay(gia.runner_v3_gia(log), do_dai=dai_cua)
        self.assertEqual(r["da_hoc"], 3, r)
        self.assertEqual(sorted(goi), ["dai.mp4", "nang.mp4"])
        lo_dai = next(x for x in log if any("dai-k" in f for _m, _d, f in x["ds"]))
        self.assertEqual(len(lo_dai["ds"]), 3)                                    # video dài đi một mình, 3 khúc
        self.assertEqual(lo_dai["kw"]["han"], 150 * 3 + 60)
        lo_ngan = next(x for x in log if x is not lo_dai)
        self.assertEqual(sorted(Path(f).name for _m, _d, f in lo_ngan["ds"]), ["nang-k1.mp4", "nhe.mp4"])
        v = self._v3("dai.mp4")
        self.assertFalse((self.kho / "_tam" / "ban-nhe").exists())                # xong là xoá bản nhẹ
        self.assertTrue(json.dumps(v, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
