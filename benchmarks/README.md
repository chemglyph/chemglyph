# Benchmarks

`blind_test_molecules.py` fixes the 20-molecule list from §11 of the project
specification; `generate_blind_test.py` renders every molecule in the `acs`
and `modern` styles under shuffled numbers and writes the key to
`blind_test_output/answer_key.json`.

The answer key is intentionally committed: it is the audit trail that proves
the figures were generated from the fixed list. This does not compromise the
blind test because the methodology requires graders to see only the shuffled
figure directory, never this repository — anyone with repo access must be
excluded from the grading pool. Generated figures stay local (gitignored);
ChemDraw reference panels are mixed in by hand before the review.
