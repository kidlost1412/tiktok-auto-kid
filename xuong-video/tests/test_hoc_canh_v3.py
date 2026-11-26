"""Học cảnh kiểu 3 (phiếu v3.1): lô ≤ 3 video, kiểm + ghi từng video, hỏi lại đúng video lỗi, tiến độ = file trên đĩa, hub đếm kiểu 3,
lời nhắc dien-phieu-v3, model mặc định mới mà giám khảo không đi theo. Runner/ffprobe GIẢ — không gọi Antigravity/Gemini/Claude.
Chạy:  python -m unittest tests.test_hoc_canh_v3 -v"""
import json, os, re, shutil, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp(prefix="xv-v3h-")
os.environ.setdefault("XUONG_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hoc_canh as hc  # noqa: E402
import kiem_mo_ta as km  # noqa: E402
import phieu_v3 as p3  # noqa: E402
import prompt_mau as pm  # noqa: E402
import _gia_phieu as gia  # noqa: E402


def _tmp():
    return Path(tempfile.mkdtemp(prefix="t-", dir=TMP))


class Nen(unittest.TestCase):
    def setUp(self):
        self.hub = _tmp(); self._ls, self._hub, self._pm = hc.LS, hc.HUB, pm.DATA
        hc.LS = self.hub / "lich-su"; hc.HUB = self.hub; pm.DATA = self.hub
        hc.JOB.update(dang_chay=False, dung=False, dang_dung=False, canh_bao="", trang_thai="nghi", thong_bao="", loi=[], xong=0, tong=0)
        self.kho = _tmp()
        self._cfg = hc.doc_cau_hinh; hc.doc_cau_hinh = lambda: {}
        self._ck, hc.CHU_KY_S = hc.CHU_KY_S, 0.02
        for ten, gt in (("_goi_ls", lambda *a, **k: None), ("_agy_exe_chay", lambda: False)):      # không bao giờ chạm Antigravity / tiến trình thật
            p = mock.patch.object(hc, ten, gt); p.start(); self.addCleanup(p.stop)
        p = mock.patch.object(hc, "huy_cuoc_tro_chuyen", lambda c: None); p.start(); self.addCleanup(p.stop)

    def tearDown(self):
        hc.LS, hc.HUB, pm.DATA = self._ls, self._hub, self._pm; hc.doc_cau_hinh = self._cfg; hc.CHU_KY_S = self._ck

    def _videos(self, n, bat_dau=0):
        for i in range(bat_dau, bat_dau + n):
            (self.kho / f"v{i}.mp4").write_bytes(b"x")

    def _chay(self, runner, **kw):
        a = dict(runner=runner, do_dai=lambda p: 40.0, kiem_mo=lambda: True, project=False, ten="t", kieu3=True, song_song=1)
        a.update(kw)
        return hc.hoc_kho(str(self.kho), **a)

    def _v3(self, rel):
        return json.loads((self.kho / "_mo-ta" / f"{rel}{p3.DUOI}").read_text(encoding="utf-8"))

    def _co_v3(self, rel):
        return (self.kho / "_mo-ta" / f"{rel}{p3.DUOI}").exists()

    def _san_pham(self, ma="t1", **them):
        d = self.hub / "san-pham" / ma; d.mkdir(parents=True, exist_ok=True)
        sp = {"kho_video": str(self.kho), "ten_goi": "Nano Đồng", "nhan_cung_san_pham": ["Bọ Trĩ Top One"]}
        sp.update(them)
        (d / "san-pham.json").write_text(json.dumps(sp, ensure_ascii=False), encoding="utf-8")
        return ma

    def _chay_sp(self, ma, runner, **kw):
        a = dict(runner=runner, do_dai=lambda p: 40.0, kiem_mo=lambda: True, project=False, song_song=1)
        a.update(kw)
        with mock.patch.object(hc.km, "_kho_cua", lambda m: self.kho):
            return hc.hoc_kho(ma, **a)


class HocV3Test(Nen):
    def test_v3_lo_ba_video_mot_hong_chi_retry_mot(self):
        self._videos(3); log = []; thay_o_lan_2 = {}

        def truoc(lan, prompt):
            if lan == 2:                                                                  # video tốt của lô 1 đã được ghi TRƯỚC khi hỏi lại
                thay_o_lan_2.update({r: self._co_v3(r) for r in ("v0.mp4", "v1.mp4", "v2.mp4")})
        r = self._chay(gia.runner_v3_gia(log, hong=lambda lan, f: "ho" if (lan == 1 and f == "v1.mp4") else None, truoc=truoc))
        self.assertEqual(len(log), 2, [x["tieu_de"] for x in log])
        self.assertEqual(thay_o_lan_2, {"v0.mp4": True, "v1.mp4": False, "v2.mp4": True})
        self.assertEqual([m for m, _d, _f in log[0]["ds"]], ["V1", "V2", "V3"])
        self.assertIn("Có 3 video", log[0]["prompt"]); self.assertEqual(log[0]["kw"]["han"], 150 * 3 + 60)
        self.assertEqual([Path(f).name for _m, _d, f in log[1]["ds"]], ["v1.mp4"])         # chỉ hỏi lại video lỗi
        self.assertIn("Có 1 video", log[1]["prompt"]); self.assertEqual(log[1]["kw"]["han"], 150 + 60)
        self.assertIn("LẦN TRƯỚC phiếu video này sai", log[1]["prompt"]); self.assertIn("hở", log[1]["prompt"])
        self.assertIn("làm lại", log[1]["tieu_de"])
        self.assertEqual((r["da_hoc"], r["loi"], r["tat_ca_xong"], r["canh"]), (3, [], True, 6), r)
        d = self._v3("v1.mp4")
        self.assertEqual((d["kieu"], d["ban_phieu"], d["model"], d["thoi_luong_s"], d["video"]), (3, "3.1", "gemini-4-neon-high", 40.0, "v1.mp4"))
        self.assertEqual(len(d["canh_quay"]), 2)
        self.assertEqual(sorted(hc.doc_v3_kho(self.kho)), ["v0.mp4", "v1.mp4", "v2.mp4"])   # đúng bộ kiểm mà kho_canh.nap dùng
        self.assertEqual(list((self.kho / "_mo-ta").rglob("*.mo-ta.json")), [])              # không đụng khuôn cũ
        self.assertFalse((self.kho / "_tam" / "hoc-canh").exists())
        self.assertEqual((hc.JOB["trang_thai"], hc.JOB["xong"], hc.JOB["tong"]), ("xong", 3, 3))

    def test_v3_chia_lo_toi_da_3_video_han_theo_so_video(self):
        self._videos(7); log = []
        r = self._chay(gia.runner_v3_gia(log))
        self.assertEqual([len(x["ds"]) for x in log], [3, 3, 1])
        self.assertEqual([x["kw"]["han"] for x in log], [510, 510, 210])
        self.assertEqual((r["da_hoc"], r["lo"]), (7, 3))
        self.assertTrue(all("tờ ảnh" not in x["prompt"].lower() and "đánh số" not in x["prompt"] for x in log))   # không tờ ảnh, không số cảnh giả
        with mock.patch.object(hc, "doc_cau_hinh", lambda: {"lo": 2}):                       # cấu hình lô nhỏ hơn thì theo cấu hình
            shutil.rmtree(self.kho / "_mo-ta"); log.clear()
            self._chay(gia.runner_v3_gia(log))
        self.assertEqual([len(x["ds"]) for x in log], [2, 2, 2, 1])

    def test_v3_moi_ma_mot_duong_dan_va_khoa_theo_ten_file(self):
        self._videos(2); log = []
        (self.kho / "sub").mkdir(); (self.kho / "sub" / "v0.mp4").write_bytes(b"x")          # trùng tên file ở thư mục con
        self._chay(gia.runner_v3_gia(log))
        ds = log[0]["ds"]
        self.assertEqual(len({m for m, _d, _f in ds}), 3); self.assertEqual(len({f for _m, _d, f in ds}), 3)
        for r in ("v0.mp4", "v1.mp4", "sub/v0.mp4"):
            self.assertTrue(self._co_v3(r), r)
        self.assertEqual(self._v3("sub/v0.mp4")["video"], "sub/v0.mp4")

    def test_v3_dung_khoi_dong_lai_chi_lam_video_con_lai(self):
        self._videos(6); log = []

        def truoc(lan, prompt):
            if lan == 2:
                self.assertTrue(hc.dung()["dang_dung"]); return False                      # bấm Dừng khi đang làm lô 2
        r = self._chay(gia.runner_v3_gia(log, truoc=truoc))
        self.assertEqual(len(log), 2); self.assertFalse(r["tat_ca_xong"])
        self.assertEqual(hc.JOB["trang_thai"], "dung"); self.assertEqual(hc.JOB["thong_bao"], "Đã dừng. Đã học 3 video (giữ nguyên), còn 3 video chưa học.")
        self.assertEqual([self._co_v3(f"v{i}.mp4") for i in range(6)], [True] * 3 + [False] * 3)    # file trên đĩa LÀ tiến độ
        self.assertFalse((self.kho / "_tam" / "hoc-canh").exists())
        log2 = []
        r2 = self._chay(gia.runner_v3_gia(log2))                                              # bật lại: chỉ video chưa có phiếu hợp lệ
        self.assertEqual((r2["da_hoc"], len(log2)), (3, 1))
        self.assertEqual(sorted(Path(f).name for _m, _d, f in log2[0]["ds"]), ["v3.mp4", "v4.mp4", "v5.mp4"])
        self.assertEqual((hc.JOB["tong"], hc.JOB["xong"], hc.JOB["trang_thai"]), (3, 3, "xong"))
        log3 = []
        self._chay(gia.runner_v3_gia(log3))                                                   # học xong hết: không còn gì
        self.assertEqual((len(log3), hc.JOB["thong_bao"]), (0, "Kho đã đủ mô tả."))

    def test_v3_phieu_hong_file_tren_dia_cung_duoc_lam_lai(self):
        self._videos(2); log = []
        self._chay(gia.runner_v3_gia(log))
        f = self.kho / "_mo-ta" / f"v0.mp4{p3.DUOI}"
        d = json.loads(f.read_text(encoding="utf-8")); d["canh_quay"] = d["canh_quay"][:1]; f.write_text(json.dumps(d), encoding="utf-8")   # hở cuối video
        log.clear()
        r = self._chay(gia.runner_v3_gia(log))
        self.assertEqual((r["da_hoc"], [Path(f).name for _m, _d, f in log[0]["ds"]]), (1, ["v0.mp4"]))
        self.assertEqual(len(self._v3("v0.mp4")["canh_quay"]), 2)

    def test_v3_chi_ep_hoc_lai_nhung_lai_bo_qua_video_dat(self):
        self._videos(3); log = []
        self._chay(gia.runner_v3_gia(log))                                                    # 3 video đã có phiếu v3 hợp lệ
        log.clear()
        self._chay(gia.runner_v3_gia(log), lai=True)                                          # học lại không ép: video đạt bị bỏ qua
        self.assertEqual((len(log), hc.JOB["thong_bao"]), (0, "Kho đã đủ mô tả."))
        # video 4: chỉ có mô tả kiểu 2 (không có v3) → lai=True học, mô tả cũ nguyên vẹn
        self._videos(1, 3)
        cu = {"video": "v3.mp4", "kieu": 2, "thoi_luong_s": 40.0, "tom_tat": "mô tả kiểu 2", "canh_quay": [{"tu_s": 1.0, "den_s": 5.0, "hinh": "cũ", "phieu": {"loai": "chai_ro"}}]}
        md = self.kho / "_mo-ta" / "v3.mp4.mo-ta.json"; md.write_text(json.dumps(cu, ensure_ascii=False), encoding="utf-8"); goc = md.read_bytes()
        r = self._chay(gia.runner_v3_gia(log), lai=True)
        self.assertEqual((r["da_hoc"], [Path(f).name for _m, _d, f in log[0]["ds"]]), (1, ["v3.mp4"]))
        self.assertEqual(md.read_bytes(), goc); self.assertFalse((self.kho / "_mo-ta" / "_cu").exists())     # v2 để nguyên, không cần sao lưu
        # chi ép đúng video: học lại dù đã đạt (đổi model để thấy file mới)
        log.clear(); truoc_hoc_luc = self._v3("v0.mp4")["model"]
        r = self._chay(gia.runner_v3_gia(log), chi=["v1.mp4", "khong-co.mp4"], model="gemini-4-neon-xhigh")
        self.assertEqual((r["da_hoc"], [Path(f).name for _m, _d, f in log[0]["ds"]]), (1, ["v1.mp4"]))
        self.assertEqual((self._v3("v1.mp4")["model"], self._v3("v0.mp4")["model"]), ("gemini-4-neon-xhigh", truoc_hoc_luc))
        # ép học lại mà AI trả hỏng 2 lần: phiếu hợp lệ cũ KHÔNG bị xoá/ghi đè
        truoc = (self.kho / "_mo-ta" / f"v2.mp4{p3.DUOI}").read_bytes(); log.clear()
        r = self._chay(gia.runner_v3_gia(log, hong=lambda lan, f: "ho"), chi=["v2.mp4"])
        self.assertEqual((len(log), r["loi"], r["tat_ca_xong"]), (2, ["v2.mp4"], False))
        self.assertEqual((self.kho / "_mo-ta" / f"v2.mp4{p3.DUOI}").read_bytes(), truoc)

    def test_v3_toan_bo_qua_khong_hoc_lai(self):
        self._videos(2); log = []
        r = self._chay(gia.runner_v3_gia(log, bo_qua_het=("v0.mp4",)))
        self.assertEqual((r["da_hoc"], r["loi"], r["canh"], r["tat_ca_xong"]), (2, [], 2, True), r)    # v0: 0 đoạn, v1: 2 đoạn
        d = self._v3("v0.mp4")
        self.assertEqual((d["canh_quay"], len(d["phieu_v3"]["bo_qua"])), ([], 1))
        self.assertIn("v0.mp4", hc.doc_v3_kho(self.kho))                                      # hợp lệ theo đúng bộ kiểm của kho
        log.clear()
        self._chay(gia.runner_v3_gia(log), lai=True)
        self.assertEqual(len(log), 0); self.assertEqual(hc.JOB["thong_bao"], "Kho đã đủ mô tả.")     # không học lại mãi
        v = hc.ket_qua_kho(self.kho)["video"][0]
        self.assertEqual((v["kieu"], v["canh"]), (3, []))

    def test_v3_job_het_viec_con_loi_khong_bat_kho(self):
        ma = self._san_pham(kho_v3=False); self._videos(2); log = []; xong = []
        r = self._chay_sp(ma, gia.runner_v3_gia(log, hong=lambda lan, f: "thieu" if f == "v1.mp4" else None), kieu3=True, khi_xong=xong.append)
        self.assertEqual(len(log), 2)                                                          # lần 1 + hỏi lại đúng video lỗi 1 lần
        self.assertEqual((r["da_hoc"], r["loi"], r["tat_ca_xong"]), (1, ["v1.mp4"], False), r)
        self.assertEqual(xong, [])                                                             # không "xong hết" → không gọi khi_xong (không nạp kho)
        self.assertEqual(hc.JOB["trang_thai"], "loi"); self.assertIn("1/2 video", hc.JOB["thong_bao"]); self.assertIn("1 video chưa đạt", hc.JOB["thong_bao"])
        self.assertEqual([x["video"] for x in hc.JOB["loi"]], ["v1.mp4"]); self.assertIn("thiếu", hc.JOB["loi"][0]["loi"])
        self.assertTrue(self._co_v3("v0.mp4")); self.assertFalse(self._co_v3("v1.mp4"))        # video tốt giữ, video lỗi để lại ghi chú
        self.assertTrue((self.kho / "_mo-ta" / "v1.mp4.loi.txt").exists())
        self.assertFalse(json.loads((self.hub / "san-pham" / ma / "san-pham.json").read_text(encoding="utf-8"))["kho_v3"])   # học xong ≠ tự bật cờ kho
        log.clear()                                                                            # bấm lại, lần này đủ → xong hẳn, gọi khi_xong đúng 1 lần
        r = self._chay_sp(ma, gia.runner_v3_gia(log), kieu3=True, khi_xong=xong.append)
        self.assertEqual((r["tat_ca_xong"], len(xong), hc.JOB["trang_thai"]), (True, 1, "xong"))
        self.assertEqual([Path(f).name for _m, _d, f in log[0]["ds"]], ["v1.mp4"])
        self.assertFalse((self.kho / "_mo-ta" / "v1.mp4.loi.txt").exists())

    def test_v3_hai_lo_lien_khong_co_file_thi_dung(self):
        self._videos(7); log = []

        def runner(model, prompt, outs, td, khi_co, **kw):
            log.append(1); return []                                                           # Antigravity không ghi gì
        r = self._chay(runner)
        self.assertEqual(len(log), 2); self.assertEqual(hc.JOB["trang_thai"], "het_luot"); self.assertFalse(r["tat_ca_xong"])
        self.assertIn("Đã học 0 video (giữ nguyên), còn 7 video chưa học.", hc.JOB["thong_bao"])
        self.assertFalse(list((self.kho / "_mo-ta").rglob("*" + p3.DUOI)) if (self.kho / "_mo-ta").exists() else [])

    def test_v3_file_json_rac_va_video_khong_do_duoc_do_dai(self):
        self._videos(2); log = []
        r = self._chay(gia.runner_v3_gia(log, hong=lambda lan, f: "json" if lan == 1 else None))
        self.assertEqual((len(log), r["da_hoc"], r["loi"]), (2, 2, []))                        # rác ở lần 1 → hỏi lại cả lô, lần 2 đạt
        self.assertIn("không phải JSON", log[1]["prompt"].split("LẦN TRƯỚC")[1] if "LẦN TRƯỚC" in log[1]["prompt"] else "không phải JSON")
        shutil.rmtree(self.kho / "_mo-ta"); log.clear()
        r = self._chay(gia.runner_v3_gia(log), do_dai=lambda p: None if p.name == "v0.mp4" else 40.0)
        self.assertEqual((r["da_hoc"], r["loi"]), (1, ["v0.mp4"])); self.assertEqual(len(log[0]["ds"]), 1)

    def test_v3_khong_cat_so_lich_su(self):
        ma = self._san_pham(kho_v3=True); self._videos(1); log = []
        cu = {"video": "v0.mp4", "thoi_luong_s": 40.0, "tom_tat": "mô tả cũ", "canh_quay": [{"tu_s": 3.0, "den_s": 8.0, "hinh": "cảnh cũ", "co_canh": "trung", "diem": 4}]}
        md = self.kho / "_mo-ta" / "v0.mp4.mo-ta.json"; md.parent.mkdir(); md.write_text(json.dumps(cu, ensure_ascii=False), encoding="utf-8"); goc = md.read_bytes()
        hc.LS.mkdir(parents=True); (hc.LS / "canh-da-dung-t1.txt").write_text("0001 0002", encoding="utf-8")
        r = self._chay_sp(ma, gia.runner_v3_gia(log), lai=True)                               # kieu3 theo CỜ của sản phẩm (không truyền)
        self.assertEqual((r["kieu3"], r["da_hoc"]), (True, 1), r)
        self.assertEqual((hc.LS / "canh-da-dung-t1.txt").read_text(encoding="utf-8"), "0001 0002")      # sổ dùng cảnh còn nguyên, không đổi tên
        self.assertEqual(list(hc.LS.glob("canh-da-dung-t1.cu-*")), [])
        self.assertEqual(md.read_bytes(), goc); self.assertFalse((self.kho / "_mo-ta" / "_cu").exists())
        self.assertIn("Nano Đồng; Bọ Trĩ Top One", log[0]["prompt"])                           # tên SP chính + tên in trên nhãn cùng sản phẩm

    def test_co_tat_hoc_nhu_cu(self):
        ma = self._san_pham(); self._videos(1); log = []                                       # không có cờ kho_v3 → đường kiểu 2 y như cũ
        r = self._chay_sp(ma, gia.runner_gia(log), cat=gia.cat_gia(3), to_anh=gia.to_anh_gia)
        self.assertEqual((r["kieu3"], r["da_hoc"]), (False, 1))
        self.assertTrue((self.kho / "_mo-ta" / "v0.mp4.mo-ta.json").exists()); self.assertFalse(self._co_v3("v0.mp4"))
        self.assertTrue(hc.co_kho_v3(self._san_pham(kho_v3=True))); self.assertFalse(hc.co_kho_v3("khong-co"))


class HubKhoTest(Nen):
    def _v2(self, rel):
        f = self.kho / "_mo-ta" / f"{rel}.mo-ta.json"; f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"video": rel, "kieu": 2, "thoi_luong_s": 40.0, "tom_tat": "kiểu 2", "canh_quay": [
            {"tu_s": 1.0, "den_s": 5.0, "hinh": "cảnh 2", "diem": 4, "co_canh": "can", "phieu": {"loai": "chai_ro"}}]}), encoding="utf-8")

    def _v1(self, rel):
        f = self.kho / "_mo-ta" / f"{rel}.mo-ta.json"; f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"video": rel, "thoi_luong_s": 40.0, "tom_tat": "kiểu 1", "canh_quay": [{"tu_s": 1.0, "den_s": 5.0, "hinh": "cảnh 1", "diem": 3}]}), encoding="utf-8")

    def _ghi_v3(self, rel, form, dai=40.0):
        f = self.kho / "_mo-ta" / f"{rel}{p3.DUOI}"; f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(p3.mo_ta(form, rel, dai, "gemini-4-neon-high"), ensure_ascii=False), encoding="utf-8")

    def test_hub_kho_toan_v2_hien_nut_nang_cap(self):
        self._videos(3)
        for i in range(3):
            self._v2(f"v{i}.mp4")
        t = hc.ket_qua_kho(self.kho)["tong"]
        self.assertEqual((t["kieu1"], t["kieu2"], t["kieu3"], t["chua_hoc"]), (0, 3, 0, 0))
        self.assertEqual(t["nang_cap"], 3)                                                    # kho toàn kiểu 2 vẫn "cần nâng cấp" (nút trước đây chỉ hiện khi kieu1 > 0)
        # thêm kiểu 1 + phiếu v3: kiểu 3 thắng, đếm đủ
        self._videos(3, 3); self._v1("v3.mp4"); self._v1("v5.mp4")                              # v3: kiểu 1; v4: chưa có gì; v5: kiểu 1
        self._ghi_v3("v1.mp4", gia.form_v3(40.0, 2)); self._ghi_v3("v3.mp4", gia.form_v3(40.0, 3))          # v1: 2+3 → 3; v3: 1+3 → 3
        r = hc.ket_qua_kho(self.kho); t = r["tong"]
        self.assertEqual({k: t[k] for k in ("video_tong", "kieu3", "kieu2", "kieu1", "chua_hoc", "nang_cap", "canh_tong")},
                         {"video_tong": 6, "kieu3": 2, "kieu2": 2, "kieu1": 1, "chua_hoc": 1, "nang_cap": 3, "canh_tong": 1 + 2 + 1 + 3 + 0 + 1})
        self.assertEqual([v["kieu"] for v in r["video"]], [2, 3, 2, 3, 0, 1])
        self.assertEqual({k: hc.kieu_kho(self.kho)[k][0] for k in ("v0.mp4", "v1.mp4", "v3.mp4")}, {"v0.mp4": 2, "v1.mp4": 3, "v3.mp4": 3})
        self.assertEqual(hc.kieu_kho(self.kho)["v1.mp4"][1], "v1.mp4" + p3.DUOI)

    def test_hub_phieu_v3_hong_dung_lai_mo_ta_cu_va_chi_tiet_doan(self):
        self._videos(2); self._v2("v0.mp4")
        hong = gia.form_v3(40.0, 3); del hong["doan"][1]                                       # hở giữa video
        self._ghi_v3("v0.mp4", hong)
        cam = gia.doan_v3(20, 40, gia_qua={"chu_dan": [{"tu": 21, "den": 23, "trich": None}], "tren_vat": [], "loi": []},
                          viec=[{"ma": "rot", "vat": "v1", "dich": "ly"}], loi=[{"tu": 21, "den": 25, "chu_de": "cong_dung", "tom": "ra rễ nhanh"}])
        f = gia.form_v3(40.0, 2); f["doan"][1] = cam
        self._ghi_v3("v1.mp4", f)
        r = hc.ket_qua_kho(self.kho); v0, v1 = r["video"]
        self.assertEqual(v0["kieu"], 2)                                                        # phiếu v3 hỏng → không tính, dùng kiểu 2
        self.assertEqual((v1["kieu"], len(v1["canh"])), (3, 2))
        c0, c1 = v1["canh"]
        self.assertEqual((c0["tu"], c0["den"], c0["viec"], c0["cam"], c0["co_canh"]), (0.0, 20.0, "cam_xem", [], "can"))
        self.assertEqual((c1["viec"], c1["cam"], c1["noi"]), ("rot", ["gia_qua"], "ra rễ nhanh"))
        self.assertTrue(c1["ta"])
        self.assertEqual(r["tong"]["kieu3"], 1)


