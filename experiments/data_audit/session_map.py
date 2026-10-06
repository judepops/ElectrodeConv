#!/usr/bin/env python3
"""Session map of the Polaron Track 4 dataset: how the 31 spots line up in 13 sessions.

What is drawn is observation, not mechanism:
  - which spots touch comes from matching image edges (Track_4/provenance/edge_match.py);
  - an image edge is inferred from a marker line in the file;
  - nothing is placed on an electrode axis; order and spacing across a '?' gap are unknown.
Facts and words follow Track_4/schematic_handoff/SCHEMATIC_BRIEF.md (aligned with losslarpV2).

Usage:  python3 session_map.py session_map.svg [light|dark]
"""
import sys

# ─────────────────────────── CONFIG ───────────────────────────
TEXT = "labelled"                     # "none" | "minimal" | "labelled" | "full"
THEME = sys.argv[2] if len(sys.argv) > 2 else "light"

W = 1480
M_L = 40                               # left margin
X_SESSION = 60                         # session label column
X0 = 220                               # first spot of every row starts here
SPOT_W, SPOT_H = 118, 34
GAP_W = 44                             # drawn width of a '?' gap (true distance unknown)
ROW_PITCH = 50
X_COUNT = 735                          # "n spots" column
X_NOTE = 820                           # per-row notes
X_BOX = 1110                           # right-hand column: confirmed / measured / not established
FONT = "Arial, Helvetica, sans-serif"

PALETTES = {  # team page tokens, losslarpV2/dashboard/site/style.css
    "light": dict(bg="#ffffff", band="#f6f5f1", ink="#16181d", muted="#5d6270", line="#dcdad3",
                  c1="#4f5bd5", c2="#d9622b", c3="#12937f", on_spot="#ffffff", copper="#7a4a1e", grey="#e9e7e1"),
    "dark": dict(bg="#171a1f", band="#0e1013", ink="#e9eaee", muted="#9aa0ad", line="#2a2f37",
                 c1="#8f98ff", c2="#ff8f5a", c3="#3cc7b0", on_spot="#0e1013", copper="#c9a27e", grey="#2a2f37"),
}

# Sessions in display order. A session is a list of pieces; a piece is a run of touching spots.
# Pieces are separated by a '?' gap. Spot = (id, batch, edge): edge "L"/"R" = inferred edge of the source image.
SESSIONS = [
    dict(h=2080, group="mixed", pieces=[[("cfe5vt7s", 3, ""), ("r17byphk", 2, ""), ("ffwubibz", 1, "R")]]),
    dict(h=2068, group="mixed", note="files named SE, not ETD",
         pieces=[[("vc2whyaq", 3, "L"), ("x77cy643", 3, ""), ("utfgcjfa", 3, ""), ("rxax5ozo", 2, "")]]),
    dict(h=2148, group="mixed", pieces=[[("f1vzngrs", 1, "L"), ("epqdaau9", 2, "")]]),
    dict(h=2156, group="mixed", pieces=[[("fzrt2k6r", 1, "L")], [("b3esycq1", 2, "")]]),
    dict(h=2272, group="mixed", pieces=[[("i9jiqjwl", 2, "L")], [("pl8uabbv", 3, "")]]),
    dict(h=2060, group="single", note="black level lifted (imaging)",
         pieces=[[("x7u69zsw", 3, "L"), ("tuy3zymq", 3, ""), ("kbdh4tri", 3, ""), ("71vgq3fw", 3, "R")]]),
    dict(h=1904, group="single", pieces=[[("mgxahqnk", 3, ""), ("hawkfj64", 3, ""), ("0grcilhi", 3, "R")]]),
    dict(h=2088, group="single", pieces=[[("ufdvpb81", 3, "L")], [("9luzk4jm", 3, ""), ("hzumfsms", 3, "")]]),
    dict(h=1612, group="single", pieces=[[("xgj4xftb", 3, "L")], [("ptg8lmto", 3, "R")]]),
    dict(h=2048, group="single", pieces=[[("3806gxp0", 2, "")], [("avn74qx1", 2, "R")]]),
    dict(h=2316, group="single", note="bright population ~15–20% of area",
         pieces=[[("4ih2ggld", 1, "")], [("5n1q8atc", 1, "")]]),
    dict(h=1880, group="single", pieces=[[("uhdslk0o", 1, "R")]]),
    dict(h=1780, group="single", pieces=[[("iv6g2oq0", 1, "")]]),
]
COPPER = {"epqdaau9"}                  # copper collector visible along the bottom edge
QUIET = [2060, 1904, 2088, 1612]       # imaged more quietly than the others (team measurement)

