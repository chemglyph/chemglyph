# REVIEW-1 — External advisor review response

Date: 2026-08-13. Scope: P0 email forensics, P1 release consistency, P2
quality confirmations. Ordered P0 -> P2 as requested.

## P0-1: The force-pushed initial commit

Verified via the commits API after the `--force-with-lease`:

- The commit object **is still publicly readable by SHA**. The API returns it
  with author email = the third-party mailbox (address redacted here; the full
  SHA and address are kept in the maintainer's private notes, not in this
  public repository).
- A compare against `main` returns "No common ancestor": the commit is no
  longer reachable from any branch or tag, but GitHub serves unreferenced
  objects by SHA indefinitely.
- the repository events API and the user's public activity feed (queried
  before the 2026-08-13 transfer to the chemglyph organization) show
  `PushEvent`/`CreateEvent` records for the day, but their `commits` arrays
  are empty — **no SHA residue in the event stream**.

Exposure assessment: the mailbox is not on any branch, not in any event
payload, and not on the account profile (`public_email` is null). Its one
public exposure is the dangling commit object itself, reachable by anyone who
knows its SHA. The SHA is short-lived knowledge (created during repo setup and
force-pushed within minutes), so this is a narrow but real leak that a
server-side purge can close.

## P0-2: Full sweep

