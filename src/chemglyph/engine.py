"""Fixed-scale structure drawing (docs/SPEC.md, sections 2 and 5).

RDKit lays out and draws the molecule; this module makes the result obey a
:class:`~chemglyph.profiles.Profile` exactly:

1. Scale. RDKit draws on a canvas large enough for its fixed bond length to
   be honored, at ``UNITS_PER_PT`` resolution, with no padding. The output
   is cropped to the drawn content and its size declared in points, so a
   14.4 pt bond is 14.4 pt on paper for every molecule.
2. Label clearance. RDKit clips bonds against each label's bounding box,
   which removes far too much of a bond that leaves a label diagonally (the
   S-O bonds of sulfate kept 1.4 pt of 14.4 pt). Bond ends next to a label
   are recomputed so that they stop ``margin_width_pt`` from the glyph
   outline itself, the way structure editors do it.
3. Hashed wedges. RDKit draws hashes 0.5 pt apart with hairline strokes.
   They are redrawn at the profile's hash spacing and line width.
4. Stroke floor. No stroke is thinner than the profile's line width.

Measurements from step 1 to 3 are returned so callers can verify them.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from importlib import resources

import numpy as np
from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D

from .profiles import Profile
from .svg_utils import content_viewbox, inner_content, parse_hex_color

UNITS_PER_PT = 10.0  # internal SVG user units per point
_STEP_PT = 0.02  # resolution of the label-clearance search
_CURVE_SAMPLES = 8

_BACKGROUND_RECT = re.compile(r"<rect\b[^>]*(?:/>|>.*?</rect>)", re.DOTALL)
_BOND_PATH = re.compile(
    r"<path class='bond-(\d+) atom-(\d+) atom-(\d+)' "
    r"d='M ([-\d.]+),([-\d.]+) L ([-\d.]+),([-\d.]+)'([^>]*)/>"
)
_ATOM_PATH = re.compile(r"<path class='atom-(\d+)' d='([^']+)'")
_STROKE_WIDTH = re.compile(r"stroke-width:([\d.]+)px")
_TOKEN = re.compile(r"[MLQCZ]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")


@dataclass
class Drawing:
    """A fixed-scale SVG plus what was measured while making it."""

    svg: str
    width_pt: float
    height_pt: float
    bond_length_pt: tuple[float, float]  # (min, max) over all bonds
    label_clearance_pt: float | None  # smallest gap from a bond end to a glyph
    shortest_labelled_bond_pt: float | None  # shortest visible bond touching a label
    notes: list[str] = field(default_factory=list)


def font_file() -> str:
    """Path to the bundled label font (Liberation Sans, SIL OFL 1.1)."""
    return str(resources.files("chemglyph") / "fonts" / "LiberationSans-Regular.ttf")


def draw(
    mol: Chem.Mol,
    profile: Profile,
    *,
    highlight_atoms: list[int] | None = None,
    show_atom_indices: bool = False,
    background: str | None = None,
) -> Drawing:
    """Draw a molecule that already has 2D coordinates at the profile's scale."""
    prepared = rdMolDraw2D.PrepareMolForDrawing(mol)
    k = UNITS_PER_PT
    mean = rdMolDraw2D.MeanBondLength(prepared)
    if mean <= 0.0:
        mean = 1.0  # no bonds: coordinates are still in bond-length units
    scale = profile.bond_length_pt * k / mean  # user units per coordinate unit

    conformer = prepared.GetConformer()
    xs = [conformer.GetAtomPosition(i).x for i in range(prepared.GetNumAtoms())]
    ys = [conformer.GetAtomPosition(i).y for i in range(prepared.GetNumAtoms())]
    room = 8 * profile.font_size_pt * k  # labels, charges, and H counts fit inside
    width = int((max(xs) - min(xs)) * scale + 2 * room)
    height = int((max(ys) - min(ys)) * scale + 2 * room)

    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    drawer.SetDrawOptions(_options(profile, mean, scale, show_atom_indices))
    drawer.DrawMolecule(prepared, highlightAtoms=highlight_atoms or [])
    drawer.FinishDrawing()
    raw = _BACKGROUND_RECT.sub("", drawer.GetDrawingText(), count=1)

    positions = {
        i: (drawer.GetDrawCoords(i).x, drawer.GetDrawCoords(i).y)
        for i in range(prepared.GetNumAtoms())
    }
    bond_lengths = _bond_lengths_pt(prepared, positions)
    glyphs = _glyph_edges(raw)

    hashed = {
        bond.GetIdx() for bond in prepared.GetBonds() if bond.GetBondDir() == Chem.BondDir.BEGINDASH
    }
    clipper = _Clipper(
        positions,
        glyphs,
        profile.margin_width_pt * k,
        0.75 * profile.bond_spacing * profile.bond_length_pt * k,
    )
    wedged = {
        bond.GetIdx()
        for bond in prepared.GetBonds()
        if bond.GetBondDir() == Chem.BondDir.BEGINWEDGE
    }
    body, hash_segments = _clip_bonds(raw, hashed, clipper)
    body = _redraw_hashes(body, prepared, hashed, hash_segments, clipper, profile)
    body = _redraw_wedges(body, prepared, wedged, clipper)
    floor = profile.line_width_pt * k
    body = _STROKE_WIDTH.sub(lambda m: f"stroke-width:{max(float(m.group(1)), floor):.1f}px", body)

    box = content_viewbox(body, margin=profile.canvas_margin_pt * k)
    rect = ""
    if background is not None:
        rect = (
            f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.width:.1f}" '
            f'height="{box.height:.1f}" fill="{background}"/>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{box.width / k:.2f}pt" '
        f'height="{box.height / k:.2f}pt" viewBox="{box.x:.1f} {box.y:.1f} '
        f'{box.width:.1f} {box.height:.1f}">{rect}{inner_content(body)}</svg>'
    )
    return Drawing(
        svg=svg,
        width_pt=box.width / k,
        height_pt=box.height / k,
        bond_length_pt=(min(bond_lengths, default=0.0), max(bond_lengths, default=0.0)),
        label_clearance_pt=(
            clipper.min_clearance / k if clipper.min_clearance is not None else None
        ),
        shortest_labelled_bond_pt=(
            clipper.shortest_visible / k if clipper.shortest_visible is not None else None
        ),
        notes=clipper.notes,
    )


