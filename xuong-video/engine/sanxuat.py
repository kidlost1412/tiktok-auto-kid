"""HUB SẢN XUẤT — một lệnh ra cả lô video.
python engine\\sanxuat.py <ma-san-pham> <so-video>
Khâu: Claude CLI viết lời → ElevenLabs (mốc từng chữ) → FFmpeg dựng nền → Remotion dựng lớp chữ DT Phudu → FFmpeg ghép.
Kết quả: ra\\<YYYY-MM-DD>\\*.mp4 + bang-ghi.csv ; lich-su\\ cập nhật để lần sau không lặp."""
import csv, datetime, json, math, random, re, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from viet_loi import viet                      # noqa: E402
from giong import tao_giong                    # noqa: E402
from dung_remotion import chuan_bi, dung_lo   # noqa: E402
from kiem_khung import scan                    # noqa: E402
from cong_thuc import chuan_hoa                # noqa: E402

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
CFG = cfg_hub()
LO_DUNG = 10   # dựng lớp chữ theo từng nhóm 10 video để thấy tiến độ


def log(msg):
    line = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(HUB / "lich-su" / "nhat-ky.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def music_pick(group, rng):
    # Kid 10/11: mặc định LUÔN dùng nhạc kho Mixkit; nhạc TikTok tạm bỏ (config "nhac_tiktok": true để bật lại)
    if group == "tiktok" or not group:
        if CFG.get("nhac_tiktok"):
            return None
        group = rng.choice(["que-acoustic", "vui-mua-sam", "tvc-doanh-nghiep", "chill-nen", "piano-nhe"])
    import kho_nhac                                 # kho mặc định + thư mục nhạc người dùng thêm (xem kho_nhac.py)
    return kho_nhac.chon_nhac(group, rng)


def prepare(task, shots, kho):
    """Dựng nền 1 video (chạy song song nhiều luồng)."""
    try:
        job, info = chuan_bi(task["plan"], task["voice"], shots, kho, task["work"], task["music"])
    except Exception as e:
        log(f"  dựng nền lỗi {task['fname']}: {str(e)[-200:]}")
        return None
    job["out"] = task["out"]
    row = [task["fname"], task["goc"], task["giong"], task["music"]["ten"] if task["music"] else "CHỌN NHẠC TIKTOK", info["thoi_luong"],
           info["phu_de"], info.get("mau_nhan"), info["chuyen_canh"], info["chuyen_dong"], info["mau"], info["the_mo"], info["the_chot"],
           task["loi"], " | ".join(info.get("canh", [])), info.get("cong_thuc", ""), " > ".join(info.get("khoi", [])), info.get("sfx", ""),
           info.get("atmos", ""), " ".join(info.get("bo_cuc", [])), info.get("sfx_lich", ""), "", "", ""]
    style = {k: info.get(k) for k in ("cong_thuc", "phu_de", "mau_nhan", "chuyen_canh", "chuyen_dong", "mau", "the_mo", "the_chot", "sfx")}
    return {"job": job, "row": row, "style": style}


def flush(tasks, out_dir, writer, fsheet, made, total, shots, kho):
    if not tasks:
        return made
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:   # 2 luồng: máy 16 GB, 3 luồng từng hết bộ nhớ
        pending = [p for p in ex.map(lambda t: prepare(t, shots, kho), tasks) if p]
    tasks.clear()
    done = set(dung_lo([p["job"] for p in pending], out_dir / "_tam" / "_public", log))
    for p in pending:
        if p["job"]["out"] in done:
            bad = scan(p["job"]["out"])
            if bad:
                p["row"][-1] = f"KIỂM: khung {bad[0][1]} ở {bad[0][0]}s ({len(bad)} chỗ)"
                log(f"  cảnh báo {Path(p['job']['out']).name}: {p['row'][-1]}")
            writer.writerow(p["row"]); fsheet.flush()
            with open(HUB / "lich-su" / "phong-cach.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(p["style"], ensure_ascii=False) + "\n")
            made += 1
            log(f"  [{made}/{total}] {Path(p['job']['out']).name}")
        else:
            log(f"  LỖI dựng chữ: {Path(p['job']['out']).name}")
    return made


def main(ma_sp, so_video):
    (HUB / "lich-su").mkdir(exist_ok=True)
    if CFG.get("che_do", "ekip") == "ekip":       # Kid 10/11/2026: ê-kíp AI 4 vai
        from ekip import chay
        return chay(ma_sp, so_video, log, music_pick)
    day = datetime.date.today().isoformat()
    out_dir = Path(CFG["duong_dan"]["ra"]) / day
    (out_dir / "_giong").mkdir(parents=True, exist_ok=True)
    sp = json.loads((HUB / "san-pham" / ma_sp / "san-pham.json").read_text(encoding="utf-8"))
    shots = json.loads((HUB / "san-pham" / ma_sp / "canh.json").read_text(encoding="utf-8"))
    per = CFG["lo"]["video_moi_giong"]
    log(f"BẮT ĐẦU {ma_sp}: {so_video} video ← {math.ceil(so_video / per)} lời × {per} cách dựng")
    scripts = viet(ma_sp, math.ceil(so_video / per), log)
    log(f"Đã có {len(scripts)} lời đạt kiểm")
    sheet = out_dir / "bang-ghi.csv"
    if sheet.exists() and "bo_cuc" not in sheet.read_text(encoding="utf-8-sig").splitlines()[0]:
        sheet = out_dir / "bang-ghi-v2.csv"      # bảng cũ thiếu cột mới → ghi bảng riêng, không làm lệch cột
    new = not sheet.exists()
    fsheet = open(sheet, "a", newline="", encoding="utf-8-sig")
    w = csv.writer(fsheet)
    if new:
        w.writerow(["file", "goc", "giong", "nhac", "thoi_luong", "phu_de", "mau_nhan", "chuyen_canh", "chuyen_dong", "mau",
                    "the_mo", "the_chot", "loi", "canh", "cong_thuc", "khoi", "sfx", "khong_khi", "bo_cuc", "lich_sfx", "luot_xem", "don", "ghi_chu"])
    sig_file = HUB / "lich-su" / f"chu-ky-{day}.txt"            # chống lặp phong cách trong ngày
    used_sigs = set(sig_file.read_text(encoding="utf-8").split()) if sig_file.exists() else set()
    made, pending, queued = 0, [], 0
    for sc in scripts:
        if queued >= so_video:
            break
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        vname = f"{ma_sp}-{sc['goc']}-{sc['giong']}-{stamp}"
        try:
            voice = tao_giong(sc["text"], CFG["giong"]["danh_sach"][sc["giong"]], out_dir / "_giong", vname)
        except Exception as e:
            log(f"  giọng lỗi ({sc['goc']}): {type(e).__name__}"); continue
        if voice["dur"] > CFG["video"]["thoi_luong_max"] - 0.7:   # đường cũ (che_do khác ekip)
            log(f"  bỏ {sc['goc']}: giọng {voice['dur']} s quá dài"); continue
        for j in range(per):
            if queued >= so_video:
                break
            rng = random.Random(f"{vname}-{j}")
            st = chuan_hoa(dict(sc["phong_cach"][j % len(sc["phong_cach"])]), rng, used_sigs)
            st["_qua"] = sp.get("qua_tang", [])
            sig_file.write_text("\n".join(sorted(used_sigs)), encoding="utf-8")
            music = music_pick(st.get("nhac"), rng)
            tag = "MIXKIT" if music else "CHON-NHAC-TIKTOK"
            fname = f"{ma_sp}_{sc['goc']}_{sc['giong']}_{tag}_{datetime.datetime.now():%Y%m%d-%H%M%S}-{j+1}.mp4"
            plan = {"seed": rng.randint(1, 10**9), "phong_cach": st, "canh": sc["canh"], "dong": sc.get("dong"),
                    "ten_thuong_hieu": sp["ten_goi"].upper()}
            pending.append({"plan": plan, "voice": voice, "music": music, "work": out_dir / "_tam" / "_public" / f"{vname}-{j}",
                            "out": str(out_dir / fname), "fname": fname, "goc": sc["goc"], "giong": sc["giong"],
                            "loi": re.sub(r"\[[^\]]*\]\s*", "", sc["text"])})
            queued += 1
            if len(pending) >= LO_DUNG:
                made = flush(pending, out_dir, w, fsheet, made, so_video, shots, sp["kho_video"])
        with open(HUB / "lich-su" / "cau-da-dung.txt", "a", encoding="utf-8") as f:
            for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\[[^\]]*\]", "", sc["text"]).strip()):
                if s.strip():
                    f.write(s.strip() + "\n")
    made = flush(pending, out_dir, w, fsheet, made, so_video, shots, sp["kho_video"])
    fsheet.close()
    shutil.rmtree(out_dir / "_tam", ignore_errors=True)
    log(f"XONG: {made} video tại {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[2] == "--lam-lai":      # sanxuat.py <ma> --lam-lai <file json danh sách>
        (HUB / "lich-su").mkdir(exist_ok=True)
        from ekip import chay
        ds = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        chay(sys.argv[1], len(ds), log, music_pick, lam_lai=ds)
    else:
        main(sys.argv[1], int(sys.argv[2]))
