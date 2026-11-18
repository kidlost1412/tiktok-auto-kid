"""Dọn bù chat của app còn sót trong Antigravity: chỉ chat thuộc Project do hub tạo, đã im lặng đủ lâu, không đang chạy.
Không gọi Antigravity thật (RPC được thay), không đụng thư mục ~/.gemini thật."""
import datetime as dt
import json
import sqlite3
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import hoc_canh as h  # noqa: E402


def _db(f, rows):
    c = sqlite3.connect(f)
    c.execute("create table conversation_summaries (conversation_id text, title text, project_id text, last_modified_time text, not_fully_idle integer)")
    c.executemany("insert into conversation_summaries (conversation_id, title, project_id, last_modified_time, not_fully_idle) values (?,?,?,?,?)", rows)
    c.commit()
    c.close()


class DonChatAgy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.proj = self.tmp / "projects"
        self.proj.mkdir()
        kho = self.tmp / "lich-su" / "_giam-khao"
        kho.mkdir(parents=True)
        self.app_id = h.id_project_hoc_canh(kho)
        (self.proj / f"{self.app_id}.json").write_text(json.dumps({"id": self.app_id, "projectResources": {"resources": [{"folderUri": h._uri_kho(kho)}]}}), encoding="utf-8")
        # Project của chủ máy: id không theo công thức của hub → không bao giờ là của app.
        (self.proj / "8a5c1a3e-4cae-4d58-b9b2-4e6cc3745a1e.json").write_text(json.dumps({"id": "8a5c1a3e-4cae-4d58-b9b2-4e6cc3745a1e", "projectResources": {"resources": [{"folderUri": h._uri_kho(kho)}]}}), encoding="utf-8")
        p = mock.patch.object(h, "PROJECT_DIR", self.proj)
        p.start()
        self.addCleanup(p.stop)
        self.now = dt.datetime(2026, 11, 18, 10, 0, tzinfo=dt.timezone.utc)

    def test_only_app_projects_are_recognised(self):
        self.assertEqual(h.project_cua_app(), {self.app_id})

    def test_reads_antigravity_time_format(self):
        t = h._thoi_diem("2026-11-16 09:18:30.9547956+00:00")
        self.assertEqual(t, dt.datetime(2026, 11, 16, 9, 18, 30, 954795, tzinfo=dt.timezone.utc))
        self.assertIsNone(h._thoi_diem("rác"))

    def test_leftovers_are_only_idle_old_chats_of_the_app(self):
        f = self.tmp / "s.db"
        cu = "2026-11-18 09:00:00.1234567+00:00"
        moi = "2026-11-18 09:50:00.0+00:00"
        _db(f, [
            ("a-cu", "Giám khảo", self.app_id, cu, 0),                                    # của app, cũ, im → dọn
            ("b-moi", "Giám khảo", self.app_id, moi, 0),                                  # của app nhưng mới 10 phút → chưa
            ("c-ban", "Giám khảo", self.app_id, cu, 1),                                   # của app nhưng chưa xong → không
            ("d-kid", "Audit dự án", "8a5c1a3e-4cae-4d58-b9b2-4e6cc3745a1e", cu, 0),      # của chủ máy → không bao giờ
            ("e-ngoai", "Mời nhà sáng tạo", "outside-of-project", cu, 0),                 # ngoài Project → không bao giờ
            ("f-hoc", "Xưởng Video · Nano Đồng · lô 1/3", "outside-of-project", cu, 0),    # Học cảnh của app ngoài Project → dọn
            ("g-trong", "", "outside-of-project", cu, 0),                                 # không tiêu đề → không biết của ai → không
        ])
        self.assertEqual(h.chat_sot(bay_gio=self.now, du_lieu=f), ["a-cu", "f-hoc"])

    def test_a_chat_still_open_in_a_run_is_never_swept(self):
        f = self.tmp / "s.db"
        _db(f, [("a-cu", "Học cảnh", self.app_id, "2026-11-18 08:00:00+00:00", 0)])
        with mock.patch.dict(h._RUNS, {"sp": {"conv": {"a-cu"}}}):
            self.assertEqual(h.chat_sot(bay_gio=self.now, du_lieu=f), [])

    def test_sweep_deletes_by_rpc_and_waits_when_antigravity_is_closed(self):
        goi = []
        with mock.patch.object(h, "chat_sot", return_value=["x1", "x2"]), \
                mock.patch.object(h, "_goi_ls", side_effect=lambda m, b, timeout=5: goi.append((m, b)) or {}):
            with mock.patch.object(h, "tim_hub", return_value=None):
                self.assertEqual(h.don_chat_sot(), 0)
            self.assertEqual(goi, [])
            with mock.patch.object(h, "tim_hub", return_value={"httpPort": 1, "csrfToken": "t"}):
                self.assertEqual(h.don_chat_sot(), 2)
        self.assertEqual(goi, [("DeleteCascadeTrajectory", {"cascadeId": "x1"}), ("DeleteCascadeTrajectory", {"cascadeId": "x2"})])

    def test_fake_runs_in_tests_never_trigger_a_real_sweep(self):
        out = self.tmp / "kq.json"

        def gui(model, prompt, tieu_de, project=None):
            out.write_text('{"ok": 1}', encoding="utf-8")
            return "cid-gia"
        ev = __import__("threading").Event()
        with mock.patch.object(h, "don_chat_sot_nen") as nen:
            txt = h.hoi_mot_lan("m", "p", out, han=600, gui=gui, huy_cuoc=lambda c: None, ngu=lambda s: None, huy=ev)
        self.assertIn("ok", txt)
        nen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
