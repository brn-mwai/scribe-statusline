# Community submission — SCRIBE

Paste-ready values for the "Share with the Community" form.

---

## Resource Type

**Tool / Project**

---

## Title

```
SCRIBE — Context-Rot Monitor & Auto-Handoff for Claude Code
```

---

## Short Description

```
A Claude Code statusline that shows how full your context window is and grades it SHARP / OK / FADING / DUMB, plus a hook that auto-writes a full session handoff at 90% so you can restart clean without losing the session.
```

---

## Full Description

```
Long Claude Code sessions get worse, not better. As the context window fills, the model
misses things it knew 200 messages ago, repeats work, and re-litigates settled decisions.
That is context rot, and it is invisible — the session looks identical at 20% and at 92%.

Two failure modes follow. You keep working in a degraded session because nothing tells you
to stop. Or you finally start fresh and lose everything: the decisions, the dead ends, the
half-finished task, the trap you hit at hour two.

SCRIBE fixes both.

1. STATUSLINE METER

On every render it reads the tail of your session transcript, sums
input_tokens + cache_read_input_tokens + cache_creation_input_tokens (that sum IS the
current context size), and divides by the window. Window auto-detects: 1M if the model id
contains "1m" or usage is already past 200k, else 200k.

  SHARP    < 50%    full quality
  OK       50-74%   fine, start being deliberate
  FADING   75-89%   quality slipping, wrap up the current thread
  DUMB     90%+     hand off now

At DUMB the whole segment turns red, blinks, and appends "! HANDOFF -> NEW INSTANCE".
The blink is ANSI SGR 5; terminals that ignore it (VS Code integrated terminal, iTerm2 by
default) render bold red instead.

2. AUTO HANDOFF AT 90%

A hook runs on UserPromptSubmit and PostToolUse. The first time context crosses 90% in a
session it:

  - archives any previous handoff to _handoff/archive/
  - writes _handoff/CURRENT.md — a skeleton pre-filled with your requests this session,
    every file edited, every file read, plus empty State / Decisions / Next steps /
    Gotchas sections
  - writes _handoff/handoff-graph.json — session, request and file nodes with
    MADE_REQUEST / EDITED / READ edges
  - injects an instruction telling Claude to fill in the skeleton, enrich the graph, and
    print a ready-to-paste continuation prompt to _handoff/CONTINUATION.md

You open a fresh session, paste the continuation prompt, and the new instance reads
CURRENT.md before touching anything.

It fires once per session (marker in ~/.claude/.scribe-dumb-fired/), so it does not nag on
every prompt after 90%. Markers older than 7 days self-prune.

WHY A HOOK AND NOT A MEMORY OR A PROMPT RULE

The model cannot see its own token count — only the harness can. A hook runs outside the
model, reads the real transcript, and injects the alert as context. The trigger is
mechanical and fires exactly when it should, not when the model happens to notice.

USE CASES

  - Multi-hour refactors and migrations where losing session state costs an hour of
    re-explaining
  - Knowing when to stop trusting an answer, instead of guessing from vibes
  - Teams standardising on when to hand off, with the handoff artifact written the same
    way every time
  - Pointing SCRIBE_HANDOFF_DIR at a repo or knowledge base so handoffs live with the work
    and become a searchable session history

CONFIG

  SCRIBE_HANDOFF_DIR   default ~/.claude/_handoff   where handoff files land
  SCRIBE_DUMB_PCT      default 90                   trigger threshold

Turn off by deleting ~/.claude/.scribe-active — the statusline shows "[SCRIBE off]" and the
hook exits immediately. Recreate the file to turn it back on.

Pure Python 3.8+ stdlib, no dependencies, works on Windows, macOS and Linux. The installer
backs up settings.json first and refuses to clobber an existing statusLine — it prints the
snippet for you to merge instead. MIT.
```

---

## URL

```
https://github.com/brn-mwai/scribe-statusline#readme
```

(Replace with a live demo page if one gets deployed.)

---

## GitHub Repo

```
https://github.com/brn-mwai/scribe-statusline
```

---

## Install Instructions

```
git clone https://github.com/brn-mwai/scribe-statusline
cd scribe-statusline
python install.py
# restart Claude Code

# The installer:
#   copies scribe_dumb_trigger.py -> ~/.claude/hooks/
#   copies statusline_scribe.py   -> ~/.claude/
#   backs up ~/.claude/settings.json to settings.json.bak-<timestamp>
#   registers the hook on UserPromptSubmit and PostToolUse
#   sets statusLine only if you don't already have one
#   writes ~/.claude/.scribe-active (delete this file to turn SCRIBE off)

# Optional:
export SCRIBE_HANDOFF_DIR=/path/to/your/repo/_handoff
export SCRIBE_DUMB_PCT=85
```

---

## Tags

```
claude-code, statusline, hooks, context-management, python, handoff, context-rot, developer-tools, session-management, cli
```

---

## About You

Your Name:
```
Brian Mwai
```

Contact:
```
mwaibryn@gmail.com
```
