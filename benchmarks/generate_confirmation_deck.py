"""Build the small-scale confirmation deck (3 graders x 12 pairs).

Design (maintainer-approved):

- opponent panel is the Indigo publication-convention reference, not stock
  RDKit;
- acs and modern are asked separately: acs pairs use "which would you rather
  put in a paper", modern pairs use "which is clearer and more professional
  on screen/web";
- 6 acs pairs + 6 modern pairs per grader, drawn without replacement from
  the blind-test list, excluding the known limitations (ferrocene,
  porphyrin) and paclitaxel (RDKit layout limitation);
- every grader sees the same 12 pairs; the HTML page embeds the question and
  collects votes without revealing molecule names, engines, or sides.

Outputs under ``benchmarks/blind_review/`` (gitignored): ``deck/``,
``review.html``, ``pair_key.json``, ``instructions.md``, ``record_sheet.csv``
and ``deck.zip``. Graders must never receive ``pair_key.json`` or repository
access.

Usage::

    python benchmarks/generate_confirmation_deck.py --seed N
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))


from blind_test_molecules import BLIND_TEST_MOLECULES, KNOWN_LIMITATIONS  # noqa: E402
from generate_review_deck import _data_url, _page  # noqa: E402
from reference_panels import _chemglyph_panel, _indigo, _indigo_panel  # noqa: E402

ACS_QUESTION = "哪张你更愿意放进论文?"
MODERN_QUESTION = "哪张在屏幕或网页上更清晰、更专业?"

# paclitaxel is excluded here because RDKit has no clean 2D layout for its
# gem-dimethyl placement (documented in REVIEW-1); it would judge the layout
# engine rather than the style.
EXCLUDED = KNOWN_LIMITATIONS | {"paclitaxel"}


def _build_html(pairs: list[dict], run_id: str) -> str:
    template = (_REPO_ROOT / "benchmarks" / "confirmation_template.html").read_text(
        encoding="utf-8"
    )
    return template.replace("__DATA_JSON__", json.dumps(pairs, ensure_ascii=False)).replace(
        "__RUN_ID__", run_id
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the confirmation review deck")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    if args.seed is None:
        args.seed = random.SystemRandom().randrange(1, 10**9)
    rng = random.Random(args.seed)

    out_dir = _REPO_ROOT / "benchmarks" / "blind_review"
    deck_dir = out_dir / "deck"
    deck_dir.mkdir(parents=True, exist_ok=True)
    for stale in deck_dir.glob("*.png"):
        stale.unlink()  # deck/ is a regenerated gitignored artifact

    eligible = [
        (label, smiles) for label, smiles, _note in BLIND_TEST_MOLECULES if label not in EXCLUDED
    ]
    rng.shuffle(eligible)
    selected = eligible[:12]
    assignments = [("acs", label, smiles) for label, smiles in selected[:6]] + [
        ("modern", label, smiles) for label, smiles in selected[6:]
    ]
    rng.shuffle(assignments)

    indigo, renderer = _indigo()
    pair_key: dict[str, dict] = {}
    html_pairs: list[dict] = []
    record_rows: list[str] = ["pair_id,pick,note"]
    for pair_number, (style, label, smiles) in enumerate(assignments, start=1):
        chemglyph_panel, _ = _chemglyph_panel(smiles, style)
        indigo_panel, _ = _indigo_panel(indigo, renderer, smiles)
        swap = rng.random() < 0.5
        image_a = indigo_panel if swap else chemglyph_panel
        image_b = chemglyph_panel if swap else indigo_panel
        page = _page(pair_number, image_a, image_b, scored=True)
        page.save(deck_dir / f"pair_{pair_number:03d}.png")
        key = f"pair_{pair_number:03d}"
        pair_key[key] = {
            "molecule": label,
            "style": style,
            "question": ACS_QUESTION if style == "acs" else MODERN_QUESTION,
            "a_engine": "indigo" if swap else "chemglyph",
            "b_engine": "chemglyph" if swap else "indigo",
        }
        html_pairs.append(
            {
                "id": key,
                "question": pair_key[key]["question"],
                "scored": True,
                "a": _data_url(image_a),
                "b": _data_url(image_b),
            }
        )
        record_rows.append(f"{key},,")

    pair_key["seed"] = args.seed
    run_id = hashlib.sha256(
        json.dumps(pair_key, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12]
    pair_key["run_id"] = run_id
    (out_dir / "pair_key.json").write_text(json.dumps(pair_key, indent=2) + "\n")
    (out_dir / "review.html").write_text(_build_html(html_pairs, run_id))
    (out_dir / "record_sheet.csv").write_text("\n".join(record_rows) + "\n")

    instructions = f"""# 化学结构图确认评审说明

感谢参与。本次共 12 组图,每组两张(A 和 B),画的是同一个分子。
每组上方会写明判断标准,两种标准随机出现:

- "哪张你更愿意放进论文?" - 按期刊排版标准判断。
- "哪张在屏幕或网页上更清晰、更专业?" - 按屏幕显示标准判断。

规则:

- 凭第一印象作答,每组一分钟以内。
- 只看图的布局、清晰度和整体观感。
- 确实没差别选"两者差不多";两张都不理想选"都不理想"。
- 独立完成,提交前不要和其他评审人讨论。

两种方式任选:

1. 打开 review.html,按页面上的问题点选,结束后复制答案或下载 answers.json;
2. 打开 deck/ 里的图片,把答案填进 record_sheet.csv(pair_id + A/B/tie/neither)。

本次评审编号(run id)是:
{run_id}
"""
    (out_dir / "instructions.md").write_text(instructions)
    with zipfile.ZipFile(out_dir / "deck.zip", "w") as archive:
        archive.write(out_dir / "review.html", arcname="review.html")
        archive.write(out_dir / "instructions.md", arcname="instructions.md")
        archive.write(out_dir / "record_sheet.csv", arcname="record_sheet.csv")
        for page in sorted(deck_dir.glob("*.png")):
            archive.write(page, arcname=page.name)
    print(
        f"seed={args.seed} run_id={run_id}: wrote 12 pairs under {out_dir}"
        " (pair_key.json stays with the organizer)"
    )


if __name__ == "__main__":
    main()
