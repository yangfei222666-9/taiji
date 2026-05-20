#!/usr/bin/env bash
set -euo pipefail

hash_file() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$file" | awk '{print $1}'
  else
    echo "No SHA-256 tool found: install sha256sum or shasum" >&2
    return 1
  fi
}

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 <file> [file...]" >&2
  exit 2
fi

echo "manifest_version: 1"
echo "generated_at: \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\""
echo "items:"

for file in "$@"; do
  if [ ! -f "$file" ]; then
    echo "Manifest input missing: $file" >&2
    exit 1
  fi

  hash="$(hash_file "$file")"
  size="$(wc -c < "$file" | tr -d ' ')"
  cat <<EOF
  - path: "$file"
    sha256: "$hash"
    size_bytes: $size
EOF
done
