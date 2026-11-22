#!/usr/bin/env python3
"""
Honeycomb macro, round 2 - the picture that tastes of one ingredient: honey.

A macro photograph of a honeycomb, rendered procedurally with the standard
library only. Deterministic: the same bytes on every run.

Design (new for r2, more photorealistic than r1):
  * irregular honeycomb - every cell gets its own size, wobble, tint and
    fill (open honey / capped wax / empty), so the comb reads organic,
    not geometric.
  * a thick glossy pool of honey poured over the comb, with an elongated
    specular highlight and a darker meniscus rim.
  * a honey drip: a wavy strand falling from the top edge ending in a
    glossy droplet about to land in the pool.
  * warm directional light from the upper left, large-scale mottling,
    fine wax texture, depth of field (sharp centre, soft edges),
    vignette and a whisper of grain.
"""
import math
import os
import struct
import zlib

OUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
OUT_PATH = os.path.join(OUT_DIR, "entry.png")

BASE = 512            # internal render resolution
W = H = 1024          # final image size
SQ3 = math.sqrt(3.0)
HEX_S = 34.0          # honeycomb cell circumradius, base pixels
FOCUS = (BASE * 0.50, BASE * 0.58)
POOL_C = (BASE * 0.54, BASE * 0.66)
POOL_R = 148.0
STRAND_CX = BASE * 0.47
STRAND_Y1 = int(BASE * 0.30)
DROP_C = (STRAND_CX + 8.0 * math.sin(STRAND_Y1 * 0.028), STRAND_Y1 + 12.0)
DROP_R = 17.0


# ---------------------------------------------------------------- helpers
def clamp255(v):
    if v < 0.0:
        return 0
    if v > 255.0:
        return 255
    return int(v + 0.5)


def lerp(a, b, t):
    return a + (b - a) * t


def sstep(a, b, x):
    if x <= a:
        return 0.0
    if x >= b:
        return 1.0
    t = (x - a) / (b - a)
    return t * t * (3.0 - 2.0 * t)


def h2(ix, iy, seed):
    """Deterministic hash of integer coords -> [0, 1)."""
    h = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = (h ^ (h >> 16)) & 0xFFFFFFFF
    return h / 4294967296.0


def vnoise(x, y):
    """Smooth value noise in [0, 1)."""
    ix = int(math.floor(x))
    iy = int(math.floor(y))
    fx = x - ix
    fy = y - iy
    ux = fx * fx * (3.0 - 2.0 * fx)
    uy = fy * fy * (3.0 - 2.0 * fy)
    a = h2(ix, iy, 7)
    b = h2(ix + 1, iy, 7)
    c = h2(ix, iy + 1, 7)
    d = h2(ix + 1, iy + 1, 7)
    return lerp(lerp(a, b, ux), lerp(c, d, ux), uy)


# ---------------------------------------------------------------- honeycomb
_cell_cache = {}


def cell_info(q, r):
    info = _cell_cache.get((q, r))
    if info is None:
        t = h2(q, r, 11)
        if t < 0.52:
            kind = 0          # open cell, full of honey
        elif t < 0.86:
            kind = 1          # capped with pale wax
        else:
            kind = 2          # empty, deep shadow
        radius = 0.86 + 0.11 * h2(q, r, 13)
        phase = h2(q, r, 17) * 6.283185307
        tint = 0.82 + 0.36 * h2(q, r, 19)
        glint = h2(q, r, 23)
        info = (kind, radius, phase, tint, glint)
        _cell_cache[(q, r)] = info
    return info


def cube_round(q, r):
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return rq, rr


def cell_center(q, r):
    return (HEX_S * 1.5 * q, HEX_S * SQ3 * (r + q / 2.0))


def pool_radius_at(ux, uy):
    """Organic wobble of the pool outline, +/-20%."""
    return POOL_R * (1.0 + 0.40 * (vnoise(ux * 2.0 + 9.1, uy * 2.0 + 3.7) - 0.5))


