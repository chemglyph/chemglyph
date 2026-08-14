# A rendering layer for publication-grade structures and reactions (MIT, RDKit-based)

Hi r/chemistry. I built a small tool and would like a critical look at
whether the defaults actually hold up to "would you put this figure in a
paper".

ChemGlyph (https://github.com/chemglyph/chemglyph) renders single molecules
and reaction schemes to SVG or PNG with three presets:

- `acs`: monochrome, tuned bond widths and label sizes
- `modern`: colored heteroatoms for screens and chat
- `textbook-cn`: heavy black lines, larger labels

The reaction engine handles plus signs, conditions above and below arrows,
yields, equilibrium and retro arrows, and wrapping for long schemes. RDKit's
built-in reaction image doesn't offer that layout control, so that part is
custom code while RDKit does parsing and depiction.

Two questions:

1. Are the style defaults right, or cosmetically off? The repo includes a
   20-molecule blind test with a documented pass threshold (see
   benchmarks/RUNBOOK.md); the deck pairs each figure against an open-source
   reference renderer (Indigo, the engine behind Ketcher), and the whole
   procedure is open-sourced so anyone can run it and submit results.
   Ferrocene and free-base porphyrin are recorded as known limitations and
   excluded from the count, along with paclitaxel (no clean 2D layout in
   RDKit). The blind test is pending, not passed; no ChemDraw comparison has
   been made.
2. Which quick-fix validation rules come up in your real workflows? There
   are four today: unmatched brackets/rings, lowercase aromatics that fail
   kekulization, and nitrogen valence via [N+]. There is deliberately no
   "does this molecule exist" judgment.

MIT licensed, offline, no database calls. Harsh feedback on the schema and
defaults is welcome.
