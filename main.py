#!/usr/bin/env python3
"""Macro honeycomb: the picture that tastes of one ingredient (honey).

Stdlib-only procedural renderer. Renders a deterministic 1024x1024 PNG
of a golden honeycomb macro: organic irregular wax cells filled with
glossy honey, a thick honey drip with a droplet, and a pooled honey gloss
at the base. One ingredient, one picture.
Writes $MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).
"""
import math
import os
import struct
import zlib

W = 1024
H = 1024
HEX = 68.0
INV_HEX = 1.0 / HEX
SQ3 = 1.7320508075688772
SQ3_3 = SQ3 / 3.0
THIRD = 1.0 / 3.0
TWO_THIRDS = 2.0 / 3.0


def _h01(a, b):
    h = (a * 374761393 + b * 668265263) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFFFF) / 16777216.0


def _chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def _write_png(path, w, h, rgb):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += _chunk(b"IHDR", ihdr)
    data += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)


def render():
    sq3 = SQ3
    sq3_3 = SQ3_3
    third = THIRD
    two_thirds = TWO_THIRDS
    inv_hex = INV_HEX
    hexs = HEX
    h01 = _h01
    # organic warp of the comb (precomputed per row / column)
    row_dx = [5.0 * math.sin(y * 0.011 + 0.7) + 3.0 * math.sin(y * 0.023 + 2.1)
              for y in range(H)]
    col_dy = [5.0 * math.sin(x * 0.009 + 1.3) + 3.0 * math.sin(x * 0.027 + 0.4)
              for x in range(W)]
    # wavy top edge of the honey pool at the base
    pool_top = [800.0 + 18.0 * math.sin(x * 0.008) + 10.0 * math.sin(x * 0.021 + 2.0)
                for x in range(W)]
    # honey strand centre (wobbles as it falls)
    strand_cx = [512.0 + 14.0 * math.sin(y * 0.011) + 6.0 * math.sin(y * 0.027 + 1.0)
                 for y in range(H)]
    dropx = strand_cx[430]
    buf = bytearray(W * H * 3)
    idx = 0
    for y in range(H):
        dxr = row_dx[y]
        sx = strand_cx[y]
        in_pool_row = y > 770
        top_light = 1.0 + 0.10 * (1.0 - y / 1024.0)
        for x in range(W):
            # ---- honeycomb cell (warped coords) ----
            xd = x + dxr
            yd = y + col_dy[x]
            q = (sq3_3 * xd - third * yd) * inv_hex
            r_ = two_thirds * yd * inv_hex
            cx_ = q
            cz_ = r_
            cy_ = -cx_ - cz_
            rx = round(cx_)
            ry = round(cy_)
            rz = round(cz_)
            ddx = abs(rx - cx_)
            ddy = abs(ry - cy_)
            ddz = abs(rz - cz_)
            if ddx > ddy and ddx > ddz:
                rx = -ry - rz
            elif ddy > ddz:
                ry = -rx - rz
            else:
                rz = -rx - ry
            ccx = hexs * sq3 * (rx + rz * 0.5)
            ccy = hexs * 1.5 * rz
            lx = xd - ccx
            ly = yd - ccy
            u = (sq3_3 * lx - third * ly) * inv_hex
            v = two_thirds * ly * inv_hex
            w_ = -u - v
            au = abs(u)
            av = abs(v)
            aw = abs(w_)
            d = au if au >= av else av
            if aw > d:
                d = aw
            h1 = h01(rx, rz)
            h2 = h01(rx + 7919, rz + 104729)
            wall_t = 0.74 + h2 * 0.08
            tint = 0.92 + h1 * 0.16
            # honey interior: glossy amber, brighter at the dome centre
            depth = d / wall_t
            if depth > 1.0:
                depth = 1.0
            lg = 1.0 + (lx * -0.35 + ly * -0.55) / hexs
            if lg < 0.55:
                lg = 0.55
            elif lg > 1.35:
                lg = 1.35
            br = 1.18 - 0.38 * depth
            hx = lx + 0.32 * hexs
            hy = ly + 0.38 * hexs
            hd2 = (hx * hx + hy * hy) / (hexs * hexs)
            spec = 0.0
            if hd2 < 0.16:
                spec = (1.0 - hd2 / 0.16) * 0.85
            hr_ = 205.0 * br * lg * tint + spec * 95.0
            hg_ = 132.0 * br * lg * tint + spec * 62.0
            hb_ = 22.0 * br * lg * tint + spec * 14.0
            # wax wall: pale creamy gold, light from upper-left
            wl = 1.0 + (lx * -0.30 + ly * -0.50) / hexs
            if wl < 0.70:
                wl = 0.70
            elif wl > 1.20:
                wl = 1.20
            rim = 1.0
            if d > 0.93:
                rim = 1.0 - (d - 0.93) / 0.07 * 0.25
            wt = 0.94 + h1 * 0.12
            wr_ = 243.0 * wl * rim * wt
            wg_ = 212.0 * wl * rim * wt
            wb_ = 136.0 * wl * rim * wt
            if d < wall_t - 0.02:
                rr = hr_
                gg = hg_
                bb = hb_
            elif d > wall_t + 0.02:
                rr = wr_
                gg = wg_
                bb = wb_
            else:
                t = (d - wall_t + 0.02) / 0.04
                t = t * t * (3.0 - 2.0 * t)
                rr = hr_ + (wr_ - hr_) * t
                gg = hg_ + (wg_ - hg_) * t
                bb = hb_ + (wb_ - hb_) * t
            # ---- honey pool at the base ----
            if in_pool_row and y > pool_top[x]:
                sw = (math.sin(x * 0.03 + y * 0.02 + 1.0) * 0.08
                      + math.sin((x + y) * 0.015) * 0.05)
                ex = (x - 620.0) / 180.0
                ey = (y - 905.0) / 95.0
                e2 = ex * ex + ey * ey
                ps = 0.0
                if e2 < 1.0:
                    ps = (1.0 - e2) * 0.85
                rr = 165.0 * (1.0 + sw) + ps * 95.0
                gg = 94.0 * (1.0 + sw) + ps * 62.0
                bb = 10.0 * (1.0 + sw) + ps * 15.0
                if y < pool_top[x] + 3.0:
                    rr += 45.0
                    gg += 30.0
                    bb += 8.0
            # ---- drip strand + droplet ----
            if y < 470:
                if y < 430:
                    sdx = x - sx
                    if -13.0 < sdx < 13.0:
                        hlx = x - (sx - 6.0)
                        hsp = 0.0
                        if -6.0 < hlx < 6.0:
                            hsp = (1.0 - (hlx * hlx) / 36.0) * 0.8
                        edge = 1.0
                        if abs(sdx) > 10.0:
                            edge = 0.85
                        rr = (206.0 + hsp * 90.0) * edge
                        gg = (131.0 + hsp * 58.0) * edge
                        bb = (21.0 + hsp * 14.0) * edge
                if 400 <= y <= 490:
                    ddx2 = x - dropx
                    ddy2 = y - 445.0
                    dd2 = ddx2 * ddx2 + ddy2 * ddy2
                    if dd2 < 1764.0:
                        sdx = x - (dropx - 14.0)
                        sdy = y - 429.0
                        sd2 = sdx * sdx + sdy * sdy
                        sp = 0.0
                        if sd2 < 196.0:
                            sp = (1.0 - sd2 / 196.0) * 0.95
                        shade = 1.0
                        if y > 462.0:
                            shade = 0.82
                        rr = (212.0 + sp * 95.0) * shade
                        gg = (136.0 + sp * 62.0) * shade
                        bb = (24.0 + sp * 15.0) * shade
                        if dd2 > 1500.0:
                            rr += 30.0
                            gg += 20.0
                            bb += 5.0
            # ---- global light, focus falloff, vignette, grain ----
            rr *= top_light
            gg *= top_light
            bb *= top_light
            fdx = x - 512.0
            fdy = y - 420.0
            f2 = (fdx * fdx + fdy * fdy) / 577600.0
            if f2 > 1.0:
                f2 = 1.0
            blur = f2 * 0.45
            if blur > 0.0:
                rr = rr * (1.0 - blur) + 200.0 * blur
                gg = gg * (1.0 - blur) + 140.0 * blur
                bb = bb * (1.0 - blur) + 42.0 * blur
            nx = (x - 512.0) / 512.0
            ny = (y - 512.0) / 512.0
            r2 = nx * nx + ny * ny
            if r2 > 0.45:
                vig = 1.0 - 0.32 * (r2 - 0.45)
                if vig < 0.55:
                    vig = 0.55
                rr *= vig
                gg *= vig
                bb *= vig
            # (no per-pixel grain: random noise is incompressible and
            # would push the PNG past the 1 MiB cap)
            if rr < 0.0:
                rr = 0.0
            elif rr > 255.0:
                rr = 255.0
            if gg < 0.0:
                gg = 0.0
            elif gg > 255.0:
                gg = 255.0
            if bb < 0.0:
                bb = 0.0
            elif bb > 255.0:
                bb = 255.0
            buf[idx] = int(rr)
            buf[idx + 1] = int(gg)
            buf[idx + 2] = int(bb)
            idx += 3
    return buf


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    rgb = render()
    _write_png(path, W, H, rgb)
    print("wrote %s (%d bytes, %dx%d)" % (path, os.path.getsize(path), W, H))


if __name__ == "__main__":
    main()
