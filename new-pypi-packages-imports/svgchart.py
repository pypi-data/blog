"""Small inline-SVG charts for the blog. Colours are the site's CSS variables.

The viewBox is 580 wide and font sizes are in viewBox units: the post column is
328 px on a 360 px phone (16 px gutters), so 22 units show as 12.4 px. Pair
with CSS `svg { width: 100%; height: auto; max-width: 580px }`.
"""
from xml.sax.saxutils import escape

W = 580
FONT = 22          # labels and values
TITLE_FONT = 22
CHAR = 0.6         # average glyph width as a fraction of the font size
PAD = 8


def _wrap(text, size, width):
    limit = max(10, int(width / (size * CHAR)))
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > limit:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + [cur] if cur else lines


def _head(title, unit):
    """Title lines and the unit line; returns (svg, y below the header)."""
    out, y = [], PAD
    for line in _wrap(title, TITLE_FONT, W - 2 * PAD):
        y += TITLE_FONT * 1.25
        out.append(f'<text x="{PAD}" y="{y:.0f}" font-size="{TITLE_FONT}" font-weight="600" '
                   f'fill="var(--ink)">{escape(line)}</text>')
    y += FONT * 1.2
    out.append(f'<text x="{PAD}" y="{y:.0f}" font-size="{FONT}" fill="var(--muted)">'
               f'{escape(unit)}</text>')
    return "".join(out), y + 14


def _svg(title, rows, fmt, height, body):
    aria = f"{title}: " + ", ".join(f"{label} {fmt.format(v)}" for label, v in rows)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height:.0f}" role="img" '
            f'aria-label="{escape(aria, {chr(34): "&quot;"})}" width="100%" '
            f'style="width:100%;height:auto" font-family="inherit">{body}</svg>')


def hbar(rows, *, title, unit, fmt="{:,.0f}"):
    head, y = _head(title, unit)
    label_w = max(len(l) for l, _ in rows) * FONT * CHAR
    value_w = max(len(fmt.format(v)) for _, v in rows) * FONT * CHAR
    x0 = PAD + label_w + 12
    bar_max = W - PAD - x0 - value_w - 10
    top = max(v for _, v in rows) or 1
    row_h, bar_h = 40, 26
    body = [head]
    for label, v in rows:
        w = max(2.0, bar_max * v / top)
        mid = y + row_h / 2
        body.append(f'<text x="{PAD + label_w:.0f}" y="{mid + FONT * 0.35:.0f}" text-anchor="end" '
                    f'font-size="{FONT}" fill="var(--ink)">{escape(label)}</text>')
        body.append(f'<rect x="{x0:.0f}" y="{mid - bar_h / 2:.0f}" width="{w:.0f}" height="{bar_h}" '
                    f'rx="3" fill="var(--primary)"/>')
        body.append(f'<text x="{x0 + w + 8:.0f}" y="{mid + FONT * 0.35:.0f}" font-size="{FONT}" '
                    f'font-weight="600" fill="var(--ink)">{escape(fmt.format(v))}</text>')
        y += row_h
    return _svg(title, rows, fmt, y + PAD, "".join(body))


def columns(rows, *, title, unit, fmt):
    """Labels may hold one space: the part after it goes on a second line."""
    head, y = _head(title, unit)
    n = len(rows)
    slot = (W - 2 * PAD) / n
    bar_w = slot * 0.7
    plot_h = 240
    top = max(v for _, v in rows) or 1
    y += FONT + 6                       # room for the tallest value label
    base = y + plot_h
    body = [head, f'<line x1="{PAD}" y1="{base:.0f}" x2="{W - PAD}" y2="{base:.0f}" '
                  f'stroke="var(--line)" stroke-width="2"/>']
    for i, (label, v) in enumerate(rows):
        h = max(2.0, plot_h * v / top)
        cx = PAD + slot * (i + 0.5)
        body.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{base - h:.1f}" width="{bar_w:.1f}" '
                    f'height="{h:.1f}" rx="3" fill="var(--primary)"/>')
        body.append(f'<text x="{cx:.1f}" y="{base - h - 6:.1f}" text-anchor="middle" '
                    f'font-size="{FONT}" font-weight="600" fill="var(--ink)">{escape(fmt.format(v))}</text>')
        top_line, _, low = label.partition(" ")
        body.append(f'<text x="{cx:.1f}" y="{base + FONT:.0f}" text-anchor="middle" '
                    f'font-size="{FONT}" fill="var(--ink)">{escape(top_line)}</text>')
        if low:
            body.append(f'<text x="{cx:.1f}" y="{base + FONT * 2:.0f}" text-anchor="middle" '
                        f'font-size="{FONT}" fill="var(--muted)">{escape(low)}</text>')
    return _svg(title, rows, fmt, base + FONT * 2 + 14, "".join(body))


