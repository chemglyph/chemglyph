"""Vector PDF from a fixed-scale SVG, with no extra dependency.

Fixed-scale figures are sized in points, which is also the PDF unit, and
contain only straight lines, quadratic and cubic curves, ellipses, and
rectangles, filled or stroked in solid colours. That subset maps one to one
onto PDF path operators, so the PDF is an exact copy of the SVG geometry.

The structure travels with the file: SMILES, InChI, InChIKey, formula, and
the molfile are stored in the document information dictionary and read back
by :func:`chemglyph.read_structure`.
"""

from __future__ import annotations

import math
import re
import zlib
from xml.etree import ElementTree as ET

from .errors import ChemGlyphRenderError

_TOKEN = re.compile(r"[MLQCZ]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")
_KAPPA = 4 * (math.sqrt(2) - 1) / 3  # cubic Bezier approximation of a quarter circle
_LINECAP = {"butt": 0, "round": 1, "square": 2}
_LINEJOIN = {"miter": 0, "round": 1, "bevel": 2}


def svg_to_pdf(svg: str, info: dict[str, str] | None = None) -> bytes:
    """Convert a ChemGlyph fixed-scale SVG to a one-page vector PDF."""
    root = ET.fromstring(svg)
    width_pt, height_pt = _size_pt(root, "width"), _size_pt(root, "height")
    vb_x, vb_y, vb_w, vb_h = (float(v) for v in root.attrib["viewBox"].split())
    scale = width_pt / vb_w

    def point(x: float, y: float) -> str:
        return f"{_num((x - vb_x) * scale)} {_num(height_pt - (y - vb_y) * scale)}"

    operators: list[str] = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in {"path", "ellipse", "rect"}:
            continue
        style = _style(element)
        fill = style.get("fill", "black" if tag != "path" else "none")
        stroke = style.get("stroke", "none")
        if fill == "none" and stroke == "none":
            continue
        geometry = _geometry(tag, element, point)
        if not geometry:
            continue
        ops = ["q"]
        if stroke != "none":
            ops.append(f"{_rgb(stroke)} RG")
            width = float(style.get("stroke-width", "1").removesuffix("px")) * scale
            ops.append(f"{_num(width)} w")
            ops.append(f"{_LINECAP.get(style.get('stroke-linecap', 'butt'), 0)} J")
            ops.append(f"{_LINEJOIN.get(style.get('stroke-linejoin', 'miter'), 0)} j")
        if fill != "none":
            ops.append(f"{_rgb(fill)} rg")
        ops.extend(geometry)
        even_odd = style.get("fill-rule") == "evenodd"
        if fill != "none" and stroke != "none":
            ops.append("B*" if even_odd else "B")
        elif fill != "none":
            ops.append("f*" if even_odd else "f")
        else:
            ops.append("S")
        ops.append("Q")
        operators.append("\n".join(ops))

    content = zlib.compress("\n".join(operators).encode("ascii"), 9)
    return _assemble(width_pt, height_pt, content, info or {})


def read_info(pdf: bytes) -> dict[str, str]:
    """Read the string entries of a PDF document information dictionary."""
    found: dict[str, str] = {}
    for match in re.finditer(rb"/(ChemGlyph\w+) \(", pdf):
        key = match.group(1).decode("ascii")
        found[key] = _read_literal(pdf, match.end())
    return found


def _size_pt(root: ET.Element, attribute: str) -> float:
    value = root.attrib.get(attribute, "")
    if not value.endswith("pt"):
        raise ChemGlyphRenderError("PDF output needs a fixed-scale SVG sized in points")
    return float(value[:-2])


def _style(element: ET.Element) -> dict[str, str]:
    style = {
        key: element.attrib[key]
        for key in (
            "fill",
            "stroke",
            "stroke-width",
            "stroke-linecap",
            "stroke-linejoin",
            "fill-rule",
        )
        if key in element.attrib
    }
    for item in element.attrib.get("style", "").split(";"):
        if ":" in item:
            key, value = item.split(":", 1)
            style[key.strip()] = value.strip()
    return style


