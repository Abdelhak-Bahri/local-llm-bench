"""Render the three vision probes with headless Chrome, so the ground truth is
known by construction: a receipt (OCR), a shape count, and a bar chart."""
import os
import random
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

RECEIPT = """<body style="margin:0;background:#f4f1ea;font:22px 'Courier New',monospace;color:#222">
<div style="width:380px;margin:30px auto;background:#fff;padding:28px;box-shadow:0 2px 8px #0002">
<div style="text-align:center;font-weight:bold">CAFÉ DU PORT</div>
<div style="text-align:center;font-size:16px">12 Rue des Quais · 24/11/2026 08:41</div><hr>
<pre style="font:inherit;margin:0">Espresso x2        5.60
Croissant x3       7.50
Omelette          12.90
Fresh juice x2     9.80
Tarte citron       6.20
Service            5.80</pre><hr>
<pre style="font:inherit;margin:0;font-weight:bold">TOTAL             47.80</pre>
<div style="text-align:center;font-size:16px;margin-top:12px">Merci et à bientôt</div></div></body>"""


def shapes_html():
    rnd = random.Random(7)
    items = ["circle-red"] * 7 + ["circle-blue"] * 5 + ["square-red"] * 4 + ["triangle-red"] * 3
    rnd.shuffle(items)
    out = []
    for i, kind in enumerate(items):
        x, y = 40 + (i % 5) * 150 + rnd.randint(0, 40), 40 + (i // 5) * 140 + rnd.randint(0, 30)
        shape, color = kind.split("-")
        fill = "#d62828" if color == "red" else "#1d4ed8"
        if shape == "circle":
            out.append(f'<circle cx="{x+40}" cy="{y+40}" r="38" fill="{fill}"/>')
        elif shape == "square":
            out.append(f'<rect x="{x}" y="{y}" width="76" height="76" fill="{fill}"/>')
        else:
            out.append(f'<polygon points="{x+40},{y} {x+80},{y+78} {x},{y+78}" fill="{fill}"/>')
    return f'<body style="margin:0;background:#fff"><svg width="800" height="600">{"".join(out)}</svg></body>'


def bars_html():
    data = [("MON", 64), ("TUE", 71), ("WED", 58), ("THU", 92), ("FRI", 85)]
    bars = []
    for i, (lbl, v) in enumerate(data):
        x, h = 110 + i * 130, v * 4.0
        bars.append(f'<rect x="{x}" y="{480-h}" width="80" height="{h}" fill="#3b6ea5"/>'
                    f'<text x="{x+40}" y="{470-h}" text-anchor="middle" font-size="22">{v}</text>'
                    f'<text x="{x+40}" y="510" text-anchor="middle" font-size="22">{lbl}</text>')
    return ('<body style="margin:0;background:#fff;font-family:Helvetica"><svg width="800" height="600">'
            '<text x="400" y="40" text-anchor="middle" font-size="26">Frames uploaded per day (thousands)</text>'
            f'<line x1="90" y1="480" x2="760" y2="480" stroke="#333"/>{"".join(bars)}</svg></body>')


def shoot(html, out, w=800, h=600):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(f"<!doctype html><meta charset=utf-8>{html}")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--window-size={w},{h}", f"--screenshot={out}", f"file://{f.name}"],
                   check=True, capture_output=True)
    os.unlink(f.name)


if __name__ == "__main__":
    d = os.path.join(HERE, "vision")
    os.makedirs(d, exist_ok=True)
    shoot(RECEIPT, os.path.join(d, "receipt.png"), 480, 560)
    shoot(shapes_html(), os.path.join(d, "shapes.png"))
    shoot(bars_html(), os.path.join(d, "bars.png"))
    print("wrote", os.listdir(d))
