"""Thử đa dạng hoá video: mệt cảnh (chống lặp cảnh), xoay công thức, trần/sàn bố cục, kiểm khung nháy, tờ ảnh ứng viên.
Không gọi AI/mạng; ffmpeg chỉ dùng trên clip tổng hợp bé xíu (bỏ qua nếu máy không có ffmpeg).
Chạy: python -m unittest discover -s xuong-video/tests   (XUONG_DATA = thư mục tạm)."""
import datetime, json, os, random, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="xv-dadang-")
os.environ.setdefault("XUONG_DATA", TMP)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import bo_cuc as BC  # noqa: E402
import cong_thuc as CT  # noqa: E402
import dao_dien as DD  # noqa: E402
import dung  # noqa: E402

VAI = ["chai_ro"] * 10 + ["phun"] * 10 + ["vuon"] * 10 + ["re"] * 5 + ["ket_qua"] * 5
CAU = ["Chai này pha rất dễ", "Phun lên lá vườn buổi sáng", "Rễ trắng ra nhiều", "Vườn xanh tốt hơn", "Kết quả thấy rõ sau một tuần",
       "Đọc nhãn thành phần trước khi mua", "Bà con pha đúng liều", "Đặt chai trong giỏ hàng ngay"]


def kho_gia(n=40):
    out = []
    for i in range(n):
        out.append({"id": f"{i + 1:03d}", "file": f"f{i}.mp4", "tu": 0.0, "den": 4.0, "dai": 4.0, "dep": [0.5, 3.5], "vai_tro": [VAI[i % len(VAI)]],
                    "mo_ta": f"cảnh {VAI[i % len(VAI)]} {i}", "soat": {"dep": 3 + i % 3, "mat": 0, "chu_muc": 0}})
    return out


def cau_gia(n=8):
    return [{"text": CAU[k % len(CAU)], "s": k * 2.5, "e": k * 2.5 + 2.3} for k in range(n)]


LAY_NANG_HOP = ["khung_mo", "khung_mo", "khung_nho", "chia_doi", "khung_mo", "khung_nho", "chia_ngang", "khung_mo"]   # đạo diễn nghiện khung trên nền mờ


