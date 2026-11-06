"""Spin-a-Zoo app: title, player setup, how to play, pause menu, main loop.

Input is keyboard only. On Batocera, spinazoo.pygame.keys turns every
configured pad (players 1-4) into these keys, using the button mapping set up
in EmulationStation: D-pad/left stick = arrows, A = A, B = B, Start = Escape.
Hotkey + Start exits through Batocera (Alt+F4).
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pygame

import art
import rules
from game import BACK, BG, CARD, DOWN, LEFT, MENU, OK, RIGHT, UP, GameScreen, Layout

SETTINGS = Path(__file__).resolve().parent / "settings.json"

# Keys used by Batocera's default pygame mapping for buttons we don't use
# (select = Space, X = X, ...) are left out on purpose, so stray presses do
# nothing.
KEYS = {
    pygame.K_LEFT: LEFT, pygame.K_RIGHT: RIGHT, pygame.K_UP: UP, pygame.K_DOWN: DOWN,
    pygame.K_a: OK, pygame.K_RETURN: OK, pygame.K_KP_ENTER: OK,
    pygame.K_b: BACK, pygame.K_BACKSPACE: BACK,
    pygame.K_ESCAPE: MENU,
}

DEFAULT_SETUP = [("green", "TL"), ("blue", "TR")]


def load_setup() -> list[tuple[str, str]]:
    try:
        data = json.loads(SETTINGS.read_text())
        setup = [(c, s) for c, s in data["players"]]
        rules.Game.new(setup)  # validates
        return setup
    except (OSError, ValueError, KeyError, TypeError):
        return list(DEFAULT_SETUP)


def save_setup(setup: list[tuple[str, str]]) -> None:
    try:
        SETTINGS.write_text(json.dumps({"players": setup}) + "\n")
    except OSError:
        pass  # read-only folder: just don't remember


# --- drawing helpers ---------------------------------------------------------

def button(surf, L: Layout, text: str, center, focused: bool, enabled: bool = True, width=None):
    t = L.font.render(text, True, art.INK if enabled else (160, 150, 160))
    w = width or t.get_width() + L.margin * 3
    rect = pygame.Rect(0, 0, w, t.get_height() + L.margin)
    rect.center = center
    fill = (255, 214, 102) if focused and enabled else (CARD if enabled else (232, 226, 218))
    pygame.draw.rect(surf, fill, rect, border_radius=rect.h // 2)
    pygame.draw.rect(surf, art.INK if focused else (190, 180, 190), rect, 4 if focused else 2,
                     border_radius=rect.h // 2)
    surf.blit(t, t.get_rect(center=rect.center))
    return rect


def title_logo(surf, L: Layout, center, now: float, scale: float = 1.0) -> None:
    """'Spin-a-Zoo' in bouncing, colored letters."""
    font = pygame.font.Font(None, int(L.h * 0.16 * scale))
    colors = [art.SQUARE_COLORS[c] for c in ("red", "blue", "yellow", "green", "purple")]
    text = "Spin-a-Zoo"
    letters = [font.render(ch, True, colors[i % 5]) for i, ch in enumerate(text)]
    outlines = [font.render(ch, True, art.INK) for ch in text]
    total = sum(img.get_width() for img in letters)
    x = center[0] - total / 2
    for i, (img, out) in enumerate(zip(letters, outlines)):
        y = center[1] - img.get_height() / 2 + math.sin(now * 3 + i * 0.6) * L.h * 0.008
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (3, 4)):
            surf.blit(out, (x + dx, y + dy))
        surf.blit(img, (x, y))
        x += img.get_width()


# --- scenes ------------------------------------------------------------------

class Scene:
    def __init__(self, app: App):
        self.app = app
        self.L = app.layout

    def handle(self, action: str, now: float) -> None: ...
    def click(self, pos, now: float) -> None: ...
    def update(self, now: float) -> None: ...
    def draw(self, now: float) -> None: ...


class Title(Scene):
    ITEMS = ("Play", "How to play", "Exit")

    def __init__(self, app):
        super().__init__(app)
        self.focus = 0
        self.rects: list[pygame.Rect] = []

    def handle(self, action, now):
        if action in (UP, LEFT):
            self.focus = (self.focus - 1) % len(self.ITEMS)
        elif action in (DOWN, RIGHT):
            self.focus = (self.focus + 1) % len(self.ITEMS)
        elif action == OK:
            self.choose(self.focus)

    def choose(self, i):
        item = self.ITEMS[i]
        if item == "Play":
            self.app.replace(Setup(self.app))
        elif item == "How to play":
            self.app.push(HowToPlay(self.app))
        else:
            self.app.running = False

    def click(self, pos, now):
        for i, r in enumerate(self.rects):
            if r.collidepoint(pos):
                self.choose(i)

    def draw(self, now):
        s, L = self.app.screen, self.L
        s.fill(BG)
        title_logo(s, L, (L.w / 2, L.h * 0.2), now)
        size = int(L.h * 0.15)
        names = rules.VALUES["animal"]
        gap = size * 1.25
        x0 = L.w / 2 - gap * (len(names) - 1) / 2
        for i, name in enumerate(names):
            bob = math.sin(now * 2.5 + i) * L.h * 0.01
            img = art.animal(name, size)
            s.blit(img, img.get_rect(center=(x0 + i * gap, L.h * 0.42 + bob)))
        self.rects = [button(s, L, item, (L.w / 2, L.h * (0.62 + i * 0.11)), i == self.focus,
                             width=int(L.w * 0.26))
                      for i, item in enumerate(self.ITEMS)]
        hint = L.font_small.render("A: choose     Hotkey + Start: exit", True, (120, 110, 120))
        s.blit(hint, hint.get_rect(midbottom=(L.w / 2, L.h - L.margin)))


class Setup(Scene):
    """Seat picker laid out like the game: four seats round a centre panel."""

    MOVES = {
        "TL": {RIGHT: "START", DOWN: "BL", UP: "BL"},
        "BL": {RIGHT: "START", UP: "TL", DOWN: "TL"},
        "TR": {LEFT: "START", DOWN: "BR", UP: "BR"},
        "BR": {LEFT: "START", UP: "TR", DOWN: "TR"},
        "START": {LEFT: "TL", RIGHT: "TR"},
    }

    def __init__(self, app):
        super().__init__(app)
        self.players = load_setup()  # (color, seat) in the order they joined
        self.focus = "START"
        self.start_rect = pygame.Rect(0, 0, 0, 0)

    def seat_color(self, seat):
        return next((c for c, s in self.players if s == seat), None)

    def cycle(self, seat):
        """A on a seat: empty -> first free color -> next free color ... -> empty."""
        current = self.seat_color(seat)
        taken = {c for c, s in self.players if s != seat}
        options = [c for c in rules.PLAYER_COLORS if c not in taken] + [None]
        nxt = options[(options.index(current) + 1) % len(options)] if current else options[0]
        if current:
            idx = next(i for i, (c, s) in enumerate(self.players) if s == seat)
            if nxt:
                self.players[idx] = (nxt, seat)
            else:
                del self.players[idx]
        elif nxt:
            self.players.append((nxt, seat))

    def clear(self, seat):
        self.players = [(c, s) for c, s in self.players if s != seat]

    def start(self):
        if len(self.players) >= 2:
            save_setup(self.players)
            self.app.replace(Play(self.app, list(self.players)))

    def handle(self, action, now):
        if action in (LEFT, RIGHT, UP, DOWN):
            self.focus = self.MOVES[self.focus].get(action, self.focus)
        elif action == OK:
            if self.focus == "START":
                self.start()
            else:
                self.cycle(self.focus)
        elif action == BACK:
            if self.focus != "START" and self.seat_color(self.focus):
                self.clear(self.focus)
            else:
                self.app.replace(Title(self.app))
        elif action == MENU:
            self.app.replace(Title(self.app))

    def click(self, pos, now):
        if self.start_rect.collidepoint(pos):
            self.focus = "START"
            self.start()
            return
        for seat, rect in self.L.panels.items():
            if rect.collidepoint(pos):
                self.focus = seat
                self.cycle(seat)

    def draw(self, now):
        s, L = self.app.screen, self.L
        s.fill(BG)
        for seat, rect in L.panels.items():
            color = self.seat_color(seat)
            focused = self.focus == seat
            pygame.draw.rect(s, CARD if color else (238, 231, 220), rect, border_radius=L.margin)
            if focused:
                pulse = 0.5 + 0.5 * math.sin(now * 5)
                w = max(4, int(L.margin * (0.25 + 0.15 * pulse)))
                pygame.draw.rect(s, art.INK, rect.inflate(w, w), w, border_radius=L.margin + w // 2)
            label = L.font_small.render(rules.SEAT_LABELS[seat], True, (130, 120, 130))
            s.blit(label, label.get_rect(midtop=(rect.centerx, rect.y + L.margin)))
            if color:
                size = int(min(rect.w, rect.h) * 0.42)
                s.blit(art.tile(color, size), art.tile(color, size).get_rect(center=rect.center))
                name = L.font.render(rules.LABELS[color], True, art.INK)
                s.blit(name, name.get_rect(midtop=(rect.centerx, rect.centery + size / 2 + L.margin / 2)))
                if self.players[0][1] == seat:
                    first = L.font_small.render("Goes first", True, art.TILE_COLORS[color])
                    s.blit(first, first.get_rect(midtop=(rect.centerx, rect.centery + size / 2
                                                         + L.margin / 2 + name.get_height())))
            else:
                t = L.font.render("Empty seat", True, (150, 140, 150))
                s.blit(t, t.get_rect(center=rect.center))
                if focused:
                    h = L.font_small.render("Press A to sit here", True, (120, 110, 120))
                    s.blit(h, h.get_rect(midtop=(rect.centerx, rect.centery + t.get_height())))

        b = L.board
        pygame.draw.rect(s, CARD, b, border_radius=L.margin)
        head = L.font_big.render("Who's playing?", True, art.INK)
        s.blit(head, head.get_rect(midtop=(b.centerx, b.top + L.margin * 2)))
        lines = [
            "Pick a seat and press A to choose a color.",
            "Press A again for another color, B to leave.",
            "The first one to sit down goes first.",
            "",
            "2 to 4 players.",
        ]
        y = b.top + L.margin * 3 + head.get_height()
        for line in lines:
            t = L.font_small.render(line, True, (90, 80, 95))
            s.blit(t, t.get_rect(midtop=(b.centerx, y)))
            y += t.get_height() + L.margin * 0.4
        ok = len(self.players) >= 2
        self.start_rect = button(s, L, "Start game!" if ok else "Need 2 players",
                                 (b.centerx, b.bottom - L.h * 0.16), self.focus == "START", ok,
                                 width=int(b.w * 0.6))
        hint = L.font_small.render("A: choose   B: back   Arrows: move", True, (130, 120, 130))
        s.blit(hint, hint.get_rect(midbottom=(b.centerx, b.bottom - L.margin)))


class Play(Scene):
    def __init__(self, app, setup):
        super().__init__(app)
        self.setup = setup
        self.screen = GameScreen(app.screen, setup)

    def handle(self, action, now):
        if action == MENU:
            self.app.push(Pause(self.app, self))
        elif action == BACK:
            pass  # B does nothing in play, so it can't undo or quit by accident
        else:
            self.screen.handle(action, now)

    def click(self, pos, now):
        self.screen.click(pos, now)

    def update(self, now):
        self.screen.update(now)

    def draw(self, now):
        self.screen.draw(now)


class Pause(Scene):
    ITEMS = ("Resume", "New board", "Change players", "How to play", "Exit game")

    def __init__(self, app, play: Play):
        super().__init__(app)
        self.play = play
        self.focus = 0
        self.rects: list[pygame.Rect] = []

    def handle(self, action, now):
        if action in (UP, LEFT):
            self.focus = (self.focus - 1) % len(self.ITEMS)
        elif action in (DOWN, RIGHT):
            self.focus = (self.focus + 1) % len(self.ITEMS)
        elif action in (BACK, MENU):
            self.app.pop()
        elif action == OK:
            self.choose(self.focus)

    def choose(self, i):
        item = self.ITEMS[i]
        if item == "Resume":
            self.app.pop()
        elif item == "New board":
            self.play.screen.new_round()
            self.app.pop()
        elif item == "Change players":
            self.app.replace_all(Setup(self.app))
        elif item == "How to play":
            self.app.push(HowToPlay(self.app))
        else:
            self.app.running = False

    def click(self, pos, now):
        for i, r in enumerate(self.rects):
            if r.collidepoint(pos):
                self.choose(i)
                return
        self.app.pop()

    def draw(self, now):
        s, L = self.app.screen, self.L
        self.play.draw(now)
        shade = pygame.Surface((L.w, L.h), pygame.SRCALPHA)
        shade.fill((20, 16, 30, 150))
        s.blit(shade, (0, 0))
        head = L.font_big.render("Paused", True, art.INK)
        step = L.h * 0.11
        box = pygame.Rect(0, 0, int(L.w * 0.34),
                          int(L.margin * 3 + head.get_height() + step * len(self.ITEMS)))
        box.center = (L.w / 2, L.h / 2)
        pygame.draw.rect(s, BG, box, border_radius=L.margin)
        pygame.draw.rect(s, art.INK, box, 4, border_radius=L.margin)
        s.blit(head, head.get_rect(midtop=(box.centerx, box.top + L.margin)))
        y0 = box.top + L.margin * 2 + head.get_height() + step / 2
        self.rects = [button(s, L, item, (box.centerx, y0 + i * step), i == self.focus,
                             width=int(box.w * 0.8)) for i, item in enumerate(self.ITEMS)]


class HowToPlay(Scene):
    def handle(self, action, now):
        if action in (OK, BACK, MENU):
            self.app.pop()

    def click(self, pos, now):
        self.app.pop()

    def draw(self, now):
        s, L = self.app.screen, self.L
        s.fill(BG)
        head = L.font_big.render("How to play", True, art.INK)
        s.blit(head, head.get_rect(midtop=(L.w / 2, L.margin)))
        icon = int(L.h * 0.085)
        sample = rules.Square("purple", "star", "dots", "lion")
        rows = [
            (art.square(sample, icon), "Spin your spinner, then cover a square that matches it."),
            (None, "No empty match left? Play on any empty square."),
            (None, "You can't play on a square that already has a tile..."),
            (self._word("WILD", (200, 60, 120), icon), "...unless you spin WILD: play anywhere, even on a tile. Stacks hold 4."),
            (self._word("ZOO!", (190, 90, 0), icon), "SPIN A ZOO! Everyone passes their spinner clockwise. Spin again!"),
            (art.tile("red", icon), "Get 4 of your tiles in a row (across, down or diagonal) to win!"),
            (None, "Board full and no winner? PLAY AGAIN!"),
        ]
        y = L.margin * 2 + head.get_height()
        x_icon = L.w * 0.12
        step = (L.h * 0.82 - y) / len(rows)
        for img, text in rows:
            if img:
                s.blit(img, img.get_rect(center=(x_icon, y + step / 2)))
            t = L.font.render(text, True, art.INK)
            if t.get_width() > L.w * 0.78:
                t = L.font_small.render(text, True, art.INK)
            s.blit(t, t.get_rect(midleft=(x_icon + icon, y + step / 2)))
            y += step
        controls = "A: spin / place     Arrows: move     Start: menu     Hotkey + Start: exit"
        t = L.font_small.render(controls, True, (90, 80, 95))
        s.blit(t, t.get_rect(midbottom=(L.w / 2, L.h - L.margin * 3)))
        t = L.font_small.render("Press A to go back", True, (130, 120, 130))
        s.blit(t, t.get_rect(midbottom=(L.w / 2, L.h - L.margin)))

    def _word(self, word, color, size):
        f = pygame.font.Font(None, int(size * 0.36))
        img = f.render(word, True, color)
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 246, 225), (size / 2, size / 2), size / 2)
        pygame.draw.circle(s, art.INK, (size / 2, size / 2), size / 2, 3)
        s.blit(img, img.get_rect(center=(size / 2, size / 2)))
        return s


# --- app ---------------------------------------------------------------------

class App:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.layout = Layout(*screen.get_size())
        self.stack: list[Scene] = []
        self.running = True

    @property
    def scene(self) -> Scene:
        return self.stack[-1]

    def push(self, scene: Scene) -> None:
        self.stack.append(scene)

    def pop(self) -> None:
        if len(self.stack) > 1:
            self.stack.pop()

    def replace(self, scene: Scene) -> None:
        self.stack[-1] = scene

    def replace_all(self, scene: Scene) -> None:
        self.stack = [scene]

    def frame(self, events, now: float) -> None:
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F4 and event.mod & pygame.KMOD_ALT:
                    self.running = False
                elif event.key in KEYS:
                    self.scene.handle(KEYS[event.key], now)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.scene.click(event.pos, now)
            if not self.running:
                return
        self.scene.update(now)
        self.scene.draw(now)


def main() -> None:
    # SDL minimizes a fullscreen window when it loses focus, and Batocera's
    # popups (like the screenshot flash) take focus for a moment, leaving the
    # game hidden behind EmulationStation. Stay on screen instead.
    os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")
    pygame.init()
    window = os.environ.get("SPINAZOO_WINDOW")
    if window:
        w, h = (int(v) for v in window.lower().split("x"))
        screen = pygame.display.set_mode((w, h))
    else:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Spin-a-Zoo")
    pygame.mouse.set_visible(bool(window))
    pygame.key.set_repeat(350, 120)
    app = App(screen)
    app.push(Title(app))
    clock = pygame.time.Clock()
    while app.running:
        app.frame(pygame.event.get(), pygame.time.get_ticks() / 1000)
        pygame.display.flip()
        # 60 fps while something moves (spin, pass, tile drop), 30 otherwise:
        # halves the CPU use for the rest of the time.
        scene = app.scene if app.running else None
        clock.tick(60 if isinstance(scene, Play) and scene.screen.busy() else 30)
    pygame.quit()
