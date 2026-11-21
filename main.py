#!/usr/bin/env python3
"""Republic of Tharun passport spread, rendered from scratch (stdlib only).

A two-page open passport spread for the invented desert Republic of Tharun:
data page with a photorealistic holder portrait (shipped beside this file
as portrait.z, zlib-compressed raw RGB 288x360), bilingual Tharuni/English
field labels, observations box and an ICAO TD3 machine-readable zone with
correct 7-3-1 check digits; visas page with a desert-transit endorsement,
a well-tax fee stamp, eight alternating arrival/departure border stamps in
chronological order and a Velmarra visitor visa. Everything except the
portrait is drawn by this program. Rendered at 2x and box-downsampled.
Deterministic: same output bytes on every run.
"""
import math
import os
import random
import struct
import zlib

W = H = 1024
S = 2
DW, DH = W * S, H * S
HERE = os.path.dirname(os.path.abspath(__file__))

NAVY = (30, 44, 78)
INK = (34, 36, 40)
GREY = (108, 110, 112)
PAPER = (247, 241, 226)
PAPER2 = (241, 234, 216)
GUIL = (226, 216, 188)
RED = (170, 40, 40)
BLUE = (40, 76, 152)
GREEN = (40, 122, 72)
GOLD = (152, 122, 56)
SIG_BLUE = (42, 62, 142)
DARK_BG = (38, 40, 46)

