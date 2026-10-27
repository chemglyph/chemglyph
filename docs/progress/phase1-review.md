# Phase 1 review: molecules done right (0.2)

Date: 2026-10-27. Covers the work after 0.1.3 up to the 0.2 release candidate.

## Exit criteria

| Criterion (docs/SPEC.md, section 4) | Status |
| --- | --- |
| ACS profile conformance tests pass | Met. Bond length, line width, label size, bond spacing, and label margin are measured in the rendered SVG for all three profiles (`tests/test_profiles.py`). |
| No unregistered severe layout issue on a corpus of 300+ molecules | Met. 416 structures from PubChem (CIDs recorded) plus hand-written entries; 14 have registered severe issues, each with its cause, in `tests/test_corpus.py`. A new severe issue, or a fixed one still on the list, fails CI. |
| Blind test against ChemDraw ACS panels, ChemGlyph chosen at 40% or more | Not run: no graders were available. Moved from the release gate to the gate for public claims and announcements (docs/SPEC.md, section 4); 0.2 is released without any comparison claim. The generator now uses the new profiles. |

## What was built

- Fixed-scale engine and three profiles (`acs1996`, `screen`, `textbook`),
  now the only molecule styles; the 0.1 names are deprecated aliases.
- Label clearance against glyph outlines and their convex hulls, wedge and
  hash redraws, stroke floor.
- Layout: input coordinates kept; otherwise the best of CoordGen, RDKit,
  seeded RDKit, RDKit ring templates, and, for cages, a projection of the
  3D shape. Layout checks: close atoms, atoms on bonds, crossings, atoms in
  rings, lost stereocentres, overlapping labels.
- Verification on every render: all bonds drawn, heteroatoms labelled,
  drawn wedges read back to the input's stereocentres, embedded structure
  round-trips to the same InChIKey, optional name check.
- Outputs: SVG and PNG with the structure embedded, vector PDF, MOL.
- Abbreviations (J. Org. Chem. list, heteroatom rule, SUP groups in the
  molfile), bold compound numbers, charge signs placed off bonds with true
  minus signs, fragment spacing for salts.
- Determinism test: byte-identical output across runs and processes.

## Numbers

| Measure | Value |
| --- | --- |
| Corpus structures rendered and verified (acs1996) | 416 of 416 |
| Registered severe layout issues | 14 (17 with CoordGen alone, before the label checks existed) |
| Layout methods used | CoordGen 379, ring template 19, RDKit 14, projection 4 |
| Render time per structure | median 0.06 s, 95th percentile 0.3 s, slowest about 1.2 s (beta-cyclodextrin) |
| Tests | about 1,830, on Python 3.11 and 3.13, Linux and macOS, and RDKit 2024.09 |

## What the checks found

The automated checks were worth more than any single feature; each of
these passed every earlier test.

- Under RDKit 2024.09, quinine was drawn, and embedded, as its C4 epimer:
  no wedge in that layout fixed the bridgehead. Now an explicit H carries
  the wedge, as chemists draw it.
- A bond was drawn inside the counter of an O (pyridine N-oxide, textbook
  profile), far from every outline edge. Labels now count as glyph hulls.
- RDKit put progesterone's C9 hydrogen on top of C10 and marked it with a
  red box. Added hydrogens now go where there is room; red boxes are off.
- RDKit writes molfiles with SUP groups that its own reader rejects.
- With true minus signs, Na+ and Cl- touched; fragments are now spaced.
- PubChem resolves some names to the wrong structure (trityl radical,
  cis- and trans-decalin), which is what the name check is for.

## Registered limitations

Helicene and fullerene (no planar drawing); BINAP, morphine, codeine,
paclitaxel, vinblastine, tetrodotoxin (crowded polycycles); cyclodextrins,
amphotericin B, forskolin, rifampicin, sitagliptin (labels in crowded
places). They render with a warning. The common cause is that layouts
place atoms, not label boxes; label-aware placement is the next layout
step.

## Plan changes

- The object API (`Compound`, `Figure`) moves to 0.4. Its real users are
  reaction schemes, which compose compounds; designing it before them
  would mean redesigning it.
- The visual regression gate is not built yet. The determinism test covers
  byte-identical output; perceptual comparison against reference images is
  added with 0.3, when formula typesetting needs it.
- Phase 2 (0.3, formulas) starts from what phase 1 learned: RDKit writes
  carbon-free formulas with H first while journals use the Hill system;
  ions and salts now have placed charges and spacing to build on.
