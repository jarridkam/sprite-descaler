"""Background remover for sprites / artwork on flat backgrounds.

Modes:
  edges  flood from the image border: only background connected to the edge goes
         (white coat inside an outline survives)
  color  remove every pixel near the background color, even enclosed holes
Options: tolerance, manual background color, grow (eat halo pixels), keep_holes.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def border_color(rgb):
    """Median color of the 1px image border."""
    b = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    return np.median(b, axis=0)


def _runs(mask):
    """Vectorized run extraction. Returns list per row of (starts, ends_exclusive)."""
    h, w = mask.shape
    m = np.zeros((h, w + 2), np.int8)
    m[:, 1:-1] = mask
    d = np.diff(m, axis=1)
    out = []
    for y in range(h):
        out.append((np.flatnonzero(d[y] == 1), np.flatnonzero(d[y] == -1)))
    return out


def edge_connected(mask):
    """Subset of mask connected (4-neighborhood) to the image border. Run-based union-find."""
    h, w = mask.shape
    rows = _runs(mask)
    ids, parent = [], []
    base = []
    n = 0
    for y in range(h):
        base.append(n)
        n += len(rows[y][0])
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for y in range(h - 1):
        s0, e0 = rows[y]
        s1, e1 = rows[y + 1]
        i = j = 0
        while i < len(s0) and j < len(s1):
            if s0[i] < e1[j] and s1[j] < e0[i]:  # overlap in x
                union(base[y] + i, base[y + 1] + j)
            if e0[i] < e1[j]:
                i += 1
            else:
                j += 1

    border = set()
    for y in range(h):
        s, e = rows[y]
        for i in range(len(s)):
            if y in (0, h - 1) or s[i] == 0 or e[i] == w:
                border.add(find(base[y] + i))
    out = np.zeros((h, w), bool)
    for y in range(h):
        s, e = rows[y]
        for i in range(len(s)):
            if find(base[y] + i) in border:
                out[y, s[i]:e[i]] = True
    return out


def drop_islands(fg, min_frac):
    """Remove foreground components smaller than min_frac of the largest one."""
    h, w = fg.shape
    rows = _runs(fg)
    base, n = [], 0
    for y in range(h):
        base.append(n)
        n += len(rows[y][0])
    if n == 0:
        return fg
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
    area = {}
    for y in range(h):
        s, e = rows[y]
        for i in range(len(s)):
            r = find(base[y] + i)
            area[r] = area.get(r, 0) + int(e[i] - s[i])
    keep_min = max(area.values()) * min_frac
    out = np.zeros((h, w), bool)
    for y in range(h):
        s, e = rows[y]
        for i in range(len(s)):
            if area[find(base[y] + i)] >= keep_min:
                out[y, s[i]:e[i]] = True
    return out


def background_mask(img, tol=30, mode="edges", color=None, grow=0, keep_holes=False, island=0.0):
    """Boolean mask, True = background."""
    a = np.array(img.convert("RGBA"))
    rgb = a[..., :3].astype(np.int32)
    bg = np.array(color if color is not None else border_color(rgb), np.float64)
    close = (np.abs(rgb - bg).max(axis=2) <= tol)
    close |= a[..., 3] < 10  # already transparent
    if mode == "edges":
        mask = edge_connected(close)
    else:
        mask = close
        if keep_holes:
            mask = edge_connected(close)
    if grow > 0:
        m = Image.fromarray((mask * 255).astype(np.uint8), "L")
        m = m.filter(ImageFilter.MaxFilter(2 * int(grow) + 1))
        mask = np.array(m) > 127
    elif grow < 0:  # shrink: protect edge pixels of the subject
        m = Image.fromarray((mask * 255).astype(np.uint8), "L")
        m = m.filter(ImageFilter.MinFilter(2 * int(-grow) + 1))
        mask = np.array(m) > 127
    if island > 0:
        mask = ~drop_islands(~mask, island)
    return mask


def remove_background(img, tol=30, mode="edges", color=None, grow=0, keep_holes=False, island=0.0):
    """Returns RGBA with background alpha = 0 (binary, pixel-art friendly)."""
    a = np.array(img.convert("RGBA"))
    mask = background_mask(img, tol, mode, color, grow, keep_holes, island)
    a[mask, 3] = 0
    return Image.fromarray(a, "RGBA")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("-t", "--tol", type=int, default=30)
    ap.add_argument("--mode", choices=["edges", "color"], default="edges")
    ap.add_argument("--color", help="background color as R,G,B (default: border median)")
    ap.add_argument("--grow", type=int, default=0, help="px to eat into subject edge (halo); negative shrinks mask")
    ap.add_argument("--island", type=float, default=0.0, help="drop specks smaller than this fraction of the subject (e.g. 0.02)")
    a = ap.parse_args()
    col = tuple(int(v) for v in a.color.split(",")) if a.color else None
    out = remove_background(Image.open(a.input), a.tol, a.mode, col, a.grow, island=a.island)
    p = a.output or str(Path(a.input).with_name(Path(a.input).stem + "_nobg.png"))
    out.save(p)
    print(p)


if __name__ == "__main__":
    sys.exit(main())
