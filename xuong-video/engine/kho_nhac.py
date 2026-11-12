"""Kho nhạc & âm thanh: gộp "kho mặc định" (gói Mixkit trong tai-nguyen) với các thư mục của người dùng.

QUY TẮC
- Nguồn thêm lưu ở config.json -> nhac.nguon: [{"duong_dan": "...", "loai": "nhac"|"sfx", "bat": true}].
- NHẠC: kho mặc định có _phan-nhom.csv (nhóm tâm trạng + thời lượng). Bài trong thư mục thêm KHÔNG có nhãn:
  tâm trạng = "chung", thời lượng đo bằng ffprobe 1 lần (lưu cache tai-nguyen/_chi-muc-nhac.json). Bài "chung" được
  đưa vào mọi nhóm (hợp mọi công thức) cùng bài của kho mặc định; chỉ lấy bài >= 40 giây.
- SFX: kho mặc định có bảng KHO trong sfx.py. File trong thư mục thêm được xếp nhóm theo TÊN THƯ MỤC CON hoặc TỪ KHOÁ trong
  tên file (vd. "whoosh", "impact", "click", "ding", "coin"...). Tên thư mục con trùng tên nhóm (vut_nhe, dap, bop...) cũng được.
  File không đoán được nhóm thì không dùng.
- Kho mặc định chưa cài vẫn chạy được: chỉ dùng nguồn thêm; nhóm nào không có file thì bỏ qua tiếng đó.
- Tải gói mặc định: tai_goi(url, sha256) — chỉ từ link người dùng đặt trong config (nhac.goi_mac_dinh_url)."""
import csv, hashlib, json, os, re, subprocess, time, urllib.request, zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
AM = (".mp3", ".wav", ".m4a", ".ogg", ".flac")
GOC_TAI_NGUYEN = HUB / "tai-nguyen"
CHI_MUC = GOC_TAI_NGUYEN / "_chi-muc-nhac.json"
TOI_THIEU_S = 40          # bài nhạc nền tối thiểu (giây), giống luật cũ của kho mặc định
LE_NGOAI = ("christmas", "xmas", "santa", "halloween", "jingle", "holiday", "valentine", "easter", "spooky", "horror")


def cfg():
    return cfg_hub()


def goc_nhac():
    return Path(cfg()["duong_dan"].get("nhac_mixkit") or (GOC_TAI_NGUYEN / "nhac-mixkit"))


def goc_sfx():
    return Path(cfg()["duong_dan"].get("sfx") or (GOC_TAI_NGUYEN / "sfx"))


def nguon_phu(loai, chi_bat=True):
    out = []
    for n in (cfg().get("nhac") or {}).get("nguon") or []:
        if n.get("loai") != loai or (chi_bat and not n.get("bat", True)):
            continue
        p = Path(str(n.get("duong_dan", "")))
        if p.is_dir() and p not in out:
            out.append(p)
    return out


def quet(folder, gioi_han=20000, het_gio=None):
    """Mọi file âm thanh trong thư mục (đệ quy, bỏ thư mục ẩn / bắt đầu bằng _). Dừng khi đủ gioi_han hoặc quá het_gio giây."""
    out, t0 = [], time.time()
    for dp, dns, fns in os.walk(folder):
        dns[:] = [d for d in dns if not d.startswith((".", "_"))]
        for f in fns:
            if f.lower().endswith(AM) and not f.startswith("."):
                out.append(Path(dp) / f)
        if len(out) >= gioi_han or (het_gio and time.time() - t0 > het_gio):
            break
    return out[:gioi_han]


# ---------------------------------------------------------------- NHẠC
def _doc_cache():
    try:
        return json.loads(CHI_MUC.read_text(encoding="utf-8"))
    except Exception:
        return {}


def thoi_luong(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, timeout=20)
    try:
        return float(r.stdout.strip().split()[0])
    except Exception:
        return 0.0


def nhac_phu():
    """Bài trong các thư mục nhạc thêm (đang bật): [{file, tieu_de, nhom:'chung', giay}]. Đo thời lượng 1 lần, lưu cache."""
    cache, doi, rows = _doc_cache(), False, []
    for folder in nguon_phu("nhac"):
        for p in quet(folder):
            try:
                st = p.stat()
            except OSError:
                continue
            k, sig = str(p), [st.st_size, int(st.st_mtime)]
            c = cache.get(k)
            if not c or c[:2] != sig:
                try:
                    d = thoi_luong(p)
                except Exception:
                    d = 0.0
                c = cache[k] = sig + [round(d, 2)]
                doi = True
            if c[2] > 0:
                rows.append({"file": k, "tieu_de": p.stem, "nhom": "chung", "giay": c[2]})
    if doi:
        try:
            CHI_MUC.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return rows


