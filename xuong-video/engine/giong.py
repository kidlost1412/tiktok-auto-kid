"""Tạo giọng ElevenLabs v4 kèm mốc thời gian từng từ (cho karaoke).
tao_giong(text_co_tag, voice_id, out_dir, ten) -> {"audio": path, "words": [{"w","s","e"}], "dur": s}
Khóa API đọc từ <thư mục dữ liệu>/.env (không in ra)."""
import base64, json, os, re, subprocess
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs, VoiceSettings

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, DATA as HUB, cfg as cfg_hub, cfg_tho
CFG = cfg_hub()
TEMPO = CFG["giong"]["toc_do"]
_client = None


def client():
    global _client
    if _client is None:
        load_dotenv(CFG["duong_dan"]["env_file"])
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise RuntimeError("Thiếu ELEVENLABS_API_KEY trong .env")
        _client = ElevenLabs(api_key=key, timeout=120)
    return _client


def words_from_alignment(chars, starts, ends):
    """Gộp ký tự thành từ, bỏ phần [tag]."""
    words, cur, s, e, in_tag = [], "", None, None, False
    for ch, a, b in zip(chars, starts, ends):
        if ch == "[":
            in_tag = True
        if in_tag:
            if ch == "]":
                in_tag = False
            continue
        if ch.isspace():
            if cur:
                words.append({"w": cur, "s": s, "e": e}); cur = ""
            continue
        if not cur:
            s = a
        cur += ch; e = b
    if cur:
        words.append({"w": cur, "s": s, "e": e})
    # bỏ từ chỉ có dấu câu, gắn dấu vào từ trước
    out = []
    for w in words:
        if re.fullmatch(r"[\W_…]+", w["w"]) and out:
            out[-1]["w"] += w["w"]; out[-1]["e"] = w["e"]
        else:
            out.append(w)
    return out


def _gop_doc(words, doc):
    """Từ đọc thay (vd 'Tê Xê Không Một') → gộp lại thành 1 từ hiển thị gốc ('TC01') giữ mốc thời gian."""
    norm = lambda x: re.sub(r"[^\w]", "", x.lower())
    for goc, noi in (doc or {}).items():
        sp = [norm(x) for x in noi.split()]
        n, i, out = len(sp), 0, []
        while i < len(words):
            if [norm(w["w"]) for w in words[i:i + n]] == sp:
                tail = re.search(r"[^\w]*$", words[i + n - 1]["w"]).group(0)
                out.append({"w": goc + tail, "s": words[i]["s"], "e": words[i + n - 1]["e"]}); i += n
            else:
                out.append(words[i]); i += 1
        words = out
    return words


def tao_giong(text, voice_id, out_dir, ten, doc=None):
    """doc: {"TC01": "Tê Xê Không Một"} — chữ hiển thị → cách đọc cho ElevenLabs."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / f"{ten}-raw.mp3"; final = out_dir / f"{ten}.mp3"; meta = out_dir / f"{ten}.json"
    if final.exists() and meta.exists():
        return json.loads(meta.read_text(encoding="utf-8"))
    noi = text
    for goc, cach in (doc or {}).items():
        noi = re.sub(re.escape(goc), cach, noi, flags=re.I)
    r = client().text_to_speech.convert_with_timestamps(
        voice_id=voice_id, text=noi, model_id=CFG["giong"]["model"], language_code="vi",
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(stability=CFG["giong"]["stability"], similarity_boost=0.75),
        request_options={"max_retries": 0})
    raw.write_bytes(base64.b64decode(r.audio_base_64))
    al = r.alignment or r.normalized_alignment
    words = words_from_alignment(al.characters, al.character_start_times_seconds, al.character_end_times_seconds)
    words = _gop_doc(words, doc)
    for w in words:
        w["s"] = round(w["s"] / TEMPO, 3); w["e"] = round(w["e"] / TEMPO, 3)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
                    f"atempo={TEMPO},loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100", "-b:a", "192k", str(final)], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)],
                               capture_output=True, text=True).stdout)
    info = {"audio": str(final), "words": words, "dur": round(dur, 3), "text": text, "voice_id": voice_id,
            "ky_tu": len(noi), "meta": str(meta)}                   # ký tự gửi ElevenLabs (tính phí theo ký tự)
    try:
        import csv as _csv, datetime as _dt
        fl = HUB / "lich-su" / "giong.csv"; moi = not fl.exists()
        with open(fl, "a", newline="", encoding="utf-8-sig") as fh:
            w = _csv.writer(fh)
            if moi:
                w.writerow(["luc", "ten", "ky_tu", "giay"])
            w.writerow([_dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ten, len(noi), round(dur, 2)])
    except Exception:
        pass
    meta.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info
