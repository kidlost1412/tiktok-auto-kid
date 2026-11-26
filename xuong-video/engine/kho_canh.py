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
from phieu import VAI_TU_LOAI, dep_may
import phieu_v3

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


def _tim_file(kho, f):
    """Đường dẫn video tương đối (dấu /) có thật trong kho, hoặc None. Mô tả có thể ghi đường dẫn tính từ thư mục cha
    (vd. "đạm 1l/x.mp4" khi kho là chính "đạm 1l") → thử bỏ phần đầu."""
    if (kho / f).exists():
        return Path(f).as_posix()
    alt = Path(*Path(f).parts[1:]) if len(Path(f).parts) > 1 else None
    return alt.as_posix() if alt and (kho / alt).exists() else None


def _doc_v3(kho, bo_file, bo):
    """{video: mô tả kiểu 3 HỢP LỆ}. Phiếu hỏng → bỏ qua (video dùng mô tả cũ), đếm vào bo["v3_hong"]."""
    md = kho / "_mo-ta"
    kq = {}
    for mt in sorted(md.rglob("*" + phieu_v3.DUOI)) if md.exists() else []:
        if any(p.startswith("_") for p in mt.relative_to(md).parts[:-1]):
            continue
        try:
            d = json.loads(mt.read_text(encoding="utf-8"))
            v = {"tom_tat": d["tom_tat"], "kieu_video": d["phieu_v3"]["kieu_video"], "vat": d["phieu_v3"]["vat"],
                 "bo_qua": d["phieu_v3"]["bo_qua"], "doan": [c["v3"] for c in d["canh_quay"]]}
            loi = phieu_v3.kiem_video(v, d.get("thoi_luong_s"))
        except Exception as e:
            loi = [str(e)]
        f = _tim_file(kho, str(d.get("video") or "")) if not loi else None
        if loi or not f:
            bo["v3_hong"] = bo.get("v3_hong", 0) + 1; continue
        if f in bo_file or f in kq:
            continue
        kq[f] = d
    return kq


def _iou(x, y):
    giao = min(x[1], y[1]) - max(x[0], y[0])
    return max(0.0, giao) / (max(x[1], y[1]) - min(x[0], y[0]))


def _moc(x):
    return x.get("goc") or [x["tu"], x["den"]]


def _ban_chup(sp_dir, giu=10):
    """Sao kho đang dùng (canh.json + bộ đếm + bảng nối id) vào _ban-chup/<giờ>/ trước khi ghi — để quay lui."""
    import datetime, shutil
    co = [sp_dir / n for n in ("canh.json", "canh-id.json", "canh-id-noi.json") if (sp_dir / n).exists()]
    if not co:
        return None
    d = sp_dir / "_ban-chup" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    d.mkdir(parents=True, exist_ok=True)
    for f in co:
        shutil.copy2(f, d / f.name)
    for cu in sorted((sp_dir / "_ban-chup").iterdir())[:-giu]:
        shutil.rmtree(cu, ignore_errors=True)
    return d


def quay_lui(ma, ban=None):
    """Tắt kho kiểu 3 của sản phẩm và trả canh.json về bản chụp (mặc định: bản cũ nhất còn giữ trước lần bật). Lịch sử dùng cảnh không bị đụng."""
    import shutil
    sp_dir = HUB / "san-pham" / ma
    chup = sorted((sp_dir / "_ban-chup").iterdir()) if (sp_dir / "_ban-chup").exists() else []
    d = sp_dir / "_ban-chup" / ban if ban else (chup[0] if chup else None)
    f_sp = sp_dir / "san-pham.json"
    sp = json.loads(f_sp.read_text(encoding="utf-8"))
    sp["kho_v3"] = False
    f_sp.write_text(json.dumps(sp, ensure_ascii=False, indent=2), encoding="utf-8")
    if d and d.exists():
        for n in ("canh.json", "canh-id-noi.json"):
            if (d / n).exists():
                shutil.copy2(d / n, sp_dir / n)
        for f in (sp_dir / "_khung").glob("*.jpg") if (sp_dir / "_khung").exists() else []:
            f.unlink()                                  # ảnh khung theo id → cắt lại cho đúng bản cũ
    return str(d) if d else None


