"""Input advisor: looks at an image BEFORE conversion and suggests changes that make the result better.

advise(img) -> list of (level, title, detail)   level: 'good' | 'tip' | 'warn'
recommend_mode(img) -> 'descale' | 'pixelize'
CHECKLIST: the static 'best possible input' list.
"""
import numpy as np
from PIL import Image

import bgremove as BG

CHECKLIST = """BEST INPUT FOR A GEN 3 STYLE SPRITE
 1. Transparent PNG, or a flat solid background (white or a color not used by the subject).
 2. Tall enough: 800 px or more on the long side (at least 12x the target height).
 3. Subject fully inside the picture with a little margin; nothing cropped by the edge.
 4. A clear dark outline around the character and around important inner shapes.
 5. Flat cel shading: 2-4 tones per material, no gradients, no watercolor/paper texture.
 6. No floor shadow, glow, motion blur, or semi-transparent effects.
 7. Front or 3/4 view, limbs separated from the body, a simple readable pose.
 8. Neighbouring parts differ in lightness (not only in hue): arm vs torso, hand vs sleeve.
 9. Face: big simple eyes and mouth (a feature should be at least 1/40 of the figure height).
10. Avoid tiny details (belts, buckles, patterns): at 64 px they become noise.
11. Wide poses shrink the figure: for 64x64, a tall or compact pose uses the canvas best."""


def _periodicity(img):
    """Comb-filter test for an upscaled pixel grid. Returns min(x,y) peak ratio (pixel art ~2+, smooth art ~1.2-1.8)."""
    a = np.array(img.convert("RGBA")).astype(float)
    L = a[..., :3] @ [0.299, 0.587, 0.114]
    L = np.where(a[..., 3] < 128, 255, L)
    h, w = L.shape
    s = min(1.0, 900 / max(h, w))
    if s < 1:
        L = np.array(Image.fromarray(L.astype(np.uint8)).resize((int(w * s), int(h * s)), Image.BILINEAR)).astype(float)
    best = []
    for g in (np.abs(np.diff(L, axis=1)).sum(0), np.abs(np.diff(L, axis=0)).sum(1)):
        n, base, top = len(g), g.mean() + 1e-9, 0.0
        for p in np.arange(6, 40, 0.1):
            for o in np.arange(0, p, p / 8):
                idx = np.round(np.arange(o, n, p)).astype(int)
                idx = idx[idx < n]
                top = max(top, g[idx].mean() / base)
        best.append(top)
    return min(best)


def recommend_mode(img):
    return "descale" if _periodicity(img) >= 1.8 else "pixelize"


