"""Single-molecule rendering on top of RDKit (see §5 of the specification)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from rdkit import Chem, Geometry
from rdkit.Chem import Descriptors, rdDepictor, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

from .errors import ChemGlyphParseError, ChemGlyphRenderError
from .styles import StyleSpec, get_style
from .svg_utils import apply_post, parse_hex_color

_MOLBLOCK_RE = re.compile(r"\bV(2000|3000)\b")
_SPECIAL_OPTION_KEYS = {"acs1996_mode", "use_bw_atom_palette"}
_FIRST_RECT_ELEMENT = re.compile(r"<rect\b[^>]*(?:/>|>.*?</rect>)", re.DOTALL)


@dataclass
class RenderResult:
    """Output of :func:`render_molecule`."""

    data: str | bytes
    fmt: str
    canonical_smiles: str
    mol_formula: str
    mol_weight: float
    warnings: list[str] = field(default_factory=list)


def render_molecule(
    structure: str,
    style: str = "modern",
    size: tuple[int, int] | None = None,
    fmt: str = "svg",
    transparent: bool = True,
    show_atom_indices: bool = False,
    highlight_atoms: list[int] | None = None,
) -> RenderResult:
    """Render a molecule from SMILES, InChI, or molblock.

    Args:
        structure: SMILES, an InChI string (``InChI=`` prefix), or a molblock
            (auto-detected via a ``V2000``/``V3000`` line).
        style: one of ``acs``, ``modern``, ``textbook-cn``.
        size: canvas size in pixels; ``None`` estimates a canvas from molecule
            size and lets RDKit auto-scale the drawing.
        fmt: ``"svg"`` or ``"png"``.
        transparent: emit a transparent background instead of the style background.
        show_atom_indices: draw atom indices next to each atom.
        highlight_atoms: atom indices to highlight with RDKit circles.

    Raises:
        ChemGlyphParseError: the structure could not be parsed.
        ChemGlyphRenderError: invalid ``fmt`` or a missing PNG backend.
    """
    mol = _parse_structure(structure)
    _prepare_for_drawing(mol)
    spec = get_style(style)
    output_fmt = _normalize_fmt(fmt)
    options = _build_options(
        spec, mol=mol, transparent=transparent, show_atom_indices=show_atom_indices
    )
    canvas = size if size is not None else _estimate_canvas(mol)

    if output_fmt == "svg":
        data = _draw_svg(mol, options, canvas, highlight_atoms, transparent=transparent)
        data = apply_post(data, spec.post)
    else:
        data = _draw_png(mol, options, canvas, highlight_atoms)

    warnings = _stereo_warnings(mol)
    return RenderResult(
        data=data,
        fmt=output_fmt,
        canonical_smiles=Chem.MolToSmiles(mol),
        mol_formula=rdMolDescriptors.CalcMolFormula(mol),
        mol_weight=Descriptors.MolWt(mol),
        warnings=warnings,
    )


def _parse_structure(structure: str) -> Chem.Mol:
    stripped = structure.strip()
    if not stripped:
        raise ChemGlyphParseError("Structure string is empty.")
    raw_error = ""
    if stripped.startswith("InChI="):
        try:
            mol = Chem.MolFromInchi(stripped)
        except Exception as exc:
            mol, raw_error = None, str(exc)
        parser = "InChI"
    elif _MOLBLOCK_RE.search(stripped):
        try:
            # NOTE: RDKit 2026's molblock reader is sensitive to leading
            # whitespace, so pass the block through untouched.
            mol = Chem.MolFromMolBlock(structure)
        except Exception as exc:
            mol, raw_error = None, str(exc)
        parser = "molblock"
    else:
        mol, raw_error = _parse_smiles(stripped)
        parser = "SMILES"
    if mol is None:
        raw = raw_error or f"RDKit could not parse the {parser} input"
        if parser == "InChI":
            suggestion = (
                "Suggested fix: verify the InChI string "
                "(regenerate it with RDKit's MolToInchi if possible)."
            )
        elif parser == "molblock":
            suggestion = (
                "Suggested fix: check the V2000/V3000 block "
                "(atom/bond counts, valences, and whitespace)."
            )
        else:
            suggestion = _quick_fix_suggestion(stripped)
        raise ChemGlyphParseError(f"Could not parse structure ({parser}): {raw}. {suggestion}")
    return mol


def _parse_smiles(smiles: str) -> tuple[Chem.Mol | None, str]:
    from .validate import parse_smiles

    return parse_smiles(smiles)


def _quick_fix_suggestion(structure: str) -> str:
    from .validate import suggest_quick_fix  # avoid import cycle at module load

    suggestion = suggest_quick_fix(structure)
    if suggestion:
        return f"Suggested fix: {suggestion}"
    return "Suggested fix: check bracket pairing, ring-closure numbers, and atom valences."


def _prepare_for_drawing(mol: Chem.Mol) -> None:
    # Sanitize-only cleaning per §5: no tautomer or functional-group
    # normalization, so the drawn structure matches the input.
    Chem.SanitizeMol(mol)
    rdDepictor.SetPreferCoordGen(True)
    rdDepictor.Compute2DCoords(mol)
    _repair_ring_embeddings(mol)


def _repair_ring_embeddings(mol: Chem.Mol) -> None:
    """Move substituents that a layout tucked inside a small ring back out.

    RDKit's 2D layouts occasionally place a pendant atom inside a ring's
    cavity (for example paclitaxel's gem-dimethyl ends up inside the central
    8-membered ring), which makes the drawing read as a different, larger
    ring system. This geometric repair runs after layout, moves only atom
    positions, and never touches bonds, atom order, or stereo flags.
    """
    for _ in range(4):
        problem = _embedded_atom(mol)
        if problem is None:
            return
        ring, atom_index = problem
        _push_atom_outside(mol, ring, atom_index)


def _ring_polygons(mol: Chem.Mol) -> list[tuple[int, ...]]:
    """Ring atom tuples for rings small enough to hold a visible cavity."""
    return [tuple(ring) for ring in mol.GetRingInfo().AtomRings() if len(ring) <= 8]


def _positions(mol: Chem.Mol) -> dict[int, tuple[float, float]]:
    conformer = mol.GetConformer()
    return {
        i: (conformer.GetAtomPosition(i).x, conformer.GetAtomPosition(i).y)
        for i in range(mol.GetNumAtoms())
    }


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test (strictly inside, boundary excluded)."""
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


