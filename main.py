#!/usr/bin/env python3
"""Republic of Veldor passport spread, rendered from scratch (stdlib only).

The holder portrait is a real generated ID photograph shipped beside this
file as portrait.z (zlib-compressed raw RGB, 288x360) and composited into
the data page. Everything else -- security paper, guilloche, typography,
MRZ with ICAO check digits, visa sticker and border stamps -- is drawn
by this program. Rendered at 2x and box-downsampled for smooth edges.
"""
import math
import os
import random
import struct
import zlib

W = H = 1024
S = 2                      # supersample factor
DW, DH = W * S, H * S
HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------- PNG writer
def _chunk(tag, data):
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def write_png(path, w, h, rgb):
    """rgb: bytes of w*h*3. Sub-filtered rows, deterministic bytes."""
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        row = rgb[y * stride:(y + 1) * stride]
        raw.append(1)
        prev = 0
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
        self.clip = (0, 0, w, h)

    def set_clip(self, x, y, w, h):
        self.clip = (max(0, x), max(0, y), min(self.w, x + w), min(self.h, y + h))

    def clear_clip(self):
        self.clip = (0, 0, self.w, self.h)

    def put(self, x, y, c):
        cx0, cy0, cx1, cy1 = self.clip
        if cx0 <= x < cx1 and cy0 <= y < cy1:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(c)

    def blend(self, x, y, c, a):
        cx0, cy0, cx1, cy1 = self.clip
        if cx0 <= x < cx1 and cy0 <= y < cy1:
            i = (y * self.w + x) * 3
            ia = 1.0 - a
            self.px[i] = int(self.px[i] * ia + c[0] * a)
            self.px[i + 1] = int(self.px[i + 1] * ia + c[1] * a)
            self.px[i + 2] = int(self.px[i + 2] * ia + c[2] * a)

    def rect(self, x, y, w, h, c):
        cx0, cy0, cx1, cy1 = self.clip
        x0, y0 = max(x, cx0), max(y, cy0)
        x1, y1 = min(x + w, cx1), min(y + h, cy1)
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

    def frame(self, x, y, w, h, c, t=1):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def line(self, x0, y0, x1, y1, c, t=1, a=None):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        r = max(0, t // 2)
        for i in range(steps + 1):
            x = int(x0 + (x1 - x0) * i / steps)
            y = int(y0 + (y1 - y0) * i / steps)
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if a is None:
                        self.put(x + dx, y + dy, c)
                    else:
                        self.blend(x + dx, y + dy, c, a)

    def ellipse(self, cx, cy, rx, ry, c, a=None):
        for dy in range(-ry, ry + 1):
            t = dy / ry if ry else 0
            half = int(rx * math.sqrt(max(0.0, 1 - t * t)))
            if a is None:
                self.rect(cx - half, cy + dy, half * 2 + 1, 1, c)
            else:
                self.rect_blend(cx - half, cy + dy, half * 2 + 1, 1, c, a)

    def ring(self, cx, cy, rx, ry, c, t=1.0, a=None):
        steps = max(24, int((rx + ry) * 2))
        for i in range(steps):
            th = 2 * math.pi * i / steps
            x = int(cx + rx * math.cos(th))
            y = int(cy + ry * math.sin(th))
            r = max(0, int(t // 2))
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if a is None:
                        self.put(x + dx, y + dy, c)
                    else:
                        self.blend(x + dx, y + dy, c, a)

    def poly(self, pts, c):
        ys = [p[1] for p in pts]
        for y in range(min(ys), max(ys) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if y0 == y1:
                    continue
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(int(x0 + (y - y0) * (x1 - x0) / (y1 - y0)))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.rect(xs[i], y, xs[i + 1] - xs[i] + 1, 1, c)


# -------------------------------------------------------------- 5x7 font
# Each glyph: 7 rows of 5 bits.
_G = {
    'A': (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11), 'B': (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    'C': (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E), 'D': (0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C),
    'E': (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F), 'F': (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    'G': (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F), 'H': (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    'I': (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E), 'J': (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    'K': (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11), 'L': (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    'M': (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11), 'N': (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    'O': (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E), 'P': (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    'Q': (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D), 'R': (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    'S': (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E), 'T': (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    'U': (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E), 'V': (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    'W': (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11), 'X': (0x11, 0x0A, 0x04, 0x04, 0x04, 0x0A, 0x11),
    'Y': (0x11, 0x0A, 0x04, 0x04, 0x04, 0x04, 0x04), 'Z': (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    '0': (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E), '1': (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    '2': (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F), '3': (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    '4': (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02), '5': (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    '6': (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E), '7': (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    '8': (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E), '9': (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    ' ': (0, 0, 0, 0, 0, 0, 0), '.': (0, 0, 0, 0, 0, 0x0C, 0x0C), ',': (0, 0, 0, 0, 0x0C, 0x04, 0x08),
    ':': (0, 0x0C, 0x0C, 0, 0x0C, 0x0C, 0), ';': (0, 0x0C, 0x0C, 0, 0x0C, 0x04, 0x08),
    '-': (0, 0, 0, 0x1F, 0, 0, 0), '/': (0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10),
    '(': (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02), ')': (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    '<': (0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02), '>': (0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08),
    "'": (0x04, 0x04, 0x08, 0, 0, 0, 0), '+': (0, 0x04, 0x04, 0x1F, 0x04, 0x04, 0),
    '*': (0, 0x04, 0x15, 0x0E, 0x15, 0x04, 0), '#': (0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A),
    '!': (0x04, 0x04, 0x04, 0x04, 0x04, 0, 0x04), '?': (0x0E, 0x11, 0x01, 0x02, 0x04, 0, 0x04),
    '=': (0, 0, 0x1F, 0, 0x1F, 0, 0), '_': (0, 0, 0, 0, 0, 0, 0x1F),
}
for _k in list(_G):
    if _k.isalpha():
        _G[_k.lower()] = _G[_k]


def text_width(s, scale, spacing=1):
    return int(len(s) * (5 * scale + spacing * scale))


def draw_text(cv, x, y, s, scale, c, spacing=1, bold=False, a=None):
    """x,y in device px; scale = device px per font pixel (float ok)."""
    cx = x
    for ch in s:
        g = _G.get(ch, _G[' '])
        for row in range(7):
            bits = g[row]
            for col in range(5):
                if bits & (0x10 >> col):
                    px = int(cx + col * scale)
                    py = int(y + row * scale)
                    sz = max(1, int(round(scale))) + (1 if bold else 0)
                    if a is None:
                        cv.rect(px, py, sz, sz, c)
                    else:
                        cv.rect_blend(px, py, sz, sz, c, a)
        cx += (5 + spacing) * scale
    return int(cx - x)


def draw_text_c(cv, cx, y, s, scale, c, spacing=1, bold=False, a=None):
    w = text_width(s, scale, spacing)
    draw_text(cv, int(cx - w / 2), y, s, scale, c, spacing, bold, a)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


# --------------------------------------------------------------- portrait
PW, PH = 288, 360


def load_portrait():
    with open(os.path.join(HERE, "portrait.z"), "rb") as f:
        raw = zlib.decompress(f.read())
    assert len(raw) == PW * PH * 3
    return raw


def blit_photo(cv, raw, x, y, w, h, ghost=False, paper=(238, 236, 228)):
    """Nearest-neighbour blit of the portrait into rect (device px)."""
    for dy in range(h):
        sy = min(PH - 1, dy * PH // h)
        srow = sy * PW * 3
        for dx in range(w):
            sx = min(PW - 1, dx * PW // w)
            i = srow + sx * 3
            r, g, b = raw[i], raw[i + 1], raw[i + 2]
            if ghost:
                lum = int(0.299 * r + 0.587 * g + 0.114 * b)
                lum = int(lum * 0.35 + 200 * 0.65)
                c = mix((lum, lum, lum), paper, 0.45)
                cv.blend(x + dx, y + dy, c, 0.55)
            else:
                cv.put(x + dx, y + dy, (r, g, b))


# ------------------------------------------------------------ decorations
def guilloche(cv, x, y, w, h, c, gap=14, amp=4.0, period=90.0, phase=0.0, a=0.35):
    yy = y
    k = 0
    while yy < y + h:
        prev = None
        for xx in range(x, x + w, 3):
            off = amp * math.sin((xx - x) * 2 * math.pi / period + phase + k * 0.7)
            p = (xx, int(yy + off))
            if prev:
                cv.line(prev[0], prev[1], p[0], p[1], c, 1, a)
            prev = p
        yy += gap
        k += 1


def rosette(cv, cx, cy, r, c, petals=9, a=0.3):
    for i in range(petals):
        th = 2 * math.pi * i / petals
        cv.ring(int(cx + r * 0.45 * math.cos(th)), int(cy + r * 0.45 * math.sin(th)),
                int(r * 0.55), int(r * 0.55), c, 1, a)


def star(cv, cx, cy, r, c, a=None):
    pts = []
    for i in range(10):
        th = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((int(cx + rr * math.cos(th)), int(cy + rr * math.sin(th))))
    if a is None:
        cv.poly(pts, c)
    else:
        tmp = Canvas(cv.w, cv.h, (0, 0, 0))
        tmp.poly(pts, (255, 255, 255))
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if 0 <= xx < cv.w and 0 <= yy < cv.h and tmp.px[(yy * cv.w + xx) * 3]:
                    cv.blend(xx, yy, c, a)


def emblem(cv, cx, cy, r, gold=(196, 160, 84), navy=(29, 53, 87)):
    """Anchor over waves inside a rope ring, star above."""
    cv.ring(cx, cy, r, r, gold, 3)
    cv.ring(cx, cy, int(r * 0.86), int(r * 0.86), gold, 1)
    # anchor: shank, crossbar, flukes, ring
    cv.line(cx, cy - int(r * 0.55), cx, cy + int(r * 0.45), navy, 3)
    cv.line(cx - int(r * 0.3), cy - int(r * 0.3), cx + int(r * 0.3), cy - int(r * 0.3), navy, 3)
    cv.ring(cx, cy - int(r * 0.62), int(r * 0.1), int(r * 0.1), navy, 2)
    cv.line(cx, cy + int(r * 0.45), cx - int(r * 0.42), cy + int(r * 0.18), navy, 3)
    cv.line(cx, cy + int(r * 0.45), cx + int(r * 0.42), cy + int(r * 0.18), navy, 3)
    # waves
    for k, wy in enumerate((0.62, 0.78)):
        prev = None
        for xx in range(cx - int(r * 0.55), cx + int(r * 0.55), 3):
            off = 3 * math.sin((xx - cx) * 0.25 + k)
            p = (xx, int(cy + r * wy + off))
            if prev:
                cv.line(prev[0], prev[1], p[0], p[1], navy, 2)
            prev = p
    star(cv, cx, cy - int(r * 0.95), int(r * 0.16), gold)


def signature(cv, x, y, w, c=(38, 44, 66)):
    pts = []
    n = 60
    for i in range(n + 1):
        t = i / n
        px = x + int(w * t)
        py = y + int(10 * math.sin(t * 9.0) * (1 - t * 0.4) + 6 * math.sin(t * 23.0))
        pts.append((px, py))
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], c, 2)
    cv.line(x + int(w * 0.1), y + 14, x + int(w * 0.95), y + 12, c, 1)


# -------------------------------------------------------------------- MRZ
def _mrz_val(ch):
    if ch == '<':
        return 0
    if ch.isdigit():
        return int(ch)
    return ord(ch) - 55


def _mrz_check(s):
    wts = (7, 3, 1)
    return str(sum(_mrz_val(c) * wts[i % 3] for i, c in enumerate(s)) % 10)


def build_mrz():
    line1 = ("P<VLDKOVAC<<MIRA" + "<" * 44)[:44]
    doc = "VD4829137"
    dob = "910704"
    exp = "330311"
    personal = "PILOTCLASS2<<<"[:14]
    body = doc + _mrz_check(doc) + "VLD" + dob + _mrz_check(dob) + "F" + exp + _mrz_check(exp) + personal + _mrz_check(personal)
    comp_src = body[0:10] + body[13:20] + body[21:43]
    line2 = (body + _mrz_check(comp_src) + "<" * 44)[:44]
    return line1, line2


# ----------------------------------------------------------------- stamps
class Stamp:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rgb = bytearray(w * h * 3)
        self.al = bytearray(w * h)

    def put(self, x, y, c, a=200):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.rgb[i:i + 3] = bytes(c)
            self.al[y * self.w + x] = a

    def rect(self, x, y, w, h, c, a=200):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.put(xx, yy, c, a)

    def frame(self, x, y, w, h, c, t=2, a=200):
        self.rect(x, y, w, t, c, a)
        self.rect(x, y + h - t, w, t, c, a)
        self.rect(x, y, t, h, c, a)
        self.rect(x + w - t, y, t, h, c, a)

    def ring(self, cx, cy, r, c, t=2, a=200):
        steps = max(32, r * 4)
        for i in range(steps):
            th = 2 * math.pi * i / steps
            x, y = int(cx + r * math.cos(th)), int(cy + r * math.sin(th))
            for dy in range(-t // 2, t // 2 + 1):
                for dx in range(-t // 2, t // 2 + 1):
                    self.put(x + dx, y + dy, c, a)

    def text(self, x, y, s, scale, c, a=200, spacing=1):
        cx = x
        for ch in s:
            g = _G.get(ch, _G[' '])
            for row in range(7):
                for col in range(5):
                    if g[row] & (0x10 >> col):
                        for dy in range(int(scale)):
                            for dx in range(int(scale)):
                                self.put(int(cx + col * scale) + dx, int(y + row * scale) + dy, c, a)
            cx += (5 + spacing) * scale

    def text_c(self, cx, y, s, scale, c, a=200, spacing=1):
        self.text(int(cx - text_width(s, scale, spacing) / 2), y, s, scale, c, a, spacing)

    def blit_rotated(self, cv, cx, cy, angle_deg, strength=0.85):
        th = math.radians(angle_deg)
        cos_t, sin_t = math.cos(th), math.sin(th)
        hw, hh = self.w // 2, self.h // 2
        R = int(math.hypot(hw, hh)) + 2
        for dy in range(-R, R + 1):
            for dx in range(-R, R + 1):
                sx = int(dx * cos_t + dy * sin_t) + hw
                sy = int(-dx * sin_t + dy * cos_t) + hh
                if 0 <= sx < self.w and 0 <= sy < self.h:
                    a = self.al[sy * self.w + sx]
                    if a:
                        i = (sy * self.w + sx) * 3
                        cv.blend(cx + dx, cy + dy, tuple(self.rgb[i:i + 3]), a / 255.0 * strength)


def make_stamp(country, kind, date, port, color, shape="rect"):
    if shape == "round":
        st = Stamp(150, 150)
        st.ring(75, 75, 70, color, 3)
        st.ring(75, 75, 60, color, 1)
        st.text_c(75, 44, country, 1.3, color)
        st.text_c(75, 60, kind, 2, color)
        st.text_c(75, 82, date, 1.5, color)
        st.text_c(75, 100, port, 1.2, color)
    else:
        st = Stamp(210, 96)
        st.frame(2, 2, 206, 92, color, 3)
        st.frame(8, 8, 194, 80, color, 1)
        st.text_c(105, 16, country, 2, color)
        st.text_c(105, 38, kind, 2, color)
        st.text_c(105, 58, date, 2, color)
        st.text_c(105, 76, port, 1, color)
    return st


# ------------------------------------------------------------------- pages
NAVY = (29, 53, 87)
GOLD = (196, 160, 84)
INK = (32, 38, 52)
PAPER = (238, 236, 228)
LABEL = (90, 100, 118)
VALUE = (24, 30, 44)


def X(v):
    return int(v * S)


def field(cv, x, y, label, value):
    draw_text(cv, X(x), X(y), label.upper(), 2.0, LABEL, spacing=1)
    draw_text(cv, X(x), X(y + 11), value.upper(), 3.1, VALUE, spacing=1, bold=True)


def paper_base(cv, px, py, pw, ph, rng):
    cv.rect(X(px), X(py), X(pw), X(ph), PAPER)
    cv.set_clip(X(px), X(py), X(pw), X(ph))
    guilloche(cv, X(px), X(py), X(pw), X(ph), (150, 175, 205), gap=15, amp=4, period=95, a=0.30)
    guilloche(cv, X(px), X(py), X(pw), X(ph), (205, 160, 160), gap=23, amp=6, period=140, phase=1.3, a=0.20)
    rosette(cv, X(px + 40), X(py + ph - 46), X(30), (140, 165, 200), a=0.25)
    rosette(cv, X(px + pw - 40), X(py + 120), X(26), (140, 165, 200), a=0.20)
    # watermark emblem, very faint, centre of page
    emblem(cv, X(px + pw // 2), X(py + ph // 2 + 30), X(70), gold=(222, 218, 205), navy=(216, 212, 198))
    # paper grain
    for _ in range(2600):
        gx = X(px) + rng.randrange(X(pw))
        gy = X(py) + rng.randrange(X(ph))
        cv.blend(gx, gy, (200, 196, 182), 0.35)
    cv.clear_clip()
    cv.frame(X(px), X(py), X(pw), X(ph), (120, 124, 130), 2)


def perforated_number(cv, x, y, text):
    """Passport number punched as dot-matrix down the page edge."""
    dot = (150, 148, 140)
    cy = y
    for ch in text:
        g = _G.get(ch, _G[' '])
        for row in range(7):
            for col in range(5):
                if g[row] & (0x10 >> col):
                    cv.ellipse(X(x + col * 3), X(cy + row * 3), 2, 2, dot)
        cy += 26


def hologram(cv, cx, cy, r):
    cols = [(255, 120, 140), (255, 190, 110), (150, 230, 150), (120, 200, 255), (190, 150, 255)]
    for i, c in enumerate(cols):
        cv.ring(X(cx), X(cy), X(r - i * 3), X(r - i * 3), c, 2, 0.55)
    star(cv, X(cx), X(cy), X(int(r * 0.45)), (255, 255, 255), a=0.5)
    cv.ellipse(X(cx), X(cy), X(r), X(r), (255, 255, 255), a=0.10)


def data_page(cv, raw, px, py, pw, ph, rng):
    paper_base(cv, px, py, pw, ph, rng)
    # header band
    cv.rect(X(px), X(py), X(pw), X(62), NAVY)
    cv.rect(X(px), X(py + 62), X(pw), X(3), GOLD)
    cv.ellipse(X(px + 34), X(py + 31), X(24), X(24), (238, 236, 228))
    emblem(cv, X(px + 34), X(py + 31), X(20))
    draw_text(cv, X(px + 66), X(py + 12), "REPUBLIC OF VELDOR", 4.4, (240, 230, 200), bold=True)
    draw_text(cv, X(px + 66), X(py + 38), "PASSPORT  /  PAS", 2.6, GOLD)
    draw_text(cv, X(px + pw - 118), X(py + 40), "TYPE P  VLD", 2.2, (200, 208, 224))

    # photo (real generated ID photograph)
    phx, phy, phw, phh = px + 20, py + 82, 150, 188
    cv.rect(X(phx - 3), X(phy - 3), X(phw + 6), X(phh + 6), (255, 255, 255))
    blit_photo(cv, raw, X(phx), X(phy), X(phw), X(phh))
    cv.frame(X(phx - 3), X(phy - 3), X(phw + 6), X(phh + 6), (110, 116, 126), 2)
    hologram(cv, phx + phw - 6, phy + phh - 8, 27)

    # ghost portrait (frameless, faint) top-right
    blit_photo(cv, raw, X(px + pw - 84), X(py + 82), X(64), X(80), ghost=True, paper=PAPER)

    # fields right of photo
    fx = px + 188
    field(cv, fx, py + 84, "Surname / Aftirnam", "Kovac")
    field(cv, fx, py + 122, "Given names / Fornam", "Mira")
    field(cv, fx, py + 160, "Nationality / Rikskap", "Veldorian")
    field(cv, fx, py + 198, "Date of birth / Foddag", "04 Jul 1991")
    field(cv, fx, py + 236, "Place of birth / Fodstad", "Port Sable")
    field(cv, fx, py + 274, "Sex / Kyn", "F")

    # signature under photo
    signature(cv, X(phx + 8), X(phy + phh + 26), X(phw - 16))
    cv.line(X(phx + 4), X(phy + phh + 44), X(phx + phw - 4), X(phy + phh + 44), LABEL, 1)
    draw_text(cv, X(phx + 4), X(phy + phh + 48), "HOLDER'S SIGNATURE", 1.8, LABEL)

    # document fields row
    field(cv, px + 20, py + 356, "Passport No.", "VD4829137")
    field(cv, px + 168, py + 356, "Date of issue", "12 Mar 2023")
    field(cv, px + 300, py + 356, "Date of expiry", "11 Mar 2033")
    field(cv, px + 20, py + 394, "Authority / Stjorn", "Port Sable")
    field(cv, px + 300, py + 394, "Issuing office", "Harbour Registry")

    # endorsements box (the telling detail)
    bx, by, bw, bh = px + 20, py + 438, pw - 40, 86
    cv.frame(X(bx), X(by), X(bw), X(bh), (120, 124, 130), 2)
    draw_text(cv, X(bx + 10), X(by + 8), "ENDORSEMENTS", 2.0, LABEL)
    draw_text(cv, X(bx + 10), X(by + 26), "VALID FOR ALL COUNTRIES EXCEPT", 2.6, VALUE, bold=True)
    draw_text(cv, X(bx + 10), X(by + 44), "THE TIDEWATER FREE PORTS", 2.6, VALUE, bold=True)
    draw_text(cv, X(bx + 10), X(by + 62), "HOLDER IS A REGISTERED HARBOUR PILOT - CLASS II", 1.8, VALUE)
    fee = make_stamp("VELDOR", "FEE PAID", "40 MARKS", "PORT SABLE", (178, 44, 44))
    fee.blit_rotated(cv, X(bx + bw - 86), X(by + 44), -9, strength=0.8)

    # perforated number down left edge
    perforated_number(cv, px + 7, py + 96, "VD4829137")

    # MRZ
    l1, l2 = build_mrz()
    mrz_scale = (pw - 36) * S / (44 * 6)
    draw_text(cv, X(px + 18), X(py + ph - 58), l1, mrz_scale, (20, 24, 34))
    draw_text(cv, X(px + 18), X(py + ph - 34), l2, mrz_scale, (20, 24, 34))


def visa_sticker(cv, raw, x, y, w, h):
    # pale security gradient
    for i in range(X(h)):
        t = i / X(h)
        cv.rect(X(x), X(y) + i, X(w), 1, mix((205, 226, 205), (190, 212, 232), t))
    cv.frame(X(x), X(y), X(w), X(h), (90, 110, 130), 2)
    draw_text_c(cv, X(x + w // 2), X(y + 8), "MERIDIAN ISLES", 3.4, NAVY, bold=True)
    draw_text_c(cv, X(x + w // 2), X(y + 28), "VISA  -  MULTIPLE ENTRY", 2.2, (60, 80, 110))
    blit_photo(cv, raw, X(x + 12), X(y + 48), X(76), X(95))
    cv.frame(X(x + 12), X(y + 48), X(76), X(95), (90, 110, 130), 2)
    fx = x + 100
    field(cv, fx, y + 50, "Surname", "Kovac")
    field(cv, fx, y + 84, "Given name", "Mira")
    field(cv, fx, y + 118, "Passport No.", "VD4829137")
    draw_text(cv, X(x + 12), X(y + h - 44), "VALID 01 NOV 2024 - 31 OCT 2025", 2.4, VALUE, bold=True)
    draw_text(cv, X(x + 12), X(y + h - 26), "ISSUED AT PORT SABLE  28 OCT 2024", 2.0, VALUE)
    draw_text(cv, X(x + 12), X(y + h - 12), "VMVLDKOVAC<<MIRA<<<<<<<<VD4829137", 1.7, (40, 50, 70))


def visas_page(cv, raw, px, py, pw, ph, rng):
    paper_base(cv, px, py, pw, ph, rng)
    draw_text(cv, X(px + 20), X(py + 14), "VISAS", 3.4, NAVY, bold=True)
    draw_text(cv, X(px + pw - 150), X(py + 18), "VELDOR - VD4829137", 1.9, LABEL)
    visa_sticker(cv, raw, px + 20, py + 44, pw - 40, 196)

    blue = (36, 84, 160)
    green = (28, 128, 84)
    red = (178, 44, 44)
    stamps = [
        make_stamp("KARST REPUBLIC", "ENTRY", "18 JUN 2023", "GREYHAVEN", blue),
        make_stamp("KARST REPUBLIC", "EXIT", "02 JUL 2023", "GREYHAVEN", blue, "round"),
        make_stamp("MERIDIAN ISLES", "ENTRY", "09 NOV 2024", "PORT AZURE", green),
        make_stamp("MERIDIAN ISLES", "EXIT", "21 DEC 2024", "PORT AZURE", green, "round"),
        make_stamp("SOLMARIA", "ENTRY", "14 MAY 2025", "CALA VERDE", red),
        make_stamp("SOLMARIA", "EXIT", "28 MAY 2025", "CALA VERDE", red, "round"),
    ]
    spots = [(px + 116, py + 300, -6), (px + 322, py + 296, 8),
             (px + 112, py + 404, 5), (px + 326, py + 408, -7),
             (px + 118, py + 508, -4), (px + 320, py + 512, 6)]
    for st, (sx, sy, ang) in zip(stamps, spots):
        st.blit_rotated(cv, X(sx), X(sy), ang, strength=0.85)

    # pencilled margin note
    draw_text(cv, X(px + 24), X(py + ph - 30), "harbour dues paid - m.k.", 2.2, (120, 122, 126))


def downsample(cv):
    out = bytearray(W * H * 3)
    src = cv.px
    sw = DW * 3
    for y in range(H):
        r0 = (2 * y) * sw
        r1 = r0 + sw
        o = y * W * 3
        for x in range(W):
            i0 = r0 + x * 6
            i1 = r1 + x * 6
            out[o] = (src[i0] + src[i0 + 3] + src[i1] + src[i1 + 3]) >> 2
            out[o + 1] = (src[i0 + 1] + src[i0 + 4] + src[i1 + 1] + src[i1 + 4]) >> 2
            out[o + 2] = (src[i0 + 2] + src[i0 + 5] + src[i1 + 2] + src[i1 + 5]) >> 2
            o += 3
    return bytes(out)


def main():
    rng = random.Random(20261121)
    raw = load_portrait()
    cv = Canvas(DW, DH, (34, 40, 56))
    # desk gradient + vignette
    for i in range(DH):
        t = i / DH
        cv.rect(0, i, DW, 1, mix((44, 52, 70), (24, 28, 40), t))
    # passport shadow + pages
    px, py, pw, ph = 42, 172, 452, 640
    cv.rect(X(px - 8), X(py + 10), X(pw * 2 + 52), X(ph), (16, 18, 26))
    data_page(cv, raw, px, py, pw, ph, rng)
    visas_page(cv, raw, px + pw + 36, py, pw, ph, rng)
    # centre fold shadow + ridge highlight
    fold = px + pw + 18
    for i in range(26):
        a = 0.20 * (1 - i / 26)
        cv.rect_blend(X(fold - i), X(py), X(1), X(ph), (60, 58, 50), a)
        cv.rect_blend(X(fold + i), X(py), X(1), X(ph), (60, 58, 50), a)
    cv.rect_blend(X(fold), X(py), X(2), X(ph), (255, 255, 250), 0.25)
    # edge curl shading
    for i in range(10):
        cv.rect_blend(X(px + i), X(py), X(1), X(ph), (90, 88, 80), 0.10 * (1 - i / 10))
        cv.rect_blend(X(px + pw * 2 + 36 - i), X(py), X(1), X(ph), (90, 88, 80), 0.10 * (1 - i / 10))

    out_dir = "/output"
    os.makedirs(out_dir, exist_ok=True)
    write_png(os.path.join(out_dir, "entry.png"), W, H, downsample(cv))


if __name__ == "__main__":
    main()
