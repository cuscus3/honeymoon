#!/usr/bin/env python3
"""Produce the guest version of the planner: itinerary intact, money removed.

Usage: python3 redact.py <in.html> <out.html> [--report]

The guest file is a genuinely different document — the numbers are not present
in it at all, so they cannot be recovered from the page source. It is encrypted
under its own passcode by build.sh.
"""
import re, sys, collections

DOT = '•••'          # •••
BLOCK = '█' * 6                # ██████ for confirmation codes

# Literal secrets. Booking references are collected structurally from every
# data-copy="..." attribute, so a new booking added to the master is redacted
# automatically rather than needing to be listed here by hand.
FIXED_LITERALS = [
    'ryan.mccusker@icloud.com',      # personal email
    '+62 877 6173 3522',             # Alit, the Suara Jiwa host — private WhatsApp
    '6287761733522',                 # ...and the same number inside the wa.me link
]

def collect_literals(s):
    codes = set(re.findall(r'data-copy="([^"]+)"', s))
    return sorted(codes, key=len, reverse=True) + FIXED_LITERALS

# Ordered: longest/most specific first so they don't clip each other.
RULES = [
    # IDR 3,902,240  /  IDR 544.5K
    (re.compile(r'IDR\s?[\d,]+(?:\.\d+)?K?'),                      lambda m: f'IDR {DOT}'),
    # $2,238  $179  ~$295  $26
    (re.compile(r'\$\s?\d[\d,]*(?:\.\d{2})?'),                     lambda m: f'${DOT}'),
    # 104,500 pts / 6,700 points / 83,000 miles
    (re.compile(r'\b\d[\d,]*\s*(pts|points|miles)\b', re.I),       lambda m: f'{DOT} {m.group(1)}'),
    # 120K, 70–80K, 100.3K, 200.6K  — points/miles. NOT "3K+ Google reviews".
    (re.compile(r'\b\d{1,3}(?:\.\d+)?(?:\s?[–—-]\s?\d{1,3}(?:\.\d+)?)?K\b(?!\+?\s*(?:\+\s*)?Google)'),
                                                                   lambda m: f'{DOT}K'),
    # bare points balances in tables: 139,332 / 24,364 (4+ digits, comma grouped, not a year)
    (re.compile(r'\b\d{1,3},\d{3}(?:,\d{3})*\b'),                  lambda m: DOT),
]

BANNER = (
  '<div style="max-width:1100px;margin:18px auto 0;padding:12px 16px;'
  'background:rgba(196,149,106,0.10);border:1px solid rgba(196,149,106,0.35);'
  'border-radius:10px;color:#c9b79c;font-size:13px;line-height:1.5;">'
  '<strong style="color:#e6d5bd;">Prices are hidden in this view.</strong> '
  'Everything else &mdash; the days, the places, the food, the maps &mdash; is exactly '
  'what we&rsquo;re doing. The <span style="font-family:monospace;">' + DOT + '</span> '
  'marks are where a number used to be. Registry gift amounts are still shown.</div>'
)

def strip_cards_tab(s):
    """Remove the Cards (points strategy) tab button and its whole section."""
    n_before = len(s)
    s = re.sub(r'<button class="tab"[^>]*data-tab="cards".*?</button>\s*', '', s, flags=re.S)
    m = re.search(r'<section[^>]*id="section-cards"[^>]*>', s)
    if m:
        # find the matching close by scanning nested <section>
        i, depth, j = m.start(), 0, m.start()
        for t in re.finditer(r'</?section\b', s[m.start():]):
            if t.group().startswith('</'):
                depth -= 1
                if depth == 0:
                    j = m.start() + t.end() + len('>')
                    break
            else:
                depth += 1
        s = s[:i] + s[j:]
    return s, n_before - len(s)

# Registry prices are the deliberate exception: the page tells friends and
# family these are gifts they can chip in toward, so hiding them defeats the
# point. Stash them before redacting, put them back after.
REGISTRY = re.compile(r'\$\s?[\d,]+(?:\.\d{2})?\s*registry', re.I)

