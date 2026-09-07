# rt-planner

An encrypted static page. The only thing stored here is AES-256-CBC ciphertext;
the plaintext never enters this repository or its history.

## Publishing an update

After editing `../honeymoon_itinerary_master.html`:

```bash
./publish.sh
```

That re-encrypts the master file into `docs/index.html`, commits, and pushes.
GitHub Pages serves it about a minute later.

## Changing the passcode

```bash
./publish.sh 'new passcode here'
```

The passcode is cached in `.passcode` (gitignored, chmod 600) so plain
`./publish.sh` keeps using it.

## How the gate works

- PBKDF2-HMAC-SHA256, 250,000 iterations, random 16-byte salt -> 256-bit key
- AES-256-CBC with a random IV
- SHA-256 of the plaintext is checked after decryption to confirm the passcode
- Decryption happens in the browser via WebCrypto; the passcode is never sent anywhere
- The unlocked passcode is kept in `localStorage`, so a visitor types it once per device
