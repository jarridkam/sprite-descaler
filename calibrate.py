"""Build gen3_profile.json from a folder of real Gen 3 64x64 sprites.
Usage: python calibrate.py calib/emerald
Data files are only read as images (never executed)."""
import glob
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import metrics as M


def main(folder):
    rows = []
    for f in sorted(glob.glob(str(Path(folder) / "*.png"))):
        try:
            im = Image.open(f).convert("RGBA")
        except Exception:
            continue
        if im.size != (64, 64):
            continue
        m = M.compute(im)
        if m:
            rows.append(m)
    keys = sorted({k for r in rows for k in r})
    prof = {"n": len(rows), "source": str(folder), "metrics": {}}
    for k in keys:
        v = np.array([r[k] for r in rows if k in r], np.float64)
        prof["metrics"][k] = {
            "median": float(np.median(v)), "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90)),
            "min": float(np.percentile(v, 1)), "max": float(np.percentile(v, 99)),
            "mean": float(v.mean()), "n": int(len(v)),
        }
    Path(M.PROFILE_PATH).write_text(json.dumps(prof, indent=1))
    print(f"{len(rows)} sprites ->", M.PROFILE_PATH)
    for k, s in prof["metrics"].items():
        print(f"{k:26s} median {s['median']:8.3f}   p10 {s['p10']:8.3f}   p90 {s['p90']:8.3f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "calib/emerald")
