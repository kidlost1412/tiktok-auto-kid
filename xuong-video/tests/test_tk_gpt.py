"""Nhiều tài khoản ChatGPT (engine/tk_gpt.py + ai._goi_gpt). KHÔNG chạy codex thật: Popen/run được thay bằng tiến trình giả."""
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

GOC = Path(__file__).resolve().parents[1]
for p in (str(GOC / "engine"), str(GOC / "app")):
    if p not in sys.path:
        sys.path.insert(0, p)

import ai  # noqa: E402
import tk_gpt  # noqa: E402


def dong(**k):
    return json.dumps(k) + "\n"


MODELS = {"data": [
    {"id": "gpt-6.2-sol", "model": "gpt-6.2-sol", "displayName": "GPT 6.2 Sol", "isDefault": True, "hidden": False,
     "supportedReasoningEfforts": [{"reasoningEffort": "low"}, {"reasoningEffort": "high"}], "defaultReasoningEffort": "high"},
    {"id": "gpt-x", "model": "gpt-x", "displayName": "X", "isDefault": False, "hidden": True, "supportedReasoningEfforts": [], "defaultReasoningEffort": "medium"}],
    "nextCursor": None}


def app_server_out(used5=9, used7=29, reached=None, allowed=True, account=True):
    rl = {"rateLimits": {"primary": {"usedPercent": used5, "windowDurationMins": 300, "resetsAt": 1900000000},
                         "secondary": {"usedPercent": used7, "windowDurationMins": 10080, "resetsAt": 1900500000},
                         "planType": "team", "rateLimitReachedType": reached}, "ordinaryUsageAllowed": allowed}
    acc = {"account": {"type": "chatgpt", "email": "a@b.c", "planType": "team", "workspaceName": "WS"}} if account else {"account": None}
    return ["noise not json\n", dong(id=1, result={"userAgent": "x"}), dong(id=2, result=acc),
            dong(id=3, result=rl) if account else dong(id=3, error={"code": -32600, "message": "no auth"}), dong(id=4, result=MODELS)]


class PopenGia:
    def __init__(self, lines):
        self.stdin = io.StringIO(); self.stdout = iter(lines); self.killed = False

    def kill(self):
        self.killed = True


class TrangThai(unittest.TestCase):
    def chay(self, lines):
        with mock.patch.object(tk_gpt, "codex_exe", return_value="codex"), \
                mock.patch.object(tk_gpt.subprocess, "Popen", side_effect=lambda *a, **k: PopenGia(lines)):
            return tk_gpt.trang_thai({"ma": "g1", "thu_muc": None}, timeout=5)

    def test_doc_day_du(self):
        t = self.chay(app_server_out())
        self.assertTrue(t["dang_nhap"])
        self.assertEqual((t["email"], t["goi"], t["workspace"]), ("a@b.c", "team", "WS"))
        self.assertEqual(t["five_hour"], {"pct": 0.09, "reset": 1900000000})
        self.assertEqual(t["seven_day"], {"pct": 0.29, "reset": 1900500000})
        self.assertFalse(t["het"])
        self.assertEqual([m["id"] for m in t["models"]], ["gpt-6.2-sol", "gpt-x"])
        m = t["models"][0]
        self.assertTrue(m["mac_dinh"]); self.assertEqual(m["effort"], ["low", "high"]); self.assertEqual(m["effort_mac_dinh"], "high")

    def test_het_theo_cac_dau_hieu(self):
        self.assertTrue(self.chay(app_server_out(reached="primary"))["het"])
        self.assertTrue(self.chay(app_server_out(allowed=False))["het"])
        self.assertTrue(self.chay(app_server_out(used5=100))["het"])

    def test_chua_dang_nhap(self):
        t = self.chay(app_server_out(account=False))
        self.assertFalse(t["dang_nhap"]); self.assertIsNone(t["email"])

    def test_app_server_hong_lui_ve_login_status(self):
        kq = mock.Mock(returncode=0)
        with mock.patch.object(tk_gpt, "codex_exe", return_value="codex"), \
                mock.patch.object(tk_gpt.subprocess, "Popen", side_effect=OSError("không có codex")), \
                mock.patch.object(tk_gpt.subprocess, "run", return_value=kq) as run:
            t = tk_gpt.trang_thai({"ma": "g1", "thu_muc": None}, timeout=5)
        self.assertTrue(t["dang_nhap"]); self.assertIsNone(t["five_hour"]); self.assertFalse(t["het"]); self.assertTrue(t["loi"])
        self.assertEqual(run.call_args[0][0][-2:], ["login", "status"])
        kq.returncode = 1
        with mock.patch.object(tk_gpt, "codex_exe", return_value="codex"), \
                mock.patch.object(tk_gpt.subprocess, "Popen", side_effect=OSError("x")), mock.patch.object(tk_gpt.subprocess, "run", return_value=kq):
            self.assertFalse(tk_gpt.trang_thai({"ma": "g1", "thu_muc": None}, timeout=5)["dang_nhap"])

    def test_env_codex_home(self):
        with mock.patch.dict(tk_gpt.os.environ, {"CODEX_HOME": "X"}):
            self.assertNotIn("CODEX_HOME", tk_gpt.env({"thu_muc": None}))
            self.assertTrue(tk_gpt.env({"thu_muc": "C:/a/b"})["CODEX_HOME"].endswith("b"))


