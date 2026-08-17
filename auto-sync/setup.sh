#!/bin/bash
# Health & Fitness Hub - self-contained auto-sync setup (fetches everything itself).
# Requires ~/.hub-sync/token to exist (the paste that runs this creates it).
set -e
BASE="https://sammypisano.github.io/auto-sync"
mkdir -p "$HOME/.hub-sync" "$HOME/Library/LaunchAgents"
if [ ! -s "$HOME/.hub-sync/token" ]; then
  echo "No token found at ~/.hub-sync/token - use the full paste Claude gave you."; exit 1
fi
curl -fsSL "$BASE/mfp_auto_sync.py" -o "$HOME/.hub-sync/mfp_auto_sync.py"
curl -fsSL "$BASE/com.sp.hubsync.plist" -o "$HOME/Library/LaunchAgents/com.sp.hubsync.plist"
if [ ! -d "$HOME/.hub-sync/venv" ]; then python3 -m venv "$HOME/.hub-sync/venv"; fi
"$HOME/.hub-sync/venv/bin/pip" install -q --upgrade pip myfitnesspal browser-cookie3
launchctl unload "$HOME/Library/LaunchAgents/com.sp.hubsync.plist" 2>/dev/null || true
launchctl load "$HOME/Library/LaunchAgents/com.sp.hubsync.plist"
echo "Installed. Running the first sync now (approve the Keychain prompt if one appears)..."
"$HOME/.hub-sync/venv/bin/python3" "$HOME/.hub-sync/mfp_auto_sync.py" || true
echo "Done - it now syncs MyFitnessPal every 3 hours whenever this Mac is on. Log: ~/.hub-sync/log.txt"