BOX = [
    ("Confirmed by Polaron", [
        "about 20 large images were cut into crops",
        "crops were grouped into batches on Polaron's own features",
        "Batch_3 is the baseline: what the supplier promised",
        "bright particles are silicon, dark are graphite",
    ]),
    ("Measured by the team", [
        "13 sessions (source images) among the 31 spots",
        "12 touching pairs by edge matching; 4 cross folders",
        "5 mixed sessions hold 13 spots",
        "1 of 31 spots shows the copper collector",
    ]),
    ("Not established", [
        "where the sessions sit on an electrode, or their order",
        "which edge is the collector for 30 of 31 spots",
        "coating thickness",
        "what “in between is pore” includes",
        "whether a batch difference is material, imaging or both",
        "whether the final two images come from known sessions",
    ]),
]
# ──────────────────────────────────────────────────────────────

P = PALETTES[THEME]
LEVEL = {"none": 0, "minimal": 1, "labelled": 2, "full": 3}[TEXT]
BATCH_COL = {1: P["c1"], 2: P["c2"], 3: P["c3"]}

# ── the numbers on the figure are derived from the table above and checked here ──
spots = [s for ses in SESSIONS for pc in ses["pieces"] for s in pc]
ids = [s[0] for s in spots]
n_batch = {b: sum(1 for s in spots if s[1] == b) for b in (1, 2, 3)}
pairs = [(a, b) for ses in SESSIONS for pc in ses["pieces"] for a, b in zip(pc, pc[1:])]
cross = [(a, b) for a, b in pairs if a[1] != b[1]]
mixed = [ses for ses in SESSIONS if len({s[1] for pc in ses["pieces"] for s in pc}) > 1]
n_mixed_spots = sum(len(pc) for ses in mixed for pc in ses["pieces"])
assert len(ids) == len(set(ids)) == 31, len(ids)
assert n_batch == {1: 7, 2: 7, 3: 17}, n_batch
assert len(SESSIONS) == 13 and len({s["h"] for s in SESSIONS}) == 13
assert len(pairs) == 12 and len(cross) == 4, (len(pairs), len(cross))
assert sum(1 for s in spots if s[2]) == 13
assert len(mixed) == 5 and n_mixed_spots == 13
assert all((ses["group"] == "mixed") == (ses in mixed) for ses in SESSIONS)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=11, fill=None, weight="normal", anchor="start", need=2, style="normal"):
    if LEVEL < need:
        return ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'font-style="{style}" fill="{fill or P["ink"]}" text-anchor="{anchor}">{esc(s)}</text>')


def rect(x, y, w, h, fill, stroke="none", sw=0, rx=0, dash=None, opacity=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    o = f' opacity="{opacity}"' if opacity is not None else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}{o}/>')


