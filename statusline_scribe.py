import json
import os
import sys
from pathlib import Path

ESC = "\x1b"
TAIL_BYTES = 262144
DUMB_PCT = int(os.environ.get("SCRIBE_DUMB_PCT") or 90)
FADING_PCT = 75
OK_PCT = 50
CLAUDE_DIR = Path.home() / ".claude"


def paint(text, color):
    return f"{ESC}[{color}m{text}{ESC}[0m"


def rot_state(pct):
    if pct >= DUMB_PCT:
        # SGR 5 blinks where the terminal supports it and degrades to bold elsewhere.
        return "DUMB", "5;1;38;5;196"
    if pct >= FADING_PCT:
        return "FADING", "38;5;214"
    if pct >= OK_PCT:
        return "OK", "38;5;42"
    return "SHARP", "38;5;42"


def last_usage(transcript_path):
    # Transcripts grow to hundreds of MB; only the tail holds the current usage entry.
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TAIL_BYTES))
            chunk = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    usage = None
    for line in chunk.splitlines():
        if '"usage"' not in line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        u = (entry.get("message") or {}).get("usage")
        if u:
            usage = u
    return usage


def context_usage(usage, model_id):
    used = (
        int(usage.get("input_tokens") or 0)
        + int(usage.get("cache_read_input_tokens") or 0)
        + int(usage.get("cache_creation_input_tokens") or 0)
    )
    window = 1_000_000 if ("1m" in (model_id or "").lower() or used > 200_000) else 200_000
    pct = round(100.0 * used / window)
    return used, pct, "1M" if window >= 1_000_000 else "200k"


def main():
    if not (CLAUDE_DIR / ".scribe-active").exists():
        sys.stdout.write(paint("[SCRIBE off]", "38;5;240"))
        return
    try:
        ctx = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        ctx = {}

    model = (ctx.get("model") or {}).get("display_name") or (ctx.get("model") or {}).get("id") or ""
    badge = paint("[SCRIBE]", "38;5;39")
    segments = []
    if model:
        segments.append(paint(model, "1;38;5;255"))

    transcript = ctx.get("transcript_path")
    usage = last_usage(transcript) if transcript else None
    if not usage:
        segments.append(badge)
        sys.stdout.write(paint(" | ", "38;5;240").join(segments))
        return

    used, pct, window = context_usage(usage, str((ctx.get("model") or {}).get("id") or ""))
    state, color = rot_state(pct)
    meter = paint(f"{state} {round(used / 1000)}k/{window} {pct}%", color)
    line = f"{badge} {meter}"
    if state == "DUMB":
        # SGR 5 blinks where the terminal supports it and degrades to bold elsewhere.
        line += " " + paint("! HANDOFF -> NEW INSTANCE", "5;1;38;5;196")
    segments.append(line)
    sys.stdout.write(paint(" | ", "38;5;240").join(segments))


if __name__ == "__main__":
    main()
