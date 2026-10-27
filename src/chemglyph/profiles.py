"""Drawing profiles in physical units (docs/SPEC.md, section 5).

A profile fixes every size of a drawing in points, so all figures drawn with
the same profile share one scale: same bond length, same label size, same
line width, whatever the molecule. Each profile cites its source.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ChemGlyphStyleError

# IUPAC 2008 (GR-1.2): lines thinner than 0.5 pt should be avoided.
IUPAC_MIN_LINE_PT = 0.5


@dataclass(frozen=True)
class Profile:
    """Every size of a drawing, in points (1 pt = 1/72 inch)."""

    name: str
    bond_length_pt: float
    line_width_pt: float
    bold_width_pt: float
    bond_spacing: float  # double-bond line separation, fraction of bond length
    margin_width_pt: float  # clear gap between a label glyph and a bond end
    hash_spacing_pt: float  # distance between the lines of a hashed wedge
    font_size_pt: float
    canvas_margin_pt: float = 2.0  # white space around the drawing
    atom_colours: dict[int, str] = field(default_factory=dict)  # empty = black
    source: str = ""


ACS1996 = Profile(
    name="acs1996",
    bond_length_pt=14.4,
    line_width_pt=0.6,
    bold_width_pt=2.0,
    bond_spacing=0.18,
    margin_width_pt=1.6,
    hash_spacing_pt=2.5,
    font_size_pt=10.0,
    source=(
        "ACS Document 1996 settings: fixed length 14.4 pt, line width 0.6 pt, "
        "bold width 2.0 pt, bond spacing 18% of length, margin width 1.6 pt, "
        "hash spacing 2.5 pt, atom labels 10 pt Arial/Helvetica"
    ),
)

PROFILES: dict[str, Profile] = {ACS1996.name: ACS1996}


def get_profile(name: str) -> Profile:
    """Return the named profile."""
    try:
        return PROFILES[name]
    except KeyError:
        choices = ", ".join(sorted(PROFILES))
        raise ChemGlyphStyleError(f"Unknown profile {name!r}; choose one of: {choices}") from None
