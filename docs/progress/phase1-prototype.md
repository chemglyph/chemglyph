# Phase 1 prototype: fixed scale against the ACS Document 1996 settings

Date: 2026-10-27. Script: `benchmarks/acs1996_prototype.py`. Molecules: the
20 blind-test structures. RDKit 2026.09.1, label font Liberation Sans
(metric-compatible with Arial, SIL OFL 1.1).

## Question

Can RDKit produce drawings at one fixed physical scale that match the ACS
Document 1996 numbers (bond 14.4 pt, line 0.6 pt, bond spacing 18%, labels
10 pt), and how far is the released `acs` style from them?

## Findings

| Measure | ACS target | 0.1.3 `acs` | Prototype |
| --- | --- | --- | --- |
| Bond length | 14.4 pt | 26.6 to 48.4 units (1.8x spread) | 14.400 pt on all 20 |
| Double-bond spacing | 18% | 17.7% to 18.2% | 17.8% to 18.1% |
| "O" glyph height | 10 pt label | 14.6 to 26.3 units (1.8x spread) | 7.08 pt on all 20 |
| Line widths | 0.6 pt | n/a | 0.6 pt, plus 0.15 and 0.3 pt hash lines on 5 molecules |

1. RDKit's `SetACS1996Mode` uses the ACS numbers, but on its own it does not
   give a constant bond length. With the self-sizing canvas (`-1, -1`) the
   drawn bond varied from 11.96 to 14.25 per coordinate unit across four
   molecules, because padding is a fraction of the canvas and the canvas
   is rounded to whole pixels. At 10x resolution the self-sizing canvas
   scaled the font but not the bonds.
2. What works: a fixed canvas large enough for the molecule, padding 0,
   `fixedBondLength` set to 144 units per mean bond (10x resolution), then
   cropping to the drawn content and declaring the size in points. Bond
   length is then exact on every molecule.
3. Hashed wedge lines come out at 0.15 and 0.3 pt (cholesterol,
   penicillin G, glucose, paclitaxel, s-ibuprofen). IUPAC 2008 advises
   against lines under 0.5 pt, so the engine must set a floor.
4. Label clearance: RDKit clips bonds against the label's bounding box plus
   padding. For bonds that leave a label diagonally this removes far more
   than the ACS 1.6 pt margin. Sulfate's S-O bonds keep only 1.4 pt of
   visible line out of 14.4 pt and read as dashes, which IUPAC warns can be
   mistaken for charges. With padding 0 they keep 4.1 pt, but horizontal
   bonds then sit too close to their labels. The fix is to clip against
   the glyph outline plus 1.6 pt, as structure editors do; RDKit already
   emits the glyphs as outline paths, so the engine can do this.

## Consequences for phase 1

- The fixed-scale renderer follows finding 2.
- Add a minimum width for hash and wedge strokes.
- Implement glyph-outline label clearance with the profile's margin width.
- Bundle Liberation Sans (OFL) so raster and PDF output look the same on
  every platform; SVG keeps naming Arial and Helvetica first.

## Follow-up: corpus and layout checks (2026-10-27)

The 416-structure corpus (`benchmarks/corpus.csv`) was rendered in all
three profiles, 1248 renders: no crash, every figure verified. Findings:

- PubChem name lookups are not always what the name says: "triphenylmethyl
  radical" resolves to triphenylmethane, and cis- and trans-decalin resolve
  to decalin without stereo. Those entries are hand-written and checked by
  formula. This is the failure the `name=` check exists for.
- With CoordGen alone, 17 structures had severe layout problems. Most were
  bridged ring systems, which chemists draw in perspective; RDKit's ring
  templates give those drawings for 18 corpus structures. After best-of
  selection 12 remain (fullerene, helicene, adamantane, cubane,
  bicyclo[1.1.1]pentane, hexamine, BINAP, morphine, codeine, paclitaxel,
  vinblastine, tetrodotoxin). They render with a layout warning and are
  listed as known limitations in `tests/test_corpus.py`. Own templates for
  the common cages are the next step for them.
- Hashed wedges toward labelled atoms needed the same flare-aware pull-back
  as solid wedges; the corpus found ten such cases the blind-test set did
  not have.
- RDKit writes carbon-free formulas with hydrogen first (H3BO3) where the
  Hill system, used by PubChem and journals, sorts alphabetically (BH3O3).
  The formula phase must order formulas itself.
