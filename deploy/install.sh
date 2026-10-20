#!/usr/bin/env bash
# Linux (Ubuntu/Debian) install as a systemd timer. Idempotent. Run as root from the repo root:  ./deploy/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."
DIR=$(pwd)
export DEBIAN_FRONTEND=noninteractive PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers

apt-get install -y -qq python3-venv git >/dev/null
id yad2bot >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin yad2bot
[ -x venv/bin/python ] || python3 -m venv venv
venv/bin/pip install -q -r requirements.txt
venv/bin/playwright install --with-deps chromium >/dev/null
chmod -R a+rX /opt/pw-browsers

if [ ! -f /etc/yad2bot.env ]; then
    install -m 600 deploy/yad2bot.env.example /etc/yad2bot.env
    echo "Created /etc/yad2bot.env. Put your tokens and chat ids in it, then rerun $0"
    exit 1
fi

# First install: start from the repo's sent_posts.json so the backlog is not re-sent.
mkdir -p /var/lib/yad2bot && chown yad2bot:yad2bot /var/lib/yad2bot
[ -f /var/lib/yad2bot/sent_posts.json ] || install -o yad2bot -g yad2bot -m 644 sent_posts.json /var/lib/yad2bot/sent_posts.json

sed "s#/opt/yad2bot#$DIR#g" deploy/yad2bot.service > /etc/systemd/system/yad2bot.service
cp deploy/yad2bot.timer /etc/systemd/system/yad2bot.timer
systemctl daemon-reload
systemctl enable --now yad2bot.timer
systemctl list-timers yad2bot.timer --no-pager | head -2
echo "Run now:  systemctl start yad2bot.service && journalctl -u yad2bot -n 20 --no-pager"
