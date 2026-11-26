"""AI soát kho cảnh BẰNG MẮT (làm 1 lần mỗi kho, thêm cảnh mới thì chỉ soát phần mới).
python soat_kho.py <ma-san-pham>
Ghép ảnh khung thành tờ 8×5 có số id → AI xem → đánh dấu từng cảnh: mặt người/đang nói, chữ chèn/bình luận, hàng khác, độ đẹp.
Ghi vào canh.json trường "soat"; cảnh lỗi nặng tự bị loại khi dựng."""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from ai import goi, lay_json, HetHanMuc  # noqa: E402
import phieu  # noqa: E402

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
COLS, ROWS, TW, TH = 8, 5, 200, 356


def to_anh(ma, ids, k):
    d = HUB / "san-pham" / ma / "_khung"
    out = HUB / "san-pham" / ma / "_soat"; out.mkdir(exist_ok=True)
    sheet = Image.new("RGB", (COLS * TW, ROWS * TH), "black")
    try:
        font = ImageFont.truetype("arialbd.ttf", 30)
    except Exception:
        font = ImageFont.load_default()
    for i, sid in enumerate(ids):
        im = Image.open(d / f"{sid}.jpg").resize((TW, TH))
        x, y = (i % COLS) * TW, (i // COLS) * TH
        sheet.paste(im, (x, y))
        dr = ImageDraw.Draw(sheet)
        dr.rectangle([x, y, x + 86, y + 38], fill="black")
        dr.text((x + 6, y + 3), sid, fill="yellow", font=font)
    f = out / f"to-{k:02d}.jpg"
    sheet.save(f, quality=85)
    return f


def ctx(sp, ids):
    """Dữ liệu điền vào mẫu prompt/soat-kho.md."""
    return {"ten": sp["ten_goi"], "ids": ", ".join(ids), "nhan": "; ".join(sp.get("nhan_cung_san_pham", [])) or "không có"}


def dung_prompt(sp, ids):
    import prompt_mau
    return prompt_mau.dien("soat-kho", **ctx(sp, ids))


def soat(ma):
    sp = json.loads((HUB / "san-pham" / ma / "san-pham.json").read_text(encoding="utf-8"))
    f = HUB / "san-pham" / ma / "canh.json"
    shots = json.loads(f.read_text(encoding="utf-8"))
    lai = "--lai" in sys.argv
    co_anh = lambda s: (HUB / "san-pham" / ma / "_khung" / f"{s['id']}.jpg").exists()
    can = [s["id"] for s in shots if ("soat" not in s or (lai and ("chu_muc" not in s["soat"] or "nhan" not in s["soat"]))) and co_anh(s)]
    # kho kiểu 3: phiếu đã có mọi trường soát trừ KHUNG NHÃN → cảnh thấy SP chính mà chưa định vị chai thì soát riêng để lấy "nhan"
    chi_nhan = {s["id"] for s in shots if s.get("kieu") == 3 and s.get("nhan_can_hop") and not (s.get("soat") or {}).get("nhan")
                and not s.get("nhan_da_tim") and s["id"] not in can and co_anh(s)}
    can += sorted(chi_nhan)
    n = COLS * ROWS
    nhom = [can[i:i + n] for i in range(0, len(can), n)]
    print(f"{ma}: soát {len(can)} cảnh / {len(nhom)} tờ")

    def lam(k_ids):
        k, ids = k_ids
        anh = to_anh(ma, ids, k)
        for lan in range(2):
            try:
                txt, u = goi("soát kho cảnh", dung_prompt(sp, ids), anh=[anh])
                return {int(x["id"]): x for x in lay_json(txt) if isinstance(x, dict) and str(x.get("id", "")).isdigit()}   # id có thể 3 hoặc 4 chữ số
            except HetHanMuc:
                raise                                  # hết hạn mức / chưa đăng nhập / chưa cài CLI: thử lại vô ích → dừng cả bước
            except Exception as e:
                print(f"  tờ {k} lỗi lần {lan + 1}: {str(e)[:150]}")
        return {}
    with ThreadPoolExecutor(3) as ex:
        kq = {}
        for r in ex.map(lam, enumerate(nhom)):
            kq.update(r)
    for s in shots:
        if int(s["id"]) in kq:
            x = kq[int(s["id"])]
            if s["id"] in chi_nhan:                  # chỉ bù khung nhãn, giữ các trường phiếu v3 đã ghi; đã tìm mà không thấy → null + đánh dấu
                s["soat"]["nhan"] = phieu._nhan(x.get("nhan"))[0]        # kiểm 4 số 0–1 + nới mép như phiếu kiểu 2
                s["nhan_da_tim"] = True
                continue
            s["soat"] = {k: x.get(k) for k in ("mat", "chu_muc", "hang_khac", "dep", "nhan", "ghi")}
    f.write_text(json.dumps(shots, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = [s for s in shots if s.get("soat") and not bad(s)]
    print(f"đã soát {sum(1 for s in shots if s.get('soat'))}; dùng làm cảnh chính được {len(ok)}")


def bad(s, chinh=True):
    """Cảnh KHÔNG dùng: chữ chèn nhiều/to (chu_muc 2), hàng khác, quá xấu.
    Kid 10/11: cảnh có người nói vẫn tốt → giữ (máy dựng sẽ đặt vào khung/ô để không lộ lệch khẩu hình); chữ chèn ít thì vẫn dùng."""
    if s.get("cam"):                                          # kho kiểu 3: luật cấm chung phieu_v3.cam (giá/quà trên hình, SP khác đọc được tên, mờ, chữ che)
        return True
    x = s.get("soat") or {}
    chu = x.get("chu_muc", 2 if x.get("chu") else 0) or 0         # AI bỏ trống → coi như không có chữ
    return bool(chu >= 2 or (x.get("dep") or 3) <= 1)        # Kid 14/11: có hàng hãng khác làm nền vẫn dùng (chỉ không làm cảnh chai chốt — xem bo_cuc.la_chai)


def nguoi_noi(s):
    """Người có thể đang nói (đặt trong khung, không full màn — miệng mấp máy lệch lời đọc). Chấm thật 14/11: AI hay ghi mat=1 cho người
    đang nói mà không nhìn máy → mặt người cỡ trung/cận cũng tính."""
    m = (s.get("soat") or {}).get("mat") or 0
    return m >= 2 or (m == 1 and s.get("co_canh") not in ("toan", None))


if __name__ == "__main__":
    soat(sys.argv[1])   # thêm --lai để soát lại theo tiêu chí mới