def _embedded_atom(mol: Chem.Mol) -> tuple[tuple[int, ...], int] | None:
    positions = _positions(mol)
    for ring in _ring_polygons(mol):
        ring_set = set(ring)
        polygon = [positions[i] for i in ring]
        for atom_index, point in positions.items():
            if atom_index in ring_set:
                continue
            if _point_in_polygon(point, polygon):
                return ring, atom_index
    return None


def _inside_any_ring(
    mol: Chem.Mol,
    positions: dict[int, tuple[float, float]],
    atom_index: int,
    point: tuple[float, float],
) -> bool:
    for ring in _ring_polygons(mol):
        if atom_index in ring:
            continue
        if _point_in_polygon(point, [positions[i] for i in ring]):
            return True
    return False


def _candidate_conflicts(
    mol: Chem.Mol,
    positions: dict[int, tuple[float, float]],
    parent_index: int,
    atom_index: int,
    point: tuple[float, float],
    escaped_ring: set[int],
) -> bool:
    """True when a candidate position would overlap an atom or cross a bond."""
    parent_point = positions[parent_index]
    for bond in mol.GetBonds():
        begin, end = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        if atom_index in (begin, end) or parent_index in (begin, end):
            continue
        if begin in escaped_ring and end in escaped_ring:
            continue  # the substituent has to cross this ring's boundary to exit
        if _segments_cross(parent_point, point, positions[begin], positions[end]):
            return True
    for other_index, other_point in positions.items():
        if other_index in (atom_index, parent_index):
            continue
        if other_index in escaped_ring:
            continue  # the substituent exits past this ring's own atoms
        if math.hypot(point[0] - other_point[0], point[1] - other_point[1]) < 0.55:
            return True
    return False


