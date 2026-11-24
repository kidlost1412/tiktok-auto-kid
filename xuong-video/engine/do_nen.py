"""Đo độ sáng nền sau chữ trên khung nền đã dựng (Kid 23/11, bài "tương phản sáng tối"): chữ trắng đọc được nhờ nền TỐI hơn chữ,
không nhờ viền mảnh hay khác màu. Nền sáng (can trắng, trời, tường) hoặc rối → đặt cờ để lớp chữ lót nền tối:
  phụ đề: line["nen"] = True → Caption.tsx thêm dải tối mờ;  khối chữ trần: block["nen_toi"] = True → Blocks.tsx thêm vùng tối mờ phía sau.
Không gọi AI. Lỗi đo (thiếu ffmpeg/khung) → bỏ qua, không chặn dựng."""
import subprocess

SANG = 110          # độ sáng trung bình 0–255 vùng sau chữ; trên mức này chữ trắng bắt đầu chìm (đo lại 23/11: cỏ lá sau phụ đề 90–128 đã khó đọc)
ROI = 44            # độ lệch chuẩn (ảnh thu 48 px): nền lổn nhổn lá, cỏ 45–54 cũng nuốt chữ
FPS = 30.0
# khối có nền riêng (thẻ, bảng, nút) không cần lót thêm
CO_NEN_RIENG = {"checklist", "so_sanh", "bang_qua", "hop_qua", "nut_gio_hang", "the_qua", "lower_third", "hook_tem", "hook_bang", "canh_bao", "dai_chay"}


def do_sang(video, t, rect, ffmpeg="ffmpeg"):
    """(trung bình, lệch chuẩn) độ sáng vùng rect=(x0,y0,x1,y1) trên khung 1080x1920 ở giây t; None nếu không đo được."""
    x0, y0, x1, y1 = [int(max(0, v)) for v in rect]
    w, h = max(2, min(1080, x1) - x0), max(2, min(1920, y1) - y0)
    try:
        r = subprocess.run([ffmpeg, "-v", "error", "-ss", f"{max(0.0, t):.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"crop={w}:{h}:{x0}:{y0},scale=48:-2,format=gray", "-f", "rawvideo", "-"],
                           capture_output=True, timeout=30)
        px = r.stdout
    except Exception:
        return None
    if not px:
        return None
    tb = sum(px) / len(px)
    return tb, (sum((p - tb) ** 2 for p in px) / len(px)) ** 0.5


def can_lot(do):
    return bool(do) and (do[0] > SANG or do[1] > ROI)


def gan_nen(base, lines, cap, blocks, cao_khoi, do=do_sang):
    """Đặt cờ nền tối cho phụ đề/khối chữ nằm trên nền sáng hoặc rối. → số chỗ được lót."""
    n = 0
    if lines and cap and cap.get("bat") is not False and cap.get("style") != "hop_mo":
        cy = float(cap.get("center_y") or 1490)
        for ln in lines:
            if can_lot(do(base, (ln["f0"] + ln["f1"]) / 2 / FPS, (160, cy - 50, 920, cy + 50))):
                ln["nen"] = True; n += 1
    for b in blocks or []:
        if b.get("loai") in CO_NEN_RIENG:
            continue
        top = float(b.get("top", 250)); cao = cao_khoi.get(b.get("loai"), 260)
        if can_lot(do(base, (b["f0"] + min(b["f1"], b["f0"] + 30)) / 2 / FPS, (140, top, 940, top + cao))):
            b["nen_toi"] = True; n += 1
    return n
