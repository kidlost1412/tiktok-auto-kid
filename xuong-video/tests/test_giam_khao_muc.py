"""Giám khảo theo DANH SÁCH KIỂM: điểm = 10 × đạt / xét, máy kiểm trước (kiem_may), tách bài học (đạo diễn) khỏi lỗi máy (loi-may.jsonl),
chấm bằng Gemini qua Antigravity (runner giả) và rơi về Claude (goi giả). KHÔNG gọi Antigravity/Claude thật."""
import json, os, re, sys, tempfile, threading, unittest
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp(prefix="xv-gk-")
os.environ.setdefault("XUONG_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import kiem_may as km  # noqa: E402
import dao_dien as dd  # noqa: E402
import ekip  # noqa: E402
import hoc_canh as hc  # noqa: E402
import prompt_mau  # noqa: E402
from PIL import Image  # noqa: E402


def shot(i, vai=(), mat=0, nhan=None, file=None):
    return {"id": i, "file": file or f"{i}.mp4", "vai_tro": list(vai), "soat": {"mat": mat, "nhan": nhan, "dep": 4}}


def seg(sh, dur=3.0, bo_cuc="khung_mo", cau=0, src=0.0, phu=()):
    return {"shot": sh, "dur": dur, "bo_cuc": bo_cuc, "cau": cau, "src_start": src, "phu_shots": list(phu)}


def muc_ai(dat=True, **ghi_de):
    """Danh sách mục AI trả lời: mọi mục đạt, ghi_de {id: (dat, ly_do, giay)}."""
    out = []
    for k in km.TEN_MUC:
        d, ly, g = ghi_de.get(k, (dat, "", None))
        out.append({"id": k, "dat": d, "ly_do": ly, "giay": g})
    return {"muc": out, "loi": [], "sua": ""}


class DiemTest(unittest.TestCase):
    def test_cong_thuc_diem(self):
        self.assertEqual(km.tinh_diem([{"id": str(i), "dat": i < 7} for i in range(10)])[0], 7.0)
        self.assertEqual(km.tinh_diem([{"dat": True}, {"dat": False}, {"dat": None}])[0], 5.0)       # None = không áp dụng, bỏ khỏi mẫu số
        n = len(km.MUC)
        self.assertEqual(km.tinh_diem([{"dat": i < 9} for i in range(n)])[0], round(10 * 9 / n, 1))
        self.assertIsNone(km.tinh_diem([{"dat": None}])[0])

    def test_hop_nhat_diem_dat_va_loi(self):
        r = km.hop_nhat(muc_ai(), [])
        self.assertEqual((r["diem"], r["dat"], r["loi"]), (10.0, True, []))
        r = km.hop_nhat(muc_ai(hook=(False, "mở đầu nhạt", 0.5), hinh_hop_loi=(False, "lệch lời", 6.0), nhan_ro=(False, "nhãn mờ", None),
                               khong_lap=(False, "lặp", 2.0)), [])
        n = len(km.AI_HOI) + len(km.CHI_MAY)                         # 3 mục cảm tính đã bỏ (Kid 23/11)
        self.assertEqual(r["diem"], round(10 * (n - 4) / n, 1))
        self.assertFalse(r["dat"])                                    # móc câu là mục nặng: trượt thì không đạt dù điểm ≥ 7
        self.assertEqual(len(r["loi"]), 3); self.assertTrue(r["loi"][0].startswith("0.5s móc câu"))
        r2 = km.hop_nhat(muc_ai(khong_lap=(False, "lặp", 2.0)), [])
        self.assertTrue(r2["dat"]) ; self.assertGreaterEqual(r2["diem"], 7)

    def test_may_bat_truot_thi_tinh_truot_va_ai_khong_can_tra(self):
        may = [{"muc": "khong_che_nhan", "nguoi_sua": "may", "giay": 3.0, "chi_tiet": "phụ đề đè nhãn lúc 3s", "sua": ""}]
        ai = muc_ai(); ai["muc"] = [m for m in ai["muc"] if m["id"] != "khong_che_nhan"]               # AI bỏ qua đúng mục máy đã bắt
        r = km.hop_nhat(ai, may)
        n = len(km.AI_HOI) + len(km.CHI_MAY)
        self.assertEqual(r["diem"], round(10 * (n - 1) / n, 1))
        m = [x for x in r["muc"] if x["id"] == "khong_che_nhan"][0]
        self.assertEqual((m["dat"], m["nguon"], m["nguoi_sua"]), (False, "may", "may"))
        self.assertTrue(r["loi"][0].startswith("[máy] "))

    def test_ai_tra_thieu_hoac_hong(self):
        self.assertIsNone(km.hop_nhat({"muc": [{"id": "hook", "dat": True}]}, []))
        self.assertIsNone(km.hop_nhat({}, []))
        cu = km.hop_nhat_cu({"diem": 9, "dat": True, "loi": ["x" * 20], "sua": ""}, [{"muc": "khong_che_nhan", "chi_tiet": "đè nhãn"}])
        self.assertLessEqual(cu["diem"], 9); self.assertLess(cu["diem"], 10)

    def test_duyet_van_dung_khoa_diem(self):
        r = km.hop_nhat(muc_ai(), [])
        for k in ("diem", "dat", "loi", "sua"):
            self.assertIn(k, r)
        self.assertIsInstance(r["diem"], float)


class MayKiemTest(unittest.TestCase):
    CHAI = dict(vai=("chai_ro",), nhan=[0.3, 0.30, 0.7, 0.45])

    def sents(self, cuoi="Bấm giỏ hàng nhé"):
        return [{"s": 0, "e": 3, "text": "Mở đầu"}, {"s": 3, "e": 6, "text": cuoi}]

    def muc(self, kq):
        return {f["muc"] for f in kq}

    def test_nguoi_that_full_man_khong_con_la_loi(self):          # Kid 15/11: người thật cầm/nói về sản phẩm là điểm cộng, lệch khẩu hình không sao
        segs = [seg(shot("A", mat=2), bo_cuc="day", cau=0), seg(shot("B", **self.CHAI), cau=1)]
        self.assertNotIn("nguoi_noi", self.muc(km.kiem(segs, self.sents(), co_qua=False)))

    def test_khung_tron_la_loi_dao_dien(self):                    # ≥ 2 đoạn toàn màn trơn (không ô chèn, không chữ lớn) → trượt; 1 đoạn = nhịp thở
        segs = [seg(shot("A"), bo_cuc="day", cau=0), seg(shot("B", **self.CHAI), cau=1)]
        kq = km.kiem(segs, self.sents(), info={"khung_tron": [[0.0, 2.0], [4.0, 6.0]]}, co_qua=False)
        f = [x for x in kq if x["muc"] == "da_dang_bo_cuc"][0]
        self.assertEqual(f["nguoi_sua"], "dao_dien")
        self.assertNotIn("da_dang_bo_cuc", self.muc(km.kiem(segs, self.sents(), info={"khung_tron": [[0.0, 2.0]]}, co_qua=False)))

    def test_phu_de_de_nhan(self):
        # nhãn thấp (y ≈ 1344–1536 trên khung 1920) nằm trong dải phụ đề 1415–1565 → trượt, lỗi máy
        thap = seg(shot("A", vai=("chai_ro",), nhan=[0.3, 0.70, 0.7, 0.80]), bo_cuc="day", cau=1)
        kq = km.kiem([thap], self.sents(), co_qua=False)
        f = [x for x in kq if x["muc"] == "khong_che_nhan"]
        self.assertTrue(f and f[0]["nguoi_sua"] == "may" and "phụ đề" in f[0]["chi_tiet"])
        cao = seg(shot("A", vai=("chai_ro",), nhan=[0.3, 0.30, 0.7, 0.45]), bo_cuc="day", cau=1)
        self.assertNotIn("khong_che_nhan", self.muc(km.kiem([cao], self.sents(), co_qua=False)))
        # toạ độ TỪNG DÒNG phụ đề (mã dựng ghi y) được ưu tiên: dòng ở y=300 thì nhãn thấp không bị đè
        props = {"cap": {"center_y": 1490}, "lines": [{"text": "a", "f0": 0, "f1": 200, "y": 300}]}
        self.assertNotIn("khong_che_nhan", self.muc(km.kiem([thap], self.sents(), props=props, co_qua=False)))

    def test_khoi_chu_de_nhan(self):
        sg = seg(shot("A", vai=("chai_ro",), nhan=[0.25, 0.14, 0.75, 0.26]), bo_cuc="day", cau=1)
        props = {"blocks": [{"loai": "checklist", "f0": 0, "f1": 120}]}                                   # top mặc định 250, cao 380
        f = [x for x in km.kiem([sg], self.sents(), props=props, co_qua=False) if x["muc"] == "khong_che_nhan"]
        self.assertTrue(f and "khối chữ" in f[0]["chi_tiet"] and f[0]["nguoi_sua"] == "may")
        props["blocks"][0]["top"] = 1000                                                                 # đã dời ra xa nhãn
        self.assertFalse([x for x in km.kiem([sg], self.sents(), props=props, co_qua=False) if "khối chữ" in x["chi_tiet"]])

    def test_thieu_qua_o_cau_chot(self):
        segs = [seg(shot("A"), cau=0), seg(shot("B", **self.CHAI), cau=1)]
        s = self.sents("Mua hôm nay được tặng kèm quà")
        f = [x for x in km.kiem(segs, s, co_qua=True, co_canh_qua=True) if x["muc"] == "chot_qua"]
        self.assertEqual(f[0]["nguoi_sua"], "dao_dien")                    # kho có cảnh quà mà đạo diễn không chọn
        f = [x for x in km.kiem(segs, s, co_qua=True, co_canh_qua=False) if x["muc"] == "chot_qua"]
        self.assertEqual(f[0]["nguoi_sua"], "may")                         # kho không có cảnh quà = lỗi dữ liệu
        segs[1]["phu_shots"] = [shot("Q-X-1")]
        self.assertNotIn("chot_qua", self.muc(km.kiem(segs, s, co_qua=True, co_canh_qua=True)))
        self.assertNotIn("chot_qua", self.muc(km.kiem(segs, self.sents("Bấm giỏ hàng, quá rẻ"), co_qua=True)))     # "quá" ≠ "quà"

    def test_lap_canh_va_dung_yen(self):
        a = shot("A", **self.CHAI)
        segs = [seg(a, cau=0), seg(shot("B"), cau=0), seg(a, cau=1)]
        f = [x for x in km.kiem(segs, self.sents(), co_qua=False) if x["muc"] == "khong_lap"]
        self.assertTrue(f and f[0]["nguoi_sua"] == "dao_dien")
        tinh = [seg(shot("A"), dur=6.5, cau=0), seg(shot("B", **self.CHAI), dur=2, cau=1)]
        f = [x for x in km.kiem(tinh, self.sents(), co_qua=False) if x["muc"] == "khong_lap"]
        self.assertTrue(f and "đứng yên" in f[0]["chi_tiet"])
        ok = [seg(shot("A"), dur=3, cau=0), seg(shot("B", **self.CHAI), dur=3, cau=1)]
        self.assertNotIn("khong_lap", self.muc(km.kiem(ok, self.sents(), co_qua=False)))

    def test_chot_khong_co_chai(self):
        segs = [seg(shot("A", **self.CHAI), cau=0), seg(shot("B"), cau=1)]
        self.assertIn("chot_chai", self.muc(km.kiem(segs, self.sents(), co_qua=False)))


class TachBaiHocTest(unittest.TestCase):
    def setUp(self):
        self.hub = Path(tempfile.mkdtemp(prefix="hub-", dir=TMP))
        for mod in (ekip, dd):
            p = mock.patch.object(mod, "HUB", self.hub); p.start(); self.addCleanup(p.stop)

    def ket_qua(self):
        may = [{"muc": "khong_che_nhan", "nguoi_sua": "may", "giay": 3.1, "chi_tiet": "phụ đề đè nhãn chai lúc 3.1s", "sua": ""},
               {"muc": "nguoi_noi", "nguoi_sua": "dao_dien", "giay": 0.0, "chi_tiet": "người đang nói full màn lúc 0s", "sua": "đặt người nói vào khung, không toàn màn"}]
        ai = muc_ai(hook=(False, "mở đầu chỉ là tên sản phẩm", 0.5), hinh_sach=(False, "lớp màu phủ hồng", 4.0), chot_qua=(False, "chốt thiếu gói quà", 8.0))
        ai["muc"] = [m for m in ai["muc"] if m["id"] not in ("khong_che_nhan", "nguoi_noi")]
        return km.hop_nhat(ai, may, co_canh_qua=False)

    def test_loi_may_khong_vao_bai_hoc(self):
        r = self.ket_qua()
        n_hoc, n_may = ekip.ghi_ket_qua_giam_khao([("v1-0", r)], "sp1", False, lambda *_: None)
        hoc = (self.hub / "lich-su" / "bai-hoc-sp1.txt").read_text(encoding="utf-8")
        self.assertIn("móc câu", hoc); self.assertIn("người nói", hoc)               # lỗi đạo diễn sửa được (kể cả do máy đo) thành bài học
        for tu in ("nhãn", "phụ đề", "lớp màu", "quà"):                              # lỗi máy / dữ liệu thì KHÔNG
            self.assertNotIn(tu, hoc)
        dong = [json.loads(l) for l in (self.hub / "lich-su" / "loi-may.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual({x["muc"] for x in dong}, {"khong_che_nhan", "chot_qua"})        # "hình sạch" AI không còn chấm (Kid 23/11)
        for x in dong:
            self.assertEqual(set(x) , {"luc", "san_pham", "video", "muc", "nguon", "giay", "chi_tiet"})
            self.assertEqual((x["san_pham"], x["video"]), ("sp1", "v1-0"))
        self.assertEqual(n_may, 2)
        # đạo diễn chỉ đọc bài học, không bao giờ đọc loi-may
        self.assertNotIn("đè nhãn", dd.bai_hoc_cho("sp1"))

    def test_bai_hoc_gop_tuong_tu(self):
        r = self.ket_qua()
        ekip.ghi_ket_qua_giam_khao([("v1-0", r)], "sp1", False, lambda *_: None)
        ekip.ghi_ket_qua_giam_khao([("v2-0", r)], "sp1", False, lambda *_: None)              # chấm lại y hệt: không thêm dòng nào
        d1 = (self.hub / "lich-su" / "bai-hoc-sp1.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(d1), len(set(d1)))
        self.assertEqual(len(d1), 2)
        moi = ekip.ghi_bai_hoc(["- móc câu: mở đầu chỉ là tên sản phẩm thôi"], "sp1")         # na ná dòng đã có → bỏ
        self.assertEqual(moi, [])
        self.assertEqual(len(km.gop_tuong_tu(["- chữ mở đầu nhạt", "- chữ mở đầu nhạt quá nên người xem lướt", "- cảnh chốt thiếu chai"])), 2)

    def test_bai_hoc_cu_ve_loi_may_bi_loc_khi_gui_dao_dien(self):
        f = self.hub / "lich-su" / "bai-hoc-sp1.txt"; f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("- Tránh phụ đề đè lên nhãn chai\n- Luôn để hình khớp lời nói\n- Luôn để hình khớp lời nói nhé\n", encoding="utf-8")
        out = dd.bai_hoc_cho("sp1")
        self.assertNotIn("phụ đề", out); self.assertEqual(out.count("khớp lời"), 1)

    def test_loi_cu_khong_co_muc(self):
        hoc, may = km.tach_bai_hoc({"loi": ["3s phụ đề đè nhãn chai", "5s cảnh lặp liền kề nhau"], "muc": []})
        self.assertEqual(hoc, ["- 5s cảnh lặp liền kề nhau"]); self.assertEqual(may, [])


def gia_runner(noi_dung, log=None):
    """Giống hoc_canh.hoi_mot_lan: ghi JSON vào file kết quả nêu trong lời nhắc rồi trả nội dung."""
    def runner(model, prompt, out_file, han=120, **kw):
        if log is not None:
            log.append({"model": model, "prompt": prompt, "out": out_file, "han": han, "kw": kw})
        Path(out_file).write_text(json.dumps(noi_dung(prompt), ensure_ascii=False), encoding="utf-8")
        return Path(out_file).read_text(encoding="utf-8")
    return runner


class ChamBangAiTest(unittest.TestCase):
    SP = {"ten_goi": "Đạm cá", "ten_ngan": "Đạm cá", "qua_tang": ["gói quà"]}
    SENTS = [{"s": 0.0, "e": 3.0, "text": "Mở đầu"}, {"s": 3.0, "e": 6.0, "text": "Bấm giỏ hàng ngay"}]

    def setUp(self):
        self.hub = Path(tempfile.mkdtemp(prefix="hub-", dir=TMP)); self.work = Path(tempfile.mkdtemp(prefix="work-", dir=TMP))
        self.cfg = {"giam_khao": {"may": "gemini", "model": "gemini-4-hydrogen-high"}}
        for ten, v in (("HUB", self.hub),):
            p = mock.patch.object(dd, ten, v); p.start(); self.addCleanup(p.stop)
        p = mock.patch.object(dd, "cfg_hub", lambda: self.cfg); p.start(); self.addCleanup(p.stop)
        p = mock.patch.object(dd, "to_ban_dung", self.anh_gia); p.start(); self.addCleanup(p.stop)
        self.claude = []
        p = mock.patch.object(dd, "goi", self.goi_gia); p.start(); self.addCleanup(p.stop)
        dd._GK_DA_BAO.clear()
        self.txt_claude = json.dumps(muc_ai(hook=(False, "chữ mở nhạt", 0.5)), ensure_ascii=False)

    @staticmethod
    def anh_gia(video, sents, out, blocks=None):
        Image.new("RGB", (60, 60), "gray").save(out)
        return out, []

    def goi_gia(self, vai, prompt, anh=None, **kw):
        self.claude.append(prompt)
        return self.txt_claude, {}

    def segs(self):
        return [seg(shot("A", mat=2), bo_cuc="day", cau=0), seg(shot("B", vai=("vuon",)), cau=1)]      # chốt không có chai → máy bắt

    def cham(self, **kw):
        return dd.giam_khao(self.SP, "x.mp4", self.SENTS, {"cong_thuc": "c", "gu": "g", "khoi": []}, self.work, segs=self.segs(), **kw)

    def test_gemini_qua_runner_gia(self):
        log = []
        ai = lambda prompt: muc_ai(hook=(False, "mở nhạt", 0.5))
        kq = self.cham(runner=gia_runner(ai, log))
        self.assertEqual(kq["nguon"], "gemini"); self.assertEqual(self.claude, [])                # không tốn Claude
        self.assertEqual(log[0]["model"], "gemini-4-hydrogen-high"); self.assertEqual(log[0]["han"], 120)
        # prompt có đường dẫn ảnh + file kết quả; ảnh/kết quả tạm đã xoá
        out = Path(log[0]["out"]); m = re.search(r"file này \(mở và xem ảnh\): (.+)", log[0]["prompt"])
        self.assertTrue(m and Path(m.group(1).strip()).is_absolute())
        self.assertFalse(out.exists()); self.assertFalse(Path(m.group(1).strip()).exists())
        # máy bắt chốt không có chai → mục đó đã trượt + prompt dặn AI bỏ qua; móc câu AI trượt → 2 mục trượt
        self.assertIn("MÁY ĐÃ KIỂM", log[0]["prompt"])
        truot = {x["id"] for x in kq["muc"] if x["dat"] is False}
        self.assertEqual(truot, {"chot_chai", "hook"})
        n = len(km.AI_HOI) + len(km.CHI_MAY)
        self.assertEqual(kq["diem"], round(10 * (n - 2) / n, 1)); self.assertFalse(kq["dat"])
        self.assertTrue(kq["may"] and kq["may"][0]["muc"] == "chot_chai")

    def test_antigravity_dong_thi_tu_mo_khong_dung_claude(self):
        trang = {"mo": False}
        def mo():
            trang["mo"] = True
            return {"ok": True}
        log = []
        with mock.patch.object(hc, "trang_thai_agy", lambda: dict(trang)), mock.patch.object(hc, "mo_antigravity", mo), mock.patch("time.sleep"):
            self.assertTrue(dd._gk_mo_agy(hc))
        self.assertTrue(trang["mo"])
        kq = self.cham(runner=gia_runner(lambda p: muc_ai(), log))
        self.assertEqual(kq["nguon"], "gemini"); self.assertEqual(self.claude, [])

    def test_mo_khong_duoc_thi_chua_cham(self):
        with mock.patch.object(hc, "trang_thai_agy", lambda: {"mo": False, "vo": False}), mock.patch.object(hc, "_msg_chua_mo", lambda: "chưa mở"),                 mock.patch.object(hc, "mo_antigravity", lambda: {"ok": False}):
            kq = self.cham()
        self.assertIsNone(kq["diem"]); self.assertEqual(self.claude, [])                           # Kid 25/11: không rơi sang Claude

    def test_loi_hoac_het_gio_thu_lai_roi_chua_cham(self):
        n = []
        def hong(model, prompt, out_file, **kw):
            n.append(1)
            raise hc.LoiTam("Antigravity không trả kết quả trong 120 giây.")
        kq = self.cham(runner=hong)
        self.assertIsNone(kq["diem"]); self.assertEqual(len(n), 2); self.assertEqual(self.claude, [])

    def test_lan_hai_cham_duoc(self):
        n = []
        def runner(model, prompt, out_file, **kw):
            n.append(1)
            if len(n) == 1:
                raise hc.LoiTam("quá hạn")
            return json.dumps(muc_ai(), ensure_ascii=False)
        kq = self.cham(runner=runner)
        self.assertEqual(kq["nguon"], "gemini"); self.assertIsNotNone(kq["diem"])

    def test_gemini_tra_sai_dinh_dang_chua_cham(self):
        kq = self.cham(runner=gia_runner(lambda p: {"muc": [{"id": "hook", "dat": True}]}))
        self.assertIsNone(kq["diem"]); self.assertEqual(self.claude, [])

    def test_cau_hinh_claude_van_cham_antigravity(self):
        self.cfg["giam_khao"]["may"] = "claude"
        kq = self.cham(runner=gia_runner(lambda p: muc_ai()))
        self.assertEqual(kq["nguon"], "gemini"); self.assertEqual(self.claude, [])

    def test_ca_hai_deu_hong_de_trong_diem(self):
        self.txt_claude = "không phải json"
        kq = self.cham(runner=gia_runner(lambda p: {"x": 1}))
        self.assertIsNone(kq["diem"])

    def test_song_song_toi_da(self):
        self.cfg["giam_khao"]["song_song"] = 2
        dang, cao, lk = [0], [0], threading.Lock()

        def runner(model, prompt, out_file, **kw):
            with lk:
                dang[0] += 1; cao[0] = max(cao[0], dang[0])
            import time; time.sleep(0.05)
            with lk:
                dang[0] -= 1
            Path(out_file).write_text(json.dumps(muc_ai()), encoding="utf-8")
            return Path(out_file).read_text(encoding="utf-8")
        ts = [threading.Thread(target=lambda: self.cham(runner=runner)) for _ in range(6)]
        [t.start() for t in ts]; [t.join(20) for t in ts]
        self.assertLessEqual(cao[0], 2); self.assertGreaterEqual(cao[0], 1)

    def test_prompt_co_danh_sach_kiem(self):
        ctx = dd.ctx_giam_khao(self.SP, self.SENTS, {"khoi": []}, [{"muc": "hook"}])
        p = prompt_mau.dien("giam-khao", **ctx)
        for k in km.AI_HOI:
            self.assertIn(f'"{k}"', p)
        for k in km.CHI_MAY | {"nguoi_noi", "hinh_sach", "khoang_tho"}:          # máy tự đo / đã bỏ → không hỏi AI
            self.assertNotIn(f'"{k}"', p)
        self.assertEqual(p.count("MÁY ĐÃ KIỂM: TRƯỢT"), 1 + (1 if "MÁY ĐÃ KIỂM: TRƯỢT" in prompt_mau.doc("giam-khao")[0] else 0))


class HoiMotLanTest(unittest.TestCase):
    def test_nhan_ket_qua_huy_cuoc_va_don_file(self):
        out = Path(tempfile.mkdtemp(prefix="hml-", dir=TMP)) / "kq.json"
        da_huy, da_gui = [], []

        def gui(model, prompt, tieu_de):
            da_gui.append((model, tieu_de)); return "cid-1"

        def ngu(giay):
            out.write_text('{"a": 1}', encoding="utf-8")
        txt = hc.hoi_mot_lan("gemini-4-hydrogen-high", "hoi", out, han=30, gui=gui, huy_cuoc=da_huy.append, ngu=ngu)
        self.assertEqual(json.loads(txt), {"a": 1}); self.assertEqual(da_huy, ["cid-1"]); self.assertFalse(out.exists())
        self.assertEqual(da_gui[0][0], "gemini-4-hydrogen-high")

    def test_het_gio_van_huy_cuoc(self):
        out = Path(tempfile.mkdtemp(prefix="hml-", dir=TMP)) / "kq.json"
        da_huy = []
        with self.assertRaises(hc.LoiTam):
            hc.hoi_mot_lan("m", "hoi", out, han=7, gui=lambda *a: "cid-2", huy_cuoc=da_huy.append, ngu=lambda g: None)
        self.assertEqual(da_huy, ["cid-2"])

    def test_chua_mo_antigravity_va_khong_dung_job_hoc_canh(self):
        out = Path(tempfile.mkdtemp(prefix="hml-", dir=TMP)) / "kq.json"

        def gui(*a):
            raise hc.ChuaMo("chưa mở")
        luu = mock.Mock()
        with mock.patch.object(hc, "_luu", luu):
            with self.assertRaises(hc.ChuaMo):
                hc.hoi_mot_lan("m", "hoi", out, han=7, gui=gui, huy_cuoc=lambda c: None, ngu=lambda g: None)
        luu.assert_not_called()                                    # không ghi hoc-canh-job.json của hub


if __name__ == "__main__":
    unittest.main()
