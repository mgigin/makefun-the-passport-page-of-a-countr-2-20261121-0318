#!/usr/bin/env python3
"""The Passport Page of a Country That Isn't There.

Draws one open passport spread for the invented Republic of Veldor and writes
it to /output/entry.png. Standard library only: the PNG is encoded by hand
(zlib + struct) and all type is set in an embedded 5x7 bitmap face, so the
program runs in a bare sandbox with no network and no third-party packages.

Everything on the page agrees with itself: the passport was issued in
Port Sable on 12 MAR 2023, and every border stamp on the facing page is
dated after that, alternating departure and arrival the way a real travel
history does.
"""
import math
import os
import struct
import zlib

W = H = 1024

# --------------------------------------------------------------------------
# 5x7 bitmap face. Each glyph is 7 rows of 5 bits, top row first.
# --------------------------------------------------------------------------
GLYPHS = {
    "A": [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "B": [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E],
    "C": [0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E],
    "D": [0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C],
    "E": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F],
    "F": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10],
    "G": [0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F],
    "H": [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "I": [0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "J": [0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C],
    "K": [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11],
    "L": [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F],
    "M": [0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11],
    "N": [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11],
    "O": [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "P": [0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10],
    "Q": [0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D],
    "R": [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
    "S": [0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E],
    "T": [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
    "U": [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "V": [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04],
    "W": [0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11],
    "X": [0x11, 0x0A, 0x04, 0x04, 0x04, 0x0A, 0x11],
    "Y": [0x11, 0x0A, 0x04, 0x04, 0x04, 0x04, 0x04],
    "Z": [0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F],
    "0": [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E],
    "1": [0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "2": [0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F],
    "3": [0x0E, 0x11, 0x01, 0x06, 0x01, 0x11, 0x0E],
    "4": [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02],
    "5": [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E],
    "6": [0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E],
    "7": [0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08],
    "8": [0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E],
    "9": [0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C],
    " ": [0, 0, 0, 0, 0, 0, 0],
    ".": [0, 0, 0, 0, 0, 0x0C, 0x0C],
    ",": [0, 0, 0, 0, 0x0C, 0x04, 0x08],
    ":": [0, 0x0C, 0x0C, 0, 0x0C, 0x0C, 0],
    "/": [0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10],
    "-": [0, 0, 0, 0x1F, 0, 0, 0],
    "<": [0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02],
    "(": [0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02],
    ")": [0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08],
    "'": [0x04, 0x04, 0x08, 0, 0, 0, 0],
    "+": [0, 0x04, 0x04, 0x1F, 0x04, 0x04, 0],
    "*": [0, 0x15, 0x0E, 0x1F, 0x0E, 0x15, 0],
}


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bytes(bg) * (w * h))
        self.clip = None  # (x0, y0, x1, y1) or None

    def _inside(self, x, y):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return False
        if self.clip:
            x0, y0, x1, y1 = self.clip
            return x0 <= x < x1 and y0 <= y < y1
        return True

    def set(self, x, y, c):
        if self._inside(x, y):
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(c)

    def blend(self, x, y, c, a):
        if self._inside(x, y):
            i = (y * self.w + x) * 3
            for k in range(3):
                self.px[i + k] = int(self.px[i + k] * (1 - a) + c[k] * a)

    def rect(self, x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(self.h, y1)):
            base = y * self.w * 3
            for x in range(max(0, x0), min(self.w, x1)):
                i = base + x * 3
                self.px[i:i + 3] = bytes(c)

    def frame(self, x0, y0, x1, y1, c, t=2):
        self.rect(x0, y0, x1, y0 + t, c)
        self.rect(x0, y1 - t, x1, y1, c)
        self.rect(x0, y0, x0 + t, y1, c)
        self.rect(x1 - t, y0, x1, y1, c)

    def ellipse(self, cx, cy, rx, ry, c, filled=True, t=2):
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
                if filled and d <= 1.0:
                    self.set(x, y, c)
                elif not filled and 1.0 - t / max(rx, ry) <= d <= 1.0:
                    self.set(x, y, c)

    def line(self, x0, y0, x1, y1, c, t=2):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i // n
            y = y0 + (y1 - y0) * i // n
            for dy in range(t):
                for dx in range(t):
                    self.set(x + dx, y + dy, c)

    def text(self, x, y, s, c, scale=2, tracking=1):
        cx = x
        for ch in s.upper():
            g = GLYPHS.get(ch, GLYPHS[" "])
            for r in range(7):
                for col in range(5):
                    if g[r] & (0x10 >> col):
                        for dy in range(scale):
                            for dx in range(scale):
                                self.set(cx + col * scale + dx,
                                         y + r * scale + dy, c)
            cx += (5 + tracking) * scale
        return cx

    def text_w(self, s, scale=2, tracking=1):
        return len(s) * (5 + tracking) * scale

    def text_c(self, cx, y, s, c, scale=2, tracking=1):
        self.text(cx - self.text_w(s, scale, tracking) // 2, y, s, c, scale,
                  tracking)

    def text_rot(self, x, y, s, c, scale, ang, tracking=1):
        """Draw text rotated by ang degrees about (x, y)."""
        rad = math.radians(ang)
        ca, sa = math.cos(rad), math.sin(rad)
        cx = 0
        for ch in s.upper():
            g = GLYPHS.get(ch, GLYPHS[" "])
            for r in range(7):
                for col in range(5):
                    if g[r] & (0x10 >> col):
                        for dy in range(scale):
                            for dx in range(scale):
                                lx = cx + col * scale + dx
                                ly = r * scale + dy
                                rx = int(x + lx * ca - ly * sa)
                                ry = int(y + lx * sa + ly * ca)
                                self.set(rx, ry, c)
            cx += (5 + tracking) * scale

    def stamp(self, cx, cy, lines, c, ang, scale=2, w=None):
        """A rectangular border stamp, rotated, inked at partial strength."""
        tw = max(self.text_w(s, scale) for s in lines)
        th = len(lines) * (7 * scale + 4)
        w = w or tw + 24
        h = th + 20
        rad = math.radians(ang)
        ca, sa = math.cos(rad), math.sin(rad)

        def put(lx, ly, col, a=0.85):
            rx = int(cx + lx * ca - ly * sa)
            ry = int(cy + lx * sa + ly * ca)
            self.blend(rx, ry, col, a)

        for lx in range(-w // 2, w // 2):
            for t in range(3):
                put(lx, -h // 2 + t, c)
                put(lx, h // 2 - t, c)
        for ly in range(-h // 2, h // 2):
            for t in range(3):
                put(-w // 2 + t, ly, c)
                put(w // 2 - t, ly, c)
        y = -h // 2 + 10
        for s in lines:
            lx = -self.text_w(s, scale) // 2
            for ch in s.upper():
                g = GLYPHS.get(ch, GLYPHS[" "])
                for r in range(7):
                    for col in range(5):
                        if g[r] & (0x10 >> col):
                            for dy in range(scale):
                                for dx in range(scale):
                                    put(lx + col * scale + dx,
                                        y + r * scale + dy, c)
                lx += 6 * scale
            y += 7 * scale + 4

    def png(self, path):
        raw = bytearray()
        stride = self.w * 3
        for y in range(self.h):
            raw.append(0)
            raw += self.px[y * stride:(y + 1) * stride]

        def chunk(tag, data):
            c = struct.pack(">I", len(data)) + tag + data
            return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

        ihdr = struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0)
        data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                + chunk(b"IEND", b""))
        with open(path, "wb") as f:
            f.write(data)
        return len(data)


# Palette: security-paper cream, deep teal ink, stamp inks.
PAPER = (238, 232, 214)
PAPER2 = (232, 224, 200)
INK = (24, 52, 58)
INK_SOFT = (70, 96, 100)
GOLD = (150, 118, 52)
BLUE = (38, 64, 140)
RED = (148, 44, 40)
GREEN = (36, 110, 74)
GREY = (120, 118, 108)


def guilloche(cv, x0, y0, x1, y1, c):
    """Faint overlapping wave lines, the way security paper is printed."""
    for k in range(0, y1 - y0, 9):
        for x in range(x0, x1, 2):
            y = y0 + k + int(3 * math.sin((x - x0) / 26.0 + k))
            cv.blend(x, y, c, 0.10)


def portrait(cv, x0, y0, x1, y1):
    """A flat duotone portrait: head, hair, shoulders, neutral ground."""
    cv.clip = (x0, y0, x1, y1)
    cv.rect(x0, y0, x1, y1, (196, 205, 200))
    for y in range(y0, y1):
        t = (y - y0) / (y1 - y0)
        cv.rect(x0, y, x1, y + 1,
                (int(196 - 30 * t), int(205 - 28 * t), int(200 - 24 * t)))
    cx = (x0 + x1) // 2
    skin = (206, 168, 138)
    skin_d = (178, 140, 112)
    hair = (58, 44, 34)
    # shoulders / coat
    cv.ellipse(cx, y1 + 30, (x1 - x0) // 2, 90, (44, 58, 66))
    cv.rect(cx - 16, y1 - 78, cx + 16, y1 - 30, skin_d)          # neck
    cv.ellipse(cx, y0 + 108, 62, 78, skin)                        # head
    cv.ellipse(cx, y0 + 74, 66, 52, hair)                         # hair mass
    cv.ellipse(cx, y0 + 96, 60, 62, skin)                         # face
    cv.rect(cx - 66, y0 + 60, cx - 52, y0 + 168, hair)            # hair sides
    cv.rect(cx + 52, y0 + 60, cx + 66, y0 + 168, hair)
    # features
    dark = (40, 34, 30)
    cv.rect(cx - 34, y0 + 108, cx - 12, y0 + 113, dark)           # brows
    cv.rect(cx + 12, y0 + 108, cx + 34, y0 + 113, dark)
    cv.ellipse(cx - 23, y0 + 124, 7, 4, dark)
    cv.ellipse(cx + 23, y0 + 124, 7, 4, dark)
    cv.line(cx, y0 + 128, cx - 3, y0 + 148, skin_d, 3)            # nose
    cv.line(cx - 3, y0 + 148, cx + 5, y0 + 150, skin_d, 3)
    cv.line(cx - 14, y0 + 164, cx + 14, y0 + 164, (140, 84, 76), 3)  # mouth
    cv.clip = None
    cv.frame(x0, y0, x1, y1, INK_SOFT, 2)


def field(cv, x, y, label, value, scale=2):
    cv.text(x, y, label, INK_SOFT, 1)
    cv.text(x, y + 11, value, INK, scale)
    return y + 11 + 7 * scale + 10


def main():
    cv = Canvas(W, H, (52, 48, 44))
    # The open booklet: two pages and a centre fold.
    cv.rect(28, 28, 996, 996, PAPER)
    cv.rect(28, 28, 512, 996, PAPER)
    cv.rect(512, 28, 996, 996, PAPER2)
    guilloche(cv, 40, 40, 500, 984, INK)
    guilloche(cv, 524, 40, 984, 984, INK)
    for x in range(500, 525):  # fold shadow
        a = 0.16 * (1 - abs(x - 512) / 13)
        for y in range(28, 996):
            cv.blend(x, y, (60, 56, 48), a)
    cv.frame(28, 28, 996, 996, (90, 84, 70), 3)

    # ---------------- left page: the data page ----------------
    cv.text_c(270, 58, "REPUBLIC OF VELDOR", INK, 3)
    cv.text_c(270, 92, "PASSPORT", GOLD, 3)
    cv.rect(70, 128, 470, 131, GOLD)
    cv.text_c(270, 140, "VELDORIAN / ENGLISH", INK_SOFT, 1)

    portrait(cv, 70, 168, 232, 372)
    cv.text(70, 382, "NO. VL 4471 9023", INK, 2)

    x = 258
    y = 168
    y = field(cv, x, y, "SURNAME / NOM", "KOVAC")
    y = field(cv, x, y, "GIVEN NAMES", "MIRA ANJA")
    y = field(cv, x, y, "NATIONALITY", "VELDORIAN")
    y = field(cv, x, y, "DATE OF BIRTH", "04 JUL 1991")
    y = field(cv, x, y, "PLACE OF BIRTH", "PORT SABLE")
    y = field(cv, x, y, "SEX", "F")

    y = 420
    y = field(cv, 70, y, "DATE OF ISSUE", "12 MAR 2023")
    y = field(cv, 258, 420, "DATE OF EXPIRY", "11 MAR 2033")
    y = field(cv, 70, y, "ISSUING AUTHORITY", "PORT SABLE PASSPORT OFFICE")
    y = field(cv, 70, y, "TYPE", "P")
    y = field(cv, 258, y - 41, "CODE", "VLD")

    # The telling detail: a visa condition that says what kind of place
    # Veldor is — a harbour republic that keeps its free ports closed.
    cv.frame(70, 560, 470, 636, INK_SOFT, 2)
    cv.text(84, 572, "VALID FOR ALL COUNTRIES", INK, 2)
    cv.text(84, 592, "EXCEPT THE TIDEWATER", INK, 2)
    cv.text(84, 612, "FREE PORTS", INK, 2)
    cv.text(84, 648, "FEE PAID 40 KRONA - RECEIPT 8814", INK_SOFT, 1)
    cv.text(84, 664, "HOLDER IS A REGISTERED HARBOUR PILOT", INK_SOFT, 1)

    # Signature line
    cv.line(70, 740, 300, 740, INK_SOFT, 2)
    cv.text(70, 748, "SIGNATURE OF HOLDER", INK_SOFT, 1)
    cv.text(96, 712, "MIRA KOVAC", INK, 2)
    # Issuing stamp, overlapping the portrait corner as real ones do.
    cv.ellipse(228, 356, 44, 44, BLUE, filled=False, t=3)
    cv.text_c(228, 340, "PORT", BLUE, 1)
    cv.text_c(228, 350, "SABLE", BLUE, 1)
    cv.text_c(228, 362, "2023", BLUE, 1)

    # Machine-readable strip
    cv.rect(70, 856, 470, 948, (250, 248, 240))
    cv.frame(70, 856, 470, 948, INK_SOFT, 2)
    cv.text(80, 872, "P<VLDKOVAC<<MIRA<ANJA<<<<<<<<<<<<<", INK, 2)
    cv.text(80, 904, "VL44719023VLD9107042F3303118<<<<04", INK, 2)
    cv.text_c(270, 962, "2", INK_SOFT, 2)

    # ---------------- right page: the travel history ----------------
    cv.text_c(754, 58, "VISAS / STAMPS", INK, 2)
    cv.rect(566, 92, 942, 95, GOLD)

    # Issued 12 MAR 2023 in Port Sable. Every stamp is later, and each
    # departure is answered by an arrival, in order.
    cv.stamp(700, 210, ["KARST REPUBLIC", "ARRIVAL", "03 JUN 2023",
                        "BY SEA - BERTH 9"], BLUE, -6)
    cv.stamp(820, 350, ["KARST REPUBLIC", "DEPARTURE", "17 JUN 2023"],
             RED, 4)
    cv.stamp(680, 470, ["VELDOR - PORT SABLE", "ARRIVAL", "18 JUN 2023",
                        "HOME PORT"], GREEN, -3)
    cv.stamp(830, 610, ["MERIDIAN ISLES", "ARRIVAL", "09 NOV 2024",
                        "90 DAYS - NO WORK"], BLUE, 7)
    cv.stamp(690, 760, ["MERIDIAN ISLES", "DEPARTURE", "02 DEC 2024"],
             RED, -5)
    cv.stamp(820, 880, ["VELDOR - PORT SABLE", "ARRIVAL", "03 DEC 2024",
                        "HOME PORT"], GREEN, 3)

    # A pencilled note in the margin, the way officers leave them.
    cv.text_rot(560, 940, "PILOT LICENCE SEEN 03 DEC 2024", GREY, 1, -90)
    cv.text_c(754, 962, "3", INK_SOFT, 2)

    os.makedirs("/output", exist_ok=True)
    n = cv.png("/output/entry.png")
    print("wrote /output/entry.png", n, "bytes")


if __name__ == "__main__":
    main()
