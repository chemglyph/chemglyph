"""Reaction layout engine (see §6 of the specification).

Each molecule is rendered separately and assembled by this module: the layout
is fully ours (RDKit's ``ReactionToImage`` is not used), which is what allows
publication-style plus signs, condition labels, arrows, and line wrapping.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from html import escape
from typing import Any

from .errors import ChemGlyphReactionError
from .molecule import render_molecule
from .styles import StyleSpec, get_style
from .svg_utils import (
    ViewBox,
    compose_svg,
    inner_content,
    measure_text,
    require_viewbox,
    wrap_group,
)

_VALID_ARROWS = {"forward", "equilibrium", "retro"}

_GAP = 12.0
_ROW_GAP = 24.0
_MARGIN = 16.0
_PLUS_FONT = 28.0
_CONDITION_FONT = 14.0
_ARROW_BASE_LENGTH = 120.0
_ARROW_LABEL_PAD = 24.0
_ARROW_TEXT_OFFSET = 6.0
_ARROW_HALF_GAP = 5.0
_ARROW_HEAD = 10.0
_ARROW_COLOR = "#000000"


@dataclass
class _Step:
    reactants: list[str]
    products: list[str]
    above: str
    below: str
    yield_text: str
    arrow: str


@dataclass
class _Item:
    kind: str
    width: float
    height: float
    draw: Callable[[float, float, float], str]


def render_reaction(spec: dict[str, Any]) -> str:
    """Render a reaction scheme JSON spec (§6.1) to a single SVG string.

    Example::

        {
          "steps": [{
            "reactants": ["OC(=O)c1ccccc1O", "CC(=O)OC(C)=O"],
            "products": ["CC(=O)Oc1ccccc1C(=O)O"],
            "conditions": {"above": "H₂SO₄ (cat.)", "below": "rt, 15 min"},
            "yield": "89%",
            "arrow": "forward"
          }],
          "style": "modern",
          "layout": {"max_width": 1200, "align": "arrow"}
        }

    Conditions are pre-formatted Unicode text; this module never parses
    chemical formulas out of them.
    """
    style_name = spec.get("style", "modern")
    style_spec = get_style(style_name)
    layout = spec.get("layout") or {}
    max_width = float(layout.get("max_width", 1200))
    if max_width <= 0:
        raise ChemGlyphReactionError("layout.max_width must be positive")
    steps = _parse_steps(spec.get("steps"))
    fragments, canonical = _render_fragments(steps, style_name)
    rows = _build_rows(steps, fragments, canonical, style_spec, max_width)
    return _compose(rows)


def _parse_steps(raw_steps: Any) -> list[_Step]:
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ChemGlyphReactionError("spec.steps must be a non-empty list")
    steps: list[_Step] = []
    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            raise ChemGlyphReactionError(f"spec.steps[{index}] must be an object")
        reactants = raw.get("reactants")
        products = raw.get("products")
        if not isinstance(reactants, list) or not reactants:
            raise ChemGlyphReactionError(f"spec.steps[{index}].reactants must be a non-empty list")
        if not isinstance(products, list) or not products:
            raise ChemGlyphReactionError(f"spec.steps[{index}].products must be a non-empty list")
        conditions = raw.get("conditions") or {}
        if not isinstance(conditions, dict):
            raise ChemGlyphReactionError(f"spec.steps[{index}].conditions must be an object")
        arrow = raw.get("arrow", "forward")
        if arrow not in _VALID_ARROWS:
            raise ChemGlyphReactionError(
                f"spec.steps[{index}].arrow must be one of {sorted(_VALID_ARROWS)}"
            )
        steps.append(
            _Step(
                reactants=[str(item) for item in reactants],
                products=[str(item) for item in products],
                above=str(conditions.get("above", "")),
                below=str(conditions.get("below", "")),
                yield_text=str(raw.get("yield", "")),
                arrow=arrow,
            )
        )
    return steps


def _render_fragments(
    steps: list[_Step], style: str
) -> tuple[dict[str, tuple[str, ViewBox]], dict[str, str]]:
    """Render unique structures once and map every input string to canonicals."""
    fragments: dict[str, tuple[str, ViewBox]] = {}
    canonical: dict[str, str] = {}
    for step in steps:
        for structure in [*step.reactants, *step.products]:
            if structure in canonical:
                continue
            result = render_molecule(structure, style=style)
            canonical[structure] = result.canonical_smiles
            if result.canonical_smiles not in fragments:
                fragments[result.canonical_smiles] = (
                    result.data,
                    require_viewbox(result.data),
                )
    return fragments, canonical


def _build_rows(
    steps: list[_Step],
    fragments: dict[str, tuple[str, ViewBox]],
    canonical: dict[str, str],
    style_spec: StyleSpec,
    max_width: float,
) -> list[list[_Item]]:
    rows: list[list[_Item]] = []
    current: list[_Item] = []
    current_width = 0.0

    for index, step in enumerate(steps):
        continuation = index > 0 and _is_continuation(
            steps[index - 1].products, step.reactants, canonical
        )
        mode = (
            "wrapped"
            if continuation and not current
            else ("continuation" if continuation else "normal")
        )
        items = _step_items(step, fragments, canonical, style_spec, mode=mode)
        step_width = sum(item.width for item in items) + _GAP * (len(items) - 1)

        if current and current_width + step_width > max_width:
            rows.append(current)
            current = []
            current_width = 0.0
            # Wrap: no arrow at row end; the next row opens with the step's
            # arrow and the intermediate is redrawn (MVP per §6.2.4).
            mode = "wrapped" if continuation else "normal"
            items = _step_items(step, fragments, canonical, style_spec, mode=mode)
            step_width = sum(item.width for item in items) + _GAP * (len(items) - 1)

        if current:
            current_width += _GAP
        current.extend(items)
        current_width += step_width
    if current:
        rows.append(current)
    return rows


def _is_continuation(
    previous_products: list[str],
    next_reactants: list[str],
    canonical: dict[str, str],
) -> bool:
    return sorted(canonical[item] for item in previous_products) == sorted(
        canonical[item] for item in next_reactants
    )


def _step_items(
    step: _Step,
    fragments: dict[str, tuple[str, ViewBox]],
    canonical: dict[str, str],
    style_spec: StyleSpec,
    *,
    mode: str,
) -> list[_Item]:
    """Build the items for one step.

    ``normal`` steps are ``reactants + arrow products``. ``continuation``
    steps skip the reactant side (already drawn as the previous products).
    ``wrapped`` rows lead with the arrow and redraw the intermediates.
    """
    items: list[_Item] = []
    if mode == "wrapped":
        items.append(_arrow_item(step, style_spec))
    if mode in {"normal", "wrapped"}:
        items.extend(_fragment_items(step.reactants, fragments, canonical))
    if mode in {"normal", "continuation"}:
        items.append(_arrow_item(step, style_spec))
    items.extend(_fragment_items(step.products, fragments, canonical))
    return items


def _fragment_items(
    structures: list[str],
    fragments: dict[str, tuple[str, ViewBox]],
    canonical: dict[str, str],
) -> list[_Item]:
    items: list[_Item] = []
    for index, structure in enumerate(structures):
        if index:
            items.append(_plus_item())
        svg, box = fragments[canonical[structure]]
        content = inner_content(svg)

        def draw(x: float, center_y: float, _top: float, content=content, box=box) -> str:
            dy = center_y - box.center_y
            return wrap_group(content, x, dy, class_name="chemglyph-fragment")

        items.append(
            _Item(
                kind="fragment",
                width=box.width,
                height=box.height,
                draw=draw,
            )
        )
    return items


def _plus_item() -> _Item:
    return _Item(
        kind="plus",
        width=_PLUS_FONT,
        height=_PLUS_FONT,
        draw=lambda x, center_y, _top: (
            f'<text class="chemglyph-plus" x="{_fmt(x + _PLUS_FONT / 2)}" '
            f'y="{_fmt(center_y + _PLUS_FONT * 0.36)}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="{_PLUS_FONT}" '
            f'fill="{_ARROW_COLOR}">+</text>'
        ),
    )


def _arrow_item(step: _Step, style_spec: StyleSpec) -> _Item:
    above = step.above
    below_text = step.below
    yield_text = step.yield_text
    longest_label = max(
        measure_text(above, _CONDITION_FONT) if above else 0.0,
        measure_text(below_text, _CONDITION_FONT) if below_text else 0.0,
        measure_text(yield_text, _CONDITION_FONT) if yield_text else 0.0,
    )
    length = max(_ARROW_BASE_LENGTH, longest_label + _ARROW_LABEL_PAD)
    bond_width = float(style_spec.draw_options.get("bondLineWidth", 2.0))
    height = (
        (_CONDITION_FONT + _ARROW_TEXT_OFFSET if above else 0.0)
        + _CONDITION_FONT
        + (_ARROW_TEXT_OFFSET + _CONDITION_FONT if below_text or yield_text else 0.0)
    )

    def draw(x: float, center_y: float, top: float) -> str:
        parts = [_draw_arrow(step.arrow, x, center_y, length, bond_width)]
        if above:
            parts.append(
                _label(
                    above,
                    "chemglyph-condition",
                    x + length / 2,
                    center_y - _ARROW_TEXT_OFFSET,
                )
            )
        if below_text or yield_text:
            below_line = below_text
            if yield_text:
                below_line = f"{below_line} ({yield_text})" if below_line else f"({yield_text})"
            parts.append(
                _label(
                    below_line,
                    "chemglyph-condition",
                    x + length / 2,
                    center_y + _ARROW_TEXT_OFFSET + _CONDITION_FONT,
                )
            )
        del top
        return "".join(parts)

    return _Item(kind="arrow", width=length, height=height, draw=draw)


def _draw_arrow(kind: str, x: float, y: float, length: float, width: float) -> str:
    stroke = f'stroke="{_ARROW_COLOR}" stroke-width="{_fmt(width)}"'
    class_name = f"chemglyph-arrow chemglyph-arrow-{kind}"
    if kind == "forward":
        line = _line(x, y, x + length, y, class_name, stroke)
        head = _arrowhead(x + length, y, pointing_right=True, stroke=stroke)
        return line + head
    if kind == "retro":
        top = _line(x, y - _ARROW_HALF_GAP, x + length, y - _ARROW_HALF_GAP, class_name, stroke)
        bottom = _line(x, y + _ARROW_HALF_GAP, x + length, y + _ARROW_HALF_GAP, class_name, stroke)
        return (
            top
            + bottom
            + _arrowhead(x, y - _ARROW_HALF_GAP, pointing_right=False, stroke=stroke)
            + _arrowhead(x, y + _ARROW_HALF_GAP, pointing_right=False, stroke=stroke)
        )
    # equilibrium: two half arrows meeting in the middle.
    middle = x + length / 2
    top = _line(x, y - _ARROW_HALF_GAP, middle, y - _ARROW_HALF_GAP, class_name, stroke)
    bottom = _line(x + length, y + _ARROW_HALF_GAP, middle, y + _ARROW_HALF_GAP, class_name, stroke)
    return (
        top
        + bottom
        + _arrowhead(middle, y - _ARROW_HALF_GAP, pointing_right=True, stroke=stroke)
        + _arrowhead(middle, y + _ARROW_HALF_GAP, pointing_right=False, stroke=stroke)
    )


def _line(x1: float, y1: float, x2: float, y2: float, class_name: str, stroke: str) -> str:
    return (
        f'<line class="{class_name}" '
        f'x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" y2="{_fmt(y2)}" {stroke}/>'
    )


def _arrowhead(x: float, y: float, *, pointing_right: bool, stroke: str) -> str:
    direction = 1.0 if pointing_right else -1.0
    tip_x = x + direction * (_ARROW_HEAD / 2)
    back_x = x - direction * (_ARROW_HEAD / 2)
    points = (
        f"{_fmt(tip_x)},{_fmt(y)} "
        f"{_fmt(back_x)},{_fmt(y - _ARROW_HEAD / 2)} "
        f"{_fmt(back_x)},{_fmt(y + _ARROW_HEAD / 2)}"
    )
    return (
        f'<polygon class="chemglyph-arrowhead" points="{points}" '
        f'fill="{_ARROW_COLOR}" {stroke} stroke-linejoin="round"/>'
    )


def _label(text: str, class_name: str, x: float, y: float) -> str:
    return (
        f'<text class="{class_name}" x="{_fmt(x)}" y="{_fmt(y)}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="{_CONDITION_FONT}" '
        f'fill="{_ARROW_COLOR}">{escape(text)}</text>'
    )


def _compose(rows: list[list[_Item]]) -> str:
    row_heights = [max((item.height for item in row), default=0.0) for row in rows]
    row_widths = [sum(item.width for item in row) + _GAP * max(len(row) - 1, 0) for row in rows]
    total_width = max(row_widths, default=0.0)
    total_height = sum(row_heights) + _ROW_GAP * max(len(rows) - 1, 0)

    parts: list[str] = []
    y_cursor = 0.0
    for row, row_height in zip(rows, row_heights, strict=True):
        center_y = y_cursor + row_height / 2
        x_cursor = 0.0
        for item in row:
            parts.append(item.draw(x_cursor, center_y, y_cursor))
            x_cursor += item.width + _GAP
        y_cursor += row_height + _ROW_GAP

    box = ViewBox(0.0, 0.0, total_width + 2 * _MARGIN, total_height + 2 * _MARGIN)
    shifted = wrap_group("".join(parts), _MARGIN, _MARGIN)
    return compose_svg(shifted, box)


def _fmt(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")
