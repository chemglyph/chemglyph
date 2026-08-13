# Giving local LLM agents first-class chemistry rendering: an MCP server

Agents are fine at emitting SMILES and bad at drawing molecules. ChemGlyph
(https://github.com/random-orbit/chemglyph) is an MCP server + Python library
that gives them publication-quality structure and reaction rendering.

Four tools, each docstring written for the model ("use this when..."):

- `render_molecule` — SMILES/InChI/molblock → SVG/PNG + formula, MW, warnings;
- `render_reaction` — a JSON schema for synthesis routes with conditions,
  yields, equilibrium/retro arrows, and line wrapping;
- `validate_structure` — errors plus a small set of automatic SMILES fixes;
- `parse_name` — English IUPAC/common names → SMILES (offline via OPSIN).

Design choices LLM folks may appreciate: conditions are pre-formatted Unicode
text (the caller passes "H₂SO₄", the tool never parses formulas); all errors
share one base type; everything is offline with no telemetry; and the SVG
comes back as an MCP image content block plus text metadata.

It's the rendering/validation/interface slice only — explicitly not a
structure editor or retrosynthesis tool. MIT licensed. Would love feedback
on the tool surface: what else should an agent-facing chemistry tool expose
that I'm missing?
