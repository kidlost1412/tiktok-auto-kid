"""Thử lớp chữ: xếp khối theo CHỈ SỐ TỪ của đạo diễn, phụ đề nhỏ/ngắn/tuỳ chọn, kiểm khung toàn màn trơ, mô tả khối.
Không gọi AI/mạng, không dựng video."""
import os, random, re, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-lopchu-"))
GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC / "engine"))

import cong_thuc as CT  # noqa: E402
import ne_nhan  # noqa: E402
import phu_de as PD  # noqa: E402

FPS = 30


def lieu(n=44, dt=0.42):
    """Lời giả: n từ, mỗi từ dt giây; câu 8 từ."""
    words = [{"w": f"t{i}", "s": round(i * dt, 3), "e": round(i * dt + dt * 0.9, 3)} for i in range(n)]
    sents = []
    for k in range(0, n, 8):
        ws = words[k:k + 8]
        sents.append({"s": ws[0]["s"], "e": ws[-1]["e"], "words": ws})
    return words, sents, round(n * dt + 0.6, 2)


def xep(khoi, recipe="danh_sach", n=44, st=None):
    words, sents, total = lieu(n)
    return CT.xep_khoi(recipe, khoi, sents, total, st or {}, random.Random(3), "BỌ TRĨ TOP ONE", words), words


