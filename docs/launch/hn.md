# Show HN: ChemGlyph, chemical structures and reactions that look publishable

ChemGlyph is a Python library and MCP server that turns SMILES and reaction
schemes into clean SVG figures. Think KaTeX for chemistry.

What's in it:

- Three presets: an ACS-style black and white, a colored style for screens,
  and a heavy-line textbook style. Transparent backgrounds by default.
- A reaction layout engine that draws plus signs, conditions above and below
  arrows, yields, equilibrium and retro arrows, and wraps long schemes.
  RDKit's own reaction renderer doesn't offer that control, so the layout
  part is written from scratch. RDKit still does parsing and 2D depiction.
- Four MCP tools so Claude Desktop and other agents can draw structures
  instead of emitting ASCII or hand-rolled SVG.
- A small validation layer with four quick fixes (bracket and ring
  mismatches, lowercase aromatics that won't kekulize, nitrogen valence).
  No "is this molecule real" judgment.

The thing I keep going back and forth on: is a rendering/validation/interface
layer on top of RDKit a real category, or is this mostly solving my own
GC-MS workbench problem? There's a blind test in the repo: 20 fixed
molecules, shuffled figures, practitioners pick what they'd publish against
an open-source reference renderer (Indigo, the engine behind Ketcher). The
molecule list, deck generator, runbook, and scorer are all in the repo, so
anyone can run the protocol and contribute results. The test is pending, not
passed, and no ChemDraw comparison has been made.

Repo: https://github.com/chemglyph/chemglyph (MIT, Python 3.11+, RDKit
2024.9+). Feedback on the style defaults and the reaction JSON schema is
welcome.
