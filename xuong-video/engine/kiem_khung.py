"""Tìm khung hỏng: quá tối, phẳng một màu (xám/đen trống). python kiem_khung.py <video> [fps]
In các khoảng thời gian có vấn đề; dùng trong kiểm tự động sau khi dựng."""
import re, subprocess, sys


def scan(path, fps=5):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vf", f"fps={fps},signalstats,metadata=print", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    bad, t, vals = [], None, {}
    for line in r.stderr.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1)); vals = {}
            continue
        m = re.search(r"lavfi\.signalstats\.(YAVG|YMIN|YMAX)=([\d.]+)", line)
        if m and t is not None:
            vals[m.group(1)] = float(m.group(2))
            if len(vals) == 3:
                flat = vals["YMAX"] - vals["YMIN"] < 60
                dark = vals["YAVG"] < 35
                if flat or dark:
                    bad.append((round(t, 1), "phẳng" if flat else "tối", vals["YAVG"]))
                vals = {"_": 1}
    return bad


if __name__ == "__main__":
    for b in scan(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5):
        print(b)
