# Gen 3 Pokemon sprite color, shading ramps and palette budgeting

## Method and provenance (read first)

Most numbers below were measured by me, not quoted from articles. Web searches found no published analysis of Gen 3 sprite shading, so the measured data is the main evidence.

- Source files: `https://raw.githubusercontent.com/pret/pokeemerald/master/graphics/pokemon/<name>/normal.pal` and `front.png` for pikachu, charmander, charizard, bulbasaur, treecko, mudkip, gardevoir, snorlax. Only `normal.pal` was used for gengar and magikarp. Palette index 0 is the transparent slot and is not drawn.
- The .pal files are JASC-PAL, 16 entries each. Entry 0 is the backdrop, which shows as #cdcdb4, #d5d5bd and similar. I excluded it. Entries 255,0,255 are unused.
- Computation, with Python and Pillow (scripts in the scratchpad, `an.py`, `use.py`, `cen.py`):
  - HSV from `colorsys`. Y is Rec.709 luma on raw 0-255 values.
  - Per-index pixel share is the percentage of non-transparent pixels in `front.png` (64x64 indexed).
  - "On BG edge" is the share of that index's pixels that touch a transparent pixel in a 4-neighbourhood.
  - Light direction: for each sprite I took the centroid of hand-picked "light" ramp indices minus the centroid of "shade" indices, normalised by the sprite bounding box. The index picks were my judgement from the palette order and luma, so it is a rough check.
- Sample size is 8 to 10 Pokemon, all from pokeemerald. Treat percentages as illustrative, not as population statistics.
- I did not inspect pokefirered, but FRLG reuses the same artwork, so pokeemerald palettes should be representative. This is unverified.
- Comparisons to Gen 2 and Gen 4 come from general knowledge, not from fetched sources. They are flagged as unverified.

## 1. Palette budgeting: how the 15 colors are divided

### Takeaway
A sprite has one 16-color palette, with index 0 transparent, so 15 usable colors. Artists spend most of them on 2 to 4 material ramps of 3 to 5 tones each, plus one outline black. Eyes, teeth and shine share one or two spare slots.

