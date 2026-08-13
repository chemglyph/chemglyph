"""Single-molecule rendering on top of RDKit (see §5 of the specification)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rdkit import Chem
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
        try:
            acs1996(options, mean_bond_length(mol))  # RDKit >= 2022.09
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
