# Images — reproducible assets

All visuals in the main README are reproducible from code.

## SVG files

- `before-after-comparison.svg` — terminal comparison (before / after diplomat-gate)
- `multi-framework-compatibility.svg` — 4 frameworks converging onto the enforcement layer

## Regeneration

Each SVG has a generator script alongside it:

```bash
# From the repo root
python docs/images/generate_before_after.py
python docs/images/generate_multi_framework.py
```

The scripts use only Python stdlib (`xml.etree.ElementTree`, `pathlib`) — no
dependencies needed. Regenerated files overwrite existing ones in place.

## Mermaid diagrams

Two additional diagrams are embedded directly in the main `README.md` as
Mermaid code blocks. GitHub renders them natively — no asset files needed.
