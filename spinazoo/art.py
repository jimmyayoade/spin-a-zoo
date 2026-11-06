"""Spin-A-Zoo! artwork, drawn in code.

Everything is drawn at twice the target size and smooth-scaled down, which
gives clean edges without pygame's slower anti-aliased primitives. Results are
cached per size, so each picture is drawn once per screen layout.

A PNG in the game's art/ folder named after an animal (elephant.png, cat.png,
eagle.png, lion.png, bear.png) replaces that animal's drawing.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import pygame

import rules

SS = 2  # supersampling factor
ART_DIR = Path(__file__).resolve().parent / "art"
# Fredoka SemiBold (SIL Open Font License, fonts/OFL.txt): round, chunky
# letters that young players read easily.
FONT_PATH = Path(__file__).resolve().parent / "fonts" / "Fredoka-SemiBold.ttf"
FONT_SCALE = 0.75  # Fredoka is wider than pygame's font at the same size

INK = (40, 32, 48)
WHITE = (255, 255, 255)

SQUARE_COLORS = {
    "green": (102, 187, 106),
    "blue": (66, 165, 245),
    "purple": (171, 71, 188),
    "red": (239, 83, 80),
    "yellow": (255, 213, 79),
}
TILE_COLORS = {
    "green": (27, 128, 52),
    "blue": (21, 90, 190),
    "yellow": (250, 175, 0),
    "red": (190, 30, 40),
}


@lru_cache(maxsize=64)
def font(px: int) -> pygame.font.Font:
    """The game's font at about the size pygame's own font would be at px."""
    try:
        return pygame.font.Font(str(FONT_PATH), max(8, int(px * FONT_SCALE)))
    except (OSError, pygame.error):
        return pygame.font.Font(None, px)  # font file missing: still playable


def shade(color, f):
    return tuple(max(0, min(255, int(c * f))) for c in color)


def fast(surf: pygame.Surface) -> pygame.Surface:
    """Convert to the screen's pixel format (much quicker to draw), once a
    screen exists."""
    if pygame.display.get_surface() is None:
        return surf
    return surf.convert_alpha() if surf.get_flags() & pygame.SRCALPHA else surf.convert()


def finish(surf: pygame.Surface, size: int) -> pygame.Surface:
    """Scale a supersampled surface down to its final size."""
    return fast(pygame.transform.smoothscale(surf, (size, size)))


def canvas(size: int) -> pygame.Surface:
    return pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)


# --- shapes ------------------------------------------------------------------

def shape_points(shape: str, cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """Polygon points for a board shape of outer radius r (circle excluded)."""
    def ring(n, radius, start=-90.0, step=None):
        step = step or 360.0 / n
        return [(cx + radius * math.cos(math.radians(start + i * step)),
                 cy + radius * math.sin(math.radians(start + i * step))) for i in range(n)]
    if shape == "square":
        return ring(4, r * 0.95, start=-45)
    if shape == "triangle":
        # nudged down so it sits visually centred
        return [(x, y + r * 0.15) for x, y in ring(3, r * 1.08)]
    if shape == "hexagon":
        return ring(6, r, start=0)
    if shape == "star":
        outer = ring(5, r * 1.05)
        inner = ring(5, r * 0.5, start=-90 + 36)
        return [p for pair in zip(outer, inner) for p in pair]
    raise ValueError(shape)


def draw_shape(surf, shape, cx, cy, r, fill, outline=INK, width=0):
    if shape == "circle":
        pygame.draw.circle(surf, fill, (cx, cy), r * 0.92)
        if width:
            pygame.draw.circle(surf, outline, (cx, cy), r * 0.92, width)
        return
    pts = shape_points(shape, cx, cy, r)
    pygame.draw.polygon(surf, fill, pts)
    if width:
        pygame.draw.polygon(surf, outline, pts, width)


@lru_cache(maxsize=64)
def shape_icon(shape: str, size: int, fill=WHITE) -> pygame.Surface:
    s = canvas(size)
    S = size * SS
    draw_shape(s, shape, S / 2, S / 2, S * 0.42, fill, INK, max(2, S // 22))
    return finish(s, size)


# --- patterns ----------------------------------------------------------------

def _note(surf, color, x, y, u):
    pygame.draw.ellipse(surf, color, (x - 1.4 * u, y - 1.0 * u, 2.8 * u, 2.0 * u))
    pygame.draw.line(surf, color, (x + 1.2 * u, y), (x + 1.2 * u, y - 4.5 * u), max(1, int(u * 0.6)))
    pygame.draw.line(surf, color, (x + 1.2 * u, y - 4.5 * u), (x + 3.0 * u, y - 3.0 * u), max(1, int(u * 0.7)))


def _leaf(surf, color, x, y, u, angle):
    pts = []
    for i in range(13):
        t = i / 12
        # leaf outline: two arcs meeting at the tips
        a = math.pi * t
        px, py = -3 * u + 6 * u * t, 1.6 * u * math.sin(a)
        pts.append((px, py))
    pts += [(px, -py) for px, py in reversed(pts)]
    ca, sa = math.cos(angle), math.sin(angle)
    pts = [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.line(surf, shade(color, 0.8), pts[0], pts[12], max(1, int(u * 0.35)))


def draw_pattern(surf, pattern, rect, color, unit=None):
    """Fill rect with a pattern. unit sets its scale (default: 1/30 of the
    width, which suits a board square); larger areas pass a unit to keep the
    pattern the same size instead of stretching it."""
    x0, y0, w, h = rect
    u = unit or w / 30
    clip = surf.get_clip()
    surf.set_clip(pygame.Rect(rect).clip(clip) if clip else pygame.Rect(rect))
    if pattern == "stripes":
        step = 6 * u
        x = x0 - h - step
        while x < x0 + w + step:
            pygame.draw.line(surf, color, (x, y0), (x + h, y0 + h), max(2, int(1.9 * u)))
            x += step
    elif pattern == "dots":
        step = 6 * u
        for row in range(int(h / step) + 2):
            off = step / 2 if row % 2 else 0
            for col in range(int(w / step) + 2):
                pygame.draw.circle(surf, color, (x0 + col * step + off, y0 + row * step + step / 2), 1.36 * u)
    elif pattern == "zigzag":
        step, seg = 6 * u, 3 * u
        for row in range(int(h / step) + 2):
            y = y0 + row * step + step / 2
            n = int(w / seg) + 3
            pts = [(x0 - seg + i * seg, y + (1.6 * u if i % 2 else -1.6 * u)) for i in range(n)]
            pygame.draw.lines(surf, color, False, pts, max(2, int(1.07 * u)))
    elif pattern == "notes":
        step = 7.5 * u
        for row in range(int(h / step) + 2):
            off = step / 2 if row % 2 else 0
            for col in range(int(w / step) + 2):
                _note(surf, color, x0 + col * step + off - step / 4, y0 + row * step + step * 0.55, u)
    elif pattern == "leaves":
        step = 7.5 * u
        for row in range(int(h / step) + 2):
            off = step / 2 if row % 2 else 0
            for col in range(int(w / step) + 2):
                _leaf(surf, color, x0 + col * step + off - step / 4, y0 + row * step + step / 2, u,
                      math.radians(35 if (row + col) % 2 else -35))
    else:
        surf.set_clip(clip)
        raise ValueError(pattern)
    surf.set_clip(clip)


@lru_cache(maxsize=64)
def pattern_swatch(pattern: str, size: int) -> pygame.Surface:
    """A round sample of a pattern, for the pattern spinner."""
    s = canvas(size)
    S = size * SS
    body = pygame.Surface((S, S), pygame.SRCALPHA)
    body.fill((236, 230, 240))
    draw_pattern(body, pattern, (0, 0, S, S), (110, 96, 120))
    mask = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(mask, WHITE, (S / 2, S / 2), S * 0.44)
    body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(body, (0, 0))
    pygame.draw.circle(s, INK, (S / 2, S / 2), S * 0.44, max(2, S // 24))
    return finish(s, size)


# --- animals -----------------------------------------------------------------

def _draw_animal(s: pygame.Surface, name: str) -> None:
    S = s.get_width()
    u = S / 100

    def P(*pts):
        return [(x * u, y * u) for x, y in pts]

    def R(x, y, w, h):
        return pygame.Rect(round(x * u), round(y * u), round(w * u), round(h * u))

    def C(x, y):
        return (x * u, y * u)

    line = max(2, round(2.2 * u))

    if name == "elephant":
        grey, dark, pink = (160, 166, 178), (120, 126, 140), (226, 170, 182)
        for x in (2, 54):  # big ears behind the head
            pygame.draw.ellipse(s, grey, R(x, 18, 44, 56))
            pygame.draw.ellipse(s, INK, R(x, 18, 44, 56), line)
            pygame.draw.ellipse(s, pink, R(x + 8, 28, 28, 36))
        pygame.draw.ellipse(s, grey, R(24, 14, 52, 58))
        pygame.draw.ellipse(s, INK, R(24, 14, 52, 58), line)
        for x0, x1 in ((40, 31), (60, 69)):  # tusks
            tusk = P((x0 - 3, 60), (x0 + 3, 62), (x1, 76))
            pygame.draw.polygon(s, (252, 248, 232), tusk)
            pygame.draw.polygon(s, INK, tusk, max(1, round(1.2 * u)))
        trunk = P((42, 52), (58, 52), (57, 74), (60, 84), (66, 88), (63, 95), (54, 91), (48, 80), (44, 66))
        pygame.draw.polygon(s, grey, trunk)
        pygame.draw.polygon(s, INK, trunk, line)
        for y in (62, 69, 76):
            pygame.draw.line(s, dark, C(46, y), C(55, y), max(1, round(u)))
        for ex in (39, 61):
            pygame.draw.circle(s, (25, 22, 30), C(ex, 42), 4 * u)
            pygame.draw.circle(s, WHITE, C(ex - 1.2, 40.8), 1.3 * u)
    elif name == "cat":
        black, white, pink = (30, 28, 34), (250, 250, 250), (240, 150, 170)
        for ear, inner in ((P((16, 44), (22, 2), (46, 24)), P((23, 34), (25, 12), (38, 25))),
                           (P((84, 44), (78, 2), (54, 24)), P((77, 34), (75, 12), (62, 25)))):
            pygame.draw.polygon(s, black, ear)
            pygame.draw.polygon(s, pink, inner)
        pygame.draw.ellipse(s, black, R(14, 18, 72, 68))
        pygame.draw.polygon(s, white, P((50, 32), (41, 56), (59, 56)))
        pygame.draw.ellipse(s, white, R(30, 52, 40, 32))
        for ex in (36, 64):
            pygame.draw.ellipse(s, (120, 200, 80), R(ex - 7, 38, 14, 15))
            pygame.draw.ellipse(s, (10, 10, 10), R(ex - 1.6, 39, 3.2, 13))
        pygame.draw.polygon(s, pink, P((45, 57), (55, 57), (50, 63)))
        pygame.draw.line(s, INK, C(50, 63), C(50, 68), max(1, round(1.2 * u)))
        pygame.draw.arc(s, INK, R(42, 63, 8, 8), math.pi, 2 * math.pi, max(1, round(1.2 * u)))
        pygame.draw.arc(s, INK, R(50, 63, 8, 8), math.pi, 2 * math.pi, max(1, round(1.2 * u)))
        for y, dy in ((62, -3), (66, 0), (70, 3)):
            pygame.draw.line(s, (200, 200, 200), C(36, y), C(10, y + dy), max(1, round(u)))
            pygame.draw.line(s, (200, 200, 200), C(64, y), C(90, y + dy), max(1, round(u)))
    elif name == "eagle":
        brown, white, yellow = (95, 60, 30), (250, 250, 245), (255, 190, 30)
        pygame.draw.ellipse(s, brown, R(6, 72, 88, 52))
        pygame.draw.ellipse(s, white, R(20, 10, 60, 70))
        pygame.draw.ellipse(s, INK, R(20, 10, 60, 70), line)
        for ex, sx in ((37, 1), (63, -1)):
            pygame.draw.circle(s, (255, 210, 60), C(ex, 40), 5.5 * u)
            pygame.draw.circle(s, (10, 10, 10), C(ex, 40), 2.8 * u)
            pygame.draw.line(s, (90, 90, 95), C(ex - 9 * sx, 31), C(ex + 7 * sx, 36), max(2, round(3 * u)))
        beak = P((38, 50), (62, 50), (61, 62), (52, 80), (49, 72), (40, 62))
        pygame.draw.polygon(s, yellow, beak)
        pygame.draw.polygon(s, INK, beak, max(1, round(1.4 * u)))
        pygame.draw.line(s, INK, C(42, 62), C(59, 62), max(1, round(1.2 * u)))
    elif name == "lion":
        mane, face, muzzle = (196, 100, 30), (240, 185, 95), (252, 228, 175)
        pts = []
        for i in range(24):
            a = math.radians(i * 15)
            rad = 48 if i % 2 else 40
            pts.append((50 + rad * math.cos(a), 52 + rad * math.sin(a)))
        pygame.draw.polygon(s, mane, P(*pts))
        pygame.draw.polygon(s, INK, P(*pts), line)
        for ex in (30, 70):
            pygame.draw.circle(s, face, C(ex, 28), 9 * u)
            pygame.draw.circle(s, (200, 130, 70), C(ex, 28), 4.5 * u)
        pygame.draw.ellipse(s, face, R(25, 24, 50, 58))
        for mx in (44, 56):
            pygame.draw.circle(s, muzzle, C(mx, 66), 9 * u)
        pygame.draw.polygon(s, (110, 60, 40), P((44, 56), (56, 56), (50, 63)))
        for ex in (40, 60):
            pygame.draw.circle(s, (20, 15, 10), C(ex, 45), 4 * u)
            pygame.draw.circle(s, WHITE, C(ex - 1.2, 43.8), 1.3 * u)
        pygame.draw.line(s, INK, C(50, 63), C(50, 69), max(1, round(1.3 * u)))
    elif name == "bear":
        brown, inner, muzzle = (125, 85, 55), (185, 130, 90), (215, 175, 135)
        for ex in (26, 74):
            pygame.draw.circle(s, brown, C(ex, 24), 12 * u)
            pygame.draw.circle(s, INK, C(ex, 24), 12 * u, line)
            pygame.draw.circle(s, inner, C(ex, 24), 6 * u)
        pygame.draw.ellipse(s, brown, R(16, 18, 68, 70))
        pygame.draw.ellipse(s, INK, R(16, 18, 68, 70), line)
        pygame.draw.ellipse(s, muzzle, R(33, 52, 34, 28))
        pygame.draw.ellipse(s, (20, 15, 12), R(42, 54, 16, 11))
        for ex in (36, 64):
            pygame.draw.circle(s, (20, 15, 12), C(ex, 44), 4.2 * u)
            pygame.draw.circle(s, WHITE, C(ex - 1.2, 42.8), 1.3 * u)
        pygame.draw.line(s, INK, C(50, 65), C(50, 71), max(1, round(1.4 * u)))
        pygame.draw.arc(s, INK, R(42, 66, 8, 8), math.pi, 2 * math.pi, max(1, round(1.4 * u)))
        pygame.draw.arc(s, INK, R(50, 66, 8, 8), math.pi, 2 * math.pi, max(1, round(1.4 * u)))
    else:
        raise ValueError(name)


@lru_cache(maxsize=64)
def animal(name: str, size: int) -> pygame.Surface:
    png = ART_DIR / f"{name}.png"
    if png.is_file():
        try:
            img = pygame.image.load(str(png)).convert_alpha()
            return pygame.transform.smoothscale(img, (size, size))
        except pygame.error:
            pass  # unreadable image: fall back to the drawing
    s = canvas(size)
    _draw_animal(s, name)
    return finish(s, size)


# --- board squares -----------------------------------------------------------

@lru_cache(maxsize=64)
def square(sq: rules.Square, size: int) -> pygame.Surface:
    """One board square: colored background, pattern, white shape, animal."""
    S = size * SS
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    bg = SQUARE_COLORS[sq.color]
    radius = S // 10
    body = pygame.Surface((S, S), pygame.SRCALPHA)
    body.fill(bg)
    draw_pattern(body, sq.pattern, (0, 0, S, S), shade(bg, 0.78))
    mask = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.rect(mask, WHITE, (0, 0, S, S), border_radius=radius)
    body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(body, (0, 0))
    pygame.draw.rect(s, shade(bg, 0.6), (0, 0, S, S), max(2, S // 50), border_radius=radius)
    draw_shape(s, sq.shape, S / 2, S / 2, S * 0.43, WHITE, INK, max(3, S // 40))
    out = finish(s, size)
    a = animal(sq.animal, int(size * 0.5))
    out.blit(a, ((size - a.get_width()) // 2, int(size * 0.5 - a.get_height() * 0.48)))
    return fast(out)


# --- tiles -------------------------------------------------------------------

def _player_symbol(s, color, cx, cy, r):
    """White symbol on each tile, so players don't rely on color alone."""
    w = max(2, round(r * 0.22))
    if color == "green":      # plus
        pygame.draw.line(s, WHITE, (cx - r, cy), (cx + r, cy), w * 2)
        pygame.draw.line(s, WHITE, (cx, cy - r), (cx, cy + r), w * 2)
    elif color == "blue":     # diamond
        pygame.draw.polygon(s, WHITE, [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)])
    elif color == "yellow":   # sun
        pygame.draw.circle(s, WHITE, (cx, cy), r * 0.5)
        for i in range(8):
            a = math.radians(i * 45)
            pygame.draw.line(s, WHITE, (cx + r * 0.68 * math.cos(a), cy + r * 0.68 * math.sin(a)),
                             (cx + r * 1.05 * math.cos(a), cy + r * 1.05 * math.sin(a)), w)
    elif color == "red":      # heart
        pygame.draw.circle(s, WHITE, (cx - r * 0.45, cy - r * 0.3), r * 0.5)
        pygame.draw.circle(s, WHITE, (cx + r * 0.45, cy - r * 0.3), r * 0.5)
        pygame.draw.polygon(s, WHITE, [(cx - r * 0.93, cy - r * 0.15), (cx + r * 0.93, cy - r * 0.15),
                                       (cx, cy + r * 0.9)])


