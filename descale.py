"""Sprite descaler: shrink (AI-upscaled) pixel art to a tiny grid with a small palette.

Pipeline:
  1. crop to alpha bbox, fit into target box
  2. k-means palette in Lab (k colors), assign every source pixel to nearest palette color
  3. search scale/offset of the target grid that minimizes per-cell color impurity
  4. each target pixel = dominant palette color of its source cell
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

LIGHT_WEIGHT = 2.5  # >1 favors keeping shading (lightness steps) when clustering
SIZES = {"64x64": (64, 64), "32x32": (32, 32), "16x32": (16, 32), "64x96": (64, 96), "96x128": (96, 128)}


# ---------- color ----------
def srgb_to_lab(rgb):
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([LIGHT_WEIGHT * (116 * f[..., 1] - 16),
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], axis=-1)


# ---------- palette ----------
def kmeans_palette(lab, weights, k, iters=60, seed=0, min_mass=0.004):
    """Weighted k-means++ on unique colors. Returns centers (k,3) in Lab."""
    rng = np.random.default_rng(seed)
    k = min(k, len(lab))
    sq = (lab ** 2).sum(1)
    centers = [lab[rng.choice(len(lab), p=weights / weights.sum())]]
    d2 = ((lab - centers[0]) ** 2).sum(1)
    for _ in range(k - 1):
        p = d2 * weights
        centers.append(lab[rng.choice(len(lab), p=p / p.sum())])
        d2 = np.minimum(d2, ((lab - centers[-1]) ** 2).sum(1))
    centers = np.array(centers)
    wsum = weights.sum()
    for _ in range(iters):
        d = sq[:, None] - 2 * lab @ centers.T + (centers ** 2).sum(1)[None]
        idx = d.argmin(1)
        mass = np.bincount(idx, weights=weights, minlength=k)
        new = centers.copy()
        ok = mass >= min_mass * wsum
        for dim in range(3):
            s_ = np.bincount(idx, weights=weights * lab[:, dim], minlength=k)
            new[ok, dim] = s_[ok] / mass[ok]
        if not ok.all():  # starved slots: move to color with biggest remaining error
            err = d[np.arange(len(lab)), idx] * weights
            for j in np.flatnonzero(~ok):
                i = err.argmax()
                new[j] = lab[i]
                err[i] = 0
        if np.allclose(new, centers, atol=1e-3):
            centers = new
            break
        centers = new
    return centers


def build_palette(rgb, opaque, k, restarts=6):
    """Palette (k,3 uint8) of true source colors nearest each cluster center."""
    px = rgb[opaque].reshape(-1, 3).astype(np.int32)
    key = (px[:, 0] << 16) | (px[:, 1] << 8) | px[:, 2]
    ukey, counts = np.unique(key, return_counts=True)
    if len(ukey) > 400000:  # noisy art: bin to 4-level steps (shift <= 2/255) to keep k-means fast
        key = ((px[:, 0] >> 2) << 18) | ((px[:, 1] >> 2) << 10) | ((px[:, 2] >> 2) << 2)
        ukey, counts = np.unique(key, return_counts=True)
        uniq = np.stack([((ukey >> 18) & 63) * 4 + 2, ((ukey >> 10) & 63) * 4 + 2, ((ukey >> 2) & 63) * 4 + 2], 1).astype(np.uint8)
    else:
        uniq = np.stack([(ukey >> 16) & 255, (ukey >> 8) & 255, ukey & 255], 1).astype(np.uint8)
    lab = srgb_to_lab(uniq)
    # sqrt weighting: small-but-distinct colors (eyes, pokeball) survive
    w = np.sqrt(counts.astype(np.float64))
    best, best_err = None, np.inf
    for s in range(restarts):
        c = kmeans_palette(lab, w, k, seed=s)
        err = (((lab[:, None] - c[None]) ** 2).sum(2).min(1) * w).sum()
        if err < best_err:
            best, best_err = c, err
    pal = []
    for c in best:  # snap to the real source color closest to the center
        pal.append(uniq[((lab - c) ** 2).sum(1).argmin()])
    pal = np.unique(np.array(pal), axis=0)
    return pal


def label_image(rgb, opaque, palette):
    lab_img = srgb_to_lab(rgb)
    lab_pal = srgb_to_lab(palette)
    labels = np.full(rgb.shape[:2], -1, np.int32)
    flat = lab_img[opaque]
    labels[opaque] = ((flat[:, None] - lab_pal[None]) ** 2).sum(2).argmin(1)
    return labels


# ---------- grid search ----------
def cell_counts(labels, k, tw, th, x0, y0, s, sy=None):
    sy = s if sy is None else sy
    """Histogram (th,tw,k+1); last bin = transparent. Source px -> cell by floor."""
    h, w = labels.shape
    ys, xs = np.mgrid[0:h, 0:w]
    cx = np.floor((xs - x0) / s).astype(np.int64)
    cy = np.floor((ys - y0) / sy).astype(np.int64)
    ok = (cx >= 0) & (cx < tw) & (cy >= 0) & (cy < th)
    lab = np.where(labels < 0, k, labels)
    idx = (cy[ok] * tw + cx[ok]) * (k + 1) + lab[ok]
    return np.bincount(idx, minlength=tw * th * (k + 1)).reshape(th, tw, k + 1)


def impurity(counts):
    tot = counts.sum(2)
    return (tot - counts.max(2)).sum() / max(tot.sum(), 1)


def search_grid(labels, k, tw, th, margin, steps=4, scale_span=0.08, scale_n=5, progress=None):
    h, w = labels.shape
    bw, bh = tw - 2 * margin, th - 2 * margin
    s0 = max(w / bw, h / bh)  # source px per target px so content fits
    best = (np.inf, None)
    for sc in np.linspace(1.0, 1 + scale_span, scale_n):
        s = s0 * sc
        # content (w,h) in source px maps to w/s, h/s cells; center in target
        base_x = -(tw * s - w) / 2
        base_y = -(th * s - h) / 2
        for oy in range(steps):
            for ox in range(steps):
                x0 = base_x + ox * s / steps - s / 2
                y0 = base_y + oy * s / steps - s / 2
                c = cell_counts(labels, k, tw, th, x0, y0, s)
                score = impurity(c)
                if score < best[0]:
                    best = (score, (x0, y0, s, c))
        if progress:
            progress(sc)
    return best


# ---------- native grid recovery ----------
def axis_period(labels, k, axis, plo=11.0, phi=24.0, pstep=0.1, noff=8):
    """Best cell period + offset along one axis by per-row color purity."""
    Lm = np.where(labels < 0, k, labels)
    if axis == 0:
        Lm = Lm.T
    Lm = Lm[::3]
    R, n = Lm.shape
    best = (np.inf, None, None)
    for p in np.arange(plo, phi, pstep):
        for o in np.arange(-p, 0, p / noff):
            c = np.floor((np.arange(n) - o) / p).astype(np.int64)
            nc = c.max() + 1
            idx = (np.arange(R)[:, None] * nc + c[None]) * (k + 1) + Lm
            cnt = np.bincount(idx.ravel(), minlength=R * nc * (k + 1)).reshape(R, nc, k + 1)
            sc = (cnt.sum(2) - cnt.max(2)).sum() / Lm.size
            if sc < best[0]:
                best = (sc, p, o)
    return best


def detect_grid(labels, k):
    """Auto-detect (px, py, ox, oy): cell sizes and offsets of the source's own pixel grid."""
    _, px, ox = axis_period(labels, k, 1)
    _, py, oy = axis_period(labels, k, 0)
    return px, py, ox, oy


