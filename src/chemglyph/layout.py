"""Layout checks and best-of layout selection (docs/SPEC.md, section 7).

A drawing can pass every structural check (all bonds drawn, the right
structure embedded) and still be unreadable: atoms on top of each other,
bonds through atoms, crossing bonds. These checks measure such problems on
the 2D coordinates, in units of the mean bond length, and the layout step
uses them to pick the best of several RDKit layouts.

Checks:

- ``close_atoms``: two atoms that are not bonded closer than 0.35 bonds,
  close enough to be read as one atom.
- ``atom_on_bond``: an atom within a quarter bond of a bond it is not part of.
- ``bond_crossings``: two bonds without a shared atom that cross.
- ``atom_in_ring``: a non-ring atom inside a ring of up to 8 members.
- ``uneven_bonds``: bonds more than 15% off the mean length.
- ``stereo_lost``: the wedges and double-bond geometry this layout allows
  do not reproduce the stereochemistry. Wedges are chosen from the
  coordinates, and around a crowded centre (a quinuclidine bridgehead) a
  layout can leave no bond that fixes the configuration; the figure would
  then show a different stereoisomer.

All but ``uneven_bonds`` make a figure misleading and count as severe, with one
exception: bridged ring systems (camphor, adamantane, morphine) are drawn in
perspective by convention, so a crossing, an atom on a bond, or an atom
inside a ring whose atoms all belong to a bridged system is counted as
``perspective`` instead. Uneven bonds only look untidy.
"""

from __future__ import annotations

import math
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import rdDepictor

# label_overlaps is filled in after drawing, from the label outlines.
_SEVERE = (
    "close_atoms",
    "atom_on_bond",
    "bond_crossings",
    "atom_in_ring",
    "stereo_lost",
    "label_overlaps",
)
_CLOSE = 0.35  # bonds


@dataclass
class LayoutReport:
    """Layout problems found on a molecule's 2D coordinates."""

    counts: dict[str, int] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)
    added_hydrogens: list[int] = field(default_factory=list)

    @property
    def severe(self) -> int:
        return sum(self.counts.get(name, 0) for name in _SEVERE)

    @property
    def score(self) -> float:
        """Lower is better: severe problems dominate, untidiness breaks ties.

        A lost stereocentre weighs less than a geometric problem because
        :func:`add_stereo_hydrogens` can usually repair it.
        """
        lost = self.counts.get("stereo_lost", 0)
        return 100.0 * (self.severe - lost) + 10.0 * lost + self.counts.get("uneven_bonds", 0)


