"""Nạp kho cảnh cho MỌI sản phẩm từ mô tả có sẵn (_mo-ta/*.mo-ta.json) + cắt ảnh khung cho AI đạo diễn nhìn.
python kho_canh.py <ma-san-pham>
→ san-pham/<ma>/canh.json (giữ tương thích máy dựng: id, file, tu, den, dai, crop, vai_tro) + san-pham/<ma>/_khung/<id>.jpg
Lọc: điểm < 3, chữ chèn sẵn, sản phẩm hãng khác, người nói vào máy (lời đọc AI sẽ lệch khẩu hình), file trong loai_tru.
Không đụng video gốc."""
import json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho

VAI_TRO = [   # vai trò chung (từ khoá trong mô tả + thẻ)
    ("chai_ro", ["cầm chai", "cam_chai", "chai_", "nhãn", "nhan_doc_ro", "can_canh_san_pham", "xoay chai", "xoay_chai"]),
    ("nhan_can", ["mặt sau", "mat_sau", "nhan_sau", "thành phần", "thanh_phan", "hướng dẫn sử dụng", "liều"]),
    ("pha_rot", ["rót", "đổ ", "đong", "pha ", "pha_thuoc", "pha_thuốc", "rot_thuoc", "phuy", "bình", "nắp"]),
    ("phun", ["phun", "xịt", "phun_xit", "phun_suong", "tưới", "tuoi_goc"]),
    ("re", ["rễ", "re_", "kích_rễ", "kich_re", "bộ rễ", "rễ trắng"]),
    ("cay_con", ["cây con", "cay_con", "ca_phe_con", "cây giống", "bầu", "giâm", "đọt non", "dot_non"]),
    ("van_de", ["bệnh", "vàng lá", "còi", "chết", "thối", "héo", "nấm", "rêu"]),
    ("vuon", ["vườn", "toàn cảnh", "toan_canh", "canh_vuon", "rẫy", "đồi"]),
    ("ket_qua", ["kết quả", "ket_qua", "kết_quả", "xanh tốt", "la_xanh", "phát triển", "bung", "nở bụi"]),
    ("kho_hang", ["kho hàng", "kho_hang", "thùng hàng", "thùng chai", "xếp chai", "kệ hàng", "kệ trưng", "cửa hàng", "cua_hang"]),  # KHÔNG dùng "kho" trơn: khớp nhầm "khoẻ"
]
NOI = ["nói vào", "nói chuyện", "đang nói", "giới thiệu vào máy", "selfie", "nhìn vào máy", "nhìn camera", "đứng nói", "ngồi nói",
       "thuyết minh trước", "livestream"]
SACH = {"", "khong", "không", "không có", "khong co", "none", "null", "false"}


def _text(x):
    return x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)