def nhac_mac_dinh():
    folder, f = goc_nhac(), goc_nhac() / "_phan-nhom.csv"
    if not f.exists():
        return []
    out = []
    for r in csv.DictReader(open(f, encoding="utf-8-sig")):
        try:
            m, s = r["thoi_luong"].split(":")
            g = int(m) * 60 + int(s)
        except Exception:
            g = 0
        if (folder / r["file"]).exists():
            out.append({"file": str(folder / r["file"]), "tieu_de": r.get("tieu_de", ""), "nhom": r["nhom"], "giay": g})
    return out


def chon_nhac(group, rng):
    """-> {"file","start","ten"} hoặc None (không có bài đủ dài thì để trống nhạc, không lỗi)."""
    def sach(rows):
        return [r for r in rows if r["giay"] >= TOI_THIEU_S
                and not any(w in (r["tieu_de"] + " " + os.path.basename(r["file"])).lower() for w in LE_NGOAI)]
    macdinh, phu = sach(nhac_mac_dinh()), sach(nhac_phu())
    pool = [r for r in macdinh if r["nhom"] == group] + phu
    pool = pool or [r for r in macdinh if r["nhom"] in ("tvc-doanh-nghiep", "vui-mua-sam")]
    if not pool:
        return None
    r = rng.choice(pool)
    return {"file": r["file"], "start": round(rng.uniform(0, max(0, r["giay"] * 0.5 - 25)), 1), "ten": r["tieu_de"]}


# ---------------------------------------------------------------- SFX
_TU_KHOA = [   # (nhóm đích, từ khoá) — khớp đầu tiên thắng; whoosh -> cả vut_nhe và vut_manh
    (("chup",), ("camera", "shutter")), (("go_phim",), ("typewriter", "keyboard", "typing")),
    (("tien",), ("coin", "money", "cash")), (("vo_tay",), ("applause", "clap")),
    (("lap_lanh",), ("sparkle", "twinkle", "glitter", "magic")), (("no_lon",), ("explosion", "boom", "blast")),
    (("vut_nhe", "vut_manh"), ("whoosh", "swoosh", "swish", "sweep", "transition")), (("keo_len",), ("riser", "swell")),
    (("dap",), ("impact", "slam", "thud", "punch", "hit")), (("ting",), ("ding", "bell", "chime", "notification")),
    (("dung",), ("correct", "success")), (("sai",), ("wrong", "error", "buzz", "fail")),
    (("bop",), ("pop", "click", "bubble", "tap", "blip")),
]
NHOM_SFX = ("vut_nhe", "vut_manh", "roi_phep", "dap", "no_lon", "keo_len", "bop", "go_phim", "chup", "ting", "lap_lanh", "dung", "sai",
            "tien", "tui_qua", "vo_tay")


def nhom_sfx(rel):
    """Đoán nhóm SFX từ đường dẫn tương đối (thư mục con + tên file)."""
    parts = [x.lower() for x in Path(rel).parts]
    for x in parts[:-1]:
        if x in NHOM_SFX:
            return [x]
    s = " ".join(parts)
    for nhom, tk in _TU_KHOA:
        if any(re.search(r"(?<![a-z])" + w, s) for w in tk):
            return list(nhom)
    return []


def sfx_phu():
    """[(đường dẫn tuyệt đối, [nhóm...])] của file trong các thư mục SFX thêm (đang bật) đoán được nhóm."""
    out = []
    for folder in nguon_phu("sfx"):
        for p in quet(folder):
            g = nhom_sfx(p.relative_to(folder))
            if g:
                out.append((str(p), g))
    return out


# ---------------------------------------------------------------- TRẠNG THÁI
_tt = {"t": 0, "v": None}


def trang_thai_mac_dinh(moi=False):
    """Kho mặc định đã cài chưa: số bài nhạc, số âm thanh, dung lượng (cache 60 giây)."""
    if not moi and _tt["v"] and time.time() - _tt["t"] < 60:
        return _tt["v"]
    n_nhac = n_sfx = tong = 0
    for goc, loai in ((goc_nhac(), "nhac"), (goc_sfx(), "sfx")):
        if not goc.is_dir():
            continue
        for p in quet(goc, gioi_han=100000):
            try:
                tong += p.stat().st_size
            except OSError:
                continue
            if loai == "nhac":
                n_nhac += 1
            else:
                n_sfx += 1
    _tt["v"] = {"cai": n_nhac > 0 or n_sfx > 0, "n_nhac": n_nhac, "n_sfx": n_sfx, "gb": round(tong / 1e9, 2), "mb": round(tong / 1e6)}
    _tt["t"] = time.time()
    return _tt["v"]


def dem_am(folder):
    """Đếm nhanh file âm thanh trong 1 thư mục thêm (dừng sau 2 giây / 5000 file)."""
    try:
        return len(quet(Path(folder), gioi_han=5000, het_gio=2))
    except OSError:
        return 0