### Cited Findings
- The hardware limit is 16 colors with one transparent slot. A Gen 3 sprite tool warns when a sheet has more than 15 non-transparent colors — [itch.io Gen 3 trainer tool, via search snippet](https://flinkerflitzer.itch.io/pokemon-gen-3-trainer)
- Palettes are shared across many Pokemon, so editing one affects every sprite that uses it — [PokeCommunity thread, via search snippet](https://www.pokecommunity.com/threads/change-pokemon-menu-sprite.405458/)
- Measured palettes (pret/pokeemerald normal.pal and front.png):

| Pokemon | Colors used | Ramps (tones) | Flat or accent colors | Black outline share |
|---|---|---|---|---|
| Pikachu | 11 | yellow 5 (#ffff7b, #ffee00, #eebd00, #c58b00, #835200), red cheek 3 (#ff4a4a, #e60000, #b40000) | white #ffffff (0.2%), grey #6a6a6a (2.5%) | #101010 = 13.2% |
| Charmander | 14 | orange 4 (#ffc562, #ff9441, #de5220, #943100), belly 3 (#ffe69c, #ffd56a, #e6ac5a) | #f69408 and #d54108 (flame/mouth, probably), green and blue bits 3, white | 8.3% |
| Bulbasaur | 14 | teal 4 (#83eec5, #62d5a4, #39947b, #184a4a), leaf green 4 (#bdff73, #9cd54a, #73ac31, #526229), red eye 3 (#ff6a62, #de4a41, #bd2920) | white, light grey #cdcdcd | 10.1% |
| Treecko | 15 | green 3 (#4abd83, #4a8b5a, #184139), leaf green 4 (same as Bulbasaur's), red belly 3 (#ff6a52, #d55239, #a44a31), yellow 3 (#ffd57b, #ffc552, #e69c4a) | white | 18.1% |
| Mudkip | 15 | blue 3 (#7bc5ff, #5aace6, #3183c5) plus indigo #4a4a83, cream-blue 4 (#c5cdff, #b4bdf6, #9cacde, #8b9cb4), orange 4 (#ffb452, #f69c41, #cd8341, #a47b5a) | grey #7b737b, white | 5.2% |
| Gardevoir | 14 | white-blue 4 (#eeeeff, #c5cdde, #a4b4cd, #8394b4), green hair 4 (#cdffac, #94e694, #73bd73, #317b4a), red 2 (#ff9c83, #e65239) | #7b5252 (1%), white | 9.6% |
| Snorlax | 15 | blue-grey 4 (#8b8bb4, #737394, #5a5a73, #41415a), cream 3 (#ffffcd, #f6f69c, #e6de94), olive #9c9c52, tan 3 (#eeac73, #d59c5a, #a46a29) | grey 2, white | 6.2% |

- Pikachu is a minimal case: one 5-tone yellow ramp, one 3-tone red, black, grey and white.
- Pixel share per tone in Pikachu's yellow: highlight 3.7%, base 35.8%, first shade 28.7%, second shade 5.2%, darkest 7.7%. The base and first shade carry the form, and the extremes are small accents or edges.
- Tone share follows the same shape in Charmander's orange: light #ffc562 4.7%, mid #ff9441 19.8%, shade #de5220 24.3%, dark #943100 16.3%. In Snorlax's cream: 8.0%, 19.7%, 14.4%.
- Evolution lines share ramps. Charmander and Charizard both use #ffe69c, #ffd56a, #ffc562, #ff9441 and #943100 (identical hex). Bulbasaur and Treecko share the identical leaf-green ramp #bdff73, #9cd54a, #73ac31, #526229. Pikachu, Charmander, Bulbasaur, Snorlax, Magikarp and others share the same backdrop entry at index 0.
- Colors repeat across species. Treecko's leaf-green ramp is identical to Bulbasaur's, so some palette entries may be ramp templates reused by the artists. This is inferred from hex equality only.
- All channel values sit on a 5-bit grid. Values such as 16, 74, 106, 123, 131, 139 and 205 show the 32-level-per-channel quantisation (15-bit color). A ramp step is a multiple of 8 on each channel at the smallest.

### Inferences
- A budgeting template for an algorithm: 1 outline black, 2 to 3 ramps of 3 to 4 tones (primary body, secondary body or belly, accent), 1 to 2 small flat accent colors, 1 white or off-white, and 1 neutral grey or dark accent for eyes and mouth. The sum comes to about 14 to 15.
- Material priority: the largest-area material gets 4 to 5 tones, secondary materials 3, and tiny features (eye color, tongue, gems) 1 to 2.
- Flat single colors in the sample: eye whites and shine (#ffffff), grey ear tips or teeth, one-off gems. Ramps are reserved for large surfaces.
- Parameter suggestion: split the budget as outline 1, primary 4 to 5, secondary 3 to 4, tertiary 3, spare 2 to 3.

### Gaps
- No large-scale survey (all 386 species) was run, so the "typical" counts come from 8 species.
- I did not identify which pixels carry each flat accent (tongue, eye, flame). Labels like "probably" are guesses from hue and position.

## 2. Shading model: light direction and shadow shape

### Takeaway
Light comes from the upper left, in every sampled sprite. Highlights sit in the upper-left interior and shadows sit lower-right with a darker rim along the lower and right silhouette. Shapes are flat, clustered bands, not smooth gradients.

### Cited Findings
- Measured light-minus-shade centroid offsets (normalised by bounding box, x negative = light to the left, y negative = light above). Source: my analysis of pret front.png files:
  - Pikachu (-0.14, -0.10)
  - Charmander (-0.22, -0.14)
  - Bulbasaur (-0.19, -0.03)
  - Mudkip (-0.16, -0.13)
  - Snorlax (-0.08, -0.30)
  - Gardevoir (-0.10, +0.03)
  - Charizard (-0.11, 0.00)
  - Treecko (-0.20, -0.26)
- Darkest ramp tones sit mostly on silhouette edges. Share of each pixel set that touches the transparent background:
  - Pikachu: #835200 57%, #c58b00 43%, base #ffee00 0%.
  - Charmander: #943100 50%, #d54108 58%.
  - Charizard: #943100 52%, #c53120 63%.
  - Bulbasaur: #184a4a 31%, #526229 31%.
  - Treecko: #526229 50%.
  - Brighter tones (highlight and base) are 0 to 5%, so they stay in the interior.
- Dithering existed but was rare for gradients, according to a one-line mention: "dithering-style shading" for complex gradients — [hub.bocatc.org, via search snippet](https://hub.bocatc.org/?p=37630). I could not verify this for Gen 3 sprites specifically.

### Inferences
- The model is: top-left key light, 3 to 5 flat bands, highlight as a small cluster on the upper-left of each volume, form shadow on the lower right, and the darkest ramp step used as a rim or "selective outline" on the lower and right edges. Because dark tones are 40 to 60% edge pixels, the outline and the darkest shade merge on the lit side.
- Rough rule for an algorithm: shade index by dot(normal, light) with light at about (-0.5, -0.5, 0.7), quantised to the tone count, then force the darkest tone onto edge pixels whose outward normal faces right or down.
- Gardevoir and Charizard show almost no vertical offset, probably because their forms (a dress, wings) are asymmetric, so treat a vertical component as weaker than the horizontal one. This is my inference.

### Gaps
- Centroid method is crude (I chose indices by hand) and sensitive to anatomy.
- I did not measure specular dots on gems and eyes beyond noting pure white is only 0.2 to 1.9% of pixels.
- Back sprites and the Emerald animated front sprites were not analysed.

## 3. Hue shifting and step sizes

### Takeaway
Gen 3 ramps usually do shift hue in the shadows, but direction depends on the material and is not uniform. Warm colors shift toward red, green and cyan-blue colors shift toward blue, and saturation rises toward the dark end. Neutral and cool materials (Snorlax, Gengar) stay at a fixed hue.

### Cited Findings (all measured: pret normal.pal, HSV with hue in degrees)
- Pikachu yellow, light to dark: H 60, 56, 48, 42, 38. Saturation 52, 100, 100, 100, 100. Value 100, 100, 93, 77, 51. Luma Y 245, 224, 186, 141, 86. Hue falls 4 to 8 degrees per step (toward orange and brown) while saturation stays at 100.
- Charmander orange, light to dark: H 38, 26, 16, 20. Saturation 62, 75, 86, 100. Y 202, 165, 108, 67. Strong shift toward red. Belly: H 45, 43, 35 with saturation 39, 58, 61.
- Bulbasaur teal: H 157, 154, 164, 180. Saturation 45, 54, 61, 68. Value 93, 84, 58, 29. Y 212, 185, 127, 63. Shadow shifts toward cyan and saturates.
- Bulbasaur leaf green: H 88, 85, 88, 77. Saturation 55, 65, 72, 58. Y 231, 191, 151, 90. Hue is nearly fixed, with the darkest step moving toward yellow-olive (opposite to the teal).
- Bulbasaur red: H 3 (fixed). Saturation 62, 71, 83. Y 137, 105, 72.
- Charizard wing blue: H 187, 193, 210. Saturation 78, 78, 77. Value 74, 58, 42. Shift toward blue-indigo. Red (#ee5241 to #c53120): H 6, saturation 73 to 84.
- Mudkip blue: H 206, 205, 207, then 240 for the darkest (#4a4a83). Saturation 52, 61, 75, 44. Y 185, 159, 118, 78. Hue is stable through three steps, then the darkest tone moves to indigo and is desaturated. It is used as an outline-like tone on the edge (58% on the background edge).
- Mudkip orange: H 34, 30, 28, 27. Saturation 68, 74, 68, 45. Y 189, 169, 142, 129. Shadow tone is desaturated brown.
- Gardevoir white-blue: H 240, 221, 217, 219. Saturation 7, 11, 20, 27. Value 100, 87, 80, 71. Y 239, 205, 178, 147. Luma steps about 34, 27, 31.
- Gardevoir green hair: H 96, 120, 120, 140. Saturation 33, 36, 39, 60. Y 238, 207, 168, 104. Hue goes yellow-green to cyan-green in the shade.
- Snorlax blue-grey: H 240 fixed, saturation 22 to 28, value 71, 58, 45, 35, Y 142, 117, 92, 67 (uniform step about 25). Cream: H 60, 60, 54, saturation 20, 37, 36 (Y 251, 240, 218), with an olive shadow #9c9c52.
- Gengar purple: H 315, 319, 307, 300. Saturation 34, 43, 50, 45. Y 149, 117, 83, 50 (uniform step about 33).
- Luma steps between adjacent tones across the sample are typically 25 to 45 (on a 0-255 scale), with the largest jumps between the base and first shadow tone. Examples: Pikachu 21, 38, 45, 55; Bulbasaur teal 27, 58, 64; Charmander 37, 57, 41.
- Value (HSV V) steps are typically 10 to 30 points, and saturation steps 5 to 15 points, with saturation rising toward the shadow in most warm and green ramps.

### Inferences
- Rule for an algorithm: per shadow step, shift hue 4 to 12 degrees toward the nearest "shadow pole" (red for warm colors, blue-cyan for greens and blues; toward 240 for neutrals), raise saturation 5 to 15 points, and drop luma 25 to 45. Highlights: hue goes toward yellow or white, saturation drops 10 to 20, luma up 15 to 40.
- Highlights shift less than shadows: Pikachu's highlight is #ffff7b (hue 60, a desaturated yellow), which is "toward white and yellow" rather than a different hue.
- Not all ramps shift: Bulbasaur's red and Snorlax's blue-grey hold hue constant. So hue shift should be a per-material parameter that can be zero.
- Cool shadow plus warm highlight is not universal. Warm materials get redder (still warm) in shadow, which is a "same-side" shift, not a complementary shift.

### Gaps
- No documented artist guidance for Gen 3 hue shifting. No GameFreak statement was found. Values above describe outcomes, not intent.
- Hue values for near-grey colors (saturation below 10) are noisy and should not be trusted.

## 4. Outline color versus fill

### Takeaway
There is one shared neutral outline black (#101010 = 16,16,16) in every sampled palette, plus a tinted dark tone of each ramp that works as a "selective outline" on the parts of the silhouette that touch a fill of that hue. The outline is separate from the darkest shade in most cases, but the two are close in value.

### Cited Findings
- #101010 appears in all 10 sampled palettes (Pikachu, Charmander, Charizard, Bulbasaur, Treecko, Mudkip, Gardevoir, Snorlax, Gengar, and Magikarp has it at index 5). It is not always the same index, but always the same value. Source: pret normal.pal.
- Share of non-transparent pixels in #101010: Pikachu 13.2%, Charmander 8.3%, Bulbasaur 10.1%, Treecko 18.1%, Mudkip 5.2%, Gardevoir 9.6%, Snorlax 6.2%, Charizard 10.7%. The share touching the background is 46 to 78% (Pikachu 70%, Charmander 78%, Treecko 77%, Gardevoir 76%). The remainder is inner lines (eyes, mouths, limb separations).
- Tinted dark tones used as an outline on parts of the sprite: Pikachu #835200 (57% on edge) and #c58b00 (43%); Charmander and Charizard #943100 (50 to 52%); Charizard #c53120 (63%); Bulbasaur #184a4a (31%) and #526229 (31%); Treecko #184139 (31%), #526229 (50%) and #e69c4a (62%); Mudkip #4a4a83 (58%), #7b737b (92%); Snorlax #41415a (51%), #6a6a73 (67%); Gardevoir #8394b4 (49%), #7b5252 (80%).
- Tinted dark outlines are roughly: warm brown (#835200, #943100) for yellow and orange areas; deep teal (#184a4a) for teal; indigo (#4a4a83) for blue; deep green (#184139, #526229) for greens.

### Inferences
- A two-tier outline is the pattern: black #101010 around the silhouette and facial details, and the ramp's darkest tint where the outline would be too heavy (lit edge, belly, light materials).
- For an algorithm: outline = near-black (16,16,16) as the default, replaced by the darkest ramp tone for edge pixels that border light fills (belly, cream, white fur). White and light-grey Pokemon (Gardevoir, Snorlax's face) get a blue-grey tinted edge in places.
- The darkest ramp tone is not the outline. In Pikachu there are 5 yellow tones plus black, and the darkest (#835200, luma 86) is much lighter than black (luma 16). In Charmander the gap is 67 vs 16.

### Gaps
- Actual placement (which edges are black vs tinted) needs image inspection; my edge-share numbers do not say which parts of the body.
- I did not check FRLG-specific differences.

## 5. Whites, highlights, eyes, teeth

### Takeaway
Pure white (#ffffff) is rare (0.2 to 2% of pixels) and is spent on eye shine, teeth, claws and tiny highlights. Large white or pale surfaces use a cool, slightly blue off-white ramp.

### Cited Findings (measured)
- White shares: Pikachu 0.2%, Charmander 1.3%, Bulbasaur 1.9%, Treecko 0.2%, Mudkip 0.2%, Gardevoir 0.2% (only #ffffff itself), Snorlax 1.5%, Charizard 1.0%.
- White-body material is not white. Gardevoir's body uses #eeeeff (27% of pixels), #c5cdde (17.5%), #a4b4cd (2.8%) and #8394b4 (6.6%), a blue-tinted ramp with saturation 7 to 27.
- Mudkip's pale face and belly: #c5cdff, #b4bdf6, #9cacde, #8b9cb4, also blue-violet (hue 215 to 232).
- Snorlax's face and belly is cream, #ffffcd, #f6f69c, #e6de94, with an olive-yellow shade (#9c9c52). Snorlax's grey tones #d5d5de and #6a6a73 are near-neutral (saturation 4 to 8).
- Gengar has three neutral greys (#ffffff, #dedede, #d5d5d5, #7b7b7b) for eyes and teeth.
- Magikarp's whites: #ffffff, #dedee6, #acacbd, #73738b: a blue-grey ramp of 4 for the whisker and belly.
- Pikachu's #6a6a6a (2.5%) is a neutral mid-grey. The role (likely ear tips or eye shading) is unverified.

### Inferences
- For an algorithm: keep #ffffff for 1 to 3 pixel highlight clusters (eye shine, teeth, claws) and give broad white surfaces a 3 to 4 tone cool ramp (hue about 215 to 240, saturation 7 to 27, luma about 240, 205, 178, 147).
- Cream and warm whites (Snorlax) shift toward olive-yellow in the shadow rather than gray.

### Gaps
- No direct data on eye construction (pupil, iris, shine layout). A pixel-level inspection of the eyes would be needed.

## 6. What makes the Gen 3 look; comparison with Gen 2 and Gen 4

### Takeaway
Gen 3 palettes are highly saturated, with many tones at 100% saturation or value, strong luma steps, and a near-black outline. This is consistent with colors made for a dim screen. The Gen 2 and Gen 4 comparisons are from general knowledge and not verified here.

### Cited Findings
- Measured saturation and value: Pikachu's yellow ramp has S=100 in four of five tones. Charmander's orange reaches S=100 in the darkest tone. Value is 100 for the highlight in nearly every ramp. Source: pret normal.pal.
- Outline #101010 has luma 16 (about 6% value), so the full contrast range per sprite is nearly 16 to 255.
- The 5-bit quantisation (32 levels per channel) restricts ramp subtlety to steps of at least 8 per channel.
- Gen 2: Game Boy Color sprites use 4 colors (shades) per sprite and Gen 4 uses larger palettes and richer shading. This is background knowledge, not verified in this research.

### Inferences
- The "Gen 3 look" in color terms: (1) near-black neutral outline, (2) 3 to 5 tone ramps with big luma steps, (3) fully saturated mid-tones, (4) hue-shifted shadows, (5) tinted selective outlines, (6) flat band shading with an upper-left light.
- For an algorithm: use a high saturation target (60 to 100% in mid-tones for characters with strong color), and keep neutral greys rare.

### Gaps
- Gen 2 and Gen 4 palettes were not fetched, so the comparison cannot be quantified.

## 7. GBA screen effect and palette compensation

### Takeaway
Credible emulator-author sources say the original GBA LCD was washed out and developers exaggerated colors to compensate. I found no Pokemon-specific documentation, and I could not confirm the claim for these sprites.

### Cited Findings
- "The Game Boy Advance has one of the worst LCD screens, with colors that are completely washed out." "Clever developers found that by greatly exaggerating the colors, they could produce better results on the real hardware." On a PC monitor this gives "a technicolor nightmare." The article models the LCD with an input gamma of 4.0 and an output gamma of 2.2 — [near.sh color emulation article (archived by ares)](https://archive.ares-emu.net/near.sh/articles/video/color-emulation.html)
- Pokefan531 measured profiles for each GBA display, widely used in emulators; the usual correction model is input gamma, 3x3 matrix, output gamma — [libretro forum, Real GBA and DS-Phat colors](https://forums.libretro.com/t/real-gba-and-ds-phat-colors/1540)
- Forum note that late GBA games (about 2006) may have been built for more sRGB-like output (GBA SP and DS Lite) while most are based on the original color space — [libretro forum (same thread, anecdotal)](https://forums.libretro.com/t/real-gba-and-ds-phat-colors/1540/269)
- A PokeBase answer speculates that some Gen 3 recolors exploited the GBA's better color display; labeled a guess — [PokeBase](https://pokemondb.net/pokebase/309046/why-shiny-pichu-is-orange-in-gsc)

### Inferences
- The measured saturation (many S=100 and V=100 tones) fits the compensation story, but it also fits a stylistic choice. It is not proof.
- Practical implication for an algorithm: if outputs are displayed on a modern sRGB screen, Gen 3 values already look vivid there. A faithful "Gen 3 look" does not need extra saturation boost, and may use values as-is. Applying a GBA-style gamma/darkening correction is an optional display step.

### Gaps
- No documented palette convention from the artists. No source ties specific Pokemon palette choices to screen compensation.

## 8. Worked example summary (for parameters)

### Takeaway
Typical ramp recipe from the measured data: 4 tones per primary material, luma about 230 / 190 / 130 / 70 for saturated colors, with the darkest tone also used as a tinted edge.

### Cited Findings
- Charmander orange: #ffc562 (Y 202), #ff9441 (165), #de5220 (108), #943100 (67).
- Bulbasaur teal: #83eec5 (212), #62d5a4 (185), #39947b (127), #184a4a (63).
- Gardevoir hair: #cdffac (238), #94e694 (207), #73bd73 (168), #317b4a (104).
- Mudkip blue: #7bc5ff (185), #5aace6 (159), #3183c5 (118), #4a4a83 (78).
- Pikachu yellow: #ffff7b (245), #ffee00 (224), #eebd00 (186), #c58b00 (141), #835200 (86).
- Black outline in every sampled palette: #101010 (16).
- Source for all: pret/pokeemerald graphics/pokemon/<name>/normal.pal.

### Inferences
- Four-tone luma targets of roughly 200-240, 160-190, 105-130, 60-85 reproduce the observed ramps, with outline at 16.

### Gaps
- The ramps are measured from the front palette. Back sprites and shiny palettes share or recolor them and were not analysed.