def check_layout(mol: Chem.Mol) -> LayoutReport:
    """Measure layout problems on the molecule's current 2D conformer."""
    report = LayoutReport(counts=dict.fromkeys((*_SEVERE, "perspective", "uneven_bonds"), 0))
    if mol.GetNumConformers() == 0 or mol.GetNumAtoms() < 2:
        return report
    conformer = mol.GetConformer()
    xy = np.array(
        [
            [conformer.GetAtomPosition(i).x, conformer.GetAtomPosition(i).y]
            for i in range(mol.GetNumAtoms())
        ]
    )
    bonds = np.array([[b.GetBeginAtomIdx(), b.GetEndAtomIdx()] for b in mol.GetBonds()], dtype=int)
    if len(bonds) == 0:
        return report
    lengths = np.linalg.norm(xy[bonds[:, 0]] - xy[bonds[:, 1]], axis=1)
    mean = float(lengths.mean()) or 1.0
    xy = xy / mean  # every distance below is in bond lengths

    bonded = {(int(a), int(b)) for a, b in bonds} | {(int(b), int(a)) for a, b in bonds}
    fragment_of = _fragments(mol)
    bridged = bridged_atoms(mol)

    def perspective(*atoms: int) -> bool:
        if all(int(atom) in bridged for atom in atoms):
            report.counts["perspective"] += 1
            return True
        return False

    # close_atoms: non-bonded pairs in one fragment that nearly coincide
    diff = xy[:, None, :] - xy[None, :, :]
    distance = np.sqrt((diff**2).sum(axis=2))
    for i, j in zip(*np.nonzero(distance < _CLOSE), strict=True):
        if i < j and (int(i), int(j)) not in bonded and fragment_of[i] == fragment_of[j]:
            report.counts["close_atoms"] += 1
            _note(report, f"atoms {i} and {j} are {distance[i, j]:.2f} bonds apart")

    # atom_on_bond: an atom near the inside of a bond it does not belong to
    a, b = xy[bonds[:, 0]], xy[bonds[:, 1]]
    ab = b - a
    length2 = np.maximum((ab**2).sum(axis=1), 1e-12)
    t = ((xy[:, None, :] - a[None, :, :]) * ab[None, :, :]).sum(axis=2) / length2[None, :]
    closest = a[None, :, :] + np.clip(t, 0, 1)[:, :, None] * ab[None, :, :]
    gap = np.sqrt(((xy[:, None, :] - closest) ** 2).sum(axis=2))
    for atom, bond in zip(*np.nonzero((gap < 0.25) & (t > 0.05) & (t < 0.95)), strict=True):
        if atom in bonds[bond] or fragment_of[atom] != fragment_of[bonds[bond][0]]:
            continue
        if perspective(atom, *bonds[bond]):
            continue
        report.counts["atom_on_bond"] += 1
        _note(report, f"atom {atom} sits on bond {bond}")

    # bond_crossings: proper intersections between bonds with no shared atom
    for i in range(len(bonds)):
        for j in range(i + 1, len(bonds)):
            if set(bonds[i]) & set(bonds[j]) or not _cross(a[i], b[i], a[j], b[j]):
                continue
            if perspective(*bonds[i], *bonds[j]):
                continue
            report.counts["bond_crossings"] += 1
            _note(report, f"bonds {i} and {j} cross")

    # atom_in_ring: a non-ring atom inside a small ring
    for ring in mol.GetRingInfo().AtomRings():
        if len(ring) > 8:
            continue
        polygon = xy[list(ring)]
        for atom in range(len(xy)):
            if atom in ring or fragment_of[atom] != fragment_of[ring[0]]:
                continue
            if not _inside(xy[atom], polygon) or perspective(atom, *ring):
                continue
            report.counts["atom_in_ring"] += 1
            _note(report, f"atom {atom} sits inside ring {tuple(ring)}")

    report.counts["uneven_bonds"] = int((np.abs(lengths / mean - 1.0) > 0.15).sum())
    if stereo_lost(mol):
        report.counts["stereo_lost"] = 1
        _note(report, "the wedges of this layout do not fix every stereocentre")
    return report


def add_stereo_hydrogens(mol: Chem.Mol) -> Chem.Mol | None:
    """Draw an explicit H on each stereocentre the layout's wedges cannot fix.

    This is the usual way to draw such centres (the C4 bridgehead H of
    quinine). Returns the molecule with those hydrogens, laid out in 2D, or
    None if there is nothing to repair or hydrogens do not repair it. New
    atoms are appended, so existing atom indices keep their meaning.
    """
    if not stereo_lost(mol):
        return None
    with _quiet():
        back = Chem.MolFromMolBlock(Chem.MolToMolBlock(mol))
    if back is None:
        return None
    wanted = dict(Chem.FindMolChiralCenters(mol, useLegacyImplementation=False))
    found = dict(
        Chem.FindMolChiralCenters(back, includeUnassigned=True, useLegacyImplementation=False)
    )
    lost = [
        atom
        for atom, label in wanted.items()
        if found.get(atom) != label and mol.GetAtomWithIdx(atom).GetTotalNumHs() == 1
    ]
    if not lost:
        return None
    with_h = Chem.AddHs(mol, onlyOnAtoms=lost, addCoords=True)
    if stereo_lost(with_h):
        return None
    return with_h


def stereo_lost(mol: Chem.Mol) -> bool:
    """True if a molfile written from this layout reads back as another stereoisomer."""
    if not any(
        atom.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED for atom in mol.GetAtoms()
    ) and not any(bond.GetStereo() != Chem.BondStereo.STEREONONE for bond in mol.GetBonds()):
        return False
    try:
        with _quiet():
            back = Chem.MolFromMolBlock(Chem.MolToMolBlock(mol))
        return back is None or Chem.MolToSmiles(back) != Chem.MolToSmiles(Chem.RemoveHs(mol))
    except (RuntimeError, ValueError):
        return False  # unwritable structures are reported by verification instead


