"""SVG assembly, measurement, and viewBox math (standard library only).

ChemGlyph deliberately avoids an SVG library dependency; RDKit output is
predictable enough for these small, well-tested helpers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape

from .errors import ChemGlyphRenderError

SVG_NS = "http://www.w3.org/2000/svg"

_VIEWBOX_RE = re.compile(
    r"""<svg\b[^>]*?\bviewBox\s*=\s*["']\s*"""
    r"""([-+0-9.eE]+)[,\s]+([-+0-9.eE]+)[,\s]+([-+0-9.eE]+)[,\s]+([-+0-9.eE]+)\s*["']"""
)
_STROKE_WIDTH_RE = re.compile(r"(stroke-width:)([0-9.]+)(px)")


@dataclass(frozen=True)
class ViewBox:
    """A parsed SVG viewBox."""

    x: float
    y: float
    width: float
    height: float

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2.0


def extract_viewbox(svg: str) -> ViewBox | None:
    """Return the viewBox of an SVG root element, or ``None`` if absent."""
    match = _VIEWBOX_RE.search(svg)
    if match is None:
        return None
    x, y, width, height = (float(part) for part in match.groups())
    return ViewBox(x=x, y=y, width=width, height=height)


def require_viewbox(svg: str) -> ViewBox:
    """Like :func:`extract_viewbox` but raise on missing viewBox."""
    box = extract_viewbox(svg)
    if box is None:
        raise ChemGlyphRenderError("SVG fragment has no viewBox attribute")
    return box


def inner_content(svg: str) -> str:
    """Return everything between the root ``<svg ...>`` tag and ``</svg>``."""
    start = svg.find(">")
    end = svg.rfind("</svg>")
    if start == -1 or end == -1 or end <= start:
        raise ChemGlyphRenderError("SVG fragment is missing the root <svg> element")
    return svg[start + 1 : end]


def wrap_group(content: str, dx: float = 0.0, dy: float = 0.0) -> str:
    """Wrap SVG content in a ``<g>`` with a translate transform."""
    return f'<g transform="translate({_fmt(dx)},{_fmt(dy)})">{content}</g>'


def compose_svg(
    children: str | list[str],
    box: ViewBox,
    background: str | None = None,
) -> str:
    """Assemble fragments into one SVG document with the given viewBox."""
    body = "".join(children) if isinstance(children, list) else children
    rect = ""
    if background is not None:
        rect = (
            f'<rect x="{_fmt(box.x)}" y="{_fmt(box.y)}" width="{_fmt(box.width)}" '
            f'height="{_fmt(box.height)}" fill="{escape(background, quote=True)}"/>'
        )
    viewbox = f'viewBox="{_fmt(box.x)} {_fmt(box.y)} {_fmt(box.width)} {_fmt(box.height)}"'
    return (
        f'<svg xmlns="{SVG_NS}" width="{_fmt(box.width)}" height="{_fmt(box.height)}" '
        f"{viewbox}>{rect}{body}</svg>"
    )


def measure_text(text: str, font_size: float, avg_char_width: float = 0.62) -> float:
    """Estimate rendered text width for a sans-serif font (no font embedding).

    This is a layout heuristic used for arrow-label sizing; it is not a glyph
    metrics engine. Unicode sub/superscripts are counted as normal characters.
    """
    return max(0.0, len(text) * font_size * avg_char_width)


def scale_stroke_widths(svg: str, factor: float) -> str:
    """Multiply every ``stroke-width:Npx`` value by ``factor``."""
    if factor == 1.0:
        return svg

    def _repl(match: re.Match[str]) -> str:
        value = float(match.group(2)) * factor
        return f"{match.group(1)}{value:.3f}{match.group(3)}"

    return _STROKE_WIDTH_RE.sub(_repl, svg)


def apply_post(svg: str, post: dict) -> str:
    """Apply post-processing parameters (currently ``stroke_scale``)."""
    result = svg
    stroke_scale = post.get("stroke_scale")
    if stroke_scale is not None:
        result = scale_stroke_widths(result, float(stroke_scale))
    return result


def parse_hex_color(value: str) -> tuple[float, float, float]:
    """Convert ``#RRGGBB`` to a 0-1 RGB tuple."""
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6:
        raise ChemGlyphRenderError(f"Invalid hex color: {value!r}")
    try:
        return (
            int(cleaned[0:2], 16) / 255.0,
            int(cleaned[2:4], 16) / 255.0,
            int(cleaned[4:6], 16) / 255.0,
        )
    except ValueError as exc:
        raise ChemGlyphRenderError(f"Invalid hex color: {value!r}") from exc


def _fmt(value: float) -> str:
    """Format a coordinate with a trimmed trailing zero."""
    return f"{value:.3f}".rstrip("0").rstrip(".")