def _gop_v3(cu, v3_shots, file_v3, so, sp_dir):
    """Thay TRỌN tập cảnh của các video có phiếu v3: giữ id cảnh cũ khi ghép một-một IoU ≥ 0,5 (điểm cao trước, hòa → id nhỏ);
    còn lại cấp id mới từ bộ đếm bền. Cảnh cũ không ghép được → bảng nối {id cũ: [id mới chồng lên]} để kế thừa độ mệt."""
    giu, noi = [], {}
    theo_file = {}
    for x in v3_shots:
        theo_file.setdefault(x["file"], []).append(x)
    for f in file_v3:
        cu_f = [y for y in cu if Path(y["file"]).as_posix() == f]
        moi_f = theo_file.get(f, [])
        cap = sorted(((_iou(_moc(o), _moc(n)), o["id"], i, j) for i, o in enumerate(cu_f) for j, n in enumerate(moi_f)),
                     key=lambda t: (-t[0], t[1], t[3]))
        dung_o, dung_n = set(), set()
        for s, _id, i, j in cap:
            if s < 0.5:
                break
            if i in dung_o or j in dung_n:
                continue
            dung_o.add(i); dung_n.add(j)
            n, o = moi_f[j], cu_f[i]
            n["id"] = o["id"]
            if o.get("kieu") == 3 and o.get("dep") == n.get("dep") and o.get("nhan_da_tim"):    # cùng khung ảnh → giữ khung nhãn đã soát
                n["soat"]["nhan"] = (o.get("soat") or {}).get("nhan"); n["nhan_da_tim"] = True
            if o.get("dep") != n.get("dep"):
                (sp_dir / "_khung" / f"{o['id']}.jpg").unlink(missing_ok=True)     # giữ id nhưng mốc đổi → cắt lại ảnh
        for j, n in enumerate(moi_f):
            if j not in dung_n:
                n["id"] = f"{so:04d}"; so += 1
                (sp_dir / "_khung" / f"{n['id']}.jpg").unlink(missing_ok=True)
        for i, o in enumerate(cu_f):
            if i not in dung_o:
                noi[o["id"]] = [n["id"] for n in moi_f if min(_moc(o)[1], _moc(n)[1]) - max(_moc(o)[0], _moc(n)[0]) > phieu_v3.MEP]   # chạm mép ≠ chồng
        giu += moi_f
    return giu, noi, so


