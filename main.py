"""Honeycomb macro: the picture that tastes of one ingredient (honey).

Renders a deterministic 1024x1024 macro photograph-style image of a honeycomb
dripping golden honey, using only the Python standard library. The image is
built at 512x512 (organic irregular hex cells, a glossy honey pool, a honey
drip strand and droplet, warm directional light, radial depth of field and a
vignette), then upscaled 2x with bilinear filtering and written as a PNG
(Sub filter, zlib level 9) to $MAKEFUN_OUTPUT_DIR/entry.png (or /output).
"""

import math
import os
import struct
import zlib

BASE = 512          # render resolution, upscaled 2x to 1024
OUT = 1024
HEX_R = 17.0        # hex cell radius in base pixels
SQ3 = math.sqrt(3.0)


def frand(q, r, salt):
    """Deterministic pseudo-random float in [0, 1) from integer cell coords."""
    x = (q * 374761393 + r * 668265263 + salt * 974634211) & 0xFFFFFFFF
    x ^= (x >> 13)
    x = (x * 1274126177) & 0xFFFFFFFF
    x ^= (x >> 16)
    return (x & 0xFFFFFFFF) / 4294967296.0


def clamp(v, a=0.0, b=1.0):
    return a if v < a else (b if v > b else v)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


def smoothstep(a, b, x):
    t = clamp((x - a) / (b - a))
    return t * t * (3.0 - 2.0 * t)


def hex_round(q, r):
    """Round fractional axial coords to the nearest hex cell (cube rounding)."""
    x = q
    z = r
    y = -x - z
    rx = round(x)
    ry = round(y)
    rz = round(z)
    dx = abs(rx - x)
    dy = abs(ry - y)
    dz = abs(rz - z)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return rx, rz


def cell_center(q, r):
    cx = HEX_R * SQ3 * (q + r * 0.5)
    cy = HEX_R * 1.5 * r
    return cx, cy


# --- palette (linear-ish 0..1 RGB) -------------------------------------------
WALL_DARK = (0.34, 0.20, 0.05)
WALL_LITE = (0.62, 0.40, 0.12)
HONEY_DEEP = (0.58, 0.30, 0.04)
HONEY_MID = (0.86, 0.55, 0.12)
HONEY_BRITE = (0.98, 0.74, 0.28)
WAX_PALE = (0.95, 0.80, 0.48)
WAX_MID = (0.87, 0.66, 0.30)
EMPTY_DARK = (0.16, 0.09, 0.03)
EMPTY_MID = (0.30, 0.18, 0.07)
POOL_DEEP = (0.52, 0.26, 0.03)
POOL_BRITE = (0.97, 0.64, 0.16)
SPEC = (1.0, 0.94, 0.78)


def cell_color(q, r, px, py):
    """Colour of base pixel (px, py) from its honeycomb cell."""
    # fractional axial coords of the pixel
    fq = (SQ3 / 3.0 * px - py / 3.0) / HEX_R
    fr = (2.0 / 3.0 * py) / HEX_R
    cq, cr = hex_round(fq, fr)
    cx, cy = cell_center(cq, cr)
    # offset from cell centre, in hex-local units
    dx = px - cx
    dy = py - cy
    u = (SQ3 / 3.0 * dx - dy / 3.0) / HEX_R
    v = (2.0 / 3.0 * dy) / HEX_R
    hdist = max(abs(u), abs(v), abs(u + v))

    kind = frand(cq, cr, 0)          # cell type
    tint = frand(cq, cr, 1)          # amber variation
    inner = 0.72 + 0.20 * frand(cq, cr, 2)   # inner surface radius
    wob = frand(cq, cr, 3) * 6.283185307

    if hdist > 1.0:
        # outside this cell (should not happen for the rounded cell, but
        # keep a safe fallback): dark wall
        return WALL_DARK
    if hdist > inner:
        # wax wall between cells; a faint top highlight
        t = (hdist - inner) / (1.0 - inner)
        col = mix(WALL_LITE, WALL_DARK, clamp(t * 1.4))
        edge = smoothstep(0.55, 0.0, abs(dy - (-HEX_R * 0.55)) / HEX_R)
        return mix(col, WALL_LITE, edge * 0.25)

    # inside the cell's surface; local coords for gloss (-1..1)
    lx = clamp(dx / (HEX_R * inner))
    ly = clamp(dy / (HEX_R * inner))
    if kind < 0.55:
        # open honey: glossy amber, brighter toward the light
        base = mix(HONEY_DEEP, HONEY_MID, 0.35 + 0.55 * tint)
        base = mix(base, HONEY_BRITE, 0.25 * max(0.0, 1.0 - (lx * lx + ly * ly)))
        # specular gloss spot, offset toward the upper-left light
        gx = lx + 0.32
        gy = ly + 0.38
        gd = math.sqrt(gx * gx + gy * gy)
        spec = math.pow(max(0.0, 1.0 - gd / 0.85), 2.5) * 0.55
        # gentle swirl inside the honey
        sw = 0.05 * math.sin((lx * 2.0 + ly * 1.5) * 3.0 + wob)
        col = mix(base, HONEY_BRITE, clamp(sw + 0.12))
        return mix(col, SPEC, spec)
    if kind < 0.85:
        # capped wax: pale matte gold, soft sheen
        base = mix(WAX_MID, WAX_PALE, 0.3 + 0.6 * tint)
        sheen = math.pow(max(0.0, 1.0 - ((lx + 0.3) ** 2 + (ly + 0.35) ** 2)), 2.0)
        return mix(base, SPEC, sheen * 0.22)
    # empty cell: dark, shadowed, faint rim light at the bottom
    base = mix(EMPTY_DARK, EMPTY_MID, 0.3 + 0.5 * tint)
    rim = smoothstep(0.45, 1.0, ly) * 0.35
    return mix(base, WALL_LITE, rim)


