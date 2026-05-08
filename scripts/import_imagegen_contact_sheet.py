#!/usr/bin/env python3
"""Import an imagegen multi-size contact sheet into fixed-cell generated strips."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from collections import deque
from pathlib import Path

from PIL import Image


def parse_hex_color(value: str) -> tuple[int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) != 6:
        raise argparse.ArgumentTypeError("expected #RRGGBB")
    return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))


def parse_csv_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def color_dist(color: tuple[int, int, int], key: tuple[int, int, int]) -> float:
    return math.sqrt(sum((color[i] - key[i]) ** 2 for i in range(3)))


def is_separator_pixel(r: int, g: int, b: int, a: int) -> bool:
    return a > 0 and r > 220 and g > 220 and b > 220 and max(r, g, b) - min(r, g, b) < 28


def detect_horizontal_bounds(image: Image.Image, rows: int) -> list[tuple[int, int]]:
    w, h = image.size
    pix = image.load()
    separators = []
    for y in range(h):
        count = 0
        for x in range(w):
            if is_separator_pixel(*pix[x, y]):
                count += 1
        if count >= w * 0.82:
            separators.append(y)

    runs = []
    if separators:
        start = prev = separators[0]
        for y in separators[1:]:
            if y <= prev + 2:
                prev = y
            else:
                runs.append((start, prev))
                start = prev = y
        runs.append((start, prev))

    boundaries = [0]
    for start, end in runs:
        center = (start + end + 1) // 2
        if 6 < center < h - 6:
            boundaries.append(center)
    boundaries.append(h)
    boundaries = sorted(set(boundaries))

    if len(boundaries) != rows + 1:
        step = h / rows
        boundaries = [round(index * step) for index in range(rows + 1)]
    return [(boundaries[i], boundaries[i + 1]) for i in range(rows)]


def remove_edge_key(image: Image.Image, key: tuple[int, int, int], threshold: float) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    w, h = rgba.size
    seen = bytearray(w * h)
    queue: deque[tuple[int, int]] = deque()

    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h - 1))
    for y in range(h):
        queue.append((0, y))
        queue.append((w - 1, y))

    while queue:
        x, y = queue.popleft()
        idx = y * w + x
        if seen[idx]:
            continue
        seen[idx] = 1
        r, g, b, a = pixels[x, y]
        if a <= 8 or color_dist((r, g, b), key) > threshold:
            continue
        pixels[x, y] = (r, g, b, 0)
        if x > 0:
            queue.append((x - 1, y))
        if x + 1 < w:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y + 1 < h:
            queue.append((x, y + 1))
    return rgba


def clear_near_key(image: Image.Image, key: tuple[int, int, int], threshold: float) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a > 0 and color_dist((r, g, b), key) <= threshold:
                pixels[x, y] = (r, g, b, 0)
    return rgba


def fit_to_cell(source: Image.Image, cell: int, key: tuple[int, int, int]) -> Image.Image:
    cleaned = clear_near_key(source, key, 36.0)
    bbox = cleaned.getbbox()
    out = Image.new("RGBA", (cell, cell), key + (255,))
    if bbox is None:
        return out
    crop = cleaned.crop(bbox)
    margin = max(1, cell // 16)
    max_side = max(1, cell - margin * 2)
    scale = min(max_side / crop.width, max_side / crop.height)
    crop = crop.resize(
        (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
        Image.Resampling.NEAREST,
    )
    transparent = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
    transparent.alpha_composite(crop, ((cell - crop.width) // 2, (cell - crop.height) // 2))
    out.alpha_composite(transparent)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--direction", required=True)
    parser.add_argument("--sizes", required=True, help="Comma-separated cell sizes, one per image row")
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--key-color", type=parse_hex_color, default=parse_hex_color("#00ff00"))
    parser.add_argument("--edge-threshold", type=float, default=118.0)
    parser.add_argument("--copy-source", action="store_true")
    args = parser.parse_args()

    source = Path(args.input).expanduser().resolve()
    run_dir = Path(args.run_dir).expanduser().resolve()
    sizes = parse_csv_ints(args.sizes)
    with Image.open(source) as opened:
        sheet = opened.convert("RGBA")

    row_bounds = detect_horizontal_bounds(sheet, len(sizes))
    col_width = sheet.width / args.columns
    outputs = []

    for row, cell in enumerate(sizes):
        y0, y1 = row_bounds[row]
        strip = Image.new("RGBA", (cell * args.columns, cell), args.key_color + (255,))
        frames_dir = run_dir / str(cell) / "generated"
        frames_dir.mkdir(parents=True, exist_ok=True)
        for col in range(args.columns):
            x0 = round(col * col_width)
            x1 = round((col + 1) * col_width)
            inset = 2
            crop = sheet.crop((x0 + inset, y0 + inset, x1 - inset, y1 - inset))
            crop = remove_edge_key(crop, args.key_color, args.edge_threshold)
            frame = fit_to_cell(crop, cell, args.key_color)
            strip.alpha_composite(frame, (col * cell, 0))
        out = frames_dir / f"{args.action}-{args.direction}.png"
        strip.save(out)
        outputs.append({"cell": cell, "path": str(out), "row_bounds": [y0, y1]})

    source_copy = None
    if args.copy_source:
        source_dir = run_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        source_copy = source_dir / source.name
        shutil.copy2(source, source_copy)

    report = {
        "input": str(source),
        "source_copy": str(source_copy) if source_copy else None,
        "action": args.action,
        "direction": args.direction,
        "sizes": sizes,
        "columns": args.columns,
        "row_bounds": row_bounds,
        "outputs": outputs,
    }
    report_path = run_dir / "imagegen-import-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
