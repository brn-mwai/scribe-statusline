import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DUMB_PCT = int(os.environ.get("SCRIBE_DUMB_PCT") or 90)
MAX_REQUESTS = 10
MAX_FILES = 30
CLAUDE_DIR = Path.home() / ".claude"
FIRED_DIR = CLAUDE_DIR / ".scribe-dumb-fired"
HANDOFF_DIR = Path(os.environ.get("SCRIBE_HANDOFF_DIR") or (CLAUDE_DIR / "_handoff"))

HANDOFF_INSTRUCTION = (
    "SCRIBE ALERT: context at {pct}% of {window} - DUMB threshold ({threshold}%+) reached. "
    "Reasoning quality degrades from here. A handoff skeleton was auto-created at "
    "{handoff} with a graph at {graph}. Do this NOW, before continuing the task: "
    "1) Complete the skeleton's State / Decisions / Next steps / Gotchas sections from your knowledge of this session. "
    "2) Enrich handoff-graph.json: add decision and next-step nodes, link them to the request and file nodes already there. "
    "3) Save any session-worthy facts to auto-memory. "
    "4) Write a ready-to-paste CONTINUATION PROMPT to {continuation} AND output it verbatim in the chat inside a fenced code block, "
    "so the user can paste it straight into a fresh instance. It must be self-contained, like a new-session kickoff: name the project + repo + branch, "
    "tell the fresh instance to read {handoff} (and any key memory) IN FULL first, summarize what is done+verified vs still pending, "
    "list the concrete ordered next steps, and flag anything blocked on the user. Mirror the depth of the prompt that started this session. "
    "5) Tell the user context is at {pct}% and recommend starting a fresh instance with that continuation prompt (which reads {handoff} first). "
    "Keep remaining work minimal."
)


def parse_transcript(transcript_path):
    entries = []
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return entries


def last_usage(entries):
    usage = None
    for e in entries:
        u = (e.get("message") or {}).get("usage")
        if u:
            usage = u
    return usage


def settings_model():
    try:
        return str(json.loads((CLAUDE_DIR / "settings.json").read_text()).get("model") or "")
    except (OSError, json.JSONDecodeError):
        return ""


def context_pct(usage, model_id):
    used = (
        int(usage.get("input_tokens") or 0)
        + int(usage.get("cache_read_input_tokens") or 0)
        + int(usage.get("cache_creation_input_tokens") or 0)
    )
    hint = (model_id or settings_model()).lower()
    window = 1_000_000 if ("1m" in hint or used > 200_000) else 200_000
    return round(100.0 * used / window), "1M" if window >= 1_000_000 else "200k"


def user_requests(entries):
    requests = []
    for e in entries:
        if e.get("type") != "user":
            continue
        content = (e.get("message") or {}).get("content")
        texts = []
        if isinstance(content, str):
            texts = [content]
        elif isinstance(content, list):
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        for t in texts:
            t = t.strip()
            if not t or t.startswith("<system-reminder") or t.startswith("<command-") or "hook success" in t[:80]:
                continue
            requests.append(t[:300])
    return requests[-MAX_REQUESTS:]


