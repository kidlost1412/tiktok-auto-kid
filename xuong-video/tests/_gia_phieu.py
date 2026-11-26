"""Đồ giả cho test học cảnh kiểu 2 (KHÔNG gọi Antigravity thật): dựng phiếu đúng từ lời nhắc, runner giả, cat/to_anh giả."""
import json, re
from pathlib import Path


def ra_tu_prompt(prompt):
    return Path(re.search(r"đúng file này \([^)]*\):\n(.+)", prompt).group(1).strip())


def phieu_tu_prompt(prompt, hong=(), loai="ket_qua", **them):
    """Phiếu ĐÚNG cho mọi cảnh/video trong lời nhắc. hong: số cảnh cố tình làm sai (loai lạ). them: ghi đè ô của mọi cảnh."""
    n_video = int(re.search(r"Có (\d+) video", prompt).group(1))
    so = [int(x) for x in re.findall(r"cảnh (\d+): từ giây", prompt)]
    canh = []
    for n in so:
        c = {"so": n, "loai": "bay_la" if n in hong else loai, "co_canh": "trung", "mat": 0, "chu_chen": 0, "hang_khac": False, "nhan_doc": "", "nhan": None,
             "loi": "", "ta": f"Cảnh số {n} tay vạch tán lá xanh", "dang_noi_ve": ""}
        c.update(them)
        canh.append(c)
    video = [{"thu_tu": i, "nghe_duoc": True, "tom_tat": f"Tóm tắt video {i}", "cay_trong": "ớt", "loi_hay": ["Câu hay số một."]} for i in range(1, n_video + 1)]
    return {"video": video, "canh": canh}


def runner_gia(log, hong_theo_lan=None, truoc=None):
    """runner(model, prompt, outs, tieu_de, khi_co, **kw) giống chay_lo: ghi phiếu đúng vào outs[0] rồi gọi khi_co. log nhận mỗi lần gọi.
    hong_theo_lan: {lần gọi (1,2,…): {số cảnh làm sai}}; truoc(lan, prompt) chạy trước khi ghi (thử dừng giữa chừng); trả [] nếu truoc trả False."""
    dem = {"n": 0}

    def runner(model, prompt, outs, tieu_de, khi_co, **kw):
        dem["n"] += 1
        log.append({"lan": dem["n"], "model": model, "prompt": prompt, "kw": kw, "tieu_de": tieu_de})
        if truoc and truoc(dem["n"], prompt) is False:
            return []
        text = json.dumps(phieu_tu_prompt(prompt, hong=(hong_theo_lan or {}).get(dem["n"], ())), ensure_ascii=False)
        outs[0].parent.mkdir(parents=True, exist_ok=True)
        outs[0].write_text(text, encoding="utf-8")
        khi_co(outs[0], text)
        return [outs[0]]
    return runner


def cat_gia(so_canh=3, dai=None, net=1.2, chuyen_dong="em"):
    dai = dai or 6.0 + 5 * so_canh + 4

    def cat(path):
        canh = [{"tu": 2.0 + 5 * i, "den": 6.0 + 5 * i, "giua": 4.0 + 5 * i, "chuyen_dong": chuyen_dong, "net": net, "rung": 0.5, "cu_may": [0.0, dai]}
                for i in range(so_canh)]
        return {"dai": dai, "vet_cat": [], "canh": canh}
    return cat


def to_anh_gia(ds, out, **kw):
    return [Path(f"{out}-1.jpg")]


