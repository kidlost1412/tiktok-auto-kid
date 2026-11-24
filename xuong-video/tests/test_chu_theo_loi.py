"""Khung "chữ theo lời" (v10 Kid duyệt, gộp 23/11): số đọc thành chữ số, khối dẫn nhỏ + từ chính to, màu theo đoạn, chia ô ≤ 2, tiếng theo kiểu hiện.
Không gọi AI / ffmpeg."""
import os, random, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import chu_theo_loi as C   # noqa: E402
import bo_cuc as BC        # noqa: E402
import sfx as SFX          # noqa: E402
from dung import sentence_times   # noqa: E402

LOI = ("Một tháng phun bọ trĩ bốn lượt là bỏ ra hai ngày công, mà lứa trứng mới vẫn nở đều. Để vậy thêm một lứa là đọt dưa leo xoăn, "
       "bông rụng, nên nhiều vườn đã đổi qua Bọ Trĩ Top One. Lắc kỹ chai, pha hai trăm bốn mươi mi li cho phuy hai trăm lít rồi phun. Chai có ở giỏ hàng.")


def _sents(txt=LOI):
    ws, t = [], 0.0
    for w in txt.split():
        ws.append({"w": w, "s": t, "e": t + 0.25}); t += 0.3
    return sentence_times(txt, ws), t


class SoHoa(unittest.TestCase):
    def test_so_doc_thanh_chu_so(self):
        self.assertEqual(C.so_hoa("pha hai trăm bốn mươi mi li"), "pha 240ml")
        self.assertEqual(C.so_hoa("phuy hai trăm lít"), "phuy 200 lít")
        self.assertEqual(C.so_hoa("mười lăm ngày"), "15 ngày")
        self.assertEqual(C.so_hoa("năm nay ba người"), "năm nay ba người")      # chữ dễ nhầm đứng một mình giữ nguyên
        self.assertEqual(C.so_hoa("năm lít"), "5 lít")
        self.assertEqual(C.so_hoa("muốn đậm thì hai, ba nắp"), "muốn đậm thì 2-3 nắp")     # khoảng, không cộng thành 5
        self.assertEqual(C.so_hoa("pha bình mười sáu là đủ"), "pha bình 16L là đủ")
        self.assertEqual(C.so_hoa("cả chục nắp"), "cả chục nắp")
        self.assertEqual(C.so_hoa("hơn một triệu nhà vườn"), "hơn 1 triệu nhà vườn")
        self.assertEqual(C.so_hoa("mười lăm nghìn"), "15.000")
        self.assertEqual(C.so_hoa("sai thứ ba là"), "sai thứ 3 là")

    def test_hook_cau_dau_khong_phai_ten_hang(self):
        def h(t):
            ws = [{"w": w, "s": i * .3, "e": i * .3 + .25} for i, w in enumerate(t.split())]
            return C._chu_hook(sentence_times(t, ws))
        self.assertEqual(h("Ớt vàng lá, còi đọt, rụng bông."), "ỚT VÀNG LÁ")
        self.assertEqual(h("Cà phê bón đủ mà vẫn còi? Lỗi ở rễ."), "VẪN CÒI?")
        self.assertEqual(h("Hơn một triệu nhà vườn đã xài."), "1 TRIỆU NHÀ VƯỜN")
        self.assertIsNone(h("Ngoài tiệm một can là một can."))      # không có gì mạnh → tên hàng

    def test_khong_cat_giua_cum_so(self):
        ws = [{"w": w, "s": i * .3, "e": i * .3 + .25} for i, w in enumerate("Đạm cá Toàn Cầu một nắp pha bình mười sáu là đủ, muốn đậm thì hai, ba nắp.".split())]
        s = sentence_times(" ".join(w["w"] for w in ws), ws)
        L = C.tao_khoi(s, [], "ĐẠM CÁ TOÀN CẦU", 6.0, random.Random(1))
        keys = [k["key"] for k in L["khoi"]]
        self.assertIn("BÌNH 16L LÀ ĐỦ", keys)
        self.assertIn("2-3 NẮP", keys)