def _segments_cross(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    """Proper intersection test for two segments (shared endpoints excluded)."""

    def orientation(
        p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]
    ) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    first, second, third, fourth = (
        orientation(c, d, a),
        orientation(c, d, b),
        orientation(a, b, c),
        orientation(a, b, d),
    )
    return bool(
        ((first > 0 and second < 0) or (first < 0 and second > 0))
        and ((third > 0 and fourth < 0) or (third < 0 and fourth > 0))
    )


def _push_atom_outside(mol: Chem.Mol, ring: tuple[int, ...], atom_index: int) -> None:
    """Move one embedded atom (and, if needed, its pendant subtree) outward."""
    positions = _positions(mol)
    atom = mol.GetAtomWithIdx(atom_index)
    ring_set = set(ring)
    point = positions[atom_index]

    # Ring centroid gives the "inside" reference direction for this ring.
    centroid = (
        sum(positions[i][0] for i in ring) / len(ring),
        sum(positions[i][1] for i in ring) / len(ring),
    )

    if atom.GetDegree() == 1:
        parent = atom.GetNeighbors()[0]
        parent_point = positions[parent.GetIdx()]
        bond_length = math.hypot(point[0] - parent_point[0], point[1] - parent_point[1])
        outward = (
            parent_point[0] - centroid[0],
            parent_point[1] - centroid[1],
        )
        outward_norm = math.hypot(*outward) or 1.0
        outward = (outward[0] / outward_norm, outward[1] / outward_norm)
        current = (
            (point[0] - parent_point[0]) / (bond_length or 1.0),
            (point[1] - parent_point[1]) / (bond_length or 1.0),
        )
        dot = current[0] * outward[0] + current[1] * outward[1]
        reflected = (current[0] - 2 * dot * outward[0], current[1] - 2 * dot * outward[1])
        rotated = []
        for degrees in (0, 30, -30, 60, -60, 90, -90, 120, -120, 180):
            if atom_index % 2:
                degrees = -degrees
            radians = math.radians(degrees)
            rotated.append(
                (
                    outward[0] * math.cos(radians) - outward[1] * math.sin(radians),
                    outward[0] * math.sin(radians) + outward[1] * math.cos(radians),
                )
            )
        for direction in (reflected, *rotated):
            candidate = (
                parent_point[0] + bond_length * direction[0],
                parent_point[1] + bond_length * direction[1],
            )
            if not _inside_any_ring(
                mol, positions, atom_index, candidate
            ) and not _candidate_conflicts(
                mol, positions, parent.GetIdx(), atom_index, candidate, ring_set
            ):
                _set_position(mol, atom_index, candidate)
                return
        # Last resort: keep the bond direction but stretch it just past the
        # ring boundary along the centroid ray (rare; usually the rotations
        # above find a bond-length-preserving exit).
        centroid_direction = (
            point[0] - centroid[0],
            point[1] - centroid[1],
        )
        centroid_norm = math.hypot(*centroid_direction) or 1.0
        centroid_direction = (
            centroid_direction[0] / centroid_norm,
            centroid_direction[1] / centroid_norm,
        )
        exit_point = _ray_exit(point, centroid_direction, [positions[i] for i in ring])
        if exit_point is not None:
            candidate = (
                exit_point[0] + 0.35 * centroid_direction[0],
                exit_point[1] + 0.35 * centroid_direction[1],
            )
            if not _candidate_conflicts(
                mol, positions, parent.GetIdx(), atom_index, candidate, ring_set
            ):
                _set_position(mol, atom_index, candidate)
        return

    # Higher-degree atom: translate the whole pendant subtree until the
    # embedded atom exits the ring along the centroid ray.
    direction = (point[0] - centroid[0], point[1] - centroid[1])
    norm = math.hypot(*direction) or 1.0
    direction = (direction[0] / norm, direction[1] / norm)
    displacement = _ray_exit(point, direction, [positions[i] for i in ring])
    if displacement is None:
        return
    margin = 0.25
    delta = (
        displacement[0] + margin * direction[0] - point[0],
        displacement[1] + margin * direction[1] - point[1],
    )
    subtree = _pendant_subtree(mol, atom_index, ring_set)
    for member in subtree:
        member_point = positions[member]
        _set_position(mol, member, (member_point[0] + delta[0], member_point[1] + delta[1]))


