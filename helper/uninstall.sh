#!/bin/zsh
# Removes everything install.sh created.
set -euo pipefail

HOST_NAME=com.open_in_apple_news.helper
for browser in "Google/Chrome" "Google/Chrome Beta" "Google/Chrome Canary" "Chromium" \
               "BraveSoftware/Brave-Browser" "Microsoft Edge"; do
  manifest="$HOME/Library/Application Support/$browser/NativeMessagingHosts/$HOST_NAME.json"
  if [[ -f $manifest ]]; then
    rm "$manifest"
    echo "Removed: $manifest"
  fi
done
rm -rf "$HOME/Library/Application Support/OpenInAppleNews"
echo "Helper removed."
