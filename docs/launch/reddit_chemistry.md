# I built a rendering layer for publication-quality structures & reactions (MIT, RDKit-based)

Hi r/chemistry — I'd appreciate a critical look at a small open-source tool
aimed squarely at "would you put this figure in a paper".

ChemGlyph (https://github.com/chemglyph/chemglyph) renders single
molecules and reaction schemes to SVG/PNG with three presets:

- `acs` — monochrome, tuned bond widths and label sizes;
- `modern` — colored heteroatoms for screens/chat;
- `textbook-cn` — heavy black lines, larger labels.

The reaction engine draws plus signs, above/below conditions, yields,
equilibrium and retro arrows, and wraps long schemes — RDKit's built-in
reaction image doesn't offer that layout control, so the layout code is ours
while RDKit does parsing and depiction.

Two questions for you:
1. Are the style defaults actually publication-grade, or cosmetically off?
   The repo includes a 20-molecule blind test and a documented pass
   criterion (≥40% chosen by practitioners); ferrocene and free-base
   porphyrin are recorded as known limitations rather than counted. The
   blind test vs ChemDraw is still pending — the methodology is in the
   README and the ChemDraw panels are added manually before the review.
2. What quick-fix validation rules do you actually hit in real workflows?
   We currently implement only four (unmatched brackets/rings, lowercase
   aromatic kekulization, nitrogen valence via [N+]) and deliberately do not
   judge "is this molecule real".

Pure MIT, offline, no database calls. Happy to take harsh feedback on the
schema and defaults.
