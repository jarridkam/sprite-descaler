"""Readability / Gen-3-fit metrics for small pixel sprites (RGBA, binary alpha).

compute(img)  -> dict of numbers
check(img)    -> list of rows (name, value, low, high, status, hint) against gen3_profile.json
Profile is built by calibrate.py from real Gen 3 sprites, so the ranges are measured, not guessed.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

import descale as D

PROFILE_PATH = Path(__file__).with_name("gen3_profile.json")


def _lstar(rgb):
    """True CIE L* (undo the clustering weight)."""
    return D.srgb_to_lab(np.asarray(rgb, np.float64))[..., 0] / D.LIGHT_WEIGHT


def _components(key, mask):
    """4-connected components of equal `key` among `mask` pixels. Returns list of sizes."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    sizes = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            k = key[y, x]
            stack = [(y, x)]
            seen[y, x] = True
            n = 0
            while stack:
                cy, cx = stack.pop()
                n += 1
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx] and key[ny, nx] == k:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            sizes.append(n)
    return sizes


def _shift(a, dy, dx, fill=0):
    out = np.full_like(a, fill)
    h, w = a.shape[:2]
    ys, yd = (slice(max(dy, 0), h + min(dy, 0)), slice(max(-dy, 0), h + min(-dy, 0)))
    xs, xd = (slice(max(dx, 0), w + min(dx, 0)), slice(max(-dx, 0), w + min(-dx, 0)))
    out[ys, xs] = a[yd, xd]
    return out


