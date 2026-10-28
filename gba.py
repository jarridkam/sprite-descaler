"""Final 'Gen 3 output' stage: GBA 15-bit colour, at most 15 visible colours, near-black outline ink."""
import numpy as np
from PIL import Image

import descale as D

NEAR_BLACK = (16, 16, 16)  # shared outline ink measured in real Gen 3 palettes


def snap555(rgb):
    """Quantize to 5 bits per channel, expanded the way the decomp .pal files do (c5*255/31)."""
    c5 = np.asarray(rgb, np.int32) >> 3
    return np.round(c5 * 255 / 31).astype(np.uint8)


def finalize(img, max_colors=15, snap=True, near_black=True):
    """Returns (RGBA image, info dict). Alpha is forced binary."""
    a = np.array(img.convert("RGBA"))
    M = a[..., 3] > 127
    a[..., 3] = np.where(M, 255, 0)
    info = dict(merged=0, before=0, after=0)
    if not M.any():
        return Image.fromarray(a, "RGBA"), info
    rgb = a[..., :3].copy()
    if near_black:  # ink-black tones all become the shared (16,16,16)
        ink = M & (rgb.max(axis=2) <= 40)
        rgb[ink] = NEAR_BLACK
    if snap:
        rgb = snap555(rgb)
    key = (rgb[..., 0].astype(np.int32) << 16) | (rgb[..., 1].astype(np.int32) << 8) | rgb[..., 2]
    ukeys, counts = np.unique(key[M], return_counts=True)
    info["before"] = int(len(ukeys))
    cols = np.stack([(ukeys >> 16) & 255, (ukeys >> 8) & 255, ukeys & 255], 1).astype(np.uint8)
    remap = {int(k): int(k) for k in ukeys}
    alive = list(range(len(ukeys)))
    lab = D.srgb_to_lab(cols) / np.array([D.LIGHT_WEIGHT, 1, 1])
    cnt = counts.astype(np.float64).copy()
    while len(alive) > max_colors:
        i = min(alive, key=lambda j: cnt[j])  # rarest colour
        others = [j for j in alive if j != i]
        d = ((lab[others] - lab[i]) ** 2).sum(1)
        j = others[int(d.argmin())]
        remap[int(ukeys[i])] = int(ukeys[j])
        for k_, v_ in list(remap.items()):  # keep chains resolved
            if v_ == int(ukeys[i]):
                remap[k_] = int(ukeys[j])
        cnt[j] += cnt[i]
        alive.remove(i)
        info["merged"] += 1
    if info["merged"]:
        k2 = key.copy()
        flat = k2[M]
        flat = np.array([remap[int(v)] for v in flat], np.int32)
        k2[M] = flat
        rgb = np.stack([(k2 >> 16) & 255, (k2 >> 8) & 255, k2 & 255], -1).astype(np.uint8)
    a[..., :3] = np.where(M[..., None], rgb, 0)
    info["after"] = int(len(np.unique(key[M]))) if not info["merged"] else int(len(alive))
    return Image.fromarray(a, "RGBA"), info