class XepKhoiTheoTu(unittest.TestCase):
    def test_doi_chi_so_tu_ra_khung(self):
        (bl, _), w = xep([{"loai": "chu_dap", "tu": 10, "den": 12, "du_lieu": {"text": "ĐỪNG ĐỂ BÔNG RỤNG"}}])
        b = [x for x in bl if x["loai"] == "chu_dap"][0]
        self.assertEqual(b["f0"], round(w[10]["s"] * FPS))
        self.assertGreaterEqual(b["f1"], round(w[12]["e"] * FPS))             # hết từ cuối (gồm cả 'den') mới tắt
        self.assertLessEqual(b["f1"], round(w[12]["e"] * FPS) + FPS)

    def test_kep_trong_khoang_hop_le(self):
        (bl, _), w = xep([{"loai": "chu_dap", "tu": -5, "den": 9999, "du_lieu": {"text": "A B"}}])
        b = [x for x in bl if x["loai"] == "chu_dap"][0]
        self.assertGreaterEqual(b["f0"], 0)
        self.assertLessEqual(b["f1"], int(round(lieu()[2] * FPS)))

    def test_moi_loai_da_dang_ky_duoc_dung_ngoai_cong_thuc(self):
        # danh_sach chỉ có giữa = checklist; đạo diễn nêu chu_so vẫn phải được dùng
        (bl, _), _w = xep([{"loai": "chu_so", "tu": 12, "den": 14, "du_lieu": {"so": "240", "don_vi": "ML"}},
                           {"loai": "canh_bao", "tu": 24, "den": 27, "du_lieu": {"text": "LỖI 2"}}])
        self.assertIn("chu_so", [b["loai"] for b in bl]); self.assertIn("canh_bao", [b["loai"] for b in bl])

    def test_loai_la_hoac_du_lieu_rac_bi_bo(self):
        (bl, _), _w = xep([{"loai": "khong_co", "tu": 5, "den": 7, "du_lieu": {"text": "x"}}, {"loai": "chu_so", "tu": 9, "den": 10, "du_lieu": {"so": "abc"}},
                           "rac", {"loai": "chu_gach", "tu": 14, "den": 16, "du_lieu": {"text": ""}}])
        self.assertFalse(any(b["loai"] in ("khong_co", "chu_so", "chu_gach") for b in bl))

    def test_kieu_cu_theo_cau_van_chay(self):
        (bl, _), _w = xep([{"loai": "hook_dap", "cau": 0, "du_lieu": {"text": "KHOAN ĐỔ!", "nhan": 0}},
                           {"loai": "checklist", "cau": 2, "du_lieu": {"items": ["MỘT", "HAI"]}},
                           {"loai": "nut_gio_hang", "cau": 5, "du_lieu": {"text": "BẤM"}}])
        ks = [b["loai"] for b in bl]
        self.assertEqual(ks[0], "hook_dap"); self.assertIn("checklist", ks); self.assertEqual(ks[-1], "nut_gio_hang")

    def test_khong_de_len_nhau_cung_vung(self):
        (bl, _), _w = xep([{"loai": "chu_dap", "tu": 12, "den": 18, "du_lieu": {"text": "MỘT"}, "vi_tri": "tren"},
                           {"loai": "chu_gach", "tu": 14, "den": 20, "du_lieu": {"text": "HAI"}, "vi_tri": "tren"},     # chờ quá lâu → bỏ
                           {"loai": "chu_mat_na", "tu": 24, "den": 28, "du_lieu": {"text": "BA"}, "vi_tri": "tren"}])
        tren = [b for b in bl if b.get("vi_tri") == "tren"]
        for i, a in enumerate(tren):
            for b in tren[i + 1:]:
                self.assertTrue(a["f1"] <= b["f0"] or b["f1"] <= a["f0"], (a, b))
        self.assertNotIn("chu_gach", [b["loai"] for b in bl])
        self.assertIn("chu_mat_na", [b["loai"] for b in bl])

    def test_cho_it_thi_doi_khong_bo(self):
        (bl, _), w = xep([{"loai": "chu_dap", "tu": 12, "den": 12, "du_lieu": {"text": "MỘT"}, "vi_tri": "giua"},
                          {"loai": "chu_gach", "tu": 14, "den": 18, "du_lieu": {"text": "HAI"}, "vi_tri": "giua"}])
        g = [b for b in bl if b.get("vi_tri") == "giua"]
        self.assertEqual(len(g), 2)
        self.assertTrue(g[0]["f1"] <= g[1]["f0"])

    def test_vung_khac_nhau_chong_len_duoc(self):
        (bl, _), _w = xep([{"loai": "chu_dap", "tu": 12, "den": 18, "du_lieu": {"text": "MỘT"}, "vi_tri": "tren"},
                           {"loai": "chu_so", "tu": 13, "den": 18, "du_lieu": {"so": "240"}, "vi_tri": "duoi"}])
        self.assertEqual(sum(b["loai"] in ("chu_dap", "chu_so") for b in bl), 2)

    def test_vi_tri_am_chuyen_qua_va_co_dinh_top(self):
        (bl, _), _w = xep([{"loai": "chu_so", "tu": 12, "den": 15, "du_lieu": {"so": "240"}, "vi_tri": "duoi", "am": "khong"},
                           {"loai": "chu_dap", "tu": 24, "den": 27, "du_lieu": {"text": "X"}, "am": "dap"}])
        a = [b for b in bl if b["loai"] == "chu_so"][0]; d = [b for b in bl if b["loai"] == "chu_dap"][0]
        self.assertEqual((a["vi_tri"], a["am"], a["co_dinh"], a["zone"]), ("duoi", "khong", True, "LOWER"))
        self.assertGreaterEqual(a["top"], 1000)
        self.assertEqual(d["am"], "dap"); self.assertNotIn("co_dinh", d)

    def test_toi_da_tam_khoi(self):
        khoi = [{"loai": "chu_dap", "tu": 2 + 5 * i, "den": 3 + 5 * i, "du_lieu": {"text": f"Ý {i}"}} for i in range(14)]
        (bl, _), _w = xep(khoi)
        self.assertLessEqual(len(bl), CT.MAX_KHOI + 2)

    def test_chot_luon_cuoi_va_cau_mo_dau_neu_khong_nem_khoi_som(self):
        (bl, cta), _w = xep([{"loai": "chu_tang", "tu": 12, "den": 14, "du_lieu": {"text": "ĐỪNG ĐỂ BÔNG RỤNG"}}])
        self.assertEqual(bl[-1]["f0"], cta); self.assertTrue(bl[0]["loai"].startswith("hook_"))
        (bl2, _), _w = xep([{"loai": "chu_dap", "tu": 0, "den": 3, "du_lieu": {"text": "KHOAN ĐỔ"}}])
        self.assertEqual(bl2[0]["loai"], "chu_dap")                         # đạo diễn đã đặt khối ngay đầu → không chèn câu mở dự phòng
        self.assertFalse(any(b["loai"].startswith("hook_") for b in bl2))

    def test_dao_dien_chon_hook_ngoai_cong_thuc_khong_bi_doi_ngau_nhien(self):
        (bl, _), _w = xep([{"loai": "hook_dap", "cau": 0, "du_lieu": {"text": "KHOAN!"}}], recipe="tvc_sang", st={"ep_mo": "hook_bang"})
        self.assertEqual(bl[0]["loai"], "hook_dap")

    def test_chu_cai_chu_lon_cat_14_ky_tu_moi_dong_2_dong(self):
        d = CT.clean_data("chu_dap", {"text": "ĐỪNG ĐỂ BÔNG RỤNG HẾT SẠCH TRƠN NHÉ BÀ CON"})
        self.assertLessEqual(len(d["text"]), 28)
        self.assertEqual(d["text"], d["text"].strip())


