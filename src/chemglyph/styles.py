"""Style presets for ChemGlyph rendering (see §4 of the specification)."""

from __future__ import annotations

from dataclasses import dataclass, field

STYLES = {"acs", "modern", "textbook-cn"}


@dataclass(frozen=True)
class StyleSpec:
    """A rendering style: RDKit draw options plus post-processing parameters."""

    name: str
    draw_options: dict = field(default_factory=dict)
    background: str | None = None
    post: dict = field(default_factory=dict)


def get_style(name: str) -> StyleSpec:
    """Return the :class:`StyleSpec` for a named style."""
    raise NotImplementedError("TODO(M1): implement style presets")
