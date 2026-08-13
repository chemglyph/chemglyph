# Blind test runbook (ChemDraw comparison)

This is the operational procedure for the manual half of the §11 blind test:
preparing ChemDraw panels, mixing them with ChemGlyph figures, running the
blind review, and recording the result. It is executed by the maintainer as
**proctor**; grading is done by 2–3 chemical practitioners who never see this
repository.

## 1. What the test decides

Two panels per (molecule, style) pair — one ChemGlyph, one ChemDraw. Graders
pick the figure they would publish. The pass criterion from §11:

- ChemGlyph selection rate ≥ 40% across eligible pairs.
- `porphyrin-free-base` and `ferrocene` (4 of 40 pairs) are excluded from the
  denominator and recorded separately as known limitations.

A passing run authorizes the README to state the result. A failing run
triggers style tuning and a rerun — molecules are never removed from the
denominator to make the numbers pass.

## 2. Eligibility and blinding

- Grader profile: chemist with publication-figure experience (e.g. grad
  student, postdoc, industry chemist). Minimum 2 graders, target 3.
- **Anyone with access to this repository is disqualified** — including the
  maintainer and any prior contributor. The answer key is committed here, so
  repo access breaks the blind.
- Graders are recorded only as `G1`, `G2`, `G3`. No names, institutions, or
  emails appear in any committed artifact.
- The proctor must not grade; a grader must never see `pair_key.json`, the
  answer key, or the unshuffled figure directory.

## 3. Pin the version and regenerate the figure set

1. Create a clean venv and install the exact released wheel:
   `pip install chemglyph==<X.Y.Z>`.
2. Record `git rev-parse HEAD`, `chemglyph.__version__`, and
   `rdkit.__version__` in the run log.
3. Generate the set with a fresh seed:

   ```bash
   python benchmarks/generate_blind_test.py \
     --out benchmarks/blind_test_output --seed <YYYYMMDD>
   ```

4. Verify: 40 figures; every entry in `answer_key.json` has `png_status: ok`
   except documented degradations; `chemglyph_version` and `rdkit_version`
   fields are present.
5. Copy `answer_key.json` to a local archive (it is overwritten by the next
   regeneration). Keep the archived copy tied to the exact reviewed set.

## 4. ChemDraw panel protocol

Tool: ChemDraw Professional. Produce two panels per molecule, saved locally
under `benchmarks/chemdraw_panels/` (this directory is gitignored — **never
commit the panels**):

- `chemdraw-acs/{label}.svg|.png` — apply the ACS Document 1996 settings
  (fixed bond length, Arial labels, black on white) to mirror `chemglyph-acs`.
- `chemdraw-modern/{label}.svg|.png` — ChemDraw defaults, white background,
  heteroatoms recolored to match `chemglyph-modern` (O `#D62728`,
  N `#1F77B4`, S `#C78F00`, Cl `#2CA02C`). If per-atom recoloring is too
  laborious, a monochrome panel is an acceptable fallback: record that color
  was excluded from judging for that style.

Rules:

- Paste the canonical SMILES from `answer_key.json` into ChemDraw rather than
  hand-drawing from the label, so topologies stay identical.
- Export SVG (preferred) plus PNG at ≥ 300 DPI; keep both.
- Parity check before mixing: display each ChemGlyph/ChemDraw pair side by
  side and normalize display scale so mean bond lengths are comparable. The
  test judges typography and layout, not export resolution.
- If a ChemDraw panel cannot be produced for a molecule (porphyrin and
  ferrocene may behave oddly), still include the pair and record a note.

## 5. Mixing and blinding (proctor only)

1. Build 40 pairs: for each (molecule, style), take the ChemGlyph panel and
   the ChemDraw panel and shuffle them into A/B under a fresh random seed.
2. Record the mapping in local-only `benchmarks/blind_review/pair_key.json`
   (gitignored): pair id → molecule, style, `A` engine, `B` engine.
3. Assemble the grading deck: one page per pair showing only the pair id and
   panels A and B at equal size. No engine names, no molecule names, no
   styling cues beyond the panels themselves.
4. Graders may work in different orders (independently shuffled decks are
   recommended to cancel ordering effects) but must not discuss answers
   before all sheets are submitted.

## 6. Grading protocol

For each pair the grader records one of: `A`, `B`, or `tie` (no preference),
plus optional free-text notes. The four porphyrin/ferrocene pairs are shown
and marked excluded; grader notes on them are recorded as known limitations
instead of being scored.

## 7. Scoring and pass criteria

- Eligible denominator: 40 − 4 = **36 pairs** (18 molecules × 2 styles).
- Per grader: `(chemglyph picks + 0.5 × ties) / 36`.
- Aggregate: mean across graders. **Pass: aggregate ≥ 40%.**
- Report breakdowns per style (`acs`, `modern`) and per molecule. Molecules
  where every grader preferred ChemDraw become the style fix list.
- On failure: tune the offending style(s), regenerate only the affected
  figures under a new seed, and rerun the full protocol.

## 8. After the review

1. Commit only aggregate, anonymized results as `benchmarks/results.json`
   (schema in §10) plus a short summary in `benchmarks/README.md`.
2. Update the README status line: replace "Blind test vs ChemDraw: pending"
   with the date, grader count, selection rate, and the porphyrin/ferrocene
   limitation note.
3. Add the ChemDraw panels to the README comparison sheet in
   `scripts/generate_docs_images.py` (third column), regenerate
   `docs/images/comparison_vs_rdkit.png`, and commit it.
4. Tick the blind-test items in `docs/progress/M4.md` and add a dated entry
   there or in `docs/progress/REVIEW-1.md`.
5. Keep `pair_key.json` and raw grader sheets local; archive or delete them
   after the result is published (30 days suggested).

## 9. Hygiene checks

- A grader with repo access invalidates their sheet; replace them.
- A pair with a missing or broken ChemDraw panel is excluded from the
  denominator and recorded.
- Never commit: ChemDraw panel files, `pair_key.json`, raw grader sheets, or
  grader identities.

## 10. `benchmarks/results.json` schema (committed)

```json
{
  "run_date": "YYYY-MM-DD",
  "chemglyph_version": "X.Y.Z",
  "rdkit_version": "YYYY.MM.P",
  "git_sha": "full-sha",
  "seed": 12345678,
  "num_graders": 3,
  "eligible_pairs": 36,
  "selection_rate": 0.55,
  "pass": true,
  "per_style": {"acs": 0.60, "modern": 0.50},
  "per_molecule": {"benzoic-acid": 0.83, "...": 0.0},
  "notes": ["porphyrin and ferrocene recorded as known limitations"]
}
```
