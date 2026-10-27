"""Structure metadata embedded in rendered figures (docs/SPEC.md, sections 3 and 7).

Every figure carries the structure it shows, so the figure itself can be
checked or re-used later:

- SVG: a ``<metadata>`` element holding a ``chemglyph:structure`` record with
  the SMILES, InChI, InChIKey, and formula as attributes and the full molfile
  (coordinates and stereo) as text.
- PNG: RDKit's standard text chunks (SMILES and molfile), readable by
  ``rdkit.Chem.MolFromPNGString`` and by :func:`read_structure`.

RDKit's own SVG metadata is not used: it lost E/Z stereo (beta-damascone)
and could not be read back for azobenzene in the 2026-10-27 check, while the
molfile round-trips all 20 blind-test molecules exactly.
"""

from __future__ import annotations

import re
from contextlib import nullcontext
from html import escape

from rdkit import Chem, rdBase
from rdkit.Chem import rdMolDescriptors

from .errors import ChemGlyphParseError

NAMESPACE = "https://github.com/chemglyph/chemglyph"
_RECORD = re.compile(
    r"<chemglyph:structure\b[^>]*>\s*<!\[CDATA\[(.*?)\]\]>\s*</chemglyph:structure>",
    re.DOTALL,
)
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def quiet():
    """Silence RDKit's logger (InChI warnings for organometallics, for example)."""
    blocker = getattr(rdBase, "BlockLogs", None)
    return blocker() if blocker is not None else nullcontext()


def identity(mol: Chem.Mol) -> dict[str, str]:
    """SMILES, InChI, InChIKey, and formula of a molecule.

    Coordinates are dropped first, so stereo comes only from the molecule's
    stereo flags. Otherwise InChI reads E/Z geometry off the 2D layout for
    ring double bonds in macrocycles (porphyrin), and the same structure
    would get a different key with and without coordinates.
    """
    with quiet():
        bare = Chem.RemoveHs(mol)  # an H drawn only to show a wedge is not identity
    bare.RemoveAllConformers()
    with quiet():
        inchi = Chem.MolToInchi(bare) or ""
        key = Chem.InchiToInchiKey(inchi) if inchi else ""
    return {
        "smiles": Chem.MolToSmiles(bare),
        "inchi": inchi,
        "inchikey": key or "",
        "formula": rdMolDescriptors.CalcMolFormula(bare),
    }


_SAP_LINE = re.compile(r"^(M  SAP .*\S)$", re.MULTILINE)


def molblock(mol: Chem.Mol) -> str:
    """A V2000 molfile that RDKit and structure editors read back.

    RDKit writes the attachment id of an abbreviation (SUP group) as one
    character, and its own reader then rejects the line as too short; the
    CTfile format gives the id two characters, so the line is padded.
    """
    return _SAP_LINE.sub(lambda match: match.group(1) + " ", Chem.MolToMolBlock(mol))


def embed_svg(svg: str, mol: Chem.Mol, *, profile: str, version: str) -> str:
    """Insert the structure record right after the root ``<svg>`` tag."""
    ident = identity(mol)
    attributes = " ".join(
        f'{name}="{escape(value, quote=True)}"'
        for name, value in (
            ("version", version),
            ("profile", profile),
            ("smiles", ident["smiles"]),
            ("inchi", ident["inchi"]),
            ("inchikey", ident["inchikey"]),
            ("formula", ident["formula"]),
        )
    )
    record = (
        f'<metadata><chemglyph:structure xmlns:chemglyph="{NAMESPACE}" {attributes}>'
        f"<![CDATA[{molblock(mol)}]]></chemglyph:structure></metadata>"
    )
    head_end = svg.index(">", svg.index("<svg")) + 1
    return svg[:head_end] + record + svg[head_end:]


def embed_png(png: bytes, mol: Chem.Mol) -> bytes:
    """Add RDKit's standard SMILES and molfile text chunks to a PNG."""
    return bytes(Chem.MolMetadataToPNGString(mol, png))


def read_structure(figure: str | bytes) -> Chem.Mol:
    """Read the structure embedded in a ChemGlyph SVG, PNG, or PDF.

    Raises:
        ChemGlyphParseError: the figure carries no readable structure.
    """
    if isinstance(figure, bytes) and figure.startswith(b"%PDF-"):
        from .pdf import read_info

        molfile = read_info(figure).get("ChemGlyphMolfile")
        if not molfile:
            raise ChemGlyphParseError("The PDF carries no embedded structure.")
        with quiet():
            mol = Chem.MolFromMolBlock(molfile)
        if mol is None:
            raise ChemGlyphParseError("The molfile embedded in the PDF could not be parsed.")
        return mol
    if isinstance(figure, bytes) and figure.startswith(_PNG_SIGNATURE):
        with quiet():
            mol = Chem.MolFromPNGString(figure)
        if mol is None:
            raise ChemGlyphParseError("The PNG carries no embedded structure.")
        return mol
    text = figure.decode("utf-8") if isinstance(figure, bytes) else figure
    match = _RECORD.search(text)
    if match is None:
        raise ChemGlyphParseError("The SVG carries no chemglyph:structure record.")
    with quiet():
        mol = Chem.MolFromMolBlock(match.group(1))
    if mol is None:
        raise ChemGlyphParseError("The embedded molfile could not be parsed.")
    return mol
