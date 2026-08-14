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

## 4. Reference panel protocol (ChemDraw or Ketcher)

The reference panels are the "opponent" side of every pair. ChemDraw
Professional is the preferred tool, but the same procedure works with
[Ketcher](https://lifescience.opensource.epam.com/ketcher/), a free,
open-source editor, when ChemDraw is not available. Record which tool made
the panels in the run log; the methodology sentence then reads "reference
editor (ChemDraw or Ketcher)".

Produce two panels per molecule, saved locally under
`benchmarks/chemdraw_panels/` (this directory is gitignored — **never commit
the panels**):

- `chemdraw-acs/{label}.svg|.png` — apply the ACS Document 1996 settings
  (fixed bond length, Arial labels, black on white) to mirror `chemglyph-acs`.
- `chemdraw-modern/{label}.svg|.png` — ChemDraw defaults, white background,
  heteroatoms recolored to match `chemglyph-modern` (classic CPK: O `#FF0D0D`,
  N `#3050F8`, S `#E8C300`, Cl `#1FB01F`). If per-atom recoloring is too
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

### Automated Indigo reference panels (no ChemDraw/Ketcher UI)

When hand-made ChemDraw panels are unavailable, `benchmarks/reference_panels.py`
produces scripted reference panels with Indigo, the Apache-2.0 engine behind
Ketcher. Install it with `pip install epam.indigo` (already in the `dev`
extra) and run:

```bash
python benchmarks/reference_panels.py
```

The script writes `benchmarks/blind_review/reference_sheet_page{1,2}.png`
(gitignored): one row per molecule, columns reference | chemglyph acs |
chemglyph modern, with every engine normalized to the same ~30 px mean bond
length. Indigo settings mirror Ketcher's look: white background,
`terminal-hetero` labels (explicit CH3), bond length 30 px, line width
1.0 px.

Use the sheets as the maintainer's tuning anchor only. They are not a blind
deck and graders must never see them; the official blind run still uses
hand-made ChemDraw/Ketcher panels mixed into the shuffled figure set per the
rules above.

### Ketcher export checklist

When Ketcher replaces ChemDraw, follow the same rules with these steps:

1. Open the Ketcher demo page and clear the canvas.
2. In the top-left menu, open the structure window and paste the SMILES from
   `answer_key.json` ("Paste" accepts SMILES). Do not hand-draw from the
   label.
3. Choose the canvas size and atom styling to mirror the ChemGlyph style
   (`acs`: black on white; `modern`: recolored heteroatoms if the UI allows,
   otherwise monochrome and note that color was excluded from judging).
4. File -> Save as SVG, named per the panel protocol above. Export PNG as
   well (Ketcher offers PNG export) and keep both.
5. Do the same parity check as ChemDraw before mixing: display the pair side
   by side and normalize the display scale so mean bond lengths match.

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

For each pair the grader records one of: `A`, `B`, `tie` (no real
preference), or `neither` (both fall short), plus optional free-text notes.
The four porphyrin/ferrocene pairs are shown and marked excluded; grader
notes on them are recorded as known limitations instead of being scored.

## 7. Scoring and pass criteria

- Eligible denominator: 40 − 4 = **36 pairs** (18 molecules × 2 styles).
- Per grader: `(chemglyph picks + 0.5 × ties) / 36`. A `neither` vote scores
  0 for ChemGlyph and the pair still counts in the denominator; a pair is
  only excluded when it is in the known-limitation list or its reference
  panel is unusable, never because both figures scored badly.
- Aggregate: mean across graders. **Pass: aggregate ≥ 40%.**
- Report breakdowns per style (`acs`, `modern`) and per molecule. Molecules
  where every grader preferred the reference figure, or that drew `neither`
  votes, become the style fix list.
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
