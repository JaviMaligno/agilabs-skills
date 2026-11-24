#!/usr/bin/env bash
# Opt-in daily routine for macOS (launchd). Runs routine-macos.sh every day at HH:MM (default 08:30);
# if the Mac was asleep then, launchd runs it on wake.
#   ./install-routine-macos.sh [HH:MM]     install or reinstall
#   ./install-routine-macos.sh --uninstall remove it
# Run it now: launchctl kickstart gui/$(id -u)/com.agent-multiplier.routine
#
# macOS does not let launchd jobs read ~/Documents, ~/Desktop or ~/Downloads, so the routine runs from
# a copy of these scripts in ~/.agent-multiplier/app. Re-run the installer after updating the skill.
set -euo pipefail
LABEL=com.agent-multiplier.routine
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SRC="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR="${AGENT_MULTIPLIER_HOME:-$HOME/.agent-multiplier}"
APP="$HOME_DIR/app"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "routine removed (data in $HOME_DIR left untouched)"
  exit 0
fi
hhmm=${1:-08:30}
h=$((10#${hhmm%%:*})); m=$((10#${hhmm##*:}))
mkdir -p "$HOME/Library/LaunchAgents" "$APP"
cp "$SRC"/*.py "$SRC"/page.html "$SRC"/routine-macos.sh "$APP/"
chmod +x "$APP/routine-macos.sh"
PYBIN="$(command -v python3)"
cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$APP/routine-macos.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>$h</integer><key>Minute</key><integer>$m</integer></dict>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>HOME</key><string>$HOME</string>
    <key>AGENT_MULTIPLIER_HOME</key><string>$HOME_DIR</string>
    <key>AGENT_MULTIPLIER_PYTHON</key><string>$PYBIN</string>
  </dict>
  <key>StandardOutPath</key><string>$HOME_DIR/launchd.log</string>
  <key>StandardErrorPath</key><string>$HOME_DIR/launchd.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "routine installed: every day at $hhmm. Page: $HOME_DIR/out/latest.html · log: $HOME_DIR/routine.log"
