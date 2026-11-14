"""Bộ biên kịch mới: 4 trục xoay vòng (mo/than/chot/vai), đề bài mới, khối giọng thật / kho cảnh / số liệu TikTok, luật kiểm, vòng gọi lại. KHÔNG gọi AI.
Chạy:  python -m unittest discover -s xuong-video/tests -v"""
import json, os, random, shutil, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
ENG = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENG))
import prompt_mau as pm  # noqa: E402
import viet_loi as vl  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def sp_mau(kho, **them):
    sp = {"ma": "sp-thu", "ten_goi": "Phân thử nghiệm Alpha", "ten_ngan": "Alpha Gold", "kho_video": str(kho),
          "su_that_duoc_noi": ["Một chai pha 200 lít nước."], "qua_tang": ["Mua 3 tặng 1"], "luat_rieng": ["Không nói giá."],
          "cat_khung_ly_do": "bỏ", "thoi_luong": [20, 25],
          "goc_ban": [{"ma": "rua-vuon", "mo_ta": "Rửa vườn sau thu hoạch (cà phê): đúng lúc, đúng việc."},
                      {"ma": "cach-dung", "mo_ta": "Cách dùng nhanh."}, {"ma": "qua-tang", "mo_ta": "Quà tặng."}]}
    sp.update(them)
    return sp


def kich_ban(i, sp, ten="Alpha Gold", gh="Bấm giỏ hàng nhé.", u=False, **them):
    """Một kịch bản hợp lệ (đủ âm tiết, ≥ 3 tag, tên ở câu 2, giỏ hàng một lần); i làm các câu khác nhau giữa các bản."""
    nho, lon = vl.khung_am_tiet(sp)[2:4]
    muc = (nho + lon) // 2
    c1, c2, c4, c5 = f"[curious] Vườn thứ {i} khựng lại.", f"[concerned] {ten} vào đúng lúc.", "[warm] Ngắn thôi.", f"[confident] {gh}"
    if u:                     # mọi câu khác nhau giữa các bản (máy chống lặp câu nguyên văn)
        c2, c4, c5 = c2[:-1] + f" lần {i}.", f"[warm] Ngắn thôi {i}.", c5[:-1] + f" {i}."
    dem = lambda *cs: sum(len(vl.re.findall(r"\w+", vl.re.sub(r"\[[^\]]*\]", "", c))) for c in cs)
    pad = ["rễ", "gốc", "lá", "đọt", "cành"]
    n3 = max(muc - dem(c1, c2, c4, c5) - 1, 3)
    c3 = f"[confident] Lô {i} " + " ".join(pad[k % 5] for k in range(n3)) + "."
    it = {"goc": "x", "text": " ".join([c1, c2, c3, c4, c5]), "dong": ["a"], "y_canh": ["a"] * 5, "chu_mo": "Một chữ móc", "nhan_tu": ["x"],
          "caption": ["Cap một"], "hashtag": ["#một"], "giong": CFG_GIONG[0]}
    it.update(them)
    return it


CFG_GIONG = list(vl.CFG["giong"]["danh_sach"])


