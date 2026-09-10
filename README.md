# honeymoon

An encrypted static page. The repo holds AES-256-CBC ciphertext only; no
plaintext of the planner is ever committed, and none is in the git history.

## Two passcodes, two different documents

| Passcode file      | Who        | What they get |
|--------------------|------------|---------------|
| `.passcode`        | Ryan/Tanya | The whole master file — every price, every points balance, every booking code |
| `.passcode-guest`  | Friends & family | Costs, points and booking references removed; the Cards tab dropped entirely |

These are two **independent encrypted payloads**, not one page with things
hidden by CSS. The guest payload is built from a genuinely different HTML
document, so the numbers are not present in the bytes a guest can decrypt.
Nobody gets at them by opening View Source.

Registry gift prices (`$360 registry`) are the deliberate exception — the page
invites friends to chip in toward those, so they stay visible in both versions.

## Publishing an update

After editing `../honeymoon_itinerary_master.html`:

```bash
./publish.sh
```

Re-runs the redactor, re-encrypts both payloads, commits, pushes. Live in ~1 min.

## Changing a passcode

```bash
./publish.sh 'newfullpass' 'newguestpass'
```

Both are cached in `.passcode` / `.passcode-guest` (gitignored, chmod 600), so a
plain `./publish.sh` keeps using them.

## The redactor

`redact.py` builds the guest document. It removes:

- every `$`, `IDR`, `NNK` points and `N,NNN pts` figure
- every booking reference, collected structurally from `data-copy="..."`
  attributes, so a booking added to the master is redacted automatically
- the personal email and the villa host's private WhatsApp number
- the whole Cards (points strategy) tab

It then **verifies its own output** and refuses to write the guest file if any
money-shaped string survived. That check is the real safety net — if you add a
cost in a format it doesn't recognise, the build fails loudly instead of
quietly publishing the number. Run `python3 redact.py <in> <out> --report` to
see exactly what was caught.