def nap(ma):
    sp_dir = HUB / "san-pham" / ma
    sp = json.loads((sp_dir / "san-pham.json").read_text(encoding="utf-8"))
    kho = Path(sp["kho_video"])
    bo_file = set(sp.get("loai_tru", {}).get("file", []))
    rieng = sp.get("vai_tro_rieng", [])          # [[vai, [từ khoá]]] riêng sản phẩm
    da_xem = set()
    file_kieu2 = set()           # video đã học kiểu 2 (phiếu): cảnh kiểu cũ còn sót của các video này sẽ bị thay
    shots, bo = [], {"diem": 0, "chu_chen": 0, "hang_khac": 0, "nguoi_noi": 0, "khong_file": 0, "trung": 0}
    v3 = _doc_v3(kho, bo_file, bo) if sp.get("kho_v3") else {}      # cờ theo SP, mặc định tắt → y như cũ
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
        f2 = _tim_file(kho, f)
        if not f2:
            bo["khong_file"] += 1; continue
        if not (kho / f).exists():
            f = str(Path(f2))
        if Path(f).as_posix() in v3:     # đã có phiếu v3 hợp lệ → mô tả cũ không dùng (vẫn giữ file để quay lui)
            continue
        if d.get("kieu") == 2:
            file_kieu2.add(f)
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
            if d.get("kieu") != 2 and any(float(s.get("tu_s", 0)) < b and float(s.get("den_s", 1e9)) > a for s in khac):   # kiểu 2: giữ, chỉ đánh dấu
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
            ph = c.get("phieu") if isinstance(c.get("phieu"), dict) and d.get("kieu") == 2 else None
            vai = [v for v, kws in VAI_TRO + rieng if any(k.lower() in blob for k in kws)]
            if ph:                                           # kiểu 2: vai trò theo loại cảnh AI điền (cộng thêm từ khoá)
                vai = list(dict.fromkeys(VAI_TU_LOAI.get(ph.get("loai"), []) + vai))
                co_noi = co_noi or ph.get("mat") == 2 or ph.get("loai") == "nguoi_noi"
            else:
                vai = vai or ["vuon"]
            kd = c.get("khung_dep_nhat") or [a, b]
            try:
                kd = [max(a, float(kd[0])), min(b, float(kd[1]))]
            except Exception:
                kd = [a, b]
            sid = f"{len(shots):04d}"
            shot = {"id": sid, "file": f, "tu": round(a + (0.3 if a < 0.3 else 0), 2), "den": round(b, 2),
                          "dai": round(b - a - (0.3 if a < 0.3 else 0), 2), "crop": sp.get("cat_khung", {}).get(f),
                          "vai_tro": vai, "diem": c.get("diem"), "co_canh": c.get("co_canh"), "mo_ta": hinh[:220],
                          "the": the[:10], "cay": d.get("cay_trong", []), "dep": [round(x, 2) for x in kd],
                          "chu_ghi": chu_ghi, "noi_ghi": co_noi}
            if ph:                                           # AI đã điền phiếu → ghi thẳng kết quả soát (soat_kho.py bỏ qua cảnh đã có soat)
                if ph.get("net") is not None:                # chấm lại điểm đẹp theo luật máy hiện hành (đổi luật không cần học lại)
                    try:
                        shot["diem"] = c["diem"] = dep_may(ph.get("net"), ph.get("chuyen_dong"), ph.get("loi"), int(ph.get("chu_chen") or 0), bool(ph.get("hang_khac")))
                    except Exception:
                        pass
                shot.update(kieu=2, loai=ph.get("loai"), noi=ph.get("dang_noi_ve") or "", loi=ph.get("loi") or "",
                            soat={"mat": 2 if ph.get("loai") == "nguoi_noi" else ph.get("mat", 0), "chu_muc": ph.get("chu_chen", 0),
                                  "hang_khac": bool(ph.get("hang_khac")), "dep": c.get("diem"), "nhan": ph.get("nhan"), "ghi": _text(c.get("hinh", ""))[:80]})
            shots.append(shot)
    v3_shots = []
    for f, d in v3.items():
        vat = d["phieu_v3"]["vat"]
        for c in d["canh_quay"]:
            g = c["v3"]
            a, b = float(g["tu"]), float(g["den"])
            if b - a < 1.0:
                bo["v3_ngan"] = bo.get("v3_ngan", 0) + 1; continue
            dau = 0.3 if a < 0.3 else 0
            dung = {x.get("id") for x in g.get("vat_thay") or []} | {x.get("vat") for x in g.get("viec") or []}
            shot = {"id": None, "file": f, "tu": round(a + dau, 2), "den": round(b, 2), "dai": round(b - a - dau, 2), "goc": [a, b],
                    "crop": sp.get("cat_khung", {}).get(f), "kieu": 3, **phieu_v3.shot_cu(g, vat, sp),
                    "v3": g, "vat": [x for x in vat if x.get("id") in dung]}
            v3_shots.append(shot)
    f_id = sp_dir / "canh-id.json"
    try:
        cuoi = int(json.loads(f_id.read_text(encoding="utf-8"))["cuoi"])
    except Exception:
        cuoi = -1
    f_cu = sp_dir / "canh.json"
    moi_v3 = []
    if v3 and not f_cu.exists():
        so = max(len(shots), cuoi + 1)
        for x in v3_shots:
            x["id"] = f"{so:04d}"; so += 1
        shots += v3_shots
    if v3:
        _ban_chup(sp_dir)
    if f_cu.exists():
        cu = json.loads(f_cu.read_text(encoding="utf-8"))
        theo_khoa = {(x["file"], round(x["tu"], 1)): x for x in cu}
        so = max([int(x["id"]) for x in cu] + [-1, cuoi if v3 else -1]) + 1
        if v3:                                       # video có phiếu v3: thay trọn tập cảnh, giữ id theo IoU
            moi_v3, noi, so = _gop_v3(cu, v3_shots, set(v3), so, sp_dir)
            cu = [x for x in cu if Path(x["file"]).as_posix() not in v3]
            theo_khoa = {(x["file"], round(x["tu"], 1)): x for x in cu}
            f_noi = sp_dir / "canh-id-noi.json"
            bang = json.loads(f_noi.read_text(encoding="utf-8")) if f_noi.exists() else {}
            bang.update(noi)
            f_noi.write_text(json.dumps(bang, ensure_ascii=False, indent=1), encoding="utf-8")
        moi_khoa = {(x["file"], round(x["tu"], 1)) for x in shots}
        # cảnh cũ: bỏ nếu file gốc không còn hoặc đã đưa vào loai_tru (lỗi rà soát #9); video đã học kiểu 2 thì chỉ giữ cảnh có trong mô tả mới
        gop = [x for x in cu if x["file"] not in bo_file and ((kho / x["file"]).exists() or Path(x["file"]).is_absolute() and Path(x["file"]).exists())
               and (x["file"] not in file_kieu2 or (x["file"], round(x["tu"], 1)) in moi_khoa)]
        vi_tri = {(x["file"], round(x["tu"], 1)): i for i, x in enumerate(gop)}
        for x in shots:
            k = (x["file"], round(x["tu"], 1))
            if k in theo_khoa:
                if x.get("kieu") == 2 and k in vi_tri:       # cảnh kiểu 2 đã có: cập nhật nội dung theo phiếu, giữ id
                    x["id"] = gop[vi_tri[k]]["id"]; gop[vi_tri[k]] = x
                continue
            x["id"] = f"{so:04d}"; so += 1; gop.append(x)
            cu_anh = sp_dir / "_khung" / f"{x['id']}.jpg"
            if cu_anh.exists():
                cu_anh.unlink()                         # ảnh khung còn sót của id cũ → cắt lại cho đúng cảnh mới
        id_cu = {y["id"] for y in cu}
        print(f"  giữ {sum(1 for x in gop if x['id'] in id_cu)} cảnh cũ (id + kết quả soát), cảnh mới: {sum(1 for x in gop if x['id'] not in id_cu)}, bỏ {len(cu) - sum(1 for x in gop if x['id'] in id_cu)}")
        shots = gop + moi_v3
    if v3:
        f_id.write_text(json.dumps({"cuoi": max([int(x["id"]) for x in shots] + [cuoi])}), encoding="utf-8")
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