def _options(
    profile: Profile, mean: float, scale: float, show_atom_indices: bool
) -> rdMolDraw2D.MolDrawOptions:
    k = UNITS_PER_PT
    options = rdMolDraw2D.MolDrawOptions()
    if hasattr(rdMolDraw2D, "SetACS1996Mode"):
        rdMolDraw2D.SetACS1996Mode(options, mean)  # monochrome and label conventions
    options.padding = 0.0
    options.fixedBondLength = scale
    options.fixedFontSize = int(round(profile.font_size_pt * k))
    options.bondLineWidth = profile.line_width_pt * k
    options.scaleBondWidth = False
    options.multipleBondOffset = profile.bond_spacing
    options.fontFile = font_file()
    options.addAtomIndices = show_atom_indices
    options.prepareMolsBeforeDrawing = False
    if profile.atom_colours:
        palette = {z: parse_hex_color(colour) for z, colour in profile.atom_colours.items()}
        setter = getattr(options, "setAtomPalette", None)
        if setter is not None:
            setter(palette)
    return options


def _bond_lengths_pt(mol: Chem.Mol, positions: dict[int, tuple[float, float]]) -> list[float]:
    conformer = mol.GetConformer()
    mean = rdMolDraw2D.MeanBondLength(mol) or 1.0
    lengths = []
    for bond in mol.GetBonds():
        begin, end = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        coordinate = (conformer.GetAtomPosition(begin) - conformer.GetAtomPosition(end)).Length()
        if coordinate <= 0.0:
            continue
        drawn = math.dist(positions[begin], positions[end])
        # Report the drawn length of a bond of mean length, in points.
        lengths.append(drawn / coordinate * mean / UNITS_PER_PT)
    return lengths


