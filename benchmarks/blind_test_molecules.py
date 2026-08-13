"""Fixed 20-molecule blind-test list (see §11 of the specification).

Each entry is ``(label, SMILES, note)``. The label is used in the answer key;
figure filenames use shuffled numbers instead so graders cannot see the
identity from the file name.
"""

from __future__ import annotations

BLIND_TEST_MOLECULES: list[tuple[str, str, str]] = [
    ("benzoic-acid", "OC(=O)c1ccccc1", ""),
    ("caffeine", "Cn1cnc2c1c(=O)n(C)c(=O)n2C", ""),
    ("s-ibuprofen", "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O", "stereo wedge"),
    ("aspirin", "CC(=O)Oc1ccccc1C(=O)O", ""),
    ("vanillin", "COc1cc(C=O)ccc1O", "fragrance-related"),
    ("linalool", "CC(C)=CCCC(C)(O)C=C", "fragrance-related"),
    ("beta-damascone", "CC(=O)/C=C/C1=C(C)CCCC1(C)C", "E/Z double bond"),
    (
        "cholesterol",
        "CC(C)CCC[C@@H](C)[C@H]1CC[C@@H]2[C@@]1(C)CC[C@H]1[C@H]2CC=C2C[C@@H](O)CC[C@]12C",
        "fused rings + multiple stereocenters",
    ),
    (
        "penicillin-g",
        "CC1(C)S[C@@H]2[C@H](NC(=O)Cc3ccccc3)C(=O)N2[C@H]1C(=O)O",
        "beta-lactam strained ring",
    ),
    ("18-crown-6", "C1COCCOCCOCCOCCOCCO1", "macrocycle"),
    (
        "porphyrin-free-base",
        "c1cc2cc3ccc(cc4ccc(cc5ccc(cc1n2)[nH]5)n4)[nH]3",
        "large conjugated system",
    ),
    ("sulfate", "[O-]S(=O)(=O)[O-]", "charge"),
    ("betaine", "C[N+](C)(C)CC([O-])=O", "zwitterion"),
    ("ferrocene", "[cH-]1cccc1.[cH-]1cccc1.[Fe+2]", "metal complex"),
    ("glucose-pyranose", "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O", ""),
    ("triphenylphosphine", "c1ccc(cc1)P(c1ccccc1)c1ccccc1", ""),
    ("tnt", "Cc1c(cc(cc1[N+](=O)[O-])[N+](=O)[O-])[N+](=O)[O-]", ""),
    (
        "paclitaxel",
        "CC1=C2[C@@]([C@]([C@H]([C@@H]3[C@]4([C@H](OC4)C[C@@H]([C@]3(C(=O)[C@@H]2OC(=O)C)C)O)OC(=O)C)OC(=O)c2ccccc2)(C[C@@H]1OC(=O)[C@H](O)[C@@H](NC(=O)c1ccccc1)c1ccccc1)O)(C)C",
        "complex natural product stress test",
    ),
    (
        "ciprofloxacin",
        "OC(=O)c1cn(C2CC2)c2cc(N3CCNCC3)c(F)cc2c1=O",
        "",
    ),
    ("e-azobenzene", "c1ccc(cc1)/N=N/c1ccccc1", "E double bond"),
]

# Figures that are excluded from the blind-test denominator and recorded
# separately as known limitations (see §11).
KNOWN_LIMITATIONS = {"porphyrin-free-base", "ferrocene"}
