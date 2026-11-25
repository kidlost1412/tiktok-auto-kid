"""y_hinh: yêu cầu hình có cấu trúc do biên kịch viết kèm y_canh. Prompt cũ đã ghim vẫn được hợp đồng gắn thêm; hỏng thì bỏ, không làm hỏng kịch bản. KHÔNG gọi AI."""
import json, os, re, sys, tempfile, unittest
from pathlib import Path

os.environ.setdefault("XUONG_DATA", tempfile.mkdtemp(prefix="xv-test-"))
ENG = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENG))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompt_mau as pm  # noqa: E402
import viet_loi as vl  # noqa: E402
from test_bien_kich_moi import Nen, kich_ban  # noqa: E402

HINH = {"muc": "truc_tiep", "viec": ["phun"], "dich": ["binh_phun"], "cay": [], "bo_phan": [], "dau_hieu": [],
        "can_sp": "khong", "can_nguoi_noi": False, "tu_khoa": ["bình phun"], "giay": 4.2}
DAU = '"y_hinh"'


class PromptTest(unittest.TestCase):
    def test_prompt_ghim_cu_them_y_hinh(self):
        cu = "Đề bài cũ đã ghim, chỉ có {{de_bai}}\nĐịnh dạng: \"y_canh\": [...] \"don_ban\": \"x\""
        out = pm.dung("bien-kich", cu, {})
        self.assertEqual(out.count(DAU), 1)
        self.assertEqual(out.count("ĐÚNG 1 phần tử cho mỗi câu"), 1)

    def test_prompt_moi_khong_lap_y_hinh(self):
        md = (Path(__file__).resolve().parents[1] / "prompt" / "bien-kich.md").read_text(encoding="utf-8")
        out = pm.dung("bien-kich", md, {})          # md gốc không chứa y_hinh: hợp đồng gắn đúng 1 lần
        out2 = pm.dung("bien-kich", out, {})        # dựng lại trên bản đã có y_hinh: không gắn thêm
        self.assertEqual(out2.count(DAU), out.count(DAU))
        self.assertEqual(out.count(DAU), 1)
        self.assertEqual(out.count("ĐÚNG 1 phần tử cho mỗi câu"), 1)


class GonTest(unittest.TestCase):
    def test_y_hinh_sai_do_dai_va_phan_tu(self):
        self.assertIsNone(vl.gon_y_hinh(None, 3)); self.assertIsNone(vl.gon_y_hinh("x", 3)); self.assertIsNone(vl.gon_y_hinh({"a": 1}, 3))
        r = vl.gon_y_hinh([HINH], 3)                                   # thiếu → đệm {}
        self.assertEqual(r[0], HINH); self.assertEqual(r[1:], [{}, {}])
        r = vl.gon_y_hinh([HINH, HINH, HINH, HINH], 2)                 # thừa → cắt
        self.assertEqual(len(r), 2)
        r = vl.gon_y_hinh([HINH, "rác", 5, None, {"la": 1}, {"viec": 3, "giay": "x", "muc": 7}], 6)
        self.assertEqual(r[0], HINH); self.assertEqual(r[1:], [{}] * 5)
        r = vl.gon_y_hinh([{"muc": "kieu_la", "viec": ["viec_la"], "can_sp": "abc", "can_nguoi_noi": "co", "viec_x": 1}], 1)   # enum lạ giữ nguyên, khoá lạ/kiểu sai bỏ
        self.assertEqual(r, [{"muc": "kieu_la", "viec": ["viec_la"], "can_sp": "abc"}])
        self.assertEqual(vl.gon_y_hinh([{"viec": "phun"}], 1), [{"viec": ["phun"]}])


class VietTest(Nen):
    def chay(self, y_hinh):
        it = kich_ban(1, self.sp, u=True)
        if y_hinh is not None:
            it["y_hinh"] = y_hinh
        goi_cu = vl.goi
        vl.goi = lambda *a, **k: (json.dumps([it], ensure_ascii=False), {})
        try:
            return vl.viet("sp-thu", 1, log=lambda *_: None)
        finally:
            vl.goi = goi_cu

    def test_y_hinh_hong_khong_lam_hong_kich_ban(self):
        self.canh([{"id": "1", "vai_tro": ["chai_ro"], "cay": ["ca_phe"], "soat": {"mat": 0, "dep": 4}}])
        for xau in ("rác", {"a": 1}, [1, "x", None], [HINH] * 9):
            ra = self.chay(xau)
            self.assertEqual(len(ra), 1, xau)
            yh = ra[0]["y_hinh"]
            self.assertTrue(yh is None or (isinstance(yh, list) and len(yh) == 5), yh)   # kich_ban(): 5 câu
        ra = self.chay([HINH, {}, "x"])
        self.assertEqual(len(ra), 1); self.assertEqual(ra[0]["y_hinh"], [HINH, {}, {}, {}, {}])
        self.assertIsNone(self.chay(None)[0]["y_hinh"])


class LamLaiTest(unittest.TestCase):
    def test_lam_lai_sidecar_co_va_thieu_y_hinh(self):
        src = (ENG / "ekip.py").read_text(encoding="utf-8")
        m = re.search(r'"kich_ban": \{k: t\["sc"\]\.get\(k\) for k in \(([^)]*)\)', src)    # sidecar ghi y_hinh cạnh y_canh
        self.assertIn('"y_hinh"', m.group(1))
        # "làm lại" nạp sc từ meta["kich_ban"] rồi bỏ khoá None: sidecar cũ (thiếu) và mới (có) đều ra sc hợp lệ
        nap = lambda kb: {k: v for k, v in kb.items() if v is not None}
        moi = json.loads(json.dumps({"text": "a.", "y_canh": ["x"], "y_hinh": [HINH]}, ensure_ascii=False))
        cu = {"text": "a.", "y_canh": ["x"]}
        null = {"text": "a.", "y_canh": ["x"], "y_hinh": None}
        self.assertEqual(nap(moi)["y_hinh"], [HINH])
        self.assertIsNone(nap(cu).get("y_hinh")); self.assertIsNone(nap(null).get("y_hinh"))
        for sc in (moi, cu, null):               # nơi dùng sau này luôn qua gon_y_hinh: thiếu/None → vắng, không lỗi
            self.assertTrue(vl.gon_y_hinh(sc.get("y_hinh"), 1) in (None, [HINH]))


if __name__ == "__main__":
    unittest.main()