def advise(img, target=(64, 64)):
    out = []
    rgba = img.convert("RGBA")
    a = np.array(rgba)
    h, w = a.shape[:2]
    tw, th = target

    # --- already pixel art?
    per = _periodicity(rgba)
    if per >= 1.8:
        out.append(("good", "Looks like upscaled pixel art",
                    "A regular pixel grid was detected. Use 'Open sprite (descale)': it recovers the original pixels "
                    "exactly, which beats re-drawing."))
    else:
        out.append(("tip", "Smooth artwork (no pixel grid)",
                    "Use 'Open artwork (pixelize)'. If you can get an AI or hand pixel-art version of the same "
                    "picture, descaling that is usually closer to the real look."))

    # --- resolution
    if max(h, w) < 400:
        out.append(("warn", f"Low resolution ({w}x{h})",
                    "Eyes and thin lines get lost. Aim for 800 px or more on the long side."))
    elif max(h, w) > 4000:
        out.append(("tip", f"Very large image ({w}x{h})", "Works, but analysis will be slow. 1000-2000 px is plenty."))
    else:
        out.append(("good", f"Resolution {w}x{h}", "Enough detail for features to survive."))

    # --- background
    transparent = (a[..., 3] < 250).mean()
    if transparent > 0.02:
        out.append(("good", "Transparent background", "No background removal needed."))
        subject = a[..., 3] > 127
    else:
        rgb = a[..., :3].astype(float)
        border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
        spread = border.std(axis=0).mean()
        if spread < 12:
            out.append(("good", "Flat background", f"Border color is uniform: 'Remove background' will work. "
                                                  f"(spread {spread:.0f})"))
        elif spread < 35:
            out.append(("tip", "Slightly uneven background",
                        "Raise Background tolerance, or paint the background one flat color first."))
        else:
            out.append(("warn", "Busy or gradient background",
                        "Automatic removal will struggle. Cut the subject out (transparent PNG) or fill the background "
                        "with one flat color."))
        mask = BG.background_mask(rgba, 30, "edges")
        subject = ~mask
        if subject.mean() > 0.97:
            out.append(("warn", "Background not detected",
                        "Almost nothing was recognized as background: use a flat background or pick its color on the Source picture."))
    ys, xs = np.where(subject)
    if len(xs) == 0:
        return out + [("warn", "No subject found", "The image looks empty after removing the background.")]

    # --- subject cropped, margin, shape
    on_edge = [subject[0].any(), subject[-1].any(), subject[:, 0].any(), subject[:, -1].any()]
    if any(on_edge):
        out.append(("warn", "Subject touches the image edge",
                    "Parts may be cut off. Leave a margin around the whole character."))
    bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    aspect = bw / bh
    use_h = min(1.0, (tw / th) / aspect) if aspect > tw / th else 1.0
    if aspect > 1.35:
        out.append(("tip", f"Wide subject (aspect {aspect:.2f})",
                    f"At {tw}x{th} it fills only ~{use_h * 100:.0f}% of the canvas height, so details shrink. "
                    "Consider a more compact pose, a crop, or a canvas that fits (e.g. wide Pokemon use the full width)."))
    elif aspect < 0.3:
        out.append(("tip", f"Very tall thin subject (aspect {aspect:.2f})", "It will be narrow: details like eyes get tiny."))
    else:
        out.append(("good", f"Subject proportions OK (aspect {aspect:.2f})", ""))

    # --- stray specks / shadows
    clean = BG.drop_islands(subject, 0.02)
    extra = (subject.sum() - clean.sum()) / max(1, subject.sum())
    if extra > 0.003:
        out.append(("tip", "Stray specks or floor shadow detected",
                    f"~{extra * 100:.1f}% of the subject area is detached bits. Remove them (Background tab: 'Drop specks') "
                    "or erase the floor shadow first."))

    # --- ink / outline presence (full resolution, crisp)
    sub = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    lum = sub[..., :3].astype(float) @ [0.299, 0.587, 0.114]
    smask = subject[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    r = max(2, int(round(max(sub.shape[:2]) / 60)))
    k = 2 * r + 1
    pad = np.pad(lum, r, mode="edge")
    c = np.pad(pad.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    local = (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)
    ink = ((local - lum) > 40) & (lum < 90) & smask
    ink_frac = ink.sum() / max(1, smask.sum())
    if ink_frac < 0.004:
        out.append(("tip", "No dark outline found",
                    "Outlines will be generated from color edges. Art with a clear dark outline (even 2-3 px) converts "
                    "noticeably better, especially between same-colored parts."))
    else:
        out.append(("good", "Dark outline present", f"~{ink_frac * 100:.1f}% of the subject is ink: lines can be kept."))

    # --- texture / soft shading: share of subject pixels with mid-strength gradients
    sc = 900 / max(sub.shape[:2])
    Ls = np.array(Image.fromarray(lum.astype(np.uint8)).resize((max(2, int(sub.shape[1] * sc)), max(2, int(sub.shape[0] * sc))),
                                                            Image.BILINEAR)).astype(float)
    ms = np.array(Image.fromarray(smask.astype(np.uint8) * 255).resize(Ls.shape[::-1], Image.NEAREST)) > 127
    gx, gy = np.abs(np.diff(Ls, axis=1)), np.abs(np.diff(Ls, axis=0))
    hh, ww = min(gx.shape[0], gy.shape[0]), min(gx.shape[1], gy.shape[1])
    g = np.maximum(gx[:hh, :ww], gy[:hh, :ww])[ms[:hh, :ww]]
    soft = float(np.mean((g >= 1.5) & (g < 10))) if len(g) else 0.0
    if soft > 0.40:
        out.append(("tip", "Soft shading / texture",
                    f"{soft * 100:.0f}% of the subject is smooth gradient (watercolor, airbrush, noise). Raise 'Flatten texture' "
                    "and 'Color pop', or repaint with flat cel shading for the cleanest result."))
    else:
        out.append(("good", "Mostly flat colors", "Shading is simple enough to quantize cleanly."))

    # --- contrast
    sl = lum[smask]
    spread = np.percentile(sl, 95) - np.percentile(sl, 5)
    if spread < 90:
        out.append(("tip", "Low overall contrast",
                    "Shading may vanish at 64 px. Raise 'Contrast before palette' or darken the shadow tones."))
    # white-on-white
    if transparent <= 0.02:
        bgc = np.median(np.concatenate([a[0, :, :3], a[-1, :, :3]]), axis=0)
        near = (np.abs(sub[..., :3].astype(int) - bgc).max(2) < 25) & smask
        if near.sum() / max(1, smask.sum()) > 0.15:
            out.append(("tip", "Big areas match the background color",
                        "(e.g. a white coat on white). 'edges' mode keeps them only while an outline separates them: "
                        "keep the outline closed, or use a background color that isn't in the subject."))
    return out


def format_advice(items):
    icon = {"good": "OK  ", "tip": "TIP ", "warn": "WARN"}
    lines = []
    for lvl, title, detail in items:
        lines.append(f"[{icon[lvl]}] {title}")
        if detail:
            lines.append(f"       {detail}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        print("==", p)
        print(format_advice(advise(Image.open(p))))
