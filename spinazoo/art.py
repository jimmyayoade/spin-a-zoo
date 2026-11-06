"""Spin-a-Zoo artwork, drawn in code.

Everything is drawn at twice the target size and smooth-scaled down, which
gives clean edges without pygame's slower anti-aliased primitives. Results are
cached per size, so each picture is drawn once per screen layout.

A PNG in the game's art/ folder named after an animal (shepherd.png, cat.png,
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


def shade(color, f):
    return tuple(max(0, min(255, int(c * f))) for c in color)


def finish(surf: pygame.Surface, size: int) -> pygame.Surface:
    """Scale a supersampled surface down to its final size."""
    return pygame.transform.smoothscale(surf, (size, size))


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


def draw_pattern(surf, pattern, rect, color):
    x0, y0, w, h = rect
    u = w / 30
    if pattern == "stripes":
        step = w / 5
        for i in range(-6, 12):
            x = x0 + i * step
            pygame.draw.line(surf, color, (x, y0), (x + h, y0 + h), max(2, int(w / 16)))
    elif pattern == "dots":
        step = w / 5
        for row in range(6):
            for col in range(6):
                off = step / 2 if row % 2 else 0
                pygame.draw.circle(surf, color, (x0 + col * step + off, y0 + row * step + step / 2), w / 22)
    elif pattern == "zigzag":
        step = h / 5
        for row in range(6):
            y = y0 + row * step + step / 2
            pts = [(x0 + i * w / 10, y + (u * 1.6 if i % 2 else -u * 1.6)) for i in range(11)]
            pygame.draw.lines(surf, color, False, pts, max(2, int(w / 28)))
    elif pattern == "notes":
        step = w / 4
        for row in range(5):
            for col in range(5):
                off = step / 2 if row % 2 else 0
                _note(surf, color, x0 + col * step + off - step / 4, y0 + row * step + step * 0.55, u)
    elif pattern == "leaves":
        step = w / 4
        for row in range(5):
            for col in range(5):
                off = step / 2 if row % 2 else 0
                _leaf(surf, color, x0 + col * step + off - step / 4, y0 + row * step + step / 2, u,
                      math.radians(35 if (row + col) % 2 else -35))
    else:
        raise ValueError(pattern)


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

    if name == "shepherd":
        tan, dark, black = (205, 145, 80), (70, 45, 25), (25, 20, 18)
        for ear in (P((20, 44), (26, 2), (46, 30)), P((80, 44), (74, 2), (54, 30))):
            pygame.draw.polygon(s, dark, ear)
            pygame.draw.polygon(s, INK, ear, line)
        pygame.draw.polygon(s, (230, 170, 120), P((27, 36), (29, 14), (40, 30)))
        pygame.draw.polygon(s, (230, 170, 120), P((73, 36), (71, 14), (60, 30)))
        pygame.draw.ellipse(s, tan, R(18, 22, 64, 64))
        pygame.draw.polygon(s, dark, P((36, 23), (64, 23), (56, 44), (50, 50), (44, 44)))
        pygame.draw.ellipse(s, INK, R(18, 22, 64, 64), line)
        pygame.draw.ellipse(s, black, R(32, 54, 36, 32))
        pygame.draw.ellipse(s, (10, 10, 10), R(42, 55, 16, 11))
        pygame.draw.line(s, (235, 235, 235), C(46, 57), C(50, 57), max(1, round(u)))
        for ex in (37, 63):
            pygame.draw.ellipse(s, (60, 35, 15), R(ex - 5, 41, 10, 9))
            pygame.draw.circle(s, WHITE, C(ex - 1.5, 43.5), 1.6 * u)
        pygame.draw.line(s, (200, 80, 90), C(50, 72), C(50, 78), line)
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
    return out


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


def _wedge(cx, cy, r, a0, a1):
    pts = [(cx, cy)]
    for k in range(13):
        a = math.radians(a0 + (a1 - a0) * k / 12 - 90)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


@lru_cache(maxsize=16)
def dial(feature: str, size: int, font_path: str | None = None) -> pygame.Surface:
    """A spinner face (without its arrow)."""
    S = size * SS
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    c = S / 2
    r = S * 0.48
    sections = rules.spinner_sections(feature)
    pygame.draw.circle(s, INK, (c, c), r + S * 0.012)
    for i, sec in enumerate(sections):
        a = section_angle(i)
        if feature == "color" and sec in SQUARE_COLORS:
            fill = SQUARE_COLORS[sec]
        elif sec == rules.WILD:
            fill = (255, 250, 235)
        elif sec == rules.ZOO:
            fill = (255, 236, 200)
        else:
            fill = (246, 242, 250) if i % 2 else (232, 226, 240)
        pygame.draw.polygon(s, fill, _wedge(c, c, r, a - 22.5, a + 22.5))
    for i in range(8):
        a = math.radians(section_angle(i) - 22.5 - 90)
        pygame.draw.line(s, INK, (c, c), (c + r * math.cos(a), c + r * math.sin(a)), max(2, S // 120))
    pygame.draw.circle(s, INK, (c, c), r, max(3, S // 80))
    out = finish(s, size)

    # icons and words, placed at final size
    font = pygame.font.Font(font_path, max(10, int(size * 0.075)))
    icon = int(size * 0.2)
    for i, sec in enumerate(sections):
        a = math.radians(section_angle(i) - 90)
        x = size / 2 + size * 0.31 * math.cos(a)
        y = size / 2 + size * 0.31 * math.sin(a)
        if sec == rules.WILD:
            img = _text(font, "WILD", (200, 60, 120))
        elif sec == rules.ZOO:
            img = _two_lines(font, "SPIN A", "ZOO!", (190, 90, 0))
        elif feature == "shape":
            img = shape_icon(sec, icon)
        elif feature == "pattern":
            img = pattern_swatch(sec, icon)
        elif feature == "animal":
            img = animal(sec, icon)
        else:
            img = None  # color sections are the color itself
        if img:
            out.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))
    return out


def _text(font, text, color):
    return font.render(text, True, color)


def _two_lines(font, a, b, color):
    ia, ib = _text(font, a, color), _text(font, b, color)
    s = pygame.Surface((max(ia.get_width(), ib.get_width()), ia.get_height() + ib.get_height()),
                       pygame.SRCALPHA)
    s.blit(ia, ((s.get_width() - ia.get_width()) // 2, 0))
    s.blit(ib, ((s.get_width() - ib.get_width()) // 2, ia.get_height()))
    return s


def draw_arrow(surf, cx, cy, size, angle_deg, color=INK):
    """The spinner's arrow, pointing angle_deg clockwise from straight up."""
    import pygame.gfxdraw
    a = math.radians(angle_deg - 90)
    ux, uy = math.cos(a), math.sin(a)
    px, py = -uy, ux
    L, back, w = size * 0.4, size * 0.1, size * 0.045
    tip = (cx + ux * L, cy + uy * L)
    pts = [tip,
           (cx + ux * (L - size * 0.1) + px * w * 1.8, cy + uy * (L - size * 0.1) + py * w * 1.8),
           (cx + ux * (L - size * 0.1) + px * w * 0.7, cy + uy * (L - size * 0.1) + py * w * 0.7),
           (cx - ux * back + px * w, cy - uy * back + py * w),
           (cx - ux * back - px * w, cy - uy * back - py * w),
           (cx + ux * (L - size * 0.1) - px * w * 0.7, cy + uy * (L - size * 0.1) - py * w * 0.7),
           (cx + ux * (L - size * 0.1) - px * w * 1.8, cy + uy * (L - size * 0.1) - py * w * 1.8)]
    pts = [(round(x), round(y)) for x, y in pts]
    shadow = [(x + 2, y + 3) for x, y in pts]
    pygame.gfxdraw.filled_polygon(surf, shadow, (0, 0, 0, 60))
    pygame.gfxdraw.filled_polygon(surf, pts, color)
    pygame.gfxdraw.aapolygon(surf, pts, color)
    pygame.gfxdraw.filled_circle(surf, round(cx), round(cy), round(size * 0.06), (250, 250, 250))
    pygame.gfxdraw.aacircle(surf, round(cx), round(cy), round(size * 0.06), color)