def pool_color(px, py):
    """Glossy honey pool at the bottom; returns (colour, mask)."""
    pcx = 0.52 * BASE
    pcy = 0.88 * BASE
    prx = 0.47 * BASE
    pry = 0.30 * BASE
    dx = (px - pcx) / prx
    dy = (py - pcy) / pry
    d = math.sqrt(dx * dx + dy * dy)
    mask = 1.0 - smoothstep(0.90, 1.0, d)
    if mask <= 0.0:
        return (0.0, 0.0, 0.0), 0.0
    ang = math.atan2(dy, dx)
    swirl = 0.5 + 0.5 * math.sin(ang * 3.0 + d * 7.0)
    col = mix(POOL_DEEP, POOL_BRITE, 0.30 + 0.45 * swirl * (1.0 - d * 0.45))
    # elongated specular highlight near the pool's upper-left
    sx = (px - 0.44 * BASE) / (0.16 * BASE)
    sy = (py - 0.80 * BASE) / (0.07 * BASE)
    spec = math.exp(-(sx * sx + sy * sy)) * 0.75
    col = mix(col, SPEC, spec)
    return col, mask


def drip_color(px, py):
    """Honey drip strand from the top plus a droplet; returns (colour, mask)."""
    dx = 0.60 * BASE
    # strand: narrow vertical band from the top edge down
    if py < 0.36 * BASE:
        half = 3.2 + 1.5 * math.sin(py * 0.09)
        off = abs(px - dx)
        if off < half:
            edge = 1.0 - off / half
            col = mix(HONEY_DEEP, HONEY_BRITE, 0.35 + 0.45 * edge)
            col = mix(col, SPEC, math.pow(edge, 3.0) * 0.5)
            return col, smoothstep(half, half * 0.55, off)
    # droplet hanging at the strand's end
    dcx = dx
    dcy = 0.385 * BASE
    dr = 17.0
    ddx = px - dcx
    ddy = py - dcy
    dist = math.sqrt(ddx * ddx + ddy * ddy)
    if dist < dr:
        t = dist / dr
        col = mix(HONEY_BRITE, HONEY_DEEP, t * 0.85)
        # bright specular dot, upper-left of the droplet
        sdx = (px - (dcx - 6.0)) / 5.0
        sdy = (py - (dcy - 7.0)) / 5.0
        spec = math.exp(-(sdx * sdx + sdy * sdy)) * 0.9
        col = mix(col, SPEC, spec)
        return col, 1.0 - smoothstep(dr * 0.82, dr, dist)
    return (0.0, 0.0, 0.0), 0.0


def render_base():
    """Render the 512x512 base image as a flat list of (r, g, b) floats."""
    img = [None] * (BASE * BASE)
    for y in range(BASE):
        row = y * BASE
        # warm directional light: brighter toward the upper-left
        for x in range(BASE):
            col = cell_color_at(x, y)
            pcol, pmask = pool_color(x, y)
            if pmask > 0.0:
                col = mix(col, pcol, pmask)
            dcol, dmask = drip_color(x, y)
            if dmask > 0.0:
                col = mix(col, dcol, dmask)
            light = 0.90 + 0.20 * (1.0 - (x + y) / float(BASE + BASE))
            img[row + x] = (col[0] * light, col[1] * light, col[2] * light)
    return img