class Co(unittest.TestCase):
    """Có HUB tạm."""
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(); self.hub = Path(self.td.name)
        self.ps = [mock.patch.object(tk_gpt, "HUB", self.hub), mock.patch.object(ai, "HUB", self.hub)]
        for p in self.ps:
            p.start()

    def tearDown(self):
        for p in self.ps:
            p.stop()
        self.td.cleanup()


def cau_hinh(*ma, dung=None):
    return {"tai_khoan_gpt": [{"ma": m, "ten": m, "thu_muc": None if m == "g1" else f"X/{m}"} for m in ma], **({"tai_khoan_gpt_dung": dung} if dung else {})}


class Chon(Co):
    def ghi(self, ma, **kv):
        tk_gpt.ghi(ma, **kv)

    def test_it_dung_nhat_va_bo_qua_het_chua_dang_nhap(self):
        c = cau_hinh("g1", "g2", "g3", "g4")
        hs = time.time() + 1000
        self.ghi("g1", dang_nhap=True, five_hour={"pct": 0.5, "reset": hs}, seven_day={"pct": 0.1, "reset": hs})
        self.ghi("g2", dang_nhap=True, five_hour={"pct": 0.2, "reset": hs}, seven_day={"pct": 0.9, "reset": hs})
        self.ghi("g3", dang_nhap=False)
        self.ghi("g4", dang_nhap=True, het=True, het_den=hs)
        self.assertEqual(tk_gpt.chon(c=c)["ma"], "g2")
        self.assertEqual(tk_gpt.chon(bo_qua=["g2"], c=c)["ma"], "g1")
        with self.assertRaises(ai.HetHanMuc):
            tk_gpt.chon(bo_qua=["g1", "g2"], c=c)

    def test_hoa_bang_theo_bay_ngay_roi_thu_tu(self):
        c = cau_hinh("g1", "g2"); hs = time.time() + 1000
        self.ghi("g1", dang_nhap=True, five_hour={"pct": 0.3, "reset": hs}, seven_day={"pct": 0.8, "reset": hs})
        self.ghi("g2", dang_nhap=True, five_hour={"pct": 0.3, "reset": hs}, seven_day={"pct": 0.2, "reset": hs})
        self.assertEqual(tk_gpt.chon(c=c)["ma"], "g2")

    def test_chua_co_cache_van_dung_duoc_va_het_den_qua_gio(self):
        c = cau_hinh("g1", "g2")
        self.assertEqual(tk_gpt.chon(c=c)["ma"], "g1")
        self.ghi("g1", het=True, het_den=time.time() - 5)                 # qua giờ mở lại → dùng lại được
        self.assertEqual(tk_gpt.chon(c=c)["ma"], "g1")
        tk_gpt.mark_het("g1", time.time() + 500)
        self.assertEqual(tk_gpt.chon(c=c)["ma"], "g2")

    def test_ghim(self):
        c = cau_hinh("g1", "g2", dung="g2"); hs = time.time() + 1000
        self.ghi("g1", dang_nhap=True, five_hour={"pct": 0.0, "reset": hs})
        self.ghi("g2", dang_nhap=True, five_hour={"pct": 0.9, "reset": hs})
        self.assertEqual(tk_gpt.chon(c=c)["ma"], "g2")
        tk_gpt.mark_het("g2", hs)
        self.assertEqual(tk_gpt.chon(c=c)["ma"], "g1")                   # ghim hết → tự chuyển
        c["tai_khoan_gpt_dung"] = "g9"
        self.assertEqual(tk_gpt.chon(c=c)["ma"], "g1")

    def test_mac_dinh_mot_tai_khoan(self):
        self.assertEqual([t["ma"] for t in tk_gpt.ds_tk({})], ["g1"])


