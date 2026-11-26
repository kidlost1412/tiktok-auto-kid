"""Tài khoản/hạn mức Antigravity + kiểm model THỰC của từng lô học cảnh. Mọi lời gọi Antigravity (_goi_ls) đều GIẢ — không chạm Antigravity thật.
Chạy:  python -m unittest tests.test_agy_trang_thai -v"""
import json, sys, time, unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_hoc_canh_v3 import Nen, hc  # noqa: E402  (Nen: dựng kho/hub tạm + chặn _goi_ls thật)
import _gia_phieu as gia  # noqa: E402

BI_MAT = "TOKEN-BI-MAT-123"
ANH = "https://anh.example/avatar-bi-mat.png"


def _user():
    return {"userStatus": {"name": "Nguyen Van Gia", "email": "gia@example.com", "apiKey": BI_MAT, "profilePictureUrl": ANH,
                           "planStatus": {"planInfo": {"planName": "Pro", "teamsTier": "TEAMS_TIER_PRO", "maxNumChatInputTokens": "999"},
                                          "availablePromptCredits": 500, "availableFlowCredits": 100},
                           "userTier": {"id": "g1-ultra-tier", "name": "Google AI Ultra", "description": "x", "upgradeSubscriptionText": "y"},
                           "cascadeModelConfigData": {"clientModelConfigs": [{"label": "L", "accessToken": BI_MAT}]}}}


def _quota(con5=0.7346509, con_tuan=0.9114926):
    return {"response": {"groups": [
        {"displayName": "Gemini Models", "buckets": [
            {"bucketId": "gemini-weekly", "window": "weekly", "remainingFraction": con_tuan, "resetTime": "2026-12-03T07:02:22Z"},
            {"bucketId": "gemini-5h", "window": "5h", "remainingFraction": con5, "resetTime": "2026-11-26T12:02:22Z"}]},
        {"displayName": "Claude and GPT models", "buckets": [
            {"bucketId": "3p-weekly", "window": "weekly", "remainingFraction": 1},
            {"bucketId": "3p-5h", "window": "5h", "remainingFraction": 1}]}]}}


def _models():
    def m(ten, enum, con):
        return {"displayName": ten, "model": enum, "quotaInfo": {"remainingFraction": con, "resetTime": "2026-11-26T12:02:22Z"}, "maxTokens": 1}
    return {"response": {"models": {
        "gemini-4-neon-high": m("Gemini 4 Neon (High)", "MODEL_PLACEHOLDER_M532", 0.7385),
        "gemini-4-hydrogen-high": m("Gemini 4 Hydrogen (High)", "MODEL_PLACEHOLDER_M525", 0.7385),
        "gemini-4-hydrogen-xhigh": m("Gemini 4 Hydrogen (XHigh)", "MODEL_PLACEHOLDER_M528", 0.7385),
        "gemini-3.8-flash-high": m("Gemini 3.8 Flash (High)", "MODEL_PLACEHOLDER_M318", 0.5),
        "gemini-pro-orchestrator": m("Orchestrator (Carbon)", "MODEL_PLACEHOLDER_M667", 1)}}}


def _buoc(resp, enum, vao="100", ra="10", nghi="5", retry=0):
    return {"chatModel": {"model": enum, "responseModel": resp, "modelDisplayName": resp,
                          "usage": {"inputTokens": vao, "outputTokens": ra, "thinkingOutputTokens": nghi, "cacheReadTokens": "7"},
                          "retryInfos": [{"traceId": "t"}] * retry, "customMetadata": {"model_enum": enum}},
            "plannerConfig": {"modelName": "gemini-4-neon-high", "planModel": "MODEL_PLACEHOLDER_M532"}}


def _meta(*buoc):
    return {"generatorMetadata": list(buoc)}


def _ls_gia(meta=None, user=None, quota=None, models=None, dem=None):
    def ls(method, body, timeout=5):
        if dem is not None:
            dem.append(method)
        return {"GetUserStatus": user, "RetrieveUserQuotaSummary": quota, "GetAvailableModels": models,
                "GetCascadeTrajectoryGeneratorMetadata": meta}.get(method)
    return ls