class MoTaKhoi(unittest.TestCase):
    def test_du_cac_loai_va_khop_registry(self):
        m = CT.mo_ta_khoi()
        for k, v in m.items():
            self.assertTrue(v["mo_ta"] and v["du_lieu"] and v["toi_da"] and v["nhom"], k)
        ts = (GOC / "remotion" / "src" / "hub" / "Blocks.tsx").read_text(encoding="utf-8")
        reg = ts[ts.index("export const REGISTRY"):ts.index("export const Blocks")]
        reg = reg[reg.index("= {"):]
        co = set(re.findall(r"\b([a-z_]+): [A-Z]\w+", reg))
        self.assertEqual(co, set(m), set(m) ^ co)
        self.assertGreaterEqual(len(CT.KHOI_CHU_LON), 5)


class KhungTron(unittest.TestCase):
    def test_tron_va_khong_tron(self):
        doan = [{"t0": 0, "t1": 3.0, "bo_cuc": "day"}, {"t0": 3.0, "t1": 7.0, "bo_cuc": "chia_ngang"},
                {"t0": 7.0, "t1": 8.0, "bo_cuc": "day"}, {"t0": 8.0, "t1": 11.0, "bo_cuc": "day_zoom"}, {"t0": 11.0, "t1": 14.0, "bo_cuc": "day"}]
        bl = [{"loai": "hook_dap", "f0": 2, "f1": 60, "data": {}}, {"loai": "chu_so", "f0": 8 * 30, "f1": 9 * 30, "data": {}},
              {"loai": "lower_third", "f0": 11 * 30, "f1": 14 * 30, "data": {}}]
        kt = CT.khung_tron(doan, bl)
        # 0–3: hook phủ 1.9 s / 3 = 63% → không trơ; 3–7: chia_ngang → bỏ; 7–8: dưới 1.2 s → bỏ;
        # 8–11: chữ số phủ 1/3 = 33% < 40% → trơ; 11–14: chỉ có lower_third (không phải khối nổi bật) → trơ
        self.assertEqual(kt, [[8.0, 11.0], [11.0, 14.0]])


