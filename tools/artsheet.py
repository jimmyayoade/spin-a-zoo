"""Render every piece of artwork to one PNG, for checking the drawings."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "spinazoo"))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))
import art  # noqa: E402
import rules  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "artsheet.png"
sheet = pygame.Surface((1500, 1000))
sheet.fill((250, 246, 238))
x = 20
for i, a in enumerate(rules.VALUES["animal"]):
    sheet.blit(art.animal(a, 180), (20 + i * 200, 20))
for i, (c, sh, p, a) in enumerate(zip(*(rules.VALUES[f] for f in rules.FEATURES))):
    sheet.blit(art.square(rules.Square(c, sh, p, a), 180), (20 + i * 200, 220))
for i, c in enumerate(rules.PLAYER_COLORS):
    sheet.blit(art.tile(c, 120), (1050 + (i % 2) * 140, 20 + (i // 2) * 140))
for i, f in enumerate(rules.FEATURES):
    d = art.dial(f, 340)
    sheet.blit(d, (20 + i * 370, 430))
    art.draw_arrow(sheet, 20 + i * 370 + 170, 430 + 170, 340, 30 + i * 70)
for i, sq in enumerate([rules.Square("yellow", "star", "notes", "eagle"), rules.Square("purple", "triangle", "leaves", "bear")]):
    s = art.square(sq, 180).copy()
    s.blit(art.tile(rules.PLAYER_COLORS[i + 2], 140), (20, 20))
    sheet.blit(s, (1050 + i * 200, 220 + 40))
pygame.image.save(sheet, out)
print(out)