class TaoKhoi(unittest.TestCase):
    def setUp(self):
        s, t = _sents()
        self.L = C.tao_khoi(s, ["hai ngày công"], "BỌ TRĨ TOP ONE", t, random.Random(3), qua_txt="Mua 2 tặng 1")
        self.k = {x["key"]: x for x in self.L["khoi"]}

    def test_tu_chinh_va_dan(self):
        self.assertIn("4 LƯỢT", self.k)
        self.assertEqual(" ".join(d["w"] for d in self.k["4 LƯỢT"]["dan"]), "1 tháng phun bọ trĩ")
        self.assertIn("2 NGÀY CÔNG", self.k)
        self.assertIn("240ml", self.k)
        self.assertIn("GIỎ HÀNG", self.k)
        self.assertEqual(self.k["GIỎ HÀNG"]["icon"], "gio")

    def test_mau_theo_doan(self):
        self.assertEqual(self.k["4 LƯỢT"]["vai"], "warn")              # trước tên hàng = vấn đề
        self.assertEqual(self.k["BỌ TRĨ TOP ONE"]["vai"], "brand")
        self.assertEqual(self.k["240ml"]["vai"], "val")
        mau = C.BANG_MAU[self.L["bang"]]
        self.assertEqual(self.k["4 LƯỢT"]["mau"], mau["warn"])

    def test_cat_cung_xen_ke_va_hook(self):
        ks = self.L["khoi"]
        self.assertTrue(all(a["f1"] == b["f0"] for a, b in zip(ks, ks[1:])))
        self.assertEqual(self.L["hook"]["text"], "BỌ TRĨ")
        self.assertEqual(ks[0]["vt"], "duoi")                            # chữ khổng lồ chiếm phía trên
        self.assertGreaterEqual(sum(x["vt"] == "tren" for x in ks), 2)
        self.assertLessEqual(sum(bool(x.get("deco")) for x in ks), 2)

    def test_dong_qua_khi_loi_chua_nhac(self):
        self.assertEqual(self.L["qua"]["text"], "MUA 2 TẶNG 1")
        bl = C.lich_am(self.L)
        self.assertTrue(bl[0]["loai"].startswith("loi_hook_"))
        self.assertTrue(all(b["loai"].startswith("loi_") for b in bl))

    def test_tiếng_theo_kieu_hien(self):
        ctx = {"rng": random.Random(1), "ui": "tick"}
        self.assertEqual(SFX._khoi({"loai": "loi_slam", "f0": 30, "f1": 60, "vai": "warn"}, ctx)[0]["nhom"], ["dap", "tick"])
        self.assertEqual(SFX._khoi({"loai": "loi_slam", "f0": 30, "f1": 60, "vai": "brand"}, ctx)[0]["nhom"], ["roi_phep"])
        go = SFX._khoi({"loai": "loi_type", "f0": 30, "f1": 75, "vai": "val", "text": "PHUY 200 LÍT"}, ctx)
        self.assertGreaterEqual(len(go), 4)                               # gõ phím rải theo chữ cái, không phải 1 click
        self.assertTrue(all(x["nhom"] == ["go_phim"] for x in go))
        self.assertEqual(SFX._khoi({"loai": "loi_fade", "f0": 30, "f1": 60, "vai": "warn"}, ctx), [])


