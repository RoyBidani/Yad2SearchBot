#!/usr/bin/env bash
# Health check of the bot on the EC2 box, run from your laptop. Needs aws cli + SSM access.
#   ./deploy/status.sh            last 24h
#   ./deploy/status.sh 3d         last 3 days
set -euo pipefail
PROFILE=${AWS_PROFILE_YAD2:-dev}; REGION=${AWS_REGION_YAD2:-us-east-1}; INSTANCE=${YAD2BOT_INSTANCE:-i-0a77cbd4d6c7ac9ee}
SINCE=${1:-24h}
if [ "$SINCE" = run ]; then
  CMD=$(aws ssm send-command --profile "$PROFILE" --region "$REGION" --instance-ids "$INSTANCE" --document-name AWS-RunShellScript \
    --parameters '{"commands":["systemctl start yad2bot.service; echo exit=$?","journalctl -u yad2bot --since -10min --no-pager | grep -E \"title|WARN|ERR|done:\" | sed -E \"s/^.*python\\[[0-9]+\\]: //\""]}' \
    --query Command.CommandId --output text)
  until S=$(aws ssm get-command-invocation --profile "$PROFILE" --region "$REGION" --command-id "$CMD" --instance-id "$INSTANCE" --query Status --output text 2>/dev/null) && [ "$S" != InProgress ] && [ "$S" != Pending ]; do sleep 5; done
  aws ssm get-command-invocation --profile "$PROFILE" --region "$REGION" --command-id "$CMD" --instance-id "$INSTANCE" --query '[StandardOutputContent,StandardErrorContent]' --output text
  exit 0
fi

CMD=$(aws ssm send-command --profile "$PROFILE" --region "$REGION" --instance-ids "$INSTANCE" \
  --document-name AWS-RunShellScript --parameters "{\"commands\":[
    \"echo '== timer';   systemctl is-enabled yad2bot.timer; systemctl list-timers yad2bot.timer --no-pager | sed -n 2p\",
    \"echo '== last run'; systemctl show yad2bot.service -p Result -p ExecMainExitTimestamp -p ExecMainStatus | tr '\\\\n' ' '; echo\",
    \"echo '== runs (time, new listings) since $SINCE'; journalctl -u yad2bot --since -$SINCE --no-pager -o short-iso | grep 'done:' | sed -E 's/^([0-9T:-]+).*done: ([0-9]+).*/\\\\1  \\\\2/'\",
    \"echo '== radware'; journalctl -u yad2bot --since -$SINCE --no-pager -o short-iso | grep 'page title' | sed -E 's/^([0-9T:-]+).*title: /\\\\1  /' | tail -3\",
    \"echo '== warnings/errors since $SINCE'; journalctl -u yad2bot --since -$SINCE --no-pager -o short-iso | grep -E 'WARN|ERR|unreachable|Traceback' | sed -E 's/python\\\\[[0-9]+\\\\]: //' | tail -5\",
    \"echo '== box'; free -m | sed -n 2p; df -h / | tail -1; systemctl is-active flightbot | sed 's/^/flightbot: /'\"
  ]}" --query Command.CommandId --output text)

for _ in $(seq 1 30); do
  S=$(aws ssm get-command-invocation --profile "$PROFILE" --region "$REGION" --command-id "$CMD" --instance-id "$INSTANCE" --query Status --output text 2>/dev/null || echo Pending)
  [ "$S" != "InProgress" ] && [ "$S" != "Pending" ] && break
  sleep 2
done
aws ssm get-command-invocation --profile "$PROFILE" --region "$REGION" --command-id "$CMD" --instance-id "$INSTANCE" \
  --query '[StandardOutputContent,StandardErrorContent]' --output text

cat <<'EOF'

How to read it: timer "enabled" + a NEXT time = scheduled. One "done" line per hour = running. Zero new listings for
hours is normal (nothing new posted). "Radware Bot Manager Captcha/Block" in the radware line = IP blocked, ping Roy's
assistant. Force a run now:  ./deploy/status.sh run
EOF