# ------------------------------------------------------------- PNG writer
def _chunk(tag, data):
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def write_png(path, w, h, rgb):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        row = rgb[y * stride:(y + 1) * stride]
        raw.append(1)
        for i in range(stride):
            raw.append((row[i] - (row[i - 3] if i >= 3 else 0)) & 0xFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
           + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


# ----------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, color):
        self.w, self.h = w, h
        self.px = bytearray(bytes(color) * (w * h))

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(c)

    def blend(self, x, y, c, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            ia = 1.0 - a
            self.px[i] = int(self.px[i] * ia + c[0] * a)
            self.px[i + 1] = int(self.px[i + 1] * ia + c[1] * a)
            self.px[i + 2] = int(self.px[i + 2] * ia + c[2] * a)

    def rect(self, x, y, w, h, c):
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + w, self.w), min(y + h, self.h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def rect_blend(self, x, y, w, h, c, a):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.blend(xx, yy, c, a)

    def frame(self, x, y, w, h, c, t=2):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def line(self, x0, y0, x1, y1, c, t=2, a=1.0):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        r = t // 2
        for i in range(n + 1):
            x = int(x0 + (x1 - x0) * i / n)
            y = int(y0 + (y1 - y0) * i / n)
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if a >= 1.0:
                        self.put(x + dx, y + dy, c)
                    else:
                        self.blend(x + dx, y + dy, c, a)

    def circle(self, cx, cy, r, c, t=2, a=1.0):
        steps = max(64, r * 4)
        for i in range(steps + 1):
            ang = 2 * math.pi * i / steps
            x = int(cx + r * math.cos(ang))
            y = int(cy + r * math.sin(ang))
            for dy in range(-(t // 2), t // 2 + 1):
                for dx in range(-(t // 2), t // 2 + 1):
                    if a >= 1.0:
                        self.put(x + dx, y + dy, c)
                    else:
                        self.blend(x + dx, y + dy, c, a)

    def disc(self, cx, cy, r, c, a=1.0):
        for yy in range(cy - r, cy + r + 1):
            dx = int(math.sqrt(max(0, r * r - (yy - cy) ** 2)))
            for xx in range(cx - dx, cx + dx + 1):
                if a >= 1.0:
                    self.put(xx, yy, c)
                else:
                    self.blend(xx, yy, c, a)

    def rounded_frame(self, x, y, w, h, r, c, t=3, a=1.0):
        for xx in range(x + r, x + w - r):
            for k in range(t):
                self.blend(xx, y + k, c, a)
                self.blend(xx, y + h - 1 - k, c, a)
        for yy in range(y + r, y + h - r):
            for k in range(t):
                self.blend(x + k, yy, c, a)
                self.blend(x + w - 1 - k, yy, c, a)
        for (cx, cy, a0) in ((x + r, y + r, 180), (x + w - r - 1, y + r, 270),
                             (x + w - r - 1, y + h - r - 1, 0), (x + r, y + h - r - 1, 90)):
            for i in range(25):
                ang = math.radians(a0 + 90 * i / 24)
                for k in range(t):
                    rr = r - k
                    self.blend(int(cx + rr * math.cos(ang)), int(cy + rr * math.sin(ang)), c, a)

    def blit_scaled(self, src, sw, sh, dx, dy, dw, dh):
        for yy in range(dh):
            sy = yy * sh // dh
            for xx in range(dw):
                sx = xx * sw // dw
                si = (sy * sw + sx) * 3
                self.put(dx + xx, dy + yy, (src[si], src[si + 1], src[si + 2]))


# ------------------------------------------------------------------- font
# 5x7 bitmap glyphs, rows top->bottom, '#' = ink.
F = {
 'A': [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
 'B': ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
 'C': [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
 'D': ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
 'E': ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
 'F': ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
 'G': [".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."],
 'H': ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
 'I': [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
 'J': ["..###", "....#", "....#", "....#", "....#", "#...#", ".###."],
 'K': ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
 'L': ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
 'M': ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
 'N': ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
 'O': [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
 'P': ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
 'Q': [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
 'R': ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
 'S': [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
 'T': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
 'U': ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
 'V': ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
 'W': ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
 'X': ["#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#"],
 'Y': ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
 'Z': ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
 '0': [".###.", "#...#", "#.###", "##..#", "#...#", "#...#", ".###."],
 '1': ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
 '2': [".###.", "#...#", "....#", "..##.", ".#...", "#....", "#####"],
 '3': [".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."],
 '4': ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
 '5': ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
 '6': [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
 '7': ["#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."],
 '8': [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
 '9': [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
 ' ': [".....", ".....", ".....", ".....", ".....", ".....", "....."],
 '.': [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
 ',': [".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."],
 '<': ["...#.", "..#..", ".#...", "#....", ".#...", "..#..", "...#."],
 '-': [".....", ".....", ".....", "#####", ".....", ".....", "....."],
 '/': ["....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."],
 ':': [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
 "'": ["..#..", "..#..", ".#...", ".....", ".....", ".....", "....."],
 '(': ["...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."],
 ')': [".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."],
 '+': [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
 '&': [".##..", "#..#.", "#.#..", ".#...", "#.#.#", "#..#.", ".##.#"],
 '·': [".....", ".....", ".....", ".##..", ".##..", ".....", "....."],
}


def glyph(ch):
    if ch in F:
        return F[ch], False
    if ch.islower() and ch.upper() in F:
        return F[ch.upper()], True
    return F[' '], False


def text_width(s, scale, tracking=1):
    return len(s) * (5 * scale + tracking * scale) - tracking * scale


def draw_text(cv, x, y, s, scale, c, tracking=1, slant=0, a=1.0):
    cx = x
    for ch in s:
        g, lower = glyph(ch)
        hscale = scale
        yoff = 0
        if lower:
            hscale = max(1, scale - 1) if scale > 1 else 1
            yoff = 7 * scale - 7 * hscale
        for ry, row in enumerate(g):
            for rx, bit in enumerate(row):
                if bit == '#':
                    sx = cx + rx * scale + int(slant * (6 - ry))
                    sy = y + yoff + ry * hscale
                    for dy in range(hscale):
                        for dx in range(scale):
                            if a >= 1.0:
                                cv.put(sx + dx, sy + dy, c)
                            else:
                                cv.blend(sx + dx, sy + dy, c, a)
        cx += 5 * scale + tracking * scale
    return cx


def centered(cv, cx, y, s, scale, c, tracking=1, a=1.0):
    draw_text(cv, cx - text_width(s, scale, tracking) // 2, y, s, scale, c, tracking, a=a)


# --------------------------------------------------------------------- MRZ
def _mrz_val(ch):
    if ch.isdigit():
        return int(ch)
    if 'A' <= ch <= 'Z':
        return ord(ch) - 55
    return 0


def _check(s):
    w = (7, 3, 1)
    return str(sum(_mrz_val(ch) * w[i % 3] for i, ch in enumerate(s)) % 10)


def build_mrz():
    line1 = "P<THNMALEK<<IDRIS"
    line1 = line1 + "<" * (44 - len(line1))
    doc = "THN730194"
    dob = "850922"
    exp = "320513"
    personal = "2209845133"
    personal = personal + "<" * (14 - len(personal))
    body = (doc + _check(doc) + "THN" + dob + _check(dob) + "M"
            + exp + _check(exp) + personal + _check(personal))
    composite = _check(body[0:10] + body[13:20] + body[21:28] + body[28:43])
    line2 = body + composite
    assert len(line1) == 44 and len(line2) == 44, (len(line1), len(line2))
    return line1, line2


# ------------------------------------------------------------------ render
def render():
    cv = Canvas(DW, DH, DARK_BG)
    rng = random.Random(20261121)

    # pages
    lp = (24, 24, 980, 2000)    # x, y, w, h (2x space)
    rp = (1044, 24, 980, 2000)
    for (px, py, pw, ph) in (lp, rp):
        cv.rect(px, py, pw, ph, PAPER)
        # guilloche: pale sine waves
        for k in range(26):
            yy = py + 40 + k * 76
            for xx in range(px + 16, px + pw - 16, 4):
                y = yy + int(9 * math.sin((xx - px) / 90.0 + k * 0.7))
                cv.blend(xx, y, GUIL, 0.55)
                cv.blend(xx, y + 2, GUIL, 0.3)
        # paper grain
        for _ in range(2600):
            gx = px + rng.randrange(8, pw - 8)
            gy = py + rng.randrange(8, ph - 8)
            cv.blend(gx, gy, PAPER2, 0.5)
        cv.frame(px, py, pw, ph, NAVY, t=4)
        cv.frame(px + 10, py + 10, pw - 20, ph - 20, NAVY, t=2)

    # centre fold shadow
    for i in range(40):
        a = 0.10 * (1 - i / 40)
        cv.rect_blend(1004 - i, 24, 1, 2000, (90, 84, 70), a)
        cv.rect_blend(1044 + i, 24, 1, 2000, (90, 84, 70), a)

    # -------------------------------------------------------- data page
    px, py, pw, ph = lp
    cx = px + pw // 2

    # perforated number top-right
    draw_text(cv, px + pw - 250, py + 34, "THN730194", 3, GREY)

    # emblem: ring, sun disc with rays, dune arcs
    ex, ey, er = cx, py + 150, 74
    cv.circle(ex, ey, er, NAVY, t=5)
    cv.circle(ex, ey, er - 12, NAVY, t=2)
    cv.disc(ex, ey - 14, 26, NAVY)
    for i in range(12):
        ang = 2 * math.pi * i / 12
        x0 = int(ex + 34 * math.cos(ang)); y0 = int(ey - 14 + 34 * math.sin(ang))
        x1 = int(ex + 50 * math.cos(ang)); y1 = int(ey - 14 + 50 * math.sin(ang))
        cv.line(x0, y0, x1, y1, NAVY, t=4)
    for k in range(3):
        yy = ey + 34 + k * 14
        for xx in range(ex - 52, ex + 53, 3):
            y = yy + int(6 * math.sin((xx - ex) / 16.0))
            cv.put(xx, y, NAVY)
            cv.put(xx, y + 1, NAVY)

    centered(cv, cx, py + 252, "REPUBLIC OF THARUN", 7, NAVY, tracking=2)
    centered(cv, cx, py + 322, "JUMHUR THARUN", 4, NAVY, tracking=3)
    centered(cv, cx, py + 372, "SAFARNAMA · PASSPORT", 4, NAVY, tracking=2)
    cv.rect(px + 60, py + 428, pw - 120, 3, NAVY)

    # type / code / number row
    ry = py + 452
    draw_text(cv, px + 60, ry, "NAW / TYPE", 2, GREY)
    draw_text(cv, px + 330, ry, "RAMZ / CODE", 2, GREY)
    draw_text(cv, px + 560, ry, "RAQM AL-JAWAZ / PASSPORT NO.", 2, GREY)
    draw_text(cv, px + 60, ry + 28, "P", 5, INK)
    draw_text(cv, px + 330, ry + 28, "THN", 5, INK)
    draw_text(cv, px + 560, ry + 28, "THN730194", 5, INK)

    # photo
    with open(os.path.join(HERE, "portrait.z"), "rb") as f:
        raw = zlib.decompress(f.read())
    ph_x, ph_y, ph_w, ph_h = px + 60, py + 560, 288, 360
    cv.blit_scaled(raw, 288, 360, ph_x, ph_y, ph_w, ph_h)
    cv.frame(ph_x - 3, ph_y - 3, ph_w + 6, ph_h + 6, NAVY, t=3)

    # fields beside photo
    fx = px + 390
    fields = [
        ("KUNYA / SURNAME", "MALEK"),
        ("ISM / GIVEN NAMES", "IDRIS"),
        ("JINSIYA / NATIONALITY", "THARUNI"),
        ("MILAD / DATE OF BIRTH", "22 SEP 1985"),
        ("MAWLID / PLACE OF BIRTH", "QASR WELLS"),
        ("JINS / SEX", "M"),
    ]
    fy = py + 560
    for label, value in fields:
        draw_text(cv, fx, fy, label, 2, GREY)
        draw_text(cv, fx, fy + 26, value, 4, INK)
        fy += 72

    # second block
    by = py + 1010
    draw_text(cv, px + 60, by, "ISDAR / DATE OF ISSUE", 2, GREY)
    draw_text(cv, px + 470, by, "INTIHA / DATE OF EXPIRY", 2, GREY)
    draw_text(cv, px + 60, by + 26, "14 MAY 2022", 4, INK)
    draw_text(cv, px + 470, by + 26, "13 MAY 2032", 4, INK)

    by += 92
    draw_text(cv, px + 60, by, "SULTA / AUTHORITY", 2, GREY)
    draw_text(cv, px + 60, by + 26, "DESERT OFFICE, SEFRA", 4, INK)

    by += 92
    draw_text(cv, px + 60, by, "RAQM SHAKHSI / PERSONAL NO.", 2, GREY)
    draw_text(cv, px + 470, by, "MIHNA / OCCUPATION", 2, GREY)
    draw_text(cv, px + 60, by + 26, "2209 8451 33", 4, INK)
    draw_text(cv, px + 470, by + 26, "CARAVAN GUIDE", 4, INK)

    # signature
    by += 110
    draw_text(cv, px + 60, by, "Idris Malek", 6, SIG_BLUE, slant=3)
    draw_text(cv, px + 60, by + 62, "TAWQI / HOLDER'S SIGNATURE", 2, GREY)

    # observations box
    by += 110
    cv.frame(px + 60, by, pw - 120, 150, NAVY, t=2)
    draw_text(cv, px + 80, by + 16, "MULAHAZAT / OBSERVATIONS", 3, NAVY)
    draw_text(cv, px + 80, by + 54, "Holder is a licensed caravan guide, licence C-118.", 2, INK)
    draw_text(cv, px + 80, by + 82, "Desert transit endorsement on page 7.", 2, INK)
    draw_text(cv, px + 80, by + 112, "Carry water - I.M", 3, SIG_BLUE, slant=2)

    # MRZ
    mrz1, mrz2 = build_mrz()
    my = py + ph - 190
    cv.frame(px + 60, my, pw - 120, 120, NAVY, t=2)
    draw_text(cv, px + 84, my + 22, mrz1, 3, INK, tracking=1)
    draw_text(cv, px + 84, my + 62, mrz2, 3, INK, tracking=1)

    # faint watermark emblem in the empty lower area
    wx, wy = px + pw // 2, my - 230
    cv.circle(wx, wy, 110, GUIL, t=4, a=0.5)
    cv.circle(wx, wy, 92, GUIL, t=2, a=0.5)
    cv.disc(wx, wy - 20, 34, GUIL, a=0.35)
    for k in range(3):
        yy = wy + 44 + k * 18
        for xx in range(wx - 68, wx + 69, 3):
            y = yy + int(7 * math.sin((xx - wx) / 18.0))
            cv.blend(xx, y, GUIL, 0.5)

    draw_text(cv, px + 60, py + ph - 56, "2", 3, GREY)

    # -------------------------------------------------------- visas page
    px, py, pw, ph = rp
    cx = px + pw // 2
    draw_text(cv, px + 60, py + 40, "VISAS · TA'SHIRAT", 5, NAVY, tracking=2)
    draw_text(cv, px + pw - 90, py + 40, "7", 4, GREY)

    # endorsement box + round fee stamp
    ey = py + 120
    cv.frame(px + 60, ey, pw - 120, 190, NAVY, t=2)
    draw_text(cv, px + 84, ey + 18, "DESERT TRANSIT ENDORSEMENT", 4, NAVY)
    draw_text(cv, px + 84, ey + 62, "SAFAR - ISSUED SEFRA 14 MAY 2022", 2, GREY)
    draw_text(cv, px + 84, ey + 92, "DESERT CROSSINGS IN CONVOY ONLY BETWEEN THE", 2, INK)
    draw_text(cv, px + 84, ey + 118, "FIRST AND THIRD WELLS. VALID ONLY WITH", 2, INK)
    draw_text(cv, px + 84, ey + 144, "CARAVAN LICENCE C-118.", 2, INK)
    sx, sy, sr = px + pw - 195, ey + 100, 92
    cv.circle(sx, sy, sr, RED, t=4, a=0.85)
    cv.circle(sx, sy, sr - 10, RED, t=2, a=0.85)
    centered(cv, sx, sy - 52, "WELL TAX", 3, RED, a=0.9)
    centered(cv, sx, sy - 24, "20 THALERS", 3, RED, a=0.9)
    centered(cv, sx, sy + 4, "PAID", 3, RED, a=0.9)
    centered(cv, sx, sy + 32, "14 MAY 2022", 2, RED, a=0.9)

    # border stamps: 2 cols x 4 rows
    stamps = [
        ("THARUN", "DEPARTURE", "03 OCT 2022", RED),
        ("VELMARRA", "ARRIVAL", "05 OCT 2022", BLUE),
        ("VELMARRA", "DEPARTURE", "19 OCT 2022", GREEN),
        ("THARUN", "ARRIVAL", "21 OCT 2022", RED),
        ("THARUN", "DEPARTURE", "11 MAR 2024", BLUE),
        ("VELMARRA", "ARRIVAL", "13 MAR 2024", RED),
        ("VELMARRA", "DEPARTURE", "02 APR 2024", GREEN),
        ("THARUN", "ARRIVAL", "04 APR 2024", BLUE),
    ]
    sw, sh = 410, 150
    sy0 = ey + 230
    for i, (country, kind, date, col) in enumerate(stamps):
        col_i, row_i = i % 2, i // 2
        x = px + 60 + col_i * (sw + 40)
        y = sy0 + row_i * (sh + 36)
        cv.rounded_frame(x, y, sw, sh, 26, col, t=4, a=0.88)
        centered(cv, x + sw // 2, y + 22, country, 4, col, a=0.92)
        centered(cv, x + sw // 2, y + 66, kind, 3, col, a=0.92)
        centered(cv, x + sw // 2, y + 100, date, 3, col, a=0.92)

    # visitor visa box
    vy = sy0 + 4 * (sh + 36) + 10
    cv.frame(px + 60, vy, pw - 120, 240, NAVY, t=2)
    cv.rect(px + 60, vy, pw - 120, 56, (232, 238, 226))
    draw_text(cv, px + 84, vy + 14, "VELMARRA · VISITOR VISA · TASGHIRA", 4, NAVY)
    draw_text(cv, px + 84, vy + 76, "TYPE", 2, GREY)
    draw_text(cv, px + 540, vy + 76, "DURATION OF STAY", 2, GREY)
    draw_text(cv, px + 84, vy + 102, "B · SINGLE ENTRY", 4, INK)
    draw_text(cv, px + 540, vy + 102, "30 DAYS", 4, INK)
    draw_text(cv, px + 84, vy + 150, "VALID FROM", 2, GREY)
    draw_text(cv, px + 540, vy + 150, "UNTIL", 2, GREY)
    draw_text(cv, px + 84, vy + 176, "01 SEP 2025", 4, INK)
    draw_text(cv, px + 540, vy + 176, "30 SEP 2025", 4, INK)
    draw_text(cv, px + 84, vy + 214, "ISSUED AT SEFRA, 20 AUG 2025", 2, GREY)
    draw_text(cv, px + 640, vy + 214, "FEE 35 THALERS", 2, GREY)

    draw_text(cv, px + 60, vy + 268, "Holder must travel in convoy between the wells.", 2, GREY)
    draw_text(cv, px + 60, vy + 296, "This passport remains the property of the Republic of Tharun.", 2, GREY)

    # perforated number bottom-right
    draw_text(cv, px + pw - 250, py + ph - 56, "THN730194", 3, GREY)

    # ------------------------------------------------------------ downsample
    out = bytearray(W * H * 3)
    for y in range(H):
        for x in range(W):
            i00 = ((2 * y) * DW + 2 * x) * 3
            i10 = i00 + 3
            i01 = i00 + DW * 3
            i11 = i01 + 3
            o = (y * W + x) * 3
            for c in range(3):
                out[o + c] = (cv.px[i00 + c] + cv.px[i10 + c] + cv.px[i01 + c] + cv.px[i11 + c]) // 4
    return bytes(out)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    rgb = render()
    write_png(os.path.join(out_dir, "entry.png"), W, H, rgb)


if __name__ == "__main__":
    main()