class Nen(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bk-"))
        self.hub, self.kho = self.tmp / "hub", self.tmp / "kho"
        (self.hub / "lich-su").mkdir(parents=True); (self.hub / "san-pham" / "sp-thu").mkdir(parents=True); self.kho.mkdir()
        self._h, self._d = vl.HUB, pm.DATA
        vl.HUB, pm.DATA = self.hub, self.tmp / "data"
        vl._GIONG_CACHE.clear()
        self.sp = sp_mau(self.kho)
        (self.hub / "san-pham" / "sp-thu" / "san-pham.json").write_text(json.dumps(self.sp, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        vl.HUB, pm.DATA = self._h, self._d
        vl._GIONG_CACHE.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def mo_ta(self, rel, kieu=2, loi=(), thu_muc=None):
        d = self.kho / "_mo-ta" / (thu_muc or "")
        d.mkdir(parents=True, exist_ok=True)
        (d / (rel + ".mo-ta.json")).write_text(json.dumps({"video": rel, "kieu": kieu, "loi_hay": list(loi)}, ensure_ascii=False), encoding="utf-8")

    def canh(self, shots):
        (self.hub / "san-pham" / "sp-thu" / "canh.json").write_text(json.dumps(shots, ensure_ascii=False), encoding="utf-8")


class TrucTest(Nen):
    def chay(self, sp, goc, n=40, seed=0, tong=None):
        dem, lo = vl.moi_dem(), vl.lo_moi()
        return vl.gan_truc(sp, goc, n, dem, {}, lo, tong or n, rng=random.Random(seed))

    def test_rang_buoc_va_han_ngach_40_ban(self):
        for ben_em in (False, True):
            sp = sp_mau(self.kho, su_that_duoc_noi=["Bên em gửi hàng từ kho."] if ben_em else ["Một chai pha 200 lít."])
            for seed in range(25):
                ts = self.chay(sp, ["rua-vuon", "cach-dung"], 40, seed)
                self.assertEqual(len(ts), 40)
                self.assertEqual({t["mo"] for t in ts[:15]}, set(vl.MO), "15 kiểu mở đều được dùng trước khi lặp")
                self.assertEqual(len({t["mo"] for t in ts[:15]}), 15)
                self.assertLessEqual(sum(t["chot"] == "qua_cu_the" for t in ts), 10)
                self.assertLessEqual(sum(t["vai"] == "dan_chuyen" for t in ts), 8)
                for t in ts:
                    if t["mo"] == "qua_truoc":
                        self.assertEqual(t["chot"], "qua_cu_the")
                    if t["mo"] == "thu_nhan" or t["than"] in ("hoai_nghi", "chuyen_that_bai"):
                        self.assertIn(t["vai"], {"nha_vuon", "nguoi_ban_quay", "chu_hang"})
                    if t["than"] in ("soi_nhan", "khang_dinh"):
                        self.assertIn(t["vai"], {"chu_hang", "dan_chuyen", "ky_thuat"})
                    if t["chot"] == "dong_hanh":
                        self.assertTrue(ben_em)
                        self.assertIn(t["vai"], {"chu_hang", "nguoi_ban_quay"})
                    self.assertIn(t["mo"], vl.MO); self.assertIn(t["than"], vl.THAN); self.assertIn(t["chot"], vl.CHOT); self.assertIn(t["vai"], vl.VAI)
            self.assertEqual(any(t["chot"] == "dong_hanh" for s in range(25) for t in self.chay(sp, ["rua-vuon"], 40, s)), ben_em)

    def test_xoay_deu_cac_khoa_va_goc(self):
        ts = self.chay(self.sp, ["rua-vuon", "cach-dung", "qua-tang"], 33, 3)
        for ax, bang in (("mo", vl.MO), ("than", vl.THAN), ("chot", vl.CHOT), ("vai", vl.VAI), ("goc", ["rua-vuon", "cach-dung", "qua-tang"])):
            dem = {k: sum(t[ax] == k for t in ts) for k in bang}
            self.assertTrue(all(v > 0 for v in dem.values()) or ax in ("chot", "vai"), (ax, dem))
        g = [t["goc"] for t in ts]
        self.assertEqual({g.count(x) for x in set(g)}, {11})

    def test_lich_su_it_dung_nhat_truoc(self):
        for k in list(vl.MO)[1:]:
            vl._them_so("mo-sp-thu.txt", k)
        t = vl.gan_truc(self.sp, ["rua-vuon"], 1, vl.moi_dem("sp-thu"), {}, vl.lo_moi(), 1, rng=random.Random(1))[0]
        self.assertEqual(t["mo"], list(vl.MO)[0])

    def test_he_so_keo_khoa_hieu_qua_len_truoc(self):
        dem, lo = vl.moi_dem(), vl.lo_moi()
        dem["mo"].update({k: 1 for k in vl.MO})
        t = vl.gan_truc(self.sp, ["rua-vuon"], 1, dem, {"mo": {"con_so": 1000.0}}, lo, 1, rng=random.Random(1))[0]
        self.assertEqual(t["mo"], "con_so")

    def test_goc_qua_tang_khong_bi_han_ngach_chot_qua(self):
        # chỉ có góc qua-tang: không còn hạn 1/4 — ít nhất không vỡ và qua_truoc vẫn đi cùng qua_cu_the
        ts = self.chay(self.sp, ["qua-tang"], 40, 5)
        self.assertTrue(all(t["chot"] == "qua_cu_the" for t in ts if t["mo"] == "qua_truoc"))

    def test_ghi_so_an_toan_khong_nem_loi(self):
        vl.HUB = self.tmp / "file-khong-phai-thu-muc"
        (self.tmp / "file-khong-phai-thu-muc").write_text("x")
        vl._them_so("mo-x.txt", "a")          # không ném lỗi


class DeBaiTest(Nen):
    def dung_prompt(self, truc, used=("CAU-DA-DUNG-SENTINEL.",), qc=None, **kw):
        sp_ai = {k: v for k, v in self.sp.items() if k not in ("kho_video",)}
        return vl.build_prompt(sp_ai, len(truc), [t["goc"] for t in truc], list(used), [], [t["than"] for t in truc], ["Câu mở cũ một."], qc, "", truc, sp_day=self.sp, **kw)

    def truc3(self):
        return [{"goc": "rua-vuon", "mo": "mat_mat", "than": "chuyen_that_bai", "chot": "thu_it", "vai": "nha_vuon"},
                {"goc": "cach-dung", "mo": "con_so", "than": "phep_tinh", "chot": "phep_tinh_chot", "vai": "ky_thuat"},
                {"goc": "qua-tang", "mo": "qua_truoc", "than": "khang_dinh", "chot": "qua_cu_the", "vai": "dan_chuyen"}]

    def test_mau_mac_dinh_dung_het_bien_da_dang_ky(self):
        mau = pm.mac_dinh("bien-kich")
        kq = pm.kiem("bien-kich", mau)
        self.assertEqual(kq, {"thieu": [], "la": []})
        for b in ("de_bai", "giong_that", "kho_canh", "so_lieu_tiktok", "loi_truoc"):
            self.assertIn("{{" + b + "}}", mau)
        for b in ("cau_da_dung", "angles", "dang"):
            self.assertNotIn("{{" + b + "}}", mau)

    def test_prompt_chi_co_mo_ta_truc_duoc_giao(self):
        self.mo_ta("a.mp4", loi=["Cái này mà sai là mất nguyên lứa luôn."])
        self.canh([{"id": "1", "vai_tro": ["chai_ro"], "cay": ["ca_phe"], "soat": {"mat": 0, "dep": 4}}])
        p = self.dung_prompt(self.truc3())
        self.assertNotIn("{{", p)
        for t in self.truc3():
            for ax, bang in (("mo", {k: v[0] for k, v in vl.MO.items()}), ("than", vl.THAN), ("chot", vl.CHOT), ("vai", vl.VAI)):
                self.assertIn(f"{t[ax]} — {bang[t[ax]]}", p)
        for k in ("nghich_ly", "dung_tay", "ba_sai_lam", "kip_luc", "chu_hang"):
            self.assertNotIn(vl.MO[k][0] if k in vl.MO else (vl.THAN.get(k) or vl.CHOT.get(k) or vl.VAI[k]), p)
        self.assertIn('bai[0]: góc = rua-vuon (Rửa vườn sau thu hoạch (cà phê): đúng lúc, đúng việc.)', p)
        self.assertIn('(ví dụ cấu trúc, KHÔNG chép: "Nguyên một lứa cành giâm… chết vì đúng một bước.")', p)
        self.assertIn("Luật câu mở: ≤ 10 âm tiết", p)
        self.assertNotIn("goc_ban", p); self.assertNotIn("cat_khung_ly_do", p); self.assertNotIn("thoi_luong", p)
        self.assertNotIn("CAU-DA-DUNG-SENTINEL", p)                              # 150 câu đã dùng không còn gửi
        self.assertIn("Câu mở cũ một.", p)
        self.assertNotIn("BẢN TRƯỚC BỊ LOẠI VÌ", p)
        self.assertIn("Chỉ trả về MỘT mảng JSON", p)
        self.assertIn('"chu_mo"', p)

    def test_khoi_kho_canh(self):
        ok = lambda vt, cay=(), mat=0: {"id": "x", "vai_tro": vt, "cay": list(cay), "soat": {"mat": mat, "dep": 4, "chu_muc": 0}}
        shots = [ok(["chai_ro"], ["ca_phe"]) for _ in range(3)] + [ok(["phun", "pha_rot"], ["ho_tieu", "khong_ro"]), ok(["van_de"], ["cay_khac"], 2),
                 ok(["kho_hang"]), {"id": "bad1", "vai_tro": ["chai_ro"], "soat": {"chu_muc": 2}}, {"id": "bad2", "vai_tro": ["re"], "soat": {"hang_khac": True}},
                 {"id": "bad3", "vai_tro": ["re"], "soat": {"dep": 1}}]
        self.canh(shots)
        k = vl.kho_canh("sp-thu")
        self.assertIn("=== KHO CẢNH ĐANG CÓ (viết sao cho hình có thật; loại ghi 0 hoặc \"ít\" thì đừng viết câu cần đúng hình đó) ===", k)
        self.assertIn("chai rõ nhãn: 3 · mặt sau nhãn: 0 · pha, rót: 1 (ít) · phun, tưới: 1 (ít) · rễ, gốc: 0 · cây con: 0 · cây bệnh: 1 (ít)", k)
        self.assertIn("người nói: 1 (ít)", k)
        self.assertIn("kho hàng: 1 (ít)", k)
        self.assertIn("Cây có trong kho: cà phê, hồ tiêu.", k)
        self.assertEqual(vl.kho_canh("khong-co-san-pham"), "")
        self.assertIn("chai rõ nhãn: 3", self.dung_prompt(self.truc3()))

    def test_khoi_giong_that(self):
        (self.hub / "san-pham" / "sp-khac").mkdir()
        (self.hub / "san-pham" / "sp-khac" / "san-pham.json").write_text(json.dumps({"ma": "sp-khac", "ten_goi": "Beta Silver", "ten_ngan": "Beta Silver"}), encoding="utf-8")
        tot = ["Mình làm vườn mấy chục năm rồi mới thấy cái này chạy thật sự đó anh em ơi.", "Bà con ra vườn sáng sớm coi đọt non nó xoăn hết một hàng ngoài kia."]
        self.mo_ta("a.mp4", loi=tot + ["Ngắn quá.", "Một chai pha hai trăm lít nước cho cả vườn nhà tôi 200 gốc.", "Dùng Beta Silver thì cây lên rất đều tay anh em ơi nghe chưa."])
        self.mo_ta("b.mp4", kieu=1, loi=["Câu của mô tả kiểu cũ không được lấy đâu nha anh em."])
        self.mo_ta("c.mp4", loi=["Câu nằm trong thư mục gạch dưới phải bị bỏ qua hoàn toàn đó nha."], thu_muc="_cu")
        self.mo_ta("d.mp4", loi=["Trong thư mục con bình thường thì vẫn lấy được câu này đó nhé anh em."], thu_muc="sub")
        k = vl.giong_that(self.sp, random.Random(1))
        self.assertTrue(k.startswith("\n=== GIỌNG NÓI THẬT NGOÀI VƯỜN (người thật nói trong clip — học NHỊP và CÁCH DÙNG TỪ; không chép câu, không lấy số liệu hay công dụng từ đây) ==="))
        for c in tot + ["Trong thư mục con bình thường thì vẫn lấy được câu này đó nhé anh em."]:
            self.assertIn(f'- "{c}"', k)
        for c in ("kiểu cũ", "gạch dưới", "200 gốc", "Beta Silver"):
            self.assertNotIn(c, k)
        self.assertLess(k.index("Mình làm vườn"), k.index("Ngắn quá"))        # câu 8–30 từ trước
        self.assertIn("GIỌNG NÓI THẬT", self.dung_prompt(self.truc3()))
        vl._GIONG_CACHE.clear(); (self.kho / "_mo-ta" / "a.mp4.mo-ta.json").unlink()
        self.mo_ta("a.mp4", loi=[])
        self.assertEqual(vl.giong_that(sp_mau(self.kho / "khong-co")), "")

    def test_giong_that_cache_theo_gio_sua(self):
        self.mo_ta("a.mp4", loi=["Câu thứ nhất của người thật nói rất tự nhiên ngoài vườn nhà mình."])
        self.assertEqual(len(vl._loi_hay_kho(self.kho)), 1)
        f = self.kho / "_mo-ta" / "a.mp4.mo-ta.json"
        f.write_text(json.dumps({"kieu": 2, "loi_hay": ["Một câu mới hoàn toàn của người thật nói ngoài vườn.", "Câu hai của người thật nói ngoài vườn nè bà con."]}, ensure_ascii=False), encoding="utf-8")
        os.utime(f, (f.stat().st_atime + 5, f.stat().st_mtime + 5))
        self.assertEqual(len(vl._loi_hay_kho(self.kho)), 2)

    def test_de_cu_van_chay_va_nhan_gia_tri_hop_ly(self):
        cu = ("CU {{luat}} | SP {{san_pham}} | ten {{ten_phai_nhac}} | n={{so_ban}} | giong={{giong}}\n"
              "angles = {{angles}}\ndang = {{dang}}\nDA DUNG: {{cau_da_dung}}\nmo dau: {{cau_mo_da_dung}}\n")
        pm.duong_dan_sua("bien-kich").parent.mkdir(parents=True, exist_ok=True)
        pm.duong_dan_sua("bien-kich").write_text(cu, encoding="utf-8")
        p = self.dung_prompt(self.truc3())
        self.assertNotIn("{{", p)
        self.assertIn('angles = ["rua-vuon", "cach-dung", "qua-tang"]', p)
        self.assertIn("chuyen_that_bai: " + vl.THAN["chuyen_that_bai"], p)
        self.assertIn("CAU-DA-DUNG-SENTINEL", p)                                 # đề cũ vẫn nhận 150 câu đã dùng
        self.assertIn("bai[0]: góc = rua-vuon", p)                               # de_bai bắt buộc → máy tự gắn vào cuối
        self.assertNotIn("BẢN TRƯỚC BỊ LOẠI VÌ", p)

    def test_xem_thu_ctx_khong_nem_loi(self):
        c = vl.ctx_xem_thu("sp-thu", self.sp, 3)
        self.assertIn("bai[2]", c["de_bai"])
        out = pm.dung("bien-kich", pm.mac_dinh("bien-kich"), c)
        self.assertNotIn("{{", out)

    def test_khoi_loi_truoc_toi_da_5(self):
        p = self.dung_prompt(self.truc3(), loi_truoc=[f"lỗi {i}" for i in range(8)])
        self.assertIn("BẢN TRƯỚC BỊ LOẠI VÌ:\n- lỗi 3\n- lỗi 4\n- lỗi 5\n- lỗi 6\n- lỗi 7\n\n=== ĐỊNH DẠNG", p)
        self.assertNotIn("lỗi 2", p)

    def test_cau_mo_chi_30_cau_gan_nhat(self):
        sp_ai = dict(self.sp)
        c = vl.ctx_bien_kich(sp_ai, 1, ["rua-vuon"], [], [], ["truoc_sau"], [f"c{i}" for i in range(100)])
        self.assertEqual(json.loads(c["cau_mo_da_dung"]), [f"c{i}" for i in range(70, 100)])
        self.assertEqual(c["dang"], json.dumps(["truoc_sau: " + vl.THAN["truoc_sau"]], ensure_ascii=False))


class CheckTest(Nen):
    def kiem(self, item, used=None):
        return vl.check(item, self.sp, used or set())[0]

    def test_ban_hop_le(self):
        for mo in ("mat_mat", "con_so"):
            self.assertEqual(self.kiem(kich_ban(1, self.sp, mo=mo, vai="nha_vuon", chot="thu_it", than="truoc_sau")), [])

    def thay(self, c_text, **them):
        it = kich_ban(2, self.sp, **them)
        it["text"] = c_text(it["text"])
        return it

    def test_tu_cam_moi(self):
        for tu in ("giải pháp toàn diện", "hiệu quả vượt trội", "chất lượng hàng đầu"):
            e = self.kiem(self.thay(lambda t: t.replace("Ngắn thôi.", f"Là {tu} đó."), mo="mat_mat"))
            self.assertTrue(any(tu in x for x in e), (tu, e))

    def test_nha_ne_khong_con_la_tu_cam_nhung_vai_ky_thuat_cam(self):
        it = self.thay(lambda t: t.replace("Ngắn thôi.", "Cứ thử đi nha."), vai="nha_vuon")
        self.assertEqual(self.kiem(it), [])
        e = self.kiem(self.thay(lambda t: t.replace("Ngắn thôi.", "Cứ thử đi nha."), vai="ky_thuat"))
        self.assertTrue(any("vai ky_thuat" in x for x in e), e)
        e = self.kiem(self.thay(lambda t: t.replace("Ngắn thôi.", "Thử đi nè."), vai="dan_chuyen"))
        self.assertTrue(any("dan_chuyen" in x for x in e), e)

    def test_tieng_dem_toi_da_2(self):
        ba = lambda t: t.replace("Ngắn thôi.", "Cứ thử đi ạ.").replace("khựng lại.", "khựng lại luôn nha.").replace("Lô 2", "Lô 2 chắc nha, ")
        e = self.kiem(self.thay(ba, vai="nha_vuon"))
        self.assertTrue(any("tiếng đệm" in x for x in e), e)
        hai = lambda t: t.replace("Ngắn thôi.", "Cứ thử đi ạ.").replace("khựng lại.", "khựng lại luôn nha.")
        self.assertFalse(any("tiếng đệm" in x for x in self.kiem(self.thay(hai, vai="nha_vuon"))))

    def test_tag_it_nhat_3_khac_nhau(self):
        e = self.kiem(self.thay(lambda t: t.replace("[warm]", "[confident]").replace("[concerned]", "[confident]").replace("[curious]", "[confident]")))
        self.assertTrue(any("tag khác nhau" in x for x in e), e)

    def test_tag_ngoai_danh_sach_thay_bang_confident_khong_loai(self):
        it = self.thay(lambda t: t.replace("[concerned]", "[like a farmer, tired]"))
        self.assertEqual(self.kiem(it), [])
        self.assertNotIn("farmer", it["text"])
        it2 = self.thay(lambda t: t.replace("[concerned]", "[Warm,   Confident]").replace("[warm]", "[whispering]"))
        e = self.kiem(it2)
        self.assertNotIn("whispering", it2["text"]); self.assertIn("[warm, confident]", it2["text"])
        self.assertEqual(e, [])

    def test_ten_san_pham_trong_2_cau_dau(self):
        muon = lambda t: t.replace("[concerned] Alpha Gold vào đúng lúc.", "[concerned] Nó vào đúng lúc.").replace("Bấm giỏ hàng nhé.", "Alpha Gold, bấm giỏ hàng nhé.")
        e = self.kiem(self.thay(muon, mo="mat_mat", than="truoc_sau"))
        self.assertTrue(any("2 câu đầu" in x for x in e), e)
        sau3 = lambda t: t.replace("[concerned] Alpha Gold vào đúng lúc. [confident] Lô 2", "[concerned] Nó vào đúng lúc. [confident] Alpha Gold, lô 2")
        for mo, than, ok in (("ket_qua_truoc", "truoc_sau", True), ("dang_xay_ra", "truoc_sau", True), ("mat_mat", "chuyen_that_bai", True), ("mat_mat", "truoc_sau", False)):
            e = self.kiem(self.thay(sau3, mo=mo, than=than))
            self.assertEqual(not any("câu đầu" in x for x in e), ok, (mo, than, e))
        e = self.kiem(self.thay(lambda t: t.replace("Alpha Gold", "Ai đó"), mo="mat_mat"))
        self.assertIn("thiếu tên thương hiệu", e)

    def test_cau_mo(self):
        dai = lambda t: t.replace("Vườn thứ 2 khựng lại.", "Vườn thứ 2 hôm nay nhìn lên thấy lá vàng hết cả một hàng dài ngoài kia luôn.")
        e = self.kiem(self.thay(dai, mo="mat_mat"))
        self.assertTrue(any("câu mở dài" in x for x in e), e)
        ten = lambda t: t.replace("[curious] Vườn thứ 2 khựng lại. [concerned] Alpha Gold vào đúng lúc.", "[curious] Alpha Gold khựng lại. [concerned] Vào đúng lúc.")
        e = self.kiem(self.thay(ten, mo="mat_mat"))
        self.assertTrue(any("bắt đầu bằng tên sản phẩm" in x for x in e), e)
        for mo in ("qua_truoc", "con_so"):
            self.assertFalse(any("bắt đầu bằng tên" in x for x in self.kiem(self.thay(ten, mo=mo))), mo)

    def test_gio_hang_dung_mot_lan(self):
        e = self.kiem(self.thay(lambda t: t.replace("Bấm giỏ hàng nhé.", "Bấm vào đó nhé."), mo="mat_mat"))
        self.assertIn("không nhắc giỏ hàng", e)
        e = self.kiem(self.thay(lambda t: t.replace("Bấm giỏ hàng nhé.", "Giỏ hàng đó, giỏ hàng này, giỏ hàng kia."), mo="mat_mat"))
        self.assertTrue(any("giỏ hàng 3 lần" in x for x in e), e)
        self.assertFalse(any("giỏ hàng" in x for x in self.kiem(self.thay(lambda t: t.replace("Bấm giỏ hàng nhé.", "Giỏ hàng đây, giỏ hàng kia."), mo="mat_mat"))))

    def test_tang_o_chot_khong_phai_qua_chi_ghi_log(self):
        nhat = []
        it = self.thay(lambda t: t.replace("Bấm giỏ hàng nhé.", "Có tặng kèm, bấm giỏ hàng."), chot="thu_it", mo="mat_mat")
        e, _ = vl.check(it, self.sp, set(), nhat.append)
        self.assertEqual(e, []); self.assertEqual(len(nhat), 1)
        nhat.clear()
        it = self.thay(lambda t: t.replace("Bấm giỏ hàng nhé.", "Có tặng kèm, bấm giỏ hàng."), chot="qua_cu_the", mo="mat_mat")
        vl.check(it, self.sp, set(), nhat.append)
        self.assertEqual(nhat, [])

    def test_so_am_tiet_va_lap_cau_van_nhu_cu(self):
        it = kich_ban(3, self.sp, mo="mat_mat")
        it["text"] = "[curious] Vườn thứ 3. [warm] Alpha Gold đây. [confident] Giỏ hàng."
        self.assertTrue(any("âm tiết" in x for x in self.kiem(it)))
        it = kich_ban(4, self.sp, mo="mat_mat")
        cau = vl.re.split(r"(?<=[.!?])\s+", vl.re.sub(r"\[[^\]]*\]", "", it["text"]).strip())[2]
        self.assertTrue(any(x.startswith("lặp câu") for x in self.kiem(it, {vl.norm(cau)})))

    def test_chu_mo_cat_30_ky_tu(self):
        self.assertEqual(vl.gon_chu_mo("Một hai ba bốn năm sáu bảy tám chín mười"), "Một hai ba bốn năm sáu bảy")
        self.assertLessEqual(len(vl.gon_chu_mo("x" * 80)), 30)
        self.assertEqual(vl.gon_chu_mo("  Chữ   móc  "), "Chữ móc")
        self.assertEqual(vl.gon_chu_mo(None), "")


class SoLieuTest(Nen):
    def ghi(self, n, xem, ma="sp-thu"):
        db = {f"v{i}": {"ma": ma, "goc": "rua-vuon", "dang": "truoc_sau", "xem24": xem} for i in range(n)}
        (self.hub / "lich-su" / "hieu-qua.json").write_text(json.dumps(db), encoding="utf-8")

    def test_cong_so_lieu(self):
        self.assertFalse(vl._cong_so_lieu("sp-thu"))                      # chưa có file
        self.ghi(14, 900); self.assertFalse(vl._cong_so_lieu("sp-thu"))   # thiếu video
        self.ghi(15, 199); self.assertFalse(vl._cong_so_lieu("sp-thu"))   # trung vị thấp (nhiễu)
        self.ghi(15, 200); self.assertTrue(vl._cong_so_lieu("sp-thu"))
        self.ghi(20, 500, ma="sp-khac"); self.assertTrue(vl._cong_so_lieu("sp-thu"))   # sản phẩm chưa đủ video → nhóm là mọi sản phẩm

    def test_so_lieu_va_he_so_chi_khi_qua_cong(self):
        import hieu_qua
        t0, h0, tt0 = vl._tom_tat, hieu_qua.he_so, vl._tom_tat
        vl._tom_tat = lambda ma, cho="bien_kich": "TOM TAT THAT"
        hieu_qua.he_so = lambda ma, chieu: {"con_so": 1.5}
        try:
            self.ghi(14, 900)
            self.assertEqual(vl._so_lieu("sp-thu"), ""); self.assertEqual(vl._he_so("sp-thu", "mo"), {})
            self.ghi(15, 900)
            self.assertEqual(vl._so_lieu("sp-thu"), "TOM TAT THAT"); self.assertEqual(vl._he_so("sp-thu", "mo"), {"con_so": 1.5})
            c = vl.ctx_bien_kich(self.sp, 1, ["rua-vuon"], [], [], ["truoc_sau"], [], None, vl._so_lieu("sp-thu"))
            self.assertIn("=== SỐ LIỆU THẬT TỪ TIKTOK (video đã đăng) ===\nTOM TAT THAT", c["so_lieu_tiktok"])
        finally:
            vl._tom_tat, hieu_qua.he_so = t0, h0


class VietTest(Nen):
    def chay(self, phan_hoi):
        prompts, goi_cu = [], vl.goi
        def goi_gia(vai, prompt, *a, **k):
            prompts.append(prompt)
            return (json.dumps(phan_hoi[len(prompts) - 1], ensure_ascii=False), {})
        vl.goi = goi_gia
        try:
            return vl.viet("sp-thu", 2, log=lambda *_: None), prompts
        finally:
            vl.goi = goi_cu

    def test_viet_hai_ban_loai_mot_goi_lai(self):
        self.canh([{"id": "1", "vai_tro": ["chai_ro"], "cay": ["ca_phe"], "soat": {"mat": 0, "dep": 4}}])
        self.mo_ta("a.mp4", loi=["Mình làm vườn mấy chục năm rồi mới thấy cái này chạy thật sự đó anh em ơi."])
        tot, xau = kich_ban(1, self.sp, u=True, chu_mo="Chữ móc rất dài vượt quá ba mươi ký tự mất rồi"), kich_ban(2, self.sp, u=True, gh="Bấm vào đó nhé.")
        ra, prompts = self.chay([[tot, xau], [kich_ban(3, self.sp, u=True)]])
        self.assertEqual(len(ra), 2); self.assertEqual(len(prompts), 2)
        self.assertNotIn("BẢN TRƯỚC BỊ LOẠI VÌ", prompts[0])
        self.assertIn("BẢN TRƯỚC BỊ LOẠI VÌ:\n- không nhắc giỏ hàng\n\n=== ĐỊNH DẠNG", prompts[1])
        for p in prompts:
            self.assertIn("bai[0]: góc =", p); self.assertIn("KHO CẢNH ĐANG CÓ", p); self.assertIn("GIỌNG NÓI THẬT", p)
        self.assertIn("bai[1]", prompts[0]); self.assertNotIn("bai[1]", prompts[1])
        for it in ra:
            self.assertEqual(it["dang"], it["than"])
            self.assertIn(it["mo"], vl.MO); self.assertIn(it["than"], vl.THAN); self.assertIn(it["chot"], vl.CHOT); self.assertIn(it["vai"], vl.VAI)
            self.assertLessEqual(len(it["chu_mo"]), 30)
            self.assertTrue(it["text"] and it["captions"] and it["hashtag"] == ["#mot"])
        self.assertTrue(ra[0]["chu_mo"].startswith("Chữ móc rất dài"))
        ls = self.hub / "lich-su"
        for ax in ("goc", "mo", "than", "dang", "chot", "vai", "mo-dau"):
            dong = (ls / f"{ax}-sp-thu.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(dong), 2, ax)
        self.assertEqual((ls / "mo-sp-thu.txt").read_text(encoding="utf-8").splitlines(), [it["mo"] for it in ra])
        self.assertEqual((ls / "than-sp-thu.txt").read_text(encoding="utf-8"), (ls / "dang-sp-thu.txt").read_text(encoding="utf-8"))

    def test_viet_khong_lap_lai_mo_giua_cac_lan_goi(self):
        ra, prompts = self.chay([[kich_ban(1, self.sp, u=True), kich_ban(2, self.sp, u=True, gh="Bấm vào đó nhé.")], [kich_ban(3, self.sp, u=True)]])
        mo_goi = [m for p in prompts for m in vl.re.findall(r"kiểu mở = (\w+) —", p)]
        self.assertEqual(len(mo_goi), len(set(mo_goi)), mo_goi)


class MaNguonTest(unittest.TestCase):
    def test_manifest_va_ghi_chu_cho_bien_kich_va_luat(self):
        man = json.loads((REPO / "prompt" / "_ban-phat-hanh.json").read_text(encoding="utf-8"))
        notes = json.loads((REPO / "prompt" / "_ghi-chu-cap-nhat.json").read_text(encoding="utf-8"))
        for k in ("bien-kich", "luat-san-xuat"):
            self.assertEqual(man[k]["ver"], "1.2.13")
            self.assertIn("15 kiểu mở đầu", notes[k]["1.2.13"])
        self.assertTrue(set(vl.DANG_BAI) == set(vl.THAN))


if __name__ == "__main__":
    unittest.main()
