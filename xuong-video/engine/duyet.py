"""TỰ DUYỆT THEO ĐIỂM (Kid 10/11/2026): video chưa được anh đánh giá mà giám khảo chấm ≥ dat_tu → tự ✅ (TryPost lấy đăng);
nếu đặt bo_duoi > 0: điểm < bo_duoi → tự ❌. Không bao giờ đè đánh giá anh đã bấm tay. Cài trong config "tu_duyet"."""
import datetime, json
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho


def tu_duyet(log=print):
    cfg = cfg_hub()
    td = cfg.get("tu_duyet") or {}
    if not td.get("bat"):
        return 0
    dat_tu = float(td.get("dat_tu", 7)); bo_duoi = float(td.get("bo_duoi", 0) or 0)
    f = HUB / "lich-su" / "danh-gia.json"
    dg = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    ra = Path(cfg["duong_dan"]["ra"]); n_dat = n_bo = 0
    for v in ra.glob("*/*.mp4"):
        if v.parent.name.startswith("_") or v.name in dg:
            continue
        mf = v.with_suffix(".json")
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
            dg[v.name] = {"ket_qua": "dat", "gop_y": "", "luc": luc, "tu_dong": f"điểm {diem} ≥ {dat_tu:g}"}; n_dat += 1
        elif bo_duoi and diem < bo_duoi:
            dg[v.name] = {"ket_qua": "bo", "gop_y": "", "luc": luc, "tu_dong": f"điểm {diem} < {bo_duoi:g}"}; n_bo += 1
    if n_dat or n_bo:
        f.write_text(json.dumps(dg, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"  ✅ Tự duyệt theo điểm: {n_dat} video đạt (≥ {dat_tu:g})" + (f", {n_bo} video bỏ (< {bo_duoi:g})" if n_bo else ""))
    return n_dat + n_bo