def best_layout(mol: Chem.Mol, repair=None) -> tuple[str, LayoutReport]:
    """Lay the molecule out and keep the best layout; deterministic.

    A bridged ring system that RDKit has a ring template for is drawn from
    the template, the conventional perspective drawing, and is not repaired
    (the repair would flatten the perspective), unless its wedges lose a
    stereocentre; then it competes with the other layouts. Otherwise CoordGen, RDKit's
    own depictor, and RDKit with seeded flip sampling are scored by
    :func:`check_layout` (each after ``repair``), and the lowest score wins;
    ties keep the earlier candidate.
    """
    candidates: list[tuple[str, np.ndarray, LayoutReport]] = []
    if bridged_atoms(mol) and _template_applies(mol):
        report = check_layout(mol)
        if not report.counts.get("stereo_lost"):
            return "ring-template", report
        candidates.append(("ring-template", mol.GetConformer().GetPositions().copy(), report))
    for name in ("coordgen", "rdkit", "rdkit-sampled"):
        if not _compute(mol, name):
            continue
        if not np.isfinite(mol.GetConformer().GetPositions()).all():
            continue  # CoordGen returns NaN for molecules of hydrogen only (H2, H+)
        if repair is not None:
            repair(mol)
        report = check_layout(mol)
        candidates.append((name, mol.GetConformer().GetPositions().copy(), report))
        if report.score == 0:
            break  # a clean layout earlier in the preference order wins outright
    if candidates and min(c[2].severe for c in candidates) and _mostly_cage(mol):
        # Cages (adamantane, cubane) have no good flat drawing; chemists draw
        # them in perspective, which is what a projection of 3D coordinates is.
        if _project(mol):
            report = check_layout(mol)
            candidates.append(("projection", mol.GetConformer().GetPositions().copy(), report))
    name, positions, report = min(candidates, key=lambda item: item[2].score)
    conformer = mol.GetConformer()
    for index, (x, y, z) in enumerate(positions):
        conformer.SetAtomPosition(index, (float(x), float(y), float(z)))
    return name, report


def space_fragments(mol: Chem.Mol) -> None:
    """Set the fragments of a salt or mixture side by side, in input order.

    RDKit leaves about one bond between fragments, which is too little once
    the labels carry charges (Na+ Cl- touched). Each fragment's extent is
    widened by an estimate of its end labels (0.42 bond per character at
    the ACS sizes, plus room for a charge sign), and fragments are placed
    left to right with 0.5 bond between them, centred vertically.
    """
    pieces = Chem.GetMolFrags(mol)
    if len(pieces) < 2 or mol.GetNumConformers() == 0:
        return
    conformer = mol.GetConformer()
    xy = conformer.GetPositions()[:, :2].copy()
    lengths = [
        float(np.linalg.norm(xy[b.GetBeginAtomIdx()] - xy[b.GetEndAtomIdx()]))
        for b in mol.GetBonds()
    ]
    bond = float(np.mean(lengths)) if lengths else 1.5
    cursor = 0.0
    for atoms in pieces:
        atoms = list(atoms)
        left = right = None
        for atom in atoms:
            half = 0.5 * _label_width(mol.GetAtomWithIdx(atom)) * bond
            lo, hi = xy[atom, 0] - half, xy[atom, 0] + half
            left = lo if left is None else min(left, lo)
            right = hi if right is None else max(right, hi)
        ys = xy[atoms, 1]
        shift_x = cursor - left
        shift_y = -(ys.min() + ys.max()) / 2
        for atom in atoms:
            x, y = xy[atom]
            conformer.SetAtomPosition(atom, (float(x + shift_x), float(y + shift_y), 0.0))
        cursor += right - left + 0.5 * bond


def _label_width(atom: Chem.Atom) -> float:
    """Rough width of an atom's label in bond lengths (0 for a bare carbon)."""
    charge = atom.GetFormalCharge()
    if atom.GetAtomicNum() == 6 and not charge and atom.GetDegree() > 0:
        return 0.0
    text = atom.GetSymbol()
    hydrogens = atom.GetTotalNumHs()
    if hydrogens:
        text += "H" + (str(hydrogens) if hydrogens > 1 else "")
    width = 0.42 * len(text)
    if charge:
        width += 0.35 * (1 if abs(charge) == 1 else 2) + 0.1
    return width


