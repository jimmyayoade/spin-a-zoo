"""Draw media/spinazoo.png: the game's picture for EmulationStation and BUA."""
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "spinazoo"))

import pygame  # noqa: E402

pygame.init()
W, H = 1280, 720
screen = pygame.display.set_mode((W, H))

import app  # noqa: E402
import art  # noqa: E402
import rules  # noqa: E402
import theme  # noqa: E402
from game import BOARD_FRAME, Layout  # noqa: E402

L = Layout(W, H)
s = theme.background("Night", W, H).copy()

# a strip of board squares along the bottom, with a few tiles on them
board = rules.make_board(random.Random(11))
cell = 150
gap = 12
strip = pygame.Rect(0, 0, 5 * cell + 6 * gap, cell + 2 * gap)
strip.midbottom = (W / 2, H - 40)
pygame.draw.rect(s, BOARD_FRAME, strip, border_radius=24)
for c in range(5):
    x = strip.x + gap + c * (cell + gap)
    s.blit(art.square(board[1][c], cell), (x, strip.y + gap))
for c, color in ((1, "red"), (3, "blue")):
    t = art.tile(color, int(cell * 1.02))
    s.blit(t, t.get_rect(center=(strip.x + gap + c * (cell + gap) + cell / 2, strip.centery)))

# spinner on each side, title and animals in the middle
for x, feature, angle in ((175, "color", 30), (W - 175, "animal", 200)):
    d = art.dial(feature, 270)
    s.blit(d, d.get_rect(center=(x, 345)))
    art.draw_arrow(s, x, 345, 270, angle, art.SPINNER_STYLE[feature]["arrow"])
app.title_logo(s, L, (W / 2, 140), 0.0, scale=1.25)
size = 120
for i, name in enumerate(rules.VALUES["animal"]):
    img = art.animal(name, size)
    s.blit(img, img.get_rect(center=(W / 2 + (i - 2) * 135, 330 + (i % 2) * 14)))

out = ROOT / "media" / "spinazoo.png"
pygame.image.save(s, str(out))
print(out)