def redact(s):
    counts = collections.Counter()
    samples = collections.defaultdict(set)

    kept = []
    def keep(m):
        kept.append(m.group(0)); return f'@@KEEP{len(kept)-1}@@'
    s = REGISTRY.sub(keep, s)
    counts['kept: registry gift prices'] = len(kept)

    for lit in collect_literals(s) :
        c = s.count(lit)
        if c:
            s = s.replace(lit, BLOCK)
            counts['literal:' + lit] += c

    # Protect the <style> block wholesale.
    styles = []
    def stash(m):
        styles.append(m.group(0)); return f'@@STYLE{len(styles)-1}@@'
    s = re.sub(r'<style\b[^>]*>.*?</style>', stash, s, flags=re.S)

    # Split into tags and text. Odd indices are tags — their attributes hold
    # rgba()/hex colours that look like money, so only text is ever rewritten.
    # Script bodies fall out as text, which is what we want: their data strings
    # carry prices that render into the page.
    parts = re.split(r'(<[^>]+>)', s)
    for i in range(0, len(parts), 2):
        chunk = parts[i]
        if not chunk:
            continue
        for rx, rep in RULES:
            key = rx.pattern[:28]
            def sub(m, key=key, rep=rep):
                counts[key] += 1
                if len(samples[key]) < 8:
                    samples[key].add(m.group(0))
                return rep(m)
            chunk = rx.sub(sub, chunk)
        parts[i] = chunk
    s = ''.join(parts)

    for i, blk in enumerate(styles):
        s = s.replace(f'@@STYLE{i}@@', blk)

    for i, k in enumerate(kept):
        s = s.replace(f'@@KEEP{i}@@', k)

    s = s.replace('<main>', '<main>' + BANNER, 1)
    return s, counts, samples

def verify(s, orig_literals):
    """Anything money-shaped left in the guest file is a leak."""
    body = re.sub(r'<style\b[^>]*>.*?</style>', '', s, flags=re.S)
    body = re.sub(r'<[^>]+>', ' ', body)   # drop tags; attributes are not user-visible
    leaks = []
    checks = [r'\$\s?\d', r'IDR\s?\d', r'\b\d{1,3}(?:\.\d+)?K\b',
              r'\b\d[\d,]*\s*(?:pts|points|miles)\b', r'\b\d{1,3},\d{3}\b']
    # Check against the ORIGINAL secrets, not ones re-read from the redacted
    # output — otherwise this matches its own replacement glyph.
    checks += [re.escape(l) for l in orig_literals]
    for rx in checks:
        for m in re.finditer(rx, body):
            ctx = re.sub(r'\s+', ' ', body[max(0, m.start()-60):m.end()+40])
            if 'Google' in ctx and 'review' in ctx.lower():
                continue          # "3K+ Google reviews" — a review count, not money
            if re.match(r'^\$\s?[\d,]+', m.group(0)) and re.search(
                    r'^\$\s?[\d,.]+\s*registry', body[m.start():m.start()+40], re.I):
                continue          # registry gift price — kept on purpose
            leaks.append((m.group(0), ctx.strip()))
    return leaks

def main():
    src, dst = sys.argv[1], sys.argv[2]
    s = open(src, encoding='utf-8').read()
    orig = len(s)
    orig_literals = collect_literals(s)
    s, dropped = strip_cards_tab(s)
    s, counts, samples = redact(s)
    leaks = verify(s, orig_literals)

    if '--report' in sys.argv:
        print(f'  Cards tab removed: {dropped:,} chars')
        for k, v in counts.most_common():
            ex = ', '.join(sorted(samples[k])[:6]) if k in samples else ''
            print(f'  {v:5}x  {k:32} {ex}')
        print(f'  {orig:,} -> {len(s):,} chars')

    if leaks:
        print(f'\n  !! {len(leaks)} MONEY-SHAPED STRINGS SURVIVED — not writing guest file:', file=sys.stderr)
        for tok, ctx in leaks[:20]:
            print(f'     {tok!r}  ...{ctx}...', file=sys.stderr)
        sys.exit(1)

    open(dst, 'w', encoding='utf-8').write(s)
    print(f'  guest file clean: 0 money-shaped strings remain')

if __name__ == '__main__':
    main()