def nap(ma):
    sp_dir = HUB / "san-pham" / ma
    sp = json.loads((sp_dir / "san-pham.json").read_text(encoding="utf-8"))
    kho = Path(sp["kho_video"])
    bo_file = set(sp.get("loai_tru", {}).get("file", []))
    rieng = sp.get("vai_tro_rieng", [])          # [[vai, [từ khoá]]] riêng sản phẩm
    da_xem = set()
    shots, bo = [], {"diem": 0, "chu_chen": 0, "hang_khac": 0, "nguoi_noi": 0, "khong_file": 0, "trung": 0}
    for mt in sorted(x for x in (kho / "_mo-ta").rglob("*.mo-ta.json")
                     if not any(part.startswith("_") for part in x.relative_to(kho / "_mo-ta").parts[:-1])):   # bỏ _goc-gemini (bản sao lưu)
        try:
            d = json.loads(mt.read_text(encoding="utf-8"))
        except Exception:
            continue
        f = d.get("video") or mt.name.replace(".mo-ta.json", "")
        if f in da_xem:          # cùng 1 video có 2 bản mô tả (2 lần Gemini chạy) → chỉ lấy 1
            bo["trung"] += 1; continue
        da_xem.add(f)
        if f in bo_file or d.get("is_duplicate") or d.get("ban_trung_cua"):
            bo["trung"] += 1; continue
        if not (kho / f).exists():
            # mô tả ghi đường dẫn tính từ thư mục cha (vd. "đạm 1l/x.mp4" khi kho là chính "đạm 1l") → thử bỏ phần đầu
            alt = Path(*Path(f).parts[1:]) if len(Path(f).parts) > 1 else None
            if alt and (kho / alt).exists():
                f = str(alt)
            else:
                bo["khong_file"] += 1; continue
        khac = [s for s in d.get("san_pham_thay", []) if isinstance(s, dict) and s.get("la_san_pham_khac")]
        # đoạn Gemini báo vấn đề nặng: nghi AI tạo, watermark, lật gương, ảnh ghép, logo kênh khác → không dùng
        nang = [v for v in d.get("van_de", []) if isinstance(v, dict) and v.get("loai") in
                ("nghi_AI", "watermark", "lat_guong", "anh_ghep", "logo_kenh")]
        for c in d.get("canh_quay", []):
            try:
                a, b = float(c["tu_s"]), float(c["den_s"])
            except Exception:
                continue
            if b - a < 1.0:
                continue
            # Gemini chấm theo kiểu B-roll nên hạ điểm cảnh người nói/cầm sản phẩm. Kid 10/11: các cảnh đó vẫn tốt (đặt trong khung)
            # → giữ điểm ≥ 2, và cả điểm 0–1 nếu là người cầm/giới thiệu sản phẩm; AI soát bằng mắt sẽ loại cảnh xấu thật.
            the_c = set(map(str, c.get("the", [])))
            if (c.get("diem") or 0) < 2 and not the_c & {"nguoi_noi_vao_may", "cam_chai", "can_san_pham", "nhan_doc_ro", "combo_san_pham"}:
                bo["diem"] += 1; continue
            chu_ghi = str(c.get("chu_chen_san", "")).strip().lower() not in SACH   # giữ lại, AI soát chấm mức chữ
            if any(float(s.get("tu_s", 0)) < b and float(s.get("den_s", 1e9)) > a for s in khac):
                bo["hang_khac"] += 1; continue
            def _chong(v):
                try:
                    return max(0.0, min(b, float(v.get("den_s", 1e9))) - max(a, float(v.get("tu_s", 0))))
                except Exception:
                    return 0.0
            if any(_chong(v) > 0.5 * (b - a) for v in nang):
                bo["van_de"] = bo.get("van_de", 0) + 1; continue
            hinh = _text(c.get("hinh", ""))
            the = [str(t) for t in c.get("the", [])]
            blob = (hinh + " " + " ".join(the) + " " + _text(c.get("san_pham", ""))).lower()
            co_noi = any(k in blob for k in NOI) or "nguoi_noi_vao_may" in the   # Kid: cảnh người nói vẫn tốt → giữ, máy đặt vào khung
            vai = [v for v, kws in VAI_TRO + rieng if any(k.lower() in blob for k in kws)] or ["vuon"]
            kd = c.get("khung_dep_nhat") or [a, b]
            try:
                kd = [max(a, float(kd[0])), min(b, float(kd[1]))]
            except Exception:
                kd = [a, b]
            sid = f"{len(shots):04d}"
            shots.append({"id": sid, "file": f, "tu": round(a + (0.3 if a < 0.3 else 0), 2), "den": round(b, 2),
                          "dai": round(b - a - (0.3 if a < 0.3 else 0), 2), "crop": sp.get("cat_khung", {}).get(f),
                          "vai_tro": vai, "diem": c.get("diem"), "co_canh": c.get("co_canh"), "mo_ta": hinh[:220],
                          "the": the[:10], "cay": d.get("cay_trong", []), "dep": [round(x, 2) for x in kd],
                          "chu_ghi": chu_ghi, "noi_ghi": co_noi})
    f_cu = sp_dir / "canh.json"
    if f_cu.exists():
        cu = json.loads(f_cu.read_text(encoding="utf-8"))
        theo_khoa = {(x["file"], round(x["tu"], 1)): x for x in cu}
        so = max([int(x["id"]) for x in cu] + [-1]) + 1
        # cảnh cũ: bỏ nếu file gốc không còn hoặc đã đưa vào loai_tru (lỗi rà soát #9)
        gop = [x for x in cu if x["file"] not in bo_file and ((kho / x["file"]).exists() or Path(x["file"]).is_absolute() and Path(x["file"]).exists())]
        for x in shots:
            if (x["file"], round(x["tu"], 1)) in theo_khoa:
                continue
            x["id"] = f"{so:04d}"; so += 1; gop.append(x)
            cu_anh = sp_dir / "_khung" / f"{x['id']}.jpg"
            if cu_anh.exists():
                cu_anh.unlink()                         # ảnh khung còn sót của id cũ → cắt lại cho đúng cảnh mới
        print(f"  giữ {len(cu)} cảnh cũ (id + kết quả soát), thêm {len(gop) - len(cu)} cảnh mới")
        shots = gop
    f_cu.write_text(json.dumps(shots, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{ma}: {len(shots)} cảnh dùng được; bỏ {bo}")
    return shots, kho


def cat_khung(ma, shots, kho):
    """1 ảnh/cảnh ở khung đẹp nhất (270x480) — AI đạo diễn xem các ảnh này để chọn cảnh."""
    out = HUB / "san-pham" / ma / "_khung"; out.mkdir(exist_ok=True)

    def one(s):
        o = out / f"{s['id']}.jpg"
        if o.exists():
            return
        t = (s["dep"][0] + s["dep"][1]) / 2
        cr = s.get("crop")
        pre = f"crop=iw*{cr[2]}:ih*{cr[3]}:iw*{cr[0]}:ih*{cr[1]}," if cr else ""
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(kho / s["file"]), "-frames:v", "1", "-vf",
                        f"{pre}scale=270:480:force_original_aspect_ratio=increase,crop=270:480", "-q:v", "4", str(o)])
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(one, shots))
    print("ảnh khung:", len(list(out.glob("*.jpg"))))


if __name__ == "__main__":
    s, k = nap(sys.argv[1])
    cat_khung(sys.argv[1], s, k)
