#!/usr/bin/env python3
"""Audit sprite-sheet motion, chroma residue, clipping, and near-duplicate frames."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageChops


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


def chroma_residue(image: Image.Image, key: tuple[int, int, int], threshold: float) -> int:
    total = 0
    for count, color in image.getcolors(maxcolors=1000000) or []:
        r, g, b, a = color
        if a > 0 and color_dist((r, g, b), key) <= threshold:
            total += count
    return total


def frame_diff(a: Image.Image, b: Image.Image) -> float:
    diff = ImageChops.difference(a.convert("RGBA"), b.convert("RGBA"))
    hist = diff.histogram()
    total = sum(value * (index % 256) for index, value in enumerate(hist))
    return total / (a.width * a.height * 4 * 255)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--cell", type=int, default=64)
    parser.add_argument("--key-color", type=parse_hex_color, default=parse_hex_color("#00ff00"))
    parser.add_argument("--chroma-threshold", type=float, default=72.0)
    parser.add_argument("--edge-margin", type=int, default=1)
    parser.add_argument("--edge-threshold", type=int, default=12)
    parser.add_argument("--min-frame-diff", type=float, default=0.012)
    parser.add_argument("--row-names", default="")
    parser.add_argument("--fail-on-warnings", action="store_true")
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()

    source = Path(args.input).expanduser().resolve()
    with Image.open(source) as opened:
        atlas = opened.convert("RGBA")

    expected = (args.columns * args.cell, args.rows * args.cell)
    errors: list[str] = []
    warnings: list[str] = []
    rows = []
    row_names = [name.strip() for name in args.row_names.split(",") if name.strip()]
    if atlas.size != expected:
        errors.append(f"atlas is {atlas.width}x{atlas.height}; expected {expected[0]}x{expected[1]}")

    for row in range(args.rows):
        row_name = row_names[row] if row < len(row_names) else str(row)
        frames = []
        row_cells = []
        for col in range(args.columns):
            box = (col * args.cell, row * args.cell, (col + 1) * args.cell, (row + 1) * args.cell)
            frame = atlas.crop(box)
            frames.append(frame)
            cell = {
                "row": row,
                "row_name": row_name,
                "column": col,
                "nontransparent_pixels": alpha_count(frame),
                "edge_pixels": edge_count(frame, args.edge_margin),
                "chroma_residue_pixels": chroma_residue(frame, args.key_color, args.chroma_threshold),
                "bbox": frame.getbbox(),
            }
            if cell["edge_pixels"] > args.edge_threshold:
                warnings.append(f"row {row_name} col {col}: sprite touches edge ({cell['edge_pixels']} pixels)")
            if cell["chroma_residue_pixels"] > 0:
                warnings.append(f"row {row_name} col {col}: chroma residue ({cell['chroma_residue_pixels']} pixels)")
            row_cells.append(cell)

        diffs = [frame_diff(frames[i - 1], frames[i]) for i in range(1, len(frames))]
        low_diffs = [round(value, 4) for value in diffs if value < args.min_frame_diff]
        if len(low_diffs) >= max(2, len(diffs) // 2):
            warnings.append(f"row {row_name}: weak motion / near-duplicate frames {low_diffs}")
        rows.append({"row": row, "row_name": row_name, "cells": row_cells, "frame_diffs": [round(value, 5) for value in diffs]})

    if args.fail_on_warnings and warnings:
        errors.extend(warnings)

    report = {
        "ok": not errors,
        "file": str(source),
        "width": atlas.width,
        "height": atlas.height,
        "errors": errors,
        "warnings": warnings,
        "rows": rows,
    }
    target = Path(args.json_out).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "errors": errors, "warnings": len(warnings)}, indent=2))


if __name__ == "__main__":
    main()
