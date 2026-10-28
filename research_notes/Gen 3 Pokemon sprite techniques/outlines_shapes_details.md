# Gen 3 Pokemon sprites: outlines, silhouettes and interior details

Method note. Web search returned almost no rigorous analysis of Gen 3 sprite technique. Bulbapedia and Pokecommunity threads returned HTTP 403. Pokebip's sprite-norms page covers only Gen 1/2 and says nothing about Gen 3 outlines. So the main evidence here is my own pixel analysis of the real sprites, using the PokeAPI sprite repo (https://github.com/PokeAPI/sprites, folders sprites/pokemon/versions/generation-iii/{emerald,firered-leafgreen,ruby-sapphire}). The sample was 16 Pokemon: Bulbasaur, Venusaur, Charizard, Blastoise, Pikachu, Gengar, Gyarados, Snorlax, Mewtwo, Pichu, Elekid, Sceptile, Mudkip, Marshtomp, Swampert, Gardevoir. I also viewed a 6x contact sheet of Pikachu, Pichu, Charizard, Blaziken, Gardevoir, Mudkip, Swampert and Gengar. Items tagged [MEASURED] are numbers I computed. Items tagged [VISUAL] are from looking at the 6x zoom. Items tagged [UNVERIFIED] are general pixel-art knowledge or inference with no Gen 3-specific source. The sample is small and was picked for being well-known, not randomly. I sampled only Emerald, FRLG and RS front sprites. The three games' front sprites for these 16 were near-identical except FRLG recolors (see Gaps).

Edge definition used below: an opaque pixel with at least one transparent 4-neighbour. "Dark" means luminance < 50.

---

## Q1. Outlines: color, thickness, pixel-perfect technique, breaks

### Takeaway
Gen 3 outlines are a single shared near-black (RGB 16,16,16) used for roughly 21-75% of the silhouette edge. The rest of the edge is selective outlining: a dark, saturated shade of the adjacent body color. Lines are 1px thick. Pure black is not used (except an oddity in Gyarados), and highlight-facing edges are lightly outlined or left unoutlined.

