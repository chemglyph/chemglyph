# Show HN: ChemGlyph — publication-quality chemical rendering for AI agents

ChemGlyph is a Python library + MCP server that turns SMILES and reaction
schemes into publication-quality SVGs. Think "KaTeX for chemistry".

- Three tuned styles: ACS-journal monochrome, a screen-friendly colored
  style, and a bold textbook style. All with optional transparency.
- A reaction layout engine that does plus signs, condition labels above and
  below arrows, yields, equilibrium/retro arrows, and line wrapping. RDKit's
  stock reaction renderer doesn't give you that control, so this part is
  built from scratch (RDKit remains the parsing/depiction core).
- Four MCP tools (render_molecule, render_reaction, validate_structure,
  parse_name), so Claude Desktop and other agents can draw chemistry natively
  instead of guessing at ASCII or bespoke SVG.
- A validation layer with deliberately narrow quick fixes (bracket/ring
  mismatches, kekulization of lowercase aromatics, nitrogen valence) and
  explicit non-goals: no editor GUI, no retrosynthesis, no online databases.

The part I'm most curious about: is "rendering layer + validation layer +
interface layer, reusing RDKit underneath" a real category, or is this
mainly solving my own GC-MS workbench problem? We're running a blind test —
20 fixed molecules, shuffled figures, chemical practitioners pick what
they'd publish — and the repo documents the pass criteria (>40% selection).
The ChemDraw comparison panels are still being added manually, so the blind
test is pending, not passed; the methodology is in the README.

Repo: https://github.com/chemglyph/chemglyph (MIT, Python >= 3.11,
RDKit >= 2024.9). Feedback on the style presets and the reaction schema
especially welcome.