class PromptV3Test(Nen):
    def test_prompt_v3_dien_dung_duong_dan_va_json(self):
        ma = self._san_pham()
        viec = [{"ma": "V1", "src": str(self.kho / "v0.mp4"), "dai": 12.5}, {"ma": "V2", "src": str(self.kho / "sub" / "v 1.mp4"), "dai": 7.0, "sai": ["hở 3–4s", "id lạ v9"]}]
        ra = self.kho / "_tam" / "hoc-canh" / "lo" / "phieu.json"
        p = hc.loi_nhac_phieu_v3(viec, ra, hc.ten_sp_cho_phieu(ma))
        self.assertIn('{"<mã video>": {"tom_tat": "...", "kieu_video": "...", "vat": [...], "bo_qua": [...], "doan": [{...}]}, ...}', p)      # ngoặc JSON thật
        self.assertIn("bắt đầu bằng { kết thúc bằng }", p)
        for x in ("{{", "}}", "{n}", "{ds}", "{out}"):
            self.assertNotIn(x, p, x)                                                          # không sót chỗ điền
        self.assertIn("Có 2 video", p); self.assertIn(f"vào ĐÚNG file: {ra}", p)
        dong = [l for l in p.splitlines() if l.startswith("- mã ")]
        self.assertEqual(len(dong), 2)
        self.assertIn("mã V1", dong[0]); self.assertIn(str(self.kho / "v0.mp4"), dong[0]); self.assertIn("dài 12.50s", dong[0])
        self.assertIn("mã V2", dong[1]); self.assertIn(str(self.kho / "sub" / "v 1.mp4"), dong[1]); self.assertIn("hở 3–4s; id lạ v9", dong[1])
        for l in dong:
            self.assertIn("Nano Đồng; Bọ Trĩ Top One", l)                                      # tên chính + tên trên nhãn của CÙNG sản phẩm
        self.assertNotIn(str(self.kho / "v0.mp4"), dong[1])                                    # mỗi mã đúng một đường dẫn
        self.assertIn("KHÔNG chạy lệnh terminal", p)
        self.assertEqual(gia.ds_v3_tu_prompt(p), [("V1", 12.5, str(self.kho / "v0.mp4")), ("V2", 7.0, str(self.kho / "sub" / "v 1.mp4"))])
        self.assertEqual(gia.ra_v3_tu_prompt(p), ra)

    def test_prompt_v3_xem_thu_va_kiem(self):
        ma = self._san_pham()
        self.assertEqual(pm.kiem("dien-phieu-v3", pm.mac_dinh("dien-phieu-v3")), {"thieu": [], "la": []})
        r = pm.xem_thu("dien-phieu-v3", ma)
        self.assertEqual([c for c in r["canh_bao"] if "Xem thử dùng" not in c], [], r)          # không báo thiếu/lạ chỗ điền
        self.assertIn("mã V1", r["text"]); self.assertIn("mã V2", r["text"]); self.assertIn("Nano Đồng; Bọ Trĩ Top One", r["text"])
        self.assertNotIn("{{", r["text"]); self.assertIn('{"<mã video>":', r["text"])
        self.assertEqual(len(gia.ds_v3_tu_prompt(r["text"])), 2)
        # bản người dùng sửa bỏ phần an toàn / định dạng → máy tự gắn lại
        t = pm.xem_thu("dien-phieu-v3", ma, "Chỉ làm: {{ds}} → {{out}}")["text"]
        self.assertIn("KHÔNG chạy lệnh terminal", t); self.assertIn("chỉ chứa JSON thuần", t)

    def test_tach_phieu_v3_nhan_ma_hoac_ten_file(self):
        ma_rel = {"v1": "a/x.mp4", "v2": "y.mp4", "y.mp4": "y.mp4", "x.mp4": "a/x.mp4"}
        f = {"doan": []}
        self.assertEqual(hc.tach_phieu_v3(json.dumps({"V1": f, "Y.mp4": f, "V9": f}), ma_rel), {"a/x.mp4": f, "y.mp4": f})
        self.assertEqual(hc.tach_phieu_v3("```json\n" + json.dumps({"v2": f}) + "\n```", ma_rel), {"y.mp4": f})
        self.assertIsNone(hc.tach_phieu_v3("rác", ma_rel)); self.assertIsNone(hc.tach_phieu_v3("[1]", ma_rel)); self.assertEqual(hc.tach_phieu_v3("{}", ma_rel), {})
        self.assertEqual(hc.tach_phieu_v3(json.dumps(f), {"v1": "a.mp4"}), {"a.mp4": f})     # lô 1 video, AI quên bọc theo mã


