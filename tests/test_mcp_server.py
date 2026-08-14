"""MCP server integration tests (see §9 of the specification).

Each test spawns the real server over stdio and drives it with the official
MCP client, so the protocol surface (tool list + call results) is exercised.
"""

from __future__ import annotations

import base64
import sys
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _call_tool(tool: str, arguments: dict[str, Any]) -> Any:
    async def run() -> Any:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "chemglyph.mcp_server"],
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await session.call_tool(tool, arguments)

    return anyio.run(run)


def _tool_names() -> set[str]:
    async def run() -> set[str]:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "chemglyph.mcp_server"],
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                return {tool.name for tool in tools.tools}

    return anyio.run(run)


def test_server_exposes_four_tools() -> None:
    assert _tool_names() == {
        "render_molecule",
        "render_reaction",
        "validate_structure",
        "parse_name",
    }


def test_render_molecule_returns_svg_image_and_metadata() -> None:
    result = _call_tool("render_molecule", {"structure": "CC(=O)Oc1ccccc1C(=O)O"})
    assert not result.is_error
    contents = result.content
    image = next(item for item in contents if item.type == "image")
    text = next(item for item in contents if item.type == "text")
    assert image.mime_type == "image/svg+xml"
    svg = base64.b64decode(image.data).decode("utf-8")
    assert "<svg" in svg
    assert "C9H8O4" in text.text


def test_render_reaction_returns_svg_image() -> None:
    result = _call_tool(
        "render_reaction",
        {
            "spec": {
                "steps": [
                    {
                        "reactants": ["OC(=O)c1ccccc1O", "CC(=O)OC(C)=O"],
                        "products": ["CC(=O)Oc1ccccc1C(=O)O"],
                        "conditions": {"above": "H2SO4 (cat.)"},
                        "yield": "89%",
                    }
                ]
            }
        },
    )
    assert not result.is_error
    image = next(item for item in result.content if item.type == "image")
    svg = base64.b64decode(image.data).decode("utf-8")
    assert "chemglyph-arrow" in svg


def test_validate_structure_returns_report_text() -> None:
    result = _call_tool("validate_structure", {"structure": "CC(=O)Oc1ccccc1C(=O)O"})
    assert not result.is_error
    text = next(item for item in result.content if item.type == "text")
    assert "'valid': True" in text.text


def test_parse_name_chinese_dictionary_resolves() -> None:
    result = _call_tool("parse_name", {"name": "阿司匹林"})
    assert not result.is_error
    text = next(item for item in result.content if item.type == "text")
    assert text.text == "CC(=O)Oc1ccccc1C(=O)O"


def test_parse_name_unknown_chinese_is_surfaced_as_error_text() -> None:
    result = _call_tool("parse_name", {"name": "六甲基苯"})
    assert not result.is_error
    text = next(item for item in result.content if item.type == "text")
    assert "built-in dictionary" in text.text