def _geometry(tag: str, element: ET.Element, point) -> list[str]:
    if tag == "rect":
        x, y = float(element.attrib.get("x", 0)), float(element.attrib.get("y", 0))
        w, h = float(element.attrib["width"]), float(element.attrib["height"])
        return [
            f"{point(x, y)} m",
            f"{point(x + w, y)} l",
            f"{point(x + w, y + h)} l",
            f"{point(x, y + h)} l",
            "h",
        ]
    if tag == "ellipse":
        cx, cy = float(element.attrib["cx"]), float(element.attrib["cy"])
        rx, ry = float(element.attrib["rx"]), float(element.attrib["ry"])
        kx, ky = rx * _KAPPA, ry * _KAPPA
        return [
            f"{point(cx + rx, cy)} m",
            f"{point(cx + rx, cy + ky)} {point(cx + kx, cy + ry)} {point(cx, cy + ry)} c",
            f"{point(cx - kx, cy + ry)} {point(cx - rx, cy + ky)} {point(cx - rx, cy)} c",
            f"{point(cx - rx, cy - ky)} {point(cx - kx, cy - ry)} {point(cx, cy - ry)} c",
            f"{point(cx + kx, cy - ry)} {point(cx + rx, cy - ky)} {point(cx + rx, cy)} c",
            "h",
        ]
    return _path(element.attrib.get("d", ""), point)


def _path(d: str, point) -> list[str]:
    tokens = _TOKEN.findall(d)
    ops: list[str] = []
    index = 0
    command = "M"
    current = (0.0, 0.0)

    def take(count: int) -> list[float]:
        nonlocal index
        values = [float(v) for v in tokens[index : index + count]]
        index += count
        return values

    while index < len(tokens):
        token = tokens[index]
        if token in "MLQCZ":
            command = token
            index += 1
            if command == "Z":
                ops.append("h")
            continue
        if command == "M":
            x, y = take(2)
            ops.append(f"{point(x, y)} m")
            current = (x, y)
            command = "L"
        elif command == "L":
            x, y = take(2)
            ops.append(f"{point(x, y)} l")
            current = (x, y)
        elif command == "Q":
            # PDF has no quadratic curve; raise it to the equivalent cubic.
            qx, qy, x, y = take(4)
            c1 = (current[0] + 2 / 3 * (qx - current[0]), current[1] + 2 / 3 * (qy - current[1]))
            c2 = (x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y))
            ops.append(f"{point(*c1)} {point(*c2)} {point(x, y)} c")
            current = (x, y)
        elif command == "C":
            x1, y1, x2, y2, x, y = take(6)
            ops.append(f"{point(x1, y1)} {point(x2, y2)} {point(x, y)} c")
            current = (x, y)
        else:  # pragma: no cover - only the commands above occur
            index += 1
    return ops


def _rgb(colour: str) -> str:
    named = {"black": "#000000", "white": "#ffffff"}
    value = named.get(colour.lower(), colour).lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    r, g, b = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return f"{_num(r)} {_num(g)} {_num(b)}"


def _num(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _literal(text: str) -> bytes:
    escaped = (
        text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\n", "\\n")
    )
    return b"(" + escaped.encode("latin-1", "replace") + b")"


def _read_literal(pdf: bytes, start: int) -> str:
    out = bytearray()
    index = start
    escapes = {ord("n"): b"\n", ord("r"): b"\r", ord("t"): b"\t"}
    while index < len(pdf):
        byte = pdf[index]
        if byte == ord("\\"):
            following = pdf[index + 1]
            out += escapes.get(following, bytes([following]))
            index += 2
            continue
        if byte == ord(")"):
            break
        out.append(byte)
        index += 1
    return out.decode("latin-1")


def _assemble(width: float, height: float, content: bytes, info: dict[str, str]) -> bytes:
    info_entries = b" ".join(
        b"/" + key.encode("ascii") + b" " + _literal(value) for key, value in info.items()
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_num(width)} {_num(height)}] "
            "/Contents 4 0 R /Resources << >> >>"
        ).encode("ascii"),
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" /Filter /FlateDecode >>\nstream\n"
        + content
        + b"\nendstream",
        b"<< /Producer (ChemGlyph) " + info_entries + b" >>",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 5 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)
