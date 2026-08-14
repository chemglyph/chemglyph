"""MCP server exposing ChemGlyph tools over stdio (see §9 of the specification).

Run with the ``chemglyph-mcp`` console script (or ``python -m
chemglyph.mcp_server``) and register it in an MCP client such as Claude
Desktop. The server speaks the official MCP protocol through the ``mcp`` SDK.
"""

from __future__ import annotations

import base64
from dataclasses import asdict
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ImageContent, TextContent

from . import __version__, parse_name, render_molecule, render_reaction, validate_structure
from .errors import ChemGlyphError

server = MCPServer(
    name="chemglyph",
    title="ChemGlyph",
    description="Publication-quality chemical structure & reaction rendering for AI agents",
    version=__version__,
)


@server.tool(
    name="render_molecule",
    description=(
        "Draw a single chemical structure as SVG or PNG. Use this when the user "
        "asks to render a molecule from SMILES, InChI, or a molblock. Example: "
        '{"structure": "CC(=O)Oc1ccccc1C(=O)O", "style": "modern", "fmt": "svg"}. '
        "Returns the image plus canonical SMILES, formula, molecular weight, and warnings."
    ),
    structured_output=False,
)
def render_molecule_tool(
    structure: str,
    style: str = "modern",
    fmt: str = "svg",
    transparent: bool = True,
    show_atom_indices: bool = False,
    highlight_atoms: list[int] | None = None,
) -> list[ImageContent | TextContent]:
    """MCP wrapper for :func:`chemglyph.render_molecule`."""
    try:
        result = render_molecule(
            structure,
            style=style,
            fmt=fmt,
            transparent=transparent,
            show_atom_indices=show_atom_indices,
            highlight_atoms=highlight_atoms,
        )
    except ChemGlyphError as exc:
        return [_error(str(exc))]
    if result.fmt == "png":
        encoded = base64.b64encode(result.data).decode("ascii")
        image = ImageContent(type="image", data=encoded, mime_type="image/png")
    else:
        encoded = base64.b64encode(result.data.encode("utf-8")).decode("ascii")
        image = ImageContent(type="image", data=encoded, mime_type="image/svg+xml")
    metadata = TextContent(
        type="text",
        text=(
            f"canonical_smiles: {result.canonical_smiles}\n"
            f"formula: {result.mol_formula}\n"
            f"molecular_weight: {result.mol_weight:.4f}\n"
            f"format: {result.fmt}\n"
            f"warnings: {result.warnings}"
        ),
    )
    return [image, metadata]


@server.tool(
    name="render_reaction",
    description=(
        "Draw a chemical reaction or synthesis route. Use this when the user "
        "asks for a reaction scheme. Pass conditions as pre-formatted Unicode "
        "text (e.g. H₂SO₄); ChemGlyph does not parse formulas out of text. "
        'Example: {"steps": [{"reactants": ["c1ccccc1O", "CC(=O)OC(C)=O"], '
        '"products": ["CC(=O)Oc1ccccc1C(=O)O"], "conditions": {"above": "H₂SO₄ (cat.)", '
        '"below": "rt, 15 min"}, "yield": "89%", "arrow": "forward"}], "style": "modern"}. '
        "See docs/reaction_schema.md for the full schema."
    ),
    structured_output=False,
)
def render_reaction_tool(spec: dict[str, Any]) -> list[ImageContent | TextContent]:
    """MCP wrapper for :func:`chemglyph.render_reaction`."""
    try:
        svg = render_reaction(spec)
    except ChemGlyphError as exc:
        return [_error(str(exc))]
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return [
        ImageContent(type="image", data=encoded, mime_type="image/svg+xml"),
        TextContent(
            type="text",
            text="Rendered reaction scheme SVG (also attached as an image).",
        ),
    ]


@server.tool(
    name="validate_structure",
    description=(
        "Validate a structure string and return errors plus automatic fixes. "
        "Use this when a SMILES may be malformed and you want a repair "
        "suggestion before rendering. Example: "
        '{"structure": "c1ccc1"} returns the fixed SMILES "C1CCC1".'
    ),
    structured_output=False,
)
def validate_structure_tool(structure: str) -> list[TextContent]:
    """MCP wrapper for :func:`chemglyph.validate_structure`."""
    try:
        report = validate_structure(structure)
    except ChemGlyphError as exc:
        return [_error(str(exc))]
    return [TextContent(type="text", text=str(asdict(report)))]


@server.tool(
    name="parse_name",
    description=(
        "Convert a chemical name into canonical SMILES, offline. Use this when "
        "the user gives a name like 'aspirin' or '阿司匹林' and you need SMILES. "
        "English IUPAC/common names resolve via OPSIN (needs the chemglyph[opsin] "
        "extra and a Java runtime); Chinese names resolve via the built-in "
        "dictionary, and unknown Chinese names return a clear error (this MCP "
        "tool cannot accept a translator callable — pre-translate to English "
        "yourself or use the library API)."
    ),
    structured_output=False,
)
def parse_name_tool(name: str) -> list[TextContent]:
    """MCP wrapper for :func:`chemglyph.parse_name`."""
    try:
        smiles = parse_name(name)
    except NotImplementedError as exc:
        return [_error(str(exc))]
    except ChemGlyphError as exc:
        return [_error(str(exc))]
    return [TextContent(type="text", text=smiles)]


def _error(message: str) -> TextContent:
    return TextContent(type="text", text=f"ChemGlyph error: {message}")


def main() -> None:
    """Entry point for the ``chemglyph-mcp`` console script."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
