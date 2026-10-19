"""Draw the extension icons (red tile, white newspaper) as PNGs, no dependencies.
Usage: make_icons.py extension/icons
"""
import os
import struct
import sys
import zlib

SUPERSAMPLE = 4
RED_TOP, RED_BOTTOM = (255, 82, 99), (226, 33, 58)


def inside_round_rect(x, y, x0, y0, x1, y1, r):
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def shade(u, v):
    """Colour at normalised point (u, v) in [0,1]^2, or None for transparent."""
    if not inside_round_rect(u, v, 0, 0, 1, 1, 0.22):
        return None
    if inside_round_rect(u, v, 0.22, 0.2, 0.78, 0.8, 0.06):  # paper
        lines = [(0.28, 0.30, 0.72, 0.38, (226, 33, 58))]  # masthead bar
        lines += [(0.28, y, 0.72, y + 0.045, (150, 150, 158)) for y in (0.47, 0.56, 0.65)]
        for x0, y0, x1, y1, colour in lines:
            if x0 <= u <= x1 and y0 <= v <= y1:
                return colour
        return (255, 255, 255)
    t = v
    return tuple(round(a + (b - a) * t) for a, b in zip(RED_TOP, RED_BOTTOM))


def render(size):
    rows = []
    n = SUPERSAMPLE
    for py in range(size):
        row = bytearray([0])  # PNG filter: none
        for px in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(n):
                for sx in range(n):
                    c = shade((px + (sx + 0.5) / n) / size, (py + (sy + 0.5) / n) / size)
                    if c:
                        acc[0] += c[0]; acc[1] += c[1]; acc[2] += c[2]; acc[3] += 1
            covered = acc[3]
            if covered:
                row += bytes([acc[0] // covered, acc[1] // covered, acc[2] // covered,
                              round(255 * covered / (n * n))])
            else:
                row += bytes(4)
        rows.append(bytes(row))
    return png(size, b"".join(rows))


def png(size, raw):
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for size in (16, 32, 48, 128):
        with open(os.path.join(out, "icon-%d.png" % size), "wb") as f:
            f.write(render(size))
