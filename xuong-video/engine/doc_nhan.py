"""AI ĐỌC NHÃN: lấy các khung chai/nhãn rõ nhất trong kho (đã nạp) → Claude đọc chữ in trên nhãn → gợi ý "sự thật sản phẩm".
Chỉ là GỢI Ý: Kid kiểm, sửa rồi bấm Lưu trên app mới thành sự thật được nói.
python doc_nhan.py <ma-san-pham>"""
import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ai import goi, lay_json  # noqa: E402

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho

def ctx(sp, ma):
    """Dữ liệu điền vào mẫu prompt/doc-nhan.md."""
    return {"ten": sp.get("ten_goi", ma)}


def dung_prompt(sp, ma):
    import prompt_mau
    return prompt_mau.dien("doc-nhan", **ctx(sp, ma))


def doc(ma, n=8):
    d = HUB / "san-pham" / ma
    sp = json.loads((d / "san-pham.json").read_text(encoding="utf-8"))
    canh = json.loads((d / "canh.json").read_text(encoding="utf-8")) if (d / "canh.json").exists() else []
    if not canh:
        return {"loi": "Kho chưa được chuẩn bị — bấm 'Chuẩn bị kho' trước."}

    def diem(s):
        t = " ".join(s.get("the", [])) + " " + " ".join(s.get("vai_tro", []))
        x = s.get("soat") or {}
        return (3 * ("nhan_mat_sau" in t or "nhan_can" in t) + 2 * ("nhan_doc_ro" in t) + ("chai_ro" in t)
                + (x.get("dep") or 3) - 5 * bool(x.get("hang_khac")) - 2 * ((x.get("chu_muc") or 0) >= 2))
    chon, file_da = [], set()
    for s in sorted(canh, key=diem, reverse=True):
        if s["file"] in file_da or not ({"chai_ro", "nhan_can"} & set(s.get("vai_tro", []))):
            continue
        chon.append(s); file_da.add(s["file"])
        if len(chon) >= n:
            break
    out = d / "_nhan"; out.mkdir(exist_ok=True)
    anh = []
    for s in chon:
        f = out / f"{s['id']}.jpg"
        t = (s["dep"][0] + s["dep"][1]) / 2
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(Path(sp["kho_video"]) / s["file"]), "-frames:v", "1",
                        "-q:v", "2", str(f)])      # độ phân giải gốc để đọc chữ nhỏ
        if f.exists():
            anh.append(f)
    if not anh:
        return {"loi": "Không tìm thấy cảnh chai/nhãn rõ trong kho."}
    txt, _ = goi("đọc nhãn", dung_prompt(sp, ma), anh=anh)
    kq = lay_json(txt)
    return kq if isinstance(kq, dict) else {"loi": "AI trả sai định dạng"}


if __name__ == "__main__":
    print(json.dumps(doc(sys.argv[1]), ensure_ascii=False, indent=1))
