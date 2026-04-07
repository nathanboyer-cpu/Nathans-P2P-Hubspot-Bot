Daily schedule (macOS LaunchAgent)
===================================

The plist runs the digest at 09:00 in your Mac’s *system timezone* (Calendar interval is wall-clock local time, not UTC).

For 09:00 GMT/UTC every day year-round:
  • Set macOS Time Zone to UTC (System Settings → General → Date & Time → Time Zone → pick a UTC/GMT region), OR
  • Edit scheduling/com.p2p-hubspot-digest.plist: change the <integer> under <key>Hour</key> to match your offset from UTC (e.g. if you stay on London time and want 09:00 UTC in summer BST, use 10).

Install (one-time):
  chmod +x scripts/run_digest.sh
  launchctl bootout gui/$(id -u)/com.p2p-hubspot-digest 2>/dev/null || true
  cp scheduling/com.p2p-hubspot-digest.plist ~/Library/LaunchAgents/
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.p2p-hubspot-digest.plist

Check:
  launchctl print gui/$(id -u)/com.p2p-hubspot-digest

Remove:
  launchctl bootout gui/$(id -u)/com.p2p-hubspot-digest
  rm ~/Library/LaunchAgents/com.p2p-hubspot-digest.plist

Logs: logs/launchd.out.log and logs/launchd.err.log

Requires .env with HubSpot + Slack (and Anthropic unless you change the job to pass --no-llm in run_digest.sh).
