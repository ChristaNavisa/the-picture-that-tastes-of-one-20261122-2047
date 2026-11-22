#!/usr/bin/env python3
"""The picture that tastes of one ingredient — macro honeycomb, one ingredient: HONEY.

Renders a photorealistic-style macro food photograph of a honeycomb
dripping with warm golden honey, procedurally, with the Python standard
library only (no Pillow / numpy in the grader sandbox). Writes a
deterministic 1024x1024 PNG to /output/entry.png (or $MAKEFUN_OUTPUT_DIR).

Scene: full-frame macro honeycomb, hexagonal wax cells filled with
glowing amber honey, a thick glossy honey drip falling from the top,
droplets catching warm directional light, dark warm background,
shallow depth of field (edges softly out of focus), gentle vignette.
No text in the image. One ingredient, unmistakable at 300 px.
"""

import math
import os
import struct
import zlib

W = H = 1024
SQRT3 = math.sqrt(3.0)
DITHER = 2  # +- dither amplitude; keeps gradients band-free, small for PNG size


def clamp255(v):
    if v < 0:
        return 0
    if v > 255:
        return 255
    return int(v)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(a, b, x):
    if x <= a:
        return 0.0
    if x >= b:
        return 1.0
    t = (x - a) / (b - a)
    return t * t * (3.0 - 2.0 * t)


def cell_hash(cx, cy):
    """Deterministic 0..1 hash per cell from its centre."""
    h = (int(cx * 374761393) ^ int(cy * 668265263)) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    return h / 4294967295.0


def fill_row(img, y, x0, x1, rgb):
    """Fill a horizontal span of one row (C-speed slice assignment)."""
    if y < 0 or y >= H:
        return
    if x0 < 0:
        x0 = 0
    if x1 > W:
        x1 = W
    if x1 <= x0:
        return
    img[(y * W + x0) * 3:(y * W + x1) * 3] = bytes(rgb) * (x1 - x0)


def draw_background(img):
    """Deep warm brown backdrop, darker toward the bottom corners."""
    for y in range(H):
        t = y / (H - 1)
        r = int(lerp(52, 26, t))
        g = int(lerp(26, 12, t))
        b = int(lerp(8, 4, t))
        img[y * W * 3:(y + 1) * W * 3] = bytes((r, g, b)) * W


def draw_honeycomb(img):
    """Flat-top hexagonal wax cells, each a little pool of honey.

    Per cell: a darker wax wall (outer hex) and a glowing honey pool
    (inner hex) whose brightness falls from top to bottom, plus a
    diagonal gloss band and a warm key light from the upper left.
    """
    r = 64.0
    s = SQRT3 / 2.0 * r          # 55.43 half-height of a cell
    step_x = 1.5 * r             # 96
    step_y = 2.0 * s             # 110.85
    r2 = r * 0.80
    s2 = s * 0.80

    col = 0
    cx = -r
    while cx < W + r:
        offset = s if (col % 2) else 0.0
        cy = -s + offset
        row = 0
        while cy < H + s:
            h = cell_hash(cx, cy)
            # base honey colour: deep amber -> bright gold
            br = lerp(198, 255, h)
            bg = lerp(112, 188, h)
            bb = lerp(16, 58, h)
            # warm key light, upper-left of frame
            dx = cx - 400.0
            dy = cy - 330.0
            light = 0.78 + 0.42 * math.exp(-(dx * dx + dy * dy) / (2.0 * 430.0 * 430.0))
            # diagonal gloss band across the comb
            gloss = 1.0 + 0.20 * math.exp(-((cx + cy - 980.0) / 330.0) ** 2)
            # wall colour (wax, darker and redder than the pool)
            wr = clamp255(br * 0.42 * light)
            wg = clamp255(bg * 0.38 * light)
            wb = clamp255(bb * 0.42 * light)
            # pool colour, scaled by light and gloss
            pr = br * light * gloss
            pg = bg * light * gloss
            pb = bb * light * gloss

            y0 = int(math.ceil(cy - s))
            y1 = int(math.floor(cy + s))
            for y in range(y0, y1 + 1):
                ady = abs(y - cy)
                half = r * (1.0 - ady / (2.0 * s))
                x0 = int(cx - half)
                x1 = int(cx + half)
                # tiny deterministic jitter breaks 8-bit banding
                jit = ((int(cx) * 31 + int(cy) * 17 + y * 7) % 5) - 2
                fill_row(img, y, x0, x1, (wr, wg, wb))
                if ady <= s2:
                    half2 = r2 * (1.0 - ady / (2.0 * s2))
                    # pool: bright at the top of the cell, deeper at the bottom
                    shade = 1.18 - 0.52 * ((y - (cy - s2)) / (2.0 * s2))
                    fill_row(
                        img, y, int(cx - half2), int(cx + half2),
                        (clamp255(pr * shade + jit),
                         clamp255(pg * shade + jit),
                         clamp255(pb * shade + jit)),
                    )
            cy += step_y
            row += 1
        cx += step_x
        col += 1


