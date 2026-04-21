#!/usr/bin/env bash
# recording_script.sh — reproducible asciinema demo for diplomat-gate
#
# Usage:
#   bash demos/openclaw/assets/recording_script.sh
#
# Prerequisites:
#   - asciinema >= 2.3   (brew install asciinema)
#   - diplomat-gate installed in the active Python environment
#   - Run from the repository root
#
# Output:
#   demos/openclaw/assets/demo.cast  (asciinema v2 cast file)
#
# Convert to GIF:
#   agg demos/openclaw/assets/demo.cast demos/openclaw/assets/demo.gif \
#       --font-family "JetBrains Mono" --font-size 14 \
#       --cols 88 --rows 24 --fps-cap 10
#
# Convert to MP4:
#   ffmpeg -i demos/openclaw/assets/demo.gif \
#          -vf "fps=30,scale=1280:-1:flags=lanczos" \
#          -c:v libx264 -pix_fmt yuv420p \
#          demos/openclaw/assets/demo.mp4

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CAST_FILE="$REPO_ROOT/demos/openclaw/assets/demo.cast"
DB_FILE="$REPO_ROOT/demos/openclaw/demo-audit.db"
PYTHON="${PYTHON:-python}"

cd "$REPO_ROOT"

# ── clean state ────────────────────────────────────────────────────────────────
rm -f "$DB_FILE" "$CAST_FILE"

# ── record ─────────────────────────────────────────────────────────────────────
asciinema rec "$CAST_FILE" \
  --cols 88 \
  --rows 24 \
  --title "diplomat-gate — 10 lines of YAML" \
  --command "bash -c '
    # small delay so the cast starts clean
    sleep 1

    echo ""
    echo "  diplomat-gate demo — 10 lines of YAML"
    echo ""
    sleep 1.5

    # ── SHOT 1: show the problem ───────────────────────────────────────────
    echo "# Step 1: run the agent WITHOUT diplomat-gate"
    sleep 1
    echo "$ $PYTHON demos/openclaw/run.py --ci --scenario 1"
    sleep 0.5
    $PYTHON demos/openclaw/run.py --ci --scenario 1
    sleep 3

    # ── SHOT 2: show the YAML ──────────────────────────────────────────────
    echo ""
    echo "# Step 2: the fix — 10 lines of YAML"
    sleep 1
    echo "$ cat demos/openclaw/policies.yaml"
    sleep 0.5
    cat demos/openclaw/policies.yaml
    sleep 2

    # ── SHOT 3: gate blocks the email ──────────────────────────────────────
    echo ""
    echo "# Step 3: same agent, behind diplomat-gate"
    sleep 1
    echo "$ $PYTHON demos/openclaw/run.py --ci --scenario 2"
    sleep 0.5
    $PYTHON demos/openclaw/run.py --ci --scenario 2
    sleep 3

    # ── SHOT 4: audit chain ────────────────────────────────────────────────
    echo ""
    echo "# Step 4: every verdict is hash-chained"
    sleep 1
    echo "$ $PYTHON demos/openclaw/run.py --ci --scenario 3"
    sleep 0.5
    $PYTHON demos/openclaw/run.py --ci --scenario 3
    sleep 3

    echo ""
    echo "  pip install diplomat-gate"
    echo "  github.com/Diplomat-ai/diplomat-gate"
    sleep 4
  '"

echo ""
echo "Cast written to: $CAST_FILE"
echo "Play back with:  asciinema play $CAST_FILE"
