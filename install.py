import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).resolve().parent
CLAUDE_DIR = Path.home() / ".claude"
HOOKS_DIR = CLAUDE_DIR / "hooks"
SETTINGS = CLAUDE_DIR / "settings.json"
PY = sys.executable


def load_settings():
    if not SETTINGS.exists():
        return {}
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"ERROR: {SETTINGS} is not valid JSON. Fix it first, then re-run.")
        sys.exit(1)


def has_command(entries, needle):
    for entry in entries:
        for hook in entry.get("hooks", []):
            if needle in str(hook.get("command", "")):
                return True
    return False


def add_hook(settings, event, matcher, command):
    events = settings.setdefault("hooks", {}).setdefault(event, [])
    if has_command(events, "scribe_dumb_trigger.py"):
        return False
    entry = {"hooks": [{"type": "command", "command": command}]}
    if matcher:
        entry["matcher"] = matcher
    events.append(entry)
    return True


def main():
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    hook_path = HOOKS_DIR / "scribe_dumb_trigger.py"
    status_path = CLAUDE_DIR / "statusline_scribe.py"
    shutil.copy2(SRC / "scribe_dumb_trigger.py", hook_path)
    shutil.copy2(SRC / "statusline_scribe.py", status_path)

    settings = load_settings()
    if SETTINGS.exists():
        backup = SETTINGS.with_suffix(f".json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(SETTINGS, backup)
        print(f"backup: {backup}")

    hook_cmd = f'"{PY}" "{hook_path}"'
    added_prompt = add_hook(settings, "UserPromptSubmit", None, hook_cmd)
    added_tool = add_hook(settings, "PostToolUse", "*", hook_cmd)

    status_cmd = f'"{PY}" "{status_path}"'
    existing = (settings.get("statusLine") or {}).get("command")
    if not existing:
        settings["statusLine"] = {"type": "command", "command": status_cmd}
        print("statusLine: installed")
    elif "statusline_scribe.py" in existing:
        print("statusLine: already SCRIBE, unchanged")
    else:
        print("statusLine: you already have one, left alone. To use SCRIBE instead, set:")
        print(f'  "statusLine": {{ "type": "command", "command": {json.dumps(status_cmd)} }}')

    SETTINGS.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    (CLAUDE_DIR / ".scribe-active").write_text("on", encoding="utf-8")

    print(f"hook UserPromptSubmit: {'added' if added_prompt else 'already present'}")
    print(f"hook PostToolUse: {'added' if added_tool else 'already present'}")
    print(f"flag: {CLAUDE_DIR / '.scribe-active'} (delete to turn SCRIBE off)")
    print("done. restart Claude Code to load the new settings.")


if __name__ == "__main__":
    main()