def bridged_atoms(mol: Chem.Mol) -> set[int]:
    """Atoms drawn in perspective: bridged ring systems and their substituents.

    A ring system is the set of rings joined by shared bonds; it is bridged
    when two of its rings share three or more atoms (norbornane, morphinan),
    and a cage when it has three or more rings and every atom lies in two of
    them (cubane, whose faces share only edges).
    The zone covers every ring atom of such a system plus the atoms bonded to
    it, since a perspective drawing also places substituents (camphor's
    gem-dimethyl) over the ring outlines.
    """
    rings = [set(ring) for ring in mol.GetRingInfo().AtomRings()]
    systems: list[list[set[int]]] = []
    for ring in rings:
        joined = [system for system in systems if any(len(ring & other) >= 2 for other in system)]
        merged = [ring] + [other for system in joined for other in system]
        systems = [system for system in systems if system not in joined] + [merged]
    zone: set[int] = set()
    for system in systems:
        bridged = any(
            len(first & second) >= 3
            for index, first in enumerate(system)
            for second in system[index + 1 :]
        )
        if not bridged and not _is_cage(system):
            continue
        atoms = set().union(*system)
        zone |= atoms
        for atom in atoms:
            zone.update(n.GetIdx() for n in mol.GetAtomWithIdx(atom).GetNeighbors())
    return zone


def _is_cage(system: list[set[int]]) -> bool:
    if len(system) < 3:
        return False
    atoms = set().union(*system)
    return all(sum(atom in ring for ring in system) >= 2 for atom in atoms)


def _mostly_cage(mol: Chem.Mol) -> bool:
    """At least half the heavy atoms are in a bridged system or cage."""
    zone_rings = set()
    for ring in mol.GetRingInfo().AtomRings():
        zone_rings.update(ring)
    perspective = bridged_atoms(mol) & zone_rings
    heavy = sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() > 1)
    return heavy > 0 and len(perspective) >= 0.5 * heavy


def _project(mol: Chem.Mol, seed: int = 42, directions: int = 400) -> bool:
    """Lay the molecule out as an orthographic view of its 3D shape.

    The viewing direction is chosen on a hemisphere of evenly spread
    directions. A view loses heavily when an atom lands on a bond it is not
    part of, when two bonds at an atom look collinear (RDKit would then
    label a carbon "C", which in a cage misleads), or when a heteroatom
    label would sit on a bond; among the rest, the view keeps atoms apart
    and avoids strongly foreshortened bonds. Deterministic for a seed.
    """
    from rdkit.Chem import AllChem

    with_h = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    if AllChem.EmbedMolecule(with_h, params) != 0:
        return False
    try:
        AllChem.MMFFOptimizeMolecule(with_h)
    except (RuntimeError, ValueError):
        pass
    xyz = with_h.GetConformer().GetPositions()[: mol.GetNumAtoms()]
    xyz = xyz - xyz.mean(axis=0)
    bonds = np.array([[b.GetBeginAtomIdx(), b.GetEndAtomIdx()] for b in mol.GetBonds()], dtype=int)
    if len(bonds) == 0:
        return False
    labelled = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() != 6]
    pairs = [
        (atom.GetIdx(), first, second, 30.0 if atom.GetDegree() == 2 else 15.0)
        for atom in mol.GetAtoms()
        for i, first in enumerate(n.GetIdx() for n in atom.GetNeighbors())
        for second in [n.GetIdx() for n in atom.GetNeighbors()][i + 1 :]
    ]
    golden = math.pi * (3 - math.sqrt(5))
    best: tuple[float, np.ndarray] | None = None
    for i in range(directions):
        z = 1 - (i + 0.5) / directions
        r = math.sqrt(1 - z * z)
        view = np.array([r * math.cos(golden * i), r * math.sin(golden * i), z])
        u = np.cross(view, [0.0, 0.0, 1.0] if abs(view[2]) < 0.9 else [1.0, 0.0, 0.0])
        u /= np.linalg.norm(u)
        v = np.cross(view, u)
        xy = np.c_[xyz @ u, xyz @ v]
        lengths = np.linalg.norm(xy[bonds[:, 0]] - xy[bonds[:, 1]], axis=1)
        mean = float(lengths.mean())
        if mean < 1e-6:
            continue
        xy_n = xy / mean
        score = _view_score(xy_n, bonds, pairs, labelled) + 5.0 * float(lengths.min()) / mean
        if best is None or score > best[0]:
            best = (score, xy)
    if best is None:
        return False
    conformer = Chem.Conformer(mol.GetNumAtoms())
    conformer.Set3D(False)
    for index, (x, y) in enumerate(best[1]):
        conformer.SetAtomPosition(index, (float(x), float(y), 0.0))
    mol.RemoveAllConformers()
    mol.AddConformer(conformer, assignId=True)
    return True


