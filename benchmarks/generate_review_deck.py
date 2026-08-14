"""Build the shuffled A/B review deck for the blind comparison.

Each page pairs one ChemGlyph figure with one stock-RDKit figure (same
molecule, same style family), sides assigned at random. No molecule names,
no engine names: the grader only sees a pair id and two candidates.

The deck is an interim opponent set (RDKit default output) for when
hand-made ChemDraw/Ketcher panels are not available yet. The official
procedure in RUNBOOK.md still applies once real panels exist.

Usage::

    python benchmarks/generate_review_deck.py [--seed N]
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import random
import sys
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from rdkit import Chem  # noqa: E402
from rdkit.Chem import rdDepictor  # noqa: E402
from rdkit.Chem.Draw import rdMolDraw2D  # noqa: E402

import chemglyph  # noqa: E402
from blind_test_molecules import BLIND_TEST_MOLECULES, KNOWN_LIMITATIONS  # noqa: E402

CELL = 420
PAD = 28
HEADER = 76
GAP = 24
BG = (255, 255, 255, 255)
INK = (24, 24, 24, 255)

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _png(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _chemglyph_panel(smiles: str, style: str) -> Image.Image:
    result = chemglyph.render_molecule(
        smiles, style=style, fmt="png", transparent=False, size=(CELL, CELL)
    )
    return _png(result.data)


def _rdkit_panel(smiles: str, *, monochrome: bool) -> Image.Image:
    mol = Chem.MolFromSmiles(smiles)
    rdDepictor.SetPreferCoordGen(True)
    rdDepictor.Compute2DCoords(mol)
    options = rdMolDraw2D.MolDrawOptions()
    if monochrome:
        options.useBWAtomPalette = True
    drawer = rdMolDraw2D.MolDraw2DCairo(CELL, CELL)
    drawer.SetDrawOptions(options)
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    return _png(bytes(drawer.GetDrawingText()))


def _page(pair_id: int, image_a: Image.Image, image_b: Image.Image, *, scored: bool) -> Image.Image:
    width = 2 * PAD + 2 * CELL + GAP
    height = HEADER + CELL + PAD
    page = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(page)
    title = f"Pair {pair_id}"
    if not scored:
        title += "  (not scored)"
    draw.text((width // 2, 24), title, font=_font(30), fill=INK, anchor="mm")
    for label, image, column in (("A", image_a, 0), ("B", image_b, 1)):
        x0 = PAD + column * (CELL + GAP)
        draw.text((x0 + CELL // 2, 52), label, font=_font(34), fill=INK, anchor="mm")
        page.paste(image, (x0, HEADER), image)
    return page


def _data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _build_html(pairs: list[dict]) -> str:
    """Single-file Chinese voting page; embeds only images and pair ids.

    Deliberately contains no molecule names, no engine names, and no key
    material, so graders cannot break the blinding from the page alone.
    """
    template = (_REPO_ROOT / "benchmarks" / "review_template.html").read_text(encoding="utf-8")
    return template.replace("__DATA_JSON__", json.dumps(pairs, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the blind review deck")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    out_dir = _REPO_ROOT / "benchmarks" / "blind_review"
    deck_dir = out_dir / "deck"
    deck_dir.mkdir(parents=True, exist_ok=True)

    pairs: list[dict] = []
    pair_key: dict[str, dict] = {}
    html_pairs: list[dict] = []
    for index, (label, smiles, _note) in enumerate(BLIND_TEST_MOLECULES):
        for style in ("acs", "modern"):
            pair_number = index * 2 + (0 if style == "acs" else 1) + 1
            chemglyph_panel = _chemglyph_panel(smiles, style)
            rdkit_panel = _rdkit_panel(smiles, monochrome=(style == "acs"))
            swap = rng.random() < 0.5
            image_a = rdkit_panel if swap else chemglyph_panel
            image_b = chemglyph_panel if swap else rdkit_panel
            scored = label not in KNOWN_LIMITATIONS
            page = _page(pair_number, image_a, image_b, scored=scored)
            page.save(deck_dir / f"pair_{pair_number:03d}.png")
            key = f"pair_{pair_number:03d}"
            pair_key[key] = {
                "molecule": label,
                "style": style,
                "a_engine": "rdkit" if swap else "chemglyph",
                "b_engine": "chemglyph" if swap else "rdkit",
                "scored": scored,
            }
            pairs.append(key)
            html_pairs.append(
                {
                    "id": key,
                    "scored": scored,
                    "a": _data_url(image_a),
                    "b": _data_url(image_b),
                }
            )
    (out_dir / "pair_key.json").write_text(json.dumps(pair_key, indent=2) + "\n")
    (out_dir / "review.html").write_text(_build_html(html_pairs))

    instructions = """# 化学结构图评审说明

感谢参与。你将看到 40 组化学结构图,每组两张(A 和 B),画的是同一个分子。
每组选一张你更愿意放进论文的图;没有明显偏好就选平局。

规则:

- 凭第一印象,每组一分钟以内。
- 只看布局、清晰度和整体观感。
- 标着"不计分"的组可以不答,答了也不计分。
- 独立完成,提交前不要和其他评审人讨论。

两种方式任选:

1. 打开 review.html,直接在页面里点选,结束后复制答案或下载 answers.json;
2. 打开 deck/ 里的图片,按 pair_001 A、pair_002 tie 这样的格式把答案列出来。

把答案发给组织者即可。
"""
    (out_dir / "instructions.md").write_text(instructions)
    with zipfile.ZipFile(out_dir / "deck.zip", "w") as archive:
        archive.write(out_dir / "review.html", arcname="review.html")
        archive.write(out_dir / "instructions.md", arcname="instructions.md")
        for page in sorted(deck_dir.glob("*.png")):
            archive.write(page, arcname=page.name)
    print(f"Wrote {len(pairs)} pages, review.html, pair_key.json, and deck.zip under {out_dir}")


if __name__ == "__main__":
    main()
