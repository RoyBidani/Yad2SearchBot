#!/bin/zsh
# Hourly entrypoint for launchd. Runs the bot, then syncs sent_posts.json to GitHub.
cd "$(dirname "$0")" || exit 1
export PATH=/opt/homebrew/bin:/usr/bin:/bin
./venv/bin/python main.py || exit 1
git add sent_posts.json
git diff --cached --quiet || { git commit -q -m "Update sent_posts.json after bot run" && git push -q origin main; }
