"""SVG assembly, measurement, and viewBox math (standard library only).

ChemGlyph deliberately avoids an SVG library dependency; RDKit output is
predictable enough for these small, well-tested helpers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from xml.etree import ElementTree as ET

from .errors import ChemGlyphRenderError

SVG_NS = "http://www.w3.org/2000/svg"

_VIEWBOX_RE = re.compile(
    r"""<svg\b[^>]*?\bviewBox\s*=\s*["']\s*"""
    r"""([-+0-9.eE]+)[,\s]+([-+0-9.eE]+)[,\s]+([-+0-9.eE]+)[,\s]+([-+0-9.eE]+)\s*["']"""
)
_STROKE_WIDTH_RE = re.compile(r"(stroke-width:)([0-9.]+)(px)")
_NUMBER_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


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


def content_viewbox(svg: str, *, margin: float = 0.0) -> ViewBox:
    """Smallest axis-aligned bounding box of the drawn geometry.

    Parses the element tree (namespace-agnostic) and collects every geometric
    anchor: path control points, circles, ellipses, rects, lines, polygons,
    and text anchors. Transforms are ignored — ChemGlyph only uses translate
    wrappers, which this caller accounts for itself. Text extents are
    approximated by their anchor point, so callers should keep a margin.

    Falls back to the document viewBox when no geometry is found; raises
    :class:`ChemGlyphRenderError` when there is no geometry and no viewBox.
    """
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise ChemGlyphRenderError(f"SVG content is not well-formed XML: {exc}") from exc
    xs: list[float] = []
    ys: list[float] = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "path":
            numbers = [float(value) for value in _NUMBER_RE.findall(element.attrib.get("d", ""))]
            xs.extend(numbers[0::2])
            ys.extend(numbers[1::2])
        elif tag == "circle":
            cx = float(element.attrib.get("cx", 0.0))
            cy = float(element.attrib.get("cy", 0.0))
            radius = float(element.attrib.get("r", 0.0))
            xs.extend((cx - radius, cx + radius))
            ys.extend((cy - radius, cy + radius))
        elif tag == "ellipse":
            cx = float(element.attrib.get("cx", 0.0))
            cy = float(element.attrib.get("cy", 0.0))
            rx = float(element.attrib.get("rx", 0.0))
            ry = float(element.attrib.get("ry", 0.0))
            xs.extend((cx - rx, cx + rx))
            ys.extend((cy - ry, cy + ry))
        elif tag == "rect":
            x = float(element.attrib.get("x", 0.0))
            y = float(element.attrib.get("y", 0.0))
            width = float(element.attrib.get("width", 0.0))
            height = float(element.attrib.get("height", 0.0))
            xs.extend((x, x + width))
            ys.extend((y, y + height))
        elif tag == "line":
            xs.extend((float(element.attrib.get("x1", 0.0)), float(element.attrib.get("x2", 0.0))))
            ys.extend((float(element.attrib.get("y1", 0.0)), float(element.attrib.get("y2", 0.0))))
        elif tag in {"polygon", "polyline"}:
            numbers = [
                float(value) for value in _NUMBER_RE.findall(element.attrib.get("points", ""))
            ]
            xs.extend(numbers[0::2])
            ys.extend(numbers[1::2])
        elif tag == "text":
            xs.append(float(element.attrib.get("x", 0.0)))
            ys.append(float(element.attrib.get("y", 0.0)))
    if not xs or not ys:
        fallback = extract_viewbox(svg)
        if fallback is None:
            raise ChemGlyphRenderError("SVG has no drawn geometry and no viewBox")
        return ViewBox(fallback.x, fallback.y, fallback.width, fallback.height)
    box = ViewBox(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    document = extract_viewbox(svg)
    if document is not None:
        box = ViewBox(
            x=max(box.x, document.x),
            y=max(box.y, document.y),
            width=min(box.x + box.width, document.x + document.width) - max(box.x, document.x),
            height=min(box.y + box.height, document.y + document.height) - max(box.y, document.y),
        )
    if margin:
        box = ViewBox(
            x=box.x - margin,
            y=box.y - margin,
            width=box.width + 2.0 * margin,
            height=box.height + 2.0 * margin,
        )
    return box


def inner_content(svg: str) -> str:
    """Return everything between the root ``<svg ...>`` tag and ``</svg>``.

    Any XML declaration before the root element is dropped along with the
    root tag, so the result is safe to nest inside another SVG document.
    """
    svg_start = svg.find("<svg")
    start = svg.find(">", svg_start)
    end = svg.rfind("</svg>")
    if svg_start == -1 or start == -1 or end == -1 or end <= start:
        raise ChemGlyphRenderError("SVG fragment is missing the root <svg> element")
    return svg[start + 1 : end]


def wrap_group(
    content: str,
    dx: float = 0.0,
    dy: float = 0.0,
    class_name: str | None = None,
) -> str:
    """Wrap SVG content in a ``<g>`` with a translate transform."""
    class_attr = f' class="{class_name}"' if class_name else ""
    return f'<g{class_attr} transform="translate({_fmt(dx)},{_fmt(dy)})">{content}</g>'


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
