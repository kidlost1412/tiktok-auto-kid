"""Chọn nhát cắt nào được chuyển cảnh MẠNH (khung "chữ theo lời", v10 Kid duyệt: ~6 nhát/21 s, chỉ ở chỗ đổi ý). Hàm thuần, không ffmpeg."""
KIEU = ("whip", "flash", "glitch", "zoom")
SFX_TEN = {"whip": "slideleft", "zoom": "zoomin"}      # tên chuyển cảnh có chuyển động → sfx.py cho tiếng vút; glitch/flash để cắt im (không chồng tiếng)


def chon(cuts, total, doi_y, phu, rng, gap=2.0, moi=3.5, toi_da=6):
    """cuts: giây các nhát cắt của base; doi_y: giây khối đổi vai (warn→brand...); phu: giây các khối/câu mới khác.
    → [(giây, kiểu, hướng ±1)] theo thời gian: ≤ toi_da, cách nhau ≥ gap, không ở 0,5 s đầu / 1,5 s cuối, không lặp kiểu liền nhau."""
    n = min(toi_da, int(total / moi))
    ung = [c for c in cuts if 0.5 <= c <= total - 1.5]
    gd = lambda c: min([abs(c - t) for t in doi_y] + [abs(c - t) + 0.5 for t in phu] + [99.0])
    ra = []
    for c in sorted(ung, key=gd):
        if len(ra) >= n:
            break
        if all(abs(c - x) >= gap for x in ra):
            ra.append(c)
    out, truoc = [], None
    for c in sorted(ra):
        k = rng.choice([x for x in KIEU if x != truoc])
        out.append((round(c, 3), k, rng.choice((-1, 1)))); truoc = k
    return out
