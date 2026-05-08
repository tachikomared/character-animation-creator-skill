#!/usr/bin/env python3
"""Implementation for fixed-cell game-character sprite atlas validation."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


def parse_hex_color(value: str) -> tuple[int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) != 6:
        raise argparse.ArgumentTypeError("expected #RRGGBB")
    return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))


def color_dist(color: tuple[int, int, int], key: tuple[int, int, int]) -> float:
    return math.sqrt(sum((color[i] - key[i]) ** 2 for i in range(3)))


def alpha_count(image: Image.Image) -> int:
    return sum(image.getchannel("A").histogram()[1:])


def edge_count(image: Image.Image, margin: int) -> int:
    alpha = image.getchannel("A")
    w, h = alpha.size
    total = 0
    for box in (
        (0, 0, w, margin),
        (0, h - margin, w, h),
        (0, 0, margin, h),
        (w - margin, 0, w, h),
    ):
        total += sum(alpha.crop(box).histogram()[1:])
    return total


def chroma_count(image: Image.Image, key: tuple[int, int, int], threshold: float) -> int:
    total = 0
    for count, color in image.getcolors(maxcolors=1000000) or []:
        r, g, b, a = color
        if a > 0 and color_dist((r, g, b), key) <= threshold:
            total += count
    return total


def bbox_center(image: Image.Image) -> tuple[float, float] | None:
    bbox = image.getbbox()
    if bbox is None:
        return None
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def frame_diff(a: Image.Image, b: Image.Image) -> float:
    diff = ImageChops.difference(a.convert("RGBA"), b.convert("RGBA"))
    hist = diff.histogram()
    total = sum(value * (index % 256) for index, value in enumerate(hist))
    return total / (a.width * a.height * 4 * 255)


def make_contact(atlas: Image.Image, rows: int, columns: int, cell: int, output: Path) -> None:
    pad = 1
    label_h = 12
    sheet = Image.new("RGBA", (columns * (cell + pad) + pad, rows * (cell + label_h + pad) + pad), (255, 255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for row in range(rows):
        for col in range(columns):
            x = col * (cell + pad) + pad
            y = row * (cell + label_h + pad) + label_h + pad
            frame = atlas.crop((col * cell, row * cell, (col + 1) * cell, (row + 1) * cell))
            bg = Image.new("RGBA", (cell, cell), (230, 230, 230, 255))
            for by in range(0, cell, 8):
                for bx in range(0, cell, 8):
                    if (bx // 8 + by // 8) % 2:
                        ImageDraw.Draw(bg).rectangle((bx, by, bx + 7, by + 7), fill=(245, 245, 245, 255))
            bg.alpha_composite(frame)
            sheet.alpha_composite(bg, (x, y))
            draw.rectangle((x, y, x + cell, y + cell), outline=(0, 120, 60, 255))
            draw.text((x + 2, y - label_h), f"{row}:{col}", fill=(0, 0, 0, 255))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--cell", type=int, default=64)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--contact-sheet")
    parser.add_argument("--min-pixels", type=int, default=80)
    parser.add_argument("--edge-margin", type=int, default=1)
    parser.add_argument("--edge-threshold", type=int, default=12)
    parser.add_argument("--chroma-key", type=parse_hex_color)
    parser.add_argument("--chroma-threshold", type=float, default=72.0)
    parser.add_argument("--max-chroma-pixels", type=int, default=0)
    parser.add_argument("--min-frame-diff", type=float, default=0.012)
    parser.add_argument("--min-bbox-shift", type=float, default=0.0)
    parser.add_argument("--row-names", default="")
    parser.add_argument("--fail-on-warnings", action="store_true")
    args = parser.parse_args()

    source = Path(args.input).expanduser().resolve()
    with Image.open(source) as opened:
        atlas = opened.convert("RGBA")

    expected = (args.columns * args.cell, args.rows * args.cell)
    errors: list[str] = []
    warnings: list[str] = []
    cells = []
    rows = []
    row_names = [name.strip() for name in args.row_names.split(",") if name.strip()]

    if atlas.size != expected:
        errors.append(f"atlas is {atlas.width}x{atlas.height}; expected {expected[0]}x{expected[1]}")

    for row in range(args.rows):
        row_frames = []
        centers = []
        row_cells = []
        row_name = row_names[row] if row < len(row_names) else str(row)
        for col in range(args.columns):
            box = (col * args.cell, row * args.cell, (col + 1) * args.cell, (row + 1) * args.cell)
            frame = atlas.crop(box)
            row_frames.append(frame)
            centers.append(bbox_center(frame))
            nontransparent = alpha_count(frame)
            edge_pixels = edge_count(frame, args.edge_margin)
            chroma_pixels = chroma_count(frame, args.chroma_key, args.chroma_threshold) if args.chroma_key else 0
            if nontransparent < args.min_pixels:
                warnings.append(f"cell {row_name}:{col} is sparse or empty ({nontransparent} pixels)")
            if edge_pixels > args.edge_threshold:
                warnings.append(f"cell {row_name}:{col} has {edge_pixels} edge pixels")
            if chroma_pixels > args.max_chroma_pixels:
                warnings.append(f"cell {row_name}:{col} has {chroma_pixels} chroma residue pixels")
            cell = {
                "row": row,
                "row_name": row_name,
                "column": col,
                "nontransparent_pixels": nontransparent,
                "edge_pixels": edge_pixels,
                "chroma_residue_pixels": chroma_pixels,
                "bbox": frame.getbbox(),
            }
            cells.append(cell)
            row_cells.append(cell)

        diffs = [frame_diff(row_frames[i - 1], row_frames[i]) for i in range(1, len(row_frames))]
        low_diffs = [round(value, 4) for value in diffs if value < args.min_frame_diff]
        valid_centers = [center for center in centers if center is not None]
        bbox_shift = 0.0
        if valid_centers:
            xs = [center[0] for center in valid_centers]
            ys = [center[1] for center in valid_centers]
            bbox_shift = max(max(xs) - min(xs), max(ys) - min(ys))
        if len(low_diffs) >= max(2, len(diffs) // 2):
            warnings.append(f"row {row_name} has weak motion / near-duplicate frames: {low_diffs}")
        if args.min_bbox_shift > 0 and bbox_shift < args.min_bbox_shift and args.columns > 1:
            warnings.append(f"row {row_name} has low bbox motion ({bbox_shift:.2f}px)")
        rows.append(
            {
                "row": row,
                "row_name": row_name,
                "frame_diffs": [round(value, 5) for value in diffs],
                "bbox_shift": round(bbox_shift, 3),
                "cells": row_cells,
            }
        )

    if args.fail_on_warnings and warnings:
        errors.extend(warnings)

    result = {
        "ok": not errors,
        "file": str(source),
        "width": atlas.width,
        "height": atlas.height,
        "errors": errors,
        "warnings": warnings,
        "cells": cells,
        "rows": rows,
    }
    out = Path(args.json_out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if args.contact_sheet:
        make_contact(atlas, args.rows, args.columns, args.cell, Path(args.contact_sheet).expanduser().resolve())
    print(json.dumps({"ok": not errors, "errors": errors, "warnings": len(warnings)}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