### Cited Findings
- Palette budget: every sprite is 64x64 with at most 15 opaque colors (+ transparent). Measured opaque color counts ranged 10-15 across the 16 sample sprites. Max was 15 in Venusaur, Charizard (RS/E), Blastoise, Gyarados, Snorlax, Mudkip and Swampert. — [PokeAPI sprites repo](https://github.com/PokeAPI/sprites) [MEASURED]
- The GBA palette is 16 entries with entry 0 transparent. A Pokecommunity thread on editing FireRed intro sprites says the palette should total 16 or 32 colors. — [PokeCommunity](https://www.pokecommunity.com/threads/firered-how-to-edit-the-intro-sprites.458026) (search snippet only; page not fully read)
- A Top Down Sprite Maker "Gen 3 Trainer" style warns if more than 15 non-transparent colors are used and snaps to 15-bit color. That is consistent with the 15+1 constraint. — [itch.io page](https://flinkerflitzer.itch.io/pokemon-gen-3-trainer) (search snippet only)
- The shared outline color is RGB (16,16,16), not (0,0,0). It is the darkest color in 15 of the 16 sampled sprites, with Gyarados as the exception [MEASURED]. A Gyarados difference of that size is odd and I did not investigate it. It is likely a palette quirk. [UNVERIFIED cause]. The 16 comes from the GBA 5-bit channel (2/31 ≈ 16/255). That is [UNVERIFIED] arithmetic reasoning.
- Share of edge pixels that are dark (lum<50), Emerald [MEASURED]. This is a rough proxy for "how black-outlined is it".
  - Pichu 0.75 (the (16,16,16) share alone is 0.75 of edge pixels)
  - Marshtomp 0.74
  - Sceptile 0.64
  - Swampert 0.59
  - Pikachu 0.55
  - Elekid 0.53
  - Gardevoir 0.47
  - Snorlax 0.43
  - Venusaur 0.40
  - Blastoise 0.40
  - Mewtwo 0.40
  - Gengar 0.38
  - Charizard 0.36
  - Bulbasaur 0.34
  - Gyarados 0.30
  - Mudkip 0.21
  So there is no single fixed rule. Small or compact yellow designs (Pichu, Pikachu, Elekid) are mostly near-black outlined. Large or colorful designs (Charizard, Mudkip, Gyarados, Bulbasaur) are heavily selective.
- Selective outlining examples [MEASURED edge-color histograms, Emerald]:
  - Charizard: most common edge color is dark orange-brown (148,49,0) at 44% of the edge; near-black is 36%. Wings and body edges use the brown, while mouth, claws and feet use near-black. [VISUAL] matches.
  - Mudkip: the most common edge color is dark blue-purple (74,74,131) at 28%; near-black only 21%. The tail fin and much of the body have no black outline. [VISUAL]
  - Gengar: dark purple (74,41,74) 40% (RS/E) vs black 38%. In FRLG the same sprite has black 61%, purple 26%, so FRLG versions differ from RS/E in outline policy for Gengar. [MEASURED]
  - Gyarados: dark blue-violet (65,65,106) 43% in RS/E (57,57,98) in FRLG, black only 30%/21%.
  - Blastoise: black 40%, dark blue-violet (74,74,131) 27%, brown 14% on the shell.
  - Pikachu: black 55%; dark brown (131,82,0) 26%; mid yellow-orange (197,139,0) 13%; bright yellow (238,189,0) 6%.
  - Gardevoir: black 47%; dark green (49,123,74) 22% on hair/dress; blue-gray (131,148,180) 20% on the white dress; red-brown 5%.
  - Rule shape: selective outline colors are 2-3 darker steps down the ramp of the neighboring fill. They share hue with the fill, never an unrelated hue, and are usually among the darkest 2 ramp entries of that color. [MEASURED + VISUAL]
- Palette-sharing implication: because the budget is 15, the selective-outline colors are usually the *shadow* color of the same ramp as the fill (e.g. Pikachu's (131,82,0) is used both as outline and shadow fill). I did not count exactly how often each outline color is reused for interior shading, but in the Pikachu ASCII dump the brown and mid-brown appear on both the silhouette edge and the interior shadow side. [VISUAL, one sprite]
- Thickness: outlines are 1px. Edge pixels in the pikachu dump show a single-pixel boundary line. Thick dark areas (Pikachu ear tips, Pichu ears) are filled shapes, not thick outlines. [VISUAL]
- Pixel-perfect technique: I counted "redundant L corners". These are edge pixels with an orthogonal neighbour on each of two axes on the edge ring and an interior diagonal fill that would make the line double-thick. Result: 0-0.07 of the edge. Medians are about 0.01. Highest: Gyarados 0.07, Gengar 0.06, Venusaur/Blastoise/Mudkip/Elekid 0.03. [MEASURED]. In plain terms, Gen 3 lines are almost always clean 1px lines with stair-steps and very few doubled L-joints. The few cases are on thick curves like Gyarados body coils and Gengar's spikes. Metric is crude, with false positives on 2px-wide features such as ear tips. [caveat]
- Curves and diagonals: [VISUAL] Diagonals mostly follow 1-1 and 2-1 / 3-1 stair patterns, with run lengths changing smoothly along a curve (e.g. Swampert's head fin, Snorlax belly). I did not measure the run-length statistics. [UNVERIFIED as a measured claim]
- Broken or omitted outlines [MEASURED + VISUAL]:
  - Light-facing edges: edge_light (lum>150 on boundary) is 13% for Blastoise and Elekid, 10% for Mudkip, 6% for Pikachu/Pichu/Gardevoir, ~0 for Gengar, Snorlax and Sceptile. Blastoise's white/pale shell and belly edges, Mudkip's white-blue tail fin and Gardevoir's white dress sit directly against transparency with a pale gray-blue rim rather than a dark line.
  - Gardevoir's white dress uses a light blue-gray (131,148,180) edge and dark gray-green only at shadow side. [VISUAL + MEASURED]
  - Flame: Charizard's tail flame and Blaziken's leg flames use warm brown/orange and yellow edges. They are not outlined in black. [VISUAL]
  - Mudkip's tail fin and the Gardevoir train are the clearest examples of fully selective (colored) outlines on a pale part. [VISUAL]
- Palette-limited consequence: a hard (0,0,0)-style outline is not used; (16,16,16) is. Same near-black also serves as eye pupil, mouth line, claw and gap color. [MEASURED palette + VISUAL]
- Compare: Platinum (Gen 4) 80x80 samples show the same pattern: Charizard dark edge 0.40 with brown (132,49,25) nearly equal to true black (0,0,0) at 204 vs 201 px; Pikachu black 98 vs brown 39. So selective outlining is a Gen 3-4 continuity. Gen 4 uses pure (0,0,0) in some sprites while Gen 3 uses (16,16,16). Gen 2 Crystal is 4 colors on a white box, so edge analysis is not meaningful. [MEASURED, small samples n=4 and n=3]
- General pixel-art guidance (not Gen 3-specific): pure black outlines can look harsh and "selout" changes the outline color according to the interior color. — [Search summary of a tutorial page](https://hub.bocatc.org/?p=37630) (low-quality aggregator; treat as general background only)
- A PokeCommunity post says outlines should contrast with surroundings, and this applies to interior lines such as eyes and mouth. — [PokeCommunity thread 461860](https://www.pokecommunity.com/threads/can-i-get-some-suggestions-how-to-do-gba-style-sprites-better-converting-non-pok%C3%A9mon-designs.461860) (search snippet only; full page 403; single forum post)

### Inferences
- Algorithm rule: outline = 1px, 4-connected-closed ring just inside the silhouette. Default color = near-black (16,16,16). Replace by "darkest ramp step of the adjacent fill" on (a) light-facing edges, (b) pale/white/yellow parts, (c) flames, fins, translucent/wing membranes. Target near-black share ≈ 35-60% of the edge, higher (≈ 55-75%) for small compact designs.
- Never use outline colors with a different hue from the fill unless it is the shared near-black. Reuse the ramp's shadow color for the outline to save palette slots.
- Where two same-colored parts touch, expect the rim to be darker (shadow ramp step) rather than near-black. I did not measure this; see Gaps.
- Remove L-corner doubles: after drawing the ring, delete the corner pixel of any orthogonal "L" where the diagonal neighbor is also on the ring.

### Gaps
- No text source explicitly states the (16,16,16) outline convention. It is purely from measurement.
- Not measured: stair-step run-length distribution; fraction of edge that is 4- vs 8-connected; whether interior contour lines use the same near-black.
- Gyarados (0,0,0) vs (16,16,16) discrepancy not explained.
- FRLG sprites are known to be different art from RS/E for some Pokemon (Gengar above, and recolors); this notes difference in outline policy but I did not systematically compare FRLG vs RS/E sprites.

---

## Q2. Interior separation, eyes, mouths, small features

### Takeaway
Interior parts are separated mostly by value steps in the same ramp, with near-black 1px lines only where an overlap would otherwise vanish (arm over belly, jaw, claw) or where the part is dark/pupil. Features are built from tiny blocks: eyes about 2x2 to 3x3 with a white shine pixel, mouths as 1px lines with a 1-3px tongue or teeth block.

### Cited Findings
- Region fragmentation [MEASURED]: counting 4-connected same-color regions, a typical Gen 3 sprite has far more tiny regions than large ones. Single-pixel regions per sprite: Pichu 74, Pikachu 142, Bulbasaur 124, Marshtomp 136, Gardevoir 212, Sceptile 370, Swampert 388, Venusaur 359. Regions ≥ 6 px are only 19-88 per sprite. This means many 1px accents (outline isolated pixels, highlights, fur flecks). Single pixels are common, but they are used as pixel-clusters of a continuous edge or texture, not random noise. Caveat: many "1px regions" are outline-edge fragments adjacent to a different-colored pixel; I did not separate those.
- Pikachu eye [MEASURED crop, Emerald]: about a 3-wide by 4-tall block of near-black with one white (255,255,255) pixel at the upper-left-center as shine, and a mid-gray (106,106,106) pixel at one corner to round it. A white pixel inside a dark eye is the shine. The grey pixel rounds a corner. Pichu's eyes follow the same recipe at similar size [VISUAL]. Other eyes: Charizard's eye is a tiny blue/white block [VISUAL]; Gardevoir's eye is a red/pink 2-3px dot with light surround [VISUAL]; Gengar's eyes are red-orange wedges with dark outline [VISUAL]; Swampert's eyes are yellow-orange 2-3px round shapes with a dark pupil [VISUAL]. So eye = dark outline + colored iris block + one light pixel, typically 2x2 to 3x3 for small Pokemon and up to roughly 4x3 for big ones. Eye size depends on the character; I did not measure systematically.
- Pikachu mouth: a 1px near-black line with a red/pink tongue block (dark red (180,0,0), red (230,0,0), light pink (255,74,74)) of ~3x2 px. Cheeks are 3x3-4x4 red blobs with a lighter pink highlight pixel (255,74,74) and darker (180,0,0) lower pixel. [MEASURED + VISUAL]
- Gengar's grin: a large dark rim with a row of white teeth as a 2-wide vertical block series (4-5 tooth blocks 2-3px wide separated by 1px dark gaps) [VISUAL]. Swampert and Charizard mouths: dark interior with pinkish tongue and a few white fang pixels [VISUAL].
- Arms/limbs vs torso: Charizard's arms and belly use near-black short contour segments plus a pale-belly color step; Swampert's arms and chest use dark-blue shadow lines and orange cuff bands. [VISUAL] Gardevoir's arm vs dress is separated by a dark red/gray 1px line and color change from skin-white to green. [VISUAL] Based on these, interior lines are used where a limb overlaps a body of similar value, and are drawn in the darkest ramp step of the part behind or in near-black. Where hue/value already differs (white belly vs orange body; Charizard belly), a color boundary alone is used. [VISUAL, 3-4 sprites]
- Emblems and stripes: Swampert's cheek fins and arm bands are 2-3px-wide colored blocks (orange/yellow) with a single dark pixel edge. Pikachu's back stripes in the Emerald sprite are dark brown 1px strokes grouped as short dashes on the back. Pichu's ear tips and tail are solid near-black shapes. [VISUAL]
- Claws and teeth: 1-2 px white or pale blocks (Charizard foot claws, Gengar teeth) set against dark gaps. [VISUAL]
- No source gives explicit "minimum feature size" numbers. Empirically, the smallest deliberate features are 1x1 (shine, nostril, tooth gap), with most readable features ≥ 2x2.

### Inferences
- Rule: choose line-vs-shade separation by luminance gap. If the gap between adjacent part fills is below approx one ramp step, insert a 1px interior line (darkest ramp step of the part behind, or near-black). If the gap is at least 2 steps, no line.
- Eye template: dark 1px contour around a 2x2 to 3x3 iris block, with 1 white pixel at the top-left. Add a grey corner pixel at 3x3 and larger for roundness.
- Mouths: 1px near-black line; add a 2-3px tongue/teeth block only when the original art shows an open mouth.
- Cheeks/emblems: ≥ 3x3 with 1 highlight and 1 shade pixel.

### Gaps
- No quantitative eye-size survey. Only a handful of eyes were inspected visually.
- No source on Gen 3 interior-line conventions other than my visual reading.

---

## Q3. Silhouette and simplification

### Takeaway
Gen 3 sprites keep the 64x64 silhouette bold and simple. Key features are exaggerated (ears, wing/fin shapes, horns), small details are merged into larger blocks, and the shapes are filled so each Pokemon stays identifiable as a flat silhouette. This section is mostly [VISUAL] and [UNVERIFIED] because I found no text source.

### Cited Findings
- Fixed canvas: all front sprites are 64x64 and typically occupy most of it. Opaque area: Pichu 502 px, Bulbasaur 732, Mudkip 852, Elekid 944, Pikachu 1082, Marshtomp 1348, Gardevoir 1525, Mewtwo 1625, Gengar 1911, Sceptile 2086, Gyarados 2125, Snorlax 2347, Charizard 2405, Venusaur 2441, Swampert 2643 (of 4096). [MEASURED]. Small Pokemon use ≈ 12-26% of the canvas, big ones up to ≈ 65%, so scale is relative but large designs are crammed.
- Exaggeration examples [VISUAL]: Pikachu's ears are tall near-black-tipped spikes, larger than in official art proportion; Pichu's ears are huge black-and-yellow triangles; Swampert's head fins are huge dark-blue vertical shapes; Charizard's wings fill the upper corners with orange membrane panels. Mudkip's central fin is a tall vertical dorsal shape that reads as the head silhouette.
- Merged details [VISUAL]: Pikachu's tail pattern, foot toes and hand fingers are 1-2 block shapes, not individual fingers. Charizard's belly plates are 2-3 pale bands. Gengar's body spikes are reduced to a few sawtooth triangles (about 3-5px wide) and the arm-fingers to 3 nubs.
- Poses: Gen 3 front sprites are posed and tilted for readability (Pikachu with one arm raised, Gardevoir leaning, Charizard roaring). The silhouette is not a straight-on official-art copy. [VISUAL]
- Gen 4 (80x80) uses larger canvases and slightly more interior detail for the same designs. [VISUAL, limited]. I did not verify other Gen 3/4 differences.

### Inferences
- Algorithm: when downscaling, preserve silhouette area at the extremities (ear tips, horns, tail tips, fin tips) by min-width rules: any protrusion should be at least 2px wide at its base and at least 3px long, otherwise either widen to 2px or drop it. Prefer fewer, bigger protrusions over many small ones.
- Fill concavities narrower than 1px (single-pixel gaps between limbs and body) unless the gap is a defining negative-space feature.
- Hard-merge detail clusters: 3+ toes/fingers become 2-3 nubs; spike rows keep alternating 1-2 px triangular teeth.

### Gaps
- No text source or developer statement found about Gen 3 silhouette priorities. All claims in this section rest on my visual reading of a few sprites and are not independently verified.
- Gen 3 sprites were painted by hand from official art; exact sprite-artist workflow is [UNVERIFIED].

---

## Q4. Texture handling (fur, scales, flame, water, metal, dither)

### Takeaway
Gen 3 does use ordered 2x2 checkerboard dithering, but sparingly and mostly in mid-tone transitions on large smooth regions (wing membranes, big bodies, fur highlights). It is not heavy. Small compact designs have near zero dither. The 15-color budget forces dither to substitute for extra ramp steps. This corrects the common claim that Gen 3 avoids dithering.

### Cited Findings
- 2x2 checkerboard block counts per sprite (Emerald) [MEASURED]: Venusaur 92, Charizard 87, Swampert 59, Gyarados 47, Sceptile 36, Gardevoir 34, Blastoise 29, Mudkip 26, Gengar 22, Marshtomp 18, Mewtwo 17, Bulbasaur 16, Snorlax 15, Pikachu 6, Elekid 5, Pichu 4. Each match is a 2x2 window with an alternating A/B pattern. Ordered dither appears on the larger Pokemon and is almost absent on the small ones. Large sprites use up to a few dozen dithered 2x2 blocks, which is small compared to an area of 2000+ px.
- Visual locations [VISUAL]: Charizard's wing membranes (teal) have a clear checker dither between two blue-teal values; Gengar has a light checker dither on the body highlight and the spots; Gardevoir's white dress has a checker transition in the highlight/shade; Venusaur's flower and back have dither patches. Dither is applied across a boundary between two adjacent ramp steps, 1-2 rows wide, rather than as a full gradient fill.
- Fur/fluff: Pikachu and Pichu use a pixel-jagged edge (alternating 1px steps) with the brighter fill pixel on top and a brown selective rim, not dither. Snorlax uses clusters of light/dark pixel flecks on belly and fur [VISUAL; MEASURED regions: 154 single-pixel regions].
- Scales/skin: Charizard/Swampert use a color step plus short 1-2px dark strokes rather than scale drawing. Sceptile's leaves and body use ramp bands. [VISUAL]
- Flame: Charizard and Blaziken flames use 3-4 color ramps (dark red/orange/orange/pale yellow) in tapering shapes, with no black outline. Blaziken's leg flames fade from orange to cream in vertical streaks with jagged tips. [VISUAL]
- Water/fins: Mudkip's and Swampert's fins use 2-3 light/mid blues, and Mudkip's tail fin is pale with a violet-gray selective edge. [VISUAL]
- Metal/armor: not sampled (no Steelix/Metagross check), a gap.
- Gen 4 contrast: Gen 4 80x80 sprites seem to use more dither and finer gradients; I did not measure. [UNVERIFIED]

### Inferences
- Algorithm: allow checker dither only at the boundary of two adjacent ramp steps, 1-2 px band width, on regions larger than ≈ 8x8 px, with a budget around 1-4% of opaque pixels (Charizard: 87 blocks ≈ 4% by 2x2-window count, though windows overlap so true share is lower). Disable it on small sprites (< ≈ 1100 px) and on edges.
- For fur, prefer edge jaggedness (alternating 1-2px steps) plus a selout rim over dither.
- For flames and glows, use 3-4 step ramps with directional tapering, no near-black outline.

### Gaps
- Checkerboard counts overlap (windows), so they overestimate coverage. Actual dithered-pixel percentage not computed.
- No source on dither policy beyond my own measurement; no metal/stone/gem texture check.

---

## Q5. Concrete examples worth citing

### Takeaway
Use these as reference sprites (Emerald art; PokeAPI sprite folder above). All findings are [MEASURED] or [VISUAL] from my own review.

### Cited Findings
- Pikachu (#25): 11 colors; near-black outline 55% plus dark-brown selout 26%; huge black ear tips; 3x4 eye with 1 white shine and gray rounding pixel; 1px mouth with red tongue; red cheek 3x3 with highlight. Almost no dither (6 blocks). Wide, low-detail, high-contrast fill.
- Pichu (#172): 12 colors, 502 px. Near-black on 75% of edge, giant black ears, solid black tail tip, almost no dither (4 blocks). Maximum simplification.
- Elekid (#239): 12 colors; 53% near-black edge; pale (lum>150) edge on 13% of boundary where yellow meets transparency.
- Charizard (#6): 14-15 colors; orange-brown selout 44% vs near-black 36%; checker-dithered wings, flame on tail with no outline; shows how a big design is split between black (mouth, claws, feet, wing ribs) and brown selout (body, wing edge).
- Mudkip (#258): 15 colors; only 21% near-black edge; tail fin and body use blue-violet (74,74,131) selout; tail fin is pale.
- Marshtomp (#259) and Swampert (#260): near-black edges 74% and 59%; orange accents (cheek fins, wrist bands, belly detail) with 2-3px blocks; Swampert's head fins are exaggerated.
- Sceptile (#254): near-black edge 64%; dark-green selout 17%; strongly defined blade/leaf shapes.
- Gardevoir (#282): 13 colors; 47% near-black; white dress edges light blue-gray (131,148,180) 20%; green dark (49,123,74) outlines on hair; dress highlight with light dither.
- Gengar (#94): 10-11 colors (RS/E 11, FRLG 10); RS/E dark-purple selout 40% vs black 38%; FRLG black 61% vs purple 26%. Large white-teeth grin; checker highlight dither on the body.
- Blaziken (#257): [VISUAL only] near-black outline, tan/cream beak and leg flames with no outline, claws as pale gray-brown shapes; I did not compute statistics for it.
- Gen 4 contrast (Platinum, 80x80, n=4): Charizard (0,0,0) 204 vs brown 201 edge px. Pikachu black 98 vs brown 39 px. The scheme is the same in spirit, but Gen 4 uses larger canvases. Gen 2 Crystal is 4 colors with a white box, so nothing comparable. [MEASURED, small sample]

### Inferences
- A "good Gen 3 recipe" for small yellow/compact designs: near-black outline on 55-75% of the edge, 2-3 ramp steps of yellow/brown for fill and rim, high-contrast black accents, little or no dither, 3x3 eyes with a white shine pixel.
- A "good Gen 3 recipe" for big colorful designs: mix of near-black and selout rims split by part material (skin vs mouth vs claws), plus localized checker dither in wings, membranes and large flat areas.

### Gaps
- No curated external analysis article about these sprites was found. Stats are from a small hand-picked sample.
- Not examined: Gen 3 sprites for round/blob types (Jigglypuff-style), ghosts, steel/rock types, legendary multi-part designs; female/alternate sprites; Unown; Deoxys forms.

---

## Overall source quality
- Web sources found were weak: SEO aggregators and forum snippets, none fully read. Bulbapedia and PokeCommunity pages returned 403.
- The only robust evidence is the sprite measurement above (reproducible from the PokeAPI sprites repo with a short script: edge = opaque pixel with a transparent 4-neighbour; classify by luminance < 50; count 2x2 A/B/B/A windows for dither).
- Prior knowledge claims flagged [UNVERIFIED] should be treated as hypotheses for the algorithm designer to test on the sprites directly.
