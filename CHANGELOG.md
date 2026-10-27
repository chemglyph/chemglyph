# Changelog

Each version below is a PyPI release. The tag `vX.Y.Z` marks the exact
commit the release was built from; for 0.1.0 to 0.1.2 this was verified by
comparing every file in the published sdist against the repository history.

## 0.1.3 (unreleased)

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
