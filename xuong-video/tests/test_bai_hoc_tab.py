"""Tab "Gu & bài học": bài học theo từng sản phẩm + tóm tắt lỗi máy (server), và bài học đi vào đề bài biên kịch. KHÔNG gọi AI."""
import json, os, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
GOC = Path(__file__).resolve().parents[1]
for p in (str(GOC / "app"), str(GOC / "engine")):
    if p not in sys.path:
        sys.path.insert(0, p)
import server  # noqa: E402
import viet_loi as vl  # noqa: E402
import dao_dien  # noqa: E402


class BaiHocTab(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bh-"))
        self.ls = self.tmp / "lich-su"; self.ls.mkdir()
        (self.tmp / "san-pham" / "sp1").mkdir(parents=True)
        (self.tmp / "san-pham" / "sp1" / "san-pham.json").write_text(json.dumps({"ten_goi": "Phân Một"}), encoding="utf-8")
        self.cu = (server.HUB, server.LS, vl.HUB, dao_dien.HUB)
        server.HUB = vl.HUB = dao_dien.HUB = self.tmp; server.LS = self.ls

    def tearDown(self):
        server.HUB, server.LS, vl.HUB, dao_dien.HUB = self.cu

    def test_bai_hoc_theo_san_pham(self):
        (self.ls / "bai-hoc-sp1.txt").write_text("- cũ\n- mới\n", encoding="utf-8")
        (self.ls / "bai-hoc-sp2.txt").write_text("- khác\n", encoding="utf-8")         # không có hồ sơ → hiện mã
        (self.ls / "bai-hoc-sp1.txt.bak").write_text("- bản lưu\n", encoding="utf-8")   # .bak và bai-hoc-cu không hiện
        (self.ls / "bai-hoc-cu.txt").write_text("- rất cũ\n", encoding="utf-8")
        ds = {x["ma"]: x for x in server.bai_hoc_theo_sp()}
        self.assertEqual(set(ds), {"sp1", "sp2"})
        self.assertEqual(ds["sp1"]["ten"], "Phân Một"); self.assertEqual(ds["sp2"]["ten"], "sp2")
        self.assertEqual(ds["sp1"]["dong"], ["- mới", "- cũ"])       # dòng mới nhất lên đầu
        self.assertRegex(ds["sp1"]["sua_luc"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")

    def test_loi_may_tom_tat(self):
        self.assertEqual(server.loi_may_tom_tat(), {"tong": 0, "nhom": []})           # chưa có file
        dong = [{"luc": f"2026-11-1{i}T10:00:00", "video": f"v{i}", "muc": "vung_an_toan", "chi_tiet": f"lỗi {i}"} for i in range(5)]
        dong.append({"luc": "2026-11-10T10:00:00", "video": "vx", "muc": "hinh_sach", "chi_tiet": "dính chữ"})
        (self.ls / "loi-may.jsonl").write_text("\n".join(json.dumps(x) for x in dong) + "\nhỏng{\n", encoding="utf-8")
        r = server.loi_may_tom_tat()
        self.assertEqual(r["tong"], 6)
        self.assertEqual([g["muc"] for g in r["nhom"]], ["vung_an_toan", "hinh_sach"])  # nhiều nhất trước
        g = r["nhom"][0]
        self.assertEqual((g["ten"], g["so"]), ("vùng an toàn", 5))
        self.assertEqual([e["video"] for e in g["gan_day"]], ["v4", "v3", "v2"])        # 3 ví dụ mới nhất, mới trước

    def test_bai_hoc_vao_de_bai_bien_kich(self):
        chung = "- Luôn chốt bằng chai chính, nhắc đúng quà thật."
        (self.ls / "bai-hoc.txt").write_text(chung + "\n- Tránh lặp góc máy cận.\n", encoding="utf-8")
        (self.ls / "bai-hoc-sp1.txt").write_text("".join(f"- Nhắc {w} {z}.\n" for w, z in zip(
            "giá liều tên quà cây đất nước phân rễ lá thân hoa trái hạt".split(), "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron".split())), encoding="utf-8")
        sp = {"ma": "sp1", "ten_goi": "Phân Một", "ten_ngan": "Phân Một"}
        so_gu = vl.ctx_bien_kich(sp, 1, ["g"], [], [], truc=[{"goc": "g", "mo": "m", "than": "t", "chot": "c", "vai": "v"}], sp_day=sp)["so_gu"]
        self.assertIn("BÀI HỌC GIÁM KHẢO", so_gu)
        self.assertIn("xi.", so_gu); self.assertNotIn("alpha", so_gu)                 # chỉ 10 dòng mới nhất
        self.assertLessEqual(so_gu.count("\n- "), 10)
        self.assertNotIn("góc máy", so_gu)                                              # dòng về cảnh/dựng bị lọc
        (self.ls / "so-gu.md").write_text("- Gu của chủ", encoding="utf-8")
        self.assertIn("Gu của chủ", vl.ctx_bien_kich(sp, 1, ["g"], [], [], truc=[{"goc": "g", "mo": "m", "than": "t", "chot": "c", "vai": "v"}], sp_day=sp)["so_gu"])

    def test_khong_co_bai_hoc_thi_khong_them_khoi(self):
        sp = {"ma": "sp1", "ten_goi": "Phân Một"}
        self.assertEqual(vl.bai_hoc_cho_loi("sp1"), "")


if __name__ == "__main__":
    unittest.main()