def _ray_exit(
    origin: tuple[float, float],
    direction: tuple[float, float],
    polygon: list[tuple[float, float]],
) -> tuple[float, float] | None:
    """First polygon boundary crossing along ``origin + t*direction``."""
    best: tuple[float, tuple[float, float]] | None = None
    for i in range(len(polygon)):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % len(polygon)]
        ex, ey = x2 - x1, y2 - y1
        denominator = direction[0] * ey - direction[1] * ex
        if abs(denominator) < 1e-9:
            continue
        t = ((x1 - origin[0]) * ey - (y1 - origin[1]) * ex) / denominator
        u = ((x1 - origin[0]) * direction[1] - (y1 - origin[1]) * direction[0]) / denominator
        if t > 1e-6 and -1e-6 <= u <= 1 + 1e-6 and (best is None or t < best[0]):
            best = (t, (origin[0] + t * direction[0], origin[1] + t * direction[1]))
    return best[1] if best else None


def _pendant_subtree(mol: Chem.Mol, root: int, blocked: set[int]) -> set[int]:
    """Non-ring atoms reachable from ``root`` without passing through a ring."""
    seen = {root}
    stack = [root]
    while stack:
        current = stack.pop()
        for neighbor in mol.GetAtomWithIdx(current).GetNeighbors():
            neighbor_index = neighbor.GetIdx()
            if neighbor_index in blocked or neighbor_index in seen:
                continue
            seen.add(neighbor_index)
            stack.append(neighbor_index)
    return seen


def _set_position(mol: Chem.Mol, atom_index: int, point: tuple[float, float]) -> None:
    mol.GetConformer().SetAtomPosition(atom_index, Geometry.Point3D(point[0], point[1], 0.0))


def _normalize_fmt(fmt: str) -> str:
    normalized = fmt.strip().lower()
    if normalized not in {"svg", "png"}:
        raise ChemGlyphRenderError(f"Unsupported format {fmt!r}; use 'svg' or 'png'.")
    return normalized


def _build_options(
    spec: StyleSpec,
    *,
    mol: Chem.Mol,
    transparent: bool,
    show_atom_indices: bool,
) -> rdMolDraw2D.MolDrawOptions:
    options = rdMolDraw2D.MolDrawOptions()
    if spec.draw_options.get("acs1996_mode"):
        _apply_acs1996_mode(options, mol)
    if spec.draw_options.get("use_bw_atom_palette"):
        _use_bw_atom_palette(options)
    for key, value in spec.draw_options.items():
        if key in _SPECIAL_OPTION_KEYS:
            continue
        if key == "atom_colours":
            palette = {
                atomic_number: parse_hex_color(color) for atomic_number, color in value.items()
            }
            _set_atom_palette(options, palette)
            continue
        setattr(options, key, value)
    if transparent:
        options.backgroundColour = _colour(0.0, 0.0, 0.0, 0.0)
    else:
        background = spec.background or "#ffffff"
        options.backgroundColour = _colour(*parse_hex_color(background), 1.0)
    options.addAtomIndices = show_atom_indices
    return options


def _colour(red: float, green: float, blue: float, alpha: float = 1.0):
    """Build an RDKit color across API generations (DrawColour vs tuple)."""
    draw_colour = getattr(rdMolDraw2D, "DrawColour", None)
    if draw_colour is not None:
        return draw_colour(red, green, blue, alpha)
    return (red, green, blue, alpha)


def _use_bw_atom_palette(options: rdMolDraw2D.MolDrawOptions) -> None:
    switch = getattr(options, "useBWAtomPalette", None)
    if callable(switch):
        switch()
    else:
        options.useBWAtomPalette = True


def _set_atom_palette(
    options: rdMolDraw2D.MolDrawOptions,
    palette: dict[int, tuple[float, float, float]],
) -> None:
    setter = getattr(options, "setAtomPalette", None)
    if setter is not None:
        setter(palette)
        return
    # Legacy API (RDKit < 2025): an atomColourPalette map of DrawColour objects.
    for atomic_number, rgb in palette.items():
        options.atomColourPalette[atomic_number] = _colour(*rgb)


