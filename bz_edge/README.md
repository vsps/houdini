# bz_edge — Edge chain → Bezier (Houdini SOP)

Select a connected, open chain of edges; the tool conforms them to a cubic bezier
between the chain's start and end points, with interactive handles.

HDA type: `piotr::bz_curve::1.2`

## Files
- `piotr_bz_curve_1.2.hda` — the asset (add from your otls dir)
- `solve.vex` — Attribute Wrangle `solve` inside the HDA (Run Over: Detail)
- `state_script.py` — Type Properties → Interactive → State Script
- `shelf_tool.py` — shelf tool script (SOP context)

## Install
1. Copy the `.hda` into `$HOUDINI_USER_PREF_DIR/otls/` (or Assets → Install Asset Library).
2. Create a shelf tool, paste `shelf_tool.py`.

## Use
Select edges → run tool → drag handles.
- **R** — reset handles (ends = original points, mids at 1/3 and 2/3)
- **L** — toggle lock on start/end points

## HDA parameters
| Parm | Type | Notes |
|---|---|---|
| `edges` | string | edge group pattern, set by shelf tool |
| `min_edges` | int | default 3 |
| `start_pos`, `handle1`, `handle2`, `end_pos` | float3 | bezier control points (absolute, object space) |
| `custom_handles` | toggle | default off; state turns it on at init |
| `lock_ends` | toggle | default off; ends stay at original points |
| `uniform` | toggle | off = keep original relative spacing |
| `blend` | float 0–1 | default 1 |

## Network inside HDA
`input → solve (wrangle) → attribdelete (detail bz_*) → output`

## Notes
- Chain must be open, unbranched, connected. Start = lower point number.
- Handles are absolute; after changing the selection press **R**.