class TrangThaiTest(Nen):
    def setUp(self):
        super().setUp()
        hc._TT_NHO.update(t=0.0, ttl=0, v=None); hc._ENUM_NHO.update(t=0.0, m={})
        p = mock.patch.object(hc, "tim_hub", lambda *a, **k: {"httpPort": 1, "csrfToken": "x"}); p.start(); self.addCleanup(p.stop)

    def test_phan_tich_ba_rpc_va_whitelist(self):
        with mock.patch.object(hc, "_goi_ls", _ls_gia(user=_user(), quota=_quota(), models=_models())):
            v = hc.trang_thai_agy_day_du()
        self.assertTrue(v["mo"]); self.assertIsNone(v["loi"])
        self.assertEqual((v["email"], v["goi"]), ("gia@example.com", "Google AI Ultra"))
        self.assertEqual(len(v["quota"]), 4)
        g5 = next(x for x in v["quota"] if x["ma"] == "gemini-5h")
        self.assertEqual((g5["nhom"], g5["cua_so"], g5["con"], g5["reset"]), ("Gemini Models", "5h", 0.7346509, 1795694542))
        self.assertAlmostEqual(v["gemini_5h"]["pct_dung"], 0.2653, places=3)
        self.assertEqual(v["gemini_5h"]["pct"], v["gemini_5h"]["pct_dung"]); self.assertEqual(v["gemini_5h"]["reset"], 1795694542)
        self.assertAlmostEqual(v["gemini_tuan"]["pct"], 0.0885, places=3)       # bucket weekly của nhóm Gemini, không phải 3p
        ids = [m["id"] for m in v["models"]]
        self.assertEqual(ids, list(dict.fromkeys([*hc.MODELS, hc.MODEL_GIAM_KHAO])))
        neon = next(m for m in v["models"] if m["id"] == "gemini-4-neon-high")
        self.assertEqual((neon["ten"], neon["con"]), ("Gemini 4 Neon (High)", 0.7385))
        self.assertIsNone(next(m for m in v["models"] if m["id"] == "gemini-4-argon-high")["con"])   # API không có id này → con None
        self.assertIsInstance(v["cap_nhat"], int)
        txt = json.dumps(v, ensure_ascii=False)
        for cam in (BI_MAT, ANH, "Nguyen Van Gia", "accessToken", "apiKey", "profilePicture"):
            self.assertNotIn(cam, txt)

    def test_antigravity_dong_khong_loi(self):
        with mock.patch.object(hc, "tim_hub", lambda *a, **k: None), mock.patch.object(hc, "_goi_ls", side_effect=AssertionError("không được gọi")):
            v = hc.trang_thai_agy_day_du()
        self.assertEqual((v["mo"], v["email"], v["goi"], v["quota"], v["models"], v["loi"]), (False, None, None, [], [], None))
        self.assertIsNone(v["gemini_5h"]); self.assertIsNone(v["gemini_tuan"])

    def test_ls_khong_tra_loi_bao_loi_khong_ne(self):
        with mock.patch.object(hc, "_goi_ls", _ls_gia()):
            v = hc.trang_thai_agy_day_du()
        self.assertTrue(v["mo"]); self.assertIn("không trả lời", v["loi"]); self.assertIsNone(v["email"])

    def test_nho_60_giay(self):
        dem = []
        with mock.patch.object(hc, "_goi_ls", _ls_gia(user=_user(), quota=_quota(), models=_models(), dem=dem)):
            hc.trang_thai_agy_day_du(); n = len(dem)
            v2 = hc.trang_thai_agy_day_du()
            self.assertEqual(len(dem), n); self.assertEqual(v2["email"], "gia@example.com")
            hc.trang_thai_agy_day_du(nho=False); self.assertEqual(len(dem), 2 * n)
            hc._TT_NHO["t"] -= 61
            hc.trang_thai_agy_day_du(); self.assertEqual(len(dem), 3 * n)

    def test_canh_bao_quota_thap(self):
        with mock.patch.object(hc, "_goi_ls", _ls_gia(quota=_quota(con5=0.03))):
            self.assertIn("3%", hc.canh_bao_quota_thap())
        with mock.patch.object(hc, "_goi_ls", _ls_gia(quota=_quota(con5=0.5))):
            self.assertIsNone(hc.canh_bao_quota_thap())
        with mock.patch.object(hc, "_goi_ls", _ls_gia()):
            self.assertIsNone(hc.canh_bao_quota_thap())