class ThemBo(Co):
    def test_them_khong_dung_lai_thu_muc_cu(self):
        c = {}
        ma = tk_gpt.them(c, "Acc 2")
        self.assertEqual(ma, "g2")
        d = self.hub / "tai-khoan-gpt" / "g2"
        self.assertIn('cli_auth_credentials_store="file"', (d / "config.toml").read_text(encoding="utf-8"))
        self.assertEqual([t["ma"] for t in c["tai_khoan_gpt"]], ["g1", "g2"])
        self.assertEqual(c["tai_khoan_gpt"][1]["thu_muc"], str(d))
        c["tai_khoan_gpt_dung"] = "g2"
        self.assertEqual(tk_gpt.bo(c, "g2"), {"ok": True})
        self.assertEqual(c["tai_khoan_gpt_dung"], "tu_dong")
        self.assertFalse(d.exists())
        self.assertEqual(len(list((self.hub / "tai-khoan-gpt" / "_da-bo").iterdir())), 1)
        self.assertEqual(tk_gpt.them(c, "Mới"), "g3")                     # g2 cũ đã cất vào _da-bo → không dùng lại mã g2

    def test_bo_giu_it_nhat_mot_va_khong_dung_thu_muc_mac_dinh(self):
        c = {}
        self.assertFalse(tk_gpt.bo(c, "g1")["ok"])
        tk_gpt.them(c, "x")
        self.assertTrue(tk_gpt.bo(c, "g1")["ok"])                          # g1 dùng ~/.codex → không cất thư mục nào
        self.assertFalse((self.hub / "tai-khoan-gpt" / "_da-bo").exists())
        self.assertFalse(tk_gpt.bo(c, "zz")["ok"])

    def test_dang_nhap_mot_phien(self):
        c = cau_hinh("g1")
        pr = mock.Mock(); pr.poll.return_value = None
        with mock.patch.object(tk_gpt, "cfg", return_value=c), mock.patch.object(tk_gpt, "codex_exe", return_value="codex"), \
                mock.patch.object(tk_gpt.subprocess, "Popen", return_value=pr) as po:
            self.assertTrue(tk_gpt.mo_dang_nhap("g1")["ok"])
            self.assertFalse(tk_gpt.mo_dang_nhap("g1")["ok"])
            self.assertEqual(po.call_count, 1)
            self.assertEqual(po.call_args[0][0], ["cmd", "/k", "codex", "login"])
            pr.poll.return_value = 0
            self.assertTrue(tk_gpt.mo_dang_nhap("g1")["ok"])
            self.assertFalse(tk_gpt.mo_dang_nhap("zz")["ok"])


class ExecGia:
    def __init__(self, kich_ban, ghi):
        self.kich_ban, self.ghi = kich_ban, ghi; self.pid = 1

    def __call__(self, cmd, **kw):
        self.ghi.append((cmd, kw.get("env") or {}))
        out, err = self.kich_ban(kw.get("env") or {})
        p = mock.Mock(); p.pid = 1; p.communicate.return_value = (out, err)
        return p


def out_ok(txt="xin chào"):
    return dong(type="item.completed", item={"type": "agent_message", "text": txt}) + dong(type="turn.completed", usage={"input_tokens": 10, "output_tokens": 5})


