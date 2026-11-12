"""Offline audio mix for the V6 preview (approximation of what the CapCut build will contain).

voice stem (as is) + music (src_in_f, level = voice.stem_lufs + music.gain_rel_voice_db measured on the used segment,
fades) + SFX (adelay at f, gain_db) -> amix (no normalisation) -> loudnorm two-pass linear to mix.target_lufs / TP.
Writes a 48 kHz stereo WAV and prints before/after measurements.

python preview_audio.py --script kich-ban.json --voice voice.wav --out mix.wav
"""
import argparse
import json
import re
import subprocess
import sys

import numpy as np

FPS = 30
SR = 48000


def decode(args_in, af):
    """One layer as float32 stereo 48 kHz samples (shape n x 2), filters applied, no delay."""
    p = subprocess.run(["ffmpeg", "-v", "error", *args_in, "-af", f"aformat=sample_fmts=flt:sample_rates={SR}:channel_layouts=stereo,{af}",
                        "-f", "f32le", "-"], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"decode failed: {' '.join(map(str, args_in))}\n{p.stderr.decode('utf-8', 'replace')[-1000:]}")
    return np.frombuffer(p.stdout, np.float32).reshape(-1, 2)


def add_layer(buf, x, off):
    """Sum x into buf starting at sample off; whatever runs past the end of buf is cut (like atrim to duration)."""
    n = max(0, min(len(x), len(buf) - off))
    buf[off:off + n] += x[:n]


def write_f32(buf, path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "pcm_f32le", path],
                       input=np.ascontiguousarray(buf).tobytes(), capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"cannot write {path}: {p.stderr.decode('utf-8', 'replace')[-500:]}")


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(map(str, cmd))}\n{p.stderr[-1000:]}")
    return p


def lufs(args_in, af="anull"):
    p = run(["ffmpeg", "-hide_banner", "-nostats", *args_in, "-af", af + ",ebur128=peak=true", "-f", "null", "-"])
    tail = p.stderr[p.stderr.rindex("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", tail).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail).group(1))
    return i, tp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.script, encoding="utf-8-sig") as fh:
        s = json.load(fh)
    dur = s["duration_f"] / FPS
    stem = s["voice"]["stem_lufs"]
    mu, mix = s["music"], s["mix"]
    # Layers are decoded one by one (trim/fades/gain applied, NO delay) and summed here at their sample offsets:
    # adelay+amix with many inputs placed short late SFX at t=0 nondeterministically (FFmpeg 9.0).
    n_out = round(dur * SR)
    buf = np.zeros((n_out, 2), np.float32)
    add_layer(buf, decode(["-i", a.voice], "anull"), 0)
    if mu.get("path"):
        seg = ["-ss", f"{mu['src_in_f'] / FPS:.4f}", "-t", f"{dur:.4f}", "-i", mu["path"]]
        m_i, _ = lufs(seg)
        gain = stem + mu["gain_rel_voice_db"] - m_i
        print(f"music segment {m_i:.1f} LUFS -> gain {gain:+.1f} dB (target {stem + mu['gain_rel_voice_db']:.1f} LUFS)")
        fo = mu["fade_out_f"] / FPS
        add_layer(buf, decode(seg, f"volume={gain:.3f}dB,afade=t=in:d={mu['fade_in_f'] / FPS:.4f},afade=t=out:st={dur - fo:.4f}:d={fo:.4f}"), 0)
    for sx in s.get("sfx", []):
        add_layer(buf, decode(["-i", sx["file"]], f"volume={sx['gain_db']}dB"), round(sx["f"] / FPS * SR))
    pre = a.out + ".pre.wav"
    write_f32(buf, pre)
    i0, tp0 = lufs(["-i", pre])
    print(f"pre-normalisation mix: {i0:.1f} LUFS, peak {tp0:.1f} dBFS")
    tgt, tp = mix["target_lufs"], mix["true_peak_max_dbtp"]
    p = run(["ffmpeg", "-hide_banner", "-nostats", "-i", pre, "-af", f"loudnorm=I={tgt}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"])
    st = json.loads(re.findall(r"\{[^{}]*\}", p.stderr)[-1])
    ln = (f"loudnorm=I={tgt}:TP={tp}:LRA=11:measured_I={st['input_i']}:measured_TP={st['input_tp']}:measured_LRA={st['input_lra']}"
          f":measured_thresh={st['input_thresh']}:offset={st['target_offset']}:linear=true")
    run(["ffmpeg", "-v", "error", "-y", "-i", pre, "-af", ln, "-ar", "48000", "-c:a", "pcm_s16le", a.out])
    i1, tp1 = lufs(["-i", a.out])
    print(f"final mix: {i1:.1f} LUFS, peak {tp1:.1f} dBFS (target {tgt} / TP <= {tp})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
