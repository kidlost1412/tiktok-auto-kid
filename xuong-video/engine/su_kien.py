"""Sổ sự kiện có cấu trúc của xưởng (mỗi dòng 1 JSON) -> <DATA>/lich-su/su-kien.jsonl.
Trang "Xưởng nhỏ" đọc sổ này để biết vai nào đang làm gì. Ghi lỗi KHÔNG BAO GIỜ làm hỏng việc sản xuất.

Mỗi sự kiện: n (số thứ tự tăng dần, dùng làm con trỏ `sau`), t (ISO giờ), vai, loai, video, msg, và các trường thêm (diem, dat, so...).
vai : he-thong | bien-kich | giong | dao-dien | dung | giam-khao | kho
loai: bat-dau-lo | bat-dau | xong | diem | dung-lai | luu | het-han-muc | loi | hoc | ket-thuc-lo"""
import datetime, json, os, threading, time
from pathlib import Path

GIU = 2000            # giữ tối đa ngần ấy dòng cuối
DU = 400              # vượt GIU + DU dòng mới cắt (đỡ ghi lại file liên tục)
BYTE = 400_000        # chỉ đếm dòng khi file lớn hơn mức này
_khoa = threading.Lock()
_cuoi = [0]


def _file():
    from duong_dan import DATA
    return Path(DATA) / "lich-su" / "su-kien.jsonl"


def _cat(f):
    ds = f.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(ds) <= GIU + DU:
        return
    tam = f.with_name(f.name + ".tmp")
    tam.write_text("\n".join(ds[-GIU:]) + "\n", encoding="utf-8")
    os.replace(tam, f)


def ghi(vai, loai, msg="", video=None, f=None, **them):
    """Ghi 1 sự kiện. Nuốt mọi lỗi."""
    try:
        f = Path(f) if f else _file()
        with _khoa:
            n = max(_cuoi[0] + 1, time.time_ns() // 1000)
            _cuoi[0] = n
            ev = {"n": n, "t": datetime.datetime.now().isoformat(timespec="seconds"), "vai": vai, "loai": loai}
            if video:
                ev["video"] = str(video)
            if msg:
                ev["msg"] = str(msg)[:200]
            ev.update({k: v for k, v in them.items() if v is not None})
            f.parent.mkdir(parents=True, exist_ok=True)
            with open(f, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
            if f.stat().st_size > BYTE:           # kiểm kích thước rẻ trước khi đếm dòng
                _cat(f)
    except Exception:
        pass


def doc(sau=0, toi_da=300, f=None):
    """Sự kiện có n > sau (tối đa `toi_da` cái cuối). Không bao giờ ném lỗi."""
    try:
        f = Path(f) if f else _file()
        if not f.exists():
            return []
        out = []
        for l in f.read_text(encoding="utf-8", errors="replace").splitlines()[-GIU:]:
            try:
                e = json.loads(l)
            except Exception:
                continue
            if isinstance(e, dict) and int(e.get("n", 0)) > int(sau or 0):
                out.append(e)
        return out[-toi_da:]
    except Exception:
        return []
