"""Spin-A-Zoo! game screen: layout, drawing, animation and turn flow."""

from __future__ import annotations

import math
import random

import pygame

import art
import rules
import theme
from rules import DRAW, PLACE, SPIN, WILD, WON, ZOO

BOARD_FRAME = (58, 112, 72)
CARD = (255, 251, 243)   # message banners stay light on every theme
GOLD = (255, 200, 40)

WINDUP_TIME = 0.18       # arrow pulls back before it spins
SPIN_TIME = 2.0
PASS_TIME = 0.9
DROP_TIME = 0.35
MESSAGE_TIME = 1.5
RIPPLE_STEP = 0.035      # delay between squares lighting up after a spin

# Inputs the screen understands (keyboard and pads both map onto these).
LEFT, RIGHT, UP, DOWN, OK, BACK, MENU = "left", "right", "up", "down", "ok", "back", "menu"


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)


def ease_out_back(t: float) -> float:
    c = 1.9
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


class Layout:
    """Where everything goes for a given screen size: the board fills the
    height, two spinner panels on each side."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        m = self.margin = round(h * 0.03)
        panel_min = h * 0.26
        self.board_size = int(min(h - 2 * m, w - 2 * panel_min - 4 * m))
        bx = (w - self.board_size) // 2
        by = (h - self.board_size) // 2
        self.board = pygame.Rect(bx, by, self.board_size, self.board_size)
        gap = self.gap = max(4, round(self.board_size * 0.012))
        self.cell = (self.board_size - 6 * gap) // rules.SIZE
        extra = (self.board_size - 6 * gap - self.cell * rules.SIZE) // 2
        self.cells = [[pygame.Rect(bx + gap + extra + c * (self.cell + gap),
                                   by + gap + extra + r * (self.cell + gap), self.cell, self.cell)
                       for c in range(rules.SIZE)] for r in range(rules.SIZE)]
        pw = bx - 2 * m
        ph = (h - 3 * m) // 2
        left, right = m, self.board.right + m
        top, bottom = m, 2 * m + ph
        self.panels = {
            "TL": pygame.Rect(left, top, pw, ph),
            "TR": pygame.Rect(right, top, pw, ph),
            "BR": pygame.Rect(right, bottom, pw, ph),
            "BL": pygame.Rect(left, bottom, pw, ph),
        }
        # panel: spinner name, spinner (as big as fits), player line
        self.dial = int(min(pw * 0.94, ph * 0.7))
        self.font_big = art.font(max(24, int(h * 0.075)))
        self.font = art.font(max(18, int(h * 0.045)))
        self.font_small = art.font(max(14, int(h * 0.032)))

    def dial_center(self, seat: str) -> tuple[float, float]:
        p = self.panels[seat]
        return p.centerx, p.y + p.h * 0.115 + self.dial / 2

    def label_y(self, seat: str) -> float:
        """Bottom of the spinner name, just above the spinner."""
        return self.dial_center(seat)[1] - self.dial / 2 - 2


class Anim:
    def __init__(self, duration: float, now: float):
        self.start, self.duration = now, duration

    def t(self, now: float) -> float:
        return min(1.0, (now - self.start) / self.duration)

    def done(self, now: float) -> bool:
        return now - self.start >= self.duration


def star_points(cx, cy, r):
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36)
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return pts


def result_icon(feature: str, section: str, size: int) -> pygame.Surface:
    """A picture of a spin result, for players who can't read yet."""
    if section == ZOO:
        return art.dial(feature, size)
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size / 2
    if section == WILD:
        colors = list(art.SQUARE_COLORS.values())
        for i, col in enumerate(colors):
            a0, a1 = i * 72 - 90, (i + 1) * 72 - 90
            pts = [(c, c)] + [(c + c * 0.95 * math.cos(math.radians(a0 + (a1 - a0) * k / 8)),
                               c + c * 0.95 * math.sin(math.radians(a0 + (a1 - a0) * k / 8))) for k in range(9)]
            pygame.draw.polygon(s, col, pts)
        pygame.draw.circle(s, art.INK, (c, c), c * 0.95, max(2, size // 30))
        pygame.draw.polygon(s, art.WHITE, star_points(c, c, c * 0.62))
        pygame.draw.polygon(s, art.INK, star_points(c, c, c * 0.62), max(2, size // 40))
        return s
    if feature == "color":
        pygame.draw.circle(s, art.SQUARE_COLORS[section], (c, c), c * 0.9)
        pygame.draw.circle(s, art.INK, (c, c), c * 0.9, max(2, size // 30))
        return s
    if feature == "shape":
        return art.shape_icon(section, size)
    if feature == "pattern":
        return art.pattern_swatch(section, size)
    return art.animal(section, size)


class GameScreen:
    def __init__(self, screen: pygame.Surface, setup: list[tuple[str, str]], seed: int | None = None,
                 sfx=None):
        self.screen = screen
        self.setup = setup
        self.sfx = sfx or (lambda name: None)  # play a sound by name
        self.layout = Layout(*screen.get_size())
        self.rng = random.Random(seed)
        self.wins: dict[str, int] = {color: 0 for color, _ in setup}  # across rounds
        self.new_round()

    # --- round state -----------------------------------------------------

    def new_round(self) -> None:
        self.game = rules.Game.new(self.setup, random.Random(self.rng.random()))
        self.angles = {f: self.rng.uniform(0, 360) for f in rules.FEATURES}
        self.board_surface = self._render_board()
        self.cursor = (2, 2)
        self.spin_anim: Anim | None = None
        self.spin_from = self.spin_to = 0.0
        self.spin_section: str | None = None
        self.spin_index = 0
        self.landed: tuple[str, int, float] | None = None  # feature, section, when
        self.reveal_time = -1.0
        self.pass_anim: Anim | None = None
        self.drop: tuple[int, int, Anim] | None = None
        self.message: tuple[str, str, float, pygame.Surface | None] | None = None
        self.hint_until = 0.0
        self.tick_section: int | None = None
        self.queued: list[tuple[float, str]] = []  # (time, sound)
        self.confetti: list[list] = []
        self.last_update: float | None = None

    def _render_board(self) -> pygame.Surface:
        L = self.layout
        s = pygame.Surface(L.board.size, pygame.SRCALPHA)
        pygame.draw.rect(s, BOARD_FRAME, s.get_rect(), border_radius=L.gap * 3)
        pygame.draw.rect(s, art.shade(BOARD_FRAME, 0.7), s.get_rect(), max(3, L.gap // 2),
                         border_radius=L.gap * 3)
        for r in range(rules.SIZE):
            for c in range(rules.SIZE):
                rect = L.cells[r][c].move(-L.board.x, -L.board.y)
                s.blit(art.square(self.game.board[r][c], L.cell), rect)
        return art.fast(s)

    def busy(self) -> bool:
        return bool(self.spin_anim or self.pass_anim or self.drop)

    def animating(self) -> bool:
        """Anything moving on screen (decides the frame rate)."""
        return self.busy() or bool(self.confetti) or self.game.phase == WON

    def later(self, delay: float, name: str, now: float) -> None:
        self.queued.append((now + delay, name))

    def say(self, title: str, sub: str = "", now: float = 0.0, forever: bool = False,
            icon: pygame.Surface | None = None) -> None:
        self.message = (title, sub, math.inf if forever else now + MESSAGE_TIME, icon)

    # --- input -----------------------------------------------------------

    def handle(self, action: str, now: float) -> None:
        g = self.game
        if g.phase in (WON, DRAW):
            if action == OK and not self.busy():
                self.sfx("select")
                self.new_round()
            return
        if self.busy():
            return
        if g.phase == SPIN and action == OK:
            self.start_spin(now)
        elif g.phase == PLACE:
            r, c = self.cursor
            if action in (LEFT, RIGHT, UP, DOWN):
                dr, dc = {LEFT: (0, -1), RIGHT: (0, 1), UP: (-1, 0), DOWN: (1, 0)}[action]
                self.cursor = ((r + dr) % rules.SIZE, (c + dc) % rules.SIZE)
                self.sfx("blip")
            elif action == OK:
                self.try_place(r, c, now)

    def click(self, pos: tuple[int, int], now: float) -> None:
        """Mouse or touch: tap the active spinner to spin, a square to place."""
        g = self.game
        if g.phase in (WON, DRAW) or g.phase == SPIN:
            if g.phase == SPIN and not self.layout.panels[g.player.seat].collidepoint(pos):
                return
            self.handle(OK, now)
            return
        for r in range(rules.SIZE):
            for c in range(rules.SIZE):
                if self.layout.cells[r][c].collidepoint(pos):
                    self.cursor = (r, c)
                    if not self.busy():
                        self.try_place(r, c, now)

    def start_spin(self, now: float) -> None:
        sections = rules.spinner_sections(self.game.spinner)
        idx = self.rng.randrange(len(sections))
        self.spin_index = idx
        self.spin_section = sections[idx]
        feature = self.game.spinner
        start = self.angles[feature]
        target = art.section_angle(idx) + self.rng.uniform(-15, 15)
        turns = self.rng.choice((3, 4))
        self.spin_from = start
        self.spin_to = start + 360 * turns + ((target - start) % 360)
        self.spin_anim = Anim(WINDUP_TIME + SPIN_TIME, now)
        self.tick_section = None
        self.landed = None
        self.message = None
        self.sfx("spin")

    def spin_angle(self, now: float) -> float:
        """Arrow angle during a spin: a short pull back, then the spin."""
        e = now - self.spin_anim.start
        windup = 14.0
        if e < WINDUP_TIME:
            return self.spin_from - windup * math.sin(math.pi / 2 * e / WINDUP_TIME)
        t = ease_out_cubic(min(1.0, (e - WINDUP_TIME) / SPIN_TIME))
        start = self.spin_from - windup
        return start + (self.spin_to - start) * t

    def try_place(self, r: int, c: int, now: float) -> None:
        if (r, c) not in self.game.legal_moves():
            self.hint_until = now + 1.2
            self.sfx("bonk")
            return
        who = self.game.turn
        self.game.place(r, c)
        self.drop = (r, c, Anim(DROP_TIME, now))
        self.message = None
        self.sfx("place")
        if self.game.phase == WON:
            color = self.game.players[who].color
            self.wins[color] = self.wins.get(color, 0) + 1
            self.say(f"{rules.LABELS[color]} wins!", "Press A to play again", now, forever=True,
                     icon=art.tile(color, 96))
            self.later(0.15, "win", now)
            self._throw_confetti()
        elif self.game.phase == DRAW:
            self.say("No winner!", "PLAY AGAIN!  Press A", now, forever=True)
            self.later(0.2, "draw", now)
        else:
            color = self.game.player.color
            self.say(f"{rules.LABELS[color]}'s turn!", "", now, icon=art.tile(color, 72))
            self.later(0.3, "turn", now)

    # --- update ----------------------------------------------------------

    def update(self, now: float) -> None:
        g = self.game
        dt = 0.0 if self.last_update is None else min(0.1, now - self.last_update)
        self.last_update = now
        for item in [q for q in self.queued if q[0] <= now]:
            self.queued.remove(item)
            self.sfx(item[1])
        self._update_confetti(dt)
        if self.spin_anim and not self.spin_anim.done(now):
            # tick each time a section passes the arrow; slows as the spin does
            section = int(((self.spin_angle(now) % 360) + 22.5) // 45) % 8
            if section != self.tick_section:
                if self.tick_section is not None:
                    self.sfx("tick")
                self.tick_section = section
        if self.spin_anim and self.spin_anim.done(now):
            feature = g.spinner
            self.angles[feature] = self.spin_to % 360
            self.spin_anim = None
            section = self.spin_section
            self.landed = (feature, self.spin_index, now)
            g.resolve(section)
            icon = result_icon(feature, section, int(self.layout.h * 0.09))
            self.sfx("stop")
            if section == ZOO:
                self.pass_anim = Anim(PASS_TIME, now)
                self.say("SPIN-A-ZOO!", "Pass the spinners!", now, icon=icon)
                self.later(0.1, "zoo", now)
            elif section == WILD:
                self.say("WILD!", "Play on any square, even on a tile", now, icon=icon)
                self.later(0.1, "wild", now)
                self._start_place(now)
            else:
                label = rules.LABELS[section]
                moves = g.legal_moves()
                matched = any(g.board[r][c].get(feature) == section for r, c in moves)
                if matched:
                    self.say(f"{label}!", f"Cover a {label.lower()} square", now, icon=icon)
                    self.later(0.1, section if feature == "animal" else feature, now)
                else:
                    self.say(f"{label}!", "None left, pick any empty square", now, icon=icon)
                    self.later(0.1, "any", now)
                self._start_place(now)
        if self.pass_anim and self.pass_anim.done(now):
            self.pass_anim = None
            self.say("Spin again!", "", now)
        if self.drop and self.drop[2].done(now):
            self.drop = None
        if self.message and now > self.message[2]:
            self.message = None

    def _start_place(self, now: float) -> None:
        self._cursor_to_legal()
        self.reveal_time = now

    def _throw_confetti(self) -> None:
        L = self.layout
        colors = list(art.SQUARE_COLORS.values()) + [GOLD, art.WHITE]
        for _ in range(160):
            self.confetti.append([
                self.rng.uniform(0, L.w), self.rng.uniform(-L.h * 0.6, 0),       # x, y
                self.rng.uniform(-L.h * 0.15, L.h * 0.15), self.rng.uniform(0, L.h * 0.3),  # vx, vy
                self.rng.uniform(0, math.tau), self.rng.uniform(-8, 8),           # angle, spin
                self.rng.choice(colors), self.rng.uniform(0.6, 1.2) * L.h * 0.012,  # color, size
            ])

    def _update_confetti(self, dt: float) -> None:
        if not self.confetti:
            return
        g = self.layout.h * 0.9
        for p in self.confetti:
            p[3] += g * dt
            p[3] *= 0.985  # air drag, so it flutters
            p[0] += p[2] * dt + math.sin(p[4]) * 0.6
            p[1] += p[3] * dt
            p[4] += p[5] * dt
        self.confetti = [p for p in self.confetti if p[1] < self.layout.h + 20]

    def _previous_spinners(self) -> dict[str, str]:
        """Spinner positions before the last pass (one seat counter-clockwise)."""
        n = len(rules.SEATS)
        return {rules.SEATS[i]: self.game.spinners[rules.SEATS[(i + 1) % n]] for i in range(n)}

    def _cursor_to_legal(self) -> None:
        moves = self.game.legal_moves()
        if not moves or self.cursor in moves:
            return
        r0, c0 = self.cursor
        self.cursor = min(moves, key=lambda m: (abs(m[0] - r0) + abs(m[1] - c0), m))

    # --- drawing ---------------------------------------------------------

    def draw(self, now: float) -> None:
        L = self.layout
        self.screen.blit(theme.background(theme.T.name, L.w, L.h), (0, 0))
        self._draw_panels(now)
        self.screen.blit(self.board_surface, L.board)
        self._draw_board_overlay(now)
        self._draw_spinners(now)
        self._draw_confetti()
        self._draw_message()

    def _prompt(self) -> str:
        """What the active player should do now, shown under their name."""
        g = self.game
        if self.busy():
            return ""
        if g.phase == SPIN:
            return "Press A to spin!"
        if g.last_spin == WILD:
            return "WILD: any square"
        moves = g.legal_moves()
        if any(g.board[r][c].get(g.spinner) == g.last_spin for r, c in moves):
            return "Pick a bright square"
        return "Any empty square"

    def _draw_panels(self, now: float) -> None:
        L, g, T = self.layout, self.game, theme.T
        seated = {p.seat: (i, p) for i, p in enumerate(g.players)}
        for seat, rect in L.panels.items():
            active = seat == g.player.seat and g.phase in (SPIN, PLACE)
            pygame.draw.rect(self.screen, T.card if seat in seated else T.card_idle, rect,
                             border_radius=L.margin)
            if active:
                color = art.TILE_COLORS[g.player.color]
                pulse = 0.5 + 0.5 * math.sin(now * 5)
                width = max(4, int(L.margin * (0.25 + 0.15 * pulse)))
                pygame.draw.rect(self.screen, theme.accent(color), rect.inflate(width, width), width,
                                 border_radius=L.margin + width // 2)
                self._draw_pointer(rect, seat, theme.accent(color))
            fy = rect.bottom - rect.h * 0.085
            if seat in seated:
                _, p = seated[seat]
                ts = int(L.h * 0.06)
                name = L.font.render(rules.LABELS[p.color], True, T.text)
                prompt = self._prompt() if active else ""
                if prompt:
                    line = L.font_small.render(prompt, True, theme.accent(art.TILE_COLORS[p.color]))
                else:
                    line = L.font_small.render(f"{p.tiles} tiles", True, T.muted)
                total = ts + 10 + max(name.get_width(), line.get_width())
                x = rect.centerx - total // 2
                self.screen.blit(art.tile(p.color, ts), (x, fy - ts // 2))
                self.screen.blit(name, (x + ts + 10, fy - name.get_height() + 4))
                self.screen.blit(line, (x + ts + 10, fy + 4))
                self._draw_wins(rect, self.wins.get(p.color, 0))
            else:
                t = L.font_small.render("Empty seat", True, T.muted)
                self.screen.blit(t, t.get_rect(center=(rect.centerx, fy)))

    def _draw_wins(self, rect, wins: int) -> None:
        """Gold stars in the panel corner, one per round won."""
        if not wins:
            return
        L = self.layout
        r = L.h * 0.017
        x, y = rect.right - L.margin * 0.6 - r, rect.top + L.margin * 0.6 + r
        if wins > 4:
            t = L.font_small.render(f"x{wins}", True, theme.T.text)
            self.screen.blit(t, t.get_rect(midright=(x + r, y)))
            x -= t.get_width() + r * 0.6
            wins = 1
        for i in range(wins):
            pts = star_points(x - i * r * 2.3, y, r)
            pygame.draw.polygon(self.screen, GOLD, pts)
            pygame.draw.polygon(self.screen, art.INK, pts, 2)

    def _draw_pointer(self, rect, seat, color) -> None:
        """Small triangle on the panel edge, pointing at the board."""
        L = self.layout
        size = L.margin * 0.8
        cy = L.dial_center(seat)[1]
        if seat in ("TL", "BL"):
            x = rect.right + L.margin * 0.15
            pts = [(x, cy - size), (x + size, cy), (x, cy + size)]
        else:
            x = rect.left - L.margin * 0.15
            pts = [(x, cy - size), (x - size, cy), (x, cy + size)]
        pygame.draw.polygon(self.screen, color, pts)

    def _spinner_positions(self, now: float) -> dict[str, tuple[float, float]]:
        L, g = self.layout, self.game
        pos = {}
        if self.pass_anim:
            t = ease_in_out(self.pass_anim.t(now))
            before = self._previous_spinners()
            for i, seat in enumerate(rules.SEATS):
                feature = before[seat]
                nxt = rules.SEATS[(i + 1) % len(rules.SEATS)]
                (x0, y0), (x1, y1) = L.dial_center(seat), L.dial_center(nxt)
                lift = math.sin(t * math.pi) * L.h * 0.04
                pos[feature] = (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t - lift)
        else:
            for seat, feature in g.spinners.items():
                pos[feature] = L.dial_center(seat)
        return pos

    def _draw_spinners(self, now: float) -> None:
        L, g = self.layout, self.game
        positions = self._spinner_positions(now)
        spinning = g.spinner if self.spin_anim else None
        order = sorted(positions, key=lambda f: f == spinning)  # spinning one on top
        for feature in order:
            cx, cy = positions[feature]
            d = art.dial(feature, L.dial)
            self.screen.blit(d, (cx - L.dial / 2, cy - L.dial / 2))
            if self.landed and self.landed[0] == feature and not self.pass_anim:
                self._draw_landed_glow(cx, cy, self.landed[1], now - self.landed[2])
            label = L.font_small.render(rules.LABELS[feature].upper(), True, theme.T.text)
            self.screen.blit(label, label.get_rect(midbottom=(cx, cy - L.dial / 2 - 2)))
            angle = self.spin_angle(now) if feature == spinning else self.angles[feature]
            art.draw_arrow(self.screen, cx, cy, L.dial, angle, self._arrow_color(feature))

    def _arrow_color(self, feature: str) -> tuple:
        """Arrows take the colour of the player at the spinner's seat (the
        seat it is moving to while spinners are passed); grey when empty."""
        seat = next(s for s, f in self.game.spinners.items() if f == feature)
        player = next((p for p in self.game.players if p.seat == seat), None)
        return art.TILE_COLORS[player.color] if player else (205, 205, 215)

    def _draw_landed_glow(self, cx, cy, index, age) -> None:
        """Outline the section the arrow stopped on, pulsing for a moment."""
        if age > 2.5:
            return
        L = self.layout
        r = L.dial * 0.48
        a0 = art.section_angle(index) - 22.5 - 90
        pts = [(cx, cy)] + [(cx + r * math.cos(math.radians(a0 + 45 * k / 10)),
                             cy + r * math.sin(math.radians(a0 + 45 * k / 10))) for k in range(11)]
        pulse = 0.5 + 0.5 * math.sin(age * 12)
        width = max(3, int(L.dial * (0.02 + 0.015 * pulse)))
        pygame.draw.polygon(self.screen, GOLD, pts, width)

    def _draw_board_overlay(self, now: float) -> None:
        L, g = self.layout, self.game
        legal = set(g.legal_moves()) if g.phase == PLACE and not self.busy() else None
        dim = pygame.Surface((L.cell, L.cell), pygame.SRCALPHA)
        pygame.draw.rect(dim, (20, 20, 30, 140), dim.get_rect(), border_radius=L.cell // 10)
        ts = int(L.cell * 0.74)
        for r in range(rules.SIZE):
            for c in range(rules.SIZE):
                rect = L.cells[r][c]
                stack = g.stacks[r][c]
                dropping = self.drop and self.drop[:2] == (r, c)
                for k, who in enumerate(stack):
                    depth = len(stack) - 1 - k
                    size = ts
                    top = k == len(stack) - 1
                    if dropping and top:
                        # falls in big, squashes past its size, settles
                        t = self.drop[2].t(now)
                        size = int(ts * (1.5 - 0.5 * ease_out_back(t)))
                    img = art.tile(g.players[who].color, max(4, size))
                    off = depth * L.cell * 0.04
                    if g.phase == WON and g.win_line and (r, c) in g.win_line and top:
                        i = g.win_line.index((r, c))
                        off -= abs(math.sin(now * 6 + i * 0.7)) * L.cell * 0.1
                    self.screen.blit(img, img.get_rect(center=(rect.centerx, rect.centery + off)))
                if dropping:
                    t = self.drop[2].t(now)
                    ring = pygame.Surface(rect.size, pygame.SRCALPHA)
                    rad = ts * (0.45 + 0.35 * t)
                    pygame.draw.circle(ring, (255, 255, 255, int(200 * (1 - t))),
                                       (rect.w / 2, rect.h / 2), rad, max(2, L.gap // 2))
                    self.screen.blit(ring, rect)
                if len(stack) > 1:
                    self._badge(rect, len(stack))
                if legal is not None and (r, c) not in legal:
                    self.screen.blit(dim, rect)
        if legal is not None:
            self._draw_ripple(legal, now)
        if g.phase == PLACE and not self.busy():
            r, c = self.cursor
            rect = L.cells[r][c]
            pulse = 0.5 + 0.5 * math.sin(now * 8)
            grow = int(L.gap * (1 + pulse))
            color = art.TILE_COLORS[g.player.color]
            pygame.draw.rect(self.screen, art.WHITE, rect.inflate(grow * 2, grow * 2),
                             max(4, L.gap), border_radius=L.cell // 8)
            pygame.draw.rect(self.screen, color, rect.inflate(grow * 2 - 8, grow * 2 - 8),
                             max(3, L.gap // 2), border_radius=L.cell // 8)
            if now < self.hint_until:
                t = L.font_small.render("Pick a bright square", True, art.WHITE, (40, 32, 48))
                self.screen.blit(t, t.get_rect(midtop=(rect.centerx, rect.bottom + 4)))
        if g.phase == WON and g.win_line:
            a = L.cells[g.win_line[0][0]][g.win_line[0][1]].center
            b = L.cells[g.win_line[-1][0]][g.win_line[-1][1]].center
            pygame.draw.line(self.screen, art.INK, a, b, int(L.cell * 0.16))
            pygame.draw.line(self.screen, GOLD, a, b, int(L.cell * 0.1))
            for r, c in g.win_line:
                pygame.draw.rect(self.screen, GOLD, L.cells[r][c], max(5, L.gap),
                                 border_radius=L.cell // 10)

    def _draw_ripple(self, legal, now) -> None:
        """Usable squares flash one after another, spreading from the cursor."""
        age = now - self.reveal_time
        if age < 0 or age > 1.5:
            return
        L = self.layout
        r0, c0 = self.cursor
        order = sorted(legal, key=lambda m: (abs(m[0] - r0) + abs(m[1] - c0), m))
        for i, (r, c) in enumerate(order):
            t = (age - i * RIPPLE_STEP) / 0.4
            if 0 <= t <= 1:
                rect = L.cells[r][c]
                glow = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(glow, (255, 255, 255, int(150 * (1 - t))), glow.get_rect(),
                                 border_radius=L.cell // 10)
                self.screen.blit(glow, rect)

    def _badge(self, rect, n) -> None:
        L = self.layout
        rad = int(L.cell * 0.13)
        center = (rect.right - rad - 3, rect.top + rad + 3)
        pygame.draw.circle(self.screen, art.INK, center, rad)
        pygame.draw.circle(self.screen, art.WHITE, center, rad - 3)
        t = L.font_small.render(str(n), True, art.INK)
        self.screen.blit(t, t.get_rect(center=center))

    def _draw_confetti(self) -> None:
        for x, y, _, _, a, _, color, size in self.confetti:
            w, h = size, size * 0.55 * abs(math.cos(a * 1.7)) + 1
            ca, sa = math.cos(a), math.sin(a)
            pts = [(x + dx * ca - dy * sa, y + dx * sa + dy * ca)
                   for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h))]
            pygame.draw.polygon(self.screen, color, pts)

    def _draw_message(self) -> None:
        if not self.message:
            return
        L = self.layout
        title, sub, _, icon = self.message
        ti = L.font_big.render(title, True, art.INK)
        si = L.font.render(sub, True, (90, 80, 95)) if sub else None
        text_w = max(ti.get_width(), si.get_width() if si else 0)
        text_h = ti.get_height() + (si.get_height() if si else 0)
        icon_w = icon.get_width() + L.margin if icon else 0
        w = text_w + icon_w + L.margin * 2
        h = max(text_h, icon.get_height() if icon else 0) + L.margin
        box = pygame.Rect(0, 0, w, h)
        box.center = L.board.center
        g = self.game
        if g.phase not in (WON, DRAW):
            box.top = L.board.top + L.margin
        elif g.phase == WON and g.win_line:
            # keep the winning row in view
            row = sum(r for r, _ in g.win_line) / len(g.win_line)
            if row >= 2:
                box.top = L.board.top + L.margin
            else:
                box.bottom = L.board.bottom - L.margin
        shadow = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 90), shadow.get_rect(), border_radius=L.margin)
        self.screen.blit(shadow, box.move(4, 6))
        pygame.draw.rect(self.screen, CARD, box, border_radius=L.margin)
        pygame.draw.rect(self.screen, art.INK, box, 4, border_radius=L.margin)
        tx = box.x + L.margin + icon_w
        if icon:
            self.screen.blit(icon, icon.get_rect(midleft=(box.x + L.margin, box.centery)))
        top = box.centery - text_h / 2
        self.screen.blit(ti, ti.get_rect(midtop=(tx + text_w / 2, top)))
        if si:
            self.screen.blit(si, si.get_rect(midtop=(tx + text_w / 2, top + ti.get_height())))
