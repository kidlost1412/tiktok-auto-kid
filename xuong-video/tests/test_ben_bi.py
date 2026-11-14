"""Độ bền của dây chuyền sản xuất (rà soát code, phần 2): máy tự dựng khi đạo diễn lỗi, mua giọng vừa đủ dùng, lưu giọng ElevenLabs ngay,
dọn tạm không xoá lô đang chạy, ghi sổ không sập khi file bị khoá, timeout Remotion, khoá đánh giá/khoá lô giữa các tiến trình.
Mọi thứ dùng đồ giả: không gọi AI / ElevenLabs / mạng, không chạy ffmpeg / node thật."""
import base64
import copy
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

GOC = Path(__file__).resolve().parents[1]
_tmp = tempfile.TemporaryDirectory()
os.environ.setdefault("XUONG_DATA", _tmp.name)
for _p in (str(GOC / "app"), str(GOC / "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bo_cuc as BC  # noqa: E402
import don_dep  # noqa: E402
import dung  # noqa: E402
import dung_remotion  # noqa: E402
import duyet  # noqa: E402
import ekip  # noqa: E402
import giong  # noqa: E402
import hieu_qua  # noqa: E402
import kho_nhac  # noqa: E402
import su_kien  # noqa: E402
from ai import HetHanMuc  # noqa: E402


def canh(i, dai=12.0, vai=("vuon",), dep=4, mat=0, ghi="", file=None):
    return {"id": f"{i:04d}", "file": file or f"clip{i}.mp4", "tu": 0.0, "den": dai, "dai": dai, "dep": [1.0, dai - 1.0], "vai_tro": list(vai),
            "mo_ta": ghi or f"canh so {i}", "the": [], "soat": {"dep": dep, "mat": mat, "ghi": ghi or f"canh so {i}"}}


def kho_gia(n=10, chai=(2, 5)):
    return [canh(i, vai=("chai_ro",) if i in chai else ("vuon",)) for i in range(1, n + 1)]


def giong_gia(text="Một hai ba bốn. Năm sáu bảy tám chín mười mười một. Chín mười.", dur=9.0):
    tu = text.replace(".", "").split()
    n = len(tu); words, t = [], 0.0
    for k, w in enumerate(tu):
        gap = 0.2 if k in (3, 10) else 0.0
        dau = t + gap
        words.append({"w": w + ("." if k in (3, 10, n - 1) else ""), "s": round(dau, 2), "e": round(dau + 0.5, 2)}); t = dau + 0.5
    return {"text": text, "words": words, "dur": dur, "meta": "meta.json", "audio": "a.mp3"}


def kiem_nhu_dung(testcase, segs, total):
    """Kiểm đúng những gì dung.render / bo_cuc.loc đọc từ plan['edl_segs']."""
    testcase.assertTrue(segs)
    testcase.assertAlmostEqual(sum(sg["dur"] for sg in segs), total, delta=0.05 * len(segs))
    rng = __import__("random").Random(1)
    for i, sg in enumerate(segs):
        sh = sg["shot"]
        for kh in ("file", "tu", "den", "dai", "dep", "id"):
            testcase.assertIn(kh, sh)
        testcase.assertIn(sg["bo_cuc"], BC.SO_PHU)
        testcase.assertEqual(len(sg["phu_shots"]), BC.SO_PHU[sg["bo_cuc"]])
        testcase.assertGreater(sg["dur"], 0)
        testcase.assertGreaterEqual(sg["src_start"], sh["tu"] - 1e-6)
        testcase.assertLessEqual(sg["src_start"], max(sh["tu"], sh["den"] - sg["dur"]) + 0.01)
        L = sg["bo_cuc"]; opt = BC.tuy_chon(rng)
        kind, mf = dung.motion_filter("zoom_vao", sg["dur"], rng)
        n_mask = len(BC.mask_sizes(L, opt))
        lines, _ = BC.loc(i, L, sg["dur"], 0, list(range(1, 1 + BC.SO_PHU[L])), list(range(10, 10 + n_mask)),
                          dung.MENU["mau"]["tu_nhien"], mf, opt, sh, list(sg["phu_shots"]))
        testcase.assertTrue(lines)


# ======================================================================== #1 máy tự dựng
class MayTuDungTest(unittest.TestCase):
    def test_segs_theo_luat_hop_le_cho_render(self):
        shots = kho_gia(10)
        v = giong_gia()
        sents = dung.sentence_times(v["text"], v["words"])
        self.assertEqual(len(sents), 3)
        total = 9.6
        per, _ = ekip.ung_vien(sents, [], shots, __import__("random").Random(3))
        segs = ekip.segs_theo_luat(sents, total, shots, per, __import__("random").Random(3))
        kiem_nhu_dung(self, segs, total)
        # câu 2 dài 4,3 s+ → 2 cảnh; câu 1 và 3 ngắn → 1 cảnh
        self.assertEqual([sum(1 for sg in segs if sg["cau"] == k) for k in range(3)], [1, 2, 1])
        ids = [sg["shot"]["id"] for sg in segs]
        self.assertEqual(len(ids), len(set(ids)))                       # kho đủ lớn → không lặp cảnh
        self.assertTrue(BC.la_chai(segs[-1]["shot"]))                   # câu chốt thấy chai
        for sg in segs:                                                 # mỗi đoạn nằm trong độ dài cảnh (kho giả đủ dài)
            self.assertLessEqual(sg["dur"], sg["shot"]["den"] - sg["shot"]["tu"] + 1e-6)

    def test_khong_lap_bo_cuc_lien_ke_va_nguoi_noi_vao_khung(self):
        shots = kho_gia(10)
        shots[0] = canh(1, mat=3)                                       # cảnh có người nói: chỉ được đặt trong khung nhỏ
        v = giong_gia(); sents = dung.sentence_times(v["text"], v["words"])
        segs = ekip.segs_theo_luat(sents, 9.6, shots, [[s["id"] for s in shots]] * 3, __import__("random").Random(0))
        for sg in segs:
            if sg["shot"]["soat"]["mat"] >= 2:
                self.assertEqual(sg["bo_cuc"], "khung_nho")
        kiem_nhu_dung(self, segs, 9.6)

    def test_kho_nho_va_canh_xau_van_dung_duoc(self):
        shots = [canh(1, vai=("chai_ro",)), canh(2, dep=1), canh(3, dep=1)]       # 2 cảnh "xấu" (dep ≤ 1)
        v = giong_gia(); sents = dung.sentence_times(v["text"], v["words"])
        segs = ekip.segs_theo_luat(sents, 9.6, shots, None, __import__("random").Random(0))   # per=None cũng được
        self.assertTrue(all(sg["shot"]["id"] == "0001" for sg in segs))           # chỉ có 1 cảnh tốt → dùng lại
        kiem_nhu_dung(self, segs, 9.6)
        tat_ca_xau = [canh(1, dep=1), canh(2, dep=1)]
        kiem_nhu_dung(self, ekip.segs_theo_luat(sents, 9.6, tat_ca_xau, None, __import__("random").Random(0)), 9.6)
        with self.assertRaises(ValueError):
            ekip.segs_theo_luat(sents, 9.6, [], None, __import__("random").Random(0))
        with self.assertRaises(ValueError):
            ekip.segs_theo_luat([], 9.6, shots, None, __import__("random").Random(0))

    def test_segs_may_dung_tu_giong(self):
        shots = kho_gia(8)
        segs = ekip.segs_may_dung(giong_gia(), {"y_canh": ["", None, ""]}, {}, shots, set(), __import__("random").Random(5))
        total = round(max(9.0 + 0.6, ekip.khung_giay({})[0] + 0.3), 2)
        kiem_nhu_dung(self, segs, total)


def _dung_ekip(td, so_video, so_loi, dao_dien, tao_giong, chon_tk=lambda: object()):
    """Chạy ekip._chay với đồ giả; trả (log, plan các video được chuyển cho chuan_bi, số lần dựng lớp chữ)."""
    td = Path(td)
    ma = "sp-test"
    d = td / "san-pham" / ma; d.mkdir(parents=True)
    (d / "san-pham.json").write_text(json.dumps({"ten_goi": "SP Thử", "kho_video": str(td / "kho")}), encoding="utf-8")
    (d / "canh.json").write_text(json.dumps(kho_gia(10)), encoding="utf-8")
    (td / "lich-su").mkdir(exist_ok=True)
    cfg = copy.deepcopy(ekip.CFG)
    cfg["duong_dan"]["ra"] = str(td / "ra"); cfg["giong"]["danh_sach"] = {"G": "vid"}; cfg["lo"]["video_moi_giong"] = 2; cfg["dung_lai"] = False
    nhat_ky, plans = [], []

    def viet(ma_sp, n, log):
        return [{"goc": f"g{i}", "giong": "G", "text": giong_gia()["text"], "captions": ["c"], "hashtag": ["#a"], "y_canh": []} for i in range(so_loi)]

    def chuan_bi(plan, voice, shots, kho, work_dir, music=None):
        plans.append(plan)
        kiem_nhu_dung(unittest.TestCase(), plan["edl_segs"], round(max(voice["dur"] + 0.6, 20.3), 2))
        Path(work_dir).mkdir(parents=True, exist_ok=True); (Path(work_dir) / "base.mp4").write_bytes(b"x")
        return {"props": "p", "frames": str(Path(work_dir) / "chu"), "base": str(Path(work_dir) / "base.mp4"), "sfx": [], "total": 20.3}, \
            {"thoi_luong": 20.3, "bo_cuc": [sg["bo_cuc"] for sg in plan["edl_segs"]], "khoi": [], "canh": [], "cong_thuc": "x", "sfx": None}

    def dung_lo(jobs, pub, log):
        for j in jobs:
            Path(j["out"]).parent.mkdir(parents=True, exist_ok=True); Path(j["out"]).write_bytes(b"mp4")
        return [j["out"] for j in jobs]

    p = [mock.patch.object(ekip, n, v) for n, v in (
        ("CFG", cfg), ("HUB", td), ("viet", viet), ("tao_giong", tao_giong), ("dao_dien", dao_dien), ("chuan_bi", chuan_bi), ("dung_lo", dung_lo),
        ("giam_khao", lambda *a, **k: {"diem": 7, "dat": True, "loi": [], "sua": ""}), ("scan", lambda *a, **k: []),
        ("kho_them_cua", lambda *a, **k: []), ("canh_qua", lambda *a, **k: {}))]
    p.append(mock.patch("ai.chon_tai_khoan", lambda *a, **k: chon_tk()))
    p.append(mock.patch.object(ekip.SK, "ghi", lambda *a, **k: None))
    for x in p:
        x.start()
    try:
        ekip._chay(ma, so_video, nhat_ky.append, lambda g, r: None)
    finally:
        for x in reversed(p):
            x.stop()
    return nhat_ky, plans


class DaoDienLoiTest(unittest.TestCase):
    def test_dao_dien_loi_van_ra_video_bang_may_tu_dung(self):
        with tempfile.TemporaryDirectory() as td:
            def dd(*a, **k):
                raise ValueError("AI không trả JSON hợp lệ")

            def tg(text, vid, out, ten, doc=None):
                return giong_gia()
            log, plans = _dung_ekip(td, so_video=2, so_loi=1, dao_dien=dd, tao_giong=tg)
        self.assertEqual(len(plans), 2)
        self.assertTrue(all(isinstance(p["edl_segs"], list) and p["edl_segs"] for p in plans))
        self.assertTrue(any("máy tự dựng theo luật" in x for x in log))
        self.assertTrue(any("[2/2]" in x for x in log))                     # cả 2 video đều được lưu

    def test_het_han_muc_khong_duoc_biet_thanh_may_tu_dung(self):
        with tempfile.TemporaryDirectory() as td:
            def dd(*a, **k):
                raise HetHanMuc("hết")
            log, plans = _dung_ekip(td, so_video=2, so_loi=1, dao_dien=dd, tao_giong=lambda *a, **k: giong_gia())
        self.assertEqual(plans, [])
        self.assertTrue(any("HẾT HẠN MỨC" in x for x in log))


# ======================================================================== #3 thứ tự mua giọng
class ThuTuMuaGiongTest(unittest.TestCase):
    def test_giong_mua_tung_dot_xen_voi_dao_dien(self):
        ev = []
        with tempfile.TemporaryDirectory() as td:
            def tg(text, vid, out, ten, doc=None):
                ev.append(("giong", ten)); return giong_gia()

            def dd(ma, sp, voice, script, shots, gu, work, rng, *a, **k):
                ev.append(("daodien", script["goc"])); raise ValueError("loi")      # rơi vào máy tự dựng, không cần AI
            log, plans = _dung_ekip(td, so_video=8, so_loi=4, dao_dien=dd, tao_giong=tg)
        loai = [e[0] for e in ev]
        self.assertEqual(loai.count("giong"), 4)
        self.assertLess(loai.index("daodien"), len(loai) - 1 - loai[::-1].index("giong"))      # đạo diễn đầu chạy TRƯỚC khi mua giọng cuối
        self.assertEqual(loai[:3], ["giong"] * 3)                                              # đợt 1 = 6 video = 3 lời
        self.assertEqual(len(plans), 8)

    def test_het_han_muc_dung_mua_giong(self):
        ev = []
        with tempfile.TemporaryDirectory() as td:
            def tg(text, vid, out, ten, doc=None):
                ev.append(ten); return giong_gia()

            def dd(*a, **k):
                raise HetHanMuc("hết hạn mức")
            log, plans = _dung_ekip(td, so_video=8, so_loi=4, dao_dien=dd, tao_giong=tg)
        self.assertEqual(len(ev), 3)                                    # chỉ đợt 1; lời thứ 4 KHÔNG bị mua giọng
        self.assertTrue(any("HẾT HẠN MỨC" in x for x in log))

    def test_tai_khoan_da_het_thi_khong_mua_giong_nao(self):
        ev = []
        with tempfile.TemporaryDirectory() as td:
            log, plans = _dung_ekip(td, so_video=4, so_loi=2, dao_dien=lambda *a, **k: 1 / 0,
                                    tao_giong=lambda *a, **k: ev.append(1) or giong_gia(), chon_tk=lambda: None)
        self.assertEqual(ev, [])
        self.assertTrue(any("ngừng mua giọng" in x for x in log))


# ======================================================================== #4 lưu giọng ElevenLabs ngay
class LuuGiongTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.d = Path(self.t.name)
        self.goi_api = []
        text = "Xin chào các bạn"
        al = SimpleNamespace(characters=list(text), character_start_times_seconds=[i * 0.1 for i in range(len(text))],
                             character_end_times_seconds=[i * 0.1 + 0.1 for i in range(len(text))])
        resp = SimpleNamespace(audio_base_64=base64.b64encode(b"MP3DATA").decode(), alignment=al, normalized_alignment=None)

        def convert(**kw):
            self.goi_api.append(kw["text"]); return resp
        self.fake_client = SimpleNamespace(text_to_speech=SimpleNamespace(convert_with_timestamps=convert))
        self.ffmpeg_loi = [True]

        def run(cmd, **kw):
            if cmd[0] == "ffmpeg":
                if self.ffmpeg_loi[0]:
                    raise subprocess.CalledProcessError(1, cmd)
                Path(cmd[-1]).write_bytes(b"FINAL"); return SimpleNamespace(returncode=0, stdout="")
            return SimpleNamespace(returncode=0, stdout="1.6\n")
        self.run = run

    def tearDown(self):
        self.t.cleanup()

    def test_hau_ky_loi_khong_mua_lai(self):
        with mock.patch.object(giong, "client", lambda: self.fake_client), mock.patch.object(giong.subprocess, "run", self.run), \
                mock.patch.object(giong, "HUB", self.d):
            with self.assertRaises(subprocess.CalledProcessError):
                giong.tao_giong("Xin chào các bạn", "vid", self.d / "_giong", "ten-1")
            self.assertEqual(len(self.goi_api), 1)
            tho = sorted(p.name for p in (self.d / "_giong").iterdir())
            self.assertTrue(any(n.startswith("_tho-") and n.endswith(".mp3") for n in tho), tho)    # âm thanh gốc đã lưu
            self.assertTrue(any(n.startswith("_tho-") and n.endswith(".json") for n in tho), tho)   # mốc từng chữ đã lưu
            self.assertFalse((self.d / "_giong" / "ten-1.json").exists())
            self.ffmpeg_loi[0] = False
            info = giong.tao_giong("Xin chào các bạn", "vid", self.d / "_giong", "ten-2")           # chạy lại, TÊN KHÁC (dấu thời gian mới)
        self.assertEqual(len(self.goi_api), 1)                          # không gọi API lần 2 = không mất tiền lần 2
        self.assertAlmostEqual(info["dur"], 1.6)
        self.assertEqual([w["w"] for w in info["words"]], ["Xin", "chào", "các", "bạn"])
        self.assertTrue((self.d / "lich-su" / "giong.csv").exists())

    def test_khac_loi_hoac_khac_giong_thi_mua_moi(self):
        self.ffmpeg_loi[0] = False
        with mock.patch.object(giong, "client", lambda: self.fake_client), mock.patch.object(giong.subprocess, "run", self.run), \
                mock.patch.object(giong, "HUB", self.d):
            giong.tao_giong("Xin chào các bạn", "vid", self.d / "_giong", "a")
            giong.tao_giong("Xin chào các bạn", "vid-khac", self.d / "_giong", "b")
            giong.tao_giong("Xin chào các bạn", "vid", self.d / "_giong", "a")        # cùng tên đã xong → đọc cache
        self.assertEqual(len(self.goi_api), 2)

    def test_ffprobe_rong_cung_khong_mat_tien(self):
        self.ffmpeg_loi[0] = False
        out = {"v": ""}
        goc = self.run

        def run(cmd, **kw):
            r = goc(cmd, **kw)
            return SimpleNamespace(returncode=0, stdout=out["v"]) if cmd[0] == "ffprobe" else r
        with mock.patch.object(giong, "client", lambda: self.fake_client), mock.patch.object(giong.subprocess, "run", run), \
                mock.patch.object(giong, "HUB", self.d):
            with self.assertRaises(RuntimeError):
                giong.tao_giong("Xin chào các bạn", "vid", self.d / "_giong", "a")
            self.assertFalse((self.d / "_giong" / "a.mp3").exists())
            out["v"] = "2.0\n"
            giong.tao_giong("Xin chào các bạn", "vid", self.d / "_giong", "b")
        self.assertEqual(len(self.goi_api), 1)


# ======================================================================== #5 dọn tạm + #12 khoá lô
class DonTamKhoaLoTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.d = Path(self.t.name)
        (self.d / "lich-su").mkdir()
        self.ra = self.d / "ra"; self.tam = self.ra / "2026-01-01" / "_tam"
        for ten, cu in (("lo-100000", False), ("lo-010000", True)):
            f = self.tam / ten / "x" / "a.bin"; f.parent.mkdir(parents=True); f.write_bytes(b"1234")
            if cu:
                for p in (f, f.parent, f.parent.parent):
                    os.utime(p, (time.time() - 30 * 3600,) * 2)
        os.utime(self.tam, (time.time() - 30 * 3600,) * 2)               # mtime thư mục _tam rất cũ (lô chạy lâu không làm nó đổi)

    def tearDown(self):
        self.t.cleanup()

    def _don(self, song=None):
        with mock.patch.object(don_dep, "_ra", lambda: self.ra), mock.patch.object(don_dep, "HUB", self.d), \
                mock.patch.object(don_dep, "khoa_con_song", lambda f=None: song):
            don_dep.don(lambda *_: None)

    def test_khong_xoa_lo_moi_du_thu_muc_tam_cu(self):
        self._don()
        self.assertTrue((self.tam / "lo-100000").exists())               # mới (file vừa ghi) → giữ
        self.assertFalse((self.tam / "lo-010000").exists())              # file nào cũng > 6 giờ → xoá

    def test_co_lo_khac_dang_chay_thi_khong_dung_vao_tam(self):
        self._don(song={"pid": os.getpid() + 1, "ma": "x"})
        self.assertTrue((self.tam / "lo-100000").exists() and (self.tam / "lo-010000").exists())

    def test_san_tuoi_theo_file_moi_nhat_trong_cay(self):
        f = self.tam / "lo-010000" / "x" / "moi.bin"; f.write_bytes(b"1")      # thư mục cũ nhưng bên trong có file vừa ghi
        self._don()
        self.assertTrue((self.tam / "lo-010000").exists())

    def test_khoa_doc_quyen_chi_mot_lo_qua(self):
        f = self.d / "lich-su" / "dang-chay.lock"
        kq = []
        bar = threading.Barrier(8)

        def lam():
            bar.wait(); kq.append(don_dep.lay_khoa_lo("sp", f))
        ths = [threading.Thread(target=lam) for _ in range(8)]
        [t.start() for t in ths]; [t.join() for t in ths]
        co = [x for x in kq if x]
        self.assertEqual(len(co), 1)
        self.assertEqual(f.read_text(encoding="utf-8").split(None, 1), [str(os.getpid()), "sp"])   # dòng đầu giữ dạng "<pid> <mã>" cho app
        self.assertIsNotNone(don_dep.khoa_con_song(f))
        self.assertFalse(don_dep.nha_khoa_lo("token-la", f))             # khoá của lô khác: không xoá nhầm
        self.assertTrue(f.exists())
        self.assertTrue(don_dep.nha_khoa_lo(co[0], f))
        self.assertFalse(f.exists())
        self.assertIsNotNone(don_dep.lay_khoa_lo("sp2", f))              # nhả xong lấy lại được

    def test_pid_cap_lai_cho_python_khac_la_khoa_cu(self):
        f = self.d / "lich-su" / "dang-chay.lock"
        tok = don_dep.lay_khoa_lo("sp", f)
        self.assertTrue(tok)
        ten, ct = don_dep.thong_tin_tien_trinh(os.getpid())
        self.assertTrue(ten and ten.lower().startswith("python"), ten)
        # cùng PID nhưng giờ tạo tiến trình khác (PID bị cấp lại cho một python khác) → khoá cũ
        with mock.patch.object(don_dep, "thong_tin_tien_trinh", lambda pid: ("python.exe", (ct or 10**17) + 50_000_000)):
            self.assertIsNone(don_dep.khoa_con_song(f))
            self.assertTrue(don_dep.lay_khoa_lo("sp-moi", f))            # khoá cũ bị dọn, lô mới vào
        with mock.patch.object(don_dep, "thong_tin_tien_trinh", lambda pid: ("chrome.exe", 1)):
            self.assertIsNone(don_dep.khoa_con_song(f))                   # PID là app khác
        with mock.patch.object(don_dep, "thong_tin_tien_trinh", lambda pid: (None, None)):
            self.assertIsNone(don_dep.khoa_con_song(f))                   # tiến trình đã chết

    def test_khoa_kieu_cu_khong_co_file_id_van_dung_luat_python(self):
        f = self.d / "lich-su" / "dang-chay.lock"
        f.write_text(f"{os.getpid()} sp", encoding="utf-8")
        self.assertIsNotNone(don_dep.khoa_con_song(f))
        with mock.patch.object(ekip, "F_KHOA", f):
            self.assertTrue(ekip.dang_co_lo())


# ======================================================================== #6 ghi sổ không sập
class GhiSoTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.d = Path(self.t.name)

    def tearDown(self):
        self.t.cleanup()

    def test_file_bi_khoa_ghi_tam_roi_gop_lai(self):
        f = self.d / "bang.csv"; chan = {"v": True}
        mo_that = open

        def mo(p, *a, **k):
            if chan["v"] and Path(p) == f:
                raise PermissionError("Excel đang mở")
            return mo_that(p, *a, **k)
        dau = su_kien.dong_csv(["a", "b"])
        with mock.patch.object(su_kien, "open", mo, create=True):
            self.assertFalse(su_kien.noi_them(f, su_kien.dong_csv([1, "x"]), ma_hoa="utf-8-sig", dau=dau, thu=2, doi=0))      # không ném lỗi
            self.assertFalse(f.exists())
            self.assertEqual((self.d / "bang.csv.cho-ghi").read_bytes(), b"1,x\r\n")
            chan["v"] = False
            self.assertTrue(su_kien.noi_them(f, su_kien.dong_csv([2, "y"]), ma_hoa="utf-8-sig", dau=dau, thu=2, doi=0))
        self.assertEqual(f.read_text(encoding="utf-8-sig").splitlines(), ["a,b", "1,x", "2,y"])
        self.assertFalse((self.d / "bang.csv.cho-ghi").exists())
        self.assertEqual(f.read_bytes().count(b"\xef\xbb\xbf"), 1)       # chỉ 1 BOM

    def test_luong_song_song_chi_mot_dong_tieu_de(self):
        f = self.d / "giong.csv"
        bar = threading.Barrier(8)

        def lam(i):
            bar.wait(); su_kien.noi_them(f, su_kien.dong_csv([i, "x"]), ma_hoa="utf-8-sig", dau=su_kien.dong_csv(["luc", "ten"]))
        ths = [threading.Thread(target=lam, args=(i,)) for i in range(8)]
        [t.start() for t in ths]; [t.join() for t in ths]
        ds = f.read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual(ds.count("luc,ten"), 1)
        self.assertEqual(len(ds), 9)

    def test_gioi_han_dong_giu_tieu_de(self):
        f = self.d / "t.csv"
        su_kien.noi_them(f, "".join(f"{i},xxxxxxxxxxxxxxxxxxxx\r\n" for i in range(500)), ma_hoa="utf-8-sig", dau="h1,h2\r\n")
        su_kien.noi_them(f, "tail,1\r\n", ma_hoa="utf-8-sig", dau="h1,h2\r\n", giu_dong=50, toi_da_byte=2000)
        ds = f.read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual(ds[0], "h1,h2"); self.assertEqual(ds[-1], "tail,1"); self.assertEqual(len(ds), 51)
        g = self.d / "nk.txt"
        su_kien.noi_them(g, "".join(f"dong {i}\n" for i in range(300)))
        su_kien.noi_them(g, "cuoi\n", giu_dong=20, toi_da_byte=500)
        self.assertEqual(g.read_text(encoding="utf-8").splitlines()[-2:], ["dong 299", "cuoi"])
        self.assertEqual(len(g.read_text(encoding="utf-8").splitlines()), 20)

    def test_ghi_that_bai_hoan_toan_van_khong_nem_loi(self):
        f = self.d / "thu-muc"; f.mkdir()                                  # f là thư mục → mở để ghi chắc chắn lỗi
        self.assertFalse(su_kien.noi_them(f, "x\n", thu=2, doi=0))

    def test_don_dep_cat_so_lich_su_khi_khong_co_lo(self):
        ls = self.d / "lich-su"; ls.mkdir(); (self.d / "ra").mkdir()
        (ls / "nhat-ky.txt").write_text("".join(f"d{i} " + "x" * 100 + "\n" for i in range(20000)), encoding="utf-8")
        with mock.patch.object(don_dep, "_ra", lambda: self.d / "ra"), mock.patch.object(don_dep, "HUB", self.d), \
                mock.patch.object(don_dep, "khoa_con_song", lambda f=None: None):
            don_dep.don(lambda *_: None)
        ds = (ls / "nhat-ky.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(ds), 8000); self.assertTrue(ds[-1].startswith("d19999 "))


# ======================================================================== #7 Remotion timeout
class RemotionTimeoutTest(unittest.TestCase):
    def test_han_mac_dinh_va_theo_config(self):
        with mock.patch.object(dung_remotion, "CFG", {}):
            self.assertEqual(dung_remotion.han_remotion(10), 300 + 20 * 10)
        with mock.patch.object(dung_remotion, "CFG", {"remotion_han_co_so": 60, "remotion_han_moi_giay": 1}):
            self.assertEqual(dung_remotion.han_remotion(10), 70)

    def test_qua_han_diet_cay_tien_trinh(self):
        with tempfile.TemporaryDirectory() as td:
            pidf = Path(td) / "pid.txt"
            ma = ("import os,sys,time\nopen(sys.argv[1],'w').write(str(os.getpid()))\n"
                  "print('{\"ok\": \"A\", \"s\": 1}', flush=True)\ntime.sleep(120)\n")
            ok, log = set(), []
            t0 = time.time()
            with self.assertRaises(dung_remotion.RemotionQuaGio) as cm:
                dung_remotion.chay_node([sys.executable, "-c", ma, str(pidf)], td, 4, ok, log.append)
            self.assertLess(time.time() - t0, 30)
            self.assertIn("quá", str(cm.exception)); self.assertIn("Remotion", str(cm.exception))
            self.assertEqual(ok, {"A"})                                  # video đã xong trước lúc treo vẫn được ghi nhận
            pid = int(pidf.read_text())
            for _ in range(40):
                if don_dep.thong_tin_tien_trinh(pid)[0] is None:
                    break
                time.sleep(0.25)
            self.assertIsNone(don_dep.thong_tin_tien_trinh(pid)[0])      # node đã bị diệt

    def test_node_binh_thuong_khong_bi_ngat(self):
        with tempfile.TemporaryDirectory() as td:
            ok = set()
            dung_remotion.chay_node([sys.executable, "-c", "print('{\"ok\": \"B\", \"s\": 2}')"], td, 30, ok, lambda *_: None)
            self.assertEqual(ok, {"B"})

    def test_dung_lo_het_gio_chi_bo_video_chua_xong(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); (td / "R" / "public").mkdir(parents=True); (td / "R" / "public" / "DTPhudu-Black.otf").write_bytes(b"f")
            log = []

            def node(cmd, cwd, han, ok, lg):
                ok.add("khong-co-gi-khop"); raise dung_remotion.RemotionQuaGio("Dựng lớp chữ (Remotion) quá 5 giây")
            jobs = [{"props": "p", "frames": str(td / "f1"), "base": "b", "out": str(td / "o.mp4"), "total": 20}]
            with mock.patch.object(dung_remotion, "REMOTION", td / "R"), mock.patch.object(dung_remotion, "chay_node", node):
                self.assertEqual(dung_remotion.dung_lo(jobs, td / "pub", log.append), [])
        self.assertTrue(any("quá 5 giây" in x for x in log))


# ======================================================================== #11 khoá đánh giá giữa tiến trình
class KhoaDanhGiaTest(unittest.TestCase):
    def test_khoa_tep_chan_tien_trinh_khac(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "danh-gia.json"
            ma = ("import sys,time\nsys.path.insert(0, sys.argv[1])\nimport su_kien\n"
                  "with su_kien.khoa_tep(sys.argv[2], 5):\n    print('locked', flush=True)\n    time.sleep(3)\n")
            p = subprocess.Popen([sys.executable, "-c", ma, str(GOC / "engine"), str(f)], stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(p.stdout.readline().strip(), "locked")
                t0 = time.time()
                with self.assertRaises(TimeoutError):
                    with su_kien.khoa_tep(f, 0.4):
                        self.fail("không được lấy được khoá khi tiến trình khác đang giữ")
                self.assertLess(time.time() - t0, 3)
                p.wait(timeout=20)
                with su_kien.khoa_tep(f, 5):                              # nhả xong lấy lại được
                    pass
            finally:
                p.kill(); p.wait()

    def test_khoa_tep_cung_tien_trinh_luong_khac(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "x.json"; kq = []
            with su_kien.khoa_tep(f, 2):
                def lam():
                    try:
                        with su_kien.khoa_tep(f, 0.3):
                            kq.append("co")
                    except TimeoutError:
                        kq.append("het-gio")
                th = threading.Thread(target=lam); th.start(); th.join()
            self.assertEqual(kq, ["het-gio"])

    def test_tu_duyet_khoa_ban_thi_khong_ghi_de(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td); (d / "lich-su").mkdir()
            ra = d / "ra" / "2026-01-01"; (ra / "_kem").mkdir(parents=True)
            (ra / "a.mp4").write_bytes(b"x"); (ra / "_kem" / "a.json").write_text(json.dumps({"diem": 9}), encoding="utf-8")
            cfg = {"tu_duyet": {"bat": True, "dat_tu": 7}, "duong_dan": {"ra": str(d / "ra")}}
            f = d / "lich-su" / "danh-gia.json"; log = []
            with mock.patch.object(duyet, "cfg_hub", lambda: cfg), mock.patch.object(duyet, "HUB", d), \
                    mock.patch.object(duyet, "khoa_tep", lambda p, cho: su_kien.khoa_tep(p, 0.3)):
                with su_kien.khoa_tep(f, 2):                             # (giả lập tiến trình app đang ghi đánh giá tay)
                    th = []
                    t = threading.Thread(target=lambda: th.append(duyet.tu_duyet(log.append))); t.start(); t.join()
                self.assertEqual(th, [0]); self.assertFalse(f.exists())
                self.assertEqual(duyet.tu_duyet(log.append), 1)           # hết bận → ghi bình thường
            self.assertEqual(json.loads(f.read_text(encoding="utf-8"))["a.mp4"]["ket_qua"], "dat")


# ======================================================================== #20 #22 nhỏ
class NhoTest(unittest.TestCase):
    def test_hieu_qua_nho_ho_so_khong_co(self):
        hieu_qua._khong_ho_so.clear()
        dem = []
        with mock.patch.object(hieu_qua, "_doc_so_lieu", lambda: {"v1": {"xem24": 5, "xem72": None, "tuong_tac": 0, "kenh": ""}}), \
                mock.patch.object(hieu_qua, "_ho_so", lambda vid, ra: dem.append(vid)):
            hieu_qua.cap_nhat(); hieu_qua.cap_nhat(); hieu_qua.cap_nhat()
        self.assertEqual(dem, ["v1"])                                    # lần 2, 3 không glob lại ổ đĩa
        hieu_qua._khong_ho_so.clear()

    def test_kho_nhac_khong_nho_thoi_luong_loi(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); bai = td / "a.mp3"; bai.write_bytes(b"abc")
            dem = {"d": 0.0}
            with mock.patch.object(kho_nhac, "nguon_phu", lambda loai: [td]), mock.patch.object(kho_nhac, "CHI_MUC", td / "idx.json"), \
                    mock.patch.object(kho_nhac, "thoi_luong", lambda p: dem["d"]):
                self.assertEqual(kho_nhac.nhac_phu(), [])
                self.assertFalse((td / "idx.json").exists())             # đo lỗi (0 s) không được nhớ
                dem["d"] = 95.5                                           # file chép xong, ffprobe đọc được
                ds = kho_nhac.nhac_phu()
            self.assertEqual([r["giay"] for r in ds], [95.5])

    def test_gom_bai_hoc_khong_xoa_bai_hoc_rieng(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); (td / "lich-su").mkdir()
            f = td / "lich-su" / "bai-hoc-sp.txt"; fc = td / "lich-su" / "bai-hoc.txt"
            dong = [f"- bài học riêng số {i}" for i in range(30)]
            f.write_text("\n".join(dong) + "\n", encoding="utf-8"); fc.write_text("- luật chung cũ\n", encoding="utf-8")
            chi_chung = "CHUNG:\n- a1\n- a2\n- a3\nRIENG:\n"
            ca_hai = "CHUNG:\n- a1\n- a2\n- a3\nRIENG:\n- r1\n- r2\n"
            log = []
            import ai
            with mock.patch.object(ekip, "HUB", td), mock.patch.object(ai, "goi", lambda *a, **k: (chi_chung, {})):
                ekip.gom_bai_hoc("sp", log.append)
                self.assertEqual(f.read_text(encoding="utf-8").splitlines(), dong)            # nguyên vẹn
                self.assertEqual(fc.read_text(encoding="utf-8"), "- luật chung cũ\n")
            with mock.patch.object(ekip, "HUB", td), mock.patch.object(ai, "goi", lambda *a, **k: (ca_hai, {})):
                ekip.gom_bai_hoc("sp", log.append)
                self.assertEqual(f.read_text(encoding="utf-8").splitlines(), ["- r1", "- r2"])
                self.assertEqual(len(fc.read_text(encoding="utf-8").splitlines()), 3)
                self.assertEqual((td / "lich-su" / "bai-hoc-sp.txt.bak").read_text(encoding="utf-8").splitlines(), dong)   # có bản lưu phòng hờ


if __name__ == "__main__":
    unittest.main()