def compute(img):
    a = np.array(img.convert("RGBA"))
    h, w = a.shape[:2]
    M = a[..., 3] > 127
    n = int(M.sum())
    if n == 0:
        return {}
    rgb = a[..., :3].astype(np.int32)
    key = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
    key = np.where(M, key, -1)
    L = _lstar(a[..., :3])

    ys, xs = np.where(M)
    bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    out = dict(
        opaque_px=n,
        fill_canvas=n / (h * w),
        fill_bbox=n / (bw * bh),
        bbox_h_frac=bh / h,
        bbox_w_frac=bw / w,
        margin_bottom=h - 1 - ys.max(),
        margin_top=int(ys.min()),
    )
    cols, counts = np.unique(key[M], return_counts=True)
    out["colors"] = int(len(cols))
    out["white_share"] = float(((rgb >= 245).all(2) & M).sum() / n)

    # boundary = opaque pixel with a transparent 4-neighbour (or canvas edge)
    nb = [~_shift(M, dy, dx, fill=False) for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    B = M & (nb[0] | nb[1] | nb[2] | nb[3])
    nbound = int(B.sum())
    out["boundary_ratio"] = nbound / n
    if nbound:
        lb = L[B]
        dark = rgb.sum(2)[B] <= 3 * 40  # near-black ink: every channel <= 40 on average
        out["edge_nearblack"] = float(dark.mean())
        out["edge_tinted_dark"] = float(((lb < 45) & ~dark).mean())
        out["edge_light"] = float((lb >= 45).mean())
        out["edge_dark_total"] = float((lb < 45).mean())

    # orphans: pixel with no same-colour 8-neighbour
    same = np.zeros(M.shape, bool)
    same4 = np.zeros(M.shape, bool)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        eq = (_shift(key, dy, dx, fill=-2) == key) & M
        same |= eq
        if abs(dy) + abs(dx) == 1:
            same4 |= eq
    out["orphan8"] = float((M & ~same).sum() / n)
    out["orphan4"] = float((M & ~same4).sum() / n)
    sizes = np.array(_components(key, M))
    out["regions"] = int(len(sizes))
    out["regions_tiny_share"] = float((sizes <= 2).mean())
    out["regions_per_color"] = len(sizes) / max(1, len(cols))

    # contrast across colour changes between opaque neighbours
    dls = []
    for dy, dx in ((0, 1), (1, 0)):
        k2 = _shift(key, -dy, -dx, fill=-1)
        L2 = _shift(L, -dy, -dx)
        pair = M & (k2 >= 0) & (k2 != key)
        dls.append(np.abs(L - L2)[pair])
    dl = np.concatenate(dls) if dls else np.array([])
    if len(dl):
        out["adj_dl_lt10"] = float((dl < 10).mean())
        out["adj_dl_lt20"] = float((dl < 20).mean())
        out["adj_dl_median"] = float(np.median(dl))

    # thin features: opaque pixels not covered by any fully-opaque 2x2 block
    blk = M & _shift(M, 0, -1) & _shift(M, -1, 0) & _shift(M, -1, -1)
    cover = blk | _shift(blk, 0, 1) | _shift(blk, 1, 0) | _shift(blk, 1, 1)
    out["thin_share"] = float((M & ~cover).sum() / n)

    # dither: 2x2 windows with ABBA pattern
    a00, a01 = key, _shift(key, 0, -1, fill=-2)
    a10, a11 = _shift(key, -1, 0, fill=-2), _shift(key, -1, -1, fill=-2)
    chk = (a00 == a11) & (a01 == a10) & (a00 != a01) & (a00 >= 0) & (a01 >= 0)
    out["dither_windows_per_100px"] = float(chk.sum() * 100 / n)

    # tone ladders: lightness gaps between colours that share a hue family
    r, g, b = [a[..., i].astype(np.float64)[M] / 255 for i in range(3)]
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0)
    hue = np.zeros_like(mx)
    d = np.maximum(mx - mn, 1e-9)
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    pk = key[M]
    Lm = L[M]
    colinfo = {}
    for kk, hh, ss, ll in zip(pk, hue, sat, Lm):
        colinfo[int(kk)] = (hh, ss, ll)
    fam = {}
    for kk, (hh, ss, ll) in colinfo.items():
        if ss > 0.18 and 5 < ll < 97:
            fam.setdefault(int(hh // 40) % 9, []).append(ll)
    steps, tones = [], []
    for f_, ls in fam.items():
        ls = sorted(ls)
        tones.append(len(ls))
        steps += [ls[i + 1] - ls[i] for i in range(len(ls) - 1)]
    out["tones_per_family"] = float(np.mean(tones)) if tones else 0.0
    out["tone_step_median"] = float(np.median(steps)) if steps else 0.0
    return out


# name: (hint when low, hint when high)
HINTS = {
    "colors": ("palette underused: room for more shading", "too many colors for a 15-color palette"),
    "fill_canvas": ("subject is small in the canvas", "subject fills the canvas edge to edge"),
    "bbox_h_frac": ("figure is short on the canvas", "figure touches top/bottom: leave a margin"),
    "boundary_ratio": ("silhouette is very blobby", "silhouette is very noisy or thin"),
    "edge_nearblack": ("outline is mostly tinted: fine for big or colorful designs", "outline is almost all black: try tinted outline on lit edges"),
    "edge_dark_total": ("many light edges: outline is missing or too pale", "outline is complete"),
    "orphan8": ("very clean: probably over-smoothed", "too many isolated pixels (noise)"),
    "regions_tiny_share": ("very clean: probably over-smoothed", "too many tiny regions (noise)"),
    "adj_dl_lt10": ("strong separation between parts", "many neighbouring parts nearly the same lightness: add lines or shade steps"),
    "thin_share": ("chunky shapes", "too many 1px-wide shapes: thicken or merge"),
    "dither_windows_per_100px": ("no dithering: fine for small sprites", "too much dithering for Gen 3"),
    "white_share": ("no pure white highlight", "too much pure white: keep white for eye shine and teeth"),
    "tone_step_median": ("tones too close: shading will not read", "tone steps very large"),
}


# which direction is a problem (others are just informative)
BAD_SIDE = {"edge_dark_total": "low", "dither_windows_per_100px": "high", "white_share": "high",
            "colors": "high", "thin_share": "high", "adj_dl_lt10": "high", "orphan8": "high",
            "regions_tiny_share": "both", "tone_step_median": "low", "edge_nearblack": "both",
            "bbox_h_frac": "high", "boundary_ratio": "high", "fill_canvas": "both"}


def load_profile():
    try:
        return json.loads(PROFILE_PATH.read_text())
    except Exception:
        return None


def check(img, profile=None):
    """Rows: (name, value, p10, p90, status, hint). status: ok / watch (outside p10-p90) / flag (outside p1-p99)."""
    profile = profile or load_profile()
    m = compute(img)
    rows = []
    if not profile or not m:
        return rows
    for name, st in profile["metrics"].items():
        if name not in m or name not in HINTS:
            continue
        v = m[name]
        lo_hint, hi_hint = HINTS[name]
        bad = BAD_SIDE.get(name, "both")
        low_bad, high_bad = bad in ("low", "both"), bad in ("high", "both")
        if (low_bad and v < st["min"]) or (high_bad and v > st["max"]):
            status = "flag"
        elif (low_bad and v < st["p10"]) or (high_bad and v > st["p90"]):
            status = "watch"
        else:
            status = "ok"
        hint = "" if status == "ok" else (lo_hint if v < st["p10"] else hi_hint)
        rows.append((name, v, st["p10"], st["p90"], status, hint))
    return rows


def main():
    import sys
    for p in sys.argv[1:]:
        for r in check(Image.open(p)):
            print(f"{r[4]:5s} {r[0]:26s} {r[1]:8.3f}  range {r[2]:.3f}..{r[3]:.3f}  {r[5]}")


if __name__ == "__main__":
    main()