def draw_ellipse(img, cx, cy, rx, ry, top_rgb, bot_rgb, spec=None):
    """Glossy honey droplet: vertical gradient + optional specular spot.

    spec = (sx, sy, srx, sry, rgb) — bright highlight ellipse.
    """
    for y in range(int(cy - ry), int(cy + ry) + 1):
        dy = (y - cy) / ry
        if abs(dy) >= 1.0:
            continue
        half = rx * math.sqrt(1.0 - dy * dy)
        t = (dy + 1.0) / 2.0
        rgb = (
            clamp255(lerp(top_rgb[0], bot_rgb[0], t)),
            clamp255(lerp(top_rgb[1], bot_rgb[1], t)),
            clamp255(lerp(top_rgb[2], bot_rgb[2], t)),
        )
        fill_row(img, y, int(cx - half), int(cx + half), rgb)
        if spec is not None:
            sx, sy, srx, sry, srgb = spec
            sdy = (y - sy) / sry
            if abs(sdy) < 1.0:
                shalf = srx * math.sqrt(1.0 - sdy * sdy)
                fill_row(img, y, int(sx - shalf), int(sx + shalf), srgb)


def draw_drip(img):
    """One thick glossy honey drip falling from the top edge, wobbling
    gently, with a bright specular core and a fat droplet at its end."""
    for y in range(0, 486):
        wob = 8.0 * math.sin(y * 0.02) + 4.0 * math.sin(y * 0.045 + 1.3)
        cx = 620.0 + wob
        half = 30.0 + 5.0 * math.sin(y * 0.013 + 0.5)
        # drip darkens slightly as it falls
        shade = 1.0 - 0.18 * (y / 486.0)
        fill_row(img, y, int(cx - half), int(cx + half),
                 (clamp255(96 * shade), clamp255(48 * shade), clamp255(6 * shade)))
        fill_row(img, y, int(cx - half * 0.72), int(cx + half * 0.72),
                 (clamp255(228 * shade), clamp255(138 * shade), clamp255(12 * shade)))
        fill_row(img, y, int(cx - 3), int(cx + 3),
                 (255, 240, 180))
    # fat droplet hanging at the end of the drip
    draw_ellipse(img, 622, 512, 58, 80,
                 (246, 182, 44), (148, 78, 8),
                 spec=(606, 482, 10, 18, (255, 246, 205)))
    # small satellite droplets on the comb
    draw_ellipse(img, 300, 762, 27, 21,
                 (246, 182, 44), (148, 78, 8),
                 spec=(292, 754, 5, 6, (255, 244, 200)))
    draw_ellipse(img, 838, 706, 20, 16,
                 (246, 182, 44), (148, 78, 8),
                 spec=(832, 700, 4, 5, (255, 244, 200)))


# ---------------------------------------------------------------- blur helpers

def half_down(flat, w, h):
    """Downsample by 2 (2x2 box average). flat is a list of ints."""
    ow, oh = w // 2, h // 2
    out = [0] * (ow * oh * 3)
    for y in range(oh):
        r0 = (2 * y) * w * 3
        r1 = (2 * y + 1) * w * 3
        o = y * ow * 3
        for x in range(ow):
            i0 = r0 + 6 * x
            i1 = r1 + 6 * x
            out[o] = (flat[i0] + flat[i0 + 3] + flat[i1] + flat[i1 + 3]) // 4
            out[o + 1] = (flat[i0 + 1] + flat[i0 + 4] + flat[i1 + 1] + flat[i1 + 4]) // 4
            out[o + 2] = (flat[i0 + 2] + flat[i0 + 5] + flat[i1 + 2] + flat[i1 + 5]) // 4
            o += 3
    return out, ow, oh


