#!/usr/bin/env python3
"""Validate 32/64/128 sprite hierarchy by comparing thumbnail primary structure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def alpha_mask(image: Image.Image) -> list[int]:
    return [1 if value > 0 else 0 for value in image.getchannel("A").tobytes()]


def mask_iou(a: list[int], b: list[int]) -> float:
    intersection = 0
    union = 0
    for left, right in zip(a, b):
        if left or right:
            union += 1
            if left and right:
                intersection += 1
    if union == 0:
        return 1.0
    return intersection / union


def dominant_color_blocks(image: Image.Image, palette_size: int) -> Image.Image:
    rgba = image.convert("RGBA")
    palette = rgba.convert("P", palette=Image.Palette.ADAPTIVE, colors=palette_size)
    return palette.convert("RGBA")


def color_delta(a: Image.Image, b: Image.Image) -> float:
    a_data = list(a.convert("RGBA").getdata())
    b_data = list(b.convert("RGBA").getdata())
    total = 0.0
    count = 0
    for left, right in zip(a_data, b_data):
        if left[3] == 0 and right[3] == 0:
            continue
        total += sum(abs(left[i] - right[i]) for i in range(3)) / (255 * 3)
        count += 1
    if count == 0:
        return 0.0
    return total / count


def frame(atlas: Image.Image, cell: int, row: int, col: int) -> Image.Image:
    return atlas.crop((col * cell, row * cell, (col + 1) * cell, (row + 1) * cell)).convert("RGBA")


def thumbnail_to_32(image: Image.Image, cell: int) -> Image.Image:
    if cell == 32:
        return image.convert("RGBA")
    return image.convert("RGBA").resize((32, 32), Image.Resampling.NEAREST)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base32", required=True)
    parser.add_argument("--sheet64")
    parser.add_argument("--sheet128")
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--min-iou", type=float, default=0.74)
    parser.add_argument("--max-color-delta", type=float, default=0.32)
    parser.add_argument("--palette-size", type=int, default=24)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--fail-on-warnings", action="store_true")
    args = parser.parse_args()

    with Image.open(Path(args.base32).expanduser().resolve()) as opened:
        base32 = opened.convert("RGBA")
    comparisons: list[tuple[int, Image.Image]] = []
    if args.sheet64:
        with Image.open(Path(args.sheet64).expanduser().resolve()) as opened:
            comparisons.append((64, opened.convert("RGBA")))
    if args.sheet128:
        with Image.open(Path(args.sheet128).expanduser().resolve()) as opened:
            comparisons.append((128, opened.convert("RGBA")))

    errors: list[str] = []
    warnings: list[str] = []
    if base32.size != (args.columns * 32, args.rows * 32):
        errors.append(f"base32 size is {base32.width}x{base32.height}; expected {args.columns * 32}x{args.rows * 32}")
    for cell, atlas in comparisons:
        expected = (args.columns * cell, args.rows * cell)
        if atlas.size != expected:
            errors.append(f"sheet{cell} size is {atlas.width}x{atlas.height}; expected {expected[0]}x{expected[1]}")

    cells = []
    for row in range(args.rows):
        for col in range(args.columns):
            base_frame = dominant_color_blocks(frame(base32, 32, row, col), args.palette_size)
            base_mask = alpha_mask(base_frame)
            for cell, atlas in comparisons:
                candidate = dominant_color_blocks(thumbnail_to_32(frame(atlas, cell, row, col), cell), args.palette_size)
                iou = mask_iou(base_mask, alpha_mask(candidate))
                delta = color_delta(base_frame, candidate)
                record = {
                    "row": row,
                    "column": col,
                    "comparison_cell": cell,
                    "silhouette_iou": round(iou, 4),
                    "color_delta": round(delta, 4),
                }
                cells.append(record)
                if iou < args.min_iou:
                    warnings.append(f"cell {row}:{col} sheet{cell} silhouette drift iou={iou:.3f}")
                if delta > args.max_color_delta:
                    warnings.append(f"cell {row}:{col} sheet{cell} color drift delta={delta:.3f}")

    if args.fail_on_warnings and warnings:
        errors.extend(warnings)

    report = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "thresholds": {
            "min_iou": args.min_iou,
            "max_color_delta": args.max_color_delta,
            "palette_size": args.palette_size,
        },
        "cells": cells,
    }
    out = Path(args.json_out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": not errors, "errors": errors, "warnings": len(warnings)}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
