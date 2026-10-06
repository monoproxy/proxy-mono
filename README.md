# Proxy Mono

Proxy Mono is a monospaced typeface rebuilt by code, for code: one variable family, Thin (100) to Black (900). It is made to hold up as a display heading and still work all the way down to code in an editor.

Proxy Mono applies a consistent set of design constraints across the character set:

- A common 700-unit character cell
- Unified stem proportions
- Consistent sidebearings and horizontal alignment
- Reproportioned glyphs across different upstream designs
- Removal or modification of source-specific details where they conflict with the unified system
- Reconstruction of selected glyphs rather than direct reuse
- Consistent relationships between related glyphs and the forms built from them

**Specimen and type tester:** https://www.monoproxy.studio/lab/proxymono

![COMING NOW Q4 2026, set in Proxy Mono at weight 650: the rebuilt M, N, W, G and Q, the shared oval of C, G, O and Q, and the zero, which is the O with a slash](documentation/letters.png)

![Proxy Mono: the wordmark at weight 650, the nine weights, the alphabet and the look-alike characters](documentation/hero.png)

![Proxy Mono across the weight axis, 100 to 900](documentation/weight-axis.gif)

![The nine weights, each with a line of code](documentation/weights.png)

![Code at text size, and the look-alike characters at 11, 13 and 16 px](documentation/code.png)

## Coverage

611 encoded characters: GF Latin Core and more. Western, Central and Eastern European languages,
Vietnamese, and a wide set of symbols, arrows, currencies and fractions.

![Accented Latin across the nine weights](documentation/specimen.png)

## Design & Lineage

Proxy Mono is a new monospace typeface system built through the synthesis, reconstruction, and refinement of three open-source typefaces: Space Mono, Martian Mono, and Geist Mono.

Rather than combining the source typefaces unchanged, Proxy Mono establishes a unified design system across the family. The source glyphs were used as starting material and then systematically reconstructed, reproportioned, interpolated, and re-spaced to work within a consistent 700-unit monospace cell and shared typographic structure.

The design is governed by a common stem logic, consistent proportions, spacing, and alignment. Selected glyphs were substantially reconstructed to establish relationships that do not exist in any single upstream typeface, including the treatment of M, N, W, G, Q, and zero.

The resulting typeface is therefore not presented as a typeface created independently of its sources. Its lineage is intentionally documented. The originality of Proxy Mono lies in the design system, synthesis, reconstruction, and typographic decisions that unify these sources into a single coherent monospace family.

### Construction Principles and Glyph Provenance

- **One stem across every glyph.** Every upright carries the same stem at each weight, on straight
  stems and on the sides of the bowls alike: 46 units at Thin, 110 at Regular, 197 at Black. Horizontals
  and arches run thinner so they read as the same weight (at Regular the bar of the H is 103, the top of
  the O 102).
- **M, N, W, G and Q rebuilt.** Every stroke of the M, N and W is one stem and runs the full cap height,
  up to Black. C, G, O, Q and the zero share one oval: flat sides, round ends.
- **No ink traps**, a slashed zero and round descenders.
- **Thin (100) to Black (900) on one cell.** Every character is 700 units wide on a 1000-unit em, cap
  height 800, x-height 600, at all nine weights. None of the fonts it starts from covers that range on
  this cell.

Every number above is measured from the built fonts, not estimated.

Where a glyph could not be reconciled with the system through simple adaptation, it was reconstructed to follow Proxy Mono’s own geometric and typographic logic.

| Glyphs / components | Source material | Proxy Mono reconstruction |
|---|---|---|
| Most capitals | Space Mono | Reconstructed within the Proxy Mono system. Ink traps are removed. M, N, and W are rebuilt so that each stroke follows a single, continuous stem and runs the full cap height. Q is reconstructed from the Proxy Mono O. |
| B, D, J, K, P, R | Martian Mono | Reconstructed and reproportioned to the 700-unit character cell and aligned to the shared Proxy Mono stem. |
| Zero | Proxy Mono O | Constructed from the Proxy Mono O, with a slash added according to the same geometric system. |
| G | Proxy Mono C | Constructed from the Proxy Mono C, adding the bar and stem to establish the G within the Proxy Mono system. |
| Lowercase, figures, punctuation, capital Y | Geist Mono | Reconstructed and interpolated to the shared Proxy Mono stem across all weights. Glyphs are centred within the 700-unit cell, and accented characters are composed using the same system. |

The source typefaces provide the starting glyph structures; Proxy Mono defines the system through which those structures are reconstructed and unified. The 700-unit cell, shared stem logic, proportions, alignment, spacing, weight interpolation, and newly constructed glyphs establish a consistent relationship across the resulting character set.

### Provenance

Proxy Mono incorporates and modifies material from the upstream typefaces identified above. Their respective licenses and attribution requirements are retained and documented separately.

## Download

The latest fonts are in [`fonts/`](fonts): `variable/` for the variable font, `ttf/` for the nine static
weights, `webfonts/` for the web.

`slant/` holds the same family with a second axis, slant 0 to 10° (an oblique, not a drawn italic). It is
not part of the Google Fonts submission, which is weight only.

## Building

The fonts are generated by a Python script, not drawn in a font editor. `sources/generator/az.py`
builds each weight from the upstream open-source fonts in `sources/upstream/`: it interpolates their
masters to the target stem, rebuilds the letters listed above, removes ink traps, composes the
accented letters and centres every glyph in its cell.

```
make build   # fonts/variable, fonts/ttf and fonts/webfonts
make test    # fontspector, Google Fonts profile
```

Python 3.12. `make build` creates the virtualenv from `requirements.txt`; `sh sources/build.sh` does the
same in one command.

## Sources

- `sources/generator/`: the scripts that build the fonts. This is the source to edit.
- `sources/upstream/`: the open-source fonts they start from. Space Mono as UFOs, Martian Mono and
  Geist Mono as published.
- `sources/masters/`: the nine masters as UFOs with a designspace, exactly as they go into the variable
  font, so the outlines can be opened in a font editor. They are written on every build.

## Quality assurance

Every build runs [fontspector](https://github.com/fonttools/fontspector) with the Google Fonts profile.
Current result: 0 failures, 3 warnings.

- `vendor_id`: MNPX is not yet registered with Microsoft.
- `unreachable_subsetting`: the combining marks belong to no Google Fonts subset, but the
  language-shaping checks for Czech, Danish and Vietnamese fail without them, so they stay.
  fontspector 1.8 also lists about 100 arrows, math signs, fractions and circled digits here, although
  `METADATA.pb` declares the `math` and `symbols` subsets; Font Bakery lists only the marks.
- `contour_count`: one symbol (⓿) has a different contour count from the reference fonts.

## Upstream

Proxy Mono incorporates and modifies material from these SIL Open Font License fonts. Their notices are kept in
[OFL.txt](OFL.txt) and [AUTHORS.txt](AUTHORS.txt):

- Space Mono: Copyright 2016 The Space Mono Project Authors
- Martian Mono: Copyright 2021 The Martian Mono Project Authors
- Geist Mono: Copyright 2024 The Geist Project Authors

## License

This Font Software is licensed under the SIL Open Font License, Version 1.1. See [OFL.txt](OFL.txt),
also available with a FAQ at https://openfontlicense.org