class GoiGpt(Co):
    def chay(self, kich_ban, c, model="gpt-6.2-sol"):
        c = dict(c); c["gpt"] = {"model": model, "effort": "high"}
        ghi = []
        with mock.patch.object(ai, "cfg", return_value=c), mock.patch.object(tk_gpt, "cfg", return_value=c), \
                mock.patch.object(ai, "he_thong", return_value="HT"), mock.patch.object(tk_gpt, "codex_exe", return_value="codex"), \
                mock.patch.object(tk_gpt, "lam_moi_nen") as nen, \
                mock.patch.object(ai.subprocess, "Popen", side_effect=ExecGia(kich_ban, ghi)):
            try:
                kq = ai._goi_gpt("vai", "đề", None, None, 5)
            except Exception as e:
                kq = e
        return kq, ghi, nen

    def token_csv(self):
        return (self.hub / "lich-su" / "token.csv").read_text(encoding="utf-8-sig")

    def test_thanh_cong_ghi_tai_khoan_va_lam_moi_nen(self):
        kq, ghi, nen = self.chay(lambda env: (out_ok(), "model: gpt-6.2-sol\nreasoning effort: high\n"), cau_hinh("g1"))
        self.assertEqual(kq[0], "xin chào")
        self.assertIn("gpt:g1", self.token_csv())
        self.assertNotIn("CODEX_HOME", ghi[0][1])
        self.assertNotIn(tk_gpt.STORE_FILE, ghi[0][0])                      # thư mục mặc định: không ép lưu file
        nen.assert_called_with("g1")

    def test_tai_khoan_rieng_dung_codex_home_va_luu_file(self):
        c = cau_hinh("g1", "g2", dung="g2")
        kq, ghi, _ = self.chay(lambda env: (out_ok(), "model: gpt-6.2-sol\n"), c)
        self.assertEqual(kq[0], "xin chào")
        self.assertTrue(ghi[0][1]["CODEX_HOME"].endswith("g2"))
        self.assertIn(tk_gpt.STORE_FILE, ghi[0][0])
        self.assertIn("gpt:g2", self.token_csv())

    def test_model_khac_thi_bao_loi(self):
        kq, _, _ = self.chay(lambda env: (out_ok(), "model: gpt-5-mini\n"), cau_hinh("g1"))
        self.assertIsInstance(kq, RuntimeError); self.assertNotIsInstance(kq, ai.HetHanMuc)
        self.assertIn("gpt-5-mini", str(kq))

    def test_model_khong_ho_tro_voi_tai_khoan(self):
        loi = dong(type="error", message="The 'gpt-9' model is not supported when using Codex with a ChatGPT account.")
        kq, _, _ = self.chay(lambda env: (loi, ""), cau_hinh("g1"), model="gpt-9")
        self.assertIsInstance(kq, RuntimeError); self.assertNotIsInstance(kq, ai.HetHanMuc); self.assertIn("không dùng được", str(kq))

    def test_danh_sach_model_da_biet_thieu_model(self):
        tk_gpt.ghi("g1", models=[{"id": "gpt-a"}])
        kq, ghi, _ = self.chay(lambda env: (out_ok(), ""), cau_hinh("g1"))
        self.assertIsInstance(kq, RuntimeError); self.assertIn("gpt-a", str(kq)); self.assertEqual(ghi, [])

    def test_het_han_muc_chuyen_tai_khoan_khac(self):
        def kb(env):
            if "CODEX_HOME" not in env:
                return dong(type="error", message="You've hit your usage limit"), ""
            return out_ok("từ g2"), "model: gpt-6.2-sol\n"
        kq, ghi, _ = self.chay(kb, cau_hinh("g1", "g2"))
        self.assertEqual(kq[0], "từ g2"); self.assertEqual(len(ghi), 2)
        self.assertTrue(tk_gpt.doc_trang_thai()["g1"]["het_den"] > time.time())

    def test_mat_dang_nhap_chuyen_va_het_ca_hai_thi_bao(self):
        kq, ghi, _ = self.chay(lambda env: (dong(type="error", message="401 Unauthorized, please login"), ""), cau_hinh("g1", "g2"))
        self.assertIsInstance(kq, ai.HetHanMuc); self.assertEqual(len(ghi), 2)
        self.assertFalse(tk_gpt.doc_trang_thai()["g1"]["dang_nhap"]); self.assertFalse(tk_gpt.doc_trang_thai()["g2"]["dang_nhap"])

    def test_loi_khac_khong_thu_lai(self):
        kq, ghi, _ = self.chay(lambda env: ("", "boom"), cau_hinh("g1", "g2"))
        self.assertIsInstance(kq, RuntimeError); self.assertNotIsInstance(kq, ai.HetHanMuc); self.assertEqual(len(ghi), 1)


if __name__ == "__main__":
    unittest.main()
