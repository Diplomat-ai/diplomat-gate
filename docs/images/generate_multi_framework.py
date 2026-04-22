"""
Generate: multi-framework-compatibility.svg

Visual: four agent frameworks converge onto a single deterministic
enforcement layer (diplomat-gate), which then dispatches three possible
verdicts (CONTINUE / STOP / REVIEW).

Reproducible — committed to docs/images/generate.py for maintainability.
Regenerate: python docs/images/generate.py
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# Design tokens (Stripe / Linear / Plausible palette)
# ---------------------------------------------------------------------------

BG = "#FFFFFF"
TEXT_PRIMARY = "#0F172A"
TEXT_MUTED = "#64748B"
BORDER_SOFT = "#E2E8F0"
GATE_FILL = "#4F46E5"
GATE_STROKE = "#312E81"

# Framework colors — desaturated, professional
FRAMEWORKS = [
    {"name": "LangChain", "sub": "agents · tools", "fill": "#FEE2E2", "stroke": "#FCA5A5"},
    {"name": "OpenClaw", "sub": "340k+ stars", "fill": "#FEF3C7", "stroke": "#FCD34D"},
    {"name": "browser-use", "sub": "79k+ stars", "fill": "#D1FAE5", "stroke": "#6EE7B7"},
    {"name": "OpenAI Agents SDK", "sub": "19k+ stars", "fill": "#DBEAFE", "stroke": "#93C5FD"},
]

# Verdicts (right side)
VERDICTS = [
    {"label": "CONTINUE", "fill": "#10B981", "stroke": "#047857"},
    {"label": "REVIEW", "fill": "#F59E0B", "stroke": "#B45309"},
    {"label": "STOP", "fill": "#EF4444", "stroke": "#991B1B"},
]

FONT_FAMILY = (
    "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', "
    "Roboto, 'Helvetica Neue', Arial, sans-serif"
)


# ---------------------------------------------------------------------------
# Canvas geometry
# ---------------------------------------------------------------------------

W, H = 1200, 560

# Columns
COL_FRAMEWORK_X = 40
COL_FRAMEWORK_W = 280
COL_GATE_X = 480
COL_GATE_W = 240
COL_VERDICT_X = 820
COL_VERDICT_W = 340

# Gate rectangle
GATE_Y = 160
GATE_H = 240

# Framework rows
FW_Y_START = 80
FW_Y_STEP = 110
FW_H = 80

# Verdict rows
VERDICT_Y_START = 140
VERDICT_Y_STEP = 100
VERDICT_H = 60


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------


def svg_root() -> ET.Element:
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"0 0 {W} {H}",
            "width": str(W),
            "height": str(H),
            "role": "img",
            "aria-labelledby": "title desc",
        },
    )
    ET.SubElement(
        root, "title", {"id": "title"}
    ).text = "diplomat-gate: one enforcement layer for four agent frameworks"
    ET.SubElement(root, "desc", {"id": "desc"}).text = (
        "Flow diagram showing LangChain, OpenClaw, browser-use and "
        "OpenAI Agents SDK converging onto diplomat-gate, which emits "
        "CONTINUE, REVIEW, or STOP verdicts."
    )

    # Background
    ET.SubElement(
        root,
        "rect",
        {
            "x": "0",
            "y": "0",
            "width": str(W),
            "height": str(H),
            "fill": BG,
        },
    )
    return root


def rounded_rect(parent, x, y, w, h, fill, stroke, stroke_w=1.5, r=10):
    ET.SubElement(
        parent,
        "rect",
        {
            "x": str(x),
            "y": str(y),
            "width": str(w),
            "height": str(h),
            "rx": str(r),
            "ry": str(r),
            "fill": fill,
            "stroke": stroke,
            "stroke-width": str(stroke_w),
        },
    )


def text(parent, x, y, content, *, size=14, weight="400", color=TEXT_PRIMARY, anchor="start"):
    el = ET.SubElement(
        parent,
        "text",
        {
            "x": str(x),
            "y": str(y),
            "font-family": FONT_FAMILY,
            "font-size": str(size),
            "font-weight": weight,
            "fill": color,
            "text-anchor": anchor,
        },
    )
    el.text = content


def line(parent, x1, y1, x2, y2, color=BORDER_SOFT, width=1.5, dash=None):
    attrs = {
        "x1": str(x1),
        "y1": str(y1),
        "x2": str(x2),
        "y2": str(y2),
        "stroke": color,
        "stroke-width": str(width),
        "stroke-linecap": "round",
    }
    if dash:
        attrs["stroke-dasharray"] = dash
    ET.SubElement(parent, "line", attrs)


# ---------------------------------------------------------------------------
# Compose the figure
# ---------------------------------------------------------------------------


def build() -> ET.Element:
    root = svg_root()

    # --- Section labels (small caps, muted) ---
    text(root, COL_FRAMEWORK_X, 50, "YOUR AGENT FRAMEWORK", size=11, weight="600", color=TEXT_MUTED)
    text(
        root,
        COL_GATE_X + COL_GATE_W / 2,
        50,
        "ENFORCEMENT LAYER",
        size=11,
        weight="600",
        color=TEXT_MUTED,
        anchor="middle",
    )
    text(root, COL_VERDICT_X, 50, "DETERMINISTIC VERDICT", size=11, weight="600", color=TEXT_MUTED)

    # --- Framework boxes (left column) ---
    for i, fw in enumerate(FRAMEWORKS):
        y = FW_Y_START + i * FW_Y_STEP
        rounded_rect(
            root, COL_FRAMEWORK_X, y, COL_FRAMEWORK_W, FW_H, fill=fw["fill"], stroke=fw["stroke"]
        )
        text(
            root,
            COL_FRAMEWORK_X + 20,
            y + 32,
            fw["name"],
            size=15,
            weight="600",
            color=TEXT_PRIMARY,
        )
        text(root, COL_FRAMEWORK_X + 20, y + 55, fw["sub"], size=12, weight="400", color=TEXT_MUTED)

        # Connector: from framework right-edge to gate left-edge
        start_x = COL_FRAMEWORK_X + COL_FRAMEWORK_W
        start_y = y + FW_H / 2
        end_x = COL_GATE_X
        end_y = GATE_Y + GATE_H / 2

        # Bezier path for soft convergence
        mid_x = (start_x + end_x) / 2
        path_d = f"M {start_x} {start_y} C {mid_x} {start_y}, {mid_x} {end_y}, {end_x} {end_y}"
        ET.SubElement(
            root,
            "path",
            {
                "d": path_d,
                "fill": "none",
                "stroke": fw["stroke"],
                "stroke-width": "1.8",
                "opacity": "0.7",
            },
        )

    # --- Gate box (center column) ---
    rounded_rect(
        root,
        COL_GATE_X,
        GATE_Y,
        COL_GATE_W,
        GATE_H,
        fill=GATE_FILL,
        stroke=GATE_STROKE,
        stroke_w=2,
        r=12,
    )

    # Gate title
    text(
        root,
        COL_GATE_X + COL_GATE_W / 2,
        GATE_Y + 80,
        "diplomat-gate",
        size=22,
        weight="700",
        color="#FFFFFF",
        anchor="middle",
    )

    # Gate sub-labels (three pillars)
    pillars = [
        "deterministic",
        "hash-chained audit",
        "framework-agnostic",
    ]
    for i, p in enumerate(pillars):
        text(
            root,
            COL_GATE_X + COL_GATE_W / 2,
            GATE_Y + 130 + i * 28,
            f"· {p}",
            size=13,
            weight="400",
            color="#E0E7FF",
            anchor="middle",
        )

    # --- Verdict boxes (right column) ---
    for i, v in enumerate(VERDICTS):
        y = VERDICT_Y_START + i * VERDICT_Y_STEP
        rounded_rect(
            root, COL_VERDICT_X, y, COL_VERDICT_W, VERDICT_H, fill=v["fill"], stroke=v["stroke"]
        )
        text(root, COL_VERDICT_X + 24, y + 38, v["label"], size=15, weight="700", color="#FFFFFF")

        # Connector: from gate right-edge to verdict left-edge
        start_x = COL_GATE_X + COL_GATE_W
        start_y = GATE_Y + GATE_H / 2
        end_x = COL_VERDICT_X
        end_y = y + VERDICT_H / 2

        mid_x = (start_x + end_x) / 2
        path_d = f"M {start_x} {start_y} C {mid_x} {start_y}, {mid_x} {end_y}, {end_x} {end_y}"
        ET.SubElement(
            root,
            "path",
            {
                "d": path_d,
                "fill": "none",
                "stroke": v["stroke"],
                "stroke-width": "2",
                "opacity": "0.8",
            },
        )

    # --- Footnote ---
    text(
        root,
        W / 2,
        H - 24,
        "One YAML policy file. One SQLite audit trail. Zero LLM calls.",
        size=13,
        weight="500",
        color=TEXT_MUTED,
        anchor="middle",
    )

    return root


def main():
    out_dir = Path(__file__).parent
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "multi-framework-compatibility.svg"

    root = build()
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    print(f"✓ wrote {out_path}")


if __name__ == "__main__":
    main()