class ChiaOThua(unittest.TestCase):
    def test_toi_da_hai_o_va_aff_vao_khung_mo(self):
        segs = [{"dur": 1.5, "shot": {"loai": "canh"}} for _ in range(6)] + [{"dur": 2.6, "shot": {"loai": "nguoi_noi"}}]
        L = ["chia_doi", "luoi_4", "khung_nho", "pip_troi", "chia_3", "day", "day"]
        ghi = []
        BC._khung_loi(segs, L, ghi)
        self.assertLessEqual(sum(K not in BC.DON_O for K in L[:6]), 2)
        self.assertEqual(L[6], "khung_mo")

    def test_kieu_moi_giu_khung_va_cot_chay(self):
        aff = lambda f: {"loai": "nguoi_noi", "file": f, "tu": 0, "dai": 9}
        segs = [{"dur": 1.5, "shot": {"loai": "canh", "file": "c0"}}, {"dur": 4.0, "shot": aff("a1")}, {"dur": 1.2, "shot": {"loai": "canh", "file": "c2"}},
                {"dur": 3.0, "shot": aff("a3")}, {"dur": 2.0, "shot": aff("a4")}]
        kho = [dict(aff(f"p{j}"), vai_tro=["chai_ro"] if j % 2 else ["vuon"]) for j in range(30)] + [{"loai": "canh", "file": f"r{j}", "tu": 0, "dai": 9, "vai_tro": ["pha_rot"]} for j in range(10)]
        kho += [dict(aff("p1"), tu=3)]                     # cùng file khác đoạn: không được vào lần 2
        L, used = ["day", "khung_hien", "day", "khung_chay", "day"], set()      # đạo diễn chọn 2 kiểu đặc biệt
        rng = random.Random(0)
        BC._khung_loi(segs, L, [], None, rng, kho, used)
        self.assertEqual(L[1], "khung_hien")             # đạo diễn chọn → giữ
        self.assertEqual(L[3], "khung_chay")
        self.assertEqual(len(segs[1]["phu_shots"]), 2)
        self.assertTrue(all(p["file"] != "a1" for p in segs[1]["phu_shots"]))
        tl = segs[3]["phu_shots"]
        self.assertEqual(len(tl), sum(BC.so_o_chay("khung_chay", 3.3)))
        tat_ca = [p["file"] for p in segs[1]["phu_shots"] + tl]
        self.assertEqual(len(tat_ca), len(set(tat_ca)))     # không cảnh nào lặp trong video
        self.assertTrue(all(p.get("vai_tro") == ["chai_ro"] for p in tl[:10]))   # aff cầm hàng đi trước
        fc, t = BC.loc(1, "khung_hien", 4.0, 0, [1, 2], [3, 4, 5], "null", "null", BC.tuy_chon(random.Random(1)), segs[1]["shot"], segs[1]["phu_shots"])
        self.assertEqual(t, [1.2, 2.4])                   # thẻ hiện ở 30% và 60% đoạn
        self.assertIn("rotate=", ";".join(fc))

    def test_may_boc_kieu_khi_dao_dien_khong_chon(self):
        aff = lambda f: {"loai": "nguoi_noi", "file": f, "tu": 0, "dai": 9}
        kho = [dict(aff(f"p{j}"), vai_tro=["chai_ro"]) for j in range(30)]
        segs = [{"dur": 1.5, "shot": {"loai": "canh", "file": "c0"}}, {"dur": 3.2, "shot": aff("a1")}, {"dur": 1.2, "shot": {"loai": "canh", "file": "c2"}}]
        L = ["day"] * 3
        rng = random.Random(0); rng.random = lambda: 0.0
        BC._khung_loi(segs, L, [], None, rng, kho, set())
        self.assertIn(L[1], BC.DAC_BIET)
        self.assertGreaterEqual(len(segs[1]["phu_shots"]), BC.SO_PHU[L[1]])
        for K in BC.THE:                                   # filter dựng được, mọi thẻ dùng hết cảnh, mặt nạ đúng cỡ
            n = BC.so_phu_toi_da(K)
            fc, t = BC.loc(1, K, 3.2, 0, list(range(1, n + 1)), [n + 1, n + 2], "null", "null", BC.tuy_chon(random.Random(1)), segs[1]["shot"], kho[:n])
            g = ";".join(fc)
            self.assertEqual(sum(f"[s1_{k}]" in g for k in range(1, n + 1)), n)
            self.assertEqual(BC.mask_sizes(K, {})[1], BC.THE[K]["o"])
            self.assertEqual(len(t), n if K in ("hien_mat", "chong_the") else 0)
        self.assertGreaterEqual(BC.SO_PHU["xoay_quanh"], 5)      # Kid: thẻ xoay ít nhất 5
        self.assertNotIn(segs[1]["shot"]["file"], [p["file"] for p in segs[1]["phu_shots"]])

    def test_o_qua_o_chot_khong_bi_ha(self):
        sh = lambda f, **k: dict({"loai": "canh", "file": f, "id": f, "tu": 0, "dai": 9, "vai_tro": ["chai_ro"]}, **k)
        segs = [{"dur": 2.0, "shot": sh(f"c{i}"), "bo_cuc": "day", "phu_shots": []} for i in range(6)]
        for i in (1, 5):
            segs[i].update(bo_cuc="chia_ngang", phu_shots=[sh("Q-tc01-1" if i == 5 else "p1")])
        L, _ = BC.ep_bo_cuc(segs, [s["bo_cuc"] for s in segs], random.Random(0), khung="chu_theo_loi")
        self.assertEqual(L[5], "chia_ngang")

    def test_the_khong_che_nhan_chai(self):
        o = BC.o_hien({"soat": {"nhan": [0.0, 0.5, 0.4, 0.9]}})        # can ở dưới trái → không đặt thẻ dưới trái
        self.assertNotIn((36, 790, 400, 520), o[1:])


if __name__ == "__main__":
    unittest.main()
