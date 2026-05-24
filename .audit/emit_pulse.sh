#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <pulse-body-file>" >&2
  exit 64
fi

BODY_FILE="$1"
if [ ! -f "$BODY_FILE" ]; then
  echo "pulse body not found: $BODY_FILE" >&2
  exit 66
fi

echo "=============================="
echo "TAIJIOS AUDIT PULSE"
echo "=============================="
cat "$BODY_FILE"
echo