class KiemModelTest(Nen):
    def setUp(self):
        super().setUp()
        hc._ENUM_NHO.update(t=0.0, m={})

    def _kiem(self, meta, yc="gemini-4-hydrogen-high", **kw):
        with mock.patch.object(hc, "_goi_ls", _ls_gia(meta=meta, models=_models(), **kw)):
            return hc.kiem_model_cuoc("cid-1", yc)

    def test_khop_bo_hau_to_muc_nghi(self):
        k = self._kiem(_meta(_buoc("gemini-4-hydrogen", "MODEL_PLACEHOLDER_M528"), _buoc("gemini-4-hydrogen", "MODEL_PLACEHOLDER_M528", retry=2)))
        self.assertEqual((k["khop"], k["chay"], k["yeu_cau"], k["thu_lai"]), (True, ["gemini-4-hydrogen"], "gemini-4-hydrogen-high", 2))
        self.assertEqual(k["token"], {"vao": 200, "ra": 20, "nghi": 10})

    def test_khop_nho_enum_khi_ten_la(self):
        k = self._kiem(_meta(_buoc("ten-la-khong-doan-duoc", "MODEL_PLACEHOLDER_M528")), yc="gemini-4-hydrogen-xhigh")
        self.assertTrue(k["khop"])
        k = self._kiem(_meta(_buoc("ten-la-khong-doan-duoc", "MODEL_PLACEHOLDER_M528")), yc="gemini-4-neon-high")
        self.assertFalse(k["khop"])

    def test_khac_ho_la_khong_khop(self):
        k = self._kiem(_meta(_buoc("gemini-4-hydrogen", "MODEL_PLACEHOLDER_M528"), _buoc("gemini-3.8-flash", "MODEL_PLACEHOLDER_M318")))
        self.assertFalse(k["khop"]); self.assertEqual(k["chay"], ["gemini-4-hydrogen", "gemini-3.8-flash"])

    def test_khong_doc_duoc_la_none(self):
        for meta in (None, {}, {"generatorMetadata": []}):
            k = self._kiem(meta)
            self.assertIsNone(k["khop"]); self.assertEqual((k["chay"], k["thu_lai"], k["token"]), ([], 0, {"vao": 0, "ra": 0, "nghi": 0}))
        with mock.patch.object(hc, "_goi_ls", side_effect=RuntimeError("hỏng")):
            self.assertIsNone(hc.kiem_model_cuoc("cid-1", "gemini-4-neon-high")["khop"])
        self.assertIsNone(hc.kiem_model_cuoc("", "gemini-4-neon-high")["khop"])

    def test_chay_lo_kiem_truoc_khi_xoa_chat(self):
        thu_tu = []
        outs = [self.kho / "ra.json"]

        def gui(model, prompt, tieu_de):
            outs[0].write_text("{}", encoding="utf-8")
            return "cid-9"

        def kiem(cid, model):
            thu_tu.append(("kiem", cid, model))
            return {"yeu_cau": model, "chay": ["gemini-3.8-flash"], "khop": False, "token": {"vao": 1, "ra": 2, "nghi": 3}, "thu_lai": 0}
        sink = []; tk = hc._MODEL_THUC.set(sink)
        try:
            r = hc.chay_lo("gemini-4-neon-high", "p", outs, "td", lambda f, t: None, han=5, gui=gui, ngu=lambda s: None,
                           huy_cuoc=lambda c: thu_tu.append(("huy", c)), xoa_cuoc=lambda c: thu_tu.append(("xoa", c)), kiem_cuoc=kiem)
        finally:
            hc._MODEL_THUC.reset(tk)
        self.assertEqual(len(r), 1)
        self.assertEqual([t[0] for t in thu_tu], ["kiem", "huy", "xoa"])                  # kiểm TRƯỚC khi huỷ + xoá chat
        self.assertEqual((sink[0]["khop"], sink[0]["chay"]), (False, ["gemini-3.8-flash"]))

    def test_chay_lo_loi_kiem_khong_lam_hong_lo(self):
        outs = [self.kho / "ra.json"]

        def gui(model, prompt, tieu_de):
            outs[0].write_text("{}", encoding="utf-8")
            return "cid-9"
        r = hc.chay_lo("gemini-4-neon-high", "p", outs, "td", lambda f, t: None, han=5, gui=gui, ngu=lambda s: None,
                       huy_cuoc=lambda c: None, xoa_cuoc=lambda c: None, kiem_cuoc=mock.Mock(side_effect=RuntimeError("x")))
        self.assertEqual(len(r), 1)

    def test_giam_khao_ghi_ket_qua_kiem(self):
        out = self.kho / "gk.json"

        def gui(model, prompt, tieu_de):
            out.write_text('{"a": 1}', encoding="utf-8")
            return "cid-gk"
        hc.GIAM_KHAO_MODEL_CUOI.clear()
        with mock.patch.object(hc, "_goi_ls", _ls_gia(meta=_meta(_buoc("gemini-4-hydrogen", "MODEL_PLACEHOLDER_M525")), models=_models())):
            text = hc.hoi_mot_lan("gemini-4-hydrogen-high", "p", out, han=5, gui=gui, huy_cuoc=lambda c: None, ngu=lambda s: None, xoa_cuoc=lambda c: None,
                                  kiem_cuoc=hc.kiem_model_cuoc)
        self.assertIn('"a"', text)
        self.assertEqual((hc.GIAM_KHAO_MODEL_CUOI["khop"], hc.GIAM_KHAO_MODEL_CUOI["vai"]), (True, "giam_khao"))


