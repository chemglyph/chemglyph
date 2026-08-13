# Reaction JSON schema

`chemglyph.render_reaction(spec)` accepts the JSON document described in
§6.1 of the project specification.

```json
{
  "steps": [
    {
      "reactants": ["OC(=O)c1ccccc1O", "CC(=O)OC(C)=O"],
      "products": ["CC(=O)Oc1ccccc1C(=O)O"],
      "conditions": {"above": "H₂SO₄ (cat.)", "below": "rt, 15 min"},
      "yield": "89%",
      "arrow": "forward"
    }
  ],
  "style": "modern",
  "layout": {"max_width": 1200, "align": "arrow"}
}
```

## Fields

- `steps` (required, non-empty array): one object per reaction step.
  - `reactants` / `products` (required, non-empty arrays of strings): SMILES,
    InChI, or molblock, exactly as accepted by `render_molecule`.
  - `conditions` (optional): `above` / `below` strings, shown above/below the
    arrow. **Pre-formatted Unicode text only** — the caller (an LLM or a
    formatting library) is responsible for subscripts like `H₂SO₄`; ChemGlyph
    does not parse formulas out of plain text.
  - `yield` (optional): appended to the below-the-arrow text in parentheses,
    e.g. `rt, 15 min (89%)`.
  - `arrow` (optional, default `forward`): `forward`, `equilibrium` (⇌), or
    `retro` (double line pointing left).
- `style` (optional, default `modern`): one of `acs`, `modern`, `textbook-cn`.
- `layout` (optional):
  - `max_width` (default `1200`): horizontal budget in SVG user units. When a
    step would overflow it, the row wraps: the current row ends with a
    down-pointing arrow and the next row redraws the intermediates once,
    followed by the step's normal arrow.
  - `align` (`"arrow"` or omitted): with `"arrow"`, every row is shifted
    right so each row's first arrow shares one vertical axis. Default is
    left-aligned rows. Fragments are always centered on the row midline.

## Continuation rule

When step N's products and step N+1's reactants resolve to the same set of
canonical SMILES (any order), the intermediates are not drawn twice within a
row. Note the comparison is set equality: a byproduct in step N's products
prevents the merge.

## Output

One SVG document with a transparent background, `viewBox` tightly bounding the
content plus a 16px margin. Layout elements carry machine-readable classes:
`chemglyph-fragment`, `chemglyph-plus`, `chemglyph-arrow`,
`chemglyph-arrow-forward|equilibrium|retro`, `chemglyph-arrowhead`,
`chemglyph-arrow-down`, `chemglyph-condition`. Condition and yield labels use
the active style's label scale (half its `maxFontSize`, clamped to 12-20
units).