def line(x1, y1, x2, y2, stroke, sw=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"{d}/>'


def diamond(cx, cy, r=6.5):
    pts = f"{cx},{cy - r} {cx + r},{cy} {cx},{cy + r} {cx - r},{cy}"
    return f'<polygon points="{pts}" fill="{P["ink"]}" stroke="{P["bg"]}" stroke-width="1.5"/>'


def arrow(x1, y, x2):
    return (line(x1, y, x2 - 8, y, P["muted"], 1.6) +
            f'<polygon points="{x2},{y} {x2 - 9},{y - 5} {x2 - 9},{y + 5}" fill="{P["muted"]}"/>')


def dots(x, y):
    return "".join(f'<circle cx="{x + i * 7:.1f}" cy="{y:.1f}" r="1.7" fill="{P["muted"]}"/>' for i in range(3))


def layer(lid, label, body):
    return f'<g inkscape:groupmode="layer" id="{lid}" inkscape:label="{label}">\n{body}\n</g>'


# ── layout: pin every vertical position, then derive H ──
Y_TITLE = 40
Y_FLOW = 72                       # top of the construction strip
Y_MAP = Y_FLOW + 128              # first group header
y = Y_MAP
row_y, headers = {}, []
for g in ("mixed", "single"):
    headers.append((g, y))
    y += 50 if LEVEL >= 2 else 14
    for ses in SESSIONS:
        if ses["group"] == g:
            row_y[ses["h"]] = y
            y += ROW_PITCH
    y += 16
Y_LEGEND = y + 6
H = Y_LEGEND + (170 if LEVEL >= 2 else 70)

# ── 1 · construction strip: large images → spots → batch folders ──
flow = []
fy = Y_FLOW
for i in range(3):                                         # a stack of large images
    flow.append(rect(M_L + 20 + i * 7, fy + 6 + i * 7, 170, 20, P["grey"], P["muted"], 1, rx=2))
flow.append(text(M_L + 20, fy + 66, "about 20 large images (Polaron)", 11, P["muted"]))
flow.append(arrow(M_L + 222, fy + 22, M_L + 262))
sx = M_L + 290                                             # one strip cut into spots (pattern of session 2080)
flow.append(dots(sx - 22, fy + 22))
for k, b in enumerate((3, 2, 1)):
    flow.append(rect(sx + k * 52, fy + 8, 52, 28, BATCH_COL[b], P["bg"], 2))
flow.append(dots(sx + 3 * 52 + 8, fy + 22))
flow.append(text(sx - 22, fy + 66, "cut into spots; neighbours can land in different folders", 11, P["muted"]))
flow.append(arrow(sx + 222, fy + 22, sx + 262))
fx = sx + 290                                              # three batch folders
for k, (b, lab) in enumerate(((1, f"Batch_1 · {n_batch[1]}"), (2, f"Batch_2 · {n_batch[2]}"),
                              (3, f"Batch_3 · {n_batch[3]} · baseline"))):
    wbox = 112 if b < 3 else 168
    xb = fx + sum((112, 112, 168)[:k]) + k * 10
    flow.append(rect(xb, fy + 6, wbox, 32, BATCH_COL[b], rx=4))
    flow.append(text(xb + wbox / 2, fy + 27, lab, 12, P["on_spot"], "bold", "middle", need=1))
flow.append(text(fx, fy + 66, "grouped by Polaron on its own features", 11, P["muted"]))

# ── 2 · group bands and headers ──
bands, heads = [], []
for g, yh in headers:
    rows = [ses for ses in SESSIONS if ses["group"] == g]
    n_sp = sum(len(pc) for ses in rows for pc in ses["pieces"])
    y_first, y_last = row_y[rows[0]["h"]], row_y[rows[-1]["h"]]
    if g == "mixed":
        bands.append(rect(M_L, yh - 8, X_BOX - M_L - 40, y_last + SPOT_H + 14 - (yh - 8), P["band"], rx=6))
        heads.append(text(X_SESSION, yh + 12, f"Mixed sessions: spots in more than one batch folder "
                          f"({len(rows)} sessions, {n_sp} spots)", 13.5, weight="bold"))
        heads.append(text(X_SESSION, yh + 29, "the ‘mixed’ test scores these 13 spots; "
                          "the ‘joins’ test scores the 4 ◆ pairs", 11, P["muted"]))
    else:
        heads.append(text(X_SESSION, yh + 12, f"Single-folder sessions ({len(rows)} sessions, {n_sp} spots)",
                          13.5, weight="bold"))
        heads.append(text(X_SESSION, yh + 29, "here the batch folder is also the session", 11, P["muted"]))

# ── 3 · spots, joins, gaps, edges ──
spot_l, join_l, gap_l, edge_l, lab_l, note_l = [], [], [], [], [], []
for ses in SESSIONS:
    yr = row_y[ses["h"]]
    x = X0
    lab_l.append(text(X_SESSION, yr + SPOT_H / 2 + 5, str(ses["h"]), 14, weight="bold", need=1))
    lab_l.append(text(X_SESSION + 40, yr + SPOT_H / 2 + 5, "px", 10.5, P["muted"]))
    n = sum(len(pc) for pc in ses["pieces"])
    lab_l.append(text(X_COUNT, yr + SPOT_H / 2 + 4, f"{n} spot" + ("s" if n > 1 else ""), 11, P["muted"], need=1))
    if ses.get("note"):
        note_l.append(text(X_NOTE, yr + SPOT_H / 2 + 4, ses["note"], 11, P["muted"]))
    pieces = ses["pieces"]
    for pi, pc in enumerate(pieces):
        if pi > 0:                                          # unknown gap between non-touching spots
            gap_l.append(rect(x + 6, yr, GAP_W - 12, SPOT_H, "none", P["muted"], 1.2, rx=3, dash="4 3"))
            gap_l.append(text(x + GAP_W / 2, yr + SPOT_H / 2 + 5, "?", 13, P["muted"], anchor="middle", need=1))
            x += GAP_W
        first, last = pc[0], pc[-1]
        if pi == 0 and first[2] != "L":                     # image continues to the left
            gap_l.append(dots(x - 30, yr + SPOT_H / 2))
        for k, (sid, b, edge) in enumerate(pc):
            xs = x + k * SPOT_W
            spot_l.append(rect(xs, yr, SPOT_W, SPOT_H, BATCH_COL[b], P["bg"], 2, rx=2))
            spot_l.append(text(xs + SPOT_W / 2, yr + 15, f"B{b}", 12.5, P["on_spot"], "bold", "middle", need=1))
            spot_l.append(text(xs + SPOT_W / 2, yr + 28, sid, 9.5, P["on_spot"], anchor="middle"))
            if edge == "L":
                edge_l.append(rect(xs - 8, yr - 4, 6, SPOT_H + 8, P["ink"]))
            if edge == "R":
                edge_l.append(rect(xs + SPOT_W + 2, yr - 4, 6, SPOT_H + 8, P["ink"]))
            if sid in COPPER:
                edge_l.append(line(xs + 2, yr + SPOT_H + 4, xs + SPOT_W - 2, yr + SPOT_H + 4, P["copper"], 4, dash="7 3"))
            if k > 0 and pc[k - 1][1] != b:                 # touching, different folders
                join_l.append(diamond(xs, yr + SPOT_H / 2, 7.5))
        x += len(pc) * SPOT_W
        if pi == len(pieces) - 1 and last[2] != "R":        # image continues to the right
            gap_l.append(dots(x + 12, yr + SPOT_H / 2))

# imaged more quietly: one bracket over the four Batch_3-only sessions
qy0, qy1 = row_y[QUIET[0]], row_y[QUIET[-1]] + SPOT_H
xq = X_NOTE - 14
note_l.append(line(xq, qy0 + 4, xq, qy1 - 4, P["muted"], 1.4))
note_l.append(line(xq, qy0 + 4, xq + 6, qy0 + 4, P["muted"], 1.4))
note_l.append(line(xq, qy1 - 4, xq + 6, qy1 - 4, P["muted"], 1.4))
note_l.append(text(X_NOTE, (qy0 + qy1) / 2 + 4, "imaged more quietly than the others", 11, P["muted"]))

# ── 4 · confirmed / measured / not established ──
box = []
by = Y_MAP
for head, lines in BOX:
    box.append(text(X_BOX, by + 12, head, 13.5, weight="bold"))
    by += 22
    for ln in lines:
        box.append(text(X_BOX, by + 12, ln, 11.5))
        by += 19
    by += 16
assert by < H - 40, "box runs off the canvas"

# ── 5 · legend and footnote ──
leg = []
ly = Y_LEGEND
lx2 = M_L + 420
items_l = [(1, "Batch_1"), (2, "Batch_2"), (3, "Batch_3 (baseline)")]
for i, (b, lab) in enumerate(items_l):
    leg.append(rect(M_L + 20, ly + i * 22, 22, 14, BATCH_COL[b], rx=2))
    leg.append(text(M_L + 50, ly + i * 22 + 12, lab, 11.5))
leg.append(diamond(M_L + 31, ly + 3 * 22 + 7))
leg.append(text(M_L + 50, ly + 3 * 22 + 12, "touching spots in different batch folders (the 4 \u2018joins\u2019)", 11.5))
leg.append(rect(lx2, ly, 6, 16, P["ink"]))
leg.append(text(lx2 + 30, ly + 12, "edge of the source image (inferred from a marker line in the file)", 11.5))
leg.append(rect(lx2 - 2, ly + 22, 22, 14, "none", P["muted"], 1.2, rx=2, dash="4 3"))
leg.append(text(lx2 + 30, ly + 22 + 12, "same session, not touching: order and distance unknown", 11.5))
leg.append(dots(lx2, ly + 2 * 22 + 7))
leg.append(text(lx2 + 30, ly + 2 * 22 + 12, "the image continues beyond the spots we have", 11.5))
leg.append(line(lx2 - 2, ly + 3 * 22 + 7, lx2 + 20, ly + 3 * 22 + 7, P["copper"], 4, dash="7 3"))
leg.append(text(lx2 + 30, ly + 3 * 22 + 12, "copper collector visible on this spot's bottom edge (1 of 31)", 11.5))
fy2 = ly + 4 * 22 + 16
leg.append(text(M_L + 20, fy2, "Touching spots meet edge to edge (found by matching image edges). "
                "‘Leave one session out’ holds out one whole row at a time.", 11, P["muted"]))
leg.append(text(M_L + 20, fy2 + 18, "spot = what Polaron calls a crop · session = one large source image, named by "
                "its height in pixels · a spot is 175 µm wide and 40–58 µm tall at 25 nm per pixel; "
                "not drawn to scale", 11, P["muted"]))
leg.append(text(M_L + 20, fy2 + 36, "Source: edge matching of all 31 BSE images (Track_4/provenance) and Polaron's messages "
                "to the teams; every count is checked in session_map.py", 11, P["muted"]))

title = text(M_L, Y_TITLE, "How the 31 spots line up: 13 sessions, 3 batch folders", 20, weight="bold")

svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
     width="{W}" height="{H}" viewBox="0 0 {W} {H}">
{layer("layer0", "0 · Background", rect(0, 0, W, H, P["bg"]))}
{layer("layer1", "1 · Title", title)}
{layer("layer2", "2 · How the batches were built", chr(10).join(flow))}
{layer("layer3", "3 · Groups", chr(10).join(bands + heads))}
{layer("layer4", "4 · Spots", chr(10).join(spot_l))}
{layer("layer5", "5 · Gaps and continuation", chr(10).join(gap_l))}
{layer("layer6", "6 · Image edges and copper", chr(10).join(edge_l))}
{layer("layer7", "7 · Cross-folder joins", chr(10).join(join_l))}
{layer("layer8", "8 · Session labels, counts, notes", chr(10).join(lab_l + note_l))}
{layer("layer9", "9 · Confirmed, measured, not established", chr(10).join(box))}
{layer("layer10", "10 · Legend", chr(10).join(leg))}
</svg>
'''
out = sys.argv[1] if len(sys.argv) > 1 else "session_map.svg"
open(out, "w").write(svg)
print(f"wrote {out} ({W} x {H}, theme {THEME}, text {TEXT})")
