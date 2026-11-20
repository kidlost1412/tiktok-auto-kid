"""Thử xoay cảnh theo tổng số lần đã dùng (chống 1 cảnh chiếm quá nửa số video ở kho nhỏ). Không gọi AI/mạng.
Chạy: python -m unittest discover -s xuong-video/tests   (XUONG_DATA = thư mục tạm)."""
import datetime, os, random, sys, tempfile, unittest
from collections import Counter
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="xv-xoay-")
os.environ.setdefault("XUONG_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import dao_dien as DD  # noqa: E402

VAI = ["chai_ro", "phun", "vuon", "re", "ket_qua", "van_de", "pha_rot"]
CAU = ["Chai này pha rất dễ", "Phun lên lá vườn buổi sáng", "Rễ trắng ra nhiều", "Vườn xanh tốt hơn", "Kết quả thấy rõ sau một tuần",
       "Đọc nhãn thành phần trước khi mua", "Bà con pha đúng liều", "Đặt chai trong giỏ hàng ngay"]
LAY = ["khung_mo", "khung_nho", "chia_doi", "khung_mo", "khung_nho", "chia_ngang", "khung_mo", "khung_nho"]


def kho_gia(n=44, so_chai=6):
    """n cảnh, so_chai cảnh đầu là chai; cảnh 0 là cảnh 'đẹp nhất' (điểm máy 5) để thử việc cảnh hơn hẳn vẫn hay thắng."""
    out = []
    for i in range(n):
        vai = ["chai_ro"] if i < so_chai else [VAI[1 + i % (len(VAI) - 1)]]
        out.append({"id": f"{i:04d}", "file": f"f{i}.mp4", "tu": 0.0, "den": 4.0, "dai": 4.0, "dep": [0.5, 3.5], "vai_tro": vai,
                    "mo_ta": f"cảnh {vai[0]} {i}", "soat": {"dep": 5 if i == 0 else 3, "mat": 0, "chu_muc": 0}})
    return out


def mo_phong(hub, shots, so_video=30, seed=5, ma="t1", moi_ngay=3, dau=None):
    """Mỗi video: chọn ứng viên thật (chon_ung_vien) → đạo diễn giả nhận ứng viên ĐẦU chưa dùng → segs_tu_bang thật (gồm lấp chỗ trống + ép chốt chai) → ghi sổ.
    → danh sách id cảnh chính của từng video."""
    rng = random.Random(seed); dau = dau or datetime.date(2026, 11, 1); vids = []
    for v in range(so_video):
        ngay = dau + datetime.timedelta(days=v // moi_ngay)
        sents = [{"text": CAU[k % len(CAU)], "s": k * 2.5, "e": k * 2.5 + 2.3} for k in range(8)]
        per, chon, boi = DD.chon_ung_vien(ma, sents, [""] * 8, shots, rng, hub=hub, today=ngay)
        da, doan = set(), []
        for k, ids in enumerate(per):
            ch = next((i for i in ids if i not in da), ids[0])
            da.add(ch); doan.append({"cau": k, "canh": [{"id": ch, "bo_cuc": LAY[k]}]})
        edl = {"doan": doan, "_boi": {"met": {i: x for i, x in boi["met"].items() if x > 0}, "mo": boi["mo"], "chot": boi["chot"], "anh_em": boi["anh_em"]}}
        segs, _ = DD.segs_tu_bang(edl, sents, 20.3, shots)
        DD.ghi_lich_su_canh(ma, segs, hub=hub, ngay=ngay)
        vids.append(DD.id_canh_chinh(segs))
    return vids


def kho_sao(n=44):
    """3 cảnh 'ngôi sao': điểm máy 5 và mô tả khớp mọi câu → nếu không có phạt dùng-trọn-đời thì video nào cũng lấy cả 3."""
    s = kho_gia(n)
    for i in (0, 1, 2):
        s[i]["mo_ta"] += " " + " ".join(CAU); s[i]["soat"]["dep"] = 5
    return s


def thong_ke(vids):
    dung = Counter(i for v in vids for i in set(v))          # số VIDEO có cảnh đó
    return max(dung.values()) / len(vids), len(dung)


class XoayCanhTest(unittest.TestCase):
    def setUp(self):
        self.hub = Path(tempfile.mkdtemp(prefix="hub-", dir=TMP))

    def test_kho_nho_khong_canh_nao_qua_nua_video(self):
        shots = kho_sao(44)
        vids = mo_phong(self.hub, shots, so_video=36)
        ty_max, so_canh = thong_ke(vids)
        self.assertLessEqual(ty_max, 0.42, f"cảnh dùng nhiều nhất chiếm {ty_max:.0%} số video")
        self.assertGreaterEqual(so_canh, 0.8 * len(shots), f"chỉ dùng {so_canh}/{len(shots)} cảnh")

    def test_dem_tron_doi_tinh_ca_phu_va_bo_id_la(self):
        ls = [{"ngay": None, "ids": ["a", "b"], "phu": []}, {"ngay": datetime.date(2026, 1, 1), "ids": ["a", "gone"], "phu": ["b"]}]
        self.assertEqual(DD.dem_dung_tron_doi(ls), {"a": 2, "b": 2, "gone": 1})

    def test_kho_lon_canh_chua_dung_thang_canh_dung_nhieu(self):
        shots = kho_gia(120)
        for s in shots:                                       # mọi cảnh cùng độ liên quan
            s["vai_tro"] = ["vuon"]; s["soat"]["dep"] = 3; s["mo_ta"] = "vườn"
        shots[0]["vai_tro"] = shots[1]["vai_tro"] = ["chai_ro"]
        (self.hub / "lich-su").mkdir()
        old = datetime.date(2026, 6, 1)                       # dùng cảnh 0010 đã 15 lần nhưng cách đây lâu (mệt ngắn hạn = 0)
        for _ in range(15):
            DD.ghi_lich_su_canh("t1", [{"shot": {"id": "0010"}}], hub=self.hub, ngay=old)
        met = DD.boi_canh("t1", hub=self.hub, today=datetime.date(2026, 11, 1))["met"]
        self.assertGreater(met["0010"], 3.5)
        self.assertNotIn("0011", met)
        rng = random.Random(1); thang = 0
        for _ in range(40):
            per, _c, _b = DD.chon_ung_vien("t1", [{"text": "Vườn xanh tốt", "s": 0, "e": 2}] * 2, ["", ""], shots, rng, hub=self.hub, today=datetime.date(2026, 11, 1))
            thang += "0010" not in per[0]
        self.assertGreaterEqual(thang, 36)                    # cảnh đã dùng 15 lần gần như không còn vào danh sách


if __name__ == "__main__":
    unittest.main()
