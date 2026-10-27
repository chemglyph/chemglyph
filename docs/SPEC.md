# ChemGlyph specification

This is the living specification. It replaces the original project
specification, which was never part of this repository; older code
comments that cite section numbers such as "§6" refer to that document.
The plan behind this version was agreed on 2026-10-27.

## 1. Goal

ChemGlyph is the rendering layer chemists use when they write papers and
when they work with AI agents. A caller gives text (a name, SMILES, InChI,
a molfile, a formula, an equation, a reaction description) and gets output
that can go straight into a journal, together with evidence that the
drawing shows what was asked for.

Two words carry the goal, and both are defined as checks:

- **Professional**: output measurably matches a published drawing standard
  (section 5) and can be taken further in ChemDraw, Word, or LaTeX.
- **Reliable**: the same input always gives the same output; the drawn
  structure is verified against the input; a name that does not match its
  structure raises a warning instead of producing a confident wrong figure.

## 2. Principles

1. Correct before pretty. A wrong structure drawn well is the worst outcome.
2. Measure, do not tune by eye. Every size comes from a profile with
   numbers and a source. Human review decides only what has no standard,
   such as the colors of the screen style.
3. One fixed scale. Bond length is set in physical units and every other
   size (font, line width, double-bond spacing, margins) follows from it.
   The canvas fits the content, never the other way round.
4. Render, do not infer. ChemGlyph draws what the caller states. It does not
   predict products, mechanisms, or properties.
5. Offline by default. Online lookups (for example a PubChem cross-check)
   happen only when the caller turns them on.
6. Deterministic. Same input, same version, byte-identical output.

## 3. Architecture

A five-stage pipeline, plus two parts that cut across it.

1. **Resolve**: names, SMILES, InChI, molfile, CDXML, mhchem formulas, and
   reaction SMILES become a `Compound` (or a `Formula`).
2. **Compound**: one chemical entity, held as an RDKit molecule, with its
   identity (InChIKey, formula, weight, charge).
3. **Depiction**: one compound can be shown as a skeletal structure, a
   condensed formula (CH₃COOH), a molecular formula (C₂H₄O₂), or a name.
   Simple salts and ions default to formulas (NaCl, SO₄²⁻), organic
   compounds to structures; the caller can always choose.
4. **Layout**: everything is placed on the profile's scale: molecule
   coordinates, inline formulas and equations, reaction rows, mechanism
   arrows. Coordinates supplied by the caller are kept.
5. **Output**: SVG (with the structure embedded as metadata), PDF, PNG at a
   given DPI, MOL and CDXML for editing, Unicode text, LaTeX (mhchem), and
   MathML.

Cross-cutting:

- **Profile**: all sizes in physical units with a cited source (section 5).
- **Verification report**: returned with every render. It records what the
  input was resolved to, whether the drawn atoms and bonds match it, the
  layout check scores, and warnings (undefined stereo, name and structure
  disagreeing).

The current public functions (`render_molecule`, `render_reaction`,
`validate_structure`, `parse_name`) stay as thin wrappers until 1.0, with
deprecation warnings once the object API replaces them.

## 4. Phases

Each phase ships as one minor version when its exit criteria pass. After
each phase the plan is reviewed and this section is updated.

| Version | Phase | Main deliverables | Exit criteria |
| --- | --- | --- | --- |
| 0.1.3 | Housekeeping | known fixes, CHANGELOG, verified tags, trusted publishing, this spec | PyPI matches the README; CI green |
| 0.2 | Molecules done right | fixed-scale engine, profiles, kept input coordinates, best-of layouts with automated layout checks, abbreviations, compound labels, SVG metadata, PDF and MOL output, verification report, object API | ACS profile conformance tests pass; no unregistered severe layout issues on a corpus of 300+ molecules; blind test against ChemDraw ACS panels at 40% or more |
| 0.3 | Formulas and equations | mhchem-syntax parser, real sub- and superscript typesetting, atom and charge balance checks with balancing suggestions, formulas inside reaction conditions | every supported syntax category renders correctly; balance checks correct on a set of textbook equations |
| 0.4 | Reaction schemes | layout rebuilt on the shared scale, unchanged scaffolds kept in the same orientation, compound numbering, structures above arrows, reaction SMILES and RXN input | five typical schemes from recent papers reproduced and accepted in a blind review |
| 0.5 | Mechanisms | curved arrows anchored to atoms and bonds, electron pairs, partial charges, transition-state brackets, multi-frame strips | ten textbook mechanisms drawn correctly from a single agent call |
| 1.0 | Stable | frozen API, documentation site, gallery | |