| Surface | Finding |
|---|---|
| chemglyph git authors/committers (all refs) | only `305297779+random-orbit@users.noreply.github.com` |
| chemglyph file contents across history | the mailbox appeared literally in `docs/progress/M0.md` from the M1 commit onward (our own incident note) — see P0 remediation below |
| chemglyph Actions logs (7 runs, raw logs) | only the noreply alias (author-check step); no mailbox or personal emails |
| PR #12063 title/body/comments | clean; no email strings |
| NetBerth `netberth` repo history | **collateral finding**: 13 commits and `refactor-report-v7.md`/`refactor-report-v8.md` contain a personal Gmail address (address redacted from this public report; details in the maintainer's private notes) in the public `netberth/netberth` repository — pre-existing, not caused by ChemGlyph, out of ChemGlyph scope, flagged to the maintainer |
| NetBerth `netberth-public` / `netberth-quarantine` | clean |
| `random-orbit` profile | `public_email` is null |

Remediation already applied (safe, non-destructive):

- `docs/progress/M0.md` no longer contains the literal address; the wording
  now describes it as a redacted third-party mailbox.
- This redaction is committed and pushed (normal commit, no history rewrite).

Remaining exposure: the address string is still in the **blobs of past
commits** (`docs/progress/M0.md` at older SHAs), plus the dangling initial
commit object. Fully closing it requires the P0-3 actions.

## P0-3: Should we ask GitHub Support to purge the dangling commit?

Recommendation: **yes, do it, but sequence it after an explicit approval for a
history rewrite** — a purge alone is insufficient because the mailbox also
lives in old blobs of the rewritten-out history.

Proposed sequence (executed on 2026-08-13 after maintainer approval — see the
execution log below):

1. `git filter-repo` (or equivalent) over `--all` to strip the address string
   from every blob, then `git push --force-with-lease origin main`.
2. Open a GitHub Support request to purge unreferenced objects (the original
   auto-generated commit plus every pre-rewrite SHA).
3. Re-verify via the commits API that all old SHAs 404.

Pros:

- Closes the only confirmed public leak of that mailbox.
- Rewritten history keeps all content, authorship (noreply), and messages.

Cons / costs:

- All SHAs change; anyone who bookmarked a commit URL loses it. No forks,
  releases, or downstream consumers exist yet, so this cost is near zero now
  and grows over time — do it early.
- Force-push needs `main` branch protection off (none configured yet).
- Support purges are best-effort and may take days; if refused, the nuclear
  fallback is delete-and-recreate the repository (nothing to lose yet).

Not recommended: leaving it as-is and relying on obscurity.

## P0-4: Account settings checklist

Confirmed in [M0.md](M0.md) maintainer checklist:

- [ ] Settings -> Emails: "Keep my email addresses private"
- [ ] Settings -> Emails: "Block command line pushes that expose my email"
- [ ] Set the public email to the noreply alias

## P1-5: Comparison image and launch wording

The comparison image is ChemGlyph `modern` vs **stock RDKit**, not ChemDraw.
Audited README and all three launch drafts for claims of a ChemDraw comparison
or a passed blind test:

- README caption now reads "**Blind test vs ChemDraw: pending — methodology
  below**" and states the ChemDraw panels are added manually before the review.
- `hn.md` and `reddit_chemistry.md` now say the blind test is pending, not
  passed; no draft implied a ChemDraw comparison.

## P1-6: PyPI vs PR #12063

- `pypi.org/pypi/chemglyph/json` returns 404: the package is **not published**.
- PR #12063's body and the linked README both guide `pip install chemglyph`.
- Action taken: the PR is now a **draft** and carries a comment explaining
  that it will be restored once PyPI 0.1.0 is live
  (comment: https://github.com/punkpeye/awesome-mcp-servers/pull/12063#issuecomment-5281505930).
- Restore steps: publish 0.1.0, verify `pip install chemglyph` works, then
  `gh pr ready 12063 --repo punkpeye/awesome-mcp-servers` and post a
  ready-now comment.

## P1-7: RDKit minimum version

- Declared floor was `rdkit>=2024.9`, but only 2026.3.5 had been tested.
- Chose option (a): verified the floor for real in a throwaway venv with
  `rdkit==2024.9.4`. One genuine incompatibility surfaced and was fixed
  (older RDKit emits an opaque white background rect even for an alpha-0
  background color; the transparent-background strip now removes the first
  rect element on every version).
- Full suite now passes on both 2024.9.4 and 2026.3.5 (58 passed, 1 skipped
  for the optional OPSIN path).
- CI gained a `test-minimum-rdkit` job (ubuntu, Python 3.11,
  `rdkit==2024.9.4`, full pytest) so the floor stays verified.

## P1 (addendum): Repository transfer to the chemglyph organization

On 2026-08-13 the repository moved from the alias account to
`github.com/chemglyph/chemglyph`. Follow-up completed:

- `git remote set-url origin https://github.com/chemglyph/chemglyph.git`;
  `git push origin main` succeeded (push permission verified, refs intact).
- Replaced the old owner/repo path in `pyproject.toml` (new `[project.urls]`
  block), README (links + CI badge), the three launch drafts, and the
  historical references in M0.md/this file. `docs/claude_desktop_config.json`
  contains no repository URL, so nothing to change there.
- Verified `curl -sI` on the old owner/repo URL returns **HTTP 301** with
  `Location: https://github.com/chemglyph/chemglyph`, and the new address
  returns 200. The old URL keeps redirecting as long as GitHub retains the
  transfer redirect.
- awesome-mcp-servers PR #12063 (still draft) updated to the new address and
  commented accordingly.
- Full-repo grep for the old owner/repo path: zero matches.

## P2-8: Consolidated TODO(question) list with suggested answers

M1:

1. Does "basic cleaning" include removing explicit Hs? — Suggested: **no** for
   v0.1 (stay input-faithful); add an opt-in `remove_hs` parameter in v0.2.
2. Should warnings also cover unassigned E/Z bond stereo? — Suggested: **yes
   in v0.2**; v0.1 keeps the spec's tetrahedral example.
3. Linalool's ~44% height fill in auto-sizing — Suggested: **accept for
   v0.1**; add tight content cropping in v0.2.

M2:

4. Wrap reading order (arrow first vs redrawn intermediate first) —
   Suggested: switch to **intermediate first, arrow last** with a true
   down-arrow glyph in v0.2; the current arrow-at-row-start form is the
   spec-literal MVP.
5. Should `align: "arrow"` center the arrow column across rows? — Suggested:
   **yes in v0.2** (rows currently left-align).
6. Should condition font scale with style? — Suggested: derive from the
   style's label size in v0.2; the fixed 14px is fine for v0.1.

M3:

7. MCP errors as `TextContent` vs `isError: true` — Suggested: **keep
   `TextContent`** in v0.1 (LLM-friendly, and the text is prefixed
   "ChemGlyph error:"); revisit structured error codes in v0.2.
8. Platform-specific Java install command in `parse_name` errors — Suggested:
   **keep it generic** (one command per common platform is maintenance
   burden); link Adoptium instead.

M4:

9. Launch order / mentioning the blind test before results — Suggested: wait
   for the blind review before HN and r/chemistry; r/LocalLLaMA can ship
   earlier without result claims. Order: r/LocalLLaMA -> HN -> r/chemistry.
10. Beta on PyPI first? — Suggested: if human visual approval of the gallery
    is pending, publish `0.1.0rc1`; otherwise go straight to `0.1.0`.

## P2-9: §6.2 rule 4 implementation status

Fully implemented for the in-row case: a step whose reactants resolve to the
same canonical-SMILES set as the previous step's products is drawn as
`arrow + products` with no reactant redraw (order-insensitive set equality).
The "MVP allows redraw" fallback is used only at a **line wrap**, where the
next row opens with the step's arrow and the intermediates are redrawn once.
There is no true down-arrow glyph yet (documented in M2.md and P2-8 item 4).

## P2-10: Snapshot assertion strength

Before: color presence/absence and a relative acs-vs-textbook width ordering
were asserted, but a uniform style regression (e.g. all bonds thinned) could
have slipped through. Added:

- Per-style golden stroke-width ranges: `max(width) <= expected + 0.15` and
  the style's exact bond width must appear (`acs` 2.0, `modern` 2.4,
  `textbook-cn` 2.6 px).
- A `StyleSpec.bondLineWidth` vs golden-constants consistency test, so editing
  the preset without updating the golden fails loudly.
- Existing assertions retained: `#D62728`/`#1F77B4` presence in `modern`,
  absence in `acs`/`textbook-cn`, wedge segments, atom/bond id sets.

## P2-11: answer_key.json in the public repo

Confirmed committed. Added `benchmarks/README.md` stating the validity
premise: the tracked key is the audit trail; the blind test stays valid only
because graders see the shuffled figure directory and never this repository —
anyone with repo access is excluded from the grading pool. ChemDraw panels
remain manual, local inputs.

## P0-3 execution log (maintainer-approved 2026-08-13)

Executed strictly in the approved order:

1. **Backup first**: mirror clone to
   `/Users/abc/backups/chemglyph-pre-rewrite.git`; the commit set was verified
   identical to the working repo (10/10) and `fsck` clean. The backup retains
   the pre-rewrite data by design — keep it private and delete it after the
   Support purge is confirmed.
2. **Rewrite**: `git filter-repo` with an email callback (old mailbox ->
   noreply identity) and a blob callback (literal -> `[redacted-email]`).
   10 commits rewritten; new history head `fc76fd4`.
3. **Post-rewrite verification, all green**:
   a. `git log --all` author/committer identities contain only the noreply
      alias;
   b. full-history blob scan plus author/committer/message scans: zero
      matches for the mailbox or its domain;
   c. ruff clean, pytest 58 passed / 1 skipped (optional OPSIN).
4. **Push**: `--force-with-lease` replaced remote `main` with `fc76fd4`; no
   tags existed to rewrite; CI green on all five jobs (4 matrix jobs +
   minimum-rdkit). A follow-up normal push then hit a GitHub server-side
   anomaly: `git push` to `main` returned HTTP 500 repeatedly while the same
   commit pushed cleanly to a scratch branch and all reads (`ls-remote`, API)
   stayed healthy. The ref was advanced via the REST ref-update endpoint
   (standard push equivalent); the scratch branch was deleted and CI is green
   again. The anomaly is recorded in the Support ticket draft so GitHub can
   inspect the repository state alongside the purge request.
5. **Support ticket draft**: written to
   `docs/progress/support_ticket_draft.md` (gitignored, kept out of the
   repository) with the full old-SHA list. The maintainer submits it at
   support.github.com while logged in; agents cannot submit on the account's
   behalf.
6. **Expected accessibility state**: after the push, the dangling initial
   commit and the pre-rewrite SHAs remain readable by SHA until GitHub
   Support garbage-collects them. This is the documented expected behavior,
   not a failure. The maintainer re-verifies 404s after Support confirms.

Remaining follow-ups: submit the support ticket; after the purge, verify 404s
for every listed SHA and delete the backup. NetBerth's separate personal-Gmail
exposure (P0-2) is out of this repository's scope and should receive the same
treatment from its own maintainer.
