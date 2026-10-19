#!/bin/zsh
# Installs the "Open in Apple News" helper for Chrome-family browsers.
#   ./install.sh                     # every installed Chrome/Chromium/Brave/Edge
#   ./install.sh --target-dir DIR    # write the browser manifest into DIR only (tests)
set -euo pipefail

HERE=${0:A:h}
HOST_NAME=com.open_in_apple_news.helper
DEST="$HOME/Library/Application Support/OpenInAppleNews"

target_dir=""
if [[ ${1:-} == --target-dir ]]; then
  target_dir=${2:?--target-dir needs a directory}
fi

# The /usr/bin/python3 stub only works once Command Line Tools are installed,
# so take the first Python 3.9+ that actually runs.
PY=""
for candidate in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [[ -x $candidate ]] && $candidate -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    PY=$candidate
    break
  fi
done
if [[ -z $PY ]]; then
  echo "Python 3.9+ is needed. Run: xcode-select --install" >&2
  exit 1
fi

EXT_ID=$($PY -I "$HERE/extension_id.py" "$HERE/../extension/manifest.json")

mkdir -p "$DEST"
cp "$HERE/open_in_news_host.py" "$DEST/open_in_news_host.py"
cat > "$DEST/host" <<EOF
#!/bin/sh
exec "$PY" -I "$DEST/open_in_news_host.py" "\$@"
EOF
chmod 755 "$DEST/host"

write_manifest() {
  mkdir -p "$1"
  cat > "$1/$HOST_NAME.json" <<EOF
{
  "name": "$HOST_NAME",
  "description": "Hands article URLs to the Apple News app",
  "path": "$DEST/host",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://$EXT_ID/"]
}
EOF
  echo "Registered helper in: $1"
}

if [[ -n $target_dir ]]; then
  write_manifest "$target_dir"
else
  found=0
  for browser in "Google/Chrome" "Google/Chrome Beta" "Google/Chrome Canary" "Chromium" \
                 "BraveSoftware/Brave-Browser" "Microsoft Edge"; do
    base="$HOME/Library/Application Support/$browser"
    if [[ -d $base ]]; then
      write_manifest "$base/NativeMessagingHosts"
      found=1
    fi
  done
  if (( ! found )); then
    echo "No Chrome-family browser profile found." >&2
    exit 1
  fi
fi

echo "Helper installed at: $DEST (Python: $PY, extension ID: $EXT_ID)"