# ---------------------------------------------------------------- render
def render_base():
    R = [0.0] * (BASE * BASE)
    G = [0.0] * (BASE * BASE)
    B = [0.0] * (BASE * BASE)
    for y in range(BASE):
        for x in range(BASE):
            # --- which honeycomb cell ---
            qf = (2.0 / 3.0 * x) / HEX_S
            rf = (-1.0 / 3.0 * x + SQ3 / 3.0 * y) / HEX_S
            q, r = cube_round(qf, rf)
            cx, cy = cell_center(q, r)
            dx = x - cx
            dy = y - cy
            lq = (2.0 / 3.0 * dx) / HEX_S
            lr = (-1.0 / 3.0 * dx + SQ3 / 3.0 * dy) / HEX_S
            d = max(abs(lq), abs(lr), abs(lq + lr))
            kind, radius, phase, tint, glint = cell_info(q, r)
            wob = 1.0 + 0.05 * math.sin(6.0 * lq + 4.0 * lr + phase)
            inside = d < radius * wob

            if inside:
                if kind == 0:
                    # open honey: deep amber, brighter toward the light
                    g = 0.5 + 0.5 * (dy / HEX_S)
                    cr = lerp(238.0, 168.0, g) * tint
                    cg = lerp(165.0, 92.0, g) * tint
                    cb = lerp(48.0, 14.0, g) * tint
                    # specular glint, upper-left of the cell
                    gx = cx - HEX_S * 0.30
                    gy = cy - HEX_S * 0.34
                    gd = (x - gx) * (x - gx) + (y - gy) * (y - gy)
                    gl = math.exp(-gd / 72.0) * (0.5 + 0.5 * glint)
                    cr += 90.0 * gl
                    cg += 70.0 * gl
                    cb += 30.0 * gl
                elif kind == 1:
                    # capped wax: pale gold dome, brighter in the middle
                    dome = 1.0 - (d / (radius * wob)) ** 2
                    cr = (225.0 + 25.0 * dome) * tint
                    cg = (185.0 + 20.0 * dome) * tint
                    cb = (95.0 + 18.0 * dome) * tint
                else:
                    # empty cell: dark brown, not pitch black, with a
                    # faint gradient so it still reads as a wax cavity
                    g = 0.5 + 0.5 * (dy / HEX_S)
                    cr = lerp(95.0, 55.0, g)
                    cg = lerp(52.0, 28.0, g)
                    cb = lerp(20.0, 8.0, g)
            else:
                # wax wall, darker in the crevice between cells
                wall = 0.72 + 0.28 * (1.0 - min(d, 1.3) / 1.3)
                cr = 208.0 * wall
                cg = 166.0 * wall
                cb = 72.0 * wall

            # --- glossy honey pool poured over the comb ---
            pdx = x - POOL_C[0]
            pdy = y - POOL_C[1]
            pr = math.hypot(pdx, pdy)
            if pr < POOL_R * 1.25:
                ux = pdx / pr if pr > 1e-6 else 0.0
                uy = pdy / pr if pr > 1e-6 else 0.0
                prr = pool_radius_at(ux, uy)
                if pr < prr:
                    pg = 0.5 + 0.5 * (pdy / POOL_R)
                    cr = lerp(240.0, 150.0, pg)
                    cg = lerp(165.0, 75.0, pg)
                    cb = lerp(55.0, 10.0, pg)
                    # subtle swirls in the liquid honey, breaks the flat look
                    sw = vnoise(x * 0.06 + 3.1, y * 0.06 + 8.7)
                    cr *= 0.92 + 0.16 * sw
                    cg *= 0.92 + 0.16 * sw
                    cb *= 0.92 + 0.16 * sw
                    # elongated specular highlight, upper-left of the pool
                    hx = POOL_C[0] - 52.0
                    hy = POOL_C[1] - 58.0
                    hd = ((x - hx) / 46.0) ** 2 + ((y - hy) / 20.0) ** 2
                    hl = math.exp(-hd * 2.0)
                    cr += 70.0 * hl
                    cg += 60.0 * hl
                    cb += 28.0 * hl
                    # darker meniscus rim near the edge
                    edge = sstep(prr - 10.0, prr, pr)
                    cr *= 1.0 - 0.25 * edge
                    cg *= 1.0 - 0.25 * edge
                    cb *= 1.0 - 0.25 * edge

            # --- honey drip: wavy strand + glossy droplet ---
            if 0 <= y <= STRAND_Y1 + 30 and abs(x - STRAND_CX) < 26.0:
                if y <= STRAND_Y1:
                    sx = STRAND_CX + 8.0 * math.sin(y * 0.028)
                    w = 6.0 + 2.5 * math.sin(y * 0.05 + 1.0)
                    ax = abs(x - sx)
                    if ax < w:
                        cr, cg, cb = 218.0, 138.0, 26.0
                        hl = math.exp(-((x - (sx - w * 0.45)) ** 2) / 8.0)
                        cr += 70.0 * hl
                        cg += 55.0 * hl
                        cb += 25.0 * hl
                        if ax > w * 0.8:
                            cr *= 0.75
                            cg *= 0.75
                            cb *= 0.75
                ddx = x - DROP_C[0]
                ddy = y - DROP_C[1]
                dd = ddx * ddx + ddy * ddy
                if dd < DROP_R * DROP_R:
                    cr, cg, cb = 222.0, 142.0, 28.0
                    hd = (x - (DROP_C[0] - 6.0)) ** 2 + (y - (DROP_C[1] - 7.0)) ** 2
                    hl = math.exp(-hd / 50.0)
                    cr += 80.0 * hl
                    cg += 65.0 * hl
                    cb += 30.0 * hl
                    if dd > (DROP_R * 0.85) ** 2:
                        cr *= 0.8
                        cg *= 0.8
                        cb *= 0.8

            # --- warm directional light + texture ---
            light = 0.80 + 0.20 * ((1.0 - x / BASE) * 0.6 + (1.0 - y / BASE) * 0.4)
            n = vnoise(x * 0.11, y * 0.11)
            m = 0.97 + 0.06 * (n - 0.5)
            cr = cr * light * m
            cg = cg * light * m
            cb = cb * light * m
            glow = math.exp(-(((x - 90.0) ** 2 + (y - 70.0) ** 2) / 135200.0))
            cr += 14.0 * glow
            cg += 7.0 * glow

            i = y * BASE + x
            R[i] = cr
            G[i] = cg
            B[i] = cb
    return R, G, B


