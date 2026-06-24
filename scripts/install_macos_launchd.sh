#!/usr/bin/env bash
set -euo pipefail

LABEL="${LABEL:-com.kanojo.backend}"
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Kanojo}"
PORT="${PORT:-8787}"
BIND_ADDRESS="${BIND_ADDRESS:-0.0.0.0}"

BACKEND_DIR="$PROJECT_ROOT/backend"
PYTHON_BIN="${PYTHON_BIN:-$BACKEND_DIR/.venv/bin/python}"
WRAPPER_DIR="$BACKEND_DIR/.launchd"
WRAPPER="$WRAPPER_DIR/run_backend.sh"
LOG_DIR="$BACKEND_DIR/logs"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST="$PLIST_DIR/$LABEL.plist"

xml_escape() {
    printf '%s' "$1" |
        sed \
            -e 's/&/\&amp;/g' \
            -e 's/</\&lt;/g' \
            -e 's/>/\&gt;/g' \
            -e 's/"/\&quot;/g' \
            -e "s/'/\&apos;/g"
}

if [[ ! -d "$BACKEND_DIR" ]]; then
    echo "Backend directory not found: $BACKEND_DIR" >&2
    exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python not found or not executable: $PYTHON_BIN" >&2
    echo "Create the backend venv first, or pass PYTHON_BIN=/path/to/python." >&2
    exit 1
fi

mkdir -p "$WRAPPER_DIR" "$LOG_DIR" "$PLIST_DIR"

cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
set -euo pipefail

cd "$BACKEND_DIR"

if [[ -f ".env" ]]; then
    set -a
    source ".env"
    set +a
fi

export PYTHONPATH="$BACKEND_DIR/src"
exec "$PYTHON_BIN" -m uvicorn kanojo_agent.main:app --host "$BIND_ADDRESS" --port "$PORT"
EOF
chmod +x "$WRAPPER"

WRAPPER_XML="$(xml_escape "$WRAPPER")"
BACKEND_XML="$(xml_escape "$BACKEND_DIR")"
OUT_LOG_XML="$(xml_escape "$LOG_DIR/launchd.out.log")"
ERR_LOG_XML="$(xml_escape "$LOG_DIR/launchd.err.log")"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$WRAPPER_XML</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$BACKEND_XML</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$OUT_LOG_XML</string>
  <key>StandardErrorPath</key>
  <string>$ERR_LOG_XML</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST"
launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl kickstart -k "gui/$UID/$LABEL"

echo "Installed $LABEL"
echo "Plist: $PLIST"
echo "Logs:"
echo "  $LOG_DIR/launchd.out.log"
echo "  $LOG_DIR/launchd.err.log"

sleep 2
curl -fsS "http://127.0.0.1:$PORT/health"
echo