def make_grid(labels, k, px, py, ox, oy):
    """Native label grid (nh,nw) for a given cell size/offset (k = transparent)."""
    h, w = labels.shape
    nw, nh = int(np.ceil((w - ox) / px)), int(np.ceil((h - oy) / py))
    counts = cell_counts(labels, k, nw, nh, ox, oy, px, py)
    grid = counts.argmax(2)  # includes transparent bin
    grid[counts.sum(2) == 0] = k  # cells outside the source
    return grid


def regrid(st, dpx=0.0, dpy=0.0, dox=0.0, doy=0.0):
    """Re-cut the native grid with manual tweaks: period deltas in source px, offsets in cell fractions."""
    px0, py0, ox0, oy0 = st["auto_grid"]
    px, py = px0 + dpx, py0 + dpy
    k = st["k"]
    st["grid"] = make_grid(st["labels"], k, px, py, ox0 + dox * px, oy0 + doy * py)
    st["freq"] = np.bincount(st["grid"][st["grid"] < k].ravel(), minlength=k).astype(np.float64)
    st["period"] = (px, py)


def thin_mask(grid, k):
    """Native cells that are 1 cell wide/tall features (eyes, outlines, highlights)."""
    g = np.pad(grid, 1, constant_values=k)
    c = g[1:-1, 1:-1]
    solid = c < k
    horiz = (g[1:-1, :-2] != c) & (g[1:-1, 2:] != c)
    vert = (g[:-2, 1:-1] != c) & (g[2:, 1:-1] != c)
    return solid & (horiz | vert)


