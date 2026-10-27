# Changelog

Each version below is a PyPI release. The tag `vX.Y.Z` marks the exact
commit the release was built from; for 0.1.0 to 0.1.2 this was verified by
comparing every file in the published sdist against the repository history.

## Unreleased

### Changed

- `render_molecule` draws with the fixed-scale profiles only, and the
  default style is `screen` instead of `modern`. The 0.1 names still work
  as aliases with a `DeprecationWarning` and a line in `warnings`: `modern`
  is `screen`, `acs` is `acs1996`, `textbook-cn` is `textbook`. They go in
  1.0. `size` is ignored with a warning, since every style draws at a fixed
  scale; use `dpi` to set PNG resolution.
- The MCP `render_molecule` tool defaults to `screen` as well.
- Reaction schemes accept the new style names. Their molecules are still
  drawn with the 0.1 canvas-fitted renderer until reactions move to the
  profiles.
- The README gallery is redrawn with the three profiles at one scale
  (`benchmarks/gallery.py`).

### Added

- Charge signs are placed like ChemDraw places them: at the upper right of
  the label as a superscript unless a bond leaves the atom in that
  direction, then at the next free corner or side (the O- of a pyridine
  N-oxide moves to the upper left). Negative charges are true minus signs,
  as wide as the plus, instead of RDKit's hyphen. The sign belongs to the
  atom's label, so bonds keep the label margin from it.
- Ions and other fragments are set side by side in input order with room
  for their labels; RDKit left about one bond between them, and Na+ Cl-,
  Ca2+ CO3 2-, and the ionic forms of MeMgBr and Cp2TiCl2 collided.
- Bracketed metal ions ([Cu+2], [Fe+3]) are drawn without the radical dot
  RDKit's valence model gives them; organic radicals keep theirs.
- `number="12a"` sets a compound number in bold (Liberation Sans Bold, SIL
  OFL 1.1, now bundled) at the label size, centred half a bond length under
  the structure. It is stored as the title of the embedded molfile in every
  output format, and in the SVG record and PDF Info.
- `abbreviate=True` draws protecting and activating groups as labels (Ac,
  Bz, Piv, Boc, Cbz, Fmoc, Alloc, Troc, Bn, PMB, Tr, MOM, THP, TMS, TES,
  TBS, TIPS, TBDPS, Ts, Ms, Tf), and a list of labels also picks common
  substituents (Me to t-Bu, Cy, Ph, p-Tol, CO2Me, CO2Et, CO2t-Bu, CF3).
  Spellings follow the J. Org. Chem. list of standard abbreviations. Acyl,
  carbamate, and benzyl groups are abbreviated only on heteroatoms; a group
  on a terminal O or NH joins the label (OTs, NHBoc, mirrored to TsO and
  BocHN when the bond comes from the right). The embedded structure, the
  identity, the name check, and `fmt="mol"` keep every atom; the molfile
  carries the abbreviations as SUP groups. A label that would overlap
  another label or a bond is drawn in full, and `report["abbreviations"]`
  and `report["abbreviations_drawn_in_full"]` list both.
- Label overlap check: a label drawn over another label or over a bond it
  does not belong to is a severe layout problem with a warning. It found 26
  of the 416 corpus structures; 14 of those came from the next item.
- The stereo hydrogens RDKit adds at ring fusions (the steroid convention)
  are moved to the free direction with the most room when RDKit places one
  on another atom, as it did for progesterone's C9 H; wedges are assigned
  after the move. RDKit's red close-contact boxes are switched off, since
  the layout checks report such atoms.
- Verification reads the configuration of every stereocentre back from the
  drawn wedges (`checks["wedges_match_stereo"]`). With abbreviations the
  drawn molecule differs from the embedded one, so the embedded round trip
  alone does not cover the drawing.
- `style="acs1996"`: a fixed-scale profile that follows the ACS Document
  1996 settings. Every molecule is drawn with 14.4 pt bonds, 0.6 pt lines,
  18% double-bond spacing, and 10 pt labels, so all figures share one scale.
  The SVG size is given in points and PNG output takes a `dpi` argument.
  `RenderResult.report` carries the measured bond length, the label
  clearance, and the shortest bond next to a label.
