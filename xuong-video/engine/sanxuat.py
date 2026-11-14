"""HUB SẢN XUẤT — một lệnh ra cả lô video (ê-kíp AI 4 vai, xem ekip.py).
python engine\\sanxuat.py <ma-san-pham> <so-video>
python engine\\sanxuat.py <ma-san-pham> --lam-lai <file json danh sách>
Khâu: Claude CLI viết lời → ElevenLabs (mốc từng chữ) → đạo diễn dựng bảng → FFmpeg dựng nền → Remotion dựng lớp chữ → FFmpeg ghép → giám khảo.
Kết quả: ra\\<YYYY-MM-DD>\\*.mp4 + bang-ghi.csv ; lich-su\\ cập nhật để lần sau không lặp."""
import datetime, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from duong_dan import DATA as HUB, cfg as cfg_hub
CFG = cfg_hub()


def log(msg):
    line = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
    try:
        print(line, flush=True)
    except Exception:                      # console đóng / mã hoá lạ → vẫn ghi sổ
        pass
    from su_kien import noi_them           # nhật ký không bao giờ làm sập lô (file bị khoá → ghi tạm .cho-ghi); quá 1,5 MB → giữ 8000 dòng cuối
    noi_them(HUB / "lich-su" / "nhat-ky.txt", line + "\n", giu_dong=8000, toi_da_byte=1_500_000)


def music_pick(group, rng):
    # Kid 10/11: mặc định LUÔN dùng nhạc kho Mixkit; nhạc TikTok tạm bỏ (config "nhac_tiktok": true để bật lại)
    if group == "tiktok" or not group:
        if CFG.get("nhac_tiktok"):
            return None
        group = rng.choice(["que-acoustic", "vui-mua-sam", "tvc-doanh-nghiep", "chill-nen", "piano-nhe"])
    import kho_nhac                                 # kho mặc định + thư mục nhạc người dùng thêm (xem kho_nhac.py)
    return kho_nhac.chon_nhac(group, rng)


if __name__ == "__main__":
    (HUB / "lich-su").mkdir(exist_ok=True)
    from ekip import chay
    if len(sys.argv) > 3 and sys.argv[2] == "--lam-lai":      # sanxuat.py <ma> --lam-lai <file json danh sách>
        ds = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        chay(sys.argv[1], len(ds), log, music_pick, lam_lai=ds)
    else:
        chay(sys.argv[1], int(sys.argv[2]), log, music_pick)
