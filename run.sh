#!/bin/zsh
# Hourly entrypoint for launchd. Runs the bot, then tries to back up sent_posts.json to your git remote.
cd "$(dirname "$0")" || exit 1
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
./venv/bin/python main.py || exit 1
git add sent_posts.json
git diff --cached --quiet && exit 0
git commit -q -m "Update sent_posts.json after bot run"
git push -q origin HEAD || echo "push skipped: no write access to origin (sent_posts.json is still saved locally)"