def files_touched(entries):
    edited, read = [], []
    for e in entries:
        content = (e.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not (isinstance(c, dict) and c.get("type") == "tool_use"):
                continue
            path = (c.get("input") or {}).get("file_path")
            if not path:
                continue
            name = c.get("name")
            if name in ("Edit", "Write", "NotebookEdit") and path not in edited:
                edited.append(path)
            elif name == "Read" and path not in read:
                read.append(path)
    read = [p for p in read if p not in edited]
    return edited[-MAX_FILES:], read[-MAX_FILES:]


def archive_existing():
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = HANDOFF_DIR / "archive"
    for fname in ("CURRENT.md", "handoff-graph.json", "CONTINUATION.md"):
        src = HANDOFF_DIR / fname
        if src.exists():
            archive.mkdir(parents=True, exist_ok=True)
            src.rename(archive / f"{stamp}-{fname}")


def write_handoff(session_id, pct, window, cwd, requests, edited, read):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    req_lines = "\n".join(f"- {r}" for r in requests) or "- (none extracted)"
    edit_lines = "\n".join(f"- `{p}`" for p in edited) or "- (none)"
    read_lines = "\n".join(f"- `{p}`" for p in read) or "- (none)"
    body = f"""---
session: {session_id}
generated: {now}
context: {pct}% of {window}
cwd: {cwd}
graph: handoff-graph.json
---

# Session Handoff (auto-generated at DUMB threshold)

## User requests this session
{req_lines}

## Files edited
{edit_lines}

## Files read
{read_lines}

## State
<!-- FILL: where the task stands right now -->

## Decisions
<!-- FILL: choices made + why -->

## Next steps
<!-- FILL: ordered, concrete -->

## Gotchas
<!-- FILL: traps the next instance must know -->
"""
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    (HANDOFF_DIR / "CURRENT.md").write_text(body, encoding="utf-8")


def write_graph(session_id, pct, cwd, requests, edited, read):
    nodes = [{"id": f"session:{session_id}", "type": "session", "label": f"session {session_id[:8]} ({pct}% ctx, cwd {cwd})"}]
    edges = []
    for i, r in enumerate(requests):
        rid = f"request:{i}"
        nodes.append({"id": rid, "type": "request", "label": r[:120]})
        edges.append({"from": f"session:{session_id}", "to": rid, "type": "MADE_REQUEST"})
    for p in edited:
        fid = f"file:{p}"
        nodes.append({"id": fid, "type": "file", "label": p})
        edges.append({"from": f"session:{session_id}", "to": fid, "type": "EDITED"})
    for p in read:
        fid = f"file:{p}"
        nodes.append({"id": fid, "type": "file", "label": p})
        edges.append({"from": f"session:{session_id}", "to": fid, "type": "READ"})
    graph = {
        "name": "handoff-graph",
        "session_id": session_id,
        "context_pct": pct,
        "nodes": nodes,
        "edges": edges,
        "enrichment": {"expected_node_types": ["decision", "next_step", "gotcha"], "status": "skeleton"},
    }
    (HANDOFF_DIR / "handoff-graph.json").write_text(json.dumps(graph, indent=1), encoding="utf-8")


def prune_old_markers():
    cutoff = time.time() - 7 * 86400
    try:
        for f in FIRED_DIR.iterdir():
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
    except OSError:
        pass


def main():
    if not (CLAUDE_DIR / ".scribe-active").exists():
        return
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    transcript = payload.get("transcript_path")
    session_id = payload.get("session_id") or "unknown"
    if not transcript:
        return
    marker = FIRED_DIR / session_id
    if marker.exists():
        return
    entries = parse_transcript(transcript)
    usage = last_usage(entries)
    if not usage:
        return
    model_id = str((payload.get("model") or {}).get("id") or "")
    pct, window = context_pct(usage, model_id)
    if pct < DUMB_PCT:
        return
    FIRED_DIR.mkdir(exist_ok=True)
    marker.write_text(str(pct))
    prune_old_markers()
    cwd = payload.get("cwd") or ""
    requests = user_requests(entries)
    edited, read = files_touched(entries)
    try:
        archive_existing()
        write_handoff(session_id, pct, window, cwd, requests, edited, read)
        write_graph(session_id, pct, cwd, requests, edited, read)
    except OSError:
        pass
    event = payload.get("hook_event_name") or "UserPromptSubmit"
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": HANDOFF_INSTRUCTION.format(
                        pct=pct,
                        window=window,
                        threshold=DUMB_PCT,
                        handoff=str(HANDOFF_DIR / "CURRENT.md"),
                        graph=str(HANDOFF_DIR / "handoff-graph.json"),
                        continuation=str(HANDOFF_DIR / "CONTINUATION.md"),
                    ),
                }
            }
        )
    )


if __name__ == "__main__":
    main()
