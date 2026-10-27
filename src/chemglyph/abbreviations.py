"""Group abbreviations (Ph, Boc, OTs, TBSO) for drawings.

Labels and spellings follow the list of standard abbreviations in the
Journal of Organic Chemistry author guidelines (ACS), which is also what
ChemDraw's default abbreviation set uses. Prefixes such as the t of t-Bu are
written with a hyphen; drawing labels cannot be set in italics.

Two rules decide where a group may be abbreviated:

- Protecting and activating groups that are acyl, carbamate, benzyl, acetal,
  or trityl groups (Ac, Boc, Bn, MOM) are abbreviated only on a heteroatom.
  On carbon they are part of the skeleton: phenylalanine's side chain is not
  drawn as "Bn", nor acetophenone as "PhAc".
- Silyl and sulfonyl groups (TMS, TBS, Ts, Tf) are abbreviated on any atom,
  as in TMS-alkynes and TosMIC.

A group on a terminal O or NH is written as one label with that atom
(OTs, NHBoc, and TsO, BocHN when the bond comes from the right).

Only the drawing uses the abbreviations. The structure embedded in the
figure, the identity, and the name check use the full molecule, and the
molfile output keeps every atom with the abbreviations as SUP groups, which
structure editors show as labels.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from rdkit import Chem
from rdkit.Chem import rdAbbreviations

from .errors import ChemGlyphStyleError

# Fraction of a molecule's atoms the abbreviations may cover. Above it the
# figure would be mostly labels (benzyl alcohol as BnOH is fine, Ph-H is not).
MAX_COVERAGE = 0.75


@dataclass(frozen=True)
class Group:
    """One abbreviation."""

    label: str
    smiles: str  # the group, written from the atom bonded to the rest
    display: str  # RDKit label markup, for a bond coming from the left
    display_west: str  # for a bond coming from the right
    on_carbon: bool  # may it stand on a carbon atom
    protecting: bool  # part of the default set (abbreviate=True)
    variants: tuple[str, ...] = ()  # terminal heteroatoms that join the label: "O", "NH"


def _g(label, smiles, *, on_carbon, protecting, variants=("O", "NH"), display=None, west=None):
    display = display or label
    return Group(label, smiles, display, west or display, on_carbon, protecting, variants)


_PH = "c1ccccc1"
GROUPS: tuple[Group, ...] = (
    # Protecting and activating groups, abbreviated only on heteroatoms.
    _g("Ac", "C(=O)C", on_carbon=False, protecting=True),
    _g("Bz", f"C(=O){_PH}", on_carbon=False, protecting=True),
    _g("Piv", "C(=O)C(C)(C)C", on_carbon=False, protecting=True),
    _g("Boc", "C(=O)OC(C)(C)C", on_carbon=False, protecting=True),
    _g("Cbz", f"C(=O)OC{_PH}", on_carbon=False, protecting=True),
    _g("Fmoc", "C(=O)OCC1c2ccccc2-c2ccccc21", on_carbon=False, protecting=True),
    _g("Alloc", "C(=O)OCC=C", on_carbon=False, protecting=True),
    _g("Troc", "C(=O)OCC(Cl)(Cl)Cl", on_carbon=False, protecting=True),
    _g("Bn", f"C{_PH}", on_carbon=False, protecting=True),
    _g("PMB", "Cc1ccc(OC)cc1", on_carbon=False, protecting=True),
    _g("Tr", f"C({_PH})({_PH}){_PH}", on_carbon=False, protecting=True),
    _g("MOM", "COC", on_carbon=False, protecting=True, variants=("O",)),
    _g("THP", "C1OCCCC1", on_carbon=False, protecting=True, variants=("O",)),
    # Silyl and sulfonyl groups, abbreviated on any atom.
    _g("TMS", "[Si](C)(C)C", on_carbon=True, protecting=True),
    _g("TES", "[Si](CC)(CC)CC", on_carbon=True, protecting=True),
    _g("TBS", "[Si](C)(C)C(C)(C)C", on_carbon=True, protecting=True),
    _g("TIPS", "[Si](C(C)C)(C(C)C)C(C)C", on_carbon=True, protecting=True),
    _g("TBDPS", f"[Si]({_PH})({_PH})C(C)(C)C", on_carbon=True, protecting=True),
    _g("Ts", "S(=O)(=O)c1ccc(C)cc1", on_carbon=True, protecting=True),
    _g("Ms", "S(=O)(=O)C", on_carbon=True, protecting=True),
    _g("Tf", "S(=O)(=O)C(F)(F)F", on_carbon=True, protecting=True),
    # Common substituents, abbreviated only when asked for by name.
    _g("Me", "C", on_carbon=True, protecting=False),
    _g("Et", "CC", on_carbon=True, protecting=False),
    _g("n-Pr", "CCC", on_carbon=True, protecting=False),
    _g("i-Pr", "C(C)C", on_carbon=True, protecting=False, west="i-Pr"),
    _g("n-Bu", "CCCC", on_carbon=True, protecting=False),
    _g("i-Bu", "CC(C)C", on_carbon=True, protecting=False),
    _g("s-Bu", "C(C)CC", on_carbon=True, protecting=False),
    _g("t-Bu", "C(C)(C)C", on_carbon=True, protecting=False),
    _g("Cy", "C1CCCCC1", on_carbon=True, protecting=False),
    _g("Ph", _PH, on_carbon=True, protecting=False),
    _g("Tol", "c1ccc(C)cc1", on_carbon=True, protecting=False, display="p-Tol"),
    _g(
        "CO2Me",
        "C(=O)OC",
        on_carbon=True,
        protecting=False,
        variants=(),
        display="CO<sub>2</sub>Me",
        west="MeO<sub>2</sub>C",
    ),
    _g(
        "CO2Et",
        "C(=O)OCC",
        on_carbon=True,
        protecting=False,
        variants=(),
        display="CO<sub>2</sub>Et",
        west="EtO<sub>2</sub>C",
    ),
    _g(
        "CO2t-Bu",
        "C(=O)OC(C)(C)C",
        on_carbon=True,
        protecting=False,
        variants=(),
        display="CO<sub>2</sub>t-Bu",
        west="t-BuO<sub>2</sub>C",
    ),
    _g(
        "CF3",
        "C(F)(F)F",
        on_carbon=True,
        protecting=False,
        variants=(),
        display="CF<sub>3</sub>",
        west="F<sub>3</sub>C",
    ),
)
_BY_LABEL = {group.label: group for group in GROUPS}


def select(choice: bool | Iterable[str]) -> list[Group]:
    """The groups for ``abbreviate=True`` (protecting groups) or a list of labels."""
    if choice is True:
        return [group for group in GROUPS if group.protecting]
    if choice is False or choice is None:
        return []
    if isinstance(choice, str):
        choice = [choice]
    groups = []
    for label in choice:
        if label not in _BY_LABEL:
            known = ", ".join(_BY_LABEL)
            raise ChemGlyphStyleError(f"Unknown abbreviation {label!r}; choose from: {known}")
        groups.append(_BY_LABEL[label])
    return groups


def definitions(groups: Iterable[Group]):
    """RDKit abbreviation definitions, the larger patterns first."""
    rows: list[tuple[int, str, str, str, str, bool]] = []
    for group in groups:
        size = Chem.MolFromSmiles(group.smiles).GetNumAtoms()
        rows.append(
            (size, group.label, group.smiles, group.display, group.display_west, group.on_carbon)
        )
        for atom in group.variants:
            # RDKit takes the attachment atom's degree from the pattern, so the
            # O or NH is terminal apart from the group; whatever it hangs off
            # (carbon included) may carry the label: R-OTs, R-NHBoc.
            pattern = ("O" if atom == "O" else "[NH]") + group.smiles
            west = group.display_west + ("O" if atom == "O" else "HN")
            rows.append((size + 1, atom + group.label, pattern, atom + group.display, west, True))
    rows.sort(key=lambda row: -row[0])
    text = "\n".join(f"{label} {smiles} {disp} {west}" for _, label, smiles, disp, west, _ in rows)
    parsed = rdAbbreviations.ParseAbbreviations(text)
    for definition, row in zip(parsed, rows, strict=True):
        if not row[5]:
            _restrict_to_heteroatoms(definition)
    return parsed


def _restrict_to_heteroatoms(definition) -> None:
    """Let a pattern match only where it hangs off an atom other than C or H."""
    original = definition.mol
    query = Chem.MolFromSmarts(Chem.MolToSmarts(original).replace("[!#0]", "[!#0;!#6;!#1]", 1))
    for key, value in original.GetPropsAsDict(includePrivate=True, includeComputed=False).items():
        if isinstance(value, int):
            query.SetUnsignedProp(key, value)
        else:
            query.SetProp(key, str(value))
    definition.mol = query


@dataclass
class Abbreviated:
    """A molecule with abbreviations: what to draw and what to record."""

    drawn: Chem.Mol  # abbreviated groups replaced by one labelled atom each
    labelled: Chem.Mol  # every atom, with the abbreviations as SUP groups
    original_index: list[int]  # drawn atom -> atom of the full molecule
    groups: list[dict]  # label, full-molecule atoms, and drawn label atom of each
    shown: dict[str, tuple[str, str]]  # label -> display forms (east, west)

    def without(self, dropped: set[int]) -> Abbreviated | None:
        """The same abbreviations minus the groups at the given positions."""
        labelled = Chem.Mol(self.labelled)
        kept = [g for i, g in enumerate(_sup_groups(labelled)) if i not in dropped]
        Chem.ClearMolSubstanceGroups(labelled)
        for group in kept:
            Chem.AddMolSubstanceGroup(labelled, group)
        return _condense(labelled, self.shown)


def abbreviate(mol: Chem.Mol, groups: list[Group]) -> Abbreviated | None:
    """Abbreviate the molecule; None when no group matches."""
    if not groups:
        return None
    work = Chem.Mol(mol)
    for atom in work.GetAtoms():
        atom.SetIntProp("_cg_index", atom.GetIdx())
    patterns = definitions(groups)
    labelled = rdAbbreviations.LabelMolAbbreviations(work, patterns, maxCoverage=MAX_COVERAGE)
    shown = {d.label: (d.displayLabel, d.displayLabelW or d.displayLabel) for d in patterns}
    return _condense(labelled, shown)


def _sup_groups(mol: Chem.Mol) -> list:
    return [g for g in Chem.GetMolSubstanceGroups(mol) if g.GetProp("TYPE") == "SUP"]


def _condense(labelled: Chem.Mol, shown: dict[str, tuple[str, str]]) -> Abbreviated | None:
    sgroups = _sup_groups(labelled)
    if not sgroups:
        return None
    drawn = rdAbbreviations.CondenseAbbreviationSubstanceGroups(Chem.Mol(labelled))
    # The label atom is the group's attachment atom, so it keeps its index tag.
    original = [atom.GetIntProp("_cg_index") for atom in drawn.GetAtoms()]
    position = {index: drawn_index for drawn_index, index in enumerate(original)}
    groups = []
    for sgroup in sgroups:
        atoms = sorted(sgroup.GetAtoms())
        label_atom = next(position[a] for a in atoms if a in position)
        groups.append({"label": sgroup.GetProp("LABEL"), "atoms": atoms, "drawn_atom": label_atom})
    # Condensing keeps only the label; restore the display forms (subscripts,
    # and the mirrored label for a bond from the right).
    for atom in drawn.GetAtoms():
        if atom.HasProp("atomLabel") and atom.GetProp("atomLabel") in shown:
            east, west = shown[atom.GetProp("atomLabel")]
            atom.SetProp("_displayLabel", east)
            atom.SetProp("_displayLabelW", west)
    return Abbreviated(drawn, labelled, original, groups, shown)
