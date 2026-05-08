#!/usr/bin/env python3
"""Assemble a single action atlas from separate direction strips."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image


DEFAULT_DIRECTIONS = [
    "south",
    "south-east",
    "east",
    "north-east",
    "north",
    "north-west",
    "west",
    "south-west",
]


def parse_hex_color(value: str) -> tuple[int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) != 6:
        raise argparse.ArgumentTypeError("expected #RRGGBB")
    return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))


def color_dist(color: tuple[int, int, int], key: tuple[int, int, int]) -> float:
    return math.sqrt(sum((color[i] - key[i]) ** 2 for i in range(3)))


def remove_edge_key(image: Image.Image, key: tuple[int, int, int], threshold: float) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    w, h = rgba.size
    seen = bytearray(w * h)
    stack: list[tuple[int, int]] = []

    for x in range(w):
        stack.append((x, 0))
        stack.append((x, h - 1))
    for y in range(h):
        stack.append((0, y))
        stack.append((w - 1, y))

    while stack:
        x, y = stack.pop()
        idx = y * w + x
        if seen[idx]:
            continue
        seen[idx] = 1
        r, g, b, a = pixels[x, y]
        if a <= 8 or color_dist((r, g, b), key) > threshold:
            continue
        pixels[x, y] = (r, g, b, 0)
        if x:
            stack.append((x - 1, y))
        if x + 1 < w:
            stack.append((x + 1, y))
        if y:
            stack.append((x, y - 1))
        if y + 1 < h:
            stack.append((x, y + 1))
    return rgba


def components(image: Image.Image, alpha_cutoff: int) -> list[dict[str, object]]:
    alpha = image.getchannel("A")
    w, h = image.size
    data = alpha.tobytes()
    seen = bytearray(w * h)
    found: list[dict[str, object]] = []
    for start, a in enumerate(data):
        if a <= alpha_cutoff or seen[start]:
            continue
        stack = [start]
        seen[start] = 1
        pixels: list[int] = []
        min_x = w
        min_y = h
        max_x = 0
        max_y = 0
        while stack:
            cur = stack.pop()
            pixels.append(cur)
            x = cur % w
            y = cur // w
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
            for nxt in (
                cur - 1 if x else -1,
                cur + 1 if x + 1 < w else -1,
                cur - w if y else -1,
                cur + w if y + 1 < h else -1,
            ):
                if nxt >= 0 and not seen[nxt] and data[nxt] > alpha_cutoff:
                    seen[nxt] = 1
                    stack.append(nxt)
        found.append(
            {
                "pixels": pixels,
                "area": len(pixels),
                "bbox": (min_x, min_y, max_x + 1, max_y + 1),
                "center_x": (min_x + max_x + 1) / 2,
            }
        )
    return found


def component_image(source: Image.Image, group: list[dict[str, object]], padding: int) -> Image.Image:
    w, h = source.size
    min_x = max(0, min(c["bbox"][0] for c in group) - padding)
    min_y = max(0, min(c["bbox"][1] for c in group) - padding)
    max_x = min(w, max(c["bbox"][2] for c in group) + padding)
    max_y = min(h, max(c["bbox"][3] for c in group) + padding)
    out = Image.new("RGBA", (max_x - min_x, max_y - min_y), (0, 0, 0, 0))
    src_px = source.load()
    out_px = out.load()
    for comp in group:
        for idx in comp["pixels"]:
            x = idx % w
            y = idx // w
            out_px[x - min_x, y - min_y] = src_px[x, y]
    return out


def fit_cell(
    sprite: Image.Image,
    cell_size: int,
    key: tuple[int, int, int],
    residue_threshold: float,
) -> Image.Image:
    bbox = sprite.getbbox()
    cell = Image.new("RGBA", (cell_size, cell_size), (0, 0, 0, 0))
    if bbox is None:
        return cell
    crop = sprite.crop(bbox)
    margin = max(2, cell_size // 16)
    max_size = cell_size - margin
    scale = min(max_size / crop.width, max_size / crop.height, 1.0)
    if scale != 1.0:
        crop = crop.resize(
            (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
            Image.Resampling.NEAREST,
        )
    cell.alpha_composite(crop, ((cell_size - crop.width) // 2, (cell_size - crop.height) // 2))

    pixels = cell.load()
    for y in range(cell_size):
        for x in range(cell_size):
            r, g, b, a = pixels[x, y]
            if a > 0 and color_dist((r, g, b), key) <= residue_threshold:
                pixels[x, y] = (r, g, b, 0)
    return cell


def extract_frames(
    path: Path,
    columns: int,
    cell_size: int,
    key: tuple[int, int, int],
    edge_threshold: float,
    residue_threshold: float,
    alpha_cutoff: int,
) -> list[Image.Image]:
    with Image.open(path) as opened:
        keyed = remove_edge_key(opened, key, edge_threshold)
    comps = components(keyed, alpha_cutoff)
    if len(comps) < columns:
        raise SystemExit(f"{path.name}: found only {len(comps)} sprite components")
    largest = max(c["area"] for c in comps)
    seeds = [c for c in comps if c["area"] >= max(80, largest * 0.18)]
    seeds = sorted(sorted(seeds, key=lambda c: c["area"], reverse=True)[:columns], key=lambda c: c["center_x"])
    if len(seeds) != columns:
        raise SystemExit(f"{path.name}: found {len(seeds)} frame seeds")

    seed_ids = {id(seed) for seed in seeds}
    groups: list[list[dict[str, object]]] = [[seed] for seed in seeds]
    for comp in comps:
        if id(comp) in seed_ids or comp["area"] < 12:
            continue
        nearest = min(range(columns), key=lambda i: abs(seeds[i]["center_x"] - comp["center_x"]))
        groups[nearest].append(comp)

    source_padding = max(3, cell_size // 16)
    return [
        fit_cell(component_image(keyed, group, source_padding), cell_size, key, residue_threshold)
        for group in groups
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--directions", default=",".join(DEFAULT_DIRECTIONS))
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--cell", type=int, default=64)
    parser.add_argument("--key-color", type=parse_hex_color, default=parse_hex_color("#00ff00"))
    parser.add_argument("--edge-threshold", type=float, default=105.0)
    parser.add_argument("--residue-threshold", type=float, default=72.0)
    parser.add_argument("--alpha-cutoff", type=int, default=16)
    parser.add_argument("--frames-dir")
    parser.add_argument("--metadata")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    directions = [direction.strip() for direction in args.directions.split(",") if direction.strip()]
    atlas = Image.new("RGBA", (args.columns * args.cell, len(directions) * args.cell), (0, 0, 0, 0))
    frames_dir = Path(args.frames_dir).expanduser().resolve() if args.frames_dir else output.parent / "frames"
    metadata = {
        "cell": args.cell,
        "columns": args.columns,
        "rows": len(directions),
        "action": args.action,
        "directions": directions,
        "rows_meta": [],
    }

    for row, direction in enumerate(directions):
        source = input_dir / f"{args.action}-{direction}.png"
        frames = extract_frames(
            source,
            args.columns,
            args.cell,
            args.key_color,
            args.edge_threshold,
            args.residue_threshold,
            args.alpha_cutoff,
        )
        row_dir = frames_dir / f"{args.action}-{direction}"
        row_dir.mkdir(parents=True, exist_ok=True)
        for col, frame in enumerate(frames):
            frame.save(row_dir / f"{col:02d}.png")
            atlas.alpha_composite(frame, (col * args.cell, row * args.cell))
        metadata["rows_meta"].append({"row": row, "action": args.action, "direction": direction, "frames": args.columns})

    output.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(output)
    metadata_path = Path(args.metadata).expanduser().resolve() if args.metadata else output.with_name(f"{args.action}-metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