- Bond ends next to a label stop 1.6 pt from the glyph outline (the ACS
  margin width) instead of RDKit's box clipping, which left sulfate with
  1.4 pt of each S-O bond. Lines, hashed wedges, and solid wedges all
  follow the rule. When two labels crowd one bond, the margin is relaxed
  in steps and a warning says so.
- Hashed wedges are drawn at the 2.5 pt hash spacing with 0.6 pt strokes
  (RDKit drew 0.15 to 0.3 pt hairlines 0.5 pt apart).
- Labels use the bundled Liberation Sans (SIL OFL 1.1), metric-compatible
  with Arial, embedded as outlines, so output does not depend on installed
  fonts.
- `style="screen"` and `style="textbook"`: the same engine with the screen
  and teaching profiles. `screen` uses the ACS geometry with classic CPK
  colours for O, N, S, and Cl; `textbook` uses 0.8 pt lines, 12 pt labels,
  and 20% bond spacing. Coloured bond halves are joined, clipped as one
  line, and split again, so label clearance holds in colour too.
- Layout checks (`chemglyph.layout`): atoms that nearly coincide, atoms on
  bonds, crossing bonds, atoms inside rings, and uneven bonds, measured on
  the 2D coordinates. Without input coordinates, the layout is now the best
  of CoordGen, RDKit's depictor, and RDKit with seeded sampling, and a
  bridged ring system with an RDKit ring template (camphor, quinuclidine,
  morphine, atropine, artemisinin) is drawn from the template in the usual
  perspective. Crossings inside a bridged system count as perspective, not
  as errors. `report["layout"]` names the method and the problems, and a
  severe problem is also a warning.
- A 416-structure corpus (`benchmarks/corpus.csv`, from PubChem with CIDs,
  plus three hand-written entries PubChem resolves wrongly by name) is part
  of the test suite: every structure must render, verify, and keep the
  label margin unless a warning says otherwise, and severe layout problems
  must stay within a list of known limitations.
- A layout whose wedges cannot fix a stereocentre (a quinuclidine bridgehead
  whose ring bonds run nearly straight through it) counts as a layout
  problem, and if the chosen layout still has one, that centre gets an
  explicit H with the wedge, as it is usually drawn. Under RDKit 2024.09
  quinine was otherwise drawn, and embedded, as its C4 epimer; verification
  caught it. `report["layout"]["added_hydrogens"]` lists such centres.
- Molecules of hydrogen only (H2, H+, D2) render; CoordGen gave them NaN
  coordinates.
- Hashed wedges pull their wide end back until every hash mark, not only
  the bond axis, keeps the label margin (a hash toward an added stereo H
  came within 1.3 pt).
- `fmt="pdf"`: a one-page vector PDF sized in points, written directly
  from the figure's geometry with no extra dependency, carrying the
  structure in its document information. `fmt="mol"` returns the molfile
  with the drawn 2D coordinates for editing in a structure editor. Both
  need a fixed-scale style.
- Highlighted bonds draw a band of about 4 pt. RDKit's ACS1996 preset sets
  a multiplier that made the band 19 pt wide, wider than the bond is long.
- Figures from the fixed-scale profiles carry their structure: SVG output
  holds a `chemglyph:structure` record (SMILES, InChI, InChIKey, formula,
  and the full molfile) and PNG output holds RDKit's standard SMILES and
  molfile chunks. `chemglyph.read_structure(figure)` reads it back. RDKit's
  own SVG metadata was not used because it lost E/Z stereo for
  beta-damascone and could not be read back for azobenzene.
- `RenderResult.report` gains a verification block: every bond drawn, every
  heteroatom labelled, and the embedded structure reading back as the input
  (`report["verified"]`). Any failure is also a warning.