# ---------------------------------------------------------------- TẢI GÓI MẶC ĐỊNH
# TODO: điền config.json -> nhac.goi_mac_dinh_url (+ goi_mac_dinh_sha256) khi gói đã đưa lên GitHub Release.
# Link có thể là 1 file .zip, hoặc file .json chỉ mục {"phan":[{"ten":"x.zip","sha256":"..","url":"(tuỳ chọn)"}]} nếu gói chia nhiều phần
# (GitHub giới hạn 2 GB mỗi file đính kèm). Không có nguồn tải nào khác.
GOC_ZIP = {"nhac-mixkit": goc_nhac, "sfx": goc_sfx}
HOP_LE_DUOI = AM + (".csv", ".json", ".txt", ".md")
TOI_DA_GIAI_NEN = 16 * 1024 ** 3


def _bao(cb, **kw):
    if cb:
        cb(kw)


def _tai_file(url, dich, cb, nhan):
    if urlparse(url).scheme != "https":
        raise ValueError("Link tải phải bắt đầu bằng https://")
    h = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": "xuong-video"})
    with urllib.request.urlopen(req, timeout=30) as r, open(dich, "wb") as f:
        tong, da = int(r.headers.get("Content-Length") or 0), 0
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            h.update(b)
            da += len(b)
            _bao(cb, buoc="tai", ghi=nhan, da=da, tong=tong)
    return h.hexdigest()


def giai_nen_an_toan(zip_path, cb=None):
    """Giải nén CHỈ vào nhac-mixkit/ và sfx/ (đường dẫn gốc trong config); chặn ../, ổ đĩa, đường dẫn tuyệt đối, symlink, đuôi lạ."""
    roots = {k: f().resolve() for k, f in GOC_ZIP.items()}
    with zipfile.ZipFile(zip_path) as z:
        ds = []
        for i in z.infolist():
            ten = i.filename.replace("\\", "/")
            if i.is_dir() or ten == "manifest.json":
                continue
            p = ten.split("/")
            if ten.startswith("/") or ":" in ten or ".." in p or "" in p or len(p) < 2 or p[0] not in roots:
                raise ValueError(f"Gói có đường dẫn không an toàn: {ten[:80]}")
            if (i.external_attr >> 16) & 0o170000 == 0o120000 or not ten.lower().endswith(HOP_LE_DUOI):
                raise ValueError(f"Gói có file không hợp lệ: {ten[:80]}")
            dich = roots[p[0]].joinpath(*p[1:]).resolve()
            if roots[p[0]] not in dich.parents:
                raise ValueError(f"Gói có đường dẫn không an toàn: {ten[:80]}")
            ds.append((i, dich))
        if sum(i.file_size for i, _ in ds) > TOI_DA_GIAI_NEN:
            raise ValueError("Gói giải nén quá lớn.")
        for n, (i, dich) in enumerate(ds, 1):
            if not (dich.exists() and dich.stat().st_size == i.file_size):     # đã có đúng cỡ thì giữ, không ghi đè
                dich.parent.mkdir(parents=True, exist_ok=True)
                with z.open(i) as src, open(dich, "wb") as out:
                    while True:
                        b = src.read(1 << 20)
                        if not b:
                            break
                        out.write(b)
            _bao(cb, buoc="giai-nen", ghi="Giải nén", da=n, tong=len(ds))
    return len(ds)


def tai_goi(url=None, sha256=None, cb=None):
    """Tải gói mặc định từ link trong config, kiểm sha256 (nếu có), giải nén vào tai-nguyen. cb(dict) báo tiến độ."""
    c = cfg().get("nhac") or {}
    url = (url or c.get("goi_mac_dinh_url") or "").strip()
    sha256 = (sha256 if sha256 is not None else c.get("goi_mac_dinh_sha256") or "").strip().lower()
    if not url:
        raise ValueError("Chưa có link tải — sẽ có khi đưa lên GitHub.")
    tmp = GOC_TAI_NGUYEN / "_tai"
    tmp.mkdir(parents=True, exist_ok=True)
    phan = [{"url": url, "sha256": sha256, "ten": "goi"}]
    if urlparse(url).path.lower().endswith(".json"):
        j = tmp / "chi-muc.json"
        _tai_file(url, j, None, "chỉ mục")
        phan = [{"url": p.get("url") or urljoin(url, p["ten"]), "sha256": (p.get("sha256") or "").lower(), "ten": p["ten"]}
                for p in json.loads(j.read_text(encoding="utf-8"))["phan"]]
        j.unlink()
    tong_file = 0
    for k, p in enumerate(phan, 1):
        z = tmp / f"phan{k}.zip"
        try:
            got = _tai_file(p["url"], z, cb, f"Tải phần {k}/{len(phan)}")
            if p["sha256"] and got != p["sha256"]:
                raise ValueError(f"Sai mã sha256 ở phần {k} — file tải về bị lỗi, thử lại.")
            tong_file += giai_nen_an_toan(z, cb)
        finally:
            z.unlink(missing_ok=True)
    _tt["v"] = None
    _bao(cb, buoc="xong", ghi="Xong", da=tong_file, tong=tong_file)
    return tong_file