class PhuDe(unittest.TestCase):
    def test_cau_hinh_mac_dinh_va_ep_kieu(self):
        self.assertEqual(PD.cau_hinh({}), {"bat": True, "co": 44, "y": 1500, "tu_moi_dong": [2, 5]})
        self.assertEqual(PD.cau_hinh(None)["co"], 44)
        c = PD.cau_hinh({"phu_de": {"bat": False, "co": "50", "y": 99999, "tu_moi_dong": [3, 4]}})
        self.assertEqual((c["bat"], c["co"], c["y"], c["tu_moi_dong"]), (False, 50, 1700, [3, 4]))
        self.assertEqual(PD.cau_hinh({"phu_de": {"tu_moi_dong": "rac", "co": "abc"}})["tu_moi_dong"], [2, 5])

    def test_cum_ngan_2_den_5_tu_theo_dau_cau(self):
        cum = PD.cat_cum(PD._tu_dem("Khoan đã, đừng đổ nguyên chai nhé các bác ơi, nó phí lắm."), 2, 5)
        self.assertTrue(all(1 <= len(c.split()) <= 5 for c in cum), cum)
        self.assertTrue(cum[0].endswith("đã,") or cum[0].endswith(","), cum)         # ngắt ở dấu phẩy trước
        self.assertEqual(" ".join(cum), "Khoan đã, đừng đổ nguyên chai nhé các bác ơi, nó phí lắm.")

    def test_khong_cat_ten_rieng_va_so(self):
        cum = PD.cat_cum(PD._tu_dem("Chai Bọ Trĩ Top One chỉ có hai trăm bốn mươi mi li lít nước thôi nhé"), 2, 5)
        j = "|".join(cum)
        self.assertIn("Bọ Trĩ Top One", j)
        self.assertTrue(any("hai trăm bốn mươi" in c for c in cum), cum)
        cum2 = PD.cat_cum(PD._tu_dem("Phuy 200 lít cần 240 ml thuốc cho mỗi lần phun nhé bà con"), 2, 5)
        self.assertTrue(any("240 ml" in c for c in cum2), cum2)

    def test_chia_dong_gan_moc_va_ngan(self):
        text = "Chai Bọ Trĩ Top One chỉ có hai trăm bốn mươi mi li lít, đừng đổ nguyên chai nhé các bác ơi."
        toks = [t for t in text.split()]
        words = [{"w": t, "s": i * 0.4, "e": i * 0.4 + 0.35} for i, t in enumerate(toks)]
        lines, by_ai = PD.chia_dong(text, None, words)
        self.assertFalse(by_ai)
        self.assertTrue(all(len(l["words"]) <= 5 for l in lines))
        self.assertEqual(sum(len(l["words"]) for l in lines), len(toks))
        self.assertTrue(all(a["f1"] <= b["f1"] and a["f0"] < b["f0"] for a, b in zip(lines, lines[1:])))
        # dòng AI dài 8 từ cũng bị chia ngắn
        ai = [" ".join(toks[:8]), " ".join(toks[8:])]
        l2, by2 = PD.chia_dong(text, ai, words)
        self.assertTrue(by2); self.assertTrue(all(len(l["words"]) <= 5 for l in l2))
        l3, _ = PD.chia_dong("Đừng đổ nguyên chai nhé các bác ơi, nó phí lắm đấy", None, [{"w": t, "s": i * 0.4, "e": i * 0.4 + 0.35} for i, t in enumerate("Đừng đổ nguyên chai nhé các bác ơi, nó phí lắm đấy".split())], (), 3, 4)
        self.assertTrue(all(len(l["words"]) <= 4 for l in l3))

    def test_an_phu_de_khi_khoi_dang_noi_cung_chu(self):
        ln = [{"text": "đừng để bông rụng", "f0": 60, "f1": 100, "words": [{"w": w, "f0": 60, "f1": 70} for w in "đừng để bông rụng".split()]},
              {"text": "bà con nhớ nhé", "f0": 60, "f1": 100, "words": [{"w": w, "f0": 60, "f1": 70} for w in "bà con nhớ nhé".split()]},
              {"text": "đừng để bông rụng", "f0": 300, "f1": 340, "words": [{"w": w, "f0": 300, "f1": 310} for w in "đừng để bông rụng".split()]}]
        bl = [{"loai": "chu_tang", "f0": 50, "f1": 120, "data": {"text": "ĐỪNG ĐỂ BÔNG RỤNG"}}]
        r = PD.loc_phu_de(ln, bl)
        self.assertEqual([x["text"] for x in r], ["bà con nhớ nhé", "đừng để bông rụng"])       # dòng thứ 3 ngoài thời gian khối → còn


class NeNhan(unittest.TestCase):
    def test_khoi_co_dinh_khong_bi_doi(self):
        bl = [{"loai": "chu_dap", "f0": 0, "f1": 90, "data": {}, "top": 720, "co_dinh": True}]
        doan = [{"t0": 0, "t1": 3, "bo_cuc": "day", "nhan": [0.1, 0.2, 0.9, 0.9]}]
        self.assertEqual(ne_nhan.dat_khoi(bl, doan), 0)
        self.assertEqual(bl[0]["top"], 720)


if __name__ == "__main__":
    unittest.main()