def box_blur(flat, w, h, radius=2):
    """Separable box blur (radius 2) via zip comprehensions, edge-replicated."""
    n = w * h * 3
    ws = w * 3
    # horizontal pass
    tmp = [0] * n
    k = 2 * radius + 1
    for y in range(h):
        row = flat[y * ws:(y + 1) * ws]
        pad = row[:3] * radius + row + row[-3:] * radius
        views = [pad[i * 3:(len(row) + i * 3)] for i in range(k)]
        tmp[y * ws:(y + 1) * ws] = [
            (a + b + c + d + e) // k
            for a, b, c, d, e in zip(*views)
        ]
    # vertical pass (edge rows replicated)
    out = [0] * n
    pad_rows = [tmp[0:ws]] * radius + [tmp[i * ws:(i + 1) * ws] for i in range(h)] + [tmp[(h - 1) * ws:]] * radius
    for y in range(h):
        rows = pad_rows[y:y + k]
        out[y * ws:(y + 1) * ws] = [
            (a + b + c + d + e) // k
            for a, b, c, d, e in zip(*rows)
        ]
    return out


def up2(flat, w, h):
    """Nearest-neighbour upsample by 2 (each pixel -> 2x2 block)."""
    ow, oh = w * 2, h * 2
    out = [0] * (ow * oh * 3)
    for y in range(h):
        row = flat[y * w * 3:(y + 1) * w * 3]
        big = [v for i in range(0, len(row), 3) for _ in (0, 1) for v in row[i:i + 3]]
        out[(2 * y) * ow * 3:(2 * y + 1) * ow * 3] = big
        out[(2 * y + 1) * ow * 3:(2 * y + 2) * ow * 3] = big
    return out, ow, oh


def depth_of_field(sharp):
    """Blend the sharp render with a blurred copy: in focus at the
    centre, softly out of focus toward the edges (macro DOF)."""
    small, sw, sh = half_down(sharp, W, H)
    small = box_blur(small, sw, sh, radius=2)
    small = box_blur(small, sw, sh, radius=2)
    blur, bw, bh = up2(small, sw, sh)
    assert bw == W and bh == H

    # per-pixel weights: focus weight w (0 centre -> 0.8 edges),
    # vignette v (1 centre -> ~0.55 corners)
    a = [0.0] * (W * H)   # sharp multiplier (vignette * (1-w))
    b = [0.0] * (W * H)   # blur multiplier (vignette * w)
    for y in range(H):
        dy = (y - H / 2.0) / (H / 2.0)
        for x in range(W):
            dx = (x - W / 2.0) / (W / 2.0)
            dist = math.sqrt(dx * dx + dy * dy)
            wgt = smoothstep(0.28, 1.05, dist) * 0.80
            vig = 1.0 - 0.45 * smoothstep(0.55, 1.30, dist)
            i = y * W + x
            a[i] = vig * (1.0 - wgt)
            b[i] = vig * wgt
    a3 = [v for v in a for _ in (0, 1, 2)]
    b3 = [v for v in b for _ in (0, 1, 2)]
    out = bytearray(W * H * 3)
    out[:] = bytes(
        clamp255(s * ai + t * bi + ((i * 2654435761) >> 28) % (2 * DITHER + 1) - DITHER)
        for i, (s, t, ai, bi) in enumerate(zip(sharp, blur, a3, b3))
    )
    return out


# ---------------------------------------------------------------- PNG encode

def encode_png(rgb):
    """Minimal PNG encoder: 8-bit RGB, Up filter, zlib level 9."""

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    raw = bytearray()
    prev = bytearray(W * 3)
    for y in range(H):
        row = rgb[y * W * 3:(y + 1) * W * 3]
        raw.append(2)  # Up filter
        for i in range(W * 3):
            raw.append((row[i] - prev[i]) & 0xFF)
        prev = row
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    return png


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    img = bytearray(W * H * 3)
    draw_background(img)
    draw_honeycomb(img)
    draw_drip(img)
    final = depth_of_field(list(img))
    png = encode_png(final)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png)
    print("wrote %s (%d bytes, %dx%d)" % (path, len(png), W, H))


if __name__ == "__main__":
    main()