- `render_molecule(..., name="cholesterol")` checks the structure against
  the name offline (built-in dictionary or OPSIN) and warns when the name
  belongs to a different structure, or to the same one with different
  stereo. The MCP tool takes the same `name` argument and reports the
  result in its text, so an agent learns about a wrong SMILES even when the
  client hides images. Identifiers are computed without coordinates, so a
  2D layout never changes an InChIKey.
- A molfile that carries 2D coordinates keeps its layout, so a structure
  arranged in a drawing program comes out the way its author placed it.
  SMILES, InChI, and molfiles with all-zero or 3D coordinates still get a
  fresh 2D layout. This applies to every style.
- Conformance tests (`tests/test_profiles.py`) measure these numbers in the
  rendered SVG for all 20 blind-test molecules in every profile, and fail
  if any bond falls back to RDKit's own clipping.

### Fixed

- A bond between two crowded labels could be drawn inside the counter of
  an O (the hole of the letter), which is far from every outline edge, so
  it passed the margin check: the N-O bond of pyridine N-oxide in the
  textbook profile was a dot inside the O. Labels now count as the convex
  hull of each glyph, and a bond end inside its own label is reported as a
  label overlap.

## 0.1.3 (2026-10-27)

### Fixed

- `validate_structure` ignored ring-closure digits inside branches, so
  `c1ccc(c1)C` was reported as an unpaired ring closure instead of getting
  the uppercase fix. Ring closures inside branches and two-digit `%nn`
  labels are now counted correctly, and an unclosed bracket and an unclosed
  parenthesis are reported separately.
- The built-in Chinese dictionary mapped 盐酸 (hydrochloric acid) to the
  chloride ion. It now resolves to HCl.
- The dependency floor is now `mcp>=2.0`. The server uses `MCPServer`,
  which first shipped in mcp 2.0.0, so an install that picked mcp 1.x could
  not start.
- The `validate_structure` MCP tool description gave `c1ccc1` as an example
  of a repair, but RDKit parses it as cyclobutadiene. The example is now
  `c1cccc1`, and a test checks that the example stays true.

### Changed

- `modern` style: classic CPK heteroatom colors (O `#FF0D0D`, N `#3050F8`,
  S `#E8C300`, Cl `#1FB01F`), label font range 12 to 28 (was 14 to 32),
  bond line width 1.8 (was 2.4), padding 0.06 (was 0.03).
- `acs` style: padding 0.05 (was 0.02).
- Layout: a substituent that the 2D layout places inside a ring of up to 8
  atoms is moved outside after layout. Only positions change; bonds, atom
  order, and stereo flags are untouched. Paclitaxel's gem-dimethyl remains a
  known limitation because no exit keeps the drawing planar.

### Added

- `docs/SPEC.md`, the project specification, now lives in the repository.
- A release workflow that builds on a `v*` tag and publishes to PyPI through
  trusted publishing, so no upload token is handled by hand.

## 0.1.2 (2026-08-14)

- MCP render tools return PNG images, since several chat clients drop SVG
  image content. Reaction SVGs are rasterized with `resvg-py`.
- MCP renders are also saved to `~/Downloads/chemglyph/` and the path is
  returned in text, for clients that hide tool images (set `save` to false
  to skip).
- Blind-review tooling: a Chinese voting page, a "neither" option, per-pair
  notes, run ids on decks, and automatic scoring.

## 0.1.1 (2026-08-14)

- Chinese names resolve through a built-in dictionary, with an optional
  translator callable for names that are not in it.
- Reaction layout: wrapped rows end with a down arrow, `layout.align:
  "arrow"` aligns the arrows of all rows, condition labels scale with the
  style, and fragments are cropped to their drawn content.
- `acs` labels scale with the molecule instead of being pinned at 10 px.
- Parse errors give parser-specific suggestions, and RDKit messages no
  longer leak to stderr during validation.
- MCP registry metadata (`server.json`).

## 0.1.0 (2026-08-13)

First release: molecule rendering in three styles (`acs`, `modern`,
`textbook-cn`), the reaction layout engine, validation with quick fixes,
English name parsing through OPSIN, and the MCP server.
