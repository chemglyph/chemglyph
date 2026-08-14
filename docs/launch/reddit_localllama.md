# An MCP server that draws molecules and reactions for local LLM agents

Agents are fine at emitting SMILES and bad at drawing molecules. ChemGlyph
(https://github.com/chemglyph/chemglyph) is an MCP server and Python library
that renders structures and reaction schemes.

Four tools, with docstrings written for the model:

- `render_molecule`: SMILES/InChI/molblock to SVG or PNG, plus formula,
  molecular weight, and warnings
- `render_reaction`: a JSON schema for synthesis routes with conditions,
  yields, equilibrium and retro arrows, and line wrapping
- `validate_structure`: errors plus a small set of automatic SMILES fixes
- `parse_name`: English names via OPSIN, Chinese names via a built-in
  dictionary, all offline

Details that might matter to agent builders: conditions are pre-formatted
Unicode text (the caller passes H₂SO₄, the tool never parses formulas), all
errors share one base type, there is no telemetry, and the SVG comes back as
an MCP image block plus text metadata.

It only does rendering, validation, and naming. No structure editor, no
retrosynthesis. MIT licensed. What else should an agent-facing chemistry
tool expose?