## 5. Standards and profiles

Professional output is anchored to published standards, not to taste.

- **IUPAC Recommendations 2008**, *Graphical representation standards for
  chemical structure diagrams* (J. Brecher, Pure Appl. Chem. 2008, 80,
  277-410). The general rules: one consistent bond length per diagram, line
  width close to the stroke width of the label font and never under 0.5 pt,
  double-bond separation at most 33% of the bond length, label text usually
  8 to 14 pt and never under 5 pt, hashed bonds with at least three hashes.
- **IUPAC Recommendations 2006**, *Graphical representation of
  stereochemical configuration* (J. Brecher, Pure Appl. Chem. 2006, 78,
  1897-1970). Wedge and hash conventions.
- **ACS Document 1996 settings**, the drawing style that structure editors
  ship under that name and that journals ask authors to use (for example
  the Organic Syntheses author instructions: "drawn using the standard ACS
  drawing parameters ... found in the 'ACS Document 1996' option"). Values,
  as documented for the style in ChemDraw's help and implemented in RDKit's
  public `SetACS1996Mode`: bond length 14.4 pt, line width 0.6 pt, bold
  width 2.0 pt, bond spacing 18% of the bond length, margin width 1.6 pt,
  hash spacing 2.5 pt, chain angle 120°, atom labels in Arial or Helvetica
  at 10 pt.

The `acs1996` profile implements the ACS values exactly, and its
conformance tests measure them in the rendered output (tolerance 2%). Other
journal profiles are added on demand, each with its source cited here.

Font handling: labels are drawn with the bundled Liberation Sans (SIL OFL
1.1), which has the same metrics as Arial, and are embedded in the SVG as
glyph outlines. Output therefore looks the same everywhere and never
depends on fonts installed on the reader's machine. No proprietary font is
bundled. (Implemented in the `acs1996` profile.)

## 6. Intellectual property rules

- Published numeric settings and recommendations are facts and are
  implemented from the sources above. Text, templates, images, and files
  from ChemDraw or its documentation are never copied into this repository.
- ChemDraw is a trademark of its owner and is named only to describe
  compatibility ("matches the ACS Document 1996 settings"). Reference panels
  made with ChemDraw for blind tests stay with the person who made them and
  are never committed or redistributed.
- File formats (MOL, RXN, CDXML) are implemented for interoperability from
  public format descriptions.
- The mhchem syntax is implemented independently. No mhchem code is copied,
  and test cases are written by us.
- Bundled data (dictionaries, test corpora) is written by the project or
  comes from sources whose license is compatible with MIT. Share-alike data
  (for example CC BY-SA) is not bundled.
- Dependencies keep permissive licenses: RDKit (BSD), Indigo (Apache-2.0),
  OPSIN (MIT), resvg-py (MIT).

## 7. Quality gates

| Gate | What it checks | When |
| --- | --- | --- |
| Structure correctness | atoms and bonds read back from the output match the input; embedded structure round-trips to the same InChIKey | every render, recorded in the report |
| Profile conformance | measured bond length, line width, font size, and bond spacing within 2% of the profile | CI |
| Layout checks | label overlap, bond crossings, substituents inside rings, labels on bonds, extreme aspect ratios, each scored | every render; CI tracks the corpus score |
| Visual regression | perceptual difference against reference images in a pinned container with pinned fonts | CI |
| Determinism | byte-identical output for the same input and version; RDKit pinned to a tested range | CI |
| Identity | name and structure compared by InChIKey when both are given; undefined stereo reported | every render |

Human blind tests (benchmarks/RUNBOOK.md) run once per minor version as the
evidence behind public claims, not as the tuning loop.

## 8. Releases and openness

- The library is developed in the open on `main`. A minor version is
  released only when its phase exit criteria pass.
- A release is a tag `vX.Y.Z` on the exact build commit. The release
  workflow builds it and publishes to PyPI through trusted publishing.
- The MCP registry entry (`io.github.random-orbit/chemglyph`) is updated
  by hand after each release (docs/registry_publish.md).
- Kept out of the repository: blind-test pair keys, grader data, reference
  panels, secrets, and any future hosted or commercial service code, which
  lives in a separate private repository.
- The library never sends telemetry.

## 9. Non-goals

No structure editor, no 3D, no property prediction or retrosynthesis, no
automatic mechanism or product inference, no default network access, no 2D
layout algorithm written from scratch (RDKit and Indigo do layout;
ChemGlyph chooses, templates, and repairs), and no special representations
for biopolymers.