# ----------------------------------------------------------------------------------------------- học kiểu 3 (phiếu v3.1)
def doan_v3(tu, den, **k):
    """Một đoạn phiếu v3.1 ĐÚNG khung (khớp phieu_v3.kiem_video)."""
    d = {"tu": tu, "den": den, "hinh": "Tay cầm chai TC01 giơ về máy", "viec": [{"ma": "cam_xem", "vat": "v1", "dich": None}],
         "vat_thay": [{"id": "v1", "mat": "truoc", "ten_doc": "TC 01", "so_luong": 1}], "cay": None, "dau_hieu": [], "sinh_vat": [],
         "so_sanh": None, "dich_thay": "", "nguoi": {"kieu": "tay", "mat_ro": False, "noi_vao_may": False}, "loi": [], "chu_dan": [],
         "gia_qua": {"chu_dan": [], "tren_vat": [], "loi": []}, "nguon": "quay_that",
         "khung": {"co_canh": "can", "chu_the_o": "giua", "net": 3, "rung": False, "toi": False, "dep": 3}}
    d.update(k)
    return d


def form_v3(dai, so_doan=2, bo_qua_het=False):
    """Phiếu video ĐÚNG phủ liền 0–dai. bo_qua_het=True: không đoạn nào, cả video nằm trong bo_qua (video đen/thẻ cuối)."""
    vat = [{"id": "v1", "loai": "chai", "chu_doc": "TC 01", "la": "sp_chinh"}]
    if bo_qua_het:
        return {"tom_tat": "toàn màn đen", "kieu_video": "khac", "vat": [], "bo_qua": [{"tu": 0, "den": dai, "ly_do": "den"}], "doan": []}
    moc = [round(dai * i / so_doan, 2) for i in range(so_doan)] + [dai]
    return {"tom_tat": "hình cho thấy tay cầm chai", "kieu_video": "huong_dan", "vat": vat, "bo_qua": [],
            "doan": [doan_v3(moc[i], moc[i + 1]) for i in range(so_doan)]}


def ds_v3_tu_prompt(prompt):
    """[(mã, độ dài, file)] đọc từ danh sách VIDEO trong lời nhắc dien-phieu-v3 (mỗi dòng: - mã V1 | … | dài 12.50s | file: …)."""
    return [(m.group(1), float(m.group(2)), m.group(3).strip()) for m in
            re.finditer(r"^- mã (\S+) \|.*?\| dài ([\d.]+)s \| file: (.+?)(?: \| LẦN TRƯỚC.*)?$", prompt, re.M)]


def ra_v3_tu_prompt(prompt):
    return Path(re.search(r"vào ĐÚNG file: (.+)", prompt).group(1).strip())


def runner_v3_gia(log, hong=None, truoc=None, bo_qua_het=()):
    """runner(model, prompt, outs, tieu_de, khi_co, **kw) giống chay_lo cho lời nhắc kiểu 3: ghi 1 file {mã: phiếu}. log nhận mỗi lần gọi.
    hong(lan, ten_file) → None (phiếu đúng) | 'thieu' (bỏ video khỏi file) | 'ho' (đoạn hở giữa video) | 'json' (cả file không phải JSON);
    truoc(lan, prompt) chạy trước khi ghi, trả False → không ghi gì ([]). bo_qua_het: tên file được ghi dạng toàn bo_qua."""
    dem = {"n": 0}

    def runner(model, prompt, outs, tieu_de, khi_co, **kw):
        dem["n"] += 1
        ds = ds_v3_tu_prompt(prompt)
        log.append({"lan": dem["n"], "model": model, "prompt": prompt, "kw": kw, "tieu_de": tieu_de, "ds": ds})
        if truoc and truoc(dem["n"], prompt) is False:
            return []
        obj, rac = {}, False
        for ma, dai, f in ds:
            ten = Path(f).name; kieu = hong(dem["n"], ten) if hong else None
            if kieu == "json":
                rac = True
            elif kieu == "thieu":
                continue
            elif kieu == "ho":
                v = form_v3(dai, 3); del v["doan"][1]; obj[ma] = v
            else:
                obj[ma] = form_v3(dai, 2, bo_qua_het=ten in bo_qua_het)
        text = "không phải json {" if rac else json.dumps(obj, ensure_ascii=False)
        outs[0].parent.mkdir(parents=True, exist_ok=True)
        outs[0].write_text(text, encoding="utf-8")
        khi_co(outs[0], text)
        return [outs[0]]
    return runner
