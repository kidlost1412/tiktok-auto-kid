"""HIỆU QUẢ THẬT → NUÔI BIÊN KỊCH & ĐẠO DIỄN (Kid 12/11/2026).

TikTok Auto gửi số liệu từng video về cổng /trypost/so-lieu → lich-su/so-lieu.csv (id = tên video).
Ở đây: ghép số liệu với hồ sơ video (ra/<ngày>/<id>.json: góc, dạng bài, đạo diễn, công thức, giọng, câu mở)
→ lưu bền vào lich-su/hieu-qua.json (hồ sơ video bị dọn sau 30 ngày vẫn còn) → tóm tắt ngắn cho prompt:
  • nhóm nào (góc / dạng bài / đạo diễn / công thức / giọng) ra view cao hơn trung bình — chỉ khi đủ mẫu;
  • câu mở của các video ăn khách nhất / kém nhất của CHÍNH sản phẩm đó.
Chưa đủ số liệu thì trả "" (prompt giữ nguyên như cũ). Tắt bằng config "hieu_qua": {"bat": false}."""
import csv, json, re, statistics, threading
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parent))
from duong_dan import DATA as HUB, cfg as cfg_hub  # noqa: E402

LS = HUB / "lich-su"
CHIEU = {"goc": "góc bán", "dang": "dạng bài", "dao_dien": "gu đạo diễn", "cong_thuc": "công thức dựng", "giong": "giọng đọc"}
_lock = threading.Lock()


def _cai():
    c = cfg_hub().get("hieu_qua") or {}
    return {"bat": c.get("bat", True), "mau_nhom": int(c.get("mau_nhom", 3)), "mau_tong": int(c.get("mau_tong", 6))}


