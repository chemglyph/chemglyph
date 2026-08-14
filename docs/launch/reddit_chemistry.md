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
   20-molecule blind test with a documented pass criterion (40% or more
   chosen by practitioners). Ferrocene and free-base porphyrin are recorded
   as known limitations and excluded from the count. The blind test against
   ChemDraw is still pending; the ChemDraw panels are added by hand before
   the review.
2. Which quick-fix validation rules come up in your real workflows? There
   are four today: unmatched brackets/rings, lowercase aromatics that fail
   kekulization, and nitrogen valence via [N+]. There is deliberately no
   "does this molecule exist" judgment.

MIT licensed, offline, no database calls. Harsh feedback on the schema and
defaults is welcome.