def resample_native(grid, k, tw, th, margin, weights, thin=1.0):
    """Area-weighted vote of native cells into target pixels. Returns (th,tw,k+1) float counts."""
    nh, nw = grid.shape
    t = min((tw - 2 * margin) / nw, (th - 2 * margin) / nh)  # target px per native cell (<1)
    ox = (tw - nw * t) / 2
    oy = (th - nh * t) / 2
    ss = 8
    fy, fx = np.mgrid[0:th * ss, 0:tw * ss]
    ux = (fx + 0.5) / ss
    uy = (fy + 0.5) / ss
    cx = np.floor((ux - ox) / t).astype(np.int64)
    cy = np.floor((uy - oy) / t).astype(np.int64)
    ok = (cx >= 0) & (cx < nw) & (cy >= 0) & (cy < nh)
    lab = grid[cy.clip(0, nh - 1), cx.clip(0, nw - 1)]
    cellw = np.where(grid == k, 1.0, weights[np.minimum(grid, k - 1)])
    cellw = cellw * np.where(thin_mask(grid, k), thin, 1.0)
    wt = cellw[cy.clip(0, nh - 1), cx.clip(0, nw - 1)]
    idx = ((fy // ss) * tw + (fx // ss)) * (k + 1) + lab
    cnt = np.bincount(idx[ok], weights=wt[ok], minlength=tw * th * (k + 1))
    return cnt.reshape(th, tw, k + 1)


# ---------- analyze / render ----------
def analyze(img, tw, th, colors=15, margin=0, steps=4, progress=None):
    """Slow part: palette, native grid recovery, resample. Returns state for render()."""
    a = np.array(img.convert("RGBA"))
    opaque = a[..., 3] > 127
    ys, xs = np.where(opaque)
    if len(xs) == 0:
        return None
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    opaque = a[..., 3] > 127
    rgb = a[..., :3]

    palette = build_palette(rgb, opaque, colors)
    labels = label_image(rgb, opaque, palette)
    k = len(palette)
    auto = detect_grid(labels, k)
    st = dict(palette=palette, labels=labels, k=k, tw=tw, th=th, margin=margin,
              auto_grid=auto, impurity=0.0)
    regrid(st)
    st["scale"] = st["period"][0]
    return st


def merge_palette(palette, freq, thresh):
    """Merge palette colors closer than thresh (Lab delta-E). Returns (kept palette, remap k->new, new freq)."""
    k = len(palette)
    if thresh <= 0:
        return palette, np.arange(k + 1), freq
    lab = srgb_to_lab(palette) / np.array([LIGHT_WEIGHT, 1, 1])
    kept, remap = [], np.zeros(k + 1, np.int64)
    for i in np.argsort(-freq):
        for j, kk in enumerate(kept):
            if np.sqrt(((lab[i] - lab[kk]) ** 2).sum()) < thresh:
                remap[i] = j
                break
        else:
            remap[i] = len(kept)
            kept.append(i)
    remap[k] = len(kept)  # transparent
    nf = np.zeros(len(kept))
    np.add.at(nf, remap[:k], freq)
    return palette[kept], remap, nf


def adjust_palette(pal, sat=1.0, contrast=1.0, c15=False):
    c = pal.astype(np.float64)
    lum = (c @ np.array([0.299, 0.587, 0.114]))[:, None]
    c = lum + (c - lum) * sat
    c = (c - 128) * contrast + 128
    c = np.clip(np.round(c), 0, 255).astype(np.uint8)
    if c15:  # GBA: 5 bits per channel
        c = (c & 0xF8) | (c >> 5)
    return c


def smooth_labels(counts, K, visible, lam, passes=3):
    """Neighbor-aware refinement (ICM): score = own vote share + lam * neighbors' agreement."""
    th, tw = visible.shape
    solid = counts[..., :K]
    p = solid / np.maximum(solid.sum(2, keepdims=True), 1e-9)
    win = solid.argmax(2)
    for _ in range(passes):
        for y in range(th):
            for x in range(tw):
                if not visible[y, x]:
                    continue
                f = np.zeros(K)
                n = 0
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < th and 0 <= xx < tw and visible[yy, xx]:
                        f[win[yy, xx]] += 1
                        n += 1
                if n:
                    win[y, x] = (p[y, x] + lam * f / n).argmax()
    return win


def render(st, detail=0.15, outline=1.15, speckle=0.6, alpha_cut=0.5, thin=1.8,
           merge=0.0, smooth=0.0, sat=1.0, contrast=1.0, c15=False):
    """Fast part. detail: boost rare colors. outline: boost darkest color. speckle: confidence below
    which isolated pixels are absorbed (0=off). merge: delta-E under which palette colors merge.
    smooth: neighbor agreement weight. sat/contrast/c15: palette post-adjust."""
    th, tw = st["th"], st["tw"]
    palette, remap, freq = merge_palette(st["palette"], st["freq"], merge)
    k = len(palette)
    grid = remap[st["grid"]]
    w = (freq.sum() / np.maximum(freq, 1)) ** detail
    w /= w.min()
    dark = srgb_to_lab(palette)[:, 0].argmin()
    w[dark] *= outline
    counts = resample_native(grid, k, tw, th, st["margin"], w, thin)

    tot = counts.sum(2)
    transp = counts[..., k]
    visible = (tot > 0) & (transp / np.maximum(tot, 1) < alpha_cut)
    if smooth > 0:
        win = smooth_labels(counts, k, visible, smooth)
    else:
        win = counts[..., :k].argmax(2)  # weights already applied in resample
    share = counts[..., :k].max(2) / np.maximum(counts[..., :k].sum(2), 1)
    if speckle > 0:
        win = remove_speckles(win, visible, share, speckle)

    pal = adjust_palette(palette, sat, contrast, c15)
    out = np.zeros((th, tw, 4), np.uint8)
    out[visible, :3] = pal[win[visible]]
    out[visible, 3] = 255
    return Image.fromarray(out, "RGBA")


def remove_speckles(win, visible, share, conf=0.6):
    """Isolated low-confidence pixel whose neighbours (>=3 of 4) agree on another color -> adopt it."""
    h, w = win.shape
    out = win.copy()
    for y in range(h):
        for x in range(w):
            if not visible[y, x] or share[y, x] >= conf:
                continue
            nb = [win[y + dy, x + dx] for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
                  if 0 <= y + dy < h and 0 <= x + dx < w and visible[y + dy, x + dx]]
            if len(nb) < 3:
                continue
            vals, cnt = np.unique(nb, return_counts=True)
            m = cnt.argmax()
            if cnt[m] >= 3 and vals[m] != win[y, x]:
                out[y, x] = vals[m]
    return out


def descale(img, tw, th, colors=15, margin=0, steps=4, **render_kw):
    st = analyze(img, tw, th, colors, margin, steps)
    if st is None:
        return Image.new("RGBA", (tw, th), (0, 0, 0, 0)), {}
    return render(st, **render_kw), dict(impurity=st["impurity"], scale=st["scale"], colors=st["k"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("-s", "--sizes", nargs="+", default=list(SIZES), choices=list(SIZES))
    ap.add_argument("-c", "--colors", type=int, default=15)
    ap.add_argument("-m", "--margin", type=int, default=0, help="transparent border in target px")
    ap.add_argument("--steps", type=int, default=4, help="grid offset search density")
    ap.add_argument("--preview", type=int, default=0, help="also write NxN nearest-neighbor preview")
    ap.add_argument("--detail", type=float, default=0.15)
    ap.add_argument("--outline", type=float, default=1.15)
    ap.add_argument("--light", type=float, default=None, help="lightness weight in palette clustering (shading)")
    ap.add_argument("--thin", type=float, default=1.8)
    ap.add_argument("--speckle", type=float, default=0.6, help="0 = off")
    ap.add_argument("--alpha-cut", type=float, default=0.5)
    ap.add_argument("--merge", type=float, default=0.0, help="merge palette colors closer than this delta-E")
    ap.add_argument("--smooth", type=float, default=0.0)
    ap.add_argument("--sat", type=float, default=1.0)
    ap.add_argument("--contrast", type=float, default=1.0)
    ap.add_argument("--gba15", action="store_true", help="snap palette to 15-bit GBA colors")
    a = ap.parse_args()
    global LIGHT_WEIGHT
    if a.light is not None:
        LIGHT_WEIGHT = a.light

    src = Image.open(a.input)
    stem = Path(a.input).stem
    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    for name in a.sizes:
        tw, th = SIZES[name]
        out, info = descale(src, tw, th, a.colors, a.margin, steps=a.steps,
                            detail=a.detail, outline=a.outline, speckle=a.speckle, thin=a.thin,
                            alpha_cut=a.alpha_cut, merge=a.merge, smooth=a.smooth, sat=a.sat,
                            contrast=a.contrast, c15=a.gba15)
        p = Path(a.outdir) / f"{stem}_{name}.png"
        out.save(p)
        print(f"{name}: {p}  {info}")
        if a.preview:
            f = a.preview
            out.resize((tw * f, th * f), Image.NEAREST).save(Path(a.outdir) / f"{stem}_{name}_x{f}.png")


if __name__ == "__main__":
    sys.exit(main())