@lru_cache(maxsize=32)
def tile(color: str, size: int) -> pygame.Surface:
    s = canvas(size)
    S = size * SS
    c = S / 2
    pygame.draw.circle(s, (0, 0, 0, 70), (c, c + S * 0.04), S * 0.47)
    pygame.draw.circle(s, INK, (c, c), S * 0.47)
    pygame.draw.circle(s, WHITE, (c, c), S * 0.44)
    pygame.draw.circle(s, TILE_COLORS[color], (c, c), S * 0.37)
    pygame.draw.circle(s, shade(TILE_COLORS[color], 1.25), (c, c), S * 0.37, max(2, S // 40))
    _player_symbol(s, color, c, c, S * 0.17)
    return finish(s, size)


# --- spinners ----------------------------------------------------------------

def section_angle(i: int) -> float:
    """Centre of spinner section i, in degrees clockwise from straight up."""
    return i * 45.0


# Each spinner has its own look: rim, arrow and section colours.
SPINNER_STYLE = {
    "color": {"rim": (126, 87, 194), "arrow": (25, 118, 210)},
    "shape": {"rim": (230, 100, 0), "arrow": (25, 118, 210),
              "sections": ((255, 193, 7), (255, 143, 0))},
    "pattern": {"rim": (173, 20, 87), "arrow": (255, 179, 0),
                # notes, stripes, dots, zigzag, leaves: deep section, bright pattern
                "sections": ((216, 27, 96), (106, 27, 154), (0, 121, 107), (230, 74, 25), (40, 53, 147)),
                "ink": ((255, 235, 59), (198, 255, 0), (255, 213, 79), (128, 222, 234), (174, 234, 0))},
    "animal": {"rim": (0, 121, 107), "arrow": (239, 108, 0),
               "sections": ((38, 166, 154), (124, 179, 66))},
}
RAINBOW = ((229, 57, 53), (251, 140, 0), (253, 216, 53), (67, 160, 71), (30, 136, 229), (142, 36, 170))
WILD_BG = (255, 255, 255)
ZOO_BG = (255, 224, 70)


def _wedge(cx, cy, r, a0, a1, r0=0.0):
    """Pie slice from angle a0 to a1 (degrees clockwise from up); r0 > 0 cuts
    out the middle, giving a ring segment."""
    pts = []
    for k in range(17):
        a = math.radians(a0 + (a1 - a0) * k / 16 - 90)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    if r0:
        for k in range(16, -1, -1):
            a = math.radians(a0 + (a1 - a0) * k / 16 - 90)
            pts.append((cx + r0 * math.cos(a), cy + r0 * math.sin(a)))
    else:
        pts.insert(0, (cx, cy))
    return pts


def fancy_text(word: str, px: int, colors=RAINBOW, outline=INK) -> pygame.Surface:
    """Bold text, each letter its own colour, with a dark outline."""
    f = font(px)
    t = max(2, px // 10)
    letters = [(f.render(ch, True, colors[i % len(colors)]), f.render(ch, True, outline))
               for i, ch in enumerate(word)]
    w = sum(img.get_width() for img, _ in letters) + 2 * t
    h = letters[0][0].get_height() + 2 * t
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    x = t
    for img, out in letters:
        for dx in (-t, 0, t):
            for dy in (-t, 0, t):
                if dx or dy:
                    s.blit(out, (x + dx, t + dy))
        s.blit(img, (x, t))
        x += img.get_width()
    return s


def _stack(*surfs: pygame.Surface) -> pygame.Surface:
    w = max(x.get_width() for x in surfs)
    h = sum(x.get_height() for x in surfs) - 4 * (len(surfs) - 1)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    y = 0
    for x in surfs:
        s.blit(x, ((w - x.get_width()) // 2, y))
        y += x.get_height() - 4
    return s


def _along(img: pygame.Surface, angle: float) -> pygame.Surface:
    """Turn text to run along a section (outwards from the hub), never upside down."""
    r = (90 - angle + 180) % 360 - 180
    if abs(r) > 90:
        r += 180
    return pygame.transform.rotozoom(img, r, 1.0)


def _fit(img: pygame.Surface, max_w: float, max_h: float) -> pygame.Surface:
    k = min(1.0, max_w / img.get_width(), max_h / img.get_height())
    if k >= 1.0:
        return img
    return pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k))))


@lru_cache(maxsize=16)
def dial(feature: str, size: int) -> pygame.Surface:
    """A spinner face (without its arrow)."""
    S = size * SS
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    c = S / 2
    style = SPINNER_STYLE[feature]
    rim_out, r = S * 0.495, S * 0.43  # coloured rim between r and rim_out
    sections = rules.spinner_sections(feature)
    values = rules.VALUES[feature]

    # rim with carnival lights
    pygame.draw.circle(s, INK, (c, c), rim_out)
    pygame.draw.circle(s, style["rim"], (c, c), rim_out - S * 0.008)
    for k in range(24):
        a = math.radians(k * 15 + 7.5 - 90)
        rad = (r + rim_out) / 2
        pygame.draw.circle(s, (255, 248, 200) if k % 2 else WHITE,
                           (c + rad * math.cos(a), c + rad * math.sin(a)), S * 0.012)

    for i, sec in enumerate(sections):
        a = section_angle(i)
        wedge = _wedge(c, c, r, a - 22.5, a + 22.5)
        if sec == rules.WILD:
            pygame.draw.polygon(s, WILD_BG, wedge)
            # a rainbow band along the outer edge
            for k, col in enumerate(RAINBOW):
                band = _wedge(c, c, r - k * S * 0.009, a - 22.5, a + 22.5, r - (k + 1) * S * 0.009)
                pygame.draw.polygon(s, col, band)
        elif sec == rules.ZOO:
            pygame.draw.polygon(s, ZOO_BG, wedge)
            for k in range(9):  # sunburst rays
                ra = a - 22.5 + k * 5
                pygame.draw.polygon(s, (255, 183, 30), _wedge(c, c, r, ra, ra + 2.5))
        elif feature == "color":
            pygame.draw.polygon(s, SQUARE_COLORS[sec], wedge)
        elif feature == "pattern":
            k = values.index(sec)
            pygame.draw.polygon(s, style["sections"][k], wedge)
            layer = pygame.Surface((S, S), pygame.SRCALPHA)
            draw_pattern(layer, sec, (0, 0, S, S), style["ink"][k], unit=S / 60)
            mask = pygame.Surface((S, S), pygame.SRCALPHA)
            pygame.draw.polygon(mask, WHITE, wedge)
            layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            s.blit(layer, (0, 0))
        else:
            pygame.draw.polygon(s, style["sections"][values.index(sec) % 2], wedge)

    # white dividers, then the outline of the face
    for i in range(8):
        a = math.radians(section_angle(i) - 22.5 - 90)
        pygame.draw.line(s, WHITE, (c, c), (c + r * math.cos(a), c + r * math.sin(a)), max(3, S // 90))
    pygame.draw.circle(s, INK, (c, c), r, max(3, S // 110))
    out = finish(s, size)

    # pictures and words, placed at final size
    icon = int(size * 0.19)
    for i, sec in enumerate(sections):
        ang = section_angle(i)
        a = math.radians(ang - 90)
        dist = 0.29 if sec in (rules.WILD, rules.ZOO) else 0.3
        x = size / 2 + size * dist * math.cos(a)
        y = size / 2 + size * dist * math.sin(a)
        if sec == rules.WILD:
            img = _along(_fit(fancy_text("WILD!", int(size * 0.13)), size * 0.32, size * 0.15), ang)
        elif sec == rules.ZOO:
            words = _stack(fancy_text("SPIN-A", int(size * 0.09)),
                           fancy_text("ZOO!", int(size * 0.11), RAINBOW[3:] + RAINBOW[:3]))
            img = _along(_fit(words, size * 0.32, size * 0.19), ang)
        elif feature == "shape":
            img = shape_icon(sec, icon)
        elif feature == "animal":
            img = _badge(sec, icon, style["rim"])
        else:
            img = None  # colour and pattern sections are the value itself
        if img:
            out.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))
    return fast(out)


@lru_cache(maxsize=16)
def _badge(name: str, size: int, ring) -> pygame.Surface:
    """An animal on a white disc with a coloured ring, so it pops."""
    s = canvas(size)
    S = size * SS
    pygame.draw.circle(s, INK, (S / 2, S / 2), S * 0.5)
    pygame.draw.circle(s, ring, (S / 2, S / 2), S * 0.47)
    pygame.draw.circle(s, WHITE, (S / 2, S / 2), S * 0.4)
    out = finish(s, size)
    a = animal(name, int(size * 0.74))
    out.blit(a, a.get_rect(center=(size / 2, size / 2)))
    return out


def draw_arrow(surf, cx, cy, size, angle_deg, color=INK):
    """The spinner's arrow, pointing angle_deg clockwise from straight up."""
    import pygame.gfxdraw
    a = math.radians(angle_deg - 90)
    ux, uy = math.cos(a), math.sin(a)
    px, py = -uy, ux
    L, back, w = size * 0.4, size * 0.1, size * 0.05
    head = L - size * 0.11

    def P(along, side):
        return (round(cx + ux * along + px * side), round(cy + uy * along + py * side))
    pts = [P(L, 0), P(head, w * 2.0), P(head, w * 0.75), P(-back, w), P(-back, -w),
           P(head, -w * 0.75), P(head, -w * 2.0)]
    shadow = [(x + 3, y + 4) for x, y in pts]
    pygame.gfxdraw.filled_polygon(surf, shadow, (0, 0, 0, 70))
    pygame.gfxdraw.filled_polygon(surf, pts, color)
    pygame.gfxdraw.aapolygon(surf, pts, INK)
    pygame.draw.polygon(surf, INK, pts, max(2, size // 160))
    # shine along the shaft
    shine = [P(head, w * 0.3), P(-back * 0.5, w * 0.45), P(-back * 0.5, w * 0.15), P(head, w * 0.05)]
    pygame.gfxdraw.filled_polygon(surf, shine, shade(color, 1.5) + (200,))
    hub = round(size * 0.065)
    pygame.gfxdraw.filled_circle(surf, round(cx), round(cy), hub, color)
    pygame.gfxdraw.aacircle(surf, round(cx), round(cy), hub, INK)
    pygame.gfxdraw.filled_circle(surf, round(cx), round(cy), max(2, hub // 2), WHITE)
