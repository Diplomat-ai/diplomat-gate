"""
Generate: before-after-comparison.svg

Visual: two stylized terminal windows side-by-side showing the same agent
scenario (OpenClaw sending an email to an insurance company on user's behalf).

Left terminal: unprotected — email reaches SMTP.
Right terminal: diplomat-gate — email blocked before reaching SMTP.

Reproducible — committed to docs/images/generate_before_after.py.
Regenerate: python docs/images/generate_before_after.py
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


# ---------------------------------------------------------------------------
# Design tokens — Stripe / Linear dark terminal aesthetic
# ---------------------------------------------------------------------------

BG = "#FFFFFF"
TEXT_PRIMARY = "#0F172A"
TEXT_MUTED = "#64748B"

# Terminal chrome
TERMINAL_BG = "#0F172A"
TERMINAL_BORDER = "#1E293B"
TERMINAL_HEADER_BG = "#1E293B"

# Traffic-light dots
DOT_RED = "#EF4444"
DOT_YELLOW = "#F59E0B"
DOT_GREEN = "#10B981"

# Terminal text colors
TERM_PROMPT = "#94A3B8"
TERM_DEFAULT = "#E2E8F0"
TERM_DIM = "#64748B"
TERM_ERROR = "#FCA5A5"
TERM_SUCCESS = "#6EE7B7"
TERM_WARNING = "#FCD34D"
TERM_INDIGO = "#A5B4FC"

# Panel labels
LABEL_WITHOUT = "#EF4444"
LABEL_WITH = "#10B981"

MONO_FONT = (
    "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Monaco, "
    "Consolas, 'Liberation Mono', 'Courier New', monospace"
)
SANS_FONT = (
    "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', "
    "Roboto, 'Helvetica Neue', Arial, sans-serif"
)


# ---------------------------------------------------------------------------
# Canvas geometry
# ---------------------------------------------------------------------------

W, H = 1200, 560

GUTTER = 40
PANEL_W = (W - GUTTER * 3) // 2  # = 373
PANEL_X_LEFT = GUTTER
PANEL_X_RIGHT = GUTTER * 2 + PANEL_W

PANEL_Y = 90
PANEL_H = 400

HEADER_H = 36
LINE_H = 22
LINE_START_Y = PANEL_Y + HEADER_H + 28


# ---------------------------------------------------------------------------
# Content — the two scenarios
# ---------------------------------------------------------------------------

LEFT_LINES = [
    ("prompt", "$ python agent.py"),
    ("dim",    ""),
    ("dim",    "# OpenClaw agent, no policy layer"),
    ("default", "agent.send_email("),
    ("default", "  to='claims@lemonade.com',"),
    ("default", "  subject='Re: claim #12345',"),
    ("default", "  body='[legal rebuttal...]',"),
    ("default", ")"),
    ("dim",    ""),
    ("dim",    "→ SMTP connect..."),
    ("dim",    "→ 250 OK"),
    ("error",  "✗ Email sent without user approval."),
    ("dim",    ""),
    ("default", ""),
]

RIGHT_LINES = [
    ("prompt", "$ python agent.py"),
    ("dim",    ""),
    ("dim",    "# Same agent, behind diplomat-gate"),
    ("default", "gate = Gate.from_yaml('policies.yaml')"),
    ("default", "verdict = gate.evaluate({"),
    ("default", "  'action': 'agent.send_email',"),
    ("default", "  'to': 'claims@lemonade.com',"),
    ("default", "  ..."),
    ("default", "})"),
    ("dim",    ""),
    ("warning", "▸ Verdict: STOP"),
    ("indigo", "  └─ email.domain_blocklist"),
    ("success", "✓ Blocked before reaching SMTP."),
    ("dim",    ""),
]

COLOR_MAP = {
    "prompt":  TERM_PROMPT,
    "dim":     TERM_DIM,
    "default": TERM_DEFAULT,
    "error":   TERM_ERROR,
    "success": TERM_SUCCESS,
    "warning": TERM_WARNING,
    "indigo":  TERM_INDIGO,
}


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def svg_root() -> ET.Element:
    root = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "viewBox": f"0 0 {W} {H}",
        "width": str(W),
        "height": str(H),
        "role": "img",
        "aria-labelledby": "title desc",
    })
    ET.SubElement(root, "title", {"id": "title"}).text = (
        "diplomat-gate before and after: same agent, different outcome"
    )
    ET.SubElement(root, "desc", {"id": "desc"}).text = (
        "Side-by-side terminal comparison showing an agent calling "
        "send_email. Without diplomat-gate the email is sent without "
        "approval. With diplomat-gate the same action is blocked "
        "by a YAML policy before reaching SMTP."
    )

    ET.SubElement(root, "rect", {
        "x": "0", "y": "0", "width": str(W), "height": str(H), "fill": BG,
    })
    return root


def rounded_rect(parent, x, y, w, h, fill, stroke=None, stroke_w=0, r=10):
    attrs = {
        "x": str(x), "y": str(y),
        "width": str(w), "height": str(h),
        "rx": str(r), "ry": str(r),
        "fill": fill,
    }
    if stroke:
        attrs["stroke"] = stroke
        attrs["stroke-width"] = str(stroke_w)
    ET.SubElement(parent, "rect", attrs)


def text(parent, x, y, content, *, size=14, weight="400",
         color=TEXT_PRIMARY, anchor="start", font=SANS_FONT):
    el = ET.SubElement(parent, "text", {
        "x": str(x), "y": str(y),
        "font-family": font,
        "font-size": str(size),
        "font-weight": weight,
        "fill": color,
        "text-anchor": anchor,
    })
    el.text = content


def circle(parent, cx, cy, r, fill):
    ET.SubElement(parent, "circle", {
        "cx": str(cx), "cy": str(cy), "r": str(r), "fill": fill,
    })


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

def draw_panel_label(parent, x, y, label_text, color):
    """Small uppercase label above each terminal."""
    text(parent, x, y, label_text,
         size=11, weight="700", color=color, anchor="start")


def draw_terminal(parent, x, y, w, h, lines):
    """A stylized terminal window with traffic-light dots and content."""
    # Window body
    rounded_rect(parent, x, y, w, h, fill=TERMINAL_BG,
                 stroke=TERMINAL_BORDER, stroke_w=1, r=8)

    # Header strip
    ET.SubElement(parent, "path", {
        "d": f"M {x + 8} {y} "
             f"L {x + w - 8} {y} "
             f"Q {x + w} {y} {x + w} {y + 8} "
             f"L {x + w} {y + HEADER_H} "
             f"L {x} {y + HEADER_H} "
             f"L {x} {y + 8} "
             f"Q {x} {y} {x + 8} {y} Z",
        "fill": TERMINAL_HEADER_BG,
    })

    # Traffic-light dots
    dot_y = y + HEADER_H / 2
    circle(parent, x + 16, dot_y, 5, DOT_RED)
    circle(parent, x + 32, dot_y, 5, DOT_YELLOW)
    circle(parent, x + 48, dot_y, 5, DOT_GREEN)

    # Content lines
    content_x = x + 20
    for i, (kind, content) in enumerate(lines):
        line_y = LINE_START_Y + i * LINE_H
        text(parent, content_x, line_y, content,
             size=13, weight="400",
             color=COLOR_MAP.get(kind, TERM_DEFAULT),
             font=MONO_FONT)


# ---------------------------------------------------------------------------
# Compose the figure
# ---------------------------------------------------------------------------

def build() -> ET.Element:
    root = svg_root()

    # Title + subtitle (top of canvas)
    text(root, W / 2, 40,
         "Same agent. Same scenario. One YAML policy apart.",
         size=18, weight="600", color=TEXT_PRIMARY, anchor="middle")
    text(root, W / 2, 62,
         "Based on a publicly documented January 2026 incident.",
         size=13, weight="400", color=TEXT_MUTED, anchor="middle")

    # Panel labels
    draw_panel_label(root, PANEL_X_LEFT, PANEL_Y - 10,
                     "WITHOUT diplomat-gate", LABEL_WITHOUT)
    draw_panel_label(root, PANEL_X_RIGHT, PANEL_Y - 10,
                     "WITH diplomat-gate", LABEL_WITH)

    # Terminals
    draw_terminal(root, PANEL_X_LEFT, PANEL_Y, PANEL_W, PANEL_H, LEFT_LINES)
    draw_terminal(root, PANEL_X_RIGHT, PANEL_Y, PANEL_W, PANEL_H, RIGHT_LINES)

    # Bottom takeaway
    text(root, W / 2, H - 22,
         "Ten lines of YAML. Deterministic. Framework-agnostic. "
         "Hash-chained audit.",
         size=13, weight="500", color=TEXT_MUTED, anchor="middle")

    return root


def main():
    out_dir = Path(__file__).parent
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "before-after-comparison.svg"

    root = build()
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    print(f"✓ wrote {out_path}")


if __name__ == "__main__":
    main()
