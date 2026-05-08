#!/usr/bin/env python3
"""Clean generated sprites toward game-ready pixel art."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image


def parse_hex_color(value: str) -> tuple[int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) != 6:
        raise argparse.ArgumentTypeError("expected #RRGGBB")
    return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))


def color_dist(color: tuple[int, int, int], key: tuple[int, int, int]) -> float:
    return math.sqrt(sum((color[i] - key[i]) ** 2 for i in range(3)))


def alpha_threshold(image: Image.Image, threshold: int) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (r, g, b, 0 if a < threshold else 255)
    return rgba


def remove_edge_chroma(image: Image.Image, key: tuple[int, int, int], threshold: float) -> Image.Image:
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


def remove_chroma_residue(image: Image.Image, key: tuple[int, int, int], threshold: float) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if a > 0 and color_dist((r, g, b), key) <= threshold:
                pixels[x, y] = (r, g, b, 0)
    return rgba


def pixelate(image: Image.Image, scale: int) -> Image.Image:
    if scale <= 1:
        return image
    small = image.resize(
        (max(1, image.width // scale), max(1, image.height // scale)),
        Image.Resampling.NEAREST,
    )
    return small.resize(image.size, Image.Resampling.NEAREST)


def quantize_keep_alpha(image: Image.Image, colors: int) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = Image.new("RGB", rgba.size, (0, 0, 0))
    rgb.paste(rgba.convert("RGB"), mask=alpha)
    quantized = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGBA")
    quantized.putalpha(alpha)
    return quantized


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cell", type=int, default=64)
    parser.add_argument("--palette", type=int, default=32)
    parser.add_argument("--alpha-threshold", type=int, default=24)
    parser.add_argument("--pixelate-scale", type=int, default=1)
    parser.add_argument("--scale-mode", choices=["nearest", "none"], default="nearest")
    parser.add_argument("--chroma-key", type=parse_hex_color)
    parser.add_argument("--edge-flood-threshold", type=float, default=105.0)
    parser.add_argument("--residue-threshold", type=float, default=72.0)
    args = parser.parse_args()

    source = Path(args.input).expanduser().resolve()
    target = Path(args.output).expanduser().resolve()
    with Image.open(source) as opened:
        image = opened.convert("RGBA")

    if args.chroma_key:
        image = remove_edge_chroma(image, args.chroma_key, args.edge_flood_threshold)
    image = alpha_threshold(image, args.alpha_threshold)
    if args.pixelate_scale > 1:
        image = pixelate(image, args.pixelate_scale)
    if args.palette > 0:
        image = quantize_keep_alpha(image, args.palette)
    if args.chroma_key:
        image = remove_chroma_residue(image, args.chroma_key, args.residue_threshold)

    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
