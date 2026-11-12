"""python -X utf8 -m unittest test_preview_audio -v   (from tc01-remotion/scripts)

Regression: with adelay+amix and many inputs, FFmpeg 9.0 mixed a short late SFX at t=0 instead of its frame (TC01 V9:
notify-pluck at f929 of 971 missing). 14 SFX on the V9 schedule, silent voice; the late 0.1 s SFX must start at its
frame within 1 ms, nothing may sound before the first SFX's end except that SFX, and 5 runs must be identical.
PREVIEW_AUDIO=<path> runs the same test against another copy of preview_audio.py (used to show the old code fails).
"""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
PA = os.environ.get("PREVIEW_AUDIO", str(HERE / "preview_audio.py"))
SR = 48000


def ff(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)


def pcm(p):
    b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(b, np.float32).reshape(-1, 2)


class ManySfx(unittest.TestCase):
    def test_late_short_sfx_at_its_frame_deterministic(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "trộn #1, a"
            d.mkdir()
            voice = d / "voice.wav"
            ff("-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo", "-t", "32.4", "-c:a", "pcm_s16le", str(voice))
            files = {}
            for k, dur, hz in (("long", 0.7, 300), ("mid", 0.48, 500), ("short", 0.1, 1000)):
                files[k] = d / f"{k} {dur}s.wav"
                ff("-f", "lavfi", "-i", f"sine=f={hz}:d={dur}:sample_rate={SR}", "-ac", "2", "-c:a", "pcm_s16le", str(files[k]))
            plan = [(0, "long"), (17, "long"), (60, "mid"), (311, "short"), (382, "mid"), (406, "long"), (446, "short"), (467, "short"),
                    (559, "mid"), (610, "long"), (733, "short"), (889, "long"), (929, "short"), (950, "short")]
            script = {"duration_f": 971, "voice": {"stem_lufs": -20.0}, "music": {"path": None}, "mix": {"target_lufs": -14.0, "true_peak_max_dbtp": -1.0},
                      "sfx": [{"f": f, "file": str(files[k]), "gain_db": 0} for f, k in plan]}
            sp = d / "kịch bản.json"
            sp.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
            first0 = pcm(files["long"])
            onsets = []
            for run in range(5):
                out = d / f"mix{run}.wav"
                subprocess.run([sys.executable, "-X", "utf8", PA, "--script", str(sp), "--voice", str(voice), "--out", str(out)], check=True, capture_output=True)
                x = pcm(str(out) + ".pre.wav")
                self.assertEqual(len(x), 971 * 1600)
                # before frame 17 only the frame-0 SFX sounds: the pre-mix equals that file there
                n = 17 * 1600
                extra = np.abs(x[:n] - np.pad(first0, ((0, max(0, n - len(first0))), (0, 0)))[:n]).max()
                self.assertLess(extra, 1e-3, f"run {run}: something extra mixed in before frame 17 (max diff {extra:.3f})")
                a = np.abs(x[915 * 1600:]).max(axis=1)
                first = 915 * 1600 + int(np.argmax(a > 1e-4)) if (a > 1e-4).any() else -1
                onsets.append(first)
                self.assertLessEqual(abs(first - 929 * 1600), 48, f"run {run}: late SFX onset at sample {first}, expected {929 * 1600}")
                self.assertGreater(np.abs(x[950 * 1600:953 * 1600]).max(), 0.05, f"run {run}: last SFX missing")
            self.assertEqual(len(set(onsets)), 1, onsets)


if __name__ == "__main__":
    unittest.main()