CARD_W = 560       # narrow card: 22-unit text is 12.9 px when shown 328 px wide


def card(rows, *, title, sub, note, foot, width=CARD_W):
    """Results card: the post's answer in one image, shown under the H1.

    rows: [(label, [(value, setup, mark)])] with one or two cells per row;
    mark is "win" (green, with a check mark) or "" (neutral). The setup line
    under each value says what was counted. At width >= 1000 (the og:image
    version) the row label sits left of the cells instead of above them.
    """
    gap, cell_pad, val_font, title_font = 12, 14, 34, 30
    wide = width >= 1000
    label_w = 300 if wide else 0
    out, y = [], PAD
    for line in _wrap(title, title_font, width - 2 * PAD):
        y += title_font * 1.2
        out.append(f'<text x="{PAD}" y="{y:.0f}" font-size="{title_font}" font-weight="800" '
                   f'fill="var(--strong)">{escape(line)}</text>')
    y += FONT * 1.3
    out.append(f'<text x="{PAD}" y="{y:.0f}" font-size="{FONT}" fill="var(--muted)">{escape(sub)}</text>')
    y += 18
    aria = [title + "."]
    for label, cells in rows:
        x0 = PAD + label_w
        cw = (width - x0 - PAD - gap * (len(cells) - 1)) / len(cells)
        wrapped = [_wrap(setup, FONT, cw - 2 * cell_pad) for _, setup, _ in cells]
        ch = cell_pad + val_font + 8 + FONT * 1.2 * max(len(w) for w in wrapped) + cell_pad - 4
        if wide:
            label_lines = _wrap(label, FONT, label_w - 16)
            ly0 = y + ch / 2 - FONT * 1.2 * (len(label_lines) - 1) / 2 + FONT * 0.35
            for k, line in enumerate(label_lines):
                out.append(f'<text x="{PAD}" y="{ly0 + FONT * 1.2 * k:.0f}" font-size="{FONT}" '
                           f'font-weight="700" fill="var(--primary)">{escape(line)}</text>')
        else:
            y += FONT
            out.append(f'<text x="{PAD}" y="{y:.0f}" font-size="{FONT}" font-weight="700" '
                       f'fill="var(--primary)">{escape(label)}</text>')
            y += 10
        parts = []
        for i, ((value, setup, mark), lines) in enumerate(zip(cells, wrapped)):
            x = x0 + i * (cw + gap)
            win = mark == "win"
            out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{cw:.0f}" height="{ch:.0f}" rx="10" '
                       f'fill="var(--b2)" stroke="{"var(--win)" if win else "var(--line)"}" stroke-width="2"/>')
            vy = y + cell_pad + val_font * 0.85
            shown = value + (" \u2713" if win else "")
            out.append(f'<text x="{x + cell_pad:.0f}" y="{vy:.0f}" font-size="{val_font}" font-weight="800" '
                       f'fill="{"var(--win)" if win else "var(--strong)"}">{escape(shown)}</text>')
            for k, line in enumerate(lines):
                ly = vy + 8 + FONT * 1.2 * (k + 1)
                out.append(f'<text x="{x + cell_pad:.0f}" y="{ly:.0f}" font-size="{FONT}" '
                           f'fill="var(--muted)">{escape(line)}</text>')
            parts.append(f"{value} ({setup})")
        aria.append(f"{label}: " + " vs ".join(parts) + ".")
        y += ch + (10 if wide else 14)
    note_lines = _wrap(note, FONT, width - 2 * PAD - 2 * cell_pad)
    nh = cell_pad * 2 + FONT * 1.25 * len(note_lines) - 6
    y += 4
    out.append(f'<rect x="{PAD}" y="{y:.0f}" width="{width - 2 * PAD}" height="{nh:.0f}" rx="10" '
               f'fill="var(--b3)" stroke="var(--warn)" stroke-width="2"/>')
    for k, line in enumerate(note_lines):
        out.append(f'<text x="{PAD + cell_pad}" y="{y + cell_pad + FONT * (0.85 + 1.25 * k):.0f}" '
                   f'font-size="{FONT}" fill="var(--strong)">{escape(line)}</text>')
    y += nh + 10
    for line in _wrap(foot, FONT, width - 2 * PAD):
        y += FONT * 1.25
        out.append(f'<text x="{PAD}" y="{y:.0f}" font-size="{FONT}" fill="var(--muted)">{escape(line)}</text>')
    aria += [note, foot]
    height = y + PAD + 4
    label = escape(" ".join(aria), {chr(34): "&quot;"})
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height:.0f}" role="img" '
            f'aria-label="{label}" width="100%" style="width:100%;height:auto" font-family="inherit">'
            f'{"".join(out)}</svg>')
