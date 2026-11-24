#!/usr/bin/env python3
"""Turn results/summary.json into article assets.

    python charts.py --results results/my-model            # SVGs + report.md (+ rasters if Chrome found)
    python charts.py --results results/my-model --svg-only
    python charts.py --results results/my-model --brand example.com   # footer on cover/carousel

Writes into <results>/charts/ (or --out):
  *.svg                   theme-aware (follows prefers-color-scheme)
  *.jpg / *-dark.jpg      light and dark, 2x, for social posts   (needs Chrome)
  cover.jpg, linkedin-carousel.pdf                                (needs Chrome)
and <results>/report.md with every number in a table.

Colours are the dataviz reference palette, validated for CVD in both modes:
series-1 blue, series-2 orange, on #fcfcfb / #1a1a19 chart surfaces. Every
chart carries its own opaque surface, so it never depends on the aurora behind
it for contrast.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import statistics as st
import subprocess
import tempfile
from collections import defaultdict
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results", "latest")   # set from --results in main()
ASSETS = os.path.join(RES, "charts")            # set from --out in main()
BRAND = ""
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
HAVE_CWEBP = shutil.which("cwebp") is not None
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, monospace"

STYLE = """
<style>
  .s{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#6b6a65;--grid:#e1e0d9;--axis:#c3c2b7;
     --s1:#2a78d6;--s2:#eb6834;--good:#0ca30c;--bad:#d03b3b;--ring:rgba(11,11,11,.10)}
  @media (prefers-color-scheme: dark){
  .s{--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#a3a29b;--grid:#2c2c2a;--axis:#383835;
     --s1:#3987e5;--s2:#d95926;--good:#0ca30c;--bad:#e66767;--ring:rgba(255,255,255,.10)}}
  text{font-family:%s;fill:var(--ink)}
  .t{font-size:22px;font-weight:620;letter-spacing:-.01em}
  .sub{font-size:15px;fill:var(--ink2)}
  .lbl{font-size:15px;fill:var(--ink2)}
  .val{font-size:15px;font-weight:600;fill:var(--ink)}
  .ax{font-size:13px;fill:var(--muted);font-family:%s}
  .foot{font-size:12px;fill:var(--muted);font-family:%s}
  .grid{stroke:var(--grid);stroke-width:1}
  .base{stroke:var(--axis);stroke-width:1}
</style>""" % (FONT, MONO, MONO)


def svg(w, h, body, title, desc):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="s" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-labelledby="t d"><title id="t">{escape(title)}</title><desc id="d">{escape(desc)}</desc>'
            f'{STYLE}<rect width="{w}" height="{h}" rx="16" fill="var(--surface)" stroke="var(--ring)"/>{body}</svg>')


def header(title, sub, x=32):
    return (f'<text class="t" x="{x}" y="46">{escape(title)}</text>'
            f'<text class="sub" x="{x}" y="72">{escape(sub)}</text>')


def footer(w, h, text):
    return f'<text class="foot" x="32" y="{h-20}">{escape(text)}</text>'


def bar(x, y, w, h, fill, r=4, horizontal=True):
    """Rounded data-end, square baseline end."""
    if w <= 0 or h <= 0:
        return ""
    r = min(r, (h if horizontal else w) / 2, (w if horizontal else h))
    if horizontal:  # baseline on the left
        return (f'<path d="M{x},{y} H{x+w-r} Q{x+w},{y} {x+w},{y+r} V{y+h-r} Q{x+w},{y+h} {x+w-r},{y+h} '
                f'H{x} Z" fill="{fill}"/>')
    return (f'<path d="M{x},{y+h} V{y+r} Q{x},{y} {x+r},{y} H{x+w-r} Q{x+w},{y} {x+w},{y+r} V{y+h} Z" '
            f'fill="{fill}"/>')


def nice_max(v, ticks=4):
    """Round an axis max up so each of `ticks` steps is 1/2/2.5/5 x 10^k."""
    import math
    raw = v / ticks
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    return step * ticks


def pct(rows):
    rows = [r for r in rows if "passed" in r]
    return (sum(bool(r["passed"]) for r in rows), len(rows))


# ------------------------------------------------------------------ charts --
def chart_accuracy(S, env):
    cats = [("Tool calling", "tools"), ("Vision", "vision"), ("Long-context recall", "needle"),
            ("Python coding", "coding"), ("Elixir coding", "elixir"),
            ("Maths & reasoning", "math"), ("Instruction following", "instruct")]
    data = [(lbl, *pct(S[k])) for lbl, k in cats if S.get(k)]
    data.sort(key=lambda d: -d[1] / d[2])
    w, rowh, top, left, right = 960, 46, 104, 230, 150
    h = top + rowh * len(data) + 56
    plot = w - left - right
    b = header("Pass rate by task family", f"{env['model'].split('/')[-1]} · {env['quant']} · "
               f"{len(data)} families, every answer machine-checked")
    for p in (0, 25, 50, 75, 100):
        x = left + plot * p / 100
        b += f'<line class="grid" x1="{x}" y1="{top-8}" x2="{x}" y2="{top + rowh*len(data)}"/>'
        b += f'<text class="ax" x="{x}" y="{top-14}" text-anchor="middle">{p}%</text>'
    for i, (lbl, ok, n) in enumerate(data):
        y = top + i * rowh + 9
        frac = ok / n
        b += f'<text class="lbl" x="{left-14}" y="{y+19}" text-anchor="end">{escape(lbl)}</text>'
        b += bar(left, y, max(plot * frac, 2), 26, "var(--s1)")
        b += (f'<text class="val" x="{left + plot*frac + 10}" y="{y+19}">{frac:.0%}'
              f'<tspan class="ax" dx="8">{ok}/{n}</tspan></text>')
    b += f'<line class="base" x1="{left}" y1="{top-8}" x2="{left}" y2="{top + rowh*len(data)}"/>'
    b += footer(w, h, f"{env['chip']} · {env['ram_gb']} GB · samples per item: "
                      f"{S['settings'].get('coding', {}).get('samples', '?')} · default sampling")
    return "accuracy", svg(w, h, b, "Pass rate by task family",
                           "; ".join(f"{l}: {o}/{n}" for l, o, n in data)), data


def chart_decode(S, env):
    by = defaultdict(list)
    for r in S["speed"]["decode"]:
        if r.get("server_decode_tps"):
            by[r["genre"]].append(r)
    genres = [g for g in ("structured", "code", "prose") if g in by]
    names = {"structured": "JSON", "code": "Code", "prose": "Prose"}
    tps = {g: [r["server_decode_tps"] for r in by[g]] for g in genres}
    acc = {g: [r["acceptance"] for r in by[g] if r.get("acceptance") is not None] for g in genres}
    w, h = 960, 392
    b = header("Generation speed depends on what you ask for",
               "Median of runs; whiskers show min–max. The draft model guesses 2 tokens ahead.")
    panels = [("Tokens per second", tps, lambda v: f"{v:.1f}", 32, "var(--s1)"),
              ("Draft tokens accepted", acc, lambda v: f"{v:.0%}", 500, "var(--s1)")]
    for title, d, fmt, x0, fill in panels:
        top, ph, pw, left = 128, 170, 400, x0 + 70
        vmax = 1.0 if "accepted" in title else max(max(v) for v in d.values()) * 1.15
        b += f'<text class="lbl" x="{x0}" y="108" style="font-weight:600;fill:var(--ink)">{title}</text>'
        bw, gap = 60, (pw - 70 - 60 * len(genres)) / max(len(genres), 1)
        for i, g in enumerate(genres):
            vals = d[g]
            if not vals:
                continue
            med = st.median(vals)
            x = left + i * (bw + gap) + gap / 2
            bh = ph * med / vmax
            b += bar(x, top + ph - bh, bw, bh, fill, horizontal=False)
            lo, hi = top + ph - ph * min(vals) / vmax, top + ph - ph * max(vals) / vmax
            if len(vals) > 1 and abs(lo - hi) > 2:
                cx = x + bw / 2
                b += (f'<line x1="{cx}" y1="{lo}" x2="{cx}" y2="{hi}" stroke="var(--ink2)" stroke-width="1.5"/>'
                      f'<line x1="{cx-6}" y1="{hi}" x2="{cx+6}" y2="{hi}" stroke="var(--ink2)" stroke-width="1.5"/>'
                      f'<line x1="{cx-6}" y1="{lo}" x2="{cx+6}" y2="{lo}" stroke="var(--ink2)" stroke-width="1.5"/>')
            b += f'<text class="val" x="{x+bw/2}" y="{min(top+ph-bh, hi)-10}" text-anchor="middle">{fmt(med)}</text>'
            b += f'<text class="lbl" x="{x+bw/2}" y="{top+ph+24}" text-anchor="middle">{names[g]}</text>'
        b += f'<line class="base" x1="{left-10}" y1="{top+ph}" x2="{x0+pw}" y2="{top+ph}"/>'
    b += footer(w, h, f"{env['chip']} · server-reported timings (llama.cpp), one request at a time, idle server")
    desc = "; ".join(f"{names[g]}: {st.median(tps[g]):.1f} tok/s, {st.median(acc[g]) if acc[g] else 0:.0%} accepted"
                     for g in genres)
    return "decode", svg(w, h, b, "Generation speed by output type", desc), {
        g: {"tps_median": st.median(tps[g]), "tps_min": min(tps[g]), "tps_max": max(tps[g]),
            "accept_median": st.median(acc[g]) if acc[g] else None, "n": len(tps[g])} for g in genres}


def chart_prefill(S, env):
    pts = defaultdict(list)
    for r in S["speed"]["prefill"]:
        # Server-measured prompt processing time. Client TTFT is useless here:
        # with max_tokens=1 the single token never arrives as a stream delta.
        pm = (r.get("server_timings") or {}).get("prompt_ms")
        if r.get("ok") and r.get("prompt_tokens") and pm:
            pts[r["target"]].append({**r, "ttft_s": pm / 1000})
    xs = sorted(pts)
    agg = [(st.median([r["prompt_tokens"] for r in pts[t]]), st.median([r["ttft_s"] for r in pts[t]]),
            st.median([r.get("server_prefill_tps") or 0 for r in pts[t]])) for t in xs]
    w, h, left, top, pw, ph = 960, 400, 90, 110, 780, 220
    import math
    lx0, lx1 = math.log10(min(a[0] for a in agg)) - 0.08, math.log10(max(a[0] for a in agg)) + 0.08
    ymax = nice_max(max(a[1] for a in agg) * 1.1)
    b = header("How long before the first word appears",
               "Time to read the prompt before answering. Fresh prompts, no cache hits.")
    for i in range(5):
        y = top + ph - ph * i / 4
        b += f'<line class="grid" x1="{left}" y1="{y}" x2="{left+pw}" y2="{y}"/>'
        b += f'<text class="ax" x="{left-10}" y="{y+4}" text-anchor="end">{ymax*i/4:.0f}s</text>'
    X = lambda v: left + pw * (math.log10(v) - lx0) / (lx1 - lx0)  # noqa: E731
    Y = lambda v: top + ph - ph * v / ymax  # noqa: E731
    path = " ".join(f"{'M' if i == 0 else 'L'}{X(a[0]):.1f},{Y(a[1]):.1f}" for i, a in enumerate(agg))
    b += f'<path d="{path}" fill="none" stroke="var(--s1)" stroke-width="2"/>'
    for n, t, tps in agg:
        b += f'<circle cx="{X(n)}" cy="{Y(t)}" r="5" fill="var(--s1)" stroke="var(--surface)" stroke-width="2"/>'
        b += f'<text class="val" x="{X(n)}" y="{Y(t)-14}" text-anchor="middle">{t:.1f}s</text>'
        b += f'<text class="ax" x="{X(n)}" y="{top+ph+22}" text-anchor="middle">{n/1000:.1f}k</text>'
    b += f'<line class="base" x1="{left}" y1="{top+ph}" x2="{left+pw}" y2="{top+ph}"/>'
    b += f'<text class="ax" x="{left+pw}" y="{top+ph+44}" text-anchor="end">prompt tokens (log scale)</text>'
    lo, hi = min(a[2] for a in agg if a[2]), max(a[2] for a in agg)
    b += footer(w, h, f"Server prefill rate {lo:,.0f}–{hi:,.0f} tok/s · {env['chip']}")
    return "prefill", svg(w, h, b, "Time to first token vs prompt length",
                          "; ".join(f"{n:.0f} tokens: {t:.1f}s" for n, t, _ in agg)), agg


def chart_concurrency(S, env):
    rows = sorted(S["speed"]["concurrency"], key=lambda r: r["n"])
    w, h, left, top, pw, ph = 960, 400, 90, 110, 700, 220
    ymax = nice_max(max(r["aggregate_tps"] for r in rows) * 1.1)
    ns = [r["n"] for r in rows]
    X = lambda n: left + pw * (ns.index(n)) / max(len(ns) - 1, 1)  # noqa: E731
    Y = lambda v: top + ph - ph * v / ymax  # noqa: E731
    b = header("More users, less speed each", "Several requests at once. The server has 4 slots.")
    for i in range(5):
        y = top + ph - ph * i / 4
        b += f'<line class="grid" x1="{left}" y1="{y}" x2="{left+pw}" y2="{y}"/>'
        b += f'<text class="ax" x="{left-10}" y="{y+4}" text-anchor="end">{ymax*i/4:.0f}</text>'
    for key, color, name in (("aggregate_tps", "var(--s1)", "Total tok/s"),
                             ("per_request_tps", "var(--s2)", "Per request tok/s")):
        path = " ".join(f"{'M' if i == 0 else 'L'}{X(r['n']):.1f},{Y(r[key]):.1f}" for i, r in enumerate(rows))
        b += f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2"/>'
        for r in rows:
            b += f'<circle cx="{X(r["n"])}" cy="{Y(r[key])}" r="5" fill="{color}" stroke="var(--surface)" stroke-width="2"/>'
            dy = -12 if key == "aggregate_tps" else 24  # total above, per-request below: never collide
            b += f'<text class="ax" x="{X(r["n"])}" y="{Y(r[key])+dy}" text-anchor="middle">{r[key]:.0f}</text>'
        last = rows[-1]
        b += f'<text class="val" x="{X(last["n"])+14}" y="{Y(last[key])+5}">{name}</text>'
    for r in rows:
        b += f'<text class="ax" x="{X(r["n"])}" y="{top+ph+22}" text-anchor="middle">{r["n"]}</text>'
    b += f'<text class="ax" x="{left+pw}" y="{top+ph+44}" text-anchor="end">concurrent requests</text>'
    b += f'<line class="base" x1="{left}" y1="{top+ph}" x2="{left+pw}" y2="{top+ph}"/>'
    # legend (2 series -> always present, plus direct labels above)
    b += (f'<rect x="{w-330}" y="36" width="12" height="12" rx="3" fill="var(--s1)"/>'
          f'<text class="lbl" x="{w-312}" y="47">Total</text>'
          f'<rect x="{w-250}" y="36" width="12" height="12" rx="3" fill="var(--s2)"/>'
          f'<text class="lbl" x="{w-232}" y="47">Per request</text>')
    b += footer(w, h, f"{env['chip']} · prose generation, 600 tokens max each")
    return "concurrency", svg(w, h, b, "Throughput vs concurrent requests",
                              "; ".join(f"{r['n']} at once: {r['aggregate_tps']:.0f} total, "
                                        f"{r['per_request_tps']:.0f} each" for r in rows)), rows


def chart_needle(S, env):
    rows = S["needle"]
    sizes = sorted({r["target"] for r in rows})
    depths = sorted({r["depth"] for r in rows})
    cell = {(r["target"], r["depth"]): r for r in rows}
    w, cw, chh, left, top = 960, 180, 52, 230, 120
    h = top + chh * len(sizes) + 60
    b = header("Finding one sentence in a long prompt",
               "A single fact hidden at 10%, 50% and 90% depth of filler text.")
    for j, d in enumerate(depths):
        b += f'<text class="lbl" x="{left + j*cw + cw/2}" y="{top-14}" text-anchor="middle">{d:.0%} deep</text>'
    for i, s in enumerate(sizes):
        y = top + i * chh
        real = [cell[(s, d)].get("prompt_tokens") for d in depths if (s, d) in cell]
        real = [x for x in real if x]
        label = f"{(st.median(real) if real else s)/1000:.0f}k tokens"
        b += f'<text class="lbl" x="{left-14}" y="{y+chh/2+5}" text-anchor="end">{label}</text>'
        for j, d in enumerate(depths):
            r = cell.get((s, d))
            x = left + j * cw
            if not r:
                continue
            ok = r["passed"]
            err = not r.get("ok", True)
            color = "var(--good)" if ok else "var(--bad)"
            mark = "✓ found" if ok else ("✕ error" if err else "✕ missed")
            b += (f'<rect x="{x+4}" y="{y+4}" width="{cw-8}" height="{chh-8}" rx="8" fill="{color}" '
                  f'fill-opacity=".14" stroke="{color}" stroke-opacity=".6"/>'
                  f'<text class="val" x="{x+cw/2}" y="{y+chh/2+5}" text-anchor="middle">{mark}</text>')
    ok, n = pct(rows)
    b += footer(w, h, f"{ok}/{n} found · context window {env['context_length']:,} tokens as loaded "
                      f"(native {env['native_context_length']:,})")
    return "needle", svg(w, h, b, "Needle-in-a-haystack recall",
                         f"{ok} of {n} placements recalled"), {"ok": ok, "n": n}


def chart_thinking():
    """Share of generated text that was reasoning, per suite (from raw transcripts)."""
    suites = [("Maths", "math"), ("Python coding", "coding_python"), ("Elixir coding", "coding_elixir")]
    # (instruct transcripts don't record the reasoning channel, so it can't be measured there)
    data = []
    for lbl, f in suites:
        p = os.path.join(RES, "raw", f"{f}.jsonl")
        if not os.path.exists(p):
            continue
        rc = cc = 0
        toks = []
        for line in open(p):
            r = json.loads(line)
            rc += len(r.get("reasoning") or "")
            cc += len(r.get("content") or "")
            if r.get("completion_tokens"):
                toks.append(r["completion_tokens"])
        if rc + cc:
            data.append((lbl, rc / (rc + cc), st.median(toks) if toks else 0))
    if not data:
        return None
    w, rowh, top, left, right = 960, 50, 118, 230, 150
    h = top + rowh * len(data) + 60
    plot = w - left - right
    b = header("Most of what it writes, you never read",
               "Share of generated text spent thinking before the answer.")
    b += (f'<rect x="{w-330}" y="36" width="12" height="12" rx="3" fill="var(--s1)"/>'
          f'<text class="lbl" x="{w-312}" y="47">Thinking</text>'
          f'<rect x="{w-220}" y="36" width="12" height="12" rx="3" fill="var(--s2)"/>'
          f'<text class="lbl" x="{w-202}" y="47">Answer</text>')
    for i, (lbl, share, med) in enumerate(data):
        y = top + i * rowh
        tw = plot * share
        b += f'<text class="lbl" x="{left-14}" y="{y+20}" text-anchor="end">{escape(lbl)}</text>'
        b += f'<rect x="{left}" y="{y+4}" width="{max(tw-1,0)}" height="24" fill="var(--s1)"/>'
        b += bar(left + tw + 1, y + 4, max(plot - tw - 1, 0), 24, "var(--s2)")
        if tw > 70:
            b += f'<text x="{left+10}" y="{y+21}" style="font-size:14px;font-weight:600;fill:#fff">{share:.0%}</text>'
        b += f'<text class="ax" x="{left+plot+12}" y="{y+21}">~{med:,.0f} tok</text>'
    b += footer(w, h, "By character count of the reasoning vs answer channels · right: median tokens per reply")
    return "thinking", svg(w, h, b, "Share of output spent thinking",
                           "; ".join(f"{l}: {s:.0%} thinking, median {m:.0f} tokens" for l, s, m in data)), data


# ------------------------------------------------------------------ render --
def _to_jpg(png, dest_noext, q):
    if shutil.which("sips"):
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(q), png,
                        "--out", dest_noext + ".jpg"], check=True, capture_output=True)
    else:
        shutil.copy(png, dest_noext + ".png")
    if HAVE_CWEBP:
        subprocess.run(["cwebp", "-quiet", "-q", str(q), png, "-o", dest_noext + ".webp"], check=True)


def themed(svg_text, mode):
    """Pin a theme: light drops the dark media block, dark makes it unconditional."""
    if mode == "dark":
        return svg_text.replace("@media (prefers-color-scheme: dark){", "@media all{")
    return re.sub(r"@media \(prefers-color-scheme: dark\)\{.*?\}\}", "", svg_text, flags=re.S)


def render(name, svg_text, scale=2):
    """SVG -> JPG + WebP via headless Chrome, 2x, once per theme."""
    for mode, suffix, bg in (("light", "", "#fcfcfb"), ("dark", "-dark", "#1a1a19")):
        _render(f"{name}{suffix}", themed(svg_text, mode), bg, scale)


def _render(name, svg_text, bg, scale):
    w = int(svg_text.split('width="')[1].split('"')[0])
    h = int(svg_text.split('height="')[1].split('"')[0])
    with tempfile.TemporaryDirectory() as d:
        html = os.path.join(d, "c.html")
        png = os.path.join(d, "c.png")
        with open(html, "w") as f:
            f.write(f"<!doctype html><meta charset=utf-8><style>html,body{{margin:0;background:{bg}}}"
                    f"svg{{display:block}}</style>{svg_text}")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--force-device-scale-factor={scale}", f"--window-size={w},{h}",
                        f"--screenshot={png}", f"file://{html}"], check=True, capture_output=True)
        _to_jpg(png, os.path.join(ASSETS, name), 88)


# ----------------------------------------------------------- cover & deck --
def shoot(html, out_png, w, h, scale=1):
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "p.html")
        open(f, "w").write(html)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--force-device-scale-factor={scale}", f"--window-size={w},{h}",
                        f"--screenshot={out_png}", f"file://{f}"], check=True, capture_output=True)


def export(png, name):
    _to_jpg(png, os.path.join(ASSETS, name), 90)


DECK_CSS = """
*{box-sizing:border-box;margin:0}
body{background:#111110;color:#f0efec;font-family:%s}
.mono{font-family:%s}
""" % (FONT, MONO)


def headline_numbers(S, out):
    n = {}
    if "decode" in out:
        d = out["decode"]
        n["prose_tps"] = d.get("prose", {}).get("tps_median")
        g, best = max(d.items(), key=lambda kv: kv[1]["tps_median"])
        n["best_genre"] = {"structured": "JSON", "code": "code", "prose": "prose"}.get(g, g)
        n["best_tps"] = best["tps_median"]
    if "accuracy" in out:
        acc = {l: (o, t) for l, o, t in out["accuracy"]}
        n["acc"] = acc
    if "thinking" in out:
        n["think_math"] = next((s for l, s, _ in out["thinking"] if l == "Maths"), None)
    if "prefill" in out and out["prefill"]:
        n["ttft_long"] = out["prefill"][-1]
    return n


def cover(S, env, out):
    n = headline_numbers(S, out)
    acc = n.get("acc", {})
    py = acc.get("Python coding")
    tiles = [
        (f"{n['prose_tps']:.0f}" if n.get("prose_tps") else "—", "tokens/s writing prose"),
        (f"{py[0]/py[1]:.0%}" if py else "—", "Python tests passed"),
        (f"{n['think_math']:.0%}" if n.get("think_math") else "—", "of a maths reply is thinking"),
        (f"{env['context_length']//1000}K", f"context as loaded (of {env['native_context_length']//1048576}M)"),
    ]
    BRAND_SFX = f" · {escape(BRAND)}" if BRAND else ""
    tiles_html = "".join(f'<div class="tile"><div class="big">{escape(v)}</div><div class="cap">{escape(c)}</div></div>'
                         for v, c in tiles)
    html = f"""<!doctype html><meta charset=utf-8><style>{DECK_CSS}
    body{{width:1200px;height:630px;padding:64px 72px;display:flex;flex-direction:column;
         background:radial-gradient(900px 500px at 85% -10%,#2a4f86 0,transparent 60%),
                    radial-gradient(700px 500px at -10% 110%,#7a3a12 0,transparent 55%),#111110}}
    .k{{font-size:20px;color:#c3c2b7;letter-spacing:.02em}}
    h1{{font-size:64px;font-weight:650;letter-spacing:-.03em;line-height:1.02;margin-top:14px}}
    h1 em{{font-style:italic;font-weight:500;color:#f0b071}}
    .tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:auto}}
    .tile{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:20px 22px}}
    .big{{font-size:52px;font-weight:650;letter-spacing:-.03em;font-variant-numeric:tabular-nums}}
    .cap{{font-size:17px;color:#c3c2b7;margin-top:6px;line-height:1.25}}
    .foot{{margin-top:22px;font-size:15px;color:#a3a29b}}</style>
    <div class="k mono">LOCAL LLM BENCHMARK</div>
    <h1>Inkling-2-Mini,<br><em>on my laptop.</em></h1>
    <div class="tiles">{tiles_html}</div>
    <div class="foot mono">{escape(env['chip'])} · {env['ram_gb']} GB · Unsloth Studio · {escape(env['quant'] or '')}{BRAND_SFX}</div>"""
    with tempfile.TemporaryDirectory() as d:
        png = os.path.join(d, "cover.png")
        shoot(html, png, 1200, 630, scale=2)
        export(png, "cover")
    print("wrote cover")


def deck(S, env, out):
    """LinkedIn document post: 1080x1350 portrait slides -> one PDF."""
    n = headline_numbers(S, out)
    acc = n.get("acc", {})
    def a(l):
        return f"{acc[l][0]/acc[l][1]:.0%}" if l in acc else "—"
    slides = [("cover", None, None)]
    lines = {
        "decode": (f"{n.get('prose_tps', 0):.0f} tokens/s on prose. {n.get('best_tps', 0):.0f} on {n.get('best_genre', '')}.",
                   "A tiny draft model guesses ahead. Predictable output means more right guesses."),
        "prefill": ("Long prompts are where you wait.",
                    "Before the first word, it has to read everything you sent."),
        "concurrency": ("Four slots, one GPU.", "Total throughput rises. Everyone gets slower."),
        "accuracy": (f"Python {a('Python coding')}. Elixir {a('Elixir coding')}. Tools {a('Tool calling')}.",
                     "Fresh problems. Every answer checked by a machine."),
        "needle": ("Finding one sentence in 34K tokens.", "Long-context recall, as loaded on 64 GB."),
        "thinking": ("Most of what it writes, you never read.", "It always thinks first, and you can't switch it off from the API."),
    }
    for k in ("accuracy", "decode", "prefill", "thinking", "needle", "concurrency"):
        if os.path.exists(os.path.join(ASSETS, f"{k}-dark.jpg")):
            slides.append((k, *lines[k]))
    BRAND_SFX = f" · {escape(BRAND)}" if BRAND else ""
    pages = []
    for i, (k, h1, sub) in enumerate(slides, 1):
        if k == "cover":
            pages.append(f'<section class="p cov"><img src="file://{ASSETS}/cover.jpg"><h2>I benchmarked a local model on my laptop.</h2>'
                         f'<p>Speed, accuracy, and the bits nobody tells you. Swipe →</p><div class="n mono">{i}/{len(slides)}</div></section>')
        else:
            pages.append(f'<section class="p"><h2>{escape(h1)}</h2><p>{escape(sub)}</p>'
                         f'<img src="file://{ASSETS}/{k}-dark.jpg"><div class="n mono">{i}/{len(slides)}{BRAND_SFX}</div></section>')
    html = f"""<!doctype html><meta charset=utf-8><style>{DECK_CSS}
    @page{{size:1080px 1350px;margin:0}}
    .p{{width:1080px;height:1350px;padding:96px 64px;display:flex;flex-direction:column;page-break-after:always;
        background:radial-gradient(800px 600px at 100% 0,#1f3a63 0,transparent 60%),#111110;position:relative}}
    h2{{font-size:64px;font-weight:650;letter-spacing:-.03em;line-height:1.05}}
    p{{font-size:30px;color:#c3c2b7;margin-top:22px;line-height:1.3}}
    .p img{{width:100%;margin-top:auto;margin-bottom:auto;border-radius:16px}}
    .cov{{justify-content:center}} .cov img{{margin:0 0 56px;border-radius:20px}}
    .n{{position:absolute;bottom:48px;left:64px;font-size:20px;color:#a3a29b}}</style>{''.join(pages)}"""
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "deck.html")
        open(f, "w").write(html)
        pdf = os.path.join(ASSETS, "linkedin-carousel.pdf")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--allow-file-access-from-files", f"--print-to-pdf={pdf}", f"file://{f}"],
                       check=True, capture_output=True)
    print("wrote linkedin-carousel.pdf", len(slides), "slides")


def main():
    import argparse
    global RES, ASSETS, BRAND
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=RES, help="a results directory written by bench.py --out")
    ap.add_argument("--out", help="where charts go (default: <results>/charts)")
    ap.add_argument("--brand", default="", help="optional footer text on the cover and carousel")
    ap.add_argument("--svg-only", action="store_true", help="skip Chrome rendering")
    a = ap.parse_args()
    RES, BRAND = os.path.abspath(a.results), a.brand
    ASSETS = os.path.abspath(a.out or os.path.join(RES, "charts"))
    raster = not a.svg_only and os.path.exists(CHROME)
    if not raster and not a.svg_only:
        print(f"Chrome not found at {CHROME} (set CHROME=...); writing SVGs only")
    S = json.load(open(os.path.join(RES, "summary.json")))
    env = S["environment"]
    os.makedirs(ASSETS, exist_ok=True)
    out = {}
    makers = [lambda: chart_accuracy(S, env), lambda: chart_decode(S, env), lambda: chart_prefill(S, env),
              lambda: chart_concurrency(S, env), lambda: chart_needle(S, env), chart_thinking]
    for mk in makers:
        try:
            res = mk()
        except (KeyError, ValueError) as e:
            print("skip:", getattr(mk, "__name__", mk), repr(e))
            continue
        if not res:
            continue
        name, text, data = res
        with open(os.path.join(ASSETS, f"{name}.svg"), "w") as f:
            f.write(text)
        if raster:
            render(name, text)
        out[name] = data
        print("wrote", name)
    if raster:
        cover(S, env, out)
        deck(S, env, out)
    write_report(S, env, out)


def write_report(S, env, out):
    L = [f"# Results — {env['model']}", "",
         f"- Run: {env['when']}", f"- Machine: {env['chip']}, {env['gpu_cores']}-core GPU, {env['ram_gb']} GB, {env['os']}",
         f"- Quant: {env['quant']} · context as loaded {env['context_length']:,} (native {env['native_context_length']:,})",
         f"- Server flags: `{env['server_flags']}`", ""]
    if "accuracy" in out:
        L += ["## Accuracy", "", "| Family | Passed | Rate |", "|---|---|---|"]
        L += [f"| {l} | {o}/{n} | {o/n:.0%} |" for l, o, n in out["accuracy"]] + [""]
        for k in ("coding", "elixir"):
            if S.get(k):
                by = defaultdict(list)
                for r in S[k]:
                    by[r["id"]].append(r["passed"])
                fails = {i: f"{sum(v)}/{len(v)}" for i, v in by.items() if not all(v)}
                L.append(f"- {k} items not passing every sample: {fails or 'none'}")
                diff = defaultdict(list)
                for r in S[k]:
                    diff[r["difficulty"]].append(r["passed"])
                L.append(f"- {k} by difficulty: " + ", ".join(f"{d} {sum(v)}/{len(v)}" for d, v in diff.items()))
        if S.get("math"):
            wrong = [(r["id"], r["got"], r["expected"]) for r in S["math"] if not r["passed"]]
            L.append(f"- maths misses (id, got, want): {wrong or 'none'}")
        L.append("")
    if "decode" in out:
        L += ["## Speed", "", "| Output | Median tok/s | Range | Draft acceptance |", "|---|---|---|---|"]
        L += [f"| {g} | {d['tps_median']:.1f} | {d['tps_min']:.1f}–{d['tps_max']:.1f} | "
              f"{(d['accept_median'] or 0):.0%} |" for g, d in out["decode"].items()] + [""]
        contended = [r for r in S["speed"]["decode"] if r.get("contended")]
        L.append(f"- decode runs that overlapped with another generation: {len(contended)}")
    if "prefill" in out:
        L += ["", "| Prompt tokens | TTFT | Server prefill tok/s |", "|---|---|---|"]
        L += [f"| {n:,.0f} | {t:.2f}s | {p:,.0f} |" for n, t, p in out["prefill"]]
    if "concurrency" in out:
        L += ["", "| Concurrent | Total tok/s | Per request tok/s | Median TTFT | Max TTFT |", "|---|---|---|---|---|"]
        L += [f"| {r['n']} | {r['aggregate_tps']:.1f} | {r['per_request_tps']:.1f} | "
              f"{r['median_ttft_s']:.2f}s | {r['max_ttft_s']:.2f}s |" for r in out["concurrency"]]
    if "thinking" in out:
        L += ["", "## Thinking share", ""] + [f"- {l}: {s:.0%} of text is reasoning, median {m:,.0f} tokens/reply"
                                               for l, s, m in out["thinking"]]
    L += ["", "## Wall-clock per suite", ""] + [f"- {k}: {v/60:.1f} min" for k, v in S.get("suite_seconds", {}).items()]
    with open(os.path.join(RES, "report.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote results/report.md")


if __name__ == "__main__":
    main()
