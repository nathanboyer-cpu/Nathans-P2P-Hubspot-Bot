Daily schedule (macOS LaunchAgent)
===================================

Why it did not fire at “09:00 UTC”
----------------------------------
1) launchd StartCalendarInterval uses your Mac’s *local* wall time, never UTC. If the plist says Hour 9, that is 09:00 where your Mac thinks it is (e.g. 09:00 BST), which is 08:00 UTC during British Summer Time — one hour early vs 09:00 UTC.

2) If logs/launchd.err.log shows “Operation not permitted” or getcwd errors, macOS Privacy is blocking the LaunchAgent from running scripts or Python inside ~/Documents (and similar protected locations). There is no reliable plist-only workaround: move the whole repo to a non-protected path (e.g. mkdir -p ~/Developer && mv “…/Nathans P2P Hubspot Bot” ~/Developer/), then edit the plist paths to the new ROOT, copy to ~/Library/LaunchAgents/, and run bootout/bootstrap again. Running from Terminal in Cursor still works; only unattended launchd is affected.

For 09:00 UTC from the UK:
  • During BST (summer): use Hour 10 in the plist (10:00 BST = 09:00 UTC).
  • During GMT (winter): use Hour 9 (09:00 GMT = 09:00 UTC).
  • Or set the Mac time zone to UTC and keep Hour 9 for 09:00 UTC year-round.

For 09:00 GMT/UTC every day without seasonal edits:
  • Set macOS Time Zone to UTC (System Settings → General → Date & Time → Time Zone), OR
  • Run the digest from a host that schedules in UTC (e.g. CI with a cron workflow).

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
