# Gen 3 Pokemon Sprite Technical Constraints (RSE / FRLG, GBA)

Method note: Bulbapedia returned HTTP 403 to direct fetch, so its claims are cited via search snippets only. Primary evidence comes from pret/pokeemerald source and from PNG/PAL files I downloaded from pret/pokeemerald master and inspected directly (measurements marked "measured"). pokefirered was NOT inspected directly; it shares the same engine/format lineage but treat as unverified.

## Sprite dimensions and placement in the canvas

### Takeaway
All Gen 3 Pokemon front and back pics are 64x64 canvases (8x8 tiles). A per-species table records the bounding box of drawn pixels and the gap from its bottom edge to the canvas bottom, so there is no fixed baseline: sprites are bottom-anchored per table, not drawn on a universal ground line.

### Cited Findings
- Source comment: "All Pokemon pics are 64x64, but this data table defines where in this 64x64 frame the sprite's non-transparent pixels actually are. .size is the dimensions of this drawn pixel area. .y_offset is the number of pixels between the drawn pixel area and the bottom edge." — [pokeemerald front_pic_coordinates.h](https://raw.githubusercontent.com/pret/pokeemerald/master/src/data/pokemon_graphics/front_pic_coordinates.h) (back table has the same comment: [back_pic_coordinates.h](https://raw.githubusercontent.com/pret/pokeemerald/master/src/data/pokemon_graphics/back_pic_coordinates.h))
- Example front entries (size WxH, y_offset): Bulbasaur 32x40 / 14; Ivysaur 40x48 / 10; Venusaur 64x64 / 3; Charmander 40x40 / 12; Charizard 64x64 / 1; Blastoise 64x64 / 0; Caterpie 32x40 / 16; Metapod 40x32 / 20 — same front_pic_coordinates.h
- Example back entries: Bulbasaur 48x32 / 16; Ivysaur 48x48 / 9; Venusaur 64x56 / 7; Charmander 48x40 / 14 — back_pic_coordinates.h above
- Drawn-area sizes are multiples of 8 (tile granularity) in all entries seen; `MON_COORDS_SIZE(w,h)` macro encodes them (wiki example `MON_COORDS_SIZE(24, 56)`, `.y_offset = 6`; older hex form `.size = 0x88`) — [decomp wiki](https://code.heni.lol/decomp/emerald/wiki/How-to-add-a-new-Pok%C3%A9mon-species)
- Bulbapedia (via search snippet): "In Generation III, all front sprites are 8x8 tiles (64x64 pixels)"; a Bulbapedia sprite-review page lists 56x56 for Gen I/II and 64x64 for Gen III — [Bulbapedia Pokemon sprites](https://bulbapedia.bulbagarden.net/wiki/Pok%C3%A9mon_sprites)
- Measured file dimensions (pokeemerald master, bulbasaur/charizard/mew): front.png 64x64, back.png 64x64, anim_front.png 64x128, icon.png 32x64. Trainer front (hiker.png) 64x64; trainer back (brendan.png) 64x256 (appears to be 4 stacked 64x64 frames).
- Trainer front pics: `TRAINER_PIC_SIZE` is the default; six entries (Sr and Jr, Pokefan M, Champion Wallace, Cycling Triathlete M, Battle Girl, Arena Tycoon Greta) use `TRAINER_PIC_SIZE * 2` (likely two-frame pics) — [pokeemerald front_pic_tables.h](https://raw.githubusercontent.com/pret/pokeemerald/master/src/data/trainer_graphics/front_pic_tables.h). Trainer coords use `.size = 8, .y_offset = 1` in the entries seen (units of .size for trainers unclear).
- Icon (party menu) is 32x64 = two 32x32 frames stacked (measured). The wiki says icons use one of three predefined shared palettes (index 0, 1, 2) rather than normal.pal — [decomp wiki](https://code.heni.lol/decomp/emerald/wiki/How-to-add-a-new-Pok%C3%A9mon-species)
- Footprint is 1bpp, two colors (black/white) — same wiki; pokemon.h declares `INCGFX_U8(".../footprint.png", ".1bpp")`.

### Inferences
- A conversion tool should output 64x64, place the subject so its lowest opaque row sits at 64 - y_offset, and optionally compute bounding box rounded up to multiples of 8. Gen 3 has no single ground line; flying/tall species touch bottom (offset 0-3), small ones float higher (offset 12-20 means the empty band is below the sprite in the canvas, i.e. the sprite sits mid-canvas and the engine shifts it onto the platform).
- Large sprites (Venusaur, Charizard, Blastoise) fill the full 64 width.

### Gaps
- Exact on-screen anchoring math (how y_offset shifts the sprite relative to platform shadows) not read from engine code.
- Back sprite 64x64 vs. whether any species are smaller was not exhaustively checked; trainer back sprite frame layout (4x64 frames) is inferred from the 64x256 measurement only.
- pokefirered not inspected.

## Palette

### Takeaway
Each Pokemon sprite uses exactly one 16-colour palette of 15-bit BGR555 colours, with index 0 transparent; shiny is a second palette applied to the same indexed image. Front and back share the same normal (and shiny) palette.

### Cited Findings
- Colour word is 15-bit BGR: bits 0-4 red, 5-9 green, 10-14 blue, bit 15 unused (0-31 per channel); OBJ palette RAM holds 256 colours split into 16 palettes of 16; colour 0 of each palette is transparent — [GBATEK](https://problemkaputt.de/gbatek.htm). pokeemerald's `PlttData` struct packs 5-bit channels — [types.h](https://raw.githubusercontent.com/pret/pokeemerald/master/include/gba/types.h)
- Per species there is a single `normal.pal` and `shiny.pal`; the source declares front pic, back pic, normal palette, shiny palette separately (one palette per species, no separate back palette): `gMonStillFrontPic_X`, `gMonPalette_X`, `gMonBackPic_X`, `gMonShinyPalette_X` — [pokemon.h graphics data](https://raw.githubusercontent.com/pret/pokeemerald/master/src/data/graphics/pokemon.h)
- Species-add guide: must use indexed mode; "limited yourself to 14 colors"; put normal RGB in normal.pal and shiny RGB in shiny.pal; shiny registered with `SPECIES_SHINY_PAL(...)` — [decomp wiki](https://code.heni.lol/decomp/emerald/wiki/How-to-add-a-new-Pok%C3%A9mon-species). Another wiki page says GBA shows 16 colours per sprite palette and each sprite uses exactly one (via search snippet).
- .pal files are JASC-PAL text, 16 lines of 8-bit RGB (measured). Values are multiples consistent with 5-bit expansion (e.g. 205, 222, 189, 156, 115, 82, 57, 24, 16 -> v*8 rounded patterns; 255 = 31), so they are 5-bit colours expanded to 8-bit. (Measured, bulbasaur/charizard/mew.)
- Shiny = same indexed pixels, different colour values only; in measured bulbasaur, entries 0,1,5-9,10 identical in normal/shiny and only the body greens changed (indices 2-4, 11-14 changed; 6-8 red tongue/accents unchanged) (measured).

### Inferences
- Tool should quantise to 5 bits/channel (c8 -> c5 = round(c/8.2) or c>>3, expanding back with e.g. (c5<<3)|(c5>>2); the decomp files show values like 205/222/189 which equal c5*8.26 rounding (e.g. 25*8.226=205.6), so the decomp converter uses c5*255/31) to match the look.
- A palette-swap shiny must keep index assignments; design palette so regions that change colour have their own indices.

### Gaps
- Whether in-game blending/fading alters palettes: not covered.
- "14 colours" in the wiki vs. real usage (below): unresolved by a primary source.

## Palette ordering conventions

### Takeaway
Index 0 is transparent/background; there is no strict universal ordering, but measured official files show consistent habits (shared near-white/black slots), not a rule.

### Cited Findings
- Index 0 is the transparent colour (GBATEK, above). In the decomp .pal files index 0 holds a placeholder colour that is not displayed: bulbasaur 205,205,172; charizard 213,213,213; mew 222,222,222 (measured). The last entry (index 15) is 255,0,255 magenta in Bulbapedia-style default files in bulbasaur but charizard actually uses index 15 as a real colour in front/anim (measured) — so index 15 is not reserved.
- Measured bulbasaur palette: [1]=255,255,255 white; [10]=16,16,16 near-black (outline); [9]=205,205,205 grey. Mew: [1]=255,255,255 white, [2]=41,41,41 dark (measured). Charizard: [1]=white-ish, [2]=255,255,255 (measured palette lines 4,5,19 only partially inspected).
- In bulbasaur the outline/dark colour is index 10 and in mew it is probably in the 10-15 range; there is no fixed index for outline across species (measured, 3 species only).

### Inferences
- Tool should put transparent at index 0 and may place white/black anywhere; treat index convention as non-binding. Many official palettes keep white at 1 and the outline near the end/middle, but this was seen in 3 species only.

### Gaps
- No survey of all 386 species for the outline-index convention; no primary documentation of an ordering rule found.

## Storage format

### Takeaway
4bpp 8x8 tiles, LZ77 compressed (GBA BIOS LZ77, via `.4bpp.lz`), built from indexed 4-bit PNGs plus JASC .pal files by the decomp's gbagfx tool.

### Cited Findings
- Front/back: `INCGFX_U32("graphics/pokemon/<species>/front.png", ".4bpp.lz")`, `back.png` same; palettes `normal.pal` / `shiny.pal` -> `.gbapal.lz`; icon `.4bpp` uncompressed `u8`; footprint `.1bpp` — [pokemon.h](https://raw.githubusercontent.com/pret/pokeemerald/master/src/data/graphics/pokemon.h)
- Animated front included from `anim_front.4bpp.lz` as `gMonFrontPic_X` — [decomp wiki](https://code.heni.lol/decomp/emerald/wiki/How-to-add-a-new-Pok%C3%A9mon-species)
- GBA 4bpp tile = 32 bytes per 8x8 tile, 4 bytes/row, low nibble is the left pixel, high nibble the right — [GBATEK](https://problemkaputt.de/gbatek.htm)
- Measured: all sprite PNGs are 4-bit indexed (bit depth 4, colour type 3) with 16-entry PLTE.
- File names per species folder: front.png, back.png, anim_front.png, icon.png, footprint.png, normal.pal, shiny.pal (measured/downloaded; matches wiki).
- Compressed data stored as u32 arrays so size is padded to 4 bytes — [pokemon.h](https://raw.githubusercontent.com/pret/pokeemerald/master/src/data/graphics/pokemon.h) (inference from type).

### Inferences
- A tool intended for decomp import should emit a 64x64 4-bit indexed PNG plus a 16-entry JASC-PAL. Size is bounded by LZ compression only for ROM space, not a hard sprite limit per se.

### Gaps
- Exact LZ77 variant byte format (header 0x10) not fetched; known from GBA BIOS but not verified here.
- Tile ordering in memory (row-major 8x8 tiles over 64x64) assumed.

## Animation frames

### Takeaway
Front sprites have two frames, stored as anim_front.png (64x128, two 64x64 frames stacked); still front.png is used where no animation plays. Back sprites are single-frame.

### Cited Findings
- Measured: anim_front.png is 64x128 for all three sampled species; front.png is 64x64.
- "Because you are limited to two frames, there are already predefined animations"; animation entries are (frame index, duration in frames) — [decomp wiki](https://code.heni.lol/decomp/emerald/wiki/How-to-add-a-new-Pok%C3%A9mon-species); front_pic_anims.h uses `ANIMCMD_FRAME(index, duration)` with indices 0 and 1 mostly — [front_pic_anims.h](https://raw.githubusercontent.com/pret/pokeemerald/master/src/data/pokemon_graphics/front_pic_anims.h) (the file also references frame index 2 for some special cases, e.g. egg; unexplained).
- Both frames of anim_front share the species palette (single palette per species).
- Back sprites have predefined animations too (wiki) but one image.

### Inferences
- Frame 2 must use the same palette indices; design with a stable body and small displacement. Frame 1 is probably identical to front.png (not verified pixel-wise).

### Gaps
- Not verified that front.png == top half of anim_front.png.
- Egg/special frame 2/3 behaviour unexplained.

## Colours actually used

### Takeaway
Official sprites use up to the full 15 non-transparent colours but often fewer; measured samples show 9-15.

### Cited Findings (measured from pokeemerald files, indices used incl. 0 background)
- Bulbasaur front: 15 indices (0-14) = 14 visible colours + background; back: 14 indices (no index 7).
- Charizard front: all 16 (0-15) used, so 15 visible colours; back: 11 indices.
- Mew front: 10 indices (0,1,3,4,10-15), i.e. 9 visible colours; back: 7 indices.
- Icons: 8-10 indices of a shared icon palette.
- Trainer front (hiker): all 16 indices used.

### Inferences
- Contradiction: wiki "14 colours" guidance vs. Charizard using 15 visible: 14 is conservative advice (likely 1 background + 14 leaves one spare/ reserved at tool level), the hardware limit is 15 + transparent.
- Back sprites generally use fewer colours than their front sprite but share the same palette.

### Gaps
- No statistical survey across the full dex.

## Art guidelines and import advice

### Takeaway
Practical rules: 64x64, 4-bit indexed, 16-entry palette with transparent index 0, edit front/back/anim_front/icon in indexed mode, supply matching normal and shiny palettes.

### Cited Findings
- Wiki steps: edit anim_front.png, front.png, back.png in indexed mode, no more than 14 colours, icon uses one of three predefined palettes, footprint two colours — [decomp wiki](https://code.heni.lol/decomp/emerald/wiki/How-to-add-a-new-Pok%C3%A9mon-species)
- Porypal tool exists to generate palettes and handle shiny variants for decomp graphics (via search snippet; not opened).

### Other generations (separate)
- Gen I/II sprites: 56x56 (Bulbapedia review page snippet, [link](https://bulbapedia.bulbagarden.net/wiki/Pok%C3%A9mon_sprites)); not Gen 3.

### Gaps
- No stylistic guide (outline thickness, dithering, shading rules) found from a primary source.
- Bulbapedia, Spriters Resource, PokeCommunity tutorials, pokefirered: not directly fetched/verified.