def cell_color_at(x, y):
    return cell_color(0, 0, x, y)


def box_blur(img, radius=2):
    """Separable box blur over a flat list of (r, g, b) floats."""
    w = BASE
    h = BASE
    tmp = [None] * (w * h)
    # horizontal pass
    for y in range(h):
        row = y * w
        for x in range(w):
            sr = sg = sb = 0.0
            n = 0
            for k in range(-radius, radius + 1):
                xx = x + k
                if 0 <= xx < w:
                    c = img[row + xx]
                    sr += c[0]
                    sg += c[1]
                    sb += c[2]
                    n += 1
            tmp[row + x] = (sr / n, sg / n, sb / n)
    out = [None] * (w * h)
    # vertical pass
    for y in range(h):
        for x in range(w):
            sr = sg = sb = 0.0
            n = 0
            for k in range(-radius, radius + 1):
                yy = y + k
                if 0 <= yy < h:
                    c = tmp[yy * w + x]
                    sr += c[0]
                    sg += c[1]
                    sb += c[2]
                    n += 1
            out[y * w + x] = (sr / n, sg / n, sb / n)
    return out


def apply_dof_vignette(img, blurred):
    """Blend toward the blurred copy away from the centre, then vignette."""
    cx = BASE * 0.5
    cy = BASE * 0.5
    maxr = math.sqrt(cx * cx + cy * cy)
    for y in range(BASE):
        row = y * BASE
        for x in range(BASE):
            dx = (x - cx) / maxr
            dy = (y - cy) / maxr
            r = math.sqrt(dx * dx + dy * dy)
            amt = clamp((r - 0.30) / 0.60, 0.0, 1.0) * 0.70
            a = img[row + x]
            b = blurred[row + x]
            col = mix(a, b, amt)
            vig = 1.0 - 0.30 * r * r
            img[row + x] = (col[0] * vig, col[1] * vig, col[2] * vig)
    return img


def upscale_bilinear(img):
    """Upscale the 512 base image to 1024x1024, return a bytearray of RGB."""
    out = bytearray(OUT * OUT * 3)
    for y in range(OUT):
        sy = (y + 0.5) / 2.0 - 0.5
        y0 = int(math.floor(sy))
        y1 = y0 + 1
        fy = sy - y0
        y0 = 0 if y0 < 0 else (BASE - 1 if y0 > BASE - 1 else y0)
        y1 = 0 if y1 < 0 else (BASE - 1 if y1 > BASE - 1 else y1)
        for x in range(OUT):
            sx = (x + 0.5) / 2.0 - 0.5
            x0 = int(math.floor(sx))
            x1 = x0 + 1
            fx = sx - x0
            x0 = 0 if x0 < 0 else (BASE - 1 if x0 > BASE - 1 else x0)
            x1 = 0 if x1 < 0 else (BASE - 1 if x1 > BASE - 1 else x1)
            c00 = img[y0 * BASE + x0]
            c10 = img[y0 * BASE + x1]
            c01 = img[y1 * BASE + x0]
            c11 = img[y1 * BASE + x1]
            r = lerp(lerp(c00[0], c10[0], fx), lerp(c01[0], c11[0], fx), fy)
            g = lerp(lerp(c00[1], c10[1], fx), lerp(c01[1], c11[1], fx), fy)
            b = lerp(lerp(c00[2], c10[2], fx), lerp(c01[2], c11[2], fx), fy)
            i = (y * OUT + x) * 3
            out[i] = int(clamp(r) * 255.0 + 0.5)
            out[i + 1] = int(clamp(g) * 255.0 + 0.5)
            out[i + 2] = int(clamp(b) * 255.0 + 0.5)
    return out


def png_bytes(rgb, w, h):
    """Encode RGB bytes as a PNG (colour type 2, Sub filter, zlib level 9)."""
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(1)  # Sub filter
        row = rgb[y * stride:(y + 1) * stride]
        for i in range(stride):
            left = row[i - 3] if i >= 3 else 0
            raw.append((row[i] - left) & 0xFF)

    def chunk(ctype, data):
        c = struct.pack(">I", len(data)) + ctype + data
        c += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    img = render_base()
    blurred = box_blur(img, radius=2)
    img = apply_dof_vignette(img, blurred)
    rgb = upscale_bilinear(img)
    data = png_bytes(rgb, OUT, OUT)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes, %dx%d)" % (path, len(data), OUT, OUT))


if __name__ == "__main__":
    main()
