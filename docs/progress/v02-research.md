# v0.2 research: mechanism arrows & Chinese naming

Two roadmap items need a design decision before implementation. Both are
written against ChemGlyph's hard constraints: offline by default, no extra
runtime dependencies, SVG assembled with the standard library, and LLM callers
that cannot supply pixel coordinates.

## 1. Mechanism (electron-pushing) arrow rendering

### Context and constraints

Mechanism arrows are curved "curly" arrows that show electron movement between
atoms or bonds. RDKit gives us exactly what we need for anchor points: the 2D
conformer coordinates of every atom (bond midpoints follow trivially). RDKit
does not give lone-pair positions; those must be derived geometrically from
the neighbors of the source atom.

### Arrow geometry

An arrow is a cubic Bezier path. With `P0` (source anchor) and `P3` (target
anchor), choose two control points so the curve bows around the midpoint. A
simple, predictable rule:

- `curve = -1..1` (or `"auto"`): sign selects bow direction, magnitude the
  depth (default depth ~25% of chord length).
- `"auto"` picks the side with more open space, or defaults clockwise.

Arrowheads: `"pair"` (double-barbed, two electrons) and `"single"`
(single-barbed, radical). Both are small polygons at the curve end, oriented
by the final tangent. This is ~30 lines of SVG math in `svg_utils.py`.

### Anchoring options

| Option | Schema | Verdict |
|---|---|---|
| A. Structural anchors | `{"from": {"atom": 5}, "to": {"bond": 3, "side": "left"}}` | Recommended: LLMs reason in atom/bond indices, and the renderer owns all geometry. |
| B. Explicit coordinates | `{"from": {"x": 120, "y": 40}, ...}` | Reject for LLM callers; useful only as an internal escape hatch. |
| C. Fully automatic | arrows inferred from the chemistry | Explicitly out of scope; ChemGlyph renders, it does not infer mechanisms. |

For bond targets, `side` resolves which side of the bond line the arrow lands
on. Lone pairs get a derived offset (bisector of neighbor directions), which
needs visual tuning but no new data.

### Recommended MVP schema (v0.3)

One mechanism = an ordered list of frames; each frame is a full molecule state
plus the arrows leading to the next state. The caller provides every
intermediate's complete SMILES; ChemGlyph never mutates a structure:

```json
{
  "mechanism": {
    "frames": [
      {
        "structure": "CC(=O)O",
        "arrows": [
          {"from": {"atom": 4}, "to": {"atom": 2}, "kind": "pair", "curve": "auto"}
        ]
      },
      {
        "structure": "CC(=O)[O-]"
      }
    ]
  }
}
```

Rendering: each frame renders as a normal molecule; arrows from frame N are
drawn on top of frame N pointing toward frame N+1. MVP renders frames as a
horizontal strip (reuse the reaction row layout). Charges are simply drawn by
RDKit from the SMILES; a `charges` delta map is therefore not required for the
MVP and is listed as an open question.

Explicit non-goals: transition states, 3D, orbital diagrams, automatic
mechanism generation.

### TODO(question)

- Should `charges` deltas be an explicit schema field (for callers that want
  to describe charge movement without restating the whole molecule), or is
  "caller provides the next frame's full SMILES" the better contract?
- Lone-pair placement heuristic: bisector of neighbors, or a fixed offset
  from the atom center at a radius proportional to bond length?
- Do reviewers want electron-pair dots on the source atom, or is the
  double-barbed arrowhead sufficient for v0.3?

## 2. Chinese chemical name-to-structure

### Problem

`parse_name` (v0.1) resolves English IUPAC/common names offline via OPSIN.
Chinese names are deliberately `NotImplementedError` ("planned for v0.2").
The difficulty: OPSIN has no Chinese support, and the offline constraint
excludes calling any online translator or PubChem API.

### Options

1. **Offline MT pipeline** (Chinese -> English -> OPSIN). Requires bundling an
   offline NMT model (hundreds of MB, model licensing, tokenizer assets).
   Chemical names are also a specialized register where general MT is
   unreliable ("苯甲酸乙酯" -> "ethyl benzoate" is fine; many systematic names
   are not). Not viable for v0.2.
2. **Rule-based Chinese parser.** A real project (morpheme splitting, 官能团
   ordering, locant reassembly) with low coverage and a long tail of edge
   cases. Not viable as a fast win.
3. **Curated dictionary** (Chinese name -> SMILES). A small, high-value
   starting set (common lab reagents, the 20 blind-test molecules, common
   drugs) is achievable and fully offline. Larger open datasets exist but
   their provenance/licensing needs checking before redistribution.
4. **Pluggable translator hook.** Keep the core offline; let the host inject a
   `name_translator` callable. ChemGlyph itself never makes network calls, so
   the non-goal is preserved at the library level.

### Recommendation

Ship **(3) + (4)** for v0.2: an opt-in `chemglyph[zh]` data extra with a small
curated dictionary plus a translator hook; the default error message explains
both options and continues to point users at English names. If the advisor
insists on automatic Chinese parsing, it should be its own milestone with a
dedicated data budget rather than a v0.2 patch.

### TODO(question)

- Is a caller-provided translator hook consistent with "no online database
  queries", given the host could attach an online translator?
- Which dictionary source (if any) has a license compatible with bundling in
  an MIT project, and what is the minimum vocabulary for the first data extra?
