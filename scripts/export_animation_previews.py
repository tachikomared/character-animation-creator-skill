#!/usr/bin/env python3
"""Export preview animations from a fixed-cell sprite atlas.

The GIF path avoids common transparent-GIF failure modes:
- stable global palette
- palette index 0 reserved for transparent pixels
- disposal=2 so frames do not accumulate into a smear
- no dithering
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def nearest_upscale(image: Image.Image, scale: int) -> Image.Image:
    if scale <= 1:
        return image
    return image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)


def checker(size: tuple[int, int], block: int = 8) -> Image.Image:
    w, h = size
    out = Image.new("RGBA", size)
    a = (42, 46, 54, 255)
    b = (68, 74, 86, 255)
    px = out.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = a if ((x // block) + (y // block)) % 2 == 0 else b
    return out


def extract_row(atlas: Image.Image, row: int, columns: int, cell: int) -> list[Image.Image]:
    frames = []
    for col in range(columns):
        box = (col * cell, row * cell, (col + 1) * cell, (row + 1) * cell)
        frames.append(atlas.crop(box).convert("RGBA"))
    return frames


def save_webp(frames: list[Image.Image], path: Path, scale: int, duration: int) -> None:
    upscaled = [nearest_upscale(frame, scale) for frame in frames]
    upscaled[0].save(
        path,
        save_all=True,
        append_images=upscaled[1:],
        duration=duration,
        loop=0,
        lossless=True,
        exact=True,
        method=6,
    )


def make_global_palette(frames: list[Image.Image]) -> list[int]:
    palette_colors: list[tuple[int, int, int]] = [(0, 255, 0)]
    seen = {palette_colors[0]}
    counts: dict[tuple[int, int, int], int] = {}
    for frame in frames:
        for count, color in frame.getcolors(maxcolors=1000000) or []:
            r, g, b, a = color
            if a == 0:
                continue
            rgb = (r, g, b)
            counts[rgb] = counts.get(rgb, 0) + count

    for rgb, _count in sorted(counts.items(), key=lambda item: item[1], reverse=True):
        if rgb in seen:
            continue
        palette_colors.append(rgb)
        seen.add(rgb)
        if len(palette_colors) == 256:
            break

    data: list[int] = []
    for rgb in palette_colors:
        data.extend(rgb)
    data.extend([0, 0, 0] * (256 - len(palette_colors)))
    return data


def save_transparent_gif(frames: list[Image.Image], path: Path, scale: int, duration: int) -> None:
    upscaled = [nearest_upscale(frame, scale).convert("RGBA") for frame in frames]
    palette = make_global_palette(upscaled)
    colors = [tuple(palette[i : i + 3]) for i in range(0, 768, 3)]
    color_to_index = {rgb: i for i, rgb in enumerate(colors)}
    nearest_cache: dict[tuple[int, int, int], int] = {}

    def nearest_index(rgb: tuple[int, int, int]) -> int:
        if rgb in nearest_cache:
            return nearest_cache[rgb]
        best = min(
            range(1, 256),
            key=lambda i: sum((rgb[channel] - colors[i][channel]) ** 2 for channel in range(3)),
        )
        nearest_cache[rgb] = best
        return best

    paletted_frames: list[Image.Image] = []
    for frame in upscaled:
        out = Image.new("P", frame.size, 0)
        out.putpalette(palette)
        src = frame.load()
        dst = out.load()
        for y in range(frame.height):
            for x in range(frame.width):
                r, g, b, a = src[x, y]
                dst[x, y] = 0 if a == 0 else color_to_index.get((r, g, b), nearest_index((r, g, b)))
        paletted_frames.append(out)

    paletted_frames[0].save(
        path,
        save_all=True,
        append_images=paletted_frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        transparency=0,
        optimize=False,
        dither=Image.Dither.NONE,
    )


def save_checker_gif(frames: list[Image.Image], path: Path, scale: int, duration: int, cell: int) -> None:
    bg = checker((cell * scale, cell * scale), block=8 * scale)
    composited = []
    for frame in frames:
        canvas = bg.copy()
        canvas.alpha_composite(nearest_upscale(frame, scale))
        composited.append(canvas.convert("RGB").quantize(colors=128, dither=Image.Dither.NONE))
    composited[0].save(
        path,
        save_all=True,
        append_images=composited[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=False,
    )


def save_strip(frames: list[Image.Image], path: Path, scale: int, cell: int) -> None:
    out = Image.new("RGBA", (cell * len(frames) * scale, cell * scale), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        out.alpha_composite(nearest_upscale(frame, scale), (i * cell * scale, 0))
    out.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--cell", type=int, default=64)
    parser.add_argument("--scale", type=int, default=4)
    parser.add_argument("--duration", type=int, default=90)
    parser.add_argument("--prefix", default="row")
    parser.add_argument("--row-names", default="")
    args = parser.parse_args()

    atlas_path = Path(args.atlas).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    row_names = [name.strip() for name in args.row_names.split(",") if name.strip()]
    if row_names and len(row_names) != args.rows:
        raise SystemExit(f"--row-names has {len(row_names)} names; expected {args.rows}")

    with Image.open(atlas_path) as opened:
        atlas = opened.convert("RGBA")

    expected = (args.columns * args.cell, args.rows * args.cell)
    if atlas.size != expected:
        raise SystemExit(f"atlas is {atlas.width}x{atlas.height}; expected {expected[0]}x{expected[1]}")

    for row in range(args.rows):
        name = row_names[row] if row_names else f"{row:02d}"
        stem = f"{args.prefix}-{name}"
        frames = extract_row(atlas, row, args.columns, args.cell)
        save_webp(frames, out_dir / f"{stem}-transparent-x{args.scale}.webp", args.scale, args.duration)
        save_transparent_gif(frames, out_dir / f"{stem}-transparent-x{args.scale}.gif", args.scale, args.duration)
        save_checker_gif(frames, out_dir / f"{stem}-checker-x{args.scale}.gif", args.scale, args.duration, args.cell)
        save_strip(frames, out_dir / f"{stem}-strip-x{args.scale}.png", args.scale, args.cell)

    print(f"wrote previews to {out_dir}")


if __name__ == "__main__":
    main()
