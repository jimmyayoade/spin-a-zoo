"""Colour themes for everything around the board (the board itself, spinners
and tiles keep their colours so the game always looks the same)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache

import pygame

import art


@dataclass(frozen=True)
class Theme:
    name: str
    bg: tuple            # screen background
    deco: tuple          # faint paw prints and leaves on the background
    card: tuple          # panels with a player
    card_idle: tuple     # empty seats
    text: tuple
    muted: tuple
    button: tuple
    button_line: tuple
    dark: bool


THEMES = {
    "Night": Theme("Night", (27, 30, 48), (36, 40, 63), (47, 51, 78), (37, 40, 61),
                   (242, 238, 230), (160, 160, 182), (58, 63, 94), (95, 100, 135), True),
    "Jungle": Theme("Jungle", (22, 52, 38), (30, 64, 47), (36, 76, 56), (28, 61, 45),
                    (240, 244, 228), (168, 196, 170), (44, 90, 66), (84, 130, 100), True),
    "Ocean": Theme("Ocean", (18, 44, 72), (25, 56, 88), (32, 66, 104), (24, 53, 85),
                   (236, 244, 250), (160, 188, 210), (40, 80, 124), (80, 124, 168), True),
    "Daylight": Theme("Daylight", (250, 244, 232), (241, 232, 214), (255, 251, 243), (238, 231, 220),
                      art.INK, (120, 110, 120), (255, 251, 243), (190, 180, 190), False),
}
ORDER = list(THEMES)

T: Theme = THEMES["Night"]


def use(name: str) -> None:
    global T
    T = THEMES.get(name, THEMES["Night"])


def accent(color: tuple) -> tuple:
    """A player colour made readable as text on the current background."""
    if not T.dark:
        return color
    return tuple(min(255, int(c + (255 - c) * 0.45)) for c in color)


def _paw(surf, color, x, y, r, angle):
    ca, sa = math.cos(angle), math.sin(angle)

    def at(dx, dy):
        return (x + dx * ca - dy * sa, y + dx * sa + dy * ca)
    pygame.draw.ellipse(surf, color, pygame.Rect(0, 0, r * 1.5, r * 1.25).move(
        at(0, r * 0.35)[0] - r * 0.75, at(0, r * 0.35)[1] - r * 0.62))
    for dx, dy in ((-0.75, -0.55), (-0.27, -0.95), (0.27, -0.95), (0.75, -0.55)):
        pygame.draw.circle(surf, color, at(dx * r, dy * r), r * 0.32)


@lru_cache(maxsize=4)
def background(name: str, w: int, h: int) -> pygame.Surface:
    """The theme's background with a scattering of paw prints and leaves."""
    th = THEMES[name]
    s = pygame.Surface((w, h))
    s.fill(th.bg)
    rng = random.Random(4)
    step = h / 5
    for row in range(7):
        for col in range(int(w / step) + 2):
            x = col * step + (step / 2 if row % 2 else 0) + rng.uniform(-step * 0.2, step * 0.2)
            y = row * step - step / 2 + rng.uniform(-step * 0.2, step * 0.2)
            if (row + col) % 3 == 0:
                art._leaf(s, th.deco, x, y, h / 160, rng.uniform(0, math.tau))
            else:
                _paw(s, th.deco, x, y, h / 60, rng.uniform(-0.6, 0.6))
    return art.fast(s)
