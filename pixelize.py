"""Pixelize: redraw smooth artwork (no pixel grid) as small pixel art with a limited palette.

Pipeline:
  1. remove flat background if the image is opaque, crop to subject, fit into target box
  2. supersample (premultiplied) and flatten texture with a median filter
  3. k-means palette (colors-1) + one reserved dark outline color
  4. each target pixel = weighted vote of its supersampled block
  5. outline pass: silhouette edge + dark line detail
The result can be saved big (nearest-neighbor) and fed to descale.py, or edited directly.
"""
import argparse
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

import descale as D
from bgremove import remove_background as _bg_remove


def remove_background(a, tol=28):
    """Flood-fill flat background from the border of an opaque image. Mutates alpha."""
    h, w = a.shape[:2]
    corners = np.array([a[0, 0, :3], a[0, -1, :3], a[-1, 0, :3], a[-1, -1, :3]], np.int32)
    bg = np.median(corners, axis=0)
    close = (np.abs(a[..., :3].astype(np.int32) - bg).sum(2) <= tol * 3 // 2)
    seen = np.zeros((h, w), bool)
    dq = deque()
    for x in range(w):
        dq.extend(((0, x), (h - 1, x)))
    for y in range(h):
        dq.extend(((y, 0), (y, w - 1)))
    while dq:
        y, x = dq.popleft()
        if not (0 <= y < h and 0 <= x < w) or seen[y, x] or not close[y, x]:
            continue
        seen[y, x] = True
        dq.extend(((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)))
    a[seen, 3] = 0
    return a


def _lum(rgb):
    return rgb.astype(np.float64) @ np.array([0.299, 0.587, 0.114])


def _box_blur(x, r):
    k = 2 * r + 1
    p = np.pad(x, r, mode="edge")
    c = p.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def _lab(c):
    """Lab with true lightness (undo the shading weight used for clustering)."""
    return D.srgb_to_lab(np.asarray(c)) / np.array([D.LIGHT_WEIGHT, 1.0, 1.0])


def small_blobs(labels, max_area):
    """Connected single-label regions (4-neighbour) no bigger than max_area px.
    Returns dicts: label, area, bbox, centroid, runs. Run-based union-find, no scipy."""
    from bgremove import _runs
    h, w = labels.shape
    blobs = []
    for lab in np.unique(labels[labels >= 0]):
        rows = _runs(labels == lab)
        base, n = [], 0
        for y in range(h):
            base.append(n)
            n += len(rows[y][0])
        if n == 0:
            continue
        parent = list(range(n))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for y in range(h - 1):
            s0, e0 = rows[y]
            s1, e1 = rows[y + 1]
            i = j = 0
            while i < len(s0) and j < len(s1):
                if s0[i] < e1[j] and s1[j] < e0[i]:
                    ra, rb = find(base[y] + i), find(base[y + 1] + j)
                    if ra != rb:
                        parent[rb] = ra
                if e0[i] < e1[j]:
                    i += 1
                else:
                    j += 1
        comp = {}
        for y in range(h):
            st_, en_ = rows[y]
            for i in range(len(st_)):
                r = find(base[y] + i)
                c = comp.get(r)
                x0, x1 = int(st_[i]), int(en_[i])
                ln = x1 - x0
                if c is None:
                    comp[r] = c = dict(label=int(lab), area=0, sx=0.0, sy=0.0, x0=x0, x1=x1, y0=y, y1=y + 1, runs=[])
                c["area"] += ln
                c["sx"] += (x0 + x1 - 1) / 2 * ln
                c["sy"] += y * ln
                c["x0"], c["x1"], c["y1"] = min(c["x0"], x0), max(c["x1"], x1), y + 1
                if c["area"] <= max_area * 2:  # keep runs only while it can still qualify
                    c["runs"].append((y, x0, x1))
                else:
                    c["runs"] = None
        for c in comp.values():
            if c["area"] <= max_area and c["runs"] is not None:
                c["cx"], c["cy"] = c["sx"] / c["area"], c["sy"] / c["area"]
                blobs.append(c)
    return blobs


def _enclosure(blob, labels, alpha, ss):
    """(enclosing label, fraction of the ring it covers) for a blob; (None, 0) if it touches the edge."""
    pad = max(2, int(ss * 0.8))
    h, w = labels.shape
    y0, y1 = max(0, blob["y0"] - pad), min(h, blob["y1"] + pad)
    x0, x1 = max(0, blob["x0"] - pad), min(w, blob["x1"] + pad)
    m = np.zeros((y1 - y0, x1 - x0), bool)
    for (y, a, b) in blob["runs"]:
        m[y - y0, a - x0:b - x0] = True
    dil = np.array(Image.fromarray((m * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(2 * pad + 1))) > 127
    ring = dil & ~m
    lab = labels[y0:y1, x0:x1][ring]
    al = alpha[y0:y1, x0:x1][ring]
    if len(lab) < 6 or (~al).mean() > 0.15:
        return None, 0.0
    lab = lab[lab >= 0]
    lab = lab[lab != blob["label"]]
    if len(lab) < 6:
        return None, 0.0
    cnt = np.bincount(lab)
    e = int(cnt.argmax())
    return e, cnt[e] / ring.sum()


def prepare(img, tw, th, colors=15, margin=1, smooth=0, ss=6, sat=1.2, contrast=1.05, auto_bg=True, tones=3):
    """Slow stage: fit subject, supersample, flatten, color-pop, region palette, feature blobs.
    tones = palette slots reserved for outline colors (taken out of `colors`)."""
    a = np.array(img.convert("RGBA"))
    if auto_bg and (a[..., 3] > 250).all():
        a = np.array(_bg_remove(Image.fromarray(a, "RGBA")))
    opaque = a[..., 3] > 127
    ys, xs = np.where(opaque)
    if len(xs) == 0:
        return None
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = a.shape[:2]

    s = min((tw - 2 * margin) / w, (th - 2 * margin) / h)
    cw, ch = max(1, round(w * s * ss)), max(1, round(h * s * ss))
    sub = Image.fromarray(a, "RGBA").convert("RGBa").resize((cw, ch), Image.LANCZOS).convert("RGBA")
    W, H = tw * ss, th * ss
    work = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    work.paste(sub, ((W - cw) // 2, (H - ch) // 2))
    wa = np.array(work)
    alpha = wa[..., 3] > 127
    rgb = wa[..., :3].copy()

    if smooth >= 3:
        rgb = np.array(Image.fromarray(rgb, "RGB").filter(ImageFilter.MedianFilter(int(smooth) | 1)))

    # ink detection at FULL resolution (thin lines are crisp there), then min/max-pooled to work size
    lum_f = _lum(a[..., :3])
    rel_f = _box_blur(lum_f, max(2, int(round(1.0 / s)))) - lum_f  # how much darker than its surroundings
    clear = a[..., 3] < 128
    lum_f = np.where(clear, 255.0, lum_f)
    rel_f = np.where(clear, -255.0, rel_f)
    by = np.floor(np.arange(ch) * h / ch).astype(int)
    bx = np.floor(np.arange(cw) * w / cw).astype(int)
    lmin_c = np.minimum.reduceat(np.minimum.reduceat(lum_f, by, axis=0), bx, axis=1)
    rel_c = np.maximum.reduceat(np.maximum.reduceat(rel_f, by, axis=0), bx, axis=1)
    ox, oy = (W - cw) // 2, (H - ch) // 2
    lmin = np.full((H, W), 255.0)
    rel = np.full((H, W), -255.0)
    lmin[oy:oy + ch, ox:ox + cw] = lmin_c
    rel[oy:oy + ch, ox:ox + cw] = rel_c

    if sat != 1.0 or contrast != 1.0:
        c = rgb.astype(np.float64)
        l2 = (c @ np.array([0.299, 0.587, 0.114]))[..., None]
        c = l2 + (c - l2) * sat
        c = (c - 128) * contrast + 128
        rgb = np.clip(c, 0, 255).astype(np.uint8)

    # ink = thin dark strokes. Regions are clustered WITHOUT ink so line pixels don't pollute fills.
    ink_all = (rel > 15) & (lmin < 110) & alpha
    r_core = max(1, int(round(ss * 0.35)))
    core = np.array(Image.fromarray((ink_all * 255).astype(np.uint8), "L").filter(ImageFilter.MinFilter(2 * r_core + 1))) > 127
    thick = np.array(Image.fromarray((core * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(2 * r_core + 3))) > 127
    ink = ink_all & ~thick  # only THIN dark strokes are lines; compact dark blobs (eyes, stripes) stay regions
    fill = alpha & ~ink
    if fill.sum() < 50:
        fill = alpha
    n_reg = max(2, colors - max(0, int(tones)))
    pal = D.build_palette(rgb, fill, n_reg)
    labels = D.label_image(rgb, alpha, pal)
    # inpaint ink pixels with the nearest fill label (a few dilation passes)
    todo = ink & alpha
    for _ in range(max(2, ss)):
        if not todo.any():
            break
        got = np.full(labels.shape, -1, np.int32)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            sh = np.roll(np.roll(labels, dy, 0), dx, 1)
            ok = sh >= 0
            ok &= ~np.roll(np.roll(todo, dy, 0), dx, 1)
            got = np.where((got < 0) & ok, sh, got)
        fillable = todo & (got >= 0)
        labels = np.where(fillable, got, labels)
        todo = todo & ~fillable
    freq = np.bincount(labels[labels >= 0], minlength=len(pal)).astype(np.float64)

    # small enclosed features (eyes, mouth, emblems): found on the cleaned region map
    area_total = int(alpha.sum())
    blobs = []
    for bl in small_blobs(labels, max(8, int(area_total * 0.03))):
        e, frac = _enclosure(bl, labels, alpha, ss)
        if e is None or frac < 0.6:
            continue
        bl["enc"] = e
        bl["dE"] = float(np.linalg.norm(_lab(pal[bl["label"]]) - _lab(pal[e])))
        bl["runs"] = None
        blobs.append(bl)
    # short, compact ink strokes (pupils, brows, nostrils, mouth) are marks to keep, not line networks
    marks = []
    ink_lab = np.where(ink_all, 0, -1).astype(np.int32)  # connected: real lines stay long and are excluded by size
    for m in small_blobs(ink_lab, int((3.2 * ss) ** 2)):
        if max(m["x1"] - m["x0"], m["y1"] - m["y0"]) <= 4 * ss and m["area"] >= ss * ss * 0.12:
            dark_v = np.concatenate([lmin[y, x0_:x1_] for (y, x0_, x1_) in m["runs"]])
            rel_v = np.concatenate([rel[y, x0_:x1_] for (y, x0_, x1_) in m["runs"]])
            if dark_v.mean() > 85 or rel_v.max() < 40:  # pigment pooling is gray-brown; real ink is near black
                continue
            cells = {}
            for (y, x0_, x1_) in m["runs"]:
                for x in range(x0_, x1_):
                    cells[(y // ss, x // ss)] = cells.get((y // ss, x // ss), 0) + 1
            marks.append(dict(cells=cells, area=m["area"]))
    accents = find_accents(rgb, alpha, ss, lmin)
    return dict(tw=tw, th=th, ss=ss, alpha=alpha, lmin=lmin, rel=rel, marks=marks, pal=pal, labels=labels, freq=freq,
                blobs=blobs, area_total=area_total, tones=int(tones), accents=accents,
                map=dict(x0=int(xs.min()), y0=int(ys.min()), w=w, h=h, cw=cw, ch=ch, ox=ox, oy=oy))


def find_accents(rgb, alpha, ss, lmin):
    """Small salient details (eye whites, claws, brows, nostrils, highlights): blobs whose lightness differs a lot from
    their surroundings, found independently of the palette so they survive color merging and sit on the silhouette
    edge too. Returns dicts in output-cell units: cx, cy, w, h, rgb, kind ('light'/'dark'), score."""
    H, W = alpha.shape
    L = _lum(rgb)
    m = alpha.astype(np.float64)
    r = int(round(2.5 * ss))
    num = _box_blur(np.where(alpha, L, 0.0), r)
    den = np.maximum(_box_blur(m, r), 1e-3)
    diff = np.where(alpha, L - num / den, 0.0)
    lab = np.full((H, W), -1, np.int32)
    lab[(diff > 22) & alpha] = 0
    lab[(diff < -40) & alpha] = 1
    total = int(alpha.sum())
    out = []
    for bl in small_blobs(lab, max(8, int(total * 0.02))):
        wc, hc = (bl["x1"] - bl["x0"]) / ss, (bl["y1"] - bl["y0"]) / ss
        area_c = bl["area"] / (ss * ss)
        if area_c < 0.45 or max(wc, hc) > 6 or min(wc, hc) < 0.4:
            continue
        ys_ = np.concatenate([np.full(b - a_, y) for (y, a_, b) in bl["runs"]])
        xs_ = np.concatenate([np.arange(a_, b) for (y, a_, b) in bl["runs"]])
        px = rgb[ys_, xs_]
        lp = L[ys_, xs_]
        pick = lp <= np.percentile(lp, 35) if bl["label"] == 1 else lp >= np.percentile(lp, 65)
        col = px[pick].mean(axis=0)  # the extreme end of the blob: real white / real ink, not the blurred average
        sal = float(np.abs(diff[ys_, xs_]).mean())
        ink_l = float(np.percentile(lmin[ys_, xs_], 15))  # full-res darkest value: real ink even when downsampling grays it
        out.append(dict(cx=bl["cx"] / ss, ink=ink_l, cy=bl["cy"] / ss, w=wc, h=hc, area=area_c, rgb=col,
                        kind="light" if bl["label"] == 0 else "dark", score=sal * min(area_c, 4.0) ** 0.5))
    return out


def focus_mask(st, boxes):
    """Cell mask (th, tw) of source-pixel boxes."""
    th, tw, ss = st["th"], st["tw"], st["ss"]
    fm = np.zeros((th, tw), bool)
    mp = st.get("map")
    for (x0, y0, x1, y1) in boxes or []:
        if mp is None:
            break
        sx, sy = mp["cw"] / mp["w"], mp["ch"] / mp["h"]
        a0 = ((min(x0, x1) - mp["x0"]) * sx + mp["ox"]) / ss
        a1 = ((max(x0, x1) - mp["x0"]) * sx + mp["ox"]) / ss
        b0 = ((min(y0, y1) - mp["y0"]) * sy + mp["oy"]) / ss
        b1 = ((max(y0, y1) - mp["y0"]) * sy + mp["oy"]) / ss
        fm[max(0, int(np.floor(b0))):min(th, int(np.ceil(b1))), max(0, int(np.floor(a0))):min(tw, int(np.ceil(a1)))] = True
    return fm


def _pixel_perfect(line, protected):
    """Remove redundant L-corner pixels and orphan dots from 1px lines."""
    h, w = line.shape
    out = line.copy()
    for _ in range(2):
        p = np.pad(out, 1)
        n, so, we, ea = p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]
        cnt4 = n.astype(int) + so + we + ea
        corner = out & (cnt4 == 2) & ((n & we) | (n & ea) | (so & we) | (so & ea))
        n8 = (p[:-2, :-2].astype(int) + p[:-2, 2:] + p[2:, :-2] + p[2:, 2:] + cnt4)
        orphan = out & (n8 == 0)
        out = out & ~((corner | orphan) & ~protected)
    return out


def render(st, line=0.4, silhouette=True, detail=0.4, alpha_cut=0.3, speckle=0.6, smooth=0.0,
           merge=0.0, outline_dark=0.4, line_abs=95, line_rel=22, outer=False,
           post_sat=1.0, post_contrast=1.0, bright=0, c15=False,
           contrast_lines=0.4, tint=0.7, feature=0.7, tidy=True, near_black=(16, 16, 16), accent=0.7, focus=None):
    """Fast stage. Returns RGBA image (tw, th).
    line: how much of the source's ink becomes lines (0 = none). line_abs / line_rel: what counts as ink.
    contrast_lines: lines between very different colors (0 = never, like a belly emblem; 1 = always).
    tint: outline color, 0 = darkest tone (black-ish), 1 = dark version of the color it borders.
    accent: stamp small salient details (eye whites, claws, brows) at >= 1 px in the closest palette color.
    focus: list of (x0, y0, x1, y1) boxes in source pixels (a face, hands): inside them every small detail is kept
    (rare colors win the vote, weaker accents are stamped).
    outline_dark: how dark tinted outlines get (multiplier). feature: protect small enclosed features
    (eyes, mouth, emblems). tidy: pixel-perfect outline cleanup. outer: outline outside the shape."""
    tw, th, ss = st["tw"], st["th"], st["ss"]
    pal0, labels0, alpha = st["pal"], st["labels"], st["alpha"]
    fm = focus_mask(st, focus)

    pal, remap, freq = D.merge_palette(pal0, st["freq"], merge)
    kr = len(pal)
    labels = np.where(labels0 >= 0, remap[np.maximum(labels0, 0)], -1)

    # outline tones: darkened versions of the biggest, mid-lightness region colors + one near-black tone
    n_tones = max(1, st["tones"])
    lum_pal = pal.astype(np.float64) @ np.array([0.299, 0.587, 0.114])
    order = [i for i in np.argsort(-freq) if 40 < lum_pal[i] < 235]
    bases, seen = [], []
    for i in order:
        lab_i = _lab(pal[i])
        if all(np.linalg.norm(lab_i - o) > 14 for o in seen):
            bases.append(i)
            seen.append(lab_i)
        if len(bases) >= n_tones - 1:
            break
    dk = np.clip(outline_dark, 0.05, 1.0)
    dark_tone = (np.array(near_black, np.float64) if near_black is not None
                 else np.clip(pal[lum_pal.argmin()].astype(np.float64) * min(dk, 0.5) * 0.8, 0, 255))
    tone_rgb = [dark_tone] + [np.clip(pal[i].astype(np.float64) * dk, 0, 255) for i in bases]
    tone_rgb = np.array(tone_rgb[:n_tones])
    tones_u8 = np.round(tone_rgb).astype(np.uint8)
    palette = np.vstack([pal, tones_u8])
    k = len(palette)
    tone0 = kr  # index of the near-black tone

    wts = (freq.sum() / np.maximum(freq, 1)) ** detail
    wts /= wts.min()
    counts = D.cell_counts(labels, k, tw, th, 0, 0, ss).astype(np.float64)
    counts[..., :kr] *= wts
    counts[..., kr:k] = 0
    tot = counts.sum(2)
    transp = counts[..., k]
    visible = (tot > 0) & (transp / np.maximum(tot, 1) < alpha_cut)
    solid = counts[..., :kr]
    share = solid.max(2) / np.maximum(solid.sum(2), 1)
    win = D.smooth_labels(counts[..., :kr], kr, visible, smooth) if smooth > 0 else solid.argmax(2)
    if fm.any():  # focus boxes: strong rarity weighting so small distinct colors (eye white, pupil) win their pixel
        wf = (freq.sum() / np.maximum(freq, 1)) ** (detail + 0.2)
        wf /= wf.min()
        raw = counts[..., :kr] / wts
        win = np.where(fm, (raw * wf).argmax(2), win)
    if speckle > 0:
        win = D.remove_speckles(win, visible, share, speckle)

    if outer:  # grow the subject by one pixel; new ring takes a neighbor's color
        p = np.pad(visible, 1, constant_values=False)
        ring = ~visible & (p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:])
        fill = win.copy()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            sh = np.roll(np.roll(win, dy, 0), dx, 1)
            vs = np.roll(np.roll(visible, dy, 0), dx, 1)
            fill = np.where(ring & vs, sh, fill)
        win = np.where(ring, fill, win)
        visible = visible | ring
        silhouette = True

    # ---- feature preserver: small enclosed regions keep >= 1 pixel, same size for same-sized features
    protected = np.zeros((th, tw), bool)
    if feature > 0:
        max_frac = 0.004 + 0.026 * feature
        min_de = 46 - 30 * feature
        for bl in sorted(st["blobs"], key=lambda b: -b["area"]):
            if bl["area"] > st["area_total"] * max_frac or bl["area"] < ss * ss * 0.12 or bl["dE"] < min_de:
                continue
            lab, enc = remap[bl["label"]], remap[bl["enc"]]
            if lab == enc:
                continue
            pw = max(1, int(round((bl["x1"] - bl["x0"]) / ss)))
            ph = max(1, int(round((bl["y1"] - bl["y0"]) / ss)))
            x0 = int(round(bl["cx"] / ss - pw / 2))
            y0 = int(round(bl["cy"] / ss - ph / 2))
            for yy in range(max(0, y0), min(th, y0 + ph)):
                for xx in range(max(0, x0), min(tw, x0 + pw)):
                    if visible[yy, xx]:
                        win[yy, xx] = lab
                        protected[yy, xx] = True

    # ---- lines: where the source has ink AND the two colors are too alike to read without one
    ink = np.zeros((th, tw))
    if line > 0:
        dark = (st["rel"] > line_rel) & (st["lmin"] < line_abs) & alpha
        ink = dark.reshape(th, ss, tw, ss).mean(axis=(1, 3))
    thr = (1.0 - line) * 0.5
    lab_pal = _lab(pal)
    DE = np.linalg.norm(lab_pal[:, None] - lab_pal[None], axis=2)
    de_cut = 10 + 60 * contrast_lines
    lmask = np.zeros((th, tw), bool)
    if line > 0:
        for (ya, xa, yb, xb) in ((slice(0, th), slice(0, tw - 1), slice(0, th), slice(1, tw)),
                                 (slice(0, th - 1), slice(0, tw), slice(1, th), slice(0, tw))):
            pa, pb = (ya, xa), (yb, xb)
            both = visible[pa] & visible[pb] & (win[pa] != win[pb])
            cond = both & (np.maximum(ink[pa], ink[pb]) >= max(thr, 1e-6)) & (DE[win[pa], win[pb]] <= de_cut)
            pick_a = ink[pa] >= ink[pb]
            tgt_a = cond & pick_a & ~protected[pa]
            tgt_b = cond & ~pick_a & ~protected[pb]
            tgt_a |= cond & ~pick_a & protected[pb] & ~protected[pa]
            tgt_b |= cond & pick_a & protected[pa] & ~protected[pb]
            lmask[pa] |= tgt_a
            lmask[pb] |= tgt_b
    if silhouette:
        p = np.pad(visible, 1, constant_values=False)
        edge = visible & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
        lmask |= edge
    if tidy:
        lmask = _pixel_perfect(lmask, protected)

    # outline color per line pixel: blend near-black with a darkened own color, then nearest tone
    own = pal[win].astype(np.float64)
    target = tone_rgb[0] * (1 - tint) + own * dk * tint
    tl = _lab(tones_u8)
    tgt_lab = _lab(np.clip(target, 0, 255).astype(np.uint8))
    tone_idx = np.linalg.norm(tgt_lab[..., None, :] - tl[None, None], axis=3).argmin(2)

    idx = np.where(lmask, kr + tone_idx, win)
    if feature > 0:
        need = ss * ss * (0.30 - 0.22 * feature)  # more feature protection = fainter marks still count
        for m in st["marks"]:
            cells = {c: n for c, n in m["cells"].items() if 0 <= c[0] < th and 0 <= c[1] < tw}
            if not cells:
                continue
            keep = [c for c, n in cells.items() if n >= need] or [max(cells, key=cells.get)]
            for (cy, cx) in keep:
                if visible[cy, cx]:
                    idx[cy, cx] = kr  # near-black tone
    if accent > 0:
        min_score = 110 - 90 * accent
        pl = _lab(palette)
        for ac in sorted(st["accents"], key=lambda a_: a_["score"]):
            cx_, cy_ = int(np.clip(ac["cx"], 0, tw - 1)), int(np.clip(ac["cy"], 0, th - 1))
            inf = bool(fm[cy_, cx_])
            if ac["score"] < min_score * (0.6 if inf and ac["kind"] == "light" else 1.0):
                continue
            pw = int(min(3, max(1, round(ac["w"]))))
            ph = int(min(3, max(1, round(ac["h"]))))
            col = np.clip(ac["rgb"], 0, 255).astype(np.uint8)
            cl = _lab(col)
            if ac["kind"] == "dark":
                if ac["ink"] > 70:
                    continue  # dark but not ink-black: it is shading, the regions already show it
                ci = tone0
            else:
                if cl[0] < 80:
                    continue
                ci = int(np.linalg.norm(pl[:kr] - cl, axis=1).argmin())
            x0 = int(np.floor(ac["cx"] - pw / 2 + 0.5))
            y0 = int(np.floor(ac["cy"] - ph / 2 + 0.5))
            for yy in range(max(0, y0), min(th, y0 + ph)):
                for xx in range(max(0, x0), min(tw, x0 + pw)):
                    if visible[yy, xx]:
                        idx[yy, xx] = ci
    pal_out = D.adjust_palette(palette, post_sat, post_contrast, c15)
    if bright:
        pal_out = np.clip(pal_out.astype(np.int32) + int(bright), 0, 255).astype(np.uint8)
    out = np.zeros((th, tw, 4), np.uint8)
    out[visible, :3] = pal_out[idx[visible]]
    out[visible, 3] = 255
    return Image.fromarray(out, "RGBA")


def pixelize(img, tw, th, colors=15, margin=1, smooth=0, line=0.4, silhouette=True,
             detail=0.4, ss=6, alpha_cut=0.3, speckle=0.6, sat=1.2, contrast=1.05, tones=3, **render_kw):
    """One-shot convenience: prepare + render."""
    st = prepare(img, tw, th, colors, margin, smooth, ss, sat, contrast, tones=tones)
    if st is None:
        return Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    return render(st, line=line, silhouette=silhouette, detail=detail, alpha_cut=alpha_cut,
                  speckle=speckle, **render_kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("-s", "--size", default="64x64", choices=list(D.SIZES))
    ap.add_argument("-c", "--colors", type=int, default=15)
    ap.add_argument("-m", "--margin", type=int, default=1)
    ap.add_argument("--smooth", type=int, default=0, help="median filter size (0/1 = off)")
    ap.add_argument("--line", type=float, default=0.4)
    ap.add_argument("--no-silhouette", action="store_true")
    ap.add_argument("--sat", type=float, default=1.35)
    ap.add_argument("--contrast", type=float, default=1.1)
    ap.add_argument("--big", type=int, default=16, help="also save nearest-neighbor upscale (feed to descale.py)")
    a = ap.parse_args()
    tw, th = D.SIZES[a.size]
    out = pixelize(Image.open(a.input), tw, th, a.colors, a.margin, a.smooth, a.line, not a.no_silhouette,
                   sat=a.sat, contrast=a.contrast)
    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    stem = Path(a.input).stem
    p = Path(a.outdir) / f"{stem}_pixel_{a.size}.png"
    out.save(p)
    print(p)
    if a.big:
        bp = Path(a.outdir) / f"{stem}_pixel_{a.size}_x{a.big}.png"
        out.resize((tw * a.big, th * a.big), Image.NEAREST).save(bp)
        print(bp)


if __name__ == "__main__":
    sys.exit(main())
