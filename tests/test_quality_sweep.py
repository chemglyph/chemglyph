"""Regression tests from the 2026-08-14 quality sweep.

Kept separate from the milestone test files so fixes found during the sweep
remain traceable to the exact symptoms they close.
"""

from __future__ import annotations

import sys
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from chemglyph import render_molecule, validate_structure
from chemglyph.errors import ChemGlyphParseError


def test_validate_quick_fix_does_not_leak_rdkit_stderr(capfd) -> None:
    report = validate_structure("c1cccc1")
    captured = capfd.readouterr()

    assert report.fixes[0].fixed_smiles == "C1CCCC1"
    assert "Can't kekulize" not in captured.err
    assert "Can't kekulize" not in captured.out


def test_console_script_entry_point_serves_mcp_over_stdio() -> None:
    # Resolve next to the active interpreter so PATH order (e.g. a PyPI copy in
    # the user site) cannot make the test exercise a different installation.
    script = str(Path(sys.executable).with_name("chemglyph-mcp"))

    async def run() -> set[str]:
        params = StdioServerParameters(command=script, args=[])
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                return {tool.name for tool in tools.tools}

    assert anyio.run(run) == {
        "render_molecule",
        "render_reaction",
        "validate_structure",
        "parse_name",
    }


def test_inchi_parse_error_suggests_inchi_not_smiles() -> None:
    with pytest.raises(ChemGlyphParseError) as exc:
        render_molecule("InChI=1S/not-a-real-inchi")
    message = str(exc.value)
    assert "verify the InChI" in message
    assert "bracket pairing" not in message
