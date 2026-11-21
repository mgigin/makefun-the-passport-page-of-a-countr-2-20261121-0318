#!/usr/bin/env python3
"""Invented passport spread for the Republic of Veldor.

Renders one open passport spread (data page + visas page) to
/output/entry.png using only the Python standard library.
Rendered at 2x and downsampled for anti-aliased, photographic edges.
Deterministic: fixed seed, no network, no clock.
"""
import math
import os
import random
import struct
import zlib

SS = 2                      # supersampling factor
W, H = 1024, 1024           # final image size
CW, CH = W * SS, H * SS     # canvas size
RNG = random.Random(20261121)

# ---------------------------------------------------------------- PNG output
def _chunk(tag, data):
    c = struct.pack(">I", len(data)) + tag + data
    return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

def write_png(path, w, h, rgb):
    """rgb: bytes of length w*h*3. Sub filter per row, zlib level 9."""
    stride = w * 3
    raw = bytearray()
    for y in range(h):
        row = rgb[y * stride:(y + 1) * stride]
        filt = bytearray(stride)
        for i in range(stride):
            left = row[i - 3] if i >= 3 else 0
            filt[i] = (row[i] - left) & 0xFF
        raw.append(1)
        raw.extend(filt)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
           + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)

# ------------------------------------------------------------------- canvas
class Canvas:
    """RGB canvas addressed in final-image coordinates (scaled by SS)."""
    def __init__(self, w, h, color):
        self.w, self.h = w, h
        self.buf = bytearray(bytes(color) * (w * h))

    def _set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i:i + 3] = bytes(color)

    def _blend(self, x, y, color, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            b = self.buf
            b[i]     = int(b[i]     + (color[0] - b[i])     * a)
            b[i + 1] = int(b[i + 1] + (color[1] - b[i + 1]) * a)
            b[i + 2] = int(b[i + 2] + (color[2] - b[i + 2]) * a)

    # -- public API in final-image coordinates ------------------------------
    def rect(self, x, y, w, h, color):
        x0, y0 = int(x * SS), int(y * SS)
        x1, y1 = int((x + w) * SS), int((y + h) * SS)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.w, x1), min(self.h, y1)
        if x1 <= x0 or y1 <= y0:
            return
        seg = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.buf[i:i + len(seg)] = seg

    def rect_blend(self, x, y, w, h, color, a):
        x0, y0 = int(x * SS), int(y * SS)
        x1, y1 = int((x + w) * SS), int((y + h) * SS)
        for yy in range(max(0, y0), min(self.h, y1)):
            for xx in range(max(0, x0), min(self.w, x1)):
                self._blend(xx, yy, color, a)

    def frame(self, x, y, w, h, color, t=1):
        self.rect(x, y, w, t, color)
        self.rect(x, y + h - t, w, t, color)
        self.rect(x, y, t, h, color)
        self.rect(x + w - t, y, t, h, color)

    def line(self, x0, y0, x1, y1, color, t=1, alpha=None):
        ax, ay = int(x0 * SS), int(y0 * SS)
        bx, by = int(x1 * SS), int(y1 * SS)
        steps = max(abs(bx - ax), abs(by - ay), 1)
        r = max(0, int(t * SS) // 2)
        for s in range(steps + 1):
            cx = ax + (bx - ax) * s // steps
            cy = ay + (by - ay) * s // steps
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if alpha is None:
                        self._set(cx + dx, cy + dy, color)
                    else:
                        self._blend(cx + dx, cy + dy, color, alpha)

    def ellipse(self, cx, cy, rx, ry, color):
        cx, cy, rx, ry = cx * SS, cy * SS, rx * SS, ry * SS
        y0, y1 = int(cy - ry), int(cy + ry)
        for yy in range(max(0, y0), min(self.h, y1 + 1)):
            t = (yy - cy) / ry
            if abs(t) > 1:
                continue
            half = rx * math.sqrt(1 - t * t)
            xa, xb = int(cx - half), int(cx + half)
            xa, xb = max(0, xa), min(self.w, xb)
            if xb > xa:
                seg = bytes(color) * (xb - xa)
                i = (yy * self.w + xa) * 3
                self.buf[i:i + len(seg)] = seg

    def ellipse_blend(self, cx, cy, rx, ry, color, a):
        cx, cy, rx, ry = cx * SS, cy * SS, rx * SS, ry * SS
        y0, y1 = int(cy - ry), int(cy + ry)
        for yy in range(max(0, y0), min(self.h, y1 + 1)):
            t = (yy - cy) / ry
            if abs(t) > 1:
                continue
            half = rx * math.sqrt(1 - t * t)
            for xx in range(max(0, int(cx - half)), min(self.w, int(cx + half))):
                self._blend(xx, yy, color, a)

    def ring(self, cx, cy, rx, ry, color, t=1.2, alpha=None):
        steps = int(max(rx, ry) * SS * 2.2)
        for s in range(steps + 1):
            ang = 2 * math.pi * s / steps
            px = cx + rx * math.cos(ang)
            py = cy + ry * math.sin(ang)
            r = max(0, int(t * SS) // 2)
            ix, iy = int(px * SS), int(py * SS)
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if alpha is None:
                        self._set(ix + dx, iy + dy, color)
                    else:
                        self._blend(ix + dx, iy + dy, color, alpha)

    def poly(self, pts, color):
        """Filled polygon, pts in final-image coordinates."""
        sp = [(x * SS, y * SS) for x, y in pts]
        ys = [p[1] for p in sp]
        y0, y1 = int(min(ys)), int(max(ys))
        n = len(sp)
        for yy in range(max(0, y0), min(self.h, y1 + 1)):
            nodes = []
            for i in range(n):
                xa, ya = sp[i]
                xb, yb = sp[(i + 1) % n]
                if ya == yb:
                    continue
                if (ya <= yy < yb) or (yb <= yy < ya):
                    nodes.append(xa + (yy - ya) * (xb - xa) / (yb - ya))
            nodes.sort()
            for k in range(0, len(nodes) - 1, 2):
                xa, xb = int(nodes[k]), int(nodes[k + 1])
                xa, xb = max(0, xa), min(self.w, xb)
                if xb > xa:
                    seg = bytes(color) * (xb - xa)
                    i = (yy * self.w + xa) * 3
                    self.buf[i:i + len(seg)] = seg

    def clip_rect(self, x, y, w, h):
        return (int(x * SS), int(y * SS), int((x + w) * SS), int((y + h) * SS))

# --------------------------------------------------------------------- font
# 5x7 bitmap font, uppercase + digits + punctuation.
_FONT_SRC = {
"A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
"B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
"C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
"D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
"E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
"F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
"G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
"H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
"I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
"J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
"K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
"L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
"M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
"N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
"O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
"P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
"Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
"R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
"S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
"T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
"U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
"V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
"W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
"X": ("#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#"),
"Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
"Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
"0": (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
"1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", "#####"),
"2": (".###.", "#...#", "....#", "..##.", ".#...", "#....", "#####"),
"3": ("#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."),
"4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
"5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
"6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
"7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
"8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
"9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
",": (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
"/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
"-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
"'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
"(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
":": (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
"<": ("...#.", "..#..", ".#...", "#....", ".#...", "..#..", "...#."),
">": (".#...", "..#..", "...#.", "....#", "...#.", "..#..", ".#..."),
"+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
"*": (".....", ".#.#.", "..#..", "#####", "..#..", ".#.#.", "....."),
"=": (".....", ".....", "#####", ".....", "#####", ".....", "....."),
"%": ("##..#", "##.#.", "...#.", "..#..", ".#...", ".#.##", "#..##"),
"&": (".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"),
"!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
"?": (".###.", "#...#", "....#", "..##.", "..#..", ".....", "..#.."),
" ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
}
FONT = {}
for _ch, _rows in _FONT_SRC.items():
    FONT[_ch] = tuple(tuple(1 if c == "#" else 0 for c in r) for r in _rows)

def text_width(s, scale, spacing=1):
    if not s:
        return 0
    return len(s) * (5 + spacing) * scale - spacing * scale

def draw_text(cv, x, y, s, scale, color, spacing=1, bold=False, alpha=None):
    """Draw text with top-left at (x, y) in final-image coords.
    scale = size of one glyph pixel in final-image pixels."""
    s = s.upper()
    px = max(1, int(round(scale * SS)))
    cx = int(x * SS)
    cy = int(y * SS)
    for ch in s:
        glyph = FONT.get(ch, FONT[" "])
        for gy in range(7):
            row = glyph[gy]
            run = 0
            for gx in range(6):
                on = gx < 5 and row[gx]
                if on:
                    run += 1
                if (not on or gx == 5) and run:
                    x0 = cx + (gx - run) * px
                    y0 = cy + gy * px
                    seg = bytes(color) * (run * px + (px // 2 if bold else 0))
                    for yy in range(y0, y0 + px):
                        if 0 <= yy < cv.h:
                            i = (yy * cv.w + x0) * 3
                            if alpha is None:
                                cv.buf[i:i + len(seg)] = seg
                            else:
                                for xx in range(x0, x0 + len(seg) // 3):
                                    cv._blend(xx, yy, color, alpha)
                    run = 0
        cx += (5 + spacing) * px
    return (cx // SS) - x

def draw_text_centered(cv, cx, y, s, scale, color, spacing=1, bold=False, alpha=None):
    w = text_width(s, scale, spacing)
    draw_text(cv, cx - w / 2, y, s, scale, color, spacing, bold, alpha)

# ------------------------------------------------------------------ helpers
def shade(color, f):
    return tuple(max(0, min(255, int(c * f))) for c in color)

def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def vgrad(cv, x, y, w, h, top, bottom):
    steps = max(1, int(h))
    for i in range(steps):
        cv.rect(x, y + i * h / steps, w, h / steps + 1, mix(top, bottom, i / steps))

def guilloche(cv, x, y, w, h, color, gap=7, amp=2.2, period=46.0, phase=0.0):
    """Fine wavy security lines across a rectangle (solid pale ink)."""
    yy = y
    while yy < y + h:
        steps = int(w)
        for s in range(steps + 1):
            xx = x + s
            off = amp * math.sin((s + phase) * 2 * math.pi / period)
            cv._set(int(xx * SS), int((yy + off) * SS), color)
        yy += gap

def rosette(cv, cx, cy, r, color, petals=9, alpha=0.5):
    """Guilloche rosette: overlapping circles, faint."""
    for k in range(petals):
        ang = 2 * math.pi * k / petals
        ox = cx + r * 0.42 * math.cos(ang)
        oy = cy + r * 0.42 * math.sin(ang)
        cv.ring(ox, oy, r * 0.58, r * 0.58, color, t=0.7, alpha=alpha)

def star(cv, cx, cy, r, color, alpha=None):
    pts = []
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    if alpha is None:
        cv.poly(pts, color)
    else:
        # cheap alpha star: draw filled then blend border
        cv.poly(pts, color)

# ------------------------------------------------------------------ portrait
def draw_portrait(cv, x, y, w, h, ghost=False):
    """Greyscale 'laser-engraved' style portrait: woman with hair pulled
    back into a bun, harbour-pilot uniform. Duotone blue-grey with soft
    photographic shading."""
    # backdrop gradient, lighter at top (studio backdrop)
    top = (208, 213, 218) if not ghost else (218, 220, 218)
    bot = (146, 154, 164) if not ghost else (208, 210, 206)
    vgrad(cv, x, y, w, h, top, bot)
    cx = x + w / 2
    skin = (178, 182, 186) if not ghost else (202, 204, 200)
    skin_hi = (198, 202, 206) if not ghost else (210, 212, 208)
    skin_sh = (120, 127, 136) if not ghost else (186, 188, 182)
    hair = (46, 50, 58) if not ghost else (152, 154, 150)
    hair_hi = (84, 90, 100) if not ghost else (170, 172, 168)
    cloth = (58, 68, 84) if not ghost else (172, 174, 170)
    head_cy = y + h * 0.40
    # hair mass behind head and shoulders (pulled back, bun at crown)
    cv.ellipse(cx, head_cy - h * 0.02, w * 0.255, h * 0.27, hair)
    cv.ellipse(cx, head_cy - h * 0.24, w * 0.10, h * 0.055, hair)  # bun
    cv.ellipse_blend(cx - w * 0.10, head_cy - h * 0.16, w * 0.10, h * 0.10, hair_hi, 0.5)
    # shoulders / uniform jacket
    cv.poly([(x + 4, y + h), (x + 12, y + h * 0.76), (cx - w * 0.21, y + h * 0.67),
             (cx + w * 0.21, y + h * 0.67), (x + w - 12, y + h * 0.76),
             (x + w - 4, y + h)], cloth)
    # shirt V + collar
    cv.poly([(cx - w * 0.115, y + h * 0.68), (cx + w * 0.115, y + h * 0.68),
             (cx, y + h * 0.88)], (200, 204, 208) if not ghost else (207, 209, 205))
    cv.poly([(cx - w * 0.20, y + h * 0.67), (cx - w * 0.115, y + h * 0.68),
             (cx - w * 0.05, y + h * 0.80), (cx - w * 0.16, y + h * 0.78)], shade(cloth, 0.8))
    cv.poly([(cx + w * 0.20, y + h * 0.67), (cx + w * 0.115, y + h * 0.68),
             (cx + w * 0.05, y + h * 0.80), (cx + w * 0.16, y + h * 0.78)], shade(cloth, 0.8))
    if not ghost:
        # small gold anchor pin on left collar
        star(cv, cx - w * 0.13, y + h * 0.74, 3.2, (196, 160, 84))
    # neck with jaw shadow
    cv.rect(cx - w * 0.07, y + h * 0.55, w * 0.14, h * 0.15, skin_sh)
    cv.ellipse_blend(cx, y + h * 0.58, w * 0.09, h * 0.035, shade(skin_sh, 0.8), 0.6)
    # face: narrower ellipse, light from the left
    cv.ellipse(cx, head_cy, w * 0.185, h * 0.225, skin)
    cv.ellipse_blend(cx - w * 0.07, head_cy - h * 0.02, w * 0.10, h * 0.16, skin_hi, 0.55)
    cv.ellipse_blend(cx + w * 0.11, head_cy + h * 0.04, w * 0.09, h * 0.16, skin_sh, 0.45)
    # hairline: hair covers top of head, swept back with a centre parting
    cv.ellipse(cx, head_cy - h * 0.135, w * 0.20, h * 0.115, hair)
    cv.ellipse_blend(cx - w * 0.08, head_cy - h * 0.16, w * 0.09, h * 0.06, hair_hi, 0.5)
    cv.ellipse_blend(cx + w * 0.09, head_cy - h * 0.15, w * 0.08, h * 0.06, hair_hi, 0.35)
    cv.line(cx, head_cy - h * 0.245, cx, head_cy - h * 0.10, shade(hair, 0.55), 0.9)
    # soft jaw shadow under the chin
    cv.ellipse_blend(cx, head_cy + h * 0.225, w * 0.10, h * 0.022, skin_sh, 0.45)
    # ears
    cv.ellipse(cx - w * 0.185, head_cy + h * 0.03, w * 0.026, h * 0.042, skin_sh)
    cv.ellipse(cx + w * 0.185, head_cy + h * 0.03, w * 0.026, h * 0.042, skin_sh)
    if not ghost:
        feat = (62, 67, 76)
        soft = (92, 99, 110)
        # eye sockets (soft shadow)
        cv.ellipse_blend(cx - w * 0.075, head_cy + h * 0.015, w * 0.045, h * 0.028, skin_sh, 0.35)
        cv.ellipse_blend(cx + w * 0.075, head_cy + h * 0.015, w * 0.045, h * 0.028, skin_sh, 0.35)
        # brows
        cv.line(cx - w * 0.115, head_cy - h * 0.028, cx - w * 0.040, head_cy - h * 0.040, feat, 1.3)
        cv.line(cx + w * 0.040, head_cy - h * 0.040, cx + w * 0.115, head_cy - h * 0.028, feat, 1.3)
        # eyes: almond + iris
        for sgn in (-1, 1):
            ex = cx + sgn * w * 0.075
            cv.ellipse(ex, head_cy + h * 0.018, w * 0.032, h * 0.014, (206, 209, 212))
            cv.ellipse(ex, head_cy + h * 0.018, w * 0.016, h * 0.012, feat)
            cv.line(ex - w * 0.032, head_cy + h * 0.010, ex + w * 0.032, head_cy + h * 0.010, feat, 0.9)
        # nose: bridge highlight + shadow + nostrils
        cv.line(cx - w * 0.004, head_cy + h * 0.03, cx - w * 0.002, head_cy + h * 0.11, skin_hi, 1.0, alpha=0.6)
        cv.line(cx + w * 0.016, head_cy + h * 0.03, cx + w * 0.010, head_cy + h * 0.11, soft, 1.0, alpha=0.55)
        cv.ellipse_blend(cx, head_cy + h * 0.122, w * 0.034, h * 0.011, soft, 0.6)
        # lips
        cv.line(cx - w * 0.052, head_cy + h * 0.182, cx + w * 0.052, head_cy + h * 0.182, feat, 1.4)
        cv.ellipse_blend(cx, head_cy + h * 0.194, w * 0.040, h * 0.010, soft, 0.5)
        # cheek + chin shading
        cv.ellipse_blend(cx - w * 0.10, head_cy + h * 0.10, w * 0.045, h * 0.045, skin_sh, 0.28)
        cv.ellipse_blend(cx + w * 0.11, head_cy + h * 0.10, w * 0.045, h * 0.045, skin_sh, 0.32)
        cv.ellipse_blend(cx, head_cy + h * 0.215, w * 0.05, h * 0.018, skin_sh, 0.30)
    # engraved line texture
    step = 3
    yy = y + 2
    while yy < y + h - 1:
        cv.rect_blend(x + 1, yy, w - 2, 0.7, (88, 96, 106), 0.15)
        yy += step
    # photo vignette corners
    cv.ellipse_blend(x + 4, y + 4, w * 0.18, h * 0.10, (90, 98, 108), 0.18)
    cv.ellipse_blend(x + w - 4, y + 4, w * 0.18, h * 0.10, (90, 98, 108), 0.18)
    if not ghost:
        cv.frame(x, y, w, h, (118, 126, 136), 1.2)

# -------------------------------------------------------------------- emblem
def draw_emblem(cv, cx, cy, r, gold=(196, 160, 84), navy=(29, 53, 87)):
    """Coat of arms: shield with anchor over waves, star above, rope ring."""
    cv.ring(cx, cy, r, r, gold, t=1.6)
    cv.ring(cx, cy, r * 0.88, r * 0.88, gold, t=0.8)
    # shield
    sw, sh = r * 0.92, r * 1.05
    pts = [(cx - sw / 2, cy - sh * 0.34), (cx + sw / 2, cy - sh * 0.34),
           (cx + sw / 2, cy + sh * 0.10), (cx, cy + sh * 0.52),
           (cx - sw / 2, cy + sh * 0.10)]
    cv.poly(pts, navy)
    cv.poly([(px, py) for px, py in pts], navy)
    # shield inner border
    pts2 = [(cx - sw * 0.40, cy - sh * 0.26), (cx + sw * 0.40, cy - sh * 0.26),
            (cx + sw * 0.40, cy + sh * 0.08), (cx, cy + sh * 0.42),
            (cx - sw * 0.40, cy + sh * 0.08)]
    for i in range(len(pts2)):
        a = pts2[i]; b = pts2[(i + 1) % len(pts2)]
        cv.line(a[0], a[1], b[0], b[1], gold, 0.9)
    # anchor
    ax, ay = cx, cy - sh * 0.02
    cv.ring(ax, ay - sh * 0.20, r * 0.075, r * 0.075, gold, t=1.1)
    cv.line(ax, ay - sh * 0.13, ax, ay + sh * 0.24, gold, 1.6)
    cv.line(ax - r * 0.16, ay - sh * 0.05, ax + r * 0.16, ay - sh * 0.05, gold, 1.3)
    cv.line(ax, ay + sh * 0.24, ax - r * 0.20, ay + sh * 0.12, gold, 1.4)
    cv.line(ax, ay + sh * 0.24, ax + r * 0.20, ay + sh * 0.12, gold, 1.4)
    cv.line(ax - r * 0.20, ay + sh * 0.12, ax - r * 0.24, ay + sh * 0.20, gold, 1.2)
    cv.line(ax + r * 0.20, ay + sh * 0.12, ax + r * 0.24, ay + sh * 0.20, gold, 1.2)
    # waves under anchor
    for k in range(2):
        wy = cy + sh * (0.30 + k * 0.07)
        for s in range(int(sw * 0.7)):
            xx = cx - sw * 0.35 + s
            off = 1.6 * math.sin(s * 2 * math.pi / (sw * 0.35))
            cv._set(int(xx * SS), int((wy + off) * SS), gold)
    # star above shield
    star(cv, cx, cy - sh * 0.52, r * 0.13, gold)

# ------------------------------------------------------------- signature ink
def signature(cv, x, y, w, color=(38, 44, 66)):
    """Flowing signature scribble: a few bezier-ish strokes."""
    pts = []
    n = 90
    for i in range(n + 1):
        t = i / n
        px = x + w * t
        py = y + 7 * math.sin(t * 9.0) * (1 - t * 0.4) + 4 * math.sin(t * 23.0)
        pts.append((px, py))
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], color, 1.1)
    # flourish underline
    cv.line(x + 4, y + 13, x + w * 0.85, y + 10, color, 0.9)
    # capital loop at start
    cv.ring(x + 8, y - 2, 6, 9, color, t=1.0)

# ------------------------------------------------------------------ MRZ bits
def _mrz_val(ch):
    if ch == "<":
        return 0
    if ch.isdigit():
        return int(ch)
    return ord(ch) - 55  # A=10 .. Z=35

def _mrz_check(s):
    weights = (7, 3, 1)
    total = sum(_mrz_val(c) * weights[i % 3] for i, c in enumerate(s))
    return str(total % 10)

def build_mrz():
    line1 = "P<VLDKOVAC<<MIRA"
    line1 = line1 + "<" * (44 - len(line1))
    doc = "VD4829137"
    dob = "910704"
    exp = "330311"
    personal = "VLD1991PS0042"
    personal = personal + "<" * (14 - len(personal))
    line2 = (doc + _mrz_check(doc) + "VLD" + dob + _mrz_check(dob) + "F"
             + exp + _mrz_check(exp) + personal + _mrz_check(personal))
    composite_src = line2[0:10] + line2[13:20] + line2[21:43]
    line2 = line2 + _mrz_check(composite_src)
    assert len(line1) == 44 and len(line2) == 44, (len(line1), len(line2))
    return line1, line2

# ---------------------------------------------------------------- data page
PAPER = (244, 241, 232)
INK = (34, 44, 62)
NAVY = (29, 53, 87)
GOLD = (196, 160, 84)
LABEL = (96, 110, 128)
GUIL = (198, 210, 220)
GUIL2 = (226, 206, 204)

def field(cv, x, y, label, value, vscale=1.55, lscale=1.05):
    draw_text(cv, x, y, label, lscale, LABEL, spacing=1)
    draw_text(cv, x, y + 11, value, vscale, INK, spacing=1, bold=True)

def data_page(cv, px, py, pw, ph):
    # paper + security print
    cv.rect(px, py, pw, ph, PAPER)
    guilloche(cv, px + 6, py + 6, pw - 12, ph - 12, GUIL, gap=8, amp=2.0)
    guilloche(cv, px + 6, py + 10, pw - 12, ph - 12, GUIL2, gap=13, amp=3.0,
              period=64.0, phase=20.0)
    rosette(cv, px + pw - 52, py + 120, 30, (170, 188, 204), alpha=0.35)
    # header band
    cv.rect(px, py, pw, 84, NAVY)
    cv.rect(px, py + 84, pw, 3, GOLD)
    draw_emblem(cv, px + 52, py + 44, 34)
    draw_text(cv, px + 100, py + 16, "REPUBLIC OF VELDOR", 2.6, GOLD, spacing=2, bold=True)
    draw_text(cv, px + 101, py + 44, "VELDORSKI RIKE", 1.15, (168, 186, 208), spacing=2)
    draw_text(cv, px + 100, py + 60, "PASSPORT", 1.7, (238, 240, 244), spacing=6, bold=True)
    draw_text(cv, px + pw - 118, py + 62, "PASS", 1.1, (168, 186, 208), spacing=3)
    # microtext line under header
    micro = "VELDOR*VELDOR*VELDOR*VELDOR*VELDOR*VELDOR*VELDOR*VELDOR"
    draw_text(cv, px + 10, py + 92, micro, 0.55, (150, 164, 182), spacing=0)
    # photo
    phx, phy, phw, phh = px + 22, py + 112, 138, 184
    draw_portrait(cv, phx, phy, phw, phh)
    # hologram seal overlapping photo corner
    hx, hy = phx + phw - 6, phy + phh - 8
    for rr, col in ((30, (140, 210, 220)), (24, (232, 190, 120)),
                    (18, (220, 160, 200)), (12, (150, 220, 190))):
        cv.ring(hx, hy, rr, rr, col, t=1.6, alpha=0.55)
    star(cv, hx, hy, 7, (240, 240, 230))
    cv.ring(hx, hy, 30, 30, (120, 140, 150), t=0.8, alpha=0.6)
    # ghost portrait (faint second image, frameless, right of photo area)
    draw_portrait(cv, px + pw - 86, py + 116, 62, 84, ghost=True)
    cv.rect_blend(px + pw - 86, py + 116, 62, 84, PAPER, 0.62)
    # top row: type / code / number (short labels, wide spacing)
    tx = px + 176
    field(cv, tx, py + 112, "TYPE", "P")
    field(cv, tx + 58, py + 112, "CODE", "VLD")
    field(cv, tx + 122, py + 112, "PASSPORT NO", "VD4829137")
    # main fields
    fx = px + 176
    field(cv, fx, py + 152, "SURNAME / AFTIRNAM", "KOVAC")
    field(cv, fx, py + 186, "GIVEN NAMES / FORNAM", "MIRA")
    field(cv, fx, py + 220, "NATIONALITY / RIKSKAP", "VELDORIAN")
    field(cv, fx, py + 254, "DATE OF BIRTH / FODDAG", "04 JUL 1991")
    field(cv, fx + 168, py + 254, "SEX / KYN", "F")
    field(cv, fx, py + 288, "PLACE OF BIRTH / FODSTAD", "PORT SABLE")
    field(cv, fx, py + 322, "DATE OF ISSUE / UTGAFDAG", "12 MAR 2023")
    field(cv, fx, py + 356, "DATE OF EXPIRY / GILDISDAG", "11 MAR 2033")
    field(cv, fx, py + 390, "AUTHORITY / STJORN", "PORT SABLE PASSPORT OFFICE", vscale=1.25)
    # signature under photo
    draw_text(cv, phx, phy + phh + 16, "SIGNATURE OF HOLDER", 0.95, LABEL)
    signature(cv, phx + 4, phy + phh + 38, 120)
    cv.line(phx, phy + phh + 56, phx + phw, phy + phh + 56, (150, 160, 175), 0.8)
    # endorsements box
    ex, ey, ew, eh = px + 22, py + 470, pw - 44, 96
    cv.frame(ex, ey, ew, eh, (140, 154, 172), 1)
    draw_text(cv, ex + 10, ey + 8, "ENDORSEMENTS / ATHUGASEMDIR", 1.0, LABEL)
    draw_text(cv, ex + 10, ey + 26, "VALID FOR ALL COUNTRIES EXCEPT", 1.25, INK, bold=True)
    draw_text(cv, ex + 10, ey + 42, "THE TIDEWATER FREE PORTS", 1.25, INK, bold=True)
    draw_text(cv, ex + 10, ey + 62, "HOLDER IS A REGISTERED HARBOUR", 1.25, INK, bold=True)
    draw_text(cv, ex + 10, ey + 78, "PILOT - CLASS II", 1.25, INK, bold=True)
    # fee stamp, slightly rotated look via offset double print
    fsx, fsy = ex + ew - 128, ey + 30
    for dx, dy, a in ((1, 1, 0.25), (0, 0, 0.8)):
        cv.frame(fsx + dx, fsy + dy, 116, 40, (176, 84, 84), 1)
        draw_text(cv, fsx + 8 + dx, fsy + 6 + dy, "FEE PAID", 1.2, (176, 84, 84),
                  alpha=a if a < 1 else None)
        draw_text(cv, fsx + 8 + dx, fsy + 22 + dy, "40 MARKS", 1.2, (176, 84, 84),
                  alpha=a if a < 1 else None)
    # perforated passport number down the left edge (dot-matrix digits)
    perf = "4829137"
    py0 = py + 620
    for i, ch in enumerate(perf):
        glyph = FONT[ch]
        for gy in range(7):
            for gx in range(5):
                if glyph[gy][gx]:
                    cv.ellipse(px + 16 + gx * 3.4, py0 + i * 30 + gy * 3.4,
                               1.1, 1.1, (120, 126, 134))
    # request text (small print, bilingual)
    rq = ["THE MINISTER FOR FOREIGN AFFAIRS OF THE REPUBLIC OF VELDOR",
          "REQUESTS ALL WHOM IT MAY CONCERN TO ALLOW THE HOLDER TO",
          "PASS FREELY WITHOUT LET OR HINDRANCE AND TO AFFORD THE",
          "HOLDER SUCH ASSISTANCE AND PROTECTION AS MAY BE NECESSARY."]
    for i, ln in enumerate(rq):
        draw_text(cv, px + 44, py + 590 + i * 13, ln, 0.95, (110, 122, 140))
    # large faint watermark emblem filling the lower page (as on real pages)
    draw_emblem(cv, px + pw / 2 + 30, py + 712, 86,
                gold=(224, 216, 198), navy=(230, 224, 206))
    rosette(cv, px + 96, py + 712, 44, (196, 208, 220), alpha=0.30)
    # MRZ band
    mrz_y = py + ph - 92
    cv.rect(px + 8, mrz_y, pw - 16, 80, (250, 249, 244))
    cv.frame(px + 8, mrz_y, pw - 16, 80, (170, 178, 188), 0.8)
    l1, l2 = build_mrz()
    draw_text(cv, px + 20, mrz_y + 12, l1, 1.72, (30, 34, 40), spacing=1)
    draw_text(cv, px + 20, mrz_y + 44, l2, 1.72, (30, 34, 40), spacing=1)
    # page number
    draw_text(cv, px + pw - 26, py + ph - 22, "2", 1.3, LABEL)

# ------------------------------------------------------------------- stamps
class StampCanvas:
    """Small RGBA-ish offscreen for one stamp, blitted rotated with alpha."""
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rgb = bytearray(w * h * 3)
        self.alpha = bytearray(w * h)

    def _put(self, x, y, color, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = y * self.w + x
            if a >= self.alpha[i]:
                self.alpha[i] = a
                j = i * 3
                self.rgb[j:j + 3] = bytes(color)

    def rect(self, x, y, w, h, color, a=200):
        for yy in range(max(0, y), min(self.h, y + h)):
            for xx in range(max(0, x), min(self.w, x + w)):
                self._put(xx, yy, color, a)

    def frame(self, x, y, w, h, color, t=2, a=200):
        self.rect(x, y, w, t, color, a)
        self.rect(x, y + h - t, w, t, color, a)
        self.rect(x, y, t, h, color, a)
        self.rect(x + w - t, y, t, h, color, a)

    def ring(self, cx, cy, r, color, t=2, a=200):
        steps = int(r * 6)
        for s in range(steps + 1):
            ang = 2 * math.pi * s / steps
            for rr in range(r - t, r + 1):
                self._put(int(cx + rr * math.cos(ang)), int(cy + rr * math.sin(ang)),
                          color, a)

    def text(self, x, y, s, scale, color, a=200, spacing=1):
        s = s.upper()
        cx = x
        for ch in s:
            glyph = FONT.get(ch, FONT[" "])
            for gy in range(7):
                for gx in range(5):
                    if glyph[gy][gx]:
                        self.rect(cx + gx * scale, y + gy * scale, scale, scale,
                                  color, a)
            cx += (5 + spacing) * scale
        return cx - x

    def text_centered(self, cx, y, s, scale, color, a=200, spacing=1):
        w = len(s) * (5 + spacing) * scale - spacing * scale
        self.text(cx - w // 2, y, s, scale, color, a, spacing)

    def blit_rotated(self, cv, cx, cy, angle_deg, strength=0.85):
        """Blit onto main canvas centered at (cx, cy) final-image coords."""
        ang = math.radians(angle_deg)
        ca, sa = math.cos(ang), math.sin(ang)
        hw, hh = self.w / 2, self.h / 2
        # destination bbox in canvas pixels
        ext = int((abs(hw * ca) + abs(hh * sa)) * SS) + 2
        exty = int((abs(hw * sa) + abs(hh * ca)) * SS) + 2
        dcx, dcy = int(cx * SS), int(cy * SS)
        for dy in range(-exty, exty + 1):
            for dx in range(-ext, ext + 1):
                # inverse-rotate into stamp space (stamp px = final px)
                sx = (dx * ca + dy * sa) / SS + hw
                sy = (-dx * sa + dy * ca) / SS + hh
                ix, iy = int(sx), int(sy)
                if 0 <= ix < self.w and 0 <= iy < self.h:
                    a = self.alpha[iy * self.w + ix]
                    if a:
                        j = (iy * self.w + ix) * 3
                        col = (self.rgb[j], self.rgb[j + 1], self.rgb[j + 2])
                        cv._blend(dcx + dx, dcy + dy, col, a / 255.0 * strength)

def make_stamp(country, kind, date, port, color, shape="rect"):
    if shape == "round":
        sc = StampCanvas(150, 150)
        sc.ring(75, 75, 70, color, t=3, a=190)
        sc.ring(75, 75, 56, color, t=2, a=190)
        sc.text_centered(75, 40, country, 1, color, a=200)
        sc.text_centered(75, 58, kind, 2, color, a=210)
        sc.text_centered(75, 78, date, 2, color, a=220)
        sc.text_centered(75, 100, port, 1, color, a=190)
        return sc
    sc = StampCanvas(210, 104)
    sc.frame(2, 2, 206, 100, color, t=3, a=190)
    sc.frame(8, 8, 194, 88, color, t=1, a=170)
    sc.text_centered(105, 16, country, 2, color, a=200)
    sc.text_centered(105, 38, kind, 3, color, a=215)
    sc.text_centered(105, 66, date, 2, color, a=220)
    sc.text_centered(105, 86, port, 1, color, a=185)
    return sc

# --------------------------------------------------------------- visas page
def visa_sticker(cv, x, y, w, h):
    vgrad(cv, x, y, w, h, (206, 228, 216), (176, 206, 196))
    guilloche(cv, x + 4, y + 4, w - 8, h - 8, (160, 196, 182), gap=6, amp=1.6)
    cv.frame(x, y, w, h, (90, 130, 116), 1.2)
    cv.rect(x, y, w, 26, (64, 110, 96))
    draw_text(cv, x + 10, y + 6, "MERIDIAN ISLES", 1.5, (240, 246, 242), spacing=2, bold=True)
    draw_text(cv, x + w - 74, y + 7, "VISA", 1.5, (240, 246, 242), spacing=3, bold=True)
    # photo thumbnail
    draw_portrait(cv, x + 12, y + 38, 74, 98)
    fx = x + 100
    rows = [("TYPE", "MULTIPLE"), ("VALID FROM", "01 NOV 2024"),
            ("UNTIL", "31 OCT 2025"), ("DURATION", "90 DAYS"),
            ("ISSUED AT", "PORT SABLE"), ("VISA NO", "MI-8841207")]
    for i, (k, v) in enumerate(rows):
        draw_text(cv, fx, y + 40 + i * 21, k, 0.95, (70, 96, 86))
        draw_text(cv, fx + 108, y + 40 + i * 21, v, 1.15, (30, 52, 44), bold=True)
    draw_text(cv, x + 12, y + h - 44, "KOVAC MIRA", 1.3, (30, 52, 44), bold=True)
    draw_text(cv, x + 12, y + h - 26, "VD4829137", 1.1, (30, 52, 44))
    # sticker MRZ line
    draw_text(cv, x + 100, y + h - 26, "V<MIRKOVAC<<MIRA<<<<<<<<<", 1.05, (44, 66, 58))
    # small round seal on sticker
    cv.ring(x + w - 44, y + h - 40, 26, 26, (64, 110, 96), t=1.4, alpha=0.7)
    star(cv, x + w - 44, y + h - 40, 9, (64, 110, 96))

def visas_page(cv, px, py, pw, ph):
    cv.rect(px, py, pw, ph, PAPER)
    guilloche(cv, px + 6, py + 6, pw - 12, ph - 12, GUIL, gap=8, amp=2.0, phase=30.0)
    guilloche(cv, px + 6, py + 10, pw - 12, ph - 12, GUIL2, gap=13, amp=3.0,
              period=64.0, phase=55.0)
    # faint watermark emblem center
    draw_emblem(cv, px + pw / 2, py + ph * 0.58, 120,
                gold=(222, 214, 196), navy=(228, 222, 204))
    draw_text(cv, px + 22, py + 18, "VISAS", 1.8, LABEL, spacing=6, bold=True)
    draw_text(cv, px + 23, py + 38, "VISUR", 1.0, (150, 162, 178), spacing=3)
    cv.line(px + 22, py + 56, px + pw - 22, py + 56, (170, 180, 194), 0.9)
    # visa sticker
    visa_sticker(cv, px + 22, py + 70, pw - 44, 196)
    # stamps: chronological, alternating arrival/departure, all after
    # the 12 MAR 2023 issue date.
    blue = (44, 74, 150)
    green = (36, 110, 84)
    red = (158, 52, 52)
    stamps = [
        (make_stamp("KARST REPUBLIC", "ARRIVAL", "18 JUN 2023", "KESTREL PORT", blue),
         px + 128, py + 340, -5, 0.88),
        (make_stamp("KARST REPUBLIC", "DEPARTURE", "02 JUL 2023", "KESTREL PORT", blue),
         px + 330, py + 352, 4, 0.82),
        (make_stamp("MERIDIAN ISLES", "ARRIVAL", "09 NOV 2024", "PORT AZURE", green, "round"),
         px + 150, py + 486, 7, 0.85),
        (make_stamp("MERIDIAN ISLES", "DEPARTURE", "21 NOV 2024", "PORT AZURE", green),
         px + 340, py + 496, -3, 0.80),
        (make_stamp("SOLMARIA", "ARRIVAL", "03 MAY 2025", "CAPE SOL", red),
         px + 132, py + 628, 5, 0.86),
        (make_stamp("SOLMARIA", "DEPARTURE", "17 MAY 2025", "CAPE SOL", red),
         px + 336, py + 640, -6, 0.79),
    ]
    for sc, cx, cy, ang, strength in stamps:
        sc.blit_rotated(cv, cx, cy, ang, strength)
    # pencilled margin note
    draw_text(cv, px + 26, py + ph - 120, "PILOT LICENCE RENEWED", 0.95, (120, 126, 130))
    draw_text(cv, px + 26, py + ph - 104, "PORT SABLE 2024", 0.95, (120, 126, 130))
    draw_text(cv, px + pw - 26, py + ph - 22, "3", 1.3, LABEL)

# --------------------------------------------------------------- downsample
def downsample(cv):
    """2x2 box downsample to 1024x1024 with fold shadow + vignette."""
    src = cv.buf
    sw = cv.w
    out = bytearray(W * H * 3)
    fold_x = W // 2
    for oy in range(H):
        sy = oy * SS
        row0 = sy * sw * 3
        row1 = (sy + 1) * sw * 3
        orow = oy * W * 3
        vy = 1.0 - 0.10 * abs(oy - H / 2) / (H / 2)
        for ox in range(W):
            sx = ox * SS * 3
            i0 = row0 + sx
            i1 = row1 + sx
            # fold shadow: darken near center spine, slight ridge highlight
            d = abs(ox - fold_x)
            f = vy
            if d < 26:
                f *= 0.78 + 0.22 * (d / 26)
            elif d < 34:
                f *= 1.03
            # edge curl shading
            if ox < 46:
                f *= 0.90 + 0.10 * (ox / 46)
            elif ox > W - 46:
                f *= 0.90 + 0.10 * ((W - ox) / 46)
            o = orow + ox * 3
            out[o]     = int((src[i0] + src[i0 + 3] + src[i1] + src[i1 + 3]) * 0.25 * f)
            out[o + 1] = int((src[i0 + 1] + src[i0 + 4] + src[i1 + 1] + src[i1 + 4]) * 0.25 * f)
            out[o + 2] = int((src[i0 + 2] + src[i0 + 5] + src[i1 + 2] + src[i1 + 5]) * 0.25 * f)
    # paper grain: sparse speckles + fibres (deterministic)
    for _ in range(9000):
        x = RNG.randrange(W)
        y = RNG.randrange(H)
        i = (y * W + x) * 3
        d = RNG.randint(-10, 10)
        for c in range(3):
            v = out[i + c] + d
            out[i + c] = 0 if v < 0 else (255 if v > 255 else v)
    for _ in range(2600):
        x = RNG.randrange(W - 2)
        y = RNG.randrange(H)
        i = (y * W + x) * 3
        d = RNG.randint(-16, -6)
        for k in range(2):
            for c in range(3):
                v = out[i + k * 3 + c] + d
                out[i + k * 3 + c] = 0 if v < 0 else (255 if v > 255 else v)
    return bytes(out)

# --------------------------------------------------------------------- main
def main():
    cv = Canvas(CW, CH, (46, 58, 66))
    # backdrop: dark desk with soft radial light
    for yy in range(0, H, 4):
        t = yy / H
        cv.rect(0, yy, W, 4, mix((58, 72, 82), (38, 48, 56), t))
    # passport cover edges peeking at sides
    cv.rect(30, 62, 964, 900, (24, 40, 62))
    cv.rect(30, 62, 964, 6, (196, 160, 84))
    # pages
    px, py, pw, ph = 40, 70, 472, 884
    data_page(cv, px, py, pw, ph)
    visas_page(cv, px + pw, py, pw, ph)
    # center spine shadow line (drawn soft; downsample adds gradient too)
    for i in range(10):
        cv.rect_blend(px + pw - 5 + i, py, 1, ph, (60, 58, 50), 0.10)
    img = downsample(cv)
    os.makedirs("/output", exist_ok=True)
    write_png("/output/entry.png", W, H, img)

if __name__ == "__main__":
    main()
