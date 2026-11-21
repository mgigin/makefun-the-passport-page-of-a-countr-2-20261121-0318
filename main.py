#!/usr/bin/env python3
"""Republic of Isvane passport spread, rendered from scratch (stdlib only).

Layout follows a classic two-page passport spread: data page with a
photorealistic holder portrait (shipped beside this file as portrait.z,
zlib-compressed raw RGB 288x360) and an ICAO TD3 machine-readable zone
with correct 7-3-1 check digits; visas page with an ice-road transit
endorsement, alternating arrival/departure border stamps and a visitor
visa. Everything except the portrait is drawn by this program.
Rendered at 2x and box-downsampled for smooth edges. Deterministic.
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

NAVY = (27, 42, 74)
NAVY_D = (18, 30, 55)
INK = (32, 34, 38)
GREY = (105, 108, 112)
PAPER = (246, 240, 224)
PAPER2 = (240, 233, 214)
RED = (168, 38, 38)
BLUE = (38, 74, 150)
GREEN = (38, 120, 70)
GOLD = (150, 120, 55)
SIG_BLUE = (40, 60, 140)

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

    def rounded_frame(self, x, y, w, h, r, c, t=3, a=1.0):
        # straight edges
        for xx in range(x + r, x + w - r):
            for k in range(t):
                self.blend(xx, y + k, c, a)
                self.blend(xx, y + h - 1 - k, c, a)
        for yy in range(y + r, y + h - r):
            for k in range(t):
                self.blend(x + k, yy, c, a)
                self.blend(x + w - 1 - k, yy, c, a)
        # corners
        for (cx, cy, a0) in ((x + r, y + r, 180), (x + w - r - 1, y + r, 270),
                             (x + w - r - 1, y + h - r - 1, 0), (x + r, y + h - r - 1, 90)):
            for i in range(25):
                ang = math.radians(a0 + 90 * i / 24)
                for k in range(t):
                    rr = r - k
                    self.blend(int(cx + rr * math.cos(ang)), int(cy + rr * math.sin(ang)), c, a)


# ------------------------------------------------------------------- font
# 5x7 bitmap glyphs, rows top->bottom, '#' = ink.
F = {
 'A': [".###.","#...#","#...#","#####","#...#","#...#","#...#"],
 'B': ["####.","#...#","#...#","####.","#...#","#...#","####."],
 'C': [".####","#....","#....","#....","#....","#....",".####"],
 'D': ["####.","#...#","#...#","#...#","#...#","#...#","####."],
 'E': ["#####","#....","#....","####.","#....","#....","#####"],
 'F': ["#####","#....","#....","####.","#....","#....","#...."],
 'G': [".####","#....","#....","#.###","#...#","#...#",".###."],
 'H': ["#...#","#...#","#...#","#####","#...#","#...#","#...#"],
 'I': [".###.","..#..","..#..","..#..","..#..","..#..",".###."],
 'J': ["..###","....#","....#","....#","....#","#...#",".###."],
 'K': ["#...#","#..#.","#.#..","##...","#.#..","#..#.","#...#"],
 'L': ["#....","#....","#....","#....","#....","#....","#####"],
 'M': ["#...#","##.##","#.#.#","#.#.#","#...#","#...#","#...#"],
 'N': ["#...#","##..#","#.#.#","#..##","#...#","#...#","#...#"],
 'O': [".###.","#...#","#...#","#...#","#...#","#...#",".###."],
 'P': ["####.","#...#","#...#","####.","#....","#....","#...."],
 'Q': [".###.","#...#","#...#","#...#","#.#.#","#..#.",".##.#"],
 'R': ["####.","#...#","#...#","####.","#.#..","#..#.","#...#"],
 'S': [".####","#....","#....",".###.","....#","....#","####."],
 'T': ["#####","..#..","..#..","..#..","..#..","..#..","..#.."],
 'U': ["#...#","#...#","#...#","#...#","#...#","#...#",".###."],
 'V': ["#...#","#...#","#...#","#...#","#...#",".#.#.","..#.."],
 'W': ["#...#","#...#","#...#","#.#.#","#.#.#","##.##","#...#"],
 'X': ["#...#",".#.#.","..#..","..#..","..#..",".#.#.","#...#"],
 'Y': ["#...#","#...#",".#.#.","..#..","..#..","..#..","..#.."],
 'Z': ["#####","....#","...#.","..#..",".#...","#....","#####"],
 '0': [".###.","#...#","#.###","##..#","#...#","#...#",".###."],
 '1': ["..#..",".##..","..#..","..#..","..#..","..#..",".###."],
 '2': [".###.","#...#","....#","..##.",".#...","#....","#####"],
 '3': [".###.","#...#","....#","..##.","....#","#...#",".###."],
 '4': ["...#.","..##.",".#.#.","#..#.","#####","...#.","...#."],
 '5': ["#####","#....","####.","....#","....#","#...#",".###."],
 '6': [".###.","#....","#....","####.","#...#","#...#",".###."],
 '7': ["#####","....#","...#.","..#..","..#..","..#..","..#.."],
 '8': [".###.","#...#","#...#",".###.","#...#","#...#",".###."],
 '9': [".###.","#...#","#...#",".####","....#","....#",".###."],
 ' ': [".....",".....",".....",".....",".....",".....","....."],
 '.': [".....",".....",".....",".....",".....",".##..",".##.."],
 ',': [".....",".....",".....",".....",".##..",".##..",".#..."],
 '<': ["...#.","..#..",".#...","#....",".#...","..#..","...#."],
 '-': [".....",".....",".....","#####",".....",".....","....."],
 '/': ["....#","...#.","...#.","..#..",".#...",".#...","#...."],
 ':': [".....",".##..",".##..",".....",".##..",".##..","....."],
 "'": ["..#..","..#..",".#...",".....",".....",".....","....."],
 '(': ["...#.","..#..",".#...",".#...",".#...","..#..","...#."],
 ')': [".#...","..#..","...#.","...#.","...#.","..#..",".#..."],
 '+': [".....","..#..","..#..","#####","..#..","..#..","....."],
 '&': [".##..","#..#.","#.#..",".#...","#.#.#","#..#.",".##.#"],
 '·': [".....",".....",".....",".##..",".##..",".....","....."],
}
# accented capitals: base letter + accent drawn above
ACCENT = {'Á': ('A', 'acute'), 'É': ('E', 'acute'), 'Í': ('I', 'acute'),
          'Ó': ('O', 'acute'), 'Ú': ('U', 'acute'), 'Ý': ('Y', 'acute'),
          'Ð': ('D', 'bar'), 'Þ': ('P', 'thorn'), 'Æ': ('A', 'ae'), 'Ö': ('O', 'dia')}


def glyph(ch):
    if ch in F:
        return F[ch], None
    if ch in ACCENT:
        base, acc = ACCENT[ch]
        return F[base], acc
    if ch.islower() and ch.upper() in F:
        return F[ch.upper()], 'lower'
    return F[' '], None


def text_width(s, scale, tracking=1):
    return len(s) * (5 * scale + tracking * scale) - tracking * scale


def draw_text(cv, x, y, s, scale, c, tracking=1, slant=0, a=1.0):
    cx = x
    for ch in s:
        g, acc = glyph(ch)
        hscale = scale
        yoff = 0
        if acc == 'lower':
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
        # accents
        ax = cx + 2 * scale
        ay = y - 2 * scale
        if acc == 'acute':
            cv.line(ax - scale, ay + scale, ax + scale, ay - scale, c, t=max(1, scale // 2), a=a)
        elif acc == 'bar':
            cv.rect(cx, y + 3 * scale, 5 * scale, max(1, scale // 2), c)
        elif acc == 'dia':
            cv.rect(ax - 2 * scale, ay, scale, scale, c)
            cv.rect(ax + scale, ay, scale, scale, c)
        elif acc == 'thorn':
            cv.rect(cx, y, max(1, scale // 2), 7 * scale, c)
        cx += 5 * scale + tracking * scale
    return cx


def draw_centered(cv, cx, y, s, scale, c, tracking=1, a=1.0):
    w = text_width(s, scale, tracking)
    return draw_text(cv, cx - w // 2, y, s, scale, c, tracking, a=a)


def draw_right(cv, rx, y, s, scale, c, tracking=1, a=1.0):
    w = text_width(s, scale, tracking)
    return draw_text(cv, rx - w, y, s, scale, c, tracking, a=a)


# ---------------------------------------------------------------- helpers
def load_portrait():
    with open(os.path.join(HERE, "portrait.z"), "rb") as f:
        raw = zlib.decompress(f.read())
    return 288, 360, raw


def blit_portrait(cv, x, y, w, h, pw, ph, raw):
    for yy in range(h):
        sy = min(ph - 1, yy * ph // h)
        for xx in range(w):
            sx = min(pw - 1, xx * pw // w)
            i = (sy * pw + sx) * 3
            cv.put(x + xx, y + yy, (raw[i], raw[i + 1], raw[i + 2]))


def guilloche(cv, x0, y0, x1, y1, rng):
    # faint wavy security lines across the page
    for k in range(46):
        base_y = y0 + (y1 - y0) * k // 46
        amp = 6 + (k % 5) * 3
        phase = rng.uniform(0, 6.28)
        col = (196, 186, 152) if k % 2 == 0 else (206, 198, 168)
        for xx in range(x0, x1, 3):
            yy = int(base_y + amp * math.sin(xx / 55.0 + phase))
            cv.blend(xx, yy, col, 0.35)
    # paper grain
    for _ in range(2600):
        xx = rng.randint(x0, x1 - 1)
        yy = rng.randint(y0, y1 - 1)
        cv.blend(xx, yy, (210, 200, 170), 0.25)


def mrz_check(s):
    vals = {str(d): d for d in range(10)}
    for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        vals[ch] = 10 + i
    vals['<'] = 0
    weights = [7, 3, 1]
    return str(sum(vals[ch] * weights[i % 3] for i, ch in enumerate(s)) % 10)


def build_mrz():
    line1 = "P<ISVSOLBERG<<LIV<ANETTE" + "<" * 20
    doc = "ISV004713"
    dob = "900214"
    exp = "330308"
    personal = "14029033714"
    l2 = (doc + mrz_check(doc) + "ISV" + dob + mrz_check(dob) + "F"
          + exp + mrz_check(exp) + personal + mrz_check(personal))
    composite_src = l2[0:10] + l2[13:20] + l2[21:43]
    line2 = l2 + mrz_check(composite_src) + "<<<"
    return line1[:44], line2[:44]


def field(cv, x, y, label, value, ls=2, vs=3, lc=GREY, vc=INK):
    draw_text(cv, x, y, label, ls, lc, tracking=1)
    draw_text(cv, x, y + 9 * ls, value, vs, vc, tracking=1)


def stamp(cv, x, y, w, h, place, sub, kind, date, c, rng):
    a = rng.uniform(0.78, 0.95)
    cv.rounded_frame(x, y, w, h, 14, c, t=4, a=a)
    cv.rounded_frame(x + 7, y + 7, w - 14, h - 14, 10, c, t=2, a=a * 0.7)
    cx = x + w // 2
    draw_centered(cv, cx, y + 16, place, 3, c, a=a)
    draw_centered(cv, cx, y + 48, sub, 2, c, a=a * 0.85)
    draw_centered(cv, cx, y + 76, kind, 3, c, a=a)
    draw_centered(cv, cx, y + 106, date, 3, c, a=a)


# ------------------------------------------------------------------- main
def render():
    rng = random.Random(20260309)
    cv = Canvas(DW, DH, NAVY_D)
    # pages
    lx0, ly0, lx1, ly1 = 28, 28, 1008, 2020
    rx0, ry0, rx1, ry1 = 1040, 28, 2020, 2020
    cv.rect(lx0, ly0, lx1 - lx0, ly1 - ly0, PAPER)
    cv.rect(rx0, ry0, rx1 - rx0, ry1 - ry0, PAPER2)
    guilloche(cv, lx0, ly0, lx1, ly1, rng)
    guilloche(cv, rx0, ry0, rx1, ry1, rng)
    # centre fold shadow
    for i in range(46):
        a = 0.16 * (1 - i / 46)
        cv.rect_blend(1024 - i, ly0, 1, ly1 - ly0, (90, 80, 60), a)
        cv.rect_blend(1024 + i, ry0, 1, ry1 - ry0, (90, 80, 60), a)
    # page frames
    cv.frame(lx0, ly0, lx1 - lx0, ly1 - ly0, NAVY, t=3)
    cv.frame(rx0, ry0, rx1 - rx0, ry1 - ry0, NAVY, t=3)

    pw, ph, praw = load_portrait()
    mrz1, mrz2 = build_mrz()

    # ============================ DATA PAGE ============================
    # perforated number top-right
    draw_right(cv, lx1 - 36, ly0 + 26, "ISV004713", 3, GREY)
    # emblem: compass rose in a ring
    ecx, ecy, er = (lx0 + lx1) // 2, ly0 + 118, 58
    cv.circle(ecx, ecy, er, NAVY, t=4)
    cv.circle(ecx, ecy, er - 10, NAVY, t=2)
    for k in range(16):
        ang = math.pi * k / 8
        r1 = er - 14 if k % 2 == 0 else (er - 14) * 0.55
        cv.line(ecx, ecy, int(ecx + r1 * math.cos(ang)), int(ecy + r1 * math.sin(ang)), NAVY, t=3)
    cv.circle(ecx, ecy, 8, NAVY, t=3)
    # country name
    draw_centered(cv, ecx, ly0 + 196, "REPUBLIC OF ISVANE", 6, NAVY, tracking=2)
    draw_centered(cv, ecx, ly0 + 256, "LYÐVELDIÐ ISVANE", 3, NAVY, tracking=2)
    draw_centered(cv, ecx, ly0 + 288, "VEGABRÉF · PASSPORT", 3, NAVY, tracking=2)
    cv.rect(lx0 + 70, ly0 + 326, lx1 - lx0 - 140, 3, NAVY)
    # type / code / number
    ty = ly0 + 344
    field(cv, lx0 + 70, ty, "TIP / TYPE", "P")
    field(cv, lx0 + 300, ty, "KOÐI / CODE", "ISV")
    field(cv, lx0 + 530, ty, "PAS NR / PASSPORT NO.", "ISV004713")
    # photo
    px, py, pwid, phei = lx0 + 70, ly0 + 448, 300, 375
    blit_portrait(cv, px, py, pwid, phei, pw, ph, praw)
    cv.frame(px, py, pwid, phei, NAVY, t=3)
    # fields right of photo
    fx = lx0 + 404
    fy = ly0 + 448
    field(cv, fx, fy, "FAMAR / SURNAME", "SOLBERG")
    field(cv, fx, fy + 78, "ANVAR / GIVEN NAMES", "LIV ANETTE")
    field(cv, fx, fy + 156, "VETRAN / NATIONALITY", "ISVAN")
    field(cv, fx, fy + 234, "DUNAR / DATE OF BIRTH", "14 FEB 1990")
    field(cv, fx, fy + 312, "IMZAR / PLACE OF BIRTH", "NORDHAVN")
    # sex under photo block
    field(cv, fx, fy + 390, "KESH / SEX", "F")
    # issue / expiry
    iy = ly0 + 862
    field(cv, lx0 + 70, iy, "ISHAN / DATE OF ISSUE", "09 MAR 2023")
    field(cv, lx0 + 530, iy, "ISHDAI / DATE OF EXPIRY", "08 MAR 2033")
    # authority / personal / occupation
    ay = ly0 + 956
    field(cv, lx0 + 70, ay, "DAFTAR / AUTHORITY", "ICE-ROAD OFFICE, NORDHAVN", vs=3)
    field(cv, lx0 + 70, ay + 78, "SHAKH NR / PERSONAL NO.", "1402 9033 71")
    field(cv, lx0 + 530, ay + 78, "STARF / OCCUPATION", "ICE-ROAD DRIVER")
    # signature
    sy = ly0 + 1120
    draw_text(cv, lx0 + 70, sy, "Liv Anette Solberg", 5, SIG_BLUE, tracking=1, slant=1)
    cv.rect(lx0 + 70, sy + 48, 460, 2, GREY)
    draw_text(cv, lx0 + 70, sy + 58, "HOLDER'S SIGNATURE / UNDIRSKRIFT", 2, GREY)
    # observations box
    oy = ly0 + 1240
    cv.frame(lx0 + 70, oy, lx1 - lx0 - 140, 210, NAVY, t=2)
    draw_text(cv, lx0 + 92, oy + 18, "MERKAR / OBSERVATIONS", 3, NAVY)
    draw_text(cv, lx0 + 92, oy + 60, "Licensed ice-road driver, licence I-2210.", 2, INK)
    draw_text(cv, lx0 + 92, oy + 92, "Ice-road transit endorsement on page 7.", 2, INK)
    draw_text(cv, lx0 + 92, oy + 138, "Convoy only after dark — L.S", 3, SIG_BLUE, slant=1)
    # MRZ box
    my = ly0 + 1500
    cv.frame(lx0 + 70, my, lx1 - lx0 - 140, 170, NAVY, t=2)
    draw_text(cv, lx0 + 92, my + 28, mrz1, 3, INK, tracking=0)
    draw_text(cv, lx0 + 92, my + 84, mrz2, 3, INK, tracking=0)
    # page number
    draw_text(cv, lx0 + 36, ly1 - 56, "2", 3, GREY)

    # ============================ VISAS PAGE ===========================
    draw_text(cv, rx0 + 70, ry0 + 40, "VISAS", 6, NAVY, tracking=2)
    draw_text(cv, rx0 + 330, ry0 + 58, "· VEGABRÉF", 3, NAVY, tracking=2)
    draw_right(cv, rx1 - 36, ry0 + 40, "7", 3, GREY)
    # endorsement box
    ey = ry0 + 130
    cv.frame(rx0 + 70, ey, rx1 - rx0 - 140, 250, NAVY, t=2)
    draw_text(cv, rx0 + 92, ey + 20, "ICE-ROAD TRANSIT ENDORSEMENT", 3, NAVY)
    draw_text(cv, rx0 + 92, ey + 58, "ISLEÐ · ISSUED NORDHAVN 09 MAR 2023", 2, GREY)
    draw_text(cv, rx0 + 92, ey + 96, "ICE ROADS OPEN ONLY WHEN THE ICE IS 40 CM OR MORE.", 2, INK)
    draw_text(cv, rx0 + 92, ey + 128, "CROSSINGS IN CONVOY ONLY, 22:00-05:00.", 2, INK)
    draw_text(cv, rx0 + 92, ey + 160, "VALID WITH ICE-ROAD LICENCE I-2210.", 2, INK)
    # red toll stamp overlapping
    tcx, tcy, tr = rx1 - 190, ey + 92, 86
    cv.circle(tcx, tcy, tr, RED, t=4, a=0.85)
    cv.circle(tcx, tcy, tr - 10, RED, t=2, a=0.7)
    draw_centered(cv, tcx, tcy - 58, "ICE-ROAD", 2, RED, a=0.85)
    draw_centered(cv, tcx, tcy - 34, "TOLL", 2, RED, a=0.85)
    draw_centered(cv, tcx, tcy - 10, "15 ISK", 2, RED, a=0.85)
    draw_centered(cv, tcx, tcy + 14, "PAID", 2, RED, a=0.85)
    draw_centered(cv, tcx, tcy + 38, "09 MAR 2023", 2, RED, a=0.85)
    # six border stamps
    stamps = [
        ("ISVANE", "REPUBLIC OF ISVANE", "DEPARTURE", "12 JAN 2024", RED),
        ("KALDVIK", "HAVARIA PORT", "ARRIVAL", "13 JAN 2024", BLUE),
        ("KALDVIK", "HAVARIA PORT", "DEPARTURE", "27 JAN 2024", BLUE),
        ("ISVANE", "REPUBLIC OF ISVANE", "ARRIVAL", "28 JAN 2024", RED),
        ("ISVANE", "REPUBLIC OF ISVANE", "DEPARTURE", "04 NOV 2025", RED),
        ("KALDVIK", "HAVARIA PORT", "ARRIVAL", "05 NOV 2025", GREEN),
    ]
    sw, sh = 400, 148
    sx0 = rx0 + 70
    sy0 = ey + 300
    for i, (pl, sub, kind, dt, col) in enumerate(stamps):
        col_i = i % 2
        row_i = i // 2
        stamp(cv, sx0 + col_i * (sw + 40), sy0 + row_i * (sh + 26), sw, sh, pl, sub, kind, dt, col, rng)
    # one more pair to mirror the reference's 8 stamps? reference shows 8; add final pair
    stamp(cv, sx0, sy0 + 3 * (sh + 26), sw, sh, "KALDVIK", "HAVARIA PORT", "DEPARTURE", "28 NOV 2025", GREEN, rng)
    stamp(cv, sx0 + sw + 40, sy0 + 3 * (sh + 26), sw, sh, "ISVANE", "REPUBLIC OF ISVANE", "ARRIVAL", "29 NOV 2025", RED, rng)
    # visitor visa box
    vy = sy0 + 4 * (sh + 26) + 30
    cv.rect_blend(rx0 + 70, vy, rx1 - rx0 - 140, 240, (200, 225, 200), 0.35)
    cv.frame(rx0 + 70, vy, rx1 - rx0 - 140, 240, GREEN, t=2)
    draw_text(cv, rx0 + 92, vy + 18, "KALDVIK · VISITOR VISA · GESTAVISA", 3, GREEN)
    field(cv, rx0 + 92, vy + 64, "TYPE", "B · SINGLE ENTRY", vs=3)
    field(cv, rx0 + 560, vy + 64, "DURATION OF STAY", "30 DAYS", vs=3)
    field(cv, rx0 + 92, vy + 138, "VALID FROM", "01 NOV 2025", vs=3)
    field(cv, rx0 + 560, vy + 138, "UNTIL", "30 NOV 2025", vs=3)
    field(cv, rx0 + 92, vy + 198, "ISSUED AT", "NORDHAVN, 22 OCT 2025", vs=2)
    field(cv, rx0 + 560, vy + 198, "FEE", "25 ISK", vs=3)
    # small print
    draw_text(cv, rx0 + 70, vy + 280, "Holder must travel in convoy on the ice roads.", 2, GREY)
    draw_text(cv, rx0 + 70, vy + 312, "This passport remains the property of the Republic of Isvane.", 2, GREY)
    # perforated number bottom-right
    draw_right(cv, rx1 - 36, ry1 - 56, "ISV004713", 3, GREY)
    return cv


def downsample(cv):
    out = bytearray(W * H * 3)
    src = cv.px
    for y in range(H):
        for x in range(W):
            r = g = b = 0
            for dy in range(S):
                base = ((y * S + dy) * DW + x * S) * 3
                for dx in range(S):
                    i = base + dx * 3
                    r += src[i]
                    g += src[i + 1]
                    b += src[i + 2]
            o = (y * W + x) * 3
            n = S * S
            out[o] = r // n
            out[o + 1] = g // n
            out[o + 2] = b // n
    return bytes(out)


def main():
    cv = render()
    rgb = downsample(cv)
    os.makedirs("/output", exist_ok=True)
    write_png("/output/entry.png", W, H, rgb)


if __name__ == "__main__":
    main()
