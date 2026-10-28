# sprite-descaler

Turns sprites and artwork into Generation-3-style (GBA) pixel art: 64x64 / 32x32 / 16x32, 15 colors + transparent, 15-bit color.

- **Descale**: recovers the native pixel grid of AI-upscaled pixel art and resamples it down.
- **Pixelize**: redraws smooth artwork as pixel art (tinted outlines, face/feature preservation).
- **Background remover**, built-in pixel editor, 240x160 GBA preview, Gen 3 checker and input advisor.

Run: `pip install numpy pillow` then `python gui.py` (or `SpriteDescaler.bat`).
Build exe: `python -m PyInstaller --onefile --windowed --name SpriteDescaler gui.py`.

`python calibrate.py <folder of real 64x64 sprites>` rebuilds `gen3_profile.json` (the shipped one was measured from 97 Emerald sprites; the sprites themselves are not included).