def _so(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def _cau_mo(loi):
    m = re.split(r"(?<=[.!?])\s+", (loi or "").strip(), maxsplit=1)
    return re.sub(r"\[[^\]]*\]", "", m[0]).strip()[:140] if m and m[0] else ""


def _doc_so_lieu():
    """{id: {xem24, xem72, tuong_tac, kenh}} — gộp nhiều dòng của cùng video (lấy số lớn nhất)."""
    f = LS / "so-lieu.csv"
    out = {}
    if not f.exists():
        return out
    with open(f, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            vid = (r.get("id") or "").strip()
            if not vid:
                continue
            d = out.setdefault(vid, {"xem24": None, "xem72": None, "tuong_tac": 0, "kenh": r.get("kenh") or ""})
            for k, cot in (("xem24", "luot_xem_24h"), ("xem72", "luot_xem_72h")):
                v = _so(r.get(cot))
                if v is not None:
                    d[k] = max(d[k] or 0, v)
            tt = sum(_so(r.get(c)) or 0 for c in ("thich", "binh_luan", "chia_se"))
            d["tuong_tac"] = max(d["tuong_tac"], tt)
    return out


def _ho_so(vid, ra):
    for f in ra.glob(f"*/{vid}.json"):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return None
        return {"ma": j.get("ma"), "goc": j.get("goc"), "dang": j.get("dang"), "dao_dien": j.get("dao_dien"),
                "cong_thuc": j.get("cong_thuc"), "giong": j.get("giong"), "cau_mo": _cau_mo(j.get("loi_doc")),
                "diem": j.get("diem"), "ngay": f.parent.name}
    return None


def cap_nhat():
    """Ghép so-lieu.csv + hồ sơ video → lich-su/hieu-qua.json. Trả {id: bản ghi}. An toàn khi gọi nhiều lần."""
    f = LS / "hieu-qua.json"
    with _lock:
        try:
            db = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        except Exception:
            db = {}
        sl = _doc_so_lieu()
        if not sl:
            return db
        try:
            ra = Path(cfg_hub()["duong_dan"]["ra"])
        except Exception:
            ra = HUB / "ra"
        doi = False
        for vid, s in sl.items():
            r = db.get(vid)
            if r is None:
                hs = _ho_so(vid, ra)
                if not hs:
                    continue                      # video không do hub này làm / hồ sơ đã mất → bỏ
                r = db[vid] = hs; doi = True
            for k in ("xem24", "xem72", "tuong_tac", "kenh"):
                if s.get(k) is not None and r.get(k) != s[k]:
                    r[k] = s[k]; doi = True
        if doi:
            LS.mkdir(parents=True, exist_ok=True)
            tmp = f.with_suffix(".tmp")
            tmp.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(f)
        return db


def _diem(r):
    """Thước đo chung: view 24h (cùng mốc cho mọi video); chưa có 24h thì tạm dùng 72h."""
    return r.get("xem24") if r.get("xem24") is not None else r.get("xem72")


def _ban_ghi(ma=None):
    try:
        db = cap_nhat()
    except Exception:
        return [], []
    tat_ca = [r for r in db.values() if _diem(r) is not None]
    return tat_ca, [r for r in tat_ca if r.get("ma") == ma]


def he_so(ma, chieu):
    """{giá trị: hệ số 0.7–1.5} theo hiệu quả (cho việc xoay vòng góc/dạng bài). Thiếu mẫu → {} (giữ xoay vòng đều)."""
    c = _cai()
    if not c["bat"]:
        return {}
    tat_ca, rieng = _ban_ghi(ma)
    nguon = rieng if len(rieng) >= c["mau_tong"] else tat_ca
    if len(nguon) < c["mau_tong"]:
        return {}
    tb = statistics.median(_diem(r) for r in nguon) or 1
    nhom = {}
    for r in nguon:
        if r.get(chieu):
            nhom.setdefault(r[chieu], []).append(_diem(r))
    return {k: max(0.7, min(1.5, statistics.median(v) / tb)) for k, v in nhom.items() if len(v) >= c["mau_nhom"]}


def tom_tat(ma, cho="bien_kich"):
    """Đoạn văn ngắn đưa vào prompt. cho = "bien_kich" (có câu mở) | "dao_dien" (chỉ nhóm dựng). "" nếu chưa đủ số liệu."""
    c = _cai()
    if not c["bat"]:
        return ""
    tat_ca, rieng = _ban_ghi(ma)
    if len(tat_ca) < c["mau_tong"]:
        return ""
    nguon = rieng if len(rieng) >= c["mau_tong"] else tat_ca
    pham_vi = "của sản phẩm này" if nguon is rieng else "của mọi sản phẩm (sản phẩm này chưa đủ video)"
    tb = statistics.median(_diem(r) for r in nguon) or 1
    dong = [f"Dựa trên {len(nguon)} video đã đăng {pham_vi}; trung vị {int(tb)} view/24h. "
            "Đây là gợi ý theo số liệu thật, KHÔNG phải luật — vẫn phải giữ đa dạng, không chép nguyên câu."]
    chieu_dung = ("goc", "dang") if cho == "bien_kich" else ("dao_dien", "cong_thuc", "dang")
    for ch in chieu_dung:
        nhom = {}
        for r in nguon:
            if r.get(ch):
                nhom.setdefault(r[ch], []).append(_diem(r))
        du = sorted(((statistics.median(v) / tb, k, len(v)) for k, v in nhom.items() if len(v) >= c["mau_nhom"]), reverse=True)
        if len(du) >= 2:
            tot = ", ".join(f"{k} (x{h:.1f}, {n} video)" for h, k, n in du[:2] if h >= 1.1)
            kem = ", ".join(f"{k} (x{h:.1f}, {n} video)" for h, k, n in du[-1:] if h <= 0.8)
            if tot or kem:
                dong.append(f"- {CHIEU[ch]}: " + (f"ăn khách: {tot}" if tot else "") + ("; " if tot and kem else "") + (f"kém: {kem}" if kem else ""))
    if cho == "bien_kich" and len(rieng) >= c["mau_tong"]:
        xep = sorted((r for r in rieng if r.get("cau_mo")), key=_diem, reverse=True)
        if len(xep) >= 4:
            dong.append("- Câu mở của video NHIỀU VIEW nhất (học cách mở, không chép):")
            dong += [f'  • "{r["cau_mo"]}" — {_diem(r)} view' for r in xep[:3]]
            dong.append("- Câu mở của video ÍT VIEW nhất (tránh kiểu mở này):")
            dong += [f'  • "{r["cau_mo"]}" — {_diem(r)} view' for r in xep[-2:]]
    return "\n".join(dong) if len(dong) > 1 else ""


def bao_cao(ma):
    """Cho giao diện: số video có số liệu (của sản phẩm / tất cả), ngưỡng, tóm tắt đang đưa cho AI."""
    c = _cai()
    tat_ca, rieng = _ban_ghi(ma)
    xep = sorted(rieng, key=_diem, reverse=True)
    return {"bat": c["bat"], "can": c["mau_tong"], "n": len(rieng), "n_tat_ca": len(tat_ca),
            "bien_kich": tom_tat(ma), "dao_dien": tom_tat(ma, "dao_dien"),
            "top": [{"cau_mo": r.get("cau_mo"), "xem": _diem(r), "goc": r.get("goc"), "dang": r.get("dang"), "ngay": r.get("ngay")} for r in xep[:5]]}


if __name__ == "__main__":       # xem thử: python hieu_qua.py <mã sản phẩm>
    import sys
    db = cap_nhat()
    print(f"{len(db)} video có số liệu + hồ sơ")
    if len(sys.argv) > 1:
        print("--- biên kịch ---\n" + (tom_tat(sys.argv[1]) or "(chưa đủ số liệu)"))
        print("--- đạo diễn ---\n" + (tom_tat(sys.argv[1], "dao_dien") or "(chưa đủ số liệu)"))
