#!/usr/bin/env bash
# Daily agent-multiplier run for macOS (installed by install-routine-macos.sh; opt-in).
#
# Every run: optional calendar refresh -> agent_multiplier.py -> page in ~/.agent-multiplier/out/latest.html
# and a copy of the figures in ~/.agent-multiplier/snapshots/<date>.json. Nothing is sent anywhere.
#
# Calendar (optional): set AGENT_MULTIPLIER_CALENDAR_CMD to a command that prints a Google Calendar
# events-list JSON for the last ~35 days (for example a `gws calendar events list ...` call). Its output
# replaces ~/.agent-multiplier/calendar.json only when it is valid JSON with an "items" list.
#
# If you also want an agent session to do something with the page (publish it, write recommendations),
# start that session's first prompt with the routine marker from config.json (default
# [agent-multiplier-routine]) so the routine's own session is left out of your figures.
set -uo pipefail

HOME_DIR="${AGENT_MULTIPLIER_HOME:-$HOME/.agent-multiplier}"
APP="$(cd "$(dirname "$0")" && pwd)"
PY="${AGENT_MULTIPLIER_PYTHON:-python3}"
mkdir -p "$HOME_DIR/out" "$HOME_DIR/snapshots"
exec >>"$HOME_DIR/routine.log" 2>&1
today=$(date +%F)
echo "=== $(date '+%F %T') agent-multiplier routine"

if [ -n "${AGENT_MULTIPLIER_CALENDAR_CMD:-}" ]; then
  if bash -c "$AGENT_MULTIPLIER_CALENDAR_CMD" >"$HOME_DIR/calendar.json.tmp" 2>/dev/null \
     && "$PY" -c "import json,sys; assert isinstance(json.load(open(sys.argv[1]))['items'], list)" "$HOME_DIR/calendar.json.tmp" 2>/dev/null; then
    mv "$HOME_DIR/calendar.json.tmp" "$HOME_DIR/calendar.json"
  else
    echo "warning: calendar command failed; keeping the previous calendar.json"
    rm -f "$HOME_DIR/calendar.json.tmp"
  fi
fi

"$PY" -I "$APP/agent_multiplier.py" --html "$HOME_DIR/out/latest.html" --json "$HOME_DIR/out/latest.json" \
  --evidence "$HOME_DIR/out/evidence.json" | head -2 || { echo "ERROR agent_multiplier.py"; exit 1; }
cp "$HOME_DIR/out/latest.json" "$HOME_DIR/snapshots/$today.json"
echo "ok: $HOME_DIR/out/latest.html"
