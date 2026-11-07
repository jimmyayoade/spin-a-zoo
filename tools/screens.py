"""Render game screens in set-up states to PNGs, for checking the layout."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SPINAZOO_SILENT", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "spinazoo"))

import pygame  # noqa: E402

pygame.init()
out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
w, h = (int(v) for v in (sys.argv[2] if len(sys.argv) > 2 else "1920x1080").split("x"))
screen = pygame.display.set_mode((w, h))

import game  # noqa: E402
import rules  # noqa: E402


def shot(name, g, now):
    g.update(now)
    g.draw(now)
    pygame.image.save(screen, str(out / f"{name}.png"))
    print(out / f"{name}.png")


# 1. start of a 3-player game, mid-spin
g = game.GameScreen(screen, [("green", "TL"), ("blue", "TR"), ("red", "BR")], seed=3)
shot("0-ready", g, 1.0)
g.handle(game.OK, 1.0)
shot("1-spinning", g, 1.7)

# 2. place phase after a value spin, with some tiles and a stack
g = game.GameScreen(screen, [("green", "TL"), ("yellow", "BR")], seed=5)
g.announce = False  # set up mid-game: no "goes first" banner
gm = g.game
for (r, c), who in {(0, 0): 0, (1, 1): 1, (2, 2): 0, (3, 1): 1, (4, 4): 0}.items():
    gm.stacks[r][c].append(who)
gm.stacks[2][2].append(1)
g.start_spin(0.0)
g.spin_section = rules.VALUES[gm.spinner][2]
g.update(4.9)
shot("2a-card", g, 5.6)
shot("2-place", g, 7.5)

# 3. a win
g = game.GameScreen(screen, [("green", "TL"), ("blue", "TR"), ("yellow", "BR"), ("red", "BL")], seed=8)
g.announce = False  # set up mid-game: no "goes first" banner
gm = g.game
for c in range(3):
    gm.stacks[1][c].append(3)
gm.stacks[0][4].append(1)
gm.turn = 3
gm.resolve(rules.WILD)
g.try_place(1, 3, 0.0)
shot("3-win", g, 1.0)

# 4. menus
import app  # noqa: E402

a = app.App(screen)
for name, make in (("4-title", lambda: app.Title(a)), ("5-setup", lambda: app.Setup(a)),
                   ("6-howto", lambda: app.HowToPlay(a))):
    a.replace_all(make())
    if name == "6-howto":
        a.push(app.Options(a))
        a.frame([], 1.0)
        pygame.image.save(screen, str(out / "6b-options.png"))
        a.pop()
    if name == "5-setup":
        a.scene.players = [("red", "BR"), ("green", "TL"), ("yellow", "BL")]
        a.scene.focus = "TR"
    a.frame([], 1.0)
    pygame.image.save(screen, str(out / f"{name}.png"))
    print(out / f"{name}.png")
play = app.Play(a, [("green", "TL"), ("blue", "TR")])
a.replace_all(play)
a.push(app.Pause(a, play))
a.frame([], 1.0)
pygame.image.save(screen, str(out / "7-pause.png"))
print(out / "7-pause.png")

# 8. win with confetti, a moment after the winning tile
g = game.GameScreen(screen, [("green", "TL"), ("blue", "TR"), ("yellow", "BR"), ("red", "BL")], seed=8)
g.announce = False  # set up mid-game: no "goes first" banner
gm = g.game
for c in range(3):
    gm.stacks[2][c + 1].append(1)
gm.turn = 1
gm.resolve(rules.WILD)
g.try_place(2, 4, 0.0)
for i in range(1, 50):
    g.update(i / 60)
shot("8-confetti", g, 50 / 60)