def _apply_acs1996_mode(options: rdMolDraw2D.MolDrawOptions, mol: Chem.Mol) -> None:
    """Enable RDKit's ACS1996 preset with the molecule's real mean bond length.

    ``SetACS1996Mode`` derives its scale from ``14.4 / meanBondLength``, so it
    must receive the actual mean bond length of *this* molecule (RDKit's
    ``MeanBondLength`` helper, which requires 2D coordinates). Passing a
    constant such as ``0.18`` inflates every bond ~8x while the preset still
    pins the label font at 10px, which is what made ACS labels look tiny.

    The preset also pins ``fixedBondLength``/``fixedFontSize`` (absolute pixel
    sizes that ignore the canvas); the ``acs`` StyleSpec re-enables adaptive
    scaling by resetting both to -1, letting ``minFontSize``/``maxFontSize``
    govern the label size like the other styles.
    """
    acs1996 = getattr(rdMolDraw2D, "SetACS1996Mode", None)
    if acs1996 is None:
        return
    mean_bond_length = getattr(rdMolDraw2D, "MeanBondLength", None)
    if mean_bond_length is not None:
        value = float(mean_bond_length(mol))
        if value <= 0.0:
            value = 1.4  # bondless molecule (e.g. a single atom): typical bond length
        try:
            acs1996(options, value)  # RDKit >= 2022.09
            return
        except TypeError:
            pass  # fall through to the legacy single-argument signature
    acs1996(options)


def _estimate_canvas(mol: Chem.Mol) -> tuple[int, int]:
    """Estimate a canvas whose aspect ratio matches the 2D coordinates.

    RDKit scales the drawing uniformly to fit the canvas, so matching the
    aspect ratio avoids large unused margins for flat or tall molecules.
    """
    conformer = mol.GetConformer()
    positions = [conformer.GetAtomPosition(i) for i in range(conformer.GetNumAtoms())]
    if not positions:
        return 300, 300
    xs = [position.x for position in positions]
    ys = [position.y for position in positions]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    # Coordinate units are roughly bond lengths; add padding for atom labels.
    pixels_per_unit = 30.0
    side_margin = 1.6
    width = _clamp((span_x + 2.0 * side_margin) * pixels_per_unit, 150.0, 1400.0)
    height = _clamp((span_y + 2.0 * side_margin) * pixels_per_unit, 150.0, 1400.0)
    return int(width), int(height)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _draw_svg(
    mol: Chem.Mol,
    options: rdMolDraw2D.MolDrawOptions,
    canvas: tuple[int, int],
    highlight_atoms: list[int] | None,
    *,
    transparent: bool,
) -> str:
    width, height = canvas
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    drawer.SetDrawOptions(options)
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol, highlightAtoms=highlight_atoms or [])
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText()
    return _strip_transparent_background(svg) if transparent else svg


def _strip_transparent_background(svg: str) -> str:
    """Drop RDKit's background rect (always the first ``<rect>`` element).

    RDKit versions differ: newer builds emit an alpha-0 fill, older builds
    still emit an opaque white rect for an alpha-0 background color. Either
    way the rect is the first element in the document, so removing it is the
    robust transparent-background fix.
    """
    return _FIRST_RECT_ELEMENT.sub("", svg, count=1)


def _draw_png(
    mol: Chem.Mol,
    options: rdMolDraw2D.MolDrawOptions,
    canvas: tuple[int, int],
    highlight_atoms: list[int] | None,
) -> bytes:
    try:
        drawer = rdMolDraw2D.MolDraw2DCairo(*canvas)
    except (AttributeError, ImportError) as exc:
        raise ChemGlyphRenderError(
            "PNG output requires the RDKit Cairo backend. Install a build with "
            "Cairo support (for example `pip install rdkit[cairo]`, or the "
            "conda-forge `rdkit` package), or use fmt='svg'."
        ) from exc
    drawer.SetDrawOptions(options)
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol, highlightAtoms=highlight_atoms or [])
    drawer.FinishDrawing()
    data = drawer.GetDrawingText()
    return bytes(data)


def _stereo_warnings(mol: Chem.Mol) -> list[str]:
    centers = Chem.FindMolChiralCenters(mol, includeUnassigned=True)
    unassigned = sum(1 for _, tag in centers if tag == "?")
    if unassigned:
        return [f"stereo centers without defined configuration: {unassigned}"]
    return []