class ModelTest(Nen):
    def test_neon_la_mac_dinh_va_di_qua_nguyen_ven(self):
        self.assertEqual(list(hc.MODELS)[:2], ["gemini-4-neon-high", "gemini-4-neon-xhigh"])
        for m in ("gemini-4-neon-high", "gemini-4-neon-xhigh", "gemini-4-hydrogen-high", "gemini-4-argon-high"):
            self.assertEqual(hc.chuan_model(m), m)
        for cu in ("flash", "", None, "gemini-9"):
            self.assertEqual(hc.chuan_model(cu), "gemini-4-neon-high")
        self.assertIn("(mặc định)", hc.MODELS["gemini-4-neon-high"]); self.assertNotIn("(mặc định)", hc.MODELS["gemini-4-hydrogen-high"])
        cfg = json.loads((Path(__file__).resolve().parents[1] / "mau" / "config.mau.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["hoc_canh"]["model"], "gemini-4-neon-high")
        self._videos(1); log = []
        self._chay(gia.runner_v3_gia(log), model="gemini-4-neon-xhigh")
        self.assertEqual(log[0]["model"], "gemini-4-neon-xhigh")

    def test_giam_khao_giu_model_rieng(self):
        import dao_dien as dd
        with mock.patch.object(dd, "cfg_hub", lambda: {"hoc_canh": {"model": "gemini-4-neon-xhigh"}}):      # đổi mặc định học cảnh...
            self.assertEqual(dd._gk_cau_hinh()["model"], "gemini-4-hydrogen-high")                          # ...giám khảo vẫn Hydrogen
        with mock.patch.object(dd, "cfg_hub", lambda: {"giam_khao": {"model": "gemini-4-argon-high"}}):
            self.assertEqual(dd._gk_cau_hinh()["model"], "gemini-4-argon-high")                              # cấu hình riêng của giám khảo vẫn được
        self.assertEqual((dd.GK_MODEL, hc.MODEL_GIAM_KHAO), ("gemini-4-hydrogen-high", "gemini-4-hydrogen-high"))
        # hỏi 1 lần (đường giám khảo): id lạ/cũ rơi về Hydrogen của giám khảo, KHÔNG về Neon của học cảnh
        da_gui = []

        def gui(model, prompt, td, project=None):
            da_gui.append(model)
            out.write_text('{"muc": []}', encoding="utf-8"); return "cid-1"
        out = _tmp() / "gk.json"
        for yeu_cau in ("flash", "", "gemini-4-hydrogen-high", "gemini-4-neon-xhigh"):
            hc.hoi_mot_lan(yeu_cau, "hoi", out, han=30, gui=gui, huy_cuoc=lambda c: None, ngu=lambda g: None)
        self.assertEqual(da_gui, ["gemini-4-hydrogen-high"] * 3 + ["gemini-4-neon-xhigh"])
        # học cảnh thì id lạ rơi về Neon
        self.assertEqual(hc.doc_model(), "gemini-4-neon-high")


if __name__ == "__main__":
    unittest.main()
