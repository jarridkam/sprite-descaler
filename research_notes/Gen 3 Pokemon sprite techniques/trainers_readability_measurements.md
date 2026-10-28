# Gen 3 trainer sprites, tiny-sprite readability metrics, and measurements of a real May sprite

Scope note: web access was limited. Bulbapedia returned 403 to fetches, Spriters Resource and PokeCommunity tutorials could not be read, and no Slynyrd / MortMort / Saint11 / Derek Yu page was retrieved. Everything under "Cited Findings" has a URL I actually read or saw in a search snippet. Everything else is labelled as an inference or a gap. Part C is computed from the file and is the strongest material here.

## Part A - How Gen 3 trainer sprites are built (compared with Pokemon sprites, Gen 2 and Gen 4)

### Takeaway
Gen 3 trainer front sprites share the Pokemon sprite format: 64x64 canvas, 16-colour palette (15 colours plus transparent), 4bpp. Back sprites are multi-frame and share the front sprite's palette. I could not retrieve any source describing face, proportion or outline conventions, so those come from measuring one sprite (Part C) and are marked as such.

### Cited Findings
- "Trainer and monster images are LZ77-compressed 64 by 64 pixels, 16 colors." Trainer palettes and sprite pointer tables sit at separate ROM offsets (FireRed $239A1C palettes, $23957C sprites; Ruby $1EC7D4 / $1EC53C). — [Data Crystal: Pokemon 3rd Generation](https://datacrystal.tcrf.net/wiki/Pokémon_3rd_Generation)
- Back images are described as "much taller" than front images, and in FRLG they are uncompressed. No exact size is given. — [Data Crystal](https://datacrystal.tcrf.net/wiki/Pokémon_3rd_Generation)
- Emerald decomp wiki: each back-pic frame is 0x0800 bytes (= 4096 px at 4bpp, so 64x64 per frame). Default back pics use 4 frames (animation order 4>1>2>3); a tutorial extends this to 5. Frames are indexed 16-colour PNGs. Brendan, May, Steven, Wally and RS-Brendan/RS-May backs originally use the same palette as their front sprite. The coordinate table has `.size = 8` and `.y_offset = 5` per trainer back pic (unit of `size` not stated). — [pokeemerald wiki: Trainer Backsprite Editing](https://code.heni.lol/decomp/emerald/wiki/Trainer-Backsprite-Editing)
- Bulbapedia (user-page note, secondary): sprite canvas is 56x56 for Gen I-II, 64x64 for Gen III, 80x80 for Gen IV. This is stated for Pokemon sprites; Gen II back sprites are 48x48 inside a 56x56 reserve. — search snippet of [Bulbapedia Pokemon sprite](https://bulbapedia.bulbagarden.net/wiki/Pokémon_sprite) and [User:G50 template](https://bulbapedia.bulbagarden.net/wiki/User:G50/Sprites/Shiny_Front/Template/Shellos)
- A PokeCommunity resource thread exists for "DS style 64x64 trainer sprites", which suggests 64x64 is also the community's canvas for later-style trainers. I did not read it. — [PokeCommunity thread](https://www.pokecommunity.com/threads/the-ds-style-64x64-trainer-sprite-resource.308798/)

### Inferences
- Measured May sprite (Part C): 15 opaque colours plus transparency = exactly the 16-entry limit. The palette budget is the main construction constraint: skin 3 tones, hair roughly 2-3, red 2, green 2, neutrals 5, with the single darkest colour (#000000) shared for gloves, shoes and ball.
- Figure fitting (measured on one sprite): figure 55 px tall in 64 px canvas (86%), top margin 5, bottom margin 4; width 37 px with an off-centre pose (margins L 9, R 18). Head with hat is roughly rows 5-20 (about 16 px, about 29% of figure height, so about 3.4 heads tall: stylised, not realistic proportions). Pigtails extend the head to about 22 px wide.
- Face on this sprite: eyes are 2x2 px each (one dark column, one white column), 5 px centre to centre, at rows 14-15; no nose pixel; mouth is a 3-px red mark; brows are not drawn separately (the hair fringe outline serves). These are one-sprite observations, not verified conventions for all Gen 3 trainers.
- Limb/clothing separation on this sprite is done with a mix: tinted dark outlines on skin and hair, black on gloves, shoes and ball, and value steps inside clothes (red 2 tones, green 2 tones).
- Pokemon sprites: nothing I could cite compares them structurally to trainers beyond the shared 64x64 / 16-colour format. A trainer figure fills a much smaller share of the canvas (19.8% opaque coverage here) than a typical Pokemon front sprite; the latter claim is from memory, unverified.

### Gaps
- No source found for RSE (May/Brendan) vs FRLG (Red/Leaf) stylistic differences, head pixel sizes, face conventions, gym leader pose rules. Would need Spriters Resource sheets or Bulbapedia sprite pages, which were not reachable.
- Gen 2 trainer sprite size (commonly said to be 56x56) and Gen 4 trainer size (80x80) are not verified for trainers specifically; only Pokemon canvases were found.
- The "much taller" back-image description (Data Crystal) vs 64x64 per frame (decomp wiki) are reconcilable only if back pics are stacked frames; I did not verify the stacked dimensions.
- The "32x48 per sprite" claim for Red/Leaf in an itch.io thread is a user statement of unclear scope; unverified, do not rely on it.

## Part B - Readability principles and implementable metrics

### Takeaway
Tutorial sources agree on: value (lightness) contrast beats hue, silhouette must read first, avoid orphan pixels and irregular stair-steps, avoid banding. None gives numeric thresholds, and I found no published automatic pixel-art quality metric; the formulas below are my proposals, with targets calibrated only against the one May sprite in Part C.

### Cited Findings
- Readability depends mainly on lightness differences; test by converting to greyscale; limited palettes read more clearly. — [Wayline colour lesson](https://www.wayline.io/learn/color-palettes/1), summary via [search results](https://www.wayline.io/learn/pixel-art)
- Silhouette test: fill the sprite with one colour and see if it still reads; start a head from a 6x6 block with shaved corners. — [PixNote glossary](https://pixnote.net/en/learn/glossary), [16 by 16 pixel art guide](https://geosirius.ifz.ru/16-16-pixel-art)
- Prefer clusters over isolated pixels; avoid banding (parallel strips of shade colours following an outline). — [PixNote glossary](https://pixnote.net/en/learn/glossary)
- Jaggies = uneven stair-step run lengths (for example 1,3,1 instead of a regular 2:1 pattern); "doubles" (extra pixel thickening a 1 px line) and orphan pixels should be removed. Workflow: block shape, even out outline steps, remove doubles, fix orphans. — [Wayline pixel art lesson 2](https://www.wayline.io/learn/pixel-art/1); also [Divoom](https://divoom.com/blogs/setup-ideas/fix-jaggies-pixel-art-without-blur) (irregular 2:1 / 3:1 alternation looks worse than regular steps)
- One guide recommends value steps instead of black outlines (black borders vanish on dark backgrounds); another recommends one clean outer silhouette with interior forms suggested by value. — [Clip Studio / GamineAI search summaries](https://gamineai.com/blog/10-pixel-art-composition-rules-readability-in-game-2026)
- A TU Delft thesis ("Pixel Fixer") targets banding and pillow shading with an error metric counting problem pixel pairs; fetch failed so details are unread. — [TU Delft repository](https://repository.tudelft.nl/file/File_65d43acd-9779-4eab-999b-9bcd4f0a96a9)
- The Derek Yu tutorial exists (10-step, reworked at derekyu.com) but no readability passage was retrieved. — [GBGames note](https://gbgames.com/2019/12/19/derek-yus-updated-pixel-art-tutorial)

### Inferences - proposed metrics
Notation: M = opaque mask, c(p) = palette colour of pixel p, L*(.) = CIE L* from sRGB (D65, linearise, Y -> L*). N4/N8 = 4/8 neighbours. Values in brackets are measured on the May sprite (Part C) and are the only calibration.

1. Silhouette fill ratio = |M| / (bbox w * bbox h). [0.40] Also canvas coverage = |M|/(W*H) [0.198] and height fraction = bbox h / H [0.86]. Target for a full-body trainer: height fraction roughly 0.8-0.9 (one sample).
2. Silhouette minimum thickness = |M| minus |opening(M, 2x2)|, and the same with 3x3. Zero is ideal for 2x2. [5 px and 27 px]. Read this as "limbs and hair are at least 2 px thick except a few tips".
3. Silhouette connectivity = number of 8-connected components of M. [1]. Flag floating bits.
4. Orphan pixels (8-neighbour) = count of p in M with no N8 neighbour of the same colour; report as a rate over |M|. [112 = 13.8%]. 4-neighbour orphan rate [211 = 26.0%]. Caveat: Gen 3 art tolerates shading orphans, so target is relative (compare against reference sprites), not zero.
5. Colour-region fragmentation = number of 4-connected same-colour regions, and share of regions of size <= 2 px. [358 regions; 277 (77%) are <= 2 px]. High because outlines and one-pixel highlights are separate regions; use per-region-class, not globally.
6. Thin-stroke fraction = share of pixels not covered by a 2x2 same-colour block. [634/810 = 78%]. Not discriminating for outlined sprites (outlines are 1 px by design); apply it only to non-outline colours, or only to the silhouette (metric 2).
7. Outline continuity = for boundary pixels B = {p in M with an N4 neighbour outside M}, share that are "dark" (L* below a threshold, e.g. 45). [222/249 = 89%]. Report also share of boundary run length that is unoutlined.
8. Adjacent-region lightness contrast: over all N4 pairs with different colours, dL = |L*a - L*b|; report min, and share below 5, 10, 15, 20. [921 colour-change edges; 1.3% < 5; 11.4% < 10; 15.1% < 15; 34.1% < 20]. Suggested flag: any boundary between *semantically different* parts (skin vs cloth, hair vs face, eye vs skin) with dL < 10. Low-dL edges inside one material (shading steps) can be fine.
9. Tone ladder per hue family: bucket colours by hue (or by ground-truth material), sort by L*, report count and consecutive steps. [skin 3 tones, steps 18.1 and 10.0; red 2, step 14.9; green 2, step 21.9]. Target from this sample: 2-3 tones per material, consecutive step >= about 10 L*.
10. Eye size and contrast: connected blob of eye colours; report area and dL(eye dark, skin) and dL(eye white, skin). [2x2 each; white vs skin dL = 9.0, dark vs skin large]. Target: eye >= 2x2 px and darkest eye pixel at least about 40 L* below skin.
11. Eye symmetry error: after matching the two eye blobs, count differing pixels in the aligned 2x2 / 3x3 window (and, for 3/4 views, compare against translation instead of mirroring). [translation: left (dark col x25, white col x26) vs right (dark col x30, white col x31) differ only in which dark pixel is darker: 2 of 4 pixels by colour index].
12. Mirror symmetry of silhouette: IoU between M and its reflection about the best vertical axis. [head rows 5-20: 0.757 at axis x=27; full figure 0.523]. Use for head and for frontal poses only.
13. Dither/checker detector: count 2x2 windows with pattern ABBA on the diagonal and checkerboard fields. [4 isolated windows; 0 fields: no dithering].
14. Banding detector (proposed): for each outline-adjacent run of a shade colour parallel to the outline for >= 6 px with constant offset 1. Not measured here.
15. Jaggy score (proposed): for each boundary chain, compute run-lengths of the step pattern and report the share of triples where max(run)/min(run) > 2 or where adjacent runs alternate non-monotonically. Not measured here.
16. Squint test: downscale the 64x64 sprite by 2x and 4x (box filter) and compare recognition against the original (e.g. SSIM of L* at same size after up-resampling, or silhouette IoU with the unblurred mask). Not measured; no source gives a number.

### Gaps
- No published numeric thresholds for orphan counts, minimum contrast or minimum feature size in any source I could read. All targets above are proposals or single-sample measurements.
- No source found for Slynyrd, Saint11, MortMort or AdamCYounis guidance (searches returned none); no academic perceptual metric for tiny sprites found. TU Delft thesis details unread.
- A perceptual standard such as WCAG contrast (ratio >= 3:1 for graphics) is a plausible anchor for icon legibility but I did not retrieve it; treat as unverified.

## Part C - Empirical measurements: C:/Users/Jarrid/Downloads/example.png

### Takeaway
It is a genuine-looking Gen 3 style May front sprite (visual check at 8x: pigtails under a white/green bandana, red sleeveless top, black gloves, holding a poke ball in the viewer-left hand). 64x64 RGBA, binary alpha, 15 opaque colours (16 with transparency), 810 opaque pixels, a single connected silhouette.

### Cited Findings
Method: scripts in `C:\Projects\sprite-descaler\research_notes\Gen 3 Pokemon sprite techniques\scratch\` (`measure.py`, `analyze2.py`; `preview8x.png` is the 8x view). Run with `C:\Users\Jarrid\AppData\Local\Programs\Python\Python312\python.exe` WITHOUT `-I`: numpy/Pillow/scipy live in the user site-packages, which `-I` disables, and the `python` on the Git Bash PATH has no numpy. The file was only read.

Key numbers

| Metric | Result | How computed |
|---|---|---|
| Image | 64x64, RGBA, alpha only {0,255} | Pillow |
| Opaque pixels | 810 (19.8% of canvas) | alpha > 0 |
| Distinct opaque colours | 15 (+ transparent = 16) | unique RGB over M |
| Bounding box | x 9-45, y 5-59; 37 w x 55 h | min/max of M |
| Margins L / R / T / B | 9 / 18 / 5 / 4 px | from bbox |
| Height / bbox fill | 86% of canvas height; bbox fill 39.8% | |
| Silhouette components | 1 (8-connected) | scipy.ndimage.label |
| Boundary pixels (N4 neighbour outside M) | 249 = 30.7% of opaque | |
| Boundary colours | #000000 97 (39.0%), #7b5952 57, #4a3039 47, #293842 13, #636173 8, unoutlined fills 27 (#ce8273 14, #dea294 6, #639a5a 5, #c64142 1, #cecbde 1) | |
| Dark (L* < 45) share of boundary | 222/249 = 89%; of which pure black 39%, tinted dark 50% (brown #7b5952, plum #4a3039, blue-grey #293842, grey-violet #636173) | |
| Black pixels total | 123 = 15.2% of opaque (97 on boundary, 26 interior) | |
| Dark-coloured pixels total (L* < 45; includes shading) | 419 = 51.7% (upper bound for "outline fraction"; #7b5952 and #636173 are also fills) | |
| 8-neighbour orphan pixels | 112 = 13.8% | no N8 pixel of same colour |
| 4-neighbour orphans | 211 = 26.0% | |
| Same-colour 4-connected regions | 358; 277 of size <= 2 | |
| Pixels not in any 2x2 same-colour block | 634 = 78% (outlines are 1 px by design) | morphological opening per colour |
| Silhouette pixels not in a 2x2 / 3x3 opaque block | 5 / 27 | opening of M |
| Colour-change edges (N4) | 921; dL < 5: 1.3%, < 10: 11.4%, < 20: 34.1% | CIE L*, D65 |
| Dithering | none: 0 checkerboard fields; 4 isolated diagonal 2x2 windows at (20,10), (29,24), (12,27), (23,31) | |
| Eyes | two 2x2 blobs: left x25-26, y14-15; right x30-31, y14-15; each = 1 dark col + 1 white col; centre spacing 5 px | blobs of {#000, #636173, #fffbff, #cecbde} in face box |
| Mouth | 3 px red (c64142/ff615a), (27,18),(28,18),(27,19) | |
| Nose / brows | no distinct nose or brow pixels found | visual + grid inspection |
| Hands | viewer-left glove + poke ball blob: 38 px, bbox about 8x7 (x9-16, y25-31; ball and glove merged); viewer-right glove: 28 px, bbox 8x5 (x38-45, y32-36); bare skin of left forearm/hand 29 px; right bare hand/wrist 12 px | connected blobs per colour set in boxes |
| Silhouette mirror IoU | head rows 5-20: 0.757 (axis x=27); full figure 0.523 (axis x=28) | best axis over reflections |

Colours by pixel count (hex, count, L*)
- #000000 123, 0.0
- #7b5952 119, 41.2
- #4a3039 79, 23.2
- #ffdbce 66, 90.0
- #636173 58, 41.9
- #ce8273 55, 61.9
- #dea294 50, 71.9
- #c64142 45, 47.2
- #a56952 40, 50.3
- #293842 40, 22.6
- #ff615a 39, 62.1
- #639a5a 31, 58.5
- #cecbde 27, 82.4
- #fffbff 20, 99.0
- #8cdb73 18, 80.4

Tone ladders (families assigned by hand from region inspection, L* descending; hue buckets alone would split brown skin/hair outline ambiguously)
- Skin: #ffdbce 90.0 > #dea294 71.9 > #ce8273 61.9 (steps 18.1, 10.0), 171 px; skin outline #7b5952 41.2 (step 20.7).
- Hair/brown: #a56952 50.3 > #7b5952 41.2 > #4a3039 23.2 (steps 9.2, 17.9), 238 px (hair outline is #4a3039).
- Red clothes/ball/mouth: #ff615a 62.1 > #c64142 47.2 (step 14.9), 84 px.
- Green bandana/belt/shoe trim: #8cdb73 80.4 > #639a5a 58.5 (step 21.9), 49 px.
- Neutrals (white bandana, gloves, shorts, socks, ball): #fffbff 99.0 > #cecbde 82.4 > #636173 41.9 > #293842 22.6 > #000000 0 (steps 16.6, 40.5, 19.3, 22.6), 268 px.

Lowest-contrast adjacent colour pairs (dL, count of edges): #293842/#4a3039 0.6 (4); #636173/#7b5952 0.7 (3); #8cdb73/#cecbde 2.0 (2); #639a5a/#ce8273 3.4 (2); #7b5952/#a56952 9.2 (35, hair-shadow vs hair); #ce8273/#dea294 10.0 (39, skin shade steps). The white of the eye (#fffbff) against light skin (#ffdbce) is only about 9 L*.

### Inferences
- Outlines are selective, not uniform: black only on gloves, shoes, ball and shorts; tinted dark brown/plum on skin and hair. Only about 11% of the silhouette boundary has no dark outline (mostly skin edges, bandana tie).
- High orphan and small-region counts (13.8% / 277 tiny regions) show real Gen 3 sprites are textured by 1-px highlights and shading flecks (hair, shorts, hands); an "orphan = defect" rule would wrongly flag this reference, so use it as a comparison metric or restrict to the silhouette boundary.
- Silhouette is clean: single component, only 5 px not in 2x2 blocks. The detail lives inside, the contour is chunky.
- Faces are tiny: two 2x2 eyes, one 3-px mouth, no nose, within roughly a 7 px wide skin area; legibility comes from the eye dark/white contrast and the dark outline around the face, not from feature size.
- No dithering: shading is by hard 2-3 tone steps with L* steps of 9-22 between neighbours in a ladder.
- Palette-limit match: 15 colours + transparent is exactly the 4bpp palette; any generated/descaled candidate exceeding 15 opaque colours cannot be a valid Gen 3 trainer.
- Hand area measures are approximate because glove, ball and skin are separate colour sets and I did not hand-segment ball vs glove.

### Gaps
- Single sample: no basis for variance or percentile targets across Gen 3 trainers. A calibration run on Red, Leaf, Brendan and gym leader sprites would be needed.
- Symmetry of eyes was assessed by translation of the 2x2 pattern; dark pixels differ (#636173 top-left vs #000000 bottom-left in the left eye, reversed in the right). I did not verify whether this is deliberate shading in the original game art.
- I did not verify that the file is an unmodified ROM extraction (alpha is clean binary, 16-colour limit holds, which is consistent with, not proof of, authenticity).
