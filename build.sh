#!/usr/bin/env bash
# Encrypt the honeymoon master HTML into docs/index.html (passcode-gated static page).
#   ./build.sh              -> uses the passcode saved in .passcode (or prompts)
#   ./build.sh "newpasscode" -> uses/saves a different one
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../honeymoon_itinerary_master.html"
TPL="$HERE/shell.html"
OUT="$HERE/docs/index.html"
ITER=250000

PASS="${1:-}"
if [ -z "$PASS" ]; then
  if [ -f "$HERE/.passcode" ]; then
    PASS="$(cat "$HERE/.passcode")"
  else
    read -r -s -p "Passcode: " PASS; echo
  fi
else
  printf '%s' "$PASS" > "$HERE/.passcode"; chmod 600 "$HERE/.passcode"
fi
[ -n "$PASS" ] || { echo "error: empty passcode" >&2; exit 1; }
[ -f "$SRC" ]  || { echo "error: missing $SRC" >&2; exit 1; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

SALT_HEX="$(openssl rand -hex 16)"
IV_HEX="$(openssl rand -hex 16)"
PASS_HEX="$(printf '%s' "$PASS" | xxd -p -c 4096 | tr -d '\n')"
KEY_HEX="$(openssl kdf -keylen 32 -kdfopt digest:SHA256 \
             -kdfopt hexpass:"$PASS_HEX" -kdfopt hexsalt:"$SALT_HEX" \
             -kdfopt iter:"$ITER" -binary PBKDF2 | xxd -p -c 4096 | tr -d '\n')"

openssl enc -aes-256-cbc -K "$KEY_HEX" -iv "$IV_HEX" -in "$SRC" -out "$TMP/ct.bin"

CT_B64="$(base64 < "$TMP/ct.bin" | tr -d '\n')"
SALT_B64="$(printf '%s' "$SALT_HEX" | xxd -r -p | base64 | tr -d '\n')"
IV_B64="$(printf '%s' "$IV_HEX" | xxd -r -p | base64 | tr -d '\n')"
SHA="$(openssl dgst -sha256 -hex < "$SRC" | awk '{print $NF}')"

printf '{"salt":"%s","iv":"%s","iter":%s,"sha256":"%s","ct":"%s"}' \
  "$SALT_B64" "$IV_B64" "$ITER" "$SHA" "$CT_B64" > "$TMP/payload.json"

mkdir -p "$HERE/docs"
python3 - "$TPL" "$TMP/payload.json" "$OUT" <<'PY'
import sys
tpl, payload, out = sys.argv[1:4]
shell = open(tpl, encoding='utf-8').read()
data = open(payload, encoding='utf-8').read()
marker = '/*__PAYLOAD__*/null'
assert marker in shell, 'payload marker missing from shell.html'
open(out, 'w', encoding='utf-8').write(shell.replace(marker, data))
PY

touch "$HERE/docs/.nojekyll"
printf 'User-agent: *\nDisallow: /\n' > "$HERE/docs/robots.txt"
echo "built $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"
