"""Frame style picker + requester taste memory (frame-styles/catalog.json, profile gu.frame_styles).

python frame_style.py pick --profile <profile.json> [--tags card brand ...]
python frame_style.py mark --profile <profile.json> --style <id> (--liked | --rejected | --clear)
python frame_style.py list [--profile <profile.json>]

Taste lives in the requester profile (workflow-data/profiles/<requester>.json) under gu.frame_styles =
{"liked": [...], "rejected": [...]}. pick never returns a rejected style; among styles that carry every --tag it returns
a liked one first (catalog order), else the first unmarked one. Nothing left -> exit 1 with the reason.
mark moves a style between liked/rejected (an id is never in both). Writes are atomic: an exclusive "<profile>.lock" file,
a timestamped copy "<profile>.bak-frame-style-<stamp>" of the previous bytes (the recovery path), a temp file in the same
folder, os.replace, then a re-read check. Every other key of the profile is kept as is. Prints one JSON line.
"""
import argparse, json, os, shutil, sys, time
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "frame-styles" / "catalog.json"


class StyleError(Exception):
    pass


def load_catalog(path=CATALOG):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_profile(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise StyleError(f"profile not found: {path}")


def taste(profile):
    fs = (profile.get("gu") or {}).get("frame_styles") or {}
    return list(fs.get("liked") or []), list(fs.get("rejected") or [])


def pick(catalog, profile, tags=()):
    liked, rejected = taste(profile)
    ok = [s for s in catalog["styles"] if all(t in s["tags"] for t in tags)]
    allowed = [s for s in ok if s["id"] not in rejected]
    if not allowed:
        raise StyleError(f"no style left: tags {list(tags)} match {[s['id'] for s in ok]}, rejected {rejected}")
    fav = [s for s in allowed if s["id"] in liked]
    s = (fav or allowed)[0]
    return {"id": s["id"], "name_vi": s["name_vi"], "defaults": s["defaults"], "reason": "liked" if fav else "not rejected (no liked style matches)",
            "candidates": [x["id"] for x in allowed], "excluded_rejected": [x["id"] for x in ok if x["id"] in rejected]}


def _indent(text):
    for line in text.splitlines()[1:]:
        if line.strip():
            return len(line) - len(line.lstrip(" ")) or None
    return 2


def mark(catalog, path, style, verdict):
    """verdict: 'liked' | 'rejected' | 'clear'. Returns the new {liked, rejected}."""
    if style not in {s["id"] for s in catalog["styles"]}:
        raise StyleError(f"unknown style {style!r}; known: {[s['id'] for s in catalog['styles']]}")
    path = Path(path)
    lock = path.with_name(path.name + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise StyleError(f"{lock} exists (another write in progress, or a crashed one: delete it if nothing is running)")
    try:
        os.close(fd)
        raw = path.read_bytes() if path.is_file() else None
        if raw is None:
            raise StyleError(f"profile not found: {path}")
        text = raw.decode("utf-8-sig")
        prof = json.loads(text)
        if not isinstance(prof.get("gu", {}), dict):
            raise StyleError("profile.gu must be an object")
        fs = prof.setdefault("gu", {}).setdefault("frame_styles", {})
        liked = [x for x in fs.get("liked") or [] if x != style]
        rejected = [x for x in fs.get("rejected") or [] if x != style]
        if verdict == "liked":
            liked.append(style)
        elif verdict == "rejected":
            rejected.append(style)
        fs["liked"], fs["rejected"] = liked, rejected
        bak = path.with_name(f"{path.name}.bak-frame-style-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}")
        shutil.copy2(path, bak)
        tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
        try:
            tmp.write_text(json.dumps(prof, ensure_ascii=False, indent=_indent(text)) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()
        if taste(read_profile(path)) != (liked, rejected):
            shutil.copy2(bak, path)
            raise StyleError(f"re-read check failed; previous profile restored from {bak}")
        return {"liked": liked, "rejected": rejected, "backup": str(bak)}
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("--profile", required=True)
    p.add_argument("--tags", nargs="*", default=[])
    m = sub.add_parser("mark")
    m.add_argument("--profile", required=True)
    m.add_argument("--style", required=True)
    g = m.add_mutually_exclusive_group(required=True)
    g.add_argument("--liked", action="store_true")
    g.add_argument("--rejected", action="store_true")
    g.add_argument("--clear", action="store_true")
    ls = sub.add_parser("list")
    ls.add_argument("--profile")
    ap.add_argument("--catalog", default=str(CATALOG))
    a = ap.parse_args(argv)
    try:
        cat = load_catalog(a.catalog)
        if a.cmd == "pick":
            res = pick(cat, read_profile(a.profile), a.tags)
        elif a.cmd == "mark":
            res = mark(cat, a.profile, a.style, "liked" if a.liked else "rejected" if a.rejected else "clear")
        else:
            liked, rejected = taste(read_profile(a.profile)) if a.profile else ([], [])
            res = {"styles": [{"id": s["id"], "name_vi": s["name_vi"], "tags": s["tags"],
                               "taste": "liked" if s["id"] in liked else "rejected" if s["id"] in rejected else ""} for s in cat["styles"]]}
    except (StyleError, ValueError, OSError) as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, **res}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        _s.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
