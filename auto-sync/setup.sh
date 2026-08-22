#!/bin/bash
# Health & Fitness Hub - self-contained auto-sync setup (fetches everything itself).
# Works on any Mac. Requires ~/.hub-sync/token to exist (the paste that runs this creates it).
set -e
BASE="https://sammypisano.github.io/auto-sync"

# --- preflight: a fresh Mac may not have Apple's command-line tools (git/python3) yet ---
if ! xcode-select -p >/dev/null 2>&1; then
  echo ""
  echo "This Mac first needs Apple's free command-line tools (git + python)."
  echo "A popup should appear now - click Install, wait for it to finish,"
  echo "then run the SAME full paste again."
  xcode-select --install 2>/dev/null || true
  exit 1
fi
for c in git python3 curl; do
  if ! command -v "$c" >/dev/null 2>&1; then
    echo "Missing '$c' - install Apple's command-line tools (run: xcode-select --install), then rerun the paste."
    exit 1
  fi
done

mkdir -p "$HOME/.hub-sync" "$HOME/Library/LaunchAgents"
if [ ! -s "$HOME/.hub-sync/token" ]; then
  echo "No token found at ~/.hub-sync/token - use the full paste Claude gave you (it saves the token first)."
  exit 1
fi

curl -fsSL "$BASE/mfp_auto_sync.py" -o "$HOME/.hub-sync/mfp_auto_sync.py"
curl -fsSL "$BASE/com.sp.hubsync.plist" -o "$HOME/Library/LaunchAgents/com.sp.hubsync.plist"

if [ ! -d "$HOME/.hub-sync/venv" ]; then python3 -m venv "$HOME/.hub-sync/venv"; fi
"$HOME/.hub-sync/venv/bin/pip" install -q --upgrade pip myfitnesspal browser-cookie3

launchctl unload "$HOME/Library/LaunchAgents/com.sp.hubsync.plist" 2>/dev/null || true
launchctl load "$HOME/Library/LaunchAgents/com.sp.hubsync.plist"

echo ""
echo "Installed. Running the first sync now."
echo "If macOS asks about 'Chrome Safe Storage' / Keychain access, click ALWAYS ALLOW -"
echo "that is how it reads your logged-in MyFitnessPal session (no password is stored)."
if "$HOME/.hub-sync/venv/bin/python3" "$HOME/.hub-sync/mfp_auto_sync.py"; then
  echo ""
  echo "All good - this Mac now syncs MyFitnessPal every 3 hours (plus 11pm) whenever it is on."
else
  echo ""
  echo "The first sync didn't finish. Most common fix: open Chrome on THIS Mac,"
  echo "log in at myfitnesspal.com, then it will succeed on its own within 3 hours"
  echo "(or rerun the paste to try again now). Log: ~/.hub-sync/log.txt"
fi