def _glyph_edges(svg: str) -> dict[int, np.ndarray]:
    """Label outlines per atom as an (n, 4) array of segments x1, y1, x2, y2."""
    edges: dict[int, list[tuple[float, float, float, float]]] = {}
    for match in _ATOM_PATH.finditer(svg):
        atom = int(match.group(1))
        edges.setdefault(atom, []).extend(_flatten(match.group(2)))
    return {atom: np.array(items) for atom, items in edges.items() if items}


def _flatten(path: str) -> list[tuple[float, float, float, float]]:
    """Polyline segments of an SVG outline made of M, L, Q, C, and Z commands."""
    tokens = _TOKEN.findall(path)
    segments: list[tuple[float, float, float, float]] = []
    command = "M"
    start = current = (0.0, 0.0)
    index = 0

    def take(count: int) -> list[float]:
        nonlocal index
        values = [float(v) for v in tokens[index : index + count]]
        index += count
        return values

    while index < len(tokens):
        token = tokens[index]
        if token in "MLQCZ":
            command = token
            index += 1
            if command == "Z":
                segments.append((*current, *start))
                current = start
            continue
        if command == "M":
            current = start = tuple(take(2))  # type: ignore[assignment]
            command = "L"  # further pairs after M are line-tos
        elif command == "L":
            point = tuple(take(2))
            segments.append((*current, *point))
            current = point  # type: ignore[assignment]
        elif command == "Q":
            cx, cy, x, y = take(4)
            previous = current
            for step in range(1, _CURVE_SAMPLES + 1):
                t = step / _CURVE_SAMPLES
                px = (1 - t) ** 2 * current[0] + 2 * (1 - t) * t * cx + t**2 * x
                py = (1 - t) ** 2 * current[1] + 2 * (1 - t) * t * cy + t**2 * y
                segments.append((*previous, px, py))
                previous = (px, py)
            current = (x, y)
        elif command == "C":
            c1x, c1y, c2x, c2y, x, y = take(6)
            previous = current
            for step in range(1, _CURVE_SAMPLES + 1):
                t = step / _CURVE_SAMPLES
                u = 1 - t
                px = u**3 * current[0] + 3 * u**2 * t * c1x + 3 * u * t**2 * c2x + t**3 * x
                py = u**3 * current[1] + 3 * u**2 * t * c1y + 3 * u * t**2 * c2y + t**3 * y
                segments.append((*previous, px, py))
                previous = (px, py)
            current = (x, y)
        else:  # pragma: no cover - RDKit emits only the commands above
            index += 1
    return segments


