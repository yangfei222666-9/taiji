#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MANIFEST="${1:-}"
PUBLIC_KEY="keys/release_pub.pem"

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

if [ -z "$MANIFEST" ]; then
  echo "Usage: $0 <manifest.yaml>" >&2
  exit 2
fi

if [ ! -f "$MANIFEST" ]; then
  echo "Manifest not found: $MANIFEST" >&2
  exit 1
fi

if [ ! -f "${MANIFEST}.sig" ]; then
  echo "Manifest signature not found: ${MANIFEST}.sig" >&2
  exit 1
fi

if [ ! -f "$PUBLIC_KEY" ]; then
  echo "Public key not found: $PUBLIC_KEY" >&2
  exit 1
fi

tmp_items="$(mktemp "${TMPDIR:-/tmp}/evidence_items.XXXXXX")"
trap 'rm -f "$tmp_items"' EXIT

awk '
  $1 == "-" && $2 == "path:" {
    path = $3
    gsub(/^"/, "", path)
    gsub(/"$/, "", path)
  }
  $1 == "sha256:" {
    hash = $2
    gsub(/^"/, "", hash)
    gsub(/"$/, "", hash)
    if (path != "") {
      print path "\t" hash
      path = ""
    }
  }
' "$MANIFEST" > "$tmp_items"

if [ ! -s "$tmp_items" ]; then
  echo "No manifest items found: $MANIFEST" >&2
  exit 1
fi

echo "[1] verify manifest signature"
openssl dgst -sha256 \
  -verify "$PUBLIC_KEY" \
  -signature "${MANIFEST}.sig" \
  "$MANIFEST"

echo
echo "[2] verify hashes"
while IFS="$(printf '\t')" read -r file expected_hash; do
  if [ ! -f "$file" ]; then
    echo "FAIL missing: $file"
    exit 1
  fi

  actual_hash="$(hash_file "$file")"
  if [ "$actual_hash" != "$expected_hash" ]; then
    echo "FAIL hash: $file"
    exit 1
  fi

  echo "OK: $file"
done < "$tmp_items"

echo
echo "ALL VERIFIED."
