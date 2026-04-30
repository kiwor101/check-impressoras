from __future__ import annotations

import struct
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ICON_FILE = BASE_DIR / "app_icon.ico"


def clamp(value: int) -> int:
    return max(0, min(255, value))


def blend(bottom: tuple[int, int, int, int], top: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    br, bg, bb, ba = bottom
    tr, tg, tb, ta = top
    alpha = ta / 255
    out_alpha = ta + ba * (1 - alpha)
    if out_alpha == 0:
        return (0, 0, 0, 0)
    return (
        clamp(int(tr * alpha + br * (1 - alpha))),
        clamp(int(tg * alpha + bg * (1 - alpha))),
        clamp(int(tb * alpha + bb * (1 - alpha))),
        clamp(int(out_alpha)),
    )


def draw_rect(
    pixels: list[list[tuple[int, int, int, int]]],
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: tuple[int, int, int, int],
) -> None:
    for y in range(max(0, y1), min(len(pixels), y2)):
        for x in range(max(0, x1), min(len(pixels[y]), x2)):
            pixels[y][x] = blend(pixels[y][x], color)


def draw_circle(
    pixels: list[list[tuple[int, int, int, int]]],
    cx: int,
    cy: int,
    radius: int,
    color: tuple[int, int, int, int],
) -> None:
    radius_sq = radius * radius
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if 0 <= y < len(pixels) and 0 <= x < len(pixels[y]):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius_sq:
                    pixels[y][x] = blend(pixels[y][x], color)


def draw_line(
    pixels: list[list[tuple[int, int, int, int]]],
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: tuple[int, int, int, int],
    width: int = 2,
) -> None:
    dx = abs(x2 - x1)
    dy = -abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx + dy
    x, y = x1, y1
    while True:
        draw_circle(pixels, x, y, width, color)
        if x == x2 and y == y2:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def make_icon_bitmap(size: int) -> bytes:
    pixels = [[(0, 0, 0, 0) for _ in range(size)] for _ in range(size)]
    scale = size / 64

    def s(value: int) -> int:
        return round(value * scale)

    draw_circle(pixels, s(32), s(32), s(29), (11, 127, 195, 255))
    draw_circle(pixels, s(32), s(32), s(25), (21, 147, 215, 255))
    draw_rect(pixels, s(16), s(18), s(48), s(31), (236, 245, 252, 255))
    draw_rect(pixels, s(13), s(28), s(51), s(45), (34, 52, 68, 255))
    draw_rect(pixels, s(18), s(39), s(46), s(51), (246, 250, 253, 255))
    draw_rect(pixels, s(22), s(43), s(37), s(47), (52, 67, 82, 255))
    draw_rect(pixels, s(42), s(31), s(46), s(35), (135, 207, 235, 255))
    draw_circle(pixels, s(46), s(45), s(13), (42, 166, 91, 255))
    draw_line(pixels, s(39), s(45), s(44), s(50), (255, 255, 255, 255), s(2))
    draw_line(pixels, s(44), s(50), s(53), s(39), (255, 255, 255, 255), s(2))

    rows = []
    for y in reversed(range(size)):
        row = bytearray()
        for x in range(size):
            r, g, b, a = pixels[y][x]
            row.extend((b, g, r, a))
        rows.append(bytes(row))

    xor_bitmap = b"".join(rows)
    and_mask_row_size = ((size + 31) // 32) * 4
    and_mask = b"\x00" * and_mask_row_size * size
    header = struct.pack(
        "<IIIHHIIIIII",
        40,
        size,
        size * 2,
        1,
        32,
        0,
        len(xor_bitmap) + len(and_mask),
        0,
        0,
        0,
        0,
    )
    return header + xor_bitmap + and_mask


def write_ico(path: Path) -> None:
    images = [(32, make_icon_bitmap(32)), (64, make_icon_bitmap(64))]
    header = struct.pack("<HHH", 0, 1, len(images))
    directory = bytearray()
    offset = 6 + 16 * len(images)
    data = bytearray()

    for size, image in images:
        directory.extend(
            struct.pack(
                "<BBBBHHII",
                size,
                size,
                0,
                0,
                1,
                32,
                len(image),
                offset,
            )
        )
        data.extend(image)
        offset += len(image)

    path.write_bytes(header + directory + data)


if __name__ == "__main__":
    write_ico(ICON_FILE)
    print(f"Icone criado: {ICON_FILE}")

