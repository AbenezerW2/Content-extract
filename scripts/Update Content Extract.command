#!/bin/bash
set -u
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Pass --branch and --app to override these defaults.
python3 "$SCRIPT_DIR/update_macos.py" "$@"
result=$?
echo
if [ "$result" -ne 0 ]; then
  echo "The update did not complete. See the message above."
fi
read -r -p "Press Return to close this window..." _reply
exit "$result"
