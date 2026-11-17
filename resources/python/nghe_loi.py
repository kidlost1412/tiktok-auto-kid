"""Nghe lời nói trong video (tiếng Việt) bằng Whisper chạy ngay trên máy, miễn phí.

Dùng: python nghe_loi.py <video> <thư mục model> [tên model]
In ra JSON: {"ok": true, "text": "...", "giay": 12.3, "thiet_bi": "cuda|cpu", "model": "..."}
Không có tiếng nói thì text rỗng. Lỗi thì {"ok": false, "error": "..."} và mã thoát 1.
Thử card đồ hoạ (CUDA) trước, không được thì chạy bằng CPU.
"""

import json
import os
import sys
import time


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    if len(sys.argv) < 3:
        print(json.dumps({"ok": False, "error": "thiếu đường dẫn video hoặc thư mục model"}))
        return 1

    video, cache = sys.argv[1], sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "large-v3-turbo"
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

    from faster_whisper import WhisperModel

    start = time.time()
    errors = []

    for device, compute in (("cuda", "float16"), ("cpu", "int8")):
        try:
            model = WhisperModel(name, device=device, compute_type=compute, download_root=cache)
            segments, _info = model.transcribe(
                video,
                language="vi",
                vad_filter=True,
                beam_size=5,
                condition_on_previous_text=False,
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            print(json.dumps({"ok": True, "text": text, "giay": round(time.time() - start, 1), "thiet_bi": device, "model": name, "loi_khac": errors}, ensure_ascii=False))
            return 0
        except Exception as e:  # noqa: BLE001 - thử thiết bị kế tiếp
            errors.append(f"{device}: {str(e)[:200]}")

    print(json.dumps({"ok": False, "error": " | ".join(errors)[:400]}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
