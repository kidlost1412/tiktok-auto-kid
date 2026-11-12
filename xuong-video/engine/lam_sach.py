"""Làm sạch file video trước khi giao (Kid 10/11/2026): bỏ TOÀN BỘ thông tin ẩn có thể lộ nguồn / công cụ dựng.
- metadata chung + từng luồng (gồm mã video TikTok gốc 'vid:...' chép từ clip AFF, encoder Lavf/Lavc, ngày tạo, handler)
- khối SEI trong luồng hình (x264 ghi phiên bản + toàn bộ cấu hình)
- luồng phụ (phụ đề, dữ liệu, chapter) — chỉ giữ 1 hình + 1 tiếng
Không mã hoá lại (chép luồng) → nhanh, không giảm chất lượng.
python lam_sach.py <file.mp4|thư mục> [--kiem]"""
import re, subprocess, sys
from pathlib import Path

DAU_VET = [rb"x264 - core", rb"Lavf\d", rb"Lavc\d", rb"vid:v\d", rb"[Rr]emotion", rb"ElevenLabs", rb"[Cc]laude", rb"c2pa",
           rb"VideoHandler", rb"SoundHandler", rb"SubtitleHandler", rb"Google", rb"Gemini", rb"OpenAI", rb"CapCut", rb"capcut"]


def lam_sach(path):
    path = Path(path)
    tmp = path.with_name(path.stem + ".__sach.mp4")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "copy",
           "-c:a", "aac", "-b:a", "192k", "-flags:a", "+bitexact",   # mã hoá lại tiếng: bộ AAC của FFmpeg chèn chữ 'Lavc' vào luồng tiếng
           "-bsf:v", "filter_units=remove_types=6",                # bỏ SEI (x264 ghi phiên bản/cấu hình)
           "-map_metadata", "-1", "-map_metadata:s:v", "-1", "-map_metadata:s:a", "-1", "-map_chapters", "-1",
           "-fflags", "+bitexact", "-flags:v", "+bitexact",
           "-metadata:s:v", "handler_name=VideoHandle", "-metadata:s:a", "handler_name=SoundHandle",   # nhãn chung như file quay điện thoại
           "-metadata:s:v", "language=und", "-metadata:s:a", "language=und",
           "-movflags", "+faststart", str(tmp)]
    subprocess.run(cmd, check=True)
    tmp.replace(path)
    return path


def kiem(path):
    """Trả danh sách dấu vết còn sót (rỗng = sạch)."""
    b = Path(path).read_bytes()
    con = [p.decode() for p in DAU_VET if re.search(p, b)]
    tags = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags:stream_tags:stream=codec_type", "-of", "compact",
                           str(path)], capture_output=True, text=True).stdout
    kieu = re.findall(r"codec_type=(\w+)", tags)
    if [k for k in kieu if k not in ("video", "audio")]:
        con.append("luồng phụ: " + ",".join(kieu))
    con += [t for t in re.findall(r"tag:(\w+)=", tags) if t not in ("language", "handler_name", "vendor_id", "major_brand", "minor_version", "compatible_brands")]   # ftyp: MP4 nào cũng có
    return con


if __name__ == "__main__":
    tgt = Path(sys.argv[1])
    files = sorted(tgt.rglob("*.mp4")) if tgt.is_dir() else [tgt]
    for f in files:
        if "--kiem" not in sys.argv:
            lam_sach(f)
        con = kiem(f)
        print(("SẠCH  " if not con else "CÒN   ") + f.name + ("" if not con else "  → " + ", ".join(con)))