def mo_phong(hub, so_video=12, so_canh=40, seed=3):
    """Cặp (kịch bản j0, anh em j1) × so_video/2; đạo diễn giả luôn nhận ứng viên ĐẦU TIÊN chưa dùng. → danh sách segs mỗi video."""
    rng = random.Random(seed); shots = kho_gia(so_canh); vids, lo = [], []
    for _ in range(so_video // 2):
        anh = None
        for j in (0, 1):
            sents = cau_gia(8)
            per, chon, boi = DD.chon_ung_vien("t1", sents, [""] * 8, shots, rng, tranh=lo, anh_em=anh, hub=hub)
            da, doan = set(), []
            for k, ids in enumerate(per):
                ch = next((i for i in ids if i not in da), ids[0])
                da.add(ch); doan.append({"cau": k, "canh": [{"id": ch, "bo_cuc": LAY_NANG_HOP[k]}]})
            edl = {"doan": doan, "_boi": {"met": {i: v for i, v in boi["met"].items() if v > 0}, "mo": boi["mo"], "chot": boi["chot"], "anh_em": boi["anh_em"]}}
            segs, _ = DD.segs_tu_bang(edl, sents, 20.3, shots)
            lo += DD.id_canh_chinh(segs) + DD.id_canh_phu(segs)
            DD.ghi_lich_su_canh("t1", segs, hub=hub)
            vids.append(segs)
            if j == 0:
                anh = DD.id_canh_chinh(segs)
    return vids


class MetCanhTest(unittest.TestCase):
    def setUp(self):
        self.hub = Path(tempfile.mkdtemp(prefix="hub-", dir=TMP))

    def test_so_khong_ngay_la_cu_so_co_ngay_theo_trong_so(self):
        ls = self.hub / "lich-su"; ls.mkdir()
        (ls / "canh-da-dung-a.txt").write_text("001 002\n001 003\n010\n011\n012\n013\n", encoding="utf-8")   # 2 dòng cũ + 4 dòng trùng 4 bản ghi có ngày bên dưới
        h = datetime.date(2026, 11, 14)
        for ngay, ids in ((h, ["010"]), (h - datetime.timedelta(days=2), ["011"]), (h - datetime.timedelta(days=6), ["012"]), (h - datetime.timedelta(days=9), ["013"])):
            DD.ghi_lich_su_canh("a", [{"shot": {"id": i}, "phu_shots": [{"id": "099"}]} for i in ids], hub=self.hub, ngay=ngay)
        met = DD.tinh_met(DD.doc_lich_su("a", self.hub), today=h)
        self.assertEqual(met["001"], 2)                                        # sổ không ngày: ×1 mỗi video
        self.assertEqual((met["010"], met["011"], met["012"]), (3, 2, 1))      # hôm nay ×3, ≤3 ngày ×2, ≤7 ngày ×1
        self.assertNotIn("013", met)                                           # quá 7 ngày không tính
        self.assertEqual(met["099"], 3 + 2 + 1)                                # ô phụ cũng tính
        self.assertEqual(DD.tinh_met([], today=h, anh_em=["005"])["005"], DD.PHAT_ANH_EM)
        self.assertEqual(DD.tinh_met([], today=h, hom_nay=["007", "007"])["007"], 6)

    def test_ung_vien_khong_chon_cung_cuc_cung_chu(self):
        shots = kho_gia(40); met = {s["id"]: 10 for s in shots[:12]}           # 12 cảnh mệt nặng
        per, chon = DD.ung_vien(cau_gia(8), [""] * 8, shots, random.Random(1), met=met)
        self.assertTrue(all(len(p) <= DD.TOI_DA_MOI_CAU for p in per))
        self.assertLess(len(chon), 0.61 * 40)                                  # kho nhỏ: ≤ 60% kho cho cả video
        self.assertFalse({s["id"] for s in shots[:12]} & set(chon) and len({s["id"] for s in shots[:12]} & set(chon)) > 3)   # cảnh mệt nhất gần như bị loại

    def test_mo_chot_khong_lap_6_video_gan(self):
        shots = kho_gia(40); mo, chot = {"001", "002"}, {"011"}
        per, _ = DD.ung_vien(cau_gia(8), [""] * 8, shots, random.Random(2), met={}, mo_gan=mo, chot_gan=chot)
        self.assertFalse(mo & set(per[0])); self.assertFalse(chot & set(per[-1]))

    def test_vai_tro_viet_co_dau_duoc_cong_diem(self):
        chai = {"id": "1", "vai_tro": ["chai_ro"], "mo_ta": "", "soat": {"dep": 3}}; vuon = {"id": "2", "vai_tro": ["vuon"], "mo_ta": "", "soat": {"dep": 3}}
        self.assertGreater(DD._diem_lien_quan(chai, "Cầm chai lên đọc nhãn", ""), DD._diem_lien_quan(vuon, "Cầm chai lên đọc nhãn", ""))
        self.assertGreater(DD._diem_lien_quan(vuon, "Ra vườn xem lá", ""), DD._diem_lien_quan(chai, "Ra vườn xem lá", ""))

    def test_kho_chung_them_rong_hon_khi_kho_rieng_nho(self):
        chung = [dict(s, id=f"V-{i}", kho_them="video-vuon") for i, s in enumerate(kho_gia(30))]
        _, chon, _ = DD.chon_ung_vien("t1", cau_gia(8), [""] * 8, kho_gia(40), random.Random(1), chung=chung, hub=self.hub)
        n_v = sum(1 for i in chon if str(i).startswith("V-"))
        _, chon2, _ = DD.chon_ung_vien("t1", cau_gia(8), [""] * 8, kho_gia(40) + [dict(s, id=f"{500 + i}", file=f"g{i}.mp4") for i, s in enumerate(kho_gia(60))],
                                       random.Random(1), chung=chung, hub=self.hub)
        self.assertGreater(n_v, sum(1 for i in chon2 if str(i).startswith("V-")))
        self.assertGreater(n_v, 8)

    def test_mo_phong_12_video_kho_40_canh(self):
        vids = mo_phong(self.hub)
        dem = {}
        for segs in vids:
            for i in set(DD.id_canh_chinh(segs) + DD.id_canh_phu(segs)):
                dem[i] = dem.get(i, 0) + 1
        self.assertLessEqual(max(dem.values()), int(0.35 * 12 + 0.999), dem)          # không cảnh nào ở > ~35% số video
        for a, b in zip(vids[::2], vids[1::2]):                                        # anh em cùng lời
            A, B = DD.id_canh_chinh(a), DD.id_canh_chinh(b)
            self.assertLessEqual(len(set(A) & set(B)), int(0.30 * len(B) + 1e-9), (A, B))
            self.assertNotEqual(A[0], B[0])
        for segs in vids:
            self.assertEqual(len(DD.id_canh_chinh(segs)), len(set(DD.id_canh_chinh(segs))))   # không lặp cảnh trong 1 video
        ls = DD.doc_lich_su("t1", self.hub)
        self.assertEqual(len(ls), 12)
        for k in range(6, 12):                                                         # cảnh mở/chốt khác mở/chốt của (tối đa) 6 video trước
            truoc = ls[max(0, k - 6):k]
            self.assertNotIn(vids[k][0]["shot"]["id"], {r["ids"][0] for r in truoc})
            self.assertNotIn(vids[k][-1]["shot"]["id"], {r["ids"][-1] for r in truoc})

    def test_to_ung_vien_o_toi_thieu_180_va_tach_2_to(self):
        old = DD.HUB; DD.HUB = self.hub
        try:
            from PIL import Image
            d = self.hub / "san-pham" / "t1" / "_khung"; d.mkdir(parents=True)
            ids = [f"{i:03d}" for i in range(50)]
            for i in ids[:-1]:                                                       # thiếu đúng 1 file ảnh → ô xám, không sập
                Image.new("RGB", (270, 480), "red").save(d / f"{i}.jpg")
            outs = DD.to_ung_vien("t1", ids, self.hub / "uv.jpg")
            self.assertEqual(len(outs), 2)
            with Image.open(outs[0]) as im:
                w, h = im.size
            self.assertGreaterEqual(w // 8, 180); self.assertLessEqual(max(w, h), 1568)
            self.assertEqual(DD.to_ung_vien("t1", [], self.hub / "rong.jpg"), [])     # review #21: rỗng không sập
        finally:
            DD.HUB = old

    def test_chon_phu_kho_trong_khong_sap(self):
        main = kho_gia(1)[0]
        ra = BC.chon_phu({"shot": main, "dur": 2.0, "src_start": 0.0}, 1, [main], random.Random(1), set())
        self.assertEqual(len(ra), 1)


class CongThucTest(unittest.TestCase):
    def _sig(self, ct, i):
        return f"{ct}|hook_{i}|to_dan|the_qua|vua"

    def test_tu_do_ton_trong_khi_khong_ap_dao_va_doi_khi_ap_dao(self):
        sigs = {self._sig("ke_chuyen", i) for i in range(5)}
        st = CT.chuan_hoa({"cong_thuc": "ke_chuyen"}, random.Random(1), set(sigs), tu_do=True, dang="phep_tinh")
        self.assertIn(st["cong_thuc"], CT.CT_HOP["phep_tinh"])                     # số-heavy → con_so/danh_sach/so_sanh
        sigs2 = {self._sig("ke_chuyen", 0), self._sig("ke_chuyen", 1)}              # ke_chuyen = 2 ≤ min(0) + 1? không (2 > 1) → đổi
        self.assertNotEqual(CT.chuan_hoa({"cong_thuc": "ke_chuyen"}, random.Random(1), set(sigs2), tu_do=True)["cong_thuc"], "ke_chuyen")
        sigs3 = {self._sig("ke_chuyen", 0)}                                        # 1 ≤ 0 + 1 → giữ lựa chọn của đạo diễn
        self.assertEqual(CT.chuan_hoa({"cong_thuc": "ke_chuyen"}, random.Random(1), set(sigs3), tu_do=True)["cong_thuc"], "ke_chuyen")

    def test_chu_ky_luon_chong_trung_ke_ca_tu_do(self):
        used = set()
        a = CT.chuan_hoa({"cong_thuc": "soi_dong"}, random.Random(5), used, tu_do=True)
        b = CT.chuan_hoa({"cong_thuc": "soi_dong"}, random.Random(5), used, tu_do=True)
        sig = lambda s: CT.chu_ky({"cong_thuc": s["cong_thuc"], "hook": s["ep_mo"], "phu_de": s["phu_de"], "chot": s["ep_chot"], "sfx": s["sfx"]})
        self.assertEqual(len(used), 2); self.assertNotEqual(sig(a), sig(b))

    def test_xoay_vong_nhieu_video_khong_cong_thuc_nao_ap_dao(self):
        used, rng, dem = set(), random.Random(9), {}
        for _ in range(24):                                                        # đạo diễn lúc nào cũng đòi ke_chuyen
            k = CT.chuan_hoa({"cong_thuc": "ke_chuyen"}, rng, used, tu_do=True)["cong_thuc"]; dem[k] = dem.get(k, 0) + 1
        self.assertLessEqual(max(dem.values()), 24 * 0.35)
        self.assertGreaterEqual(len(dem), 5)

    def test_ds_cong_thuc_cho_dao_dien_bo_2_nhieu_nhat(self):
        used = {self._sig("ke_chuyen", i) for i in range(4)} | {self._sig("soi_dong", i) for i in range(3)} | {self._sig("tvc_sang", 0)}
        ds = CT.ct_cho_dao_dien(used)
        self.assertNotIn("ke_chuyen", ds); self.assertNotIn("soi_dong", ds); self.assertEqual(len(ds), len(CT.RECIPES) - 2)
        self.assertEqual(CT.ct_cho_dao_dien(set()), list(CT.RECIPES))              # chưa lệch → không bỏ gì


class BoCucTest(unittest.TestCase):
    def _segs(self, n, nguoi=()):
        shots = kho_gia(n + 10)
        for i in nguoi:
            shots[i]["soat"]["mat"] = 2
        return [{"shot": shots[i], "dur": 2.4, "src_start": 0.0, "phu_shots": [], "cau": i} for i in range(n)], shots

    def _kiem(self, L, segs):
        n = len(L)
        self.assertLessEqual(sum(k in BC.HOP_MO for k in L), int(0.45 * n + 1e-9), L)
        self.assertGreaterEqual(sum(k in BC.TOAN for k in L), -int(-0.35 * n // 1), L)
        self.assertFalse(any(L[i] == L[i - 1] == L[i - 2] for i in range(2, n)), L)
        for sg, k in zip(segs, L):
            if BC._nguoi_noi(sg["shot"]):
                self.assertNotIn(k, ("day", "day_zoom", "pip_troi", "pip_giua"))
            self.assertGreaterEqual(len(sg.get("phu_shots", [])), BC.SO_PHU[k])

    def test_tran_san_bat_ke_dao_dien_chon_gi(self):
        for ban_dau in (["khung_mo"] * 10, ["khung_nho", "chia_doi"] * 5, ["day"] * 10, ["day_zoom", "khung_mo", "khung_mo"] * 3 + ["khung_mo"]):
            segs, shots = self._segs(10, nguoi=(3, 4))
            pool = shots[10:]
            lay = lambda sg, n: [s for s in pool if s["file"] != sg["shot"]["file"]][:n]
            L, ghi = BC.ep_bo_cuc(segs, ban_dau, random.Random(1), lay)
            self._kiem(L, segs)

    def test_chay_lai_khong_doi_them(self):
        segs, shots = self._segs(10)
        lay = lambda sg, n: [s for s in shots[10:] if s["file"] != sg["shot"]["file"]][:n]
        L, _ = BC.ep_bo_cuc(segs, ["khung_mo"] * 10, random.Random(1), lay)
        L2, g2 = BC.ep_bo_cuc(segs, L, random.Random(99), lay)
        self.assertEqual(L, L2); self.assertEqual(g2, [])

    def test_punch_in_khong_day_nhan_ra_ngoai_khung(self):
        nhan = [0.3, 0.2, 0.7, 0.8]
        rng = random.Random(4)
        for _ in range(200):
            o = BC.tuy_chon(rng, {"soat": {"nhan": nhan}})
            p, ax, ay = o["punch"], o["ax"], o["ay"]
            if p > 0:                                       # khung cắt: [ax·p, ax·p + (1−p)] theo từng trục; nhãn phải nằm gọn trong
                self.assertLessEqual(ax * p, nhan[0]); self.assertGreaterEqual(ax * p + 1 - p, nhan[2])
                self.assertLessEqual(ay * p, nhan[1]); self.assertGreaterEqual(ay * p + 1 - p, nhan[3])
            self.assertGreaterEqual(o["punch"], 0.0); self.assertLessEqual(o["punch"], 0.10)
        nb = BC.nhan_hieu_dung("day", {"punch": 0.1, "ax": 0.5, "ay": 0.5}, nhan)
        self.assertTrue(all(0 <= v <= 1 for v in nb))


@unittest.skipUnless(shutil.which("ffmpeg"), "không có ffmpeg")
class KiemChopTest(unittest.TestCase):
    def _clip(self, ten, chen=None):
        f = Path(TMP) / ten
        vf = "format=yuv420p" if chen is None else f"drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='eq(n,{chen})',format=yuv420p"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x406080:s=108x192:r=30:d=2", "-vf", vf, "-c:v", "libx264", str(f)], check=True)
        return f

    def test_bat_khung_trang_chen_gan_diem_cat(self):
        ra = dung.kiem_chop(self._clip("trang.mp4", chen=30), cuts=[1.0])
        self.assertTrue(any(x["loai"] == "trang" and abs(x["t"] - 1.0) < 0.1 for x in ra), ra)

    def test_clip_sach_khong_co(self):
        self.assertEqual(dung.kiem_chop(self._clip("sach.mp4"), cuts=[1.0]), [])

    def test_khung_trang_xa_diem_cat_khong_bao(self):
        self.assertEqual(dung.kiem_chop(self._clip("xa.mp4", chen=5), cuts=[1.5]), [])


@unittest.skipUnless(shutil.which("ffmpeg"), "không có ffmpeg")
class RenderThatTest(unittest.TestCase):
    """Dựng thật 4 đoạn tổng hợp (zoomin, đoạn ngắn <3×chuyển, ô phụ) → không khung nháy quanh điểm cắt."""

    def test_zoomin_va_pip_khong_nhay(self):
        kho = Path(TMP) / "kho"; kho.mkdir(exist_ok=True)
        mk = lambda ten, src: subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(kho / ten)], check=True)
        mk("a.mp4", "color=c=0xE0E0E0:s=540x960:r=30,drawbox=x=190:y=250:w=160:h=450:color=white:t=fill"); mk("b.mp4", "testsrc2=s=540x960:r=30")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "10", str(kho / "v.wav")], check=True)
        sh = lambda i, f, vt: {"id": f"{i:03d}", "file": f, "tu": 0.0, "den": 4.0, "dai": 4.0, "dep": [0.5, 3.0], "vai_tro": vt, "soat": {"dep": 4, "nhan": [0.35, 0.26, 0.65, 0.73] if vt == ["chai_ro"] else None}}
        S = [sh(1, "a.mp4", ["chai_ro"]), sh(2, "b.mp4", ["vuon"])]
        segs = [{"shot": S[i % 2], "src_start": 0.0, "dur": d, "bo_cuc": L, "phu_shots": [], "cau": i}
                for i, (d, L) in enumerate(zip([2.2, 0.7, 2.0, 2.0, 2.4], ["day", "day_zoom", "pip_troi", "khung_mo", "day"]))]
        plan = {"seed": 5, "phong_cach": {"chuyen_canh": "zoomin", "chuyen_dong": "dung", "mau": "tu_nhien", "nhip": "vua"}, "edl_segs": segs, "vmin": 8.5}
        out = Path(TMP) / "r.mp4"
        info = dung.render(plan, {"dur": 8.7, "audio": str(kho / "v.wav")}, S, str(kho), str(out))
        self.assertEqual(info["tds"][:3], [0.0, 0.0, 0.28])                                      # đoạn 0,7 s < 3×0,28 → cắt thẳng ở 2 mép
        self.assertEqual(dung.kiem_chop(out, cuts=info["cuts"]), [])


if __name__ == "__main__":
    unittest.main()
