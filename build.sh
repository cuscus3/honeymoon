#!/usr/bin/env bash
# Encrypt the planner into docs/index.html as TWO independent payloads:
#   full  — the whole master file            (unlocked by .passcode)
#   guest — costs and booking refs removed   (unlocked by .passcode-guest)
# The guest payload is a genuinely different document: the numbers are not in
# it, so they cannot be recovered from the published page by any means.
#
#   ./build.sh                    use the saved passcodes
#   ./build.sh FULLPASS GUESTPASS set/replace them
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../honeymoon_itinerary_master.html"
TPL="$HERE/shell.html"
OUT="$HERE/docs/index.html"
ITER=250000

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

read_pass() {   # $1=file  $2=cli value  $3=prompt
  local f="$HERE/$1"
  if [ -n "${2:-}" ]; then printf '%s' "$2" > "$f"; chmod 600 "$f"; fi
  [ -f "$f" ] || { read -r -s -p "$3: " v; echo; printf '%s' "$v" > "$f"; chmod 600 "$f"; }
  cat "$f"
}
FULL_PASS="$(read_pass .passcode       "${1:-}" 'Full passcode')"
GUEST_PASS="$(read_pass .passcode-guest "${2:-}" 'Guest passcode')"
[ -n "$FULL_PASS" ] && [ -n "$GUEST_PASS" ] || { echo "error: empty passcode" >&2; exit 1; }
[ "$FULL_PASS" != "$GUEST_PASS" ] || { echo "error: the two passcodes must differ" >&2; exit 1; }
[ -f "$SRC" ] || { echo "error: missing $SRC" >&2; exit 1; }

# --- guest variant (aborts if any money-shaped string survives) --------------
echo "Building guest variant:"
python3 "$HERE/redact.py" "$SRC" "$TMP/guest.html" --report

encrypt_one() {   # $1=plaintext file  $2=passcode  -> JSON object on stdout
  local salt iv key ct sha
  salt="$(openssl rand -hex 16)"; iv="$(openssl rand -hex 16)"
  key="$(openssl kdf -keylen 32 -kdfopt digest:SHA256 \
          -kdfopt hexpass:"$(printf '%s' "$2" | xxd -p -c 4096 | tr -d '\n')" \
          -kdfopt hexsalt:"$salt" -kdfopt iter:"$ITER" -binary PBKDF2 \
        | xxd -p -c 4096 | tr -d '\n')"
  openssl enc -aes-256-cbc -K "$key" -iv "$iv" -in "$1" -out "$1.enc"
  ct="$(base64 < "$1.enc" | tr -d '\n')"
  sha="$(openssl dgst -sha256 -hex < "$1" | awk '{print $NF}')"
  printf '{"salt":"%s","iv":"%s","iter":%s,"sha256":"%s","ct":"%s"}' \
    "$(printf '%s' "$salt" | xxd -r -p | base64 | tr -d '\n')" \
    "$(printf '%s' "$iv"   | xxd -r -p | base64 | tr -d '\n')" \
    "$ITER" "$sha" "$ct"
}

cp "$SRC" "$TMP/full.html"
{ printf '{"full":';  encrypt_one "$TMP/full.html"  "$FULL_PASS"
  printf ',"guest":'; encrypt_one "$TMP/guest.html" "$GUEST_PASS"
  printf '}'; } > "$TMP/payload.json"

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
