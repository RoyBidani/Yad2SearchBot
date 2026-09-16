#!/bin/zsh
# One-shot setup on macOS: venv, deps, Chromium, hourly launchd agent pointing at THIS checkout.
# Safe to re-run. Does not touch .env or searches.json.
set -e
cd "$(dirname "$0")"
REPO="$(pwd)"
LABEL="com.yad2bot"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt
./venv/bin/playwright install chromium
chmod +x run.sh

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>$REPO/run.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$REPO/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$REPO/launchd.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

cat <<EOF

Installed. Hourly agent: $LABEL -> $REPO/run.sh

Next:
  1. Create .env (see README):   TELEGRAM_BOT_TOKEN=...  CHAT_ID_ME=...
  2. Edit searches.json to taste.
  3. ./venv/bin/python main.py --dry-run     # see matches, send nothing
  4. ./venv/bin/python main.py --seed        # mark current listings as seen, ONCE
  5. launchctl kickstart -k gui/$(id -u)/$LABEL    # first live run now (or wait an hour)
EOF
