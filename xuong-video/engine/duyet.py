"""TỰ DUYỆT THEO ĐIỂM (Kid 10/11/2026): video chưa được anh đánh giá mà giám khảo chấm ≥ dat_tu → tự ✅ (TryPost lấy đăng);
nếu đặt bo_duoi > 0: điểm < bo_duoi → tự ❌. Không bao giờ đè đánh giá anh đã bấm tay. Cài trong config "tu_duyet"."""
import datetime, json
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho, kem, ghi_json, KHOA_DANH_GIA
from su_kien import khoa_tep


def tu_duyet(log=print):
    cfg = cfg_hub()
    td = cfg.get("tu_duyet") or {}
    if not td.get("bat"):
        return 0
    dat_tu = float(td.get("dat_tu", 7)); bo_duoi = float(td.get("bo_duoi", 0) or 0)
    f = HUB / "lich-su" / "danh-gia.json"
    doc = lambda: json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    dg = doc()
    ra = Path(cfg["duong_dan"]["ra"]); n_dat = n_bo = 0
    moi = {}                                   # quyết định tự duyệt (chưa ghi) — quét mất thời gian nên KHÔNG giữ khoá lúc này
    for v in ra.glob("*/*.mp4"):
        if v.parent.name.startswith("_") or v.name.endswith(".part.mp4") or v.name in dg:      # .part.mp4 = đang ghi dở
            continue
        mf = kem(v, ".json")
        if not mf.exists():
            continue
        try:
            diem = json.loads(mf.read_text(encoding="utf-8")).get("diem")
        except Exception:
            continue
        if diem is None:
            continue
        luc = datetime.datetime.now().isoformat(timespec="minutes")
        if diem >= dat_tu:
            moi[v.name] = {"ket_qua": "dat", "gop_y": "", "luc": luc, "tu_dong": f"điểm {diem} ≥ {dat_tu:g}"}
        elif bo_duoi and diem < bo_duoi:
            moi[v.name] = {"ket_qua": "bo", "gop_y": "", "luc": luc, "tu_dong": f"điểm {diem} < {bo_duoi:g}"}
    if moi:
        try:                                   # khoá luồng + KHOÁ HĐH trên file: bấm tay ✅/❌ ở app (tiến trình khác) cũng chờ cùng khoá
            with KHOA_DANH_GIA, khoa_tep(f, 10):
                hien = doc()                   # đọc lại ngay trước khi ghi: quyết định tay của anh (✅/❌) luôn thắng
                for ten, x in moi.items():
                    if ten in hien:
                        continue
                    hien[ten] = x
                    if x["ket_qua"] == "dat": n_dat += 1
                    else: n_bo += 1
                if n_dat or n_bo:
                    ghi_json(f, hien, indent=1)
        except TimeoutError:
            n_dat = n_bo = 0
            log("  (tự duyệt: file đánh giá đang bận — để lô sau)")
    if n_dat or n_bo:
        log(f"  ✅ Tự duyệt theo điểm: {n_dat} video đạt (≥ {dat_tu:g})" + (f", {n_bo} video bỏ (< {bo_duoi:g})" if n_bo else ""))
    return n_dat + n_bo
