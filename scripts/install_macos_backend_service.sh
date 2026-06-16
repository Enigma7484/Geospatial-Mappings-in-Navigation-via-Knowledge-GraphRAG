#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$HOME/.georoute-backend"
PLIST="$HOME/Library/LaunchAgents/com.georoute.backend.plist"
LOG_DIR="$RUNTIME_DIR/logs"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR" "$RUNTIME_DIR/scripts" "$RUNTIME_DIR/data"

rsync -a --delete "$ROOT_DIR/app/" "$RUNTIME_DIR/app/"
rsync -a "$ROOT_DIR/data/user_histories_osm_trace.json" "$RUNTIME_DIR/data/user_histories_osm_trace.json"
rsync -a "$ROOT_DIR/requirements-deploy.txt" "$RUNTIME_DIR/requirements-deploy.txt"
rsync -a "$ROOT_DIR/scripts/run_live_backend.sh" "$RUNTIME_DIR/scripts/run_live_backend.sh"
chmod +x "$RUNTIME_DIR/scripts/run_live_backend.sh"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.georoute.backend</string>

  <key>ProgramArguments</key>
  <array>
    <string>$RUNTIME_DIR/scripts/run_live_backend.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$RUNTIME_DIR</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>GEOROUTE_ALLOWED_ORIGINS</key>
    <string>*</string>
    <key>GEOROUTE_PROMPT_RANKER</key>
    <string>lexical</string>
    <key>GEOROUTE_USER_HISTORY_PATH</key>
    <string>data/user_histories_osm_trace.json</string>
    <key>OSMNX_CACHE_FOLDER</key>
    <string>osmnx_cache</string>
  </dict>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/backend.launchd.out.log</string>

  <key>StandardErrorPath</key>
  <string>$LOG_DIR/backend.launchd.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/com.georoute.backend"

echo "Installed and started com.georoute.backend"
echo "Backend URL: http://127.0.0.1:8000"
echo "Runtime copy: $RUNTIME_DIR"
echo "Logs:"
echo "  $LOG_DIR/backend.launchd.out.log"
echo "  $LOG_DIR/backend.launchd.err.log"
