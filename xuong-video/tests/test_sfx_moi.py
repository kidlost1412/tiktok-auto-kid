"""Âm thanh chọn theo nghĩa (sfx.py) + kiểm âm (kiem_am.py) + danh mục âm đóng gói (mau/sfx-moi).
Không gọi mạng/AI. ffmpeg thật chỉ dùng để tạo/đo âm tổng hợp (sin/nhiễu) trong thư mục tạm; không có ffmpeg thì bỏ qua phần đó."""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GOC = Path(__file__).resolve().parents[1]
_tmp = tempfile.TemporaryDirectory()
os.environ.setdefault("XUONG_DATA", _tmp.name)
for _p in (str(GOC / "app"), str(GOC / "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import kho_nhac  # noqa: E402
import kiem_am as KA  # noqa: E402
import sfx as SFX  # noqa: E402

CO_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
F = lambda s: int(round(s * 30))


def kh(loai, t0, t1, **kw):
    return {"loai": loai, "f0": F(t0), "f1": F(t1), **kw}


class Nen(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.addCleanup(SFX.dung_lai)
        for p in (mock.patch.object(SFX, "ROOT", Path(self.td.name) / "sfx"), mock.patch.object(kho_nhac, "sfx_phu", lambda: [])):
            p.start()
            self.addCleanup(p.stop)
        SFX.dung_lai()

    def lich(self, blocks, cuts=(), total=20.0, muc="vua", seed=3, **kw):
        """giu_mo=False: bỏ âm mở MẶC ĐỊNH (chọn từ thực đơn) để các test ánh xạ chỉ nhìn tiếng của khối (test riêng ở TestHookMacDinh)."""
        kw.setdefault("trans", "cat")
        giu = kw.pop("giu_mo", False) or "am_mo" in kw or "st" in kw
        ev = SFX.len_lich(muc, blocks, list(cuts), total, random.Random(seed), kw.pop("pops", None), **kw)
        return ev if giu else [e for e in ev if e["nguon"] != "mo"]


class TestDanhMuc(Nen):
    def test_goi_moi_du_va_da_do_san(self):
        dm = SFX.danh_muc()
        moi = [e for e in dm.values() if e["goc"] == "moi"]
        self.assertEqual(len(moi), 40)                                     # 45 file đóng gói − 5 file chói bị CAM (ting/xèng 8,5–9 kHz, tách bật lửa, 2 máy đánh chữ)
        for e in moi:
            for k in ("nhom", "vai", "mo_ta", "dai", "dinh_db", "t_dinh", "t_bat", "tan_cong"):
                self.assertIn(k, e, e["file"])
            self.assertTrue(Path(e["file"]).exists())
            self.assertTrue(e["mo_ta"])
        self.assertEqual({e["vai"] for e in moi if e["nhom"] == "go_phim"}, {"typing"})

    def test_thieu_file_khong_loi(self):
        g = Path(self.td.name) / "moi"
        g.mkdir()
        (g / "danh-muc.json").write_text(json.dumps([{"nhom": "dap", "file": "dap/khong-co.wav", "mo_ta": "x", "dai": 1, "dinh_db": -3, "t_dinh": 0.1, "t_bat": 0}]), encoding="utf-8")
        with mock.patch.object(kho_nhac, "goc_sfx_moi", lambda: g):
            SFX.dung_lai()
            self.assertEqual(SFX.danh_muc(), {})
            self.assertEqual(SFX.len_lich("vua", [kh("hook_dap", 1, 3)], [], 10, random.Random(1)), [])      # không file nào → lịch rỗng, không lỗi

    def test_hong_json_goi_khong_lam_sap(self):
        g = Path(self.td.name) / "moi"
        g.mkdir()
        (g / "danh-muc.json").write_text("{không phải json", encoding="utf-8")
        with mock.patch.object(kho_nhac, "goc_sfx_moi", lambda: g):
            SFX.dung_lai()
            self.assertEqual(SFX.len_lich("vua", [kh("hook_dap", 1, 3)], [], 10, random.Random(1)), [])

    @unittest.skipUnless(CO_FFMPEG, "cần ffmpeg")
    def test_do_mot_lan_roi_nho(self):
        goc = Path(self.td.name) / "sfx"
        (goc / "x").mkdir(parents=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=800:duration=0.3", str(goc / "x" / "a.wav")], check=True)
        (goc / "x" / "hong.wav").write_bytes(b"khong phai am thanh")
        with mock.patch.object(SFX, "KHO_MAC_DINH", {"bop": ["x/a.wav", "x/hong.wav", "x/mat.wav"]}), \
                mock.patch.object(kho_nhac, "goc_sfx_moi", lambda: Path(self.td.name) / "khong-co"):
            SFX.dung_lai()
            dm = SFX.danh_muc(do_het=True)
            self.assertEqual([e["file"] for e in dm.values()], ["x/a.wav"])         # file hỏng + file thiếu bị loại
            e = next(iter(dm.values()))
            self.assertAlmostEqual(e["dai"], 0.3, delta=0.05)
            self.assertAlmostEqual(e["dinh_db"], -18.1, delta=1.5)        # sine của lavfi mặc định biên độ 1/8
            self.assertTrue((goc / "_kho-am.json").exists())
            SFX.dung_lai()
            with mock.patch.object(kho_nhac, "do_am", side_effect=AssertionError("đo lại")):
                self.assertIsNotNone(SFX.dac_tinh("x/a.wav"))                         # lần 2 lấy từ cache

    def test_mo_ta_am(self):
        d = SFX.mo_ta_am()
        for k in ("dap", "go_phim", "tick", "con_dau", "tien", "khong"):
            self.assertIn(k, d)
            self.assertTrue(d[k].strip())
        self.assertIn("gõ máy", d["go_phim"])
        for k in ("no_lon", "vo_tay"):                                                    # nổ meme / vỗ tay: không mời đạo diễn chọn
            self.assertNotIn(k, d)
        for k in ("chup", "sai"):                                                         # màn trập / còi sai: trả lại, kèm điều kiện dùng trong mô tả
            self.assertIn(k, d)
            self.assertIn("CHỈ", d[k])
        self.assertNotIn("nen_vuon", d)                                                  # kho cũ không cài thì nhóm không có file bị bỏ

    def test_nhom_moi_nhan_dang_file_nguoi_dung(self):
        self.assertEqual(kho_nhac.nhom_sfx("x/rubber-stamp-01.wav"), ["con_dau"])
        self.assertEqual(kho_nhac.nhom_sfx("tick/a.mp3"), ["tick"])


class TestAnhXa(Nen):
    def test_go_may_khong_bao_gio_dap_hay_no(self):
        ev = self.lich([kh("hook_go_may", 0.5, 4.0, text="NẤM TRĨ HẠI BÔNG")], total=8)
        self.assertGreaterEqual(len(ev), 3)
        self.assertEqual({e["nhom"] for e in ev}, {"go_phim"})
        self.assertTrue(all(e["vai"] == "typing" and e["db"] <= -12 for e in ev))
        self.assertTrue(all(e["t"] >= 0.5 - 0.03 for e in ev))
        self.assertEqual(len({e["cum"] for e in ev}), 1)                              # cả lúc gõ = 1 cử chỉ

    def test_go_may_trai_het_luc_go(self):
        ev = self.lich([kh("hook_go_may", 1.0, 5.0, text="x" * 40, cps=10)], total=8)
        self.assertGreater(max(e["t_neo"] for e in ev) - min(e["t_neo"] for e in ev), 2.5)

    def test_hook_dap_la_nhat_tram_nhe_khong_phai_man_trap(self):
        ev = self.lich([kh("hook_dap", 3.0, 5.0)], total=8)                         # 24/11 chủ hàng: bỏ màn trập; nhát trầm nhẹ, ngắn ≤ 0,5 s
        self.assertEqual([e["nhom"] for e in ev], ["dap"])
        self.assertEqual(ev[0]["vai"], "hit")
        self.assertLessEqual(ev[0]["dai"], 0.5)

    def test_canh_bao_la_am_bao_khong_phai_chuong_tien(self):
        ev = self.lich([kh("canh_bao", 2.0, 4.0)], total=8)
        self.assertEqual({e["nhom"] for e in ev}, {"dap"})                          # không còi sai kiểu game show
        self.assertEqual(ev[0]["vai"], "hit")

    def test_sai_chi_khi_loi_neu_cai_sai(self):
        wb = lambda text, f0=1.0, **kw: kh("loi_slam", f0, f0 + 1.5, vai="warn", text=text, **kw)
        ev = self.lich([wb("SAI LẦM PHỔ BIẾN")], total=8)
        self.assertEqual([e["nhom"] for e in ev], ["sai"])
        self.assertEqual(ev[0]["vai"], "alert")
        for t in ("ĐỪNG PHUN BUỔI TRƯA", "lỗi thường gặp", "tốn tiền", "phí thuốc", "không nên", "NHẦM"):
            self.assertEqual([e["nhom"] for e in self.lich([wb(t)], total=8)], ["sai"], t)
        for t in ("MẤT MÙA", "PHUY 200 LÍT", "CÂY RỤNG LÁ", "SAIGON"):    # warn trung tính / từ chứa "sai" không phải từ nguyên
            self.assertNotIn("sai", {e["nhom"] for e in self.lich([wb(t)], total=8)}, t)
        ev = self.lich([wb("SAI"), wb("LỖI", 4.0), wb("ĐỪNG", 7.0)], total=12)
        self.assertEqual(sum(e["nhom"] == "sai" for e in ev), 1)                       # tối đa 1 lần/video
        self.assertNotIn("sai", {e["nhom"] for e in self.lich([kh("loi_slam", 1, 2.5, vai="val", text="SAI")], total=8)})   # không phải warn
        self.assertEqual({e["nhom"] for e in self.lich([kh("canh_bao", 2, 4, text="lỗi thường gặp")], total=8)}, {"sai"})
        self.assertEqual({e["nhom"] for e in self.lich([kh("canh_bao", 2, 4, text="chú ý")], total=8)}, {"dap"})

    def test_chup_chi_khi_hinh_loe_trang(self):
        ev = self.lich([kh("loi_hook_flash", 0.0, 2.0, text="BỌ TRĨ")], total=8)
        self.assertEqual([e["nhom"] for e in ev if e["nguon"] != "mo"], ["chup"])
        self.assertEqual([e["nhom"] for e in self.lich([kh("loi_hook_drop", 0.0, 2.0, text="BỌ TRĨ")], total=8)], ["dap"])
        for b in (kh("loi_slam", 1, 2.5, vai="warn", text="MẤT 30%"), kh("loi_slam", 1, 2.5, vai="val", text="200 LÍT")):
            self.assertNotIn("chup", {e["nhom"] for e in self.lich([b], total=8)})
        self.assertEqual([e["nhom"] for e in self.lich([kh("truoc_sau", 2, 4)], total=8)], ["chup"])

    def test_tem_la_cai_thich_khong_phai_man_trap(self):
        ev = self.lich([kh("hook_tem", 2.0, 4.0)], total=8)
        self.assertEqual([e["nhom"] for e in ev], ["con_dau"])
        self.assertNotIn("chup", {e["nhom"] for e in ev})

    def test_the_qua_va_hop_qua_mot_tieng(self):
        for loai in ("the_qua", "hop_qua"):
            ev = self.lich([kh(loai, 2.0, 5.0)], total=8)
            self.assertEqual(len(ev), 1, loai)

    def test_nut_gio_hang_dung_tu_noi(self):
        ev = self.lich([kh("nut_gio_hang", 15.4, 18.0, t_am=15.9)], total=18)
        self.assertEqual([e["nhom"] for e in ev], ["tien"])
        self.assertAlmostEqual(ev[0]["t_neo"], 15.9, places=2)

    def test_so_dem_tach_roi_ting_khi_dung(self):
        ev = self.lich([kh("so_dem", 4.4, 6.4)], total=10)
        self.assertEqual([e["nhom"] for e in ev][-1], "ting")
        self.assertAlmostEqual(ev[-1]["t_neo"], F(4.4) / 30 + 26 / 30, places=2)
        self.assertIn(ev[0]["nhom"], ("tick", "bop"))
        self.assertLess(ev[0]["t"], ev[-1]["t"])

    def test_checklist_cung_mot_tieng_moi_dong(self):
        ev = self.lich([kh("checklist", 2.0, 6.0, n=4)], total=10)
        self.assertEqual(len(ev), 4)
        self.assertEqual(len({e["file"] for e in ev}), 1)
        self.assertTrue(all(e["lap_ok"] for e in ev))

    def test_mot_ho_ui_moi_video(self):
        bl = [kh("hook_hoi", 1, 3), kh("nhan_dan", 4, 6), kh("so_dem", 7, 9), kh("loai_la", 11, 12), kh("checklist", 13, 17, n=3)]
        for seed in range(8):
            ev = self.lich(bl, total=20, seed=seed)
            ui = {e["nhom"] for e in ev if e["vai"] == "ui"}
            self.assertEqual(len(ui), 1, (seed, ui))

    def test_loai_la_nhe_khong_sap(self):
        ev = self.lich([kh("hook_dap", 0, 2), kh("khoi_moi_chua_biet", 5, 7), {"loai": None, "f0": F(8), "f1": F(9)}, {"f0": F(9), "f1": F(10)},
                        {"loai": "x"}, {"loai": "y", "f0": "hong"}], total=12)
        la = [e for e in ev if abs(e["t_neo"] - 5.05) < 0.01]
        self.assertEqual(len(la), 1)
        self.assertEqual(la[0]["vai"], "ui")
        self.assertLessEqual(la[0]["db"], -12.5)
        self.assertEqual(self.lich([kh("khoi_la", 0, 2)], total=5)[0]["vai"], "ui")

    def test_khoi_loi_khong_lam_hong_lich(self):
        with mock.patch.object(SFX, "_khoi", side_effect=[RuntimeError("x"), [SFX._sp("dap", 5.0, 1, chinh=True)]]):
            ev = self.lich([kh("hook_dap", 1, 2), kh("hook_dap", 5, 6)], total=10)
        self.assertEqual(len(ev), 1)


class TestGhiDe(Nen):
    def test_am_ghi_de_ho_va_khong(self):
        ev = self.lich([kh("hook_dap", 2, 4, am="chup")], total=8)                         # đạo diễn chọn màn trập thì được
        self.assertEqual([e["nhom"] for e in ev], ["chup"])
        ev = self.lich([kh("hook_dap", 2, 4, am="no_lon")], total=8)                       # nổ meme bị đổi sang "dap"
        self.assertEqual([e["nhom"] for e in ev], ["dap"])
        ev = self.lich([kh("hook_dap", 2, 4, am="ting")], total=8)
        self.assertEqual([e["nhom"] for e in ev], ["ting"])
        self.assertEqual(self.lich([kh("hook_dap", 2, 4, am="khong")], total=8), [])
        ev = self.lich([kh("hook_dap", 2, 4, am="nhom_khong_co")], total=8)               # tên lạ → quay về ánh xạ mặc định
        self.assertEqual([e["nhom"] for e in ev], ["dap"])

    def test_am_go_phim_thanh_chuoi_go(self):
        ev = self.lich([kh("hook_dap", 2, 4, am="go_phim", text="abcdefghij" * 3)], total=8)
        self.assertGreaterEqual(len(ev), 3)
        self.assertEqual({e["nhom"] for e in ev}, {"go_phim"})

    def test_am_riser_dinh_roi_vao_dau_khoi(self):
        ev = self.lich([kh("hook_dap", 5, 7, am="keo_len")], total=10)
        self.assertEqual(ev[0]["nhom"], "keo_len")
        self.assertAlmostEqual(ev[0]["t_neo"], 5.0, places=2)
        m = SFX.dac_tinh(ev[0]["file"])
        self.assertAlmostEqual(ev[0]["t"] + m["t_dinh"], 5.0, delta=0.01)


class TestAmMo(Nen):
    def test_khong_no_o_giay_0_mac_dinh(self):
        for muc in ("gon", "vua", "soi_dong", "mo_dau_am"):
            ev = self.lich([kh("hook_mat_na", 0, 2.5), kh("canh_bao", 6, 8)], muc=muc, total=10)
            self.assertFalse([e for e in ev if e["t"] < 0.5 and e["vai"] in ("hit",)], muc)
            self.assertNotIn("no_lon", {e["nhom"] for e in ev})

    def test_am_mo_do_dao_dien_chon(self):
        ev = self.lich([kh("hook_tung_tu", 0, 2.5), kh("canh_bao", 6, 8)], total=10, am_mo="dap")
        mo = [e for e in ev if e["nguon"] == "mo"]
        self.assertEqual([e["nhom"] for e in mo], ["dap"])
        self.assertEqual(mo[0]["uu"], 0)
        self.assertFalse([e for e in ev if e["nhom"] == "vut_nhe" and e["t"] < 1.0])      # vút tự động của khối đầu nhường chỗ

    def test_am_mo_qua_st(self):
        ev = self.lich([kh("hook_tung_tu", 0, 2.5)], total=10, st={"am_mo": "ting"})
        self.assertEqual([e["nhom"] for e in ev if e["nguon"] == "mo"], ["ting"])

    def test_am_mo_khong_bo_nhat_tu_dong_cua_khoi_dau(self):
        ev = self.lich([kh("hook_tung_tu", 0, 2.5), kh("canh_bao", 6, 8)], total=10, am_mo="khong")
        self.assertEqual([e["nhom"] for e in ev], ["dap"])                              # vút tự động của khối đầu bị bỏ, không rít đĩa
        ev2 = self.lich([kh("hook_dap", 0, 2.5), kh("canh_bao", 6, 8)], total=10, giu_mo=True)
        self.assertEqual([e["nhom"] for e in ev2], ["dap", "thong_bao"])                 # nhát nặng thứ 2 hạ xuống tiếng nhẹ (≤ 1/3 cử chỉ); # khối đầu tự có tiếng giây đầu → không thêm rít đĩa

    def test_am_mo_ten_la_bi_bo_qua(self):
        ev = self.lich([kh("hook_mat_na", 0, 2.5)], total=10, am_mo="khong_co_nhom_nay")
        self.assertEqual([e["nhom"] for e in ev if e["nguon"] == "mo"], [])


class TestChuyenCanh(Nen):
    CUTS = [2, 4, 6, 8, 10, 12]

    def vut(self, **kw):
        return [e for e in self.lich([kh("canh_bao", 0.5, 1.5)], cuts=self.CUTS, total=14, **kw) if e["nguon"] == "chuyen"]

    def test_cat_cung_va_fade_im_lang(self):
        for t in ("cat", "fade", None, "hon_hop", "dissolve"):
            self.assertEqual(self.vut(trans=t), [], t)

    def test_chuyen_dong_moi_co_vut(self):
        for t in ("slideleft", "slideup", "zoomin", "smoothleft"):
            self.assertGreaterEqual(len(self.vut(trans=t)), 3, t)

    def test_hon_hop_theo_tung_cat(self):
        ev = self.vut(trans="hon_hop", chuyen_tung_cat=["fade", "slideleft", "cat", "zoomin", "fade", "smoothup"])
        self.assertEqual(sorted(round(e["t_neo"] - 0.14) for e in ev), [4, 8, 12])

    def test_khong_theo_xac_suat(self):
        a = [e["t_neo"] for e in self.vut(trans="slideleft", am_mo="khong")]      # am_mo="khong": âm mở ngẫu nhiên theo seed không được làm đổi mật độ
        b = [e["t_neo"] for s in range(5) for e in self.lich([kh("canh_bao", 0.5, 1.5)], cuts=self.CUTS, total=14, seed=s, trans="slideleft", am_mo="khong")
             if e["nguon"] == "chuyen"]
        self.assertEqual(len(b), 5 * len(a))

    def test_lat_trang_mot_cu_chi(self):
        lat = [3.0 + 0.2 * k for k in range(12)]
        ev = self.lich([kh("canh_bao", 0.5, 1.5)], total=10, pops=[{"lat": lat}])
        tk = [e for e in ev if e["nguon"] == "lat"]
        self.assertTrue(3 <= len(tk) <= 8)
        self.assertEqual(len({e["cum"] for e in tk}), 1)
        ts = sorted(e["t_neo"] for e in tk)
        self.assertTrue(all(b - a >= 0.16 - 1e-6 for a, b in zip(ts, ts[1:])))
        self.assertEqual(KA.chi_so_lich(tk, 10)["so_cu_chi"], 1)
        ev2 = self.lich([kh("canh_bao", 0.5, 1.5)], total=10, lat_trang=[lat])
        self.assertEqual(len([e for e in ev2 if e["nguon"] == "lat"]), len(tk))

    def test_pops_so_tu_gop(self):
        ev = self.lich([kh("canh_bao", 0.5, 1.5)], total=10, pops=[3.0, 3.03, 3.1, 6.0])
        self.assertEqual(len([e for e in ev if e["nguon"] == "pop"]), 2)


class TestHanChe(Nen):
    def test_mat_do_toi_da(self):
        bl = [kh("khoi_la", 0.5 + 0.8 * k, 1.2 + 0.8 * k) for k in range(12)] + [kh("canh_bao", 9.9, 10)]
        for muc, cap in (("gon", 6), ("vua", 9), ("soi_dong", 12)):
            ev = self.lich(bl, total=10.5, muc=muc)
            self.assertLessEqual(KA.chi_so_lich(ev, 10.5)["cu_chi_toi_da_10s"], cap, muc)
            self.assertTrue([e for e in ev if e["nhom"] in ("dap", "thong_bao")], "ưu tiên cao (khối cuối) phải còn")

    def test_bo_tieng_thap_truoc(self):
        bl = [kh("canh_bao", 1, 2), kh("khoi_la", 2.5, 3), kh("khoi_la", 3.5, 4), kh("khoi_la", 4.5, 5), kh("canh_bao", 6, 7), kh("khoi_la", 7.5, 8),
              kh("hook_dap", 8.5, 9.5)]
        ev = self.lich(bl, total=10, muc="gon")
        self.assertEqual({e["nhom"] for e in ev if e["uu"] <= 1}, {"dap", "thong_bao"})
        self.assertLessEqual(len(ev), 6)

    def test_file_dung_toi_da_2_lan(self):
        bl = [kh("hook_mat_na", 3.2 * k, 3.2 * k + 2) for k in range(14)]
        ev = self.lich(bl, total=46, muc="soi_dong")
        dem = {}
        for e in ev:
            dem[e["file"]] = dem.get(e["file"], 0) + 1
        self.assertTrue(dem)
        self.assertLessEqual(max(dem.values()), 2)
        self.assertEqual(KA.chi_so_lich(ev, 46)["file_lap"], [])

    def test_ho_tro_lap_ok_khong_tinh_lap(self):
        ev = self.lich([kh("hook_go_may", 1, 3, text="x" * 80)], total=6)
        self.assertGreater(len(ev), len({e["file"] for e in ev}))      # nhiều tiếng gõ dùng lại ít file hơn số tiếng
        self.assertEqual(KA.chi_so_lich(ev, 6)["file_lap"], [])

    def test_nhat_nang_toi_da_mot_phan_ba(self):
        bl = [kh("hook_dap", 1.5 * k, 1.5 * k + 1) for k in range(7)] + [kh("canh_bao", 11, 12), kh("so_dem", 12.5, 14)]
        ev = self.lich(bl, total=15, muc="soi_dong")
        r = KA.chi_so_lich(ev, 15)
        self.assertGreaterEqual(r["so_nang"], 1)
        self.assertLessEqual(r["so_nang"], max(1, r["so_cu_chi"] // 3))

    def test_khoang_cach_khac_ho(self):
        bl = [kh("canh_bao", 2.0, 3.0), kh("the_qua", 2.1, 3.0), kh("khoi_la", 2.2, 3.0)]
        ev = self.lich(bl, total=6)
        self.assertEqual(KA.chi_so_lich(ev, 6)["va_cham"], [])
        self.assertEqual([e["nhom"] for e in ev if e["uu"] == 1 or e["uu"] == 0].count("dap"), 1)


class TestMucVaGain(Nen):
    def test_gain_ve_dinh_theo_vai(self):
        ev = self.lich([kh("hook_dap", 3, 5), kh("canh_bao", 6, 8), kh("hook_go_may", 9, 11, text="abc" * 10), kh("so_dem", 12, 14)], total=16)
        goc = {"whoosh": -9, "hit": -9, "foley": -8, "alert": -10, "typing": -13, "ui": -11, "bell": -10}   # hit −3 dB: nhát trầm nhẹ
        for e in ev:
            m = SFX.dac_tinh(e["file"])
            self.assertAlmostEqual(e["db"], goc[e["vai"]], delta=1.6, msg=e["nhom"])
            self.assertAlmostEqual(e["gain"] + m["dinh_db"], e["db"], delta=0.02)

    def test_neo_theo_dinh_va_luc_bat(self):
        ev = self.lich([kh("hook_dap", 3, 5), kh("canh_bao", 8, 10)], total=12)
        d = {e["nhom"]: e for e in ev}
        m = SFX.dac_tinh(d["dap"]["file"])
        self.assertAlmostEqual(d["dap"]["t"] + m["t_bat"], d["dap"]["t_neo"], delta=0.002)           # chữ đập (neo="bat"): LÚC BẮT ĐẦU rơi đúng khung chữ chạm
        ev = self.lich([kh("hook_dap", 3, 5, am="dap"), kh("canh_bao", 8, 10)], total=12)
        d = {e["nhom"]: e for e in ev}
        m = SFX.dac_tinh(d["dap"]["file"])
        self.assertAlmostEqual(d["dap"]["t"] + m["t_dinh"], d["dap"]["t_neo"], delta=0.002)           # nhát trầm do đạo diễn chọn: ĐỈNH rơi vào mốc
        ev = self.lich([kh("so_dem", 3, 5)], total=8)
        d = {e["nhom"]: e for e in ev}
        m = SFX.dac_tinh(d["ting"]["file"])
        self.assertAlmostEqual(d["ting"]["t"] + m["t_bat"], d["ting"]["t_neo"], delta=0.002)          # chuông: lúc bắt đầu nghe

    def test_muc_chi_doi_so_luong_va_to_khong_doi_cap_am_hinh(self):
        bl = [kh("hook_dap", 1, 3), kh("canh_bao", 5, 7), kh("hook_mat_na", 9, 11), kh("so_dem", 13, 15), kh("nut_gio_hang", 17, 19)]
        kq = {}
        for muc in ("gon", "vua", "soi_dong", "mo_dau_am", "em", "ten_la"):
            kq[muc] = self.lich(bl, total=20, muc=muc, seed=5)
        cap = lambda ev: [(e["khoi"] if "khoi" in e else None, e["nhom"]) for e in ev if e["nhom"] in ("dap", "sai", "ting", "tien")]
        self.assertEqual(cap(kq["gon"]), cap(kq["soi_dong"]))
        self.assertLess(kq["gon"][0]["gain"], kq["soi_dong"][0]["gain"])
        self.assertEqual([e["nhom"] for e in kq["em"]], [e["nhom"] for e in kq["gon"]])
        self.assertEqual(kq["ten_la"][0]["db"], kq["vua"][0]["db"])

    def test_xac_dinh_cung_hat_giong(self):
        bl = [kh("hook_dap", 1, 3), kh("checklist", 4, 8, n=3), kh("hook_go_may", 9, 11, text="ab" * 9)]
        a, b = self.lich(bl, total=14, seed=11), self.lich(bl, total=14, seed=11)
        self.assertEqual(a, b)


class TestTronLenh(Nen):
    def test_tick_ngan_khong_bi_nuot_dinh(self):
        ev = self.lich([kh("hook_go_may", 1, 3, text="abcdef")], total=6)
        args, fc = SFX.tron_lenh(ev, 1, "0:a", "a", 6)
        self.assertEqual(args.count("-i"), len(ev))
        self.assertIn("amix=inputs=%d" % (len(ev) + 1), fc[-1])
        self.assertIn("level=0", fc[-1])                           # limiter chỉ cắt đỉnh, không tự nâng to lại (đỉnh thật ≤ ~-1,4 dBFS)
        for f in fc[:-2]:
            self.assertIn("afade=t=out", f)
        self.assertEqual(SFX.tron_lenh([], 1, "0:a", "a", 6)[1], ["[0:a]anull[a]"])


@unittest.skipUnless(CO_FFMPEG, "cần ffmpeg")
class TestKiemAm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        d = Path(cls.td.name)

        def ff(out, graph):
            subprocess.run(["ffmpeg", "-v", "error", "-y", *graph, str(d / out)], check=True)
            return str(d / out)
        sine = lambda dur, vol: ["-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}", "-af", f"volume={vol}dB"]
        cls.on = ff("on.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-af", "volume=8dB,afade=t=out:st=5:d=1"])
        cls.lang = ff("lang.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                                   "-filter_complex", "[0:a]volume=0dB,aformat=sample_rates=44100:channel_layouts=mono[a];[1:a]atrim=0:3.5,aformat=sample_rates=44100:channel_layouts=mono[b];"
                                   "[a][b][a]concat=n=3:v=0:a=1,afade=t=out:st=7:d=0.4"])
        cls.cut = ff("cut.wav", sine(3, 0))
        cls.to = ff("to.wav", ["-f", "lavfi", "-i", "sine=frequency=300:duration=4", "-af", "volume=17.5dB,afade=t=out:st=3.5:d=0.5"])

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def test_do_on_dinh(self):
        r = KA.do_am_thanh(self.on)
        self.assertAlmostEqual(r["dai"], 6.0, delta=0.1)
        self.assertTrue(-20 < r["lufs"] < -8, r)
        self.assertLess(r["dinh_that_db"], -5)
        self.assertEqual(r["im_lang"], [])
        self.assertFalse(r["dut_dot_ngot"])

    def test_quang_lang_hon_2s(self):
        r = KA.do_am_thanh(self.lang)
        self.assertEqual(len(r["im_lang"]), 1, r)
        a, b = r["im_lang"][0]
        self.assertAlmostEqual(a, 2.0, delta=0.3)
        self.assertGreaterEqual(b - a, 3.0)

    def test_cat_dot_ngot(self):
        self.assertTrue(KA.do_am_thanh(self.cut)["dut_dot_ngot"])

    def test_dinh_that_gan_0(self):
        r = KA.do_am_thanh(self.to)
        self.assertGreater(r["dinh_that_db"], -3)
        self.assertFalse(r["dut_dot_ngot"])

    def test_kiem_am_tom_tat_va_nghe_thu(self):
        ev = [{"nhom": "dap", "vai": "hit", "file": "a", "t": 0.0, "t_neo": 0.1, "ly_do": "x"},
              {"nhom": "sai", "vai": "alert", "file": "b", "t": 2.0, "t_neo": 2.05, "ly_do": "băng cảnh báo"}]
        r = KA.kiem_am(self.to, ev, 4.0)
        self.assertIn("LUFS", r["tom_tat"])
        self.assertLessEqual(len(r["nghe_thu"]), 5)
        self.assertTrue(any("vượt" in v for v in r["van_de"]), r["van_de"])          # đỉnh thật > -1
        for m in r["nghe_thu"]:
            self.assertEqual(set(m), {"t", "gi", "vi_sao"})
        r2 = KA.kiem_am(self.lang, ev, 11.0)
        self.assertTrue(any(v.startswith("lặng") for v in r2["van_de"]))
        self.assertTrue(any("lặng" in m["gi"] for m in r2["nghe_thu"]))


class TestHookMacDinh(Nen):
    """23/11 Kid (bọ trĩ v10): hook phải có tiếng; tiếng trầm/đe chói bị loại; file lệch 1 kênh đưa về giữa."""
    def mo(self, loi_dau, seed, **kw):
        ev = self.lich([kh("hook_tung_tu", 1.0, 3.0), kh("canh_bao", 6, 8)], total=10, seed=seed, giu_mo=True, loi_dau=loi_dau, **kw)
        return [e for e in ev if e["nguon"] == "mo"]

    def test_thuc_don_am_mo_theo_loi_mo(self):
        tp = {m[0]["nhom"] for m in (self.mo("Cùng là bọ trĩ mà sao vườn anh sạch", k) for k in range(40)) if m}
        self.assertIn("rit_dia", tp)                                                      # tương phản → rít đĩa được phép
        self.assertLessEqual(tp, {"rit_dia", "dap", "vut_nhe"})
        for loi in ("Phuy 200 lít chỉ 350 nghìn", "Giá chỉ ba trăm nghìn"):
            so = {m[0]["nhom"] for m in (self.mo(loi, k) for k in range(40)) if m}
            self.assertIn("ting", so)                                                     # mở bằng số/giá → chuông
            self.assertNotIn("rit_dia", so)
        tt = [self.mo("Bọ trĩ hại bông rất nhanh", k) for k in range(60)]
        self.assertTrue(any(not m for m in tt), "thỉnh thoảng không có âm mở")
        thuong = {m[0]["nhom"] for m in tt if m}
        self.assertEqual(thuong, {"dap", "vut_nhe"})                                      # lời thường: không rít đĩa, không chuông
        self.assertEqual(self.mo("Cùng là bọ trĩ", 5), self.mo("Cùng là bọ trĩ", 5))     # cùng lời + cùng seed → cùng âm

    def test_am_mo_khong_ca_video_chung_mot_am(self):
        dung = {tuple(e["nhom"] for e in self.mo(l, k)) for l in ("Tưởng là hết", "Giá 99 nghìn", "Bọ trĩ hại bông") for k in range(30)}
        self.assertGreaterEqual(len(dung), 4)

    def test_boom_mo_khong_de_loi(self):
        for k in range(30):
            for e in self.mo("Bọ trĩ hại bông", k, giong_t0=0.6):
                if e["nhom"] == "dap":
                    m = SFX.dac_tinh(e["file"])
                    self.assertLessEqual(e["t"] + m["t_dinh"], 0.6, "đỉnh boom trước từ đầu tiên")
                    self.assertLessEqual(e["t"] + e["dai"], 0.6 + 0.12 + 0.01, "đuôi boom hết trước/sát lúc giọng vào")
                    self.assertLessEqual(e["db"], -9.0, "boom hạ nhỏ hơn nhát thường (−6 dB)")
        for e in self.mo("Bọ trĩ hại bông", 1, giong_t0=0.0) + self.mo("Bọ trĩ hại bông", 2, giong_t0=0.0):
            if e["nhom"] == "dap":
                self.assertLessEqual(e["dai"], 0.5)                                       # giọng vào ngay: boom cắt ngắn

    def test_dao_dien_tat_hoac_chon_khac(self):
        bl = [kh("hook_tung_tu", 1.0, 3.0)]
        self.assertNotIn("rit_dia", {e["nhom"] for e in self.lich(bl, total=6, am_mo="khong")})
        self.assertEqual([e["nhom"] for e in self.lich(bl, total=6, am_mo="ting") if e["nguon"] == "mo"], ["ting"])

    def test_tieng_bi_cam_khong_bao_gio_duoc_chon(self):
        with mock.patch.dict(SFX.KHO, {"chup": ["opener/anvil-loud.mp3", "x/transition-windy-swoosh.wav"]}):
            self.assertEqual(SFX._chon_file(["chup"], {}, random.Random(1)), (None, None))

    def test_file_lech_kenh_dua_ve_giua_va_dim_xi(self):
        ev = self.lich([kh("hook_dap", 1, 3)], total=5)
        with mock.patch.object(SFX, "lech_kenh", lambda p: 160.0):
            fc = SFX.tron_lenh(ev, 1, "0:a", "a", 5)[1]
        self.assertIn("pan=stereo|c0=c0|c1=c0", fc[0])
        with mock.patch.object(SFX, "lech_kenh", lambda p: 0.5):
            fc = SFX.tron_lenh(ev, 1, "0:a", "a", 5)[1]
        self.assertNotIn("pan=stereo", fc[0])
        self.assertIn("highshelf=f=7000", fc[0])


class TestChiSoLich(unittest.TestCase):
    def ev(self, t, nhom="bop", **kw):
        return {"nhom": nhom, "file": kw.pop("file", f"{nhom}.wav"), "t": t, "t_neo": t, **kw}

    def test_cu_chi_va_lo(self):
        ev = [self.ev(1.0), self.ev(1.05, "tick"), self.ev(5.0), self.ev(9.0)]
        r = KA.chi_so_lich(ev, 10)
        self.assertEqual(r["so_cu_chi"], 3)                       # 2 tiếng trong 80 ms = 1 cử chỉ
        self.assertEqual(r["lo_dai_nhat"]["giay"], 4.0)
        self.assertEqual(r["cu_chi_moi_10s"], 3.0)
        self.assertEqual(r["cu_chi_toi_da_10s"], 3)

    def test_ty_le_nang_lap_va_cham(self):
        ev = [self.ev(1.0, "dap", vai="hit"), self.ev(3.0, "dap", vai="hit", file="dap2.wav"), self.ev(5.0), self.ev(5.2, "ting"),
              self.ev(7.0, file="a"), self.ev(8.0, file="a"), self.ev(9.0, file="a")]
        r = KA.chi_so_lich(ev, 10)
        self.assertEqual(r["so_nang"], 2)
        self.assertEqual(r["so_cu_chi"], 7)                       # 5.0 và 5.2 cách 0,2 s > 80 ms: 2 cử chỉ riêng
        self.assertAlmostEqual(r["ty_le_nang"], 2 / 7, places=2)
        self.assertEqual(r["va_cham"][0]["a"], "bop")
        self.assertEqual(r["file_lap"], [{"file": "a", "so_lan": 3}])

    def test_cum_va_lap_ok(self):
        ev = [self.ev(1.0 + 0.1 * k, "go_phim", cum="g", lap_ok=True, file="k.wav") for k in range(6)]
        r = KA.chi_so_lich(ev, 5)
        self.assertEqual(r["so_cu_chi"], 1)
        self.assertEqual(r["file_lap"], [])
        self.assertEqual(r["va_cham"], [])

    def test_rong(self):
        r = KA.chi_so_lich([], 12)
        self.assertEqual((r["so_cu_chi"], r["lo_dai_nhat"]["giay"]), (0, 12.0))

    def test_nghe_thu_toi_da_5(self):
        ev = [self.ev(1.5 * k, "dap" if k % 2 else "sai", vai="hit" if k % 2 else "alert", ly_do="r") for k in range(14)]
        do = {"dai": 21.0, "im_lang": [(3.0, 6.0), (10.0, 13.0), (15.0, 18.0)], "dut_dot_ngot": True, "lufs": -15, "dinh_that_db": -3}
        li = KA.chi_so_lich(ev, 21)
        self.assertLessEqual(len(KA.chon_cho_nghe(do, ev, li, 21)), 5)


if __name__ == "__main__":
    unittest.main()
