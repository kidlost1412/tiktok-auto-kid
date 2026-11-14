"""Tạo giọng ElevenLabs v4 kèm mốc thời gian từng từ (cho karaoke).
tao_giong(text_co_tag, voice_id, out_dir, ten) -> {"audio": path, "words": [{"w","s","e"}], "dur": s}
Khóa API đọc từ <thư mục dữ liệu>/.env, dự phòng .env gốc repo (không in ra)."""
import base64, hashlib, json, os, re, subprocess
from pathlib import Path

from dotenv import dotenv_values
from elevenlabs import ElevenLabs, VoiceSettings

import sys as _s0; from pathlib import Path as _P0
_s0.path.insert(0, str(_P0(__file__).resolve().parents[1] / "engine"))
from duong_dan import CODE, REPO, DATA as HUB, cfg as cfg_hub, cfg_tho, ghi_nguyen_tu
CFG = cfg_hub()
TEMPO = CFG["giong"]["toc_do"]
_client = None


class ThieuKhoaGiong(RuntimeError):
    """Chưa có khoá ElevenLabs (thông báo tiếng Việt, hiện thẳng cho chủ app)."""


def _khoa_giong():
    """Khoá ElevenLabs: biến môi trường → <thư mục dữ liệu>/.env → .env gốc repo. Đọc lại file mỗi lần (điền khoá xong không cần khởi động lại)."""
    key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    if key:
        return key
    for f in (Path(CFG["duong_dan"]["env_file"]), REPO / ".env"):
        try:
            if f.is_file():
                key = (dotenv_values(f).get("ELEVENLABS_API_KEY") or "").strip()
                if key:
                    return key
        except Exception:
            continue
    return ""


def co_khoa_giong():
    """True nếu đã có khoá ElevenLabs (không in, không gọi mạng)."""
    return bool(_khoa_giong())


def client():
    global _client
    if _client is None:
        key = _khoa_giong()
        if not key:
            raise ThieuKhoaGiong("Chưa điền khoá ElevenLabs (ELEVENLABS_API_KEY) trong file .env của thư mục dữ liệu hub "
                                 f"({CFG['duong_dan']['env_file']}) - điền khoá rồi chạy lại.")
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


def _mau_doc(goc):
    """'MIG 38' khớp cả 'MiG 38', 'Mig-38', 'MIG38' (không phân biệt hoa thường, nối bằng cách/gạch/chấm hoặc liền) — nguyên từ."""
    tu = re.findall(r"\w+", goc)
    if not tu:
        return re.compile(re.escape(goc), re.I)
    return re.compile(r"(?<!\w)" + r"[\s\-_.]*".join(re.escape(t) for t in tu) + r"(?!\w)", re.I)


def _khoa_tho(noi, voice_id):
    """Khoá theo NỘI DUNG (lời gửi đi + giọng + mô hình + độ ổn định) — lần chạy sau cùng lời/cùng giọng dùng lại bản đã mua, không phụ thuộc tên video."""
    g = CFG["giong"]
    return hashlib.sha1(f"{g['model']}|{g['stability']}|{voice_id}|{noi}".encode("utf-8")).hexdigest()[:16]


def _doc_tho(mp3, js):
    """Bản ElevenLabs đã lưu ngay sau khi mua → {"characters","starts","ends"}; thiếu/hỏng → None (khi đó mới phải mua lại)."""
    try:
        if mp3.is_file() and mp3.stat().st_size > 0 and js.is_file():
            a = json.loads(js.read_text(encoding="utf-8"))
            if a.get("characters") and len(a["characters"]) == len(a["starts"]) == len(a["ends"]):
                return a
    except Exception:
        pass
    return None


def tao_giong(text, voice_id, out_dir, ten, doc=None):
    """doc: {"TC01": "Tê Xê Không Một"} — chữ hiển thị → cách đọc cho ElevenLabs.
    Tiền ElevenLabs chỉ trả MỘT lần cho mỗi (lời, giọng): âm thanh gốc + mốc từng chữ được lưu xuống đĩa ngay khi API trả về, TRƯỚC mọi bước
    ffmpeg/ffprobe; bước hậu kỳ lỗi hay máy bị tắt giữa chừng thì lần chạy lại đọc từ bản đã lưu, không mua lại."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"{ten}.mp3"; meta = out_dir / f"{ten}.json"
    if final.exists() and meta.exists():
        return json.loads(meta.read_text(encoding="utf-8"))
    noi = text
    for goc, cach in sorted((doc or {}).items(), key=lambda kv: -len(kv[0])):
        noi = re.sub(_mau_doc(goc), lambda m, c=cach: c, noi)
    k = _khoa_tho(noi, voice_id)
    raw, raw_js = out_dir / f"_tho-{k}.mp3", out_dir / f"_tho-{k}.json"
    al = _doc_tho(raw, raw_js)
    if al is None:
        r = client().text_to_speech.convert_with_timestamps(
            voice_id=voice_id, text=noi, model_id=CFG["giong"]["model"], language_code="vi",
            output_format="mp3_44100_128",
            voice_settings=VoiceSettings(stability=CFG["giong"]["stability"], similarity_boost=0.75),
            request_options={"max_retries": 0})
        audio = base64.b64decode(r.audio_base_64)
        a = r.alignment or r.normalized_alignment
        al = {"characters": list(a.characters), "starts": list(a.character_start_times_seconds), "ends": list(a.character_end_times_seconds)} if a else None
        try:                                              # LƯU NGAY: mp3 trước, json (dấu hiệu "đủ bộ") sau cùng
            ghi_nguyen_tu(raw, audio)
            if al:
                ghi_nguyen_tu(raw_js, json.dumps(al, ensure_ascii=False))
        except Exception:
            raw.write_bytes(audio)                        # đĩa lỗi lặt vặt: vẫn đủ để ffmpeg chạy tiếp lần này
        if not al:
            raise RuntimeError("ElevenLabs không trả mốc thời gian từng chữ (đã lưu âm thanh gốc " + raw.name + ")")
    words = words_from_alignment(al["characters"], al["starts"], al["ends"])
    words = _gop_doc(words, doc)
    for w in words:
        w["s"] = round(w["s"] / TEMPO, 3); w["e"] = round(w["e"] / TEMPO, 3)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
                    f"atempo={TEMPO},loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100", "-b:a", "192k", str(final)], check=True)
    try:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)],
                                   capture_output=True, text=True).stdout)
    except ValueError:
        final.unlink(missing_ok=True)                     # file giọng dở dang không được coi là xong
        raise RuntimeError("ffprobe không đọc được độ dài giọng — âm thanh gốc vẫn còn, chạy lại sẽ không mua lại")
    info = {"audio": str(final), "words": words, "dur": round(dur, 3), "text": text, "voice_id": voice_id,
            "ky_tu": len(noi), "meta": str(meta)}                   # ký tự gửi ElevenLabs (tính phí theo ký tự)
    import datetime as _dt, su_kien as _sk
    _sk.noi_them(HUB / "lich-su" / "giong.csv", _sk.dong_csv([_dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ten, len(noi), round(dur, 2)]),
                 ma_hoa="utf-8-sig", dau=_sk.dong_csv(["luc", "ten", "ky_tu", "giay"]), giu_dong=4000, toi_da_byte=400_000)
    ghi_nguyen_tu(meta, json.dumps(info, ensure_ascii=False, indent=1))
    return info