def _view_score(xy: np.ndarray, bonds: np.ndarray, pairs, labelled) -> float:
    a, b = xy[bonds[:, 0]], xy[bonds[:, 1]]
    ab = b - a
    length2 = np.maximum((ab**2).sum(axis=1), 1e-12)
    t = ((xy[:, None, :] - a[None]) * ab[None]).sum(axis=2) / length2[None]
    gap = np.linalg.norm(
        xy[:, None, :] - (a[None] + np.clip(t, 0, 1)[:, :, None] * ab[None]), axis=2
    )
    member = (np.arange(len(xy))[:, None] == bonds[None, :, 0]) | (
        np.arange(len(xy))[:, None] == bonds[None, :, 1]
    )
    inside = (t > 0.05) & (t < 0.95) & ~member
    penalty = 100.0 * float(((gap < 0.2) & inside).sum())
    if labelled:
        # A label needs room: off other bonds, away from other atoms, and its
        # own bonds not so foreshortened that the label covers them.
        penalty += 30.0 * float(((gap[labelled] < 0.45) & inside[labelled]).sum())
        near = np.linalg.norm(xy[labelled][:, None] - xy[None], axis=2)
        near[np.arange(len(labelled)), labelled] = 9.0
        penalty += 30.0 * float((near < 0.6).sum())
        lengths = np.sqrt(length2)
        own = member[labelled].any(axis=0)
        penalty += 30.0 * float(((lengths < 0.7) & own).sum())
    for centre, first, second, limit in pairs:
        e1, e2 = xy[first] - xy[centre], xy[second] - xy[centre]
        cosine = float(e1 @ e2) / max(float(np.linalg.norm(e1) * np.linalg.norm(e2)), 1e-12)
        if abs(cosine) > math.cos(math.radians(limit)):
            penalty += 50.0
    distance = np.linalg.norm(xy[:, None] - xy[None], axis=2)
    np.fill_diagonal(distance, 9.0)
    return 10.0 * min(float(distance.min()), 0.6) - penalty


def _template_applies(mol: Chem.Mol) -> bool:
    """Lay out with RDKit's ring templates; True if a template changed the result."""
    if not _compute(mol, "rdkit"):
        return False
    plain = mol.GetConformer().GetPositions().copy()
    if not _compute(mol, "rdkit-templates"):
        return False
    return not np.allclose(plain, mol.GetConformer().GetPositions(), atol=1e-3)


def _compute(mol: Chem.Mol, name: str) -> bool:
    try:
        if name == "coordgen":
            rdDepictor.SetPreferCoordGen(True)
            rdDepictor.Compute2DCoords(mol)
        elif name == "rdkit":
            rdDepictor.Compute2DCoords(mol, forceRDKit=True)
        elif name == "rdkit-templates":
            rdDepictor.Compute2DCoords(mol, forceRDKit=True, useRingTemplates=True)
        else:
            rdDepictor.Compute2DCoords(
                mol,
                forceRDKit=True,
                nFlipsPerSample=3,
                nSample=50,
                sampleSeed=42,
                permuteDeg4Nodes=True,
            )
    except (TypeError, RuntimeError, ValueError, IndexError):
        # an option missing from this RDKit, or a layout failure; RDKit
        # 2024.09 raises IndexError (map::at) from seeded sampling
        return False
    finally:
        rdDepictor.SetPreferCoordGen(True)
    return True


@contextmanager
def _quiet():
    """Silence RDKit's log (stereo warnings while testing a layout's wedges)."""
    RDLogger.DisableLog("rdApp.*")
    try:
        yield
    finally:
        RDLogger.EnableLog("rdApp.*")


def _fragments(mol: Chem.Mol) -> list[int]:
    fragment_of = [0] * mol.GetNumAtoms()
    for number, atoms in enumerate(Chem.GetMolFrags(mol)):
        for atom in atoms:
            fragment_of[atom] = number
    return fragment_of


def _cross(p1: np.ndarray, p2: np.ndarray, q1: np.ndarray, q2: np.ndarray) -> bool:
    def orient(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))

    d1, d2 = orient(q1, q2, p1), orient(q1, q2, p2)
    d3, d4 = orient(p1, p2, q1), orient(p1, p2, q2)
    return d1 * d2 < -1e-9 and d3 * d4 < -1e-9


def _inside(point: np.ndarray, polygon: np.ndarray) -> bool:
    x, y = point
    inside = False
    previous = len(polygon) - 1
    for current in range(len(polygon)):
        x1, y1 = polygon[current]
        x2, y2 = polygon[previous]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
        previous = current
    return inside


def _note(report: LayoutReport, text: str) -> None:
    if len(report.examples) < 10:
        report.examples.append(text)
