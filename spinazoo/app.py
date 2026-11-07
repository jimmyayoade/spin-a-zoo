"""Spin-A-Zoo! app: title, player setup, options, how to play, pause, main loop.

Input is keyboard only. On Batocera, spinazoo.pygame.keys turns every
configured pad (players 1-4) into keys, a different set per controller (see
pads.py), so the game knows which controller pressed. Which of the south/east
buttons confirms is an option (south by default: A on Xbox-style pads).
Hotkey + Start exits through Batocera (Alt+F4).

Controllers option: "Shared" lets any controller play any turn; "One each"
links a controller to a seat when that player presses A on it in the setup
screen, and then only that controller can spin and place on their turn.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pygame

import art
import pads
import rules
import sound
import theme
from game import BACK, DOWN, LEFT, MENU, OK, RIGHT, UP, GameScreen, Layout

SETTINGS = Path(__file__).resolve().parent / "settings.json"

# Keyboard-only keys (no controller sends them). Keys that Batocera's default
# pygame mapping gives to buttons we don't use (select = Space, X = X, ...)
# are left out, so stray presses do nothing.
KEYS = {
    pygame.K_a: OK, pygame.K_RETURN: OK, pygame.K_KP_ENTER: OK,
    pygame.K_b: BACK, pygame.K_BACKSPACE: BACK,
}


def _pad_tables():
    """Controller keys -> (controller, button), by scancode and by key."""
    by_scan, by_key = {}, {}
    for pad, names in enumerate(pads.PADS):
        for button, name in zip(pads.BUTTONS, names):
            by_scan[getattr(pygame, "KSCAN_" + name)] = (pad, button)
            by_key[getattr(pygame, "K_" + (name.lower() if len(name) == 1 else name))] = (pad, button)
    return by_scan, by_key


PAD_BY_SCAN, PAD_BY_KEY = _pad_tables()
DIRECTIONS = {"up": UP, "down": DOWN, "left": LEFT, "right": RIGHT, "start": MENU}

DEFAULT_SETUP = [("green", "TL"), ("blue", "TR")]
DEFAULTS = {"players": DEFAULT_SETUP, "sound": True, "music": True, "theme": "Night", "confirm": "south",
            "controllers": "shared", "pads": {}}


def load_settings() -> dict:
    """Saved players and options, from settings.json next to the game."""
    settings = {k: (type(v)(v) if isinstance(v, (list, dict)) else v) for k, v in DEFAULTS.items()}
    try:
        data = json.loads(SETTINGS.read_text())
    except (OSError, ValueError):
        return settings
    if not isinstance(data, dict):
        return settings
    try:
        setup = [(c, s) for c, s in data["players"]]
        rules.Game.new(setup)  # validates
        settings["players"] = setup
    except (ValueError, KeyError, TypeError):
        pass
    for key in ("sound", "music"):
        if isinstance(data.get(key), bool):
            settings[key] = data[key]
    if data.get("theme") in theme.THEMES:
        settings["theme"] = data["theme"]
    if data.get("confirm") in ("south", "east"):
        settings["confirm"] = data["confirm"]
    if data.get("controllers") in ("shared", "each"):
        settings["controllers"] = data["controllers"]
    if isinstance(data.get("pads"), dict):
        settings["pads"] = {seat: pad for seat, pad in data["pads"].items()
                            if seat in rules.SEATS and type(pad) is int and 0 <= pad < len(pads.PADS)}
    return settings


def save_settings(settings: dict) -> None:
    try:
        SETTINGS.write_text(json.dumps(settings) + "\n")
    except OSError:
        pass  # read-only folder: just don't remember


# --- drawing helpers ---------------------------------------------------------

def button(surf, L: Layout, label: str, center, focused: bool, enabled: bool = True, width=None):
    T = theme.T
    color = art.INK if focused and enabled else (T.text if enabled else T.muted)
    t = L.font.render(label, True, color)
    w = width or t.get_width() + L.margin * 3
    rect = pygame.Rect(0, 0, w, t.get_height() + L.margin)
    rect.center = center
    fill = (255, 214, 102) if focused and enabled else T.button
    pygame.draw.rect(surf, fill, rect, border_radius=rect.h // 2)
    pygame.draw.rect(surf, art.INK if focused else T.button_line, rect, 4 if focused else 2,
                     border_radius=rect.h // 2)
    surf.blit(t, t.get_rect(center=rect.center))
    return rect


def title_logo(surf, L: Layout, center, now: float, scale: float = 1.0) -> None:
    """'Spin-A-Zoo!' in bouncing, colored letters."""
    font = art.font(int(L.h * 0.16 * scale))
    colors = [art.SQUARE_COLORS[c] for c in ("red", "blue", "yellow", "green", "purple")]
    word = "Spin-A-Zoo!"
    letters = [font.render(ch, True, colors[i % 5]) for i, ch in enumerate(word)]
    outlines = [font.render(ch, True, art.INK) for ch in word]
    total = sum(img.get_width() for img in letters)
    x = center[0] - total / 2
    for i, (img, out) in enumerate(zip(letters, outlines)):
        y = center[1] - img.get_height() / 2 + math.sin(now * 3 + i * 0.6) * L.h * 0.008
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (3, 4)):
            surf.blit(out, (x + dx, y + dy))
        surf.blit(img, (x, y))
        x += img.get_width()


def background(app) -> None:
    L = app.layout
    app.screen.blit(theme.background(theme.T.name, L.w, L.h), (0, 0))


def text(surf, font, s, color, **pos):
    img = font.render(s, True, color)
    surf.blit(img, img.get_rect(**pos))
    return img


# --- scenes ------------------------------------------------------------------

class Scene:
    def __init__(self, app: App):
        self.app = app
        self.L = app.layout

    def handle(self, action: str, now: float) -> None: ...
    def click(self, pos, now: float) -> None: ...
    def update(self, now: float) -> None: ...
    def draw(self, now: float) -> None: ...


class Menu(Scene):
    """A vertical list of buttons."""

    ITEMS: tuple[str, ...] = ()

    def __init__(self, app):
        super().__init__(app)
        self.focus = 0
        self.rects: list[pygame.Rect] = []

    def handle(self, action, now):
        if action in (UP, LEFT):
            self.focus = (self.focus - 1) % len(self.ITEMS)
            self.app.sfx("blip")
        elif action in (DOWN, RIGHT):
            self.focus = (self.focus + 1) % len(self.ITEMS)
            self.app.sfx("blip")
        elif action == OK:
            self.app.sfx("select")
            self.choose(self.ITEMS[self.focus])
        elif action in (BACK, MENU):
            self.back()

    def click(self, pos, now):
        for i, r in enumerate(self.rects):
            if r.collidepoint(pos):
                self.focus = i
                self.app.sfx("select")
                self.choose(self.ITEMS[i])
                return

    def choose(self, item: str) -> None: ...
    def back(self) -> None: ...


class Title(Menu):
    ITEMS = ("Play", "How to play", "Options", "Exit")

    def choose(self, item):
        if item == "Play":
            self.app.replace(Setup(self.app))
        elif item == "How to play":
            self.app.push(HowToPlay(self.app))
        elif item == "Options":
            self.app.push(Options(self.app))
        else:
            self.app.running = False

    def draw(self, now):
        s, L = self.app.screen, self.L
        background(self.app)
        title_logo(s, L, (L.w / 2, L.h * 0.19), now)
        size = int(L.h * 0.15)
        names = rules.VALUES["animal"]
        gap = size * 1.25
        x0 = L.w / 2 - gap * (len(names) - 1) / 2
        for i, name in enumerate(names):
            bob = math.sin(now * 2.5 + i) * L.h * 0.01
            img = art.animal(name, size)
            s.blit(img, img.get_rect(center=(x0 + i * gap, L.h * 0.41 + bob)))
        self.rects = [button(s, L, item, (L.w / 2, L.h * (0.59 + i * 0.1)), i == self.focus,
                             width=int(L.w * 0.26))
                      for i, item in enumerate(self.ITEMS)]
        text(s, L.font_small, "A: choose     Hotkey + Start: exit", theme.T.muted,
             midbottom=(L.w / 2, L.h - L.margin))


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
        self.players = list(app.settings["players"])  # (color, seat) in join order
        self.pads = dict(app.settings["pads"])         # seat -> controller ("One each")
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
        self.pads.pop(seat, None)

    @property
    def one_each(self) -> bool:
        return self.app.settings["controllers"] == "each"

    def press_seat(self, seat):
        """A on a seat. With one controller each, the controller that sits
        down is linked to the seat; on a seat someone else's controller (or no
        controller) has, the first press just takes it over, the next changes
        the color."""
        pad = self.app.pad
        if self.one_each and pad is not None and self.seat_color(seat) and self.pads.get(seat) != pad:
            self.pads[seat] = pad
            self.app.sfx("place")
            return
        self.cycle(seat)
        if not self.seat_color(seat):
            self.pads.pop(seat, None)
            self.app.sfx("back")
            return
        if self.one_each and pad is not None:
            self.pads[seat] = pad
        self.app.sfx("place")

    def start(self):
        if len(self.players) >= 2:
            self.app.settings["players"] = list(self.players)
            seated = {s for _, s in self.players}
            self.app.settings["pads"] = {s: p for s, p in self.pads.items() if s in seated}
            save_settings(self.app.settings)
            self.app.sfx("select")
            self.app.replace(Play(self.app, list(self.players)))
        else:
            self.app.sfx("bonk")

    def handle(self, action, now):
        if action in (LEFT, RIGHT, UP, DOWN):
            self.focus = self.MOVES[self.focus].get(action, self.focus)
            self.app.sfx("blip")
        elif action == OK:
            if self.focus == "START":
                self.start()
            else:
                self.press_seat(self.focus)
        elif action == BACK:
            self.app.sfx("back")
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
                self.app.pad = None
                self.press_seat(seat)

    def draw(self, now):
        s, L, T = self.app.screen, self.L, theme.T
        background(self.app)
        for seat, rect in L.panels.items():
            color = self.seat_color(seat)
            focused = self.focus == seat
            pygame.draw.rect(s, T.card if color else T.card_idle, rect, border_radius=L.margin)
            if focused:
                pulse = 0.5 + 0.5 * math.sin(now * 5)
                w = max(4, int(L.margin * (0.25 + 0.15 * pulse)))
                pygame.draw.rect(s, T.text, rect.inflate(w, w), w, border_radius=L.margin + w // 2)
            text(s, L.font_small, rules.SEAT_LABELS[seat], T.muted, midtop=(rect.centerx, rect.y + L.margin))
            if color and self.one_each:
                pad = self.pads.get(seat)
                icon = art.pad_icon(None if pad is None else pad + 1, int(L.h * 0.055))
                at = (rect.x + L.margin * 0.5, rect.bottom - L.margin * 0.5 - icon.get_height())
                s.blit(icon, at)
                text(s, L.font_small, "Press A on yours!" if pad is None
                     else f"Controller {pad + 1}", T.muted,
                     midleft=(at[0] + icon.get_width() + L.margin * 0.4, at[1] + icon.get_height() / 2))
            if color:
                size = int(min(rect.w, rect.h) * 0.42)
                s.blit(art.tile(color, size), art.tile(color, size).get_rect(center=rect.center))
                name = text(s, L.font, rules.LABELS[color], T.text,
                            midtop=(rect.centerx, rect.centery + size / 2 + L.margin / 2))
                if self.players[0][1] == seat:
                    text(s, L.font_small, "Goes first", theme.accent(art.TILE_COLORS[color]),
                         midtop=(rect.centerx, rect.centery + size / 2 + L.margin / 2 + name.get_height()))
            else:
                t = text(s, L.font, "Empty seat", T.muted, center=rect.center)
                if focused:
                    text(s, L.font_small, "Press A to sit here", T.muted,
                         midtop=(rect.centerx, rect.centery + t.get_height()))

        b = L.board
        pygame.draw.rect(s, T.card, b, border_radius=L.margin)
        head = text(s, L.font_big, "Who's playing?", T.text, midtop=(b.centerx, b.top + L.margin * 2))
        if self.one_each:
            lines = [
                "Pick a seat and press A on your own controller.",
                "Press A again for another color, B to leave.",
                "The first one to sit down goes first.",
                "",
                "2 to 4 players, one controller each.",
            ]
        else:
            lines = [
                "Pick a seat and press A to choose a color.",
                "Press A again for another color, B to leave.",
                "The first one to sit down goes first.",
                "",
                "2 to 4 players.",
            ]
        y = b.top + L.margin * 3 + head.get_height()
        for line in lines:
            t = text(s, L.font_small, line, T.muted, midtop=(b.centerx, y))
            y += t.get_height() + L.margin * 0.4
        ok = len(self.players) >= 2
        self.start_rect = button(s, L, "Start game!" if ok else "Need 2 players",
                                 (b.centerx, b.bottom - L.h * 0.16), self.focus == "START", ok,
                                 width=int(b.w * 0.6))
        text(s, L.font_small, "A: choose   B: back   Arrows: move", T.muted,
             midbottom=(b.centerx, b.bottom - L.margin))


class Play(Scene):
    def __init__(self, app, setup):
        super().__init__(app)
        self.setup = setup
        self.screen = GameScreen(app.screen, setup, sfx=app.sfx, pads=self.pads())

    def pads(self) -> dict[str, int] | None:
        """seat -> controller when each player has their own, else None."""
        st = self.app.settings
        return dict(st["pads"]) if st["controllers"] == "each" else None

    def handle(self, action, now):
        if action == MENU:  # any controller can pause
            self.app.sfx("select")
            self.app.push(Pause(self.app, self))
        elif action == BACK:
            pass  # B does nothing in play, so it can't undo or quit by accident
        elif self.wrong_controller():
            if action == OK:
                self.screen.not_your_turn(now)
        else:
            self.screen.handle(action, now)

    def wrong_controller(self) -> bool:
        """One controller each, and someone else's controller pressed on this
        player's turn. A seat with no controller linked, and the keyboard,
        can always play."""
        pads_ = self.screen.pads
        g = self.screen.game
        if pads_ is None or g.phase not in (rules.SPIN, rules.PLACE) or self.app.pad is None:
            return False
        owner = pads_.get(g.player.seat)
        return owner is not None and owner != self.app.pad

    def click(self, pos, now):
        self.screen.click(pos, now)

    def update(self, now):
        self.screen.pads = self.pads()  # follows the option if changed from the pause menu
        self.screen.update(now)

    def draw(self, now):
        self.screen.draw(now)


class Pause(Menu):
    ITEMS = ("Resume", "New board", "Change players", "How to play", "Options", "Exit game")

    def __init__(self, app, play: Play):
        super().__init__(app)
        self.play = play

    def back(self):
        self.app.sfx("back")
        self.app.pop()

    def choose(self, item):
        if item == "Resume":
            self.app.pop()
        elif item == "New board":
            self.play.screen.new_round()
            self.app.pop()
        elif item == "Change players":
            self.app.replace_all(Setup(self.app))
        elif item == "How to play":
            self.app.push(HowToPlay(self.app))
        elif item == "Options":
            self.app.push(Options(self.app))
        else:
            self.app.running = False

    def click(self, pos, now):
        if not any(r.collidepoint(pos) for r in self.rects):
            self.app.pop()
            return
        super().click(pos, now)

    def draw(self, now):
        s, L, T = self.app.screen, self.L, theme.T
        self.play.draw(now)
        shade = pygame.Surface((L.w, L.h), pygame.SRCALPHA)
        shade.fill((10, 10, 20, 160))
        s.blit(shade, (0, 0))
        head = L.font_big.render("Paused", True, T.text)
        step = L.h * 0.095
        box = pygame.Rect(0, 0, int(L.w * 0.34), int(L.margin * 3 + head.get_height() + step * len(self.ITEMS)))
        box.center = (L.w / 2, L.h / 2)
        pygame.draw.rect(s, T.card, box, border_radius=L.margin)
        pygame.draw.rect(s, T.button_line, box, 3, border_radius=L.margin)
        s.blit(head, head.get_rect(midtop=(box.centerx, box.top + L.margin)))
        y0 = box.top + L.margin * 2 + head.get_height() + step / 2
        self.rects = [button(s, L, item, (box.centerx, y0 + i * step), i == self.focus,
                             width=int(box.w * 0.8)) for i, item in enumerate(self.ITEMS)]


class Options(Scene):
    """Theme, sound, music and which pad button confirms."""

    ROWS = ("Theme", "Sound effects", "Music", "A button", "Controllers", "Done")

    def __init__(self, app):
        super().__init__(app)
        self.focus = 0
        self.rects: list[pygame.Rect] = []

    def value(self, row) -> str:
        st = self.app.settings
        if row == "Theme":
            return st["theme"]
        if row == "Sound effects":
            return "On" if st["sound"] else "Off"
        if row == "Music":
            return "On" if st["music"] else "Off"
        if row == "A button":
            return "South" if st["confirm"] == "south" else "East"
        if row == "Controllers":
            return "Shared" if st["controllers"] == "shared" else "One each"
        return ""

    def change(self, row, step=1):
        st = self.app.settings
        if row == "Theme":
            names = theme.ORDER
            st["theme"] = names[(names.index(st["theme"]) + step) % len(names)]
            theme.use(st["theme"])
        elif row == "Sound effects":
            st["sound"] = self.app.sounds.enabled = not st["sound"]
        elif row == "Music":
            st["music"] = not st["music"]
            self.app.sounds.set_music(st["music"])
        elif row == "A button":
            st["confirm"] = "east" if st["confirm"] == "south" else "south"
        elif row == "Controllers":
            st["controllers"] = "each" if st["controllers"] == "shared" else "shared"
        save_settings(st)
        self.app.sfx("select")

    def handle(self, action, now):
        row = self.ROWS[self.focus]
        if action == UP:
            self.focus = (self.focus - 1) % len(self.ROWS)
            self.app.sfx("blip")
        elif action == DOWN:
            self.focus = (self.focus + 1) % len(self.ROWS)
            self.app.sfx("blip")
        elif action in (LEFT, RIGHT) and row != "Done":
            self.change(row, -1 if action == LEFT else 1)
        elif action == OK:
            if row == "Done":
                self.app.sfx("back")
                self.app.pop()
            else:
                self.change(row)
        elif action in (BACK, MENU):
            self.app.sfx("back")
            self.app.pop()

    def click(self, pos, now):
        for i, r in enumerate(self.rects):
            if r.collidepoint(pos):
                self.focus = i
                self.handle(OK, now)
                return

    def draw(self, now):
        s, L, T = self.app.screen, self.L, theme.T
        background(self.app)
        text(s, L.font_big, "Options", T.text, midtop=(L.w / 2, L.margin * 2))
        step = L.h * 0.105
        y0 = L.h * 0.25
        self.rects = []
        for i, row in enumerate(self.ROWS):
            label = row if row == "Done" else f"{row}:  < {self.value(row)} >"
            self.rects.append(button(s, L, label, (L.w / 2, y0 + i * step), i == self.focus,
                                     width=int(L.w * 0.42)))
        notes = {
            "Theme": "The colors around the board.",
            "A button": "South = the bottom button (A on Xbox-style pads). East = the right one.",
            "Music": "A little tune while you play.",
            "Sound effects": "Spins, animal calls, cheers.",
            "Controllers": ("Shared: any controller plays any turn." if self.app.settings["controllers"] == "shared"
                            else "One each: only your own controller plays your turn. Pick it when you sit down."),
        }
        note = notes.get(self.ROWS[self.focus], "")
        if note:
            text(s, L.font_small, note, T.muted, midbottom=(L.w / 2, L.h - L.margin * 3))
        text(s, L.font_small, "Left/Right or A: change     B: back", T.muted,
             midbottom=(L.w / 2, L.h - L.margin))


class HowToPlay(Scene):
    def handle(self, action, now):
        if action in (OK, BACK, MENU):
            self.app.sfx("back")
            self.app.pop()

    def click(self, pos, now):
        self.app.pop()

    def draw(self, now):
        s, L, T = self.app.screen, self.L, theme.T
        background(self.app)
        head = text(s, L.font_big, "How to play", T.text, midtop=(L.w / 2, L.margin))
        icon = int(L.h * 0.085)
        sample = rules.Square("purple", "star", "dots", "lion")
        rows = [
            (art.square(sample, icon), "Spin your spinner, then cover a square that matches it."),
            (None, "No empty match left? Play on any empty square."),
            (None, "You can't play on a square that already has a tile..."),
            (self._word("WILD", (200, 60, 120), icon), "...unless you spin WILD: play anywhere, even on a tile. Stacks hold 4."),
            (self._word("ZOO!", (190, 90, 0), icon), "SPIN-A-ZOO! Everyone passes their spinner clockwise. Spin again!"),
            (art.tile("red", icon), "Get 4 of your tiles in a row (across, down or diagonal) to win!"),
            (None, "Board full and no winner? PLAY AGAIN!"),
        ]
        y = L.margin * 2 + head.get_height()
        x_icon = L.w * 0.12
        row_h = (L.h * 0.82 - y) / len(rows)
        for img, line in rows:
            if img:
                s.blit(img, img.get_rect(center=(x_icon, y + row_h / 2)))
            t = L.font.render(line, True, T.text)
            if t.get_width() > L.w * 0.78:
                t = L.font_small.render(line, True, T.text)
            s.blit(t, t.get_rect(midleft=(x_icon + icon, y + row_h / 2)))
            y += row_h
        text(s, L.font_small, "A: spin / place     Arrows: move     Start: menu     Hotkey + Start: exit",
             T.muted, midbottom=(L.w / 2, L.h - L.margin * 3))
        text(s, L.font_small, "Press A to go back", T.muted, midbottom=(L.w / 2, L.h - L.margin))

    def _word(self, word, color, size):
        f = art.font(int(size * 0.36))
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
        self.pad: int | None = None  # controller behind the last press (None: keyboard/mouse)
        self.settings = load_settings()
        theme.use(self.settings["theme"])
        self.sounds = sound.Sounds(self.settings["sound"], self.settings["music"])

    def sfx(self, name: str) -> None:
        self.sounds.play(name)

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

    def read(self, key: int, scancode: int | None = None) -> tuple[str | None, int | None]:
        """What a key press means: (action, controller). Controller keys are
        found by scancode, so the keyboard layout doesn't matter; the key is
        only used when there's no scancode (tests)."""
        hit = PAD_BY_SCAN.get(scancode) if scancode else PAD_BY_KEY.get(key)
        if hit is None:
            return KEYS.get(key), None
        pad, button = hit
        if button in ("south", "east"):
            return (OK if button == self.settings["confirm"] else BACK), pad
        return DIRECTIONS[button], pad

    def action(self, key: int) -> str | None:
        return self.read(key)[0]

    def frame(self, events, now: float) -> None:
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F4 and event.mod & pygame.KMOD_ALT:
                    self.running = False
                else:
                    action, self.pad = self.read(event.key, getattr(event, "scancode", None))
                    if action:
                        self.scene.handle(action, now)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.pad = None
                self.scene.click(event.pos, now)
            if not self.running:
                return
        self.sounds.update()
        self.scene.update(now)
        self.scene.draw(now)


def main() -> None:
    # SDL minimizes a fullscreen window when it loses focus, and Batocera's
    # popups (like the screenshot flash) take focus for a moment, leaving the
    # game hidden behind EmulationStation. Stay on screen instead.
    os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")
    pygame.mixer.pre_init(sound.RATE, -16, 1, 512)
    pygame.init()
    window = os.environ.get("SPINAZOO_WINDOW")
    if window:
        w, h = (int(v) for v in window.lower().split("x"))
        screen = pygame.display.set_mode((w, h))
    else:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Spin-A-Zoo!")
    pygame.mouse.set_visible(bool(window))
    pygame.key.set_repeat(350, 120)
    app = App(screen)
    app.push(Title(app))
    clock = pygame.time.Clock()
    while app.running:
        app.frame(pygame.event.get(), pygame.time.get_ticks() / 1000)
        pygame.display.flip()
        # 60 fps while something moves (spin, pass, tile drop, confetti), 30
        # otherwise: halves the CPU use for the rest of the time.
        scene = app.scene if app.running else None
        clock.tick(60 if isinstance(scene, Play) and scene.screen.animating() else 30)
    pygame.quit()
