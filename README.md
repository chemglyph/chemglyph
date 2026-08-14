# ChemGlyph

Publication-quality chemical structure and reaction rendering for AI agents.
ChemGlyph is the KaTeX of chemistry: a rendering layer, a validation layer,
and an MCP interface on top of [RDKit](https://www.rdkit.org).

[![CI](https://github.com/chemglyph/chemglyph/actions/workflows/ci.yml/badge.svg)](https://github.com/chemglyph/chemglyph/actions/workflows/ci.yml)

## Install

```bash
pip install chemglyph
```

## Render a molecule

```python
import chemglyph

result = chemglyph.render_molecule("c1ccccc1")  # benzene
open("benzene.svg", "w").write(result.data)
```

`render_molecule` takes SMILES, InChI, or molblock and returns SVG (or PNG)
plus `canonical_smiles`, `mol_formula`, `mol_weight`, and `warnings`.

## Styles

Three styles, same molecule (benzoic acid, caffeine, (S)-ibuprofen):

![ChemGlyph style gallery](docs/images/gallery_3x3.png)

```python
chemglyph.render_molecule(smiles, style="acs")  # black/white, ACS journal
chemglyph.render_molecule(smiles, style="modern")  # colored heteroatoms, screens
chemglyph.render_molecule(smiles, style="textbook-cn")  # bold monochrome, textbook
```

All styles default to a transparent background (`transparent=True`) and
support `fmt="png"`.

## Reactions

```python
spec = {
    "steps": [
        {
            "reactants": ["OC(=O)c1ccccc1O", "CC(=O)OC(C)=O"],
            "products": ["CC(=O)Oc1ccccc1C(=O)O", "CC(=O)O"],
            "conditions": {"above": "H₂SO₄ (cat.)", "below": "rt, 15 min"},
            "yield": "89%",
            "arrow": "forward",
        }
    ],
    "style": "modern",
}
svg = chemglyph.render_reaction(spec)
```

Conditions are pre-formatted Unicode text, so pass `H₂SO₄`, not `H2SO4`.
ChemGlyph does not parse formulas out of text. The full schema
(multi-step chains, equilibrium and retro arrows, line wrapping) is in
[docs/reaction_schema.md](docs/reaction_schema.md).

The aspirin demo writes a two-step route:

```bash
python examples/aspirin_synthesis.py  # writes examples/aspirin_synthesis.svg
```

## Validation

`validate_structure` reports parse errors and applies four quick fixes:
unmatched brackets and ring closures (reported, not guessed), kekulization
failures of lowercase aromatic atoms, and nitrogen valence errors via a
formal `[N+]`. Anything else passes RDKit's message through unchanged.

```python
report = chemglyph.validate_structure("c1cccc1")
report.fixes[0].description  # 'lowercase aromatic atoms could not be kekulized...'
report.fixes[0].fixed_smiles  # 'C1CCCC1'
```

## Naming

```python
chemglyph.parse_name("aspirin")  # 'CC(=O)Oc1ccccc1C(=O)O'
```

English IUPAC and common names resolve offline through OPSIN
(`pip install 'chemglyph[opsin]'`, plus a Java runtime). Chinese names use
the built-in dictionary, and the library API accepts a translator callable
for names that are not in it:

```python
chemglyph.parse_name("阿司匹林")  # 'CC(=O)Oc1ccccc1C(=O)O'
chemglyph.parse_name("六甲基苯", translator=to_english)
```

ChemGlyph itself never calls an online service, including for translation.

## MCP server

Run the bundled console script (stdio transport):

```bash
chemglyph-mcp
```

Claude Desktop registration (macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "chemglyph": {
      "command": "chemglyph-mcp"
    }
  }
}
```

| Tool | Use it when | Returns |
|---|---|---|
| `render_molecule` | the user asks to draw one structure from SMILES/InChI/molblock | SVG or PNG image plus formula, MW, warnings |
| `render_reaction` | the user asks for a reaction or synthesis route | reaction SVG image |
| `validate_structure` | a SMILES may be malformed and you need a repair | validation report JSON |
| `parse_name` | the user gives a name like "aspirin" instead of SMILES | canonical SMILES or an error |

## Benchmarks

`benchmarks/` holds the fixed 20-molecule blind test and a generator that
writes shuffled, numbered PNG/SVG figures plus `answer_key.json`:

```bash
python benchmarks/generate_blind_test.py --seed 1234
```

Pass criteria: two or three chemical practitioners blind-pick the figures
they would publish; ChemGlyph passes at 40% or higher. Ferrocene and the
free-base porphyrin are excluded from the denominator and recorded as known
limitations. The procedure is documented in
[benchmarks/RUNBOOK.md](benchmarks/RUNBOOK.md).

![ChemGlyph vs RDKit default](docs/images/comparison_vs_rdkit.png)

Blind test vs ChemDraw: pending. The image above compares ChemGlyph `modern`
with RDKit's stock output; ChemDraw panels are added by hand during the
review, and the image is regenerated afterwards.

## Roadmap

- v0.2: Chinese naming (built-in dictionary plus translator hook), down-arrow
  line wrapping, arrow column alignment, cropped fragments. All shipped.
- Next: mechanism (electron-pushing) arrows, see
  [docs/progress/v02-research.md](docs/progress/v02-research.md).
- Later: a larger Chinese dictionary as an optional data extra.

## Non-goals

No structure editor GUI (Ketcher/ChemDraw competition), no 3D visualization,
no retrosynthesis or property prediction, no online database queries, and no
automatic mechanism generation. The full list is in the project
specification.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/ruff check . && .venv/bin/ruff format . && .venv/bin/pytest
```

Python 3.11+, RDKit 2024.9+, MIT license. All errors derive from
`chemglyph.errors.ChemGlyphError`.