def blur3(ch):
    """One separable 3-tap box blur pass."""
    tmp = [0.0] * (BASE * BASE)
    for y in range(BASE):
        row = y * BASE
        for x in range(BASE):
            a = ch[row + (x - 1 if x > 0 else 0)]
            b = ch[row + x]
            c = ch[row + (x + 1 if x < BASE - 1 else BASE - 1)]
            tmp[row + x] = (a + b + c) / 3.0
    out = [0.0] * (BASE * BASE)
    for y in range(BASE):
        for x in range(BASE):
            a = tmp[(y - 1 if y > 0 else 0) * BASE + x]
            b = tmp[y * BASE + x]
            c = tmp[(y + 1 if y < BASE - 1 else BASE - 1) * BASE + x]
            out[y * BASE + x] = (a + b + c) / 3.0
    return out


def grain_tile():
    """256x256 tile of hash noise, for the film grain."""
    return [h2(ix, iy, 41) for iy in range(256) for ix in range(256)]


def main():
    R, G, B = render_base()
    Rb, Gb, Bb = blur3(R), blur3(G), blur3(B)
    tile = grain_tile()

    # depth of field + vignette + grain, at base resolution
    for y in range(BASE):
        for x in range(BASE):
            i = y * BASE + x
            dx = x - FOCUS[0]
            dy = y - FOCUS[1]
            dist = math.hypot(dx, dy)
            w = sstep(70.0, 250.0, dist) * 0.85
            r = R[i] * (1.0 - w) + Rb[i] * w
            g = G[i] * (1.0 - w) + Gb[i] * w
            b = B[i] * (1.0 - w) + Bb[i] * w
            nx = x / BASE
            ny = y / BASE
            rn = math.hypot(nx - 0.5, ny - 0.5) * 2.0
            vig = 1.0 - 0.30 * sstep(0.55, 1.05, rn)
            gr = (tile[((x + 13) % 256) + ((y + 29) % 256) * 256] - 0.5) * 3.0
            R[i] = r * vig + gr
            G[i] = g * vig + gr
            B[i] = b * vig + gr

    # upscale 2x (exact averages) to 1024x1024, interleaved RGB bytes
    px = bytearray(W * H * 3)
    for iy in range(BASE):
        iy1 = iy + 1 if iy < BASE - 1 else BASE - 1
        oy0 = iy * 2
        oy1 = oy0 + 1
        for ix in range(BASE):
            ix1 = ix + 1 if ix < BASE - 1 else BASE - 1
            i00 = iy * BASE + ix
            i10 = iy * BASE + ix1
            i01 = iy1 * BASE + ix
            i11 = iy1 * BASE + ix1
            r00, g00, b00 = R[i00], G[i00], B[i00]
            r10, g10, b10 = R[i10], G[i10], B[i10]
            r01, g01, b01 = R[i01], G[i01], B[i01]
            r11, g11, b11 = R[i11], G[i11], B[i11]
            o = (oy0 * W + ix * 2) * 3
            px[o] = clamp255(r00)
            px[o + 1] = clamp255(g00)
            px[o + 2] = clamp255(b00)
            px[o + 3] = clamp255((r00 + r10) * 0.5)
            px[o + 4] = clamp255((g00 + g10) * 0.5)
            px[o + 5] = clamp255((b00 + b10) * 0.5)
            o = (oy1 * W + ix * 2) * 3
            px[o] = clamp255((r00 + r01) * 0.5)
            px[o + 1] = clamp255((g00 + g01) * 0.5)
            px[o + 2] = clamp255((b00 + b01) * 0.5)
            px[o + 3] = clamp255((r00 + r10 + r01 + r11) * 0.25)
            px[o + 4] = clamp255((g00 + g10 + g01 + g11) * 0.25)
            px[o + 5] = clamp255((b00 + b10 + b01 + b11) * 0.25)

    # PNG encode (filter Sub, zlib level 9). Sub stores each pixel as the
    # difference from its left neighbour, which compresses far better than
    # raw bytes for the smooth gradients in this image.
    raw = bytearray()
    row_bytes = W * 3
    for y in range(H):
        raw.append(1)
        row = px[y * row_bytes:(y + 1) * row_bytes]
        raw += row[:3]
        for i in range(3, row_bytes):
            raw.append((row[i] - row[i - 3]) & 0xFF)
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return c

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "wb") as f:
        f.write(png)
    print("wrote %s (%d bytes, %dx%d)" % (OUT_PATH, len(png), W, H))


if __name__ == "__main__":
    main()
