"""Nạp ĐẦU TIÊN khi chạy cả bộ (discover xếp theo tên): cả bộ test dùng 1 thư mục dữ liệu tạm riêng.
Trước đây module nào nạp duong_dan trước khi lớp test đặt XUONG_DATA thì cả bộ ghi vào du-lieu/ của repo, các lớp sau thấy rác của nhau."""
import os
import tempfile
import unittest

os.environ["XUONG_DATA"] = tempfile.mkdtemp(prefix="xv-test-")


class MoiTruongTest(unittest.TestCase):
    def test_du_lieu_tam(self):
        self.assertTrue(os.environ["XUONG_DATA"].lower().startswith(tempfile.gettempdir().lower()))
