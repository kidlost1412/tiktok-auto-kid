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