class HocGhiModelThucTest(Nen):
    def _runner_kiem(self, buoc_moi_lo):
        """Runner giả của kiểu 3: AI ghi phiếu như thường, rồi hook kiểm model THẬT (kiem_model_cuoc, _goi_ls giả) chạy như trong chay_lo."""
        log = []; inner = gia.runner_v3_gia(log)

        def runner(model, prompt, outs, tieu_de, khi_co, **kw):
            r = inner(model, prompt, outs, tieu_de, khi_co, **kw)
            hc._kiem_truoc_xoa(hc.kiem_model_cuoc, "cid-lo", model)
            return r
        return runner, log

    def test_v3_ghi_model_thuc_va_canh_bao_khi_khac_model(self):
        self._videos(3)
        runner, log = self._runner_kiem(None)
        meta = _meta(_buoc("gemini-4-neon", "MODEL_PLACEHOLDER_M532", vao="1000", ra="50", nghi="20"), _buoc("gemini-3.8-flash", "MODEL_PLACEHOLDER_M318", vao="10", ra="1", nghi="0", retry=1))
        with mock.patch.object(hc, "_goi_ls", _ls_gia(meta=meta, models=_models())):
            r = self._chay(runner)
        self.assertTrue(r["tat_ca_xong"], r)
        self.assertEqual(len(r["model_thuc"]), 1)
        m = r["model_thuc"][0]
        self.assertEqual((m["lo"], m["lan"], m["khop"], m["yeu_cau"], m["thu_lai"]), (1, 1, False, "gemini-4-neon-high", 1))
        self.assertEqual(m["chay"], ["gemini-4-neon", "gemini-3.8-flash"]); self.assertEqual(m["token"], {"vao": 1010, "ra": 51, "nghi": 20})
        self.assertIn("Antigravity đã chạy model gemini-4-neon, gemini-3.8-flash thay vì gemini-4-neon-high", hc.JOB["canh_bao"])
        self.assertEqual(hc.JOB["model_thuc"], r["model_thuc"])

    def test_v3_khop_khong_canh_bao_va_khong_kiem_duoc_la_none(self):
        self._videos(2)
        runner, _ = self._runner_kiem(None)
        with mock.patch.object(hc, "_goi_ls", _ls_gia(meta=_meta(_buoc("gemini-4-neon", "MODEL_PLACEHOLDER_M532")), models=_models())):
            r = self._chay(runner)
        self.assertEqual([x["khop"] for x in r["model_thuc"]], [True]); self.assertEqual(hc.JOB["canh_bao"], "")
        self._videos(2, 5)
        runner, _ = self._runner_kiem(None)
        r = self._chay(runner)                                                            # _goi_ls trả None (Nen) → không kiểm được
        self.assertEqual([x["khop"] for x in r["model_thuc"]], [None]); self.assertEqual(hc.JOB["canh_bao"], "")
        self.assertTrue(r["tat_ca_xong"])

    def test_v2_ghi_model_thuc(self):
        self._videos(2)
        log = []; inner = gia.runner_gia(log)

        def runner(model, prompt, outs, tieu_de, khi_co, **kw):
            r = inner(model, prompt, outs, tieu_de, khi_co, **kw)
            hc._kiem_truoc_xoa(hc.kiem_model_cuoc, "cid-lo", model)
            return r
        with mock.patch.object(hc, "_goi_ls", _ls_gia(meta=_meta(_buoc("gemini-3.8-flash", "MODEL_PLACEHOLDER_M318")), models=_models())):
            r = self._chay(runner, kieu3=False, cat=gia.cat_gia(3), to_anh=gia.to_anh_gia)
        self.assertTrue(r["model_thuc"]); self.assertFalse(r["model_thuc"][0]["khop"])
        self.assertIn("thay vì gemini-4-neon-high", hc.JOB["canh_bao"])


if __name__ == "__main__":
    unittest.main()