def _distance_to_edges(points: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Distance from each point (n, 2) to the nearest segment in edges (m, 4)."""
    a = edges[:, 0:2]
    b = edges[:, 2:4]
    ab = b - a
    length2 = np.maximum((ab**2).sum(axis=1), 1e-12)
    ap = points[:, None, :] - a[None, :, :]
    t = np.clip((ap * ab[None, :, :]).sum(axis=2) / length2[None, :], 0.0, 1.0)
    closest = a[None, :, :] + t[:, :, None] * ab[None, :, :]
    return np.sqrt(((points[:, None, :] - closest) ** 2).sum(axis=2)).min(axis=1)


class _Clipper:
    """Moves bond ends so they stop a fixed gap away from label glyphs."""

    def __init__(
        self,
        positions: dict[int, tuple[float, float]],
        glyphs: dict[int, np.ndarray],
        margin: float,
        offset_threshold: float,
    ) -> None:
        self.positions = positions
        self.glyphs = glyphs
        self.margin = margin
        # A centred double bond's lines sit half a spacing off the atom axis;
        # the inner line of an offset double bond sits a full spacing off.
        self.offset_threshold = offset_threshold
        self.min_clearance: float | None = None
        self.shortest_visible: float | None = None
        self.notes: list[str] = []

    def segment(
        self, p1: tuple[float, float], p2: tuple[float, float], atom_a: int, atom_b: int
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """Recompute the ends of one drawn line of the bond atom_a-atom_b."""
        labelled = [atom for atom in (atom_a, atom_b) if atom in self.glyphs]
        if not labelled:
            return p1, p2
        direction = np.array(p2) - np.array(p1)
        length = float(np.hypot(*direction))
        if length < 1e-9:
            return p1, p2
        unit = direction / length
        origin = np.array(p1)

        def along(point: tuple[float, float]) -> float:
            return float(np.dot(np.array(point) - origin, unit))

        ta, tb = along(self.positions[atom_a]), along(self.positions[atom_b])
        # The inner line of an offset double bond is shortened on purpose;
        # it may be pulled back from a label but never stretched toward it.
        normal = np.array([-unit[1], unit[0]])
        offset_line = all(
            abs(float(np.dot(np.array(self.positions[atom]) - origin, normal)))
            > self.offset_threshold
            for atom in (atom_a, atom_b)
        )
        # Ends are matched to atoms by order along the line, not by distance:
        # RDKit sometimes places a whole line on one atom's side.
        first, second = (atom_a, atom_b) if ta <= tb else (atom_b, atom_a)
        end_atoms = {0.0: first, length: second}
        window = self._clear_window(origin, unit, ta, tb, labelled, (atom_a, atom_b))
        if window is None:
            self.notes.append(
                f"bond {atom_a}-{atom_b}: no clear room between the labels; "
                "drawn as RDKit placed it"
            )
            return p1, p2
        low, high = window
        new_t = {0.0: 0.0, length: length}
        for t_end, atom in end_atoms.items():
            if atom not in self.glyphs:
                continue
            at_start = t_end == 0.0  # the start end pairs with the window's low side
            clipped = low if at_start else high
            if offset_line:
                # Only move toward the middle, never past RDKit's own end.
                clipped = max(clipped, t_end) if at_start else min(clipped, t_end)
            new_t[t_end] = clipped
        start, end = sorted((new_t[0.0], new_t[length]))
        visible = end - start
        if visible <= 0:
            self.notes.append(
                f"bond {atom_a}-{atom_b}: clipping left no line; drawn as RDKit placed it"
            )
            return p1, p2
        if self.shortest_visible is None or visible < self.shortest_visible:
            self.shortest_visible = visible
        for atom in labelled:
            gap = self._gap(origin + unit * start, origin + unit * end, self.glyphs[atom])
            if self.min_clearance is None or gap < self.min_clearance:
                self.min_clearance = gap
        q1 = origin + unit * start
        q2 = origin + unit * end
        return (float(q1[0]), float(q1[1])), (float(q2[0]), float(q2[1]))

    def _clear_window(
        self,
        origin: np.ndarray,
        unit: np.ndarray,
        ta: float,
        tb: float,
        labelled: list[int],
        atoms: tuple[int, int],
    ) -> tuple[float, float] | None:
        """The stretch of the atom-to-atom line that stays clear of every glyph.

        Distances are taken to the glyphs of both bonded atoms, so a charge
        sign of the far atom is avoided too. The longest clear run wins;
        when two labels crowd each other the margin is relaxed in steps and
        the relaxation is reported, rather than letting a bond touch a glyph.
        """
        step = _STEP_PT * UNITS_PER_PT
        lo, hi = min(ta, tb), max(ta, tb)
        count = max(2, int((hi - lo) / step) + 1)
        ts = np.linspace(lo, hi, count)
        points = origin[None, :] + ts[:, None] * unit[None, :]
        edges = np.vstack([self.glyphs[atom] for atom in labelled])
        distances = _distance_to_edges(points, edges)
        minimum_run = 1.0 * UNITS_PER_PT  # a visible bond shorter than 1 pt reads as a dot
        for factor in (1.0, 0.75, 0.5):
            clear = distances >= self.margin * factor
            best: tuple[float, float] | None = None
            run_start = None
            for index, ok in enumerate([*clear, False]):
                if ok and run_start is None:
                    run_start = index
                elif not ok and run_start is not None:
                    run = (float(ts[run_start]), float(ts[index - 1]))
                    if best is None or run[1] - run[0] > best[1] - best[0]:
                        best = run
                    run_start = None
            if best is not None and best[1] - best[0] >= minimum_run:
                if factor < 1.0:
                    self.notes.append(
                        f"labels crowd bond {atoms[0]}-{atoms[1]}; label margin reduced to "
                        f"{self.margin * factor / UNITS_PER_PT:.1f} pt"
                    )
                return best
        return None

    def _gap(self, q1: np.ndarray, q2: np.ndarray, edges: np.ndarray) -> float:
        points = np.linspace(q1, q2, 50)
        return float(_distance_to_edges(points, edges).min())


def _clip_bonds(
    svg: str, hashed: set[int], clipper: _Clipper
) -> tuple[str, dict[int, list[tuple[float, float, float, float]]]]:
    """Re-clip every straight bond line; pull hashed-wedge lines out for redrawing.

    Coloured styles draw one bond line as two halves, one per atom colour.
    Halves are joined back into one line, clipped as a whole, and split again
    at the new middle, each keeping its colour.
    """
    hash_segments: dict[int, list[tuple[float, float, float, float]]] = {}
    matches = list(_BOND_PATH.finditer(svg))
    by_bond: dict[int, list[re.Match[str]]] = {}
    for match in matches:
        by_bond.setdefault(int(match.group(1)), []).append(match)

    replacement: dict[int, str] = {}
    for bond, pieces in by_bond.items():
        if bond in hashed:
            for match in pieces:
                hash_segments.setdefault(bond, []).append(_coords(match))
                replacement[match.start()] = ""
            continue
        for line in _join_halves(pieces):
            atom_a, atom_b = int(line[0].group(2)), int(line[0].group(3))
            p1 = _coords(line[0])[:2]
            p2 = _coords(line[-1])[2:]
            q1, q2 = clipper.segment(p1, p2, atom_a, atom_b)
            if len(line) == 1:
                replacement[line[0].start()] = _bond_path(line[0], q1, q2)
                continue
            middle = ((q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2)
            replacement[line[0].start()] = _bond_path(line[0], q1, middle)
            replacement[line[-1].start()] = _bond_path(line[-1], middle, q2)
            for extra in line[1:-1]:
                replacement[extra.start()] = ""

    out: list[str] = []
    cursor = 0
    for match in matches:
        out.append(svg[cursor : match.start()])
        out.append(replacement.get(match.start(), match.group(0)))
        cursor = match.end()
    out.append(svg[cursor:])
    return "".join(out), hash_segments


def _coords(match: re.Match[str]) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = (float(v) for v in match.group(4, 5, 6, 7))
    return x1, y1, x2, y2


def _bond_path(match: re.Match[str], start: tuple[float, float], end: tuple[float, float]) -> str:
    bond, atom_a, atom_b = match.group(1, 2, 3)
    return (
        f"<path class='bond-{bond} atom-{atom_a} atom-{atom_b}' "
        f"d='M {start[0]:.1f},{start[1]:.1f} L {end[0]:.1f},{end[1]:.1f}'{match.group(8)}/>"
    )


def _join_halves(pieces: list[re.Match[str]]) -> list[list[re.Match[str]]]:
    """Chain pieces of one bond whose ends meet and that run in one direction."""
    remaining = list(pieces)
    lines: list[list[re.Match[str]]] = []
    while remaining:
        line = [remaining.pop(0)]
        extended = True
        while extended:
            extended = False
            for other in list(remaining):
                head, tail = _coords(line[0]), _coords(line[-1])
                candidate = _coords(other)
                if _meets(tail[2:], candidate[:2]) and _collinear(tail, candidate):
                    line.append(other)
                elif _meets(candidate[2:], head[:2]) and _collinear(candidate, head):
                    line.insert(0, other)
                else:
                    continue
                remaining.remove(other)
                extended = True
        lines.append(line)
    return lines


def _meets(p: tuple[float, ...], q: tuple[float, ...]) -> bool:
    return math.dist(p, q) < 0.5


def _collinear(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    ax, ay = a[2] - a[0], a[3] - a[1]
    bx, by = b[2] - b[0], b[3] - b[1]
    norm = math.hypot(ax, ay) * math.hypot(bx, by)
    return norm > 0 and abs(ax * by - ay * bx) / norm < 0.05 and ax * bx + ay * by > 0


def _redraw_hashes(
    svg: str,
    mol: Chem.Mol,
    hashed: set[int],
    original: dict[int, list[tuple[float, float, float, float]]],
    clipper: _Clipper,
    profile: Profile,
) -> str:
    """Hashed wedges at the profile's spacing, narrow end at the stereocentre."""
    k = UNITS_PER_PT
    paths = []
    for index in sorted(hashed):
        bond = mol.GetBondWithIdx(index)
        narrow, wide = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        p_narrow = clipper.positions[narrow]
        p_wide = clipper.positions[wide]
        (q1, q2) = clipper.segment(p_narrow, p_wide, narrow, wide)
        length = math.dist(q1, q2)
        if length <= 0:
            continue
        # Keep RDKit's wedge width at the wide end so solid and hashed wedges match.
        widths = [math.dist((x1, y1), (x2, y2)) for x1, y1, x2, y2 in original.get(index, [])]
        wide_width = max(widths, default=profile.bold_width_pt * k * 2)
        full = math.dist(p_narrow, p_wide)
        ux, uy = (q2[0] - q1[0]) / length, (q2[1] - q1[1]) / length
        nx, ny = -uy, ux
        count = max(3, round(length / (profile.hash_spacing_pt * k)))
        spacing = length / count
        lines = []
        for step in range(count):
            t = length - step * spacing  # from the wide end back toward the centre
            cx, cy = q1[0] + ux * t, q1[1] + uy * t
            # Width grows linearly from the stereocentre (distance from p_narrow).
            from_centre = math.dist(p_narrow, (cx, cy))
            half = max(wide_width * from_centre / full, profile.line_width_pt * k) / 2
            lines.append(
                f"M {cx - nx * half:.1f},{cy - ny * half:.1f} "
                f"L {cx + nx * half:.1f},{cy + ny * half:.1f}"
            )
        colour = profile.atom_colours.get(mol.GetAtomWithIdx(narrow).GetAtomicNum(), "#000000")
        paths.append(
            f"<path class='bond-{index} atom-{narrow} atom-{wide} hash' d='{' '.join(lines)}' "
            f"style='fill:none;stroke:{colour};stroke-width:{profile.line_width_pt * k:.1f}px;"
            "stroke-linecap:butt'/>"
        )
    if not paths:
        return svg
    closing = svg.rfind("</svg>")
    return svg[:closing] + "".join(paths) + svg[closing:]


_WEDGE_PATH = re.compile(r"<path class='bond-(\d+) atom-(\d+) atom-(\d+)' d='(M [^']*Z)'([^>]*)/>")


def _redraw_wedges(svg: str, mol: Chem.Mol, wedged: set[int], clipper: _Clipper) -> str:
    """Solid wedges re-clipped like every other bond end next to a label.

    The tip stays at the stereocentre and the wedge keeps RDKit's flare
    (width per unit length); only where it stops changes.
    """
    if not wedged:
        return svg
    pieces: dict[int, list[tuple[list[tuple[float, float]], str]]] = {}
    for found in _WEDGE_PATH.finditer(svg):
        if int(found.group(1)) in wedged:
            shape = [
                (float(x), float(y)) for x, y in re.findall(r"([-\d.]+),([-\d.]+)", found.group(4))
            ]
            pieces.setdefault(int(found.group(1)), []).append((shape, found.group(5)))
    seen: set[int] = set()

    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1))
        if index not in wedged:
            return match.group(0)
        if index in seen:
            return ""  # a wedge split into coloured halves becomes one shape
        seen.add(index)
        bond = mol.GetBondWithIdx(index)
        narrow, wide = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        p_narrow = clipper.positions[narrow]
        p_wide = clipper.positions[wide]
        full = math.dist(p_narrow, p_wide)
        corners = [point for shape, _ in pieces[index] for point in shape]
        # The whole wedge takes the colour of the piece at the stereocentre.
        style = min(
            pieces[index],
            key=lambda piece: min(math.dist(point, p_narrow) for point in piece[0]),
        )[1]
        if full <= 0 or len(corners) < 3:
            return match.group(0)
        ux, uy = (p_wide[0] - p_narrow[0]) / full, (p_wide[1] - p_narrow[1]) / full
        nx, ny = -uy, ux
        # Flare: half-width per unit distance from the tip, from RDKit's own shape.
        flare = max(
            abs((x - p_narrow[0]) * nx + (y - p_narrow[1]) * ny)
            / max((x - p_narrow[0]) * ux + (y - p_narrow[1]) * uy, 1e-9)
            for x, y in corners
            if (x - p_narrow[0]) * ux + (y - p_narrow[1]) * uy > 0.2 * full
        )
        q1, q2 = clipper.segment(p_narrow, p_wide, narrow, wide)
        t1 = (q1[0] - p_narrow[0]) * ux + (q1[1] - p_narrow[1]) * uy
        t2 = (q2[0] - p_narrow[0]) * ux + (q2[1] - p_narrow[1]) * uy

        def outline(a: float, b: float) -> list[tuple[float, float]]:
            ha, hb = flare * a, flare * b
            pa = (p_narrow[0] + ux * a, p_narrow[1] + uy * a)
            pb = (p_narrow[0] + ux * b, p_narrow[1] + uy * b)
            shape = [
                (pa[0] + nx * ha, pa[1] + ny * ha),
                (pb[0] + nx * hb, pb[1] + ny * hb),
                (pb[0] - nx * hb, pb[1] - ny * hb),
                (pa[0] - nx * ha, pa[1] - ny * ha),
            ]
            return [pa, shape[1], shape[2]] if ha < 0.05 else shape

        # The axis keeps the margin; pull the wide end back until the flared
        # corners keep it too.
        step = _STEP_PT * UNITS_PER_PT
        for atom, at_wide in ((wide, True), (narrow, False)):
            edges = clipper.glyphs.get(atom)
            if edges is None:
                continue
            while t2 - t1 > UNITS_PER_PT:
                shape = np.array(outline(t1, t2))
                ring = np.vstack([shape, shape[:1]])
                samples = np.vstack(
                    [np.linspace(ring[i], ring[i + 1], 12) for i in range(len(shape))]
                )
                if _distance_to_edges(samples, edges).min() >= clipper.margin - 1e-6:
                    break
                if at_wide:
                    t2 -= step
                else:
                    t1 += step
        points = outline(t1, t2)
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points) + " Z"
        return f"<path class='bond-{index} atom-{narrow} atom-{wide} wedge' d='{d}'{style}/>"

    return _WEDGE_PATH.sub(replace, svg)
