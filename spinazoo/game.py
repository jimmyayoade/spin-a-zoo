"""Spin-a-Zoo game screen: layout, drawing, animation and turn flow."""

from __future__ import annotations

import math
import os
import random

import pygame

import art
import rules
from rules import DRAW, PLACE, SPIN, WILD, WON, ZOO

BG = (250, 244, 232)
BOARD_FRAME = (58, 112, 72)
CARD = (255, 251, 243)
CARD_IDLE = (238, 231, 220)
GOLD = (255, 200, 40)

SPIN_TIME = 2.0
PASS_TIME = 0.9
DROP_TIME = 0.25
MESSAGE_TIME = 1.4

# Inputs the screen understands (keyboard and pads both map onto these).
LEFT, RIGHT, UP, DOWN, OK, BACK = "left", "right", "up", "down", "ok", "back"


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)


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
        self.dial = int(min(pw * 0.78, ph * 0.64))
        self.font_big = pygame.font.Font(None, max(24, int(h * 0.075)))
        self.font = pygame.font.Font(None, max(18, int(h * 0.045)))
        self.font_small = pygame.font.Font(None, max(14, int(h * 0.032)))

    def dial_center(self, seat: str) -> tuple[float, float]:
        p = self.panels[seat]
        return p.centerx, p.y + p.h * 0.47


class Anim:
    def __init__(self, duration: float, now: float):
        self.start, self.duration = now, duration

    def t(self, now: float) -> float:
        return min(1.0, (now - self.start) / self.duration)

    def done(self, now: float) -> bool:
        return now - self.start >= self.duration


class GameScreen:
    def __init__(self, screen: pygame.Surface, setup: list[tuple[str, str]], seed: int | None = None):
        self.screen = screen
        self.setup = setup
        self.layout = Layout(*screen.get_size())
        self.rng = random.Random(seed)
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
        self.pass_anim: Anim | None = None
        self.drop: tuple[int, int, Anim] | None = None
        self.message: tuple[str, str, float] | None = None
        self.hint_until = 0.0

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
        return s

    def busy(self) -> bool:
        return bool(self.spin_anim or self.pass_anim or self.drop)

    def say(self, title: str, sub: str = "", now: float = 0.0, forever: bool = False) -> None:
        self.message = (title, sub, math.inf if forever else now + MESSAGE_TIME)

    # --- input -----------------------------------------------------------

    def handle(self, action: str, now: float) -> None:
        g = self.game
        if g.phase in (WON, DRAW):
            if action == OK and not self.busy():
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
        self.spin_section = sections[idx]
        feature = self.game.spinner
        start = self.angles[feature]
        target = art.section_angle(idx) + self.rng.uniform(-15, 15)
        turns = self.rng.choice((3, 4))
        self.spin_from = start
        self.spin_to = start + 360 * turns + ((target - start) % 360)
        self.spin_anim = Anim(SPIN_TIME, now)
        self.message = None

    def try_place(self, r: int, c: int, now: float) -> None:
        if (r, c) not in self.game.legal_moves():
            self.hint_until = now + 1.2
            return
        who = self.game.turn
        self.game.place(r, c)
        self.drop = (r, c, Anim(DROP_TIME, now))
        self.message = None
        if self.game.phase == WON:
            name = rules.LABELS[self.game.players[who].color]
            self.say(f"{name} wins!", "Press A to play again", now, forever=True)
        elif self.game.phase == DRAW:
            self.say("No winner!", "PLAY AGAIN!  Press A", now, forever=True)

    # --- update ----------------------------------------------------------

    def update(self, now: float) -> None:
        g = self.game
        if self.spin_anim and self.spin_anim.done(now):
            self.angles[g.spinner] = self.spin_to % 360
            self.spin_anim = None
            section = self.spin_section
            g.resolve(section)
            if section == ZOO:
                self.pass_anim = Anim(PASS_TIME, now)
                self.say("SPIN A ZOO!", "Pass the spinners!", now)
            elif section == WILD:
                self.say("WILD!", "Play on any square, even on a tile", now)
                self._cursor_to_legal()
            else:
                label = rules.LABELS[section]
                moves = g.legal_moves()
                matched = any(g.board[r][c].get(g.spinner) == section for r, c in moves)
                if matched:
                    self.say(f"{label}!", f"Cover a {label.lower()} square", now)
                else:
                    self.say(f"{label}!", "None left, pick any empty square", now)
                self._cursor_to_legal()
        if self.pass_anim and self.pass_anim.done(now):
            self.pass_anim = None
            self.say("Spin again!", "", now)
        if self.drop and self.drop[2].done(now):
            self.drop = None
        if self.message and now > self.message[2]:
            self.message = None

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
        s = self.screen
        s.fill(BG)
        self._draw_panels(now)
        s.blit(self.board_surface, self.layout.board)
        self._draw_board_overlay(now)
        self._draw_spinners(now)
        self._draw_message()

    def _draw_panels(self, now: float) -> None:
        L, g = self.layout, self.game
        seated = {p.seat: (i, p) for i, p in enumerate(g.players)}
        for seat, rect in L.panels.items():
            active = seat == g.player.seat and g.phase in (SPIN, PLACE)
            pygame.draw.rect(self.screen, CARD if seat in seated else CARD_IDLE, rect,
                             border_radius=L.margin)
            if active:
                color = art.TILE_COLORS[g.player.color]
                pulse = 0.5 + 0.5 * math.sin(now * 5)
                width = max(4, int(L.margin * (0.25 + 0.15 * pulse)))
                pygame.draw.rect(self.screen, color, rect.inflate(width, width), width,
                                 border_radius=L.margin + width // 2)
                self._draw_pointer(rect, seat, color)
            # footer: who sits here
            fy = rect.bottom - L.h * 0.055
            if seat in seated:
                _, p = seated[seat]
                ts = int(L.h * 0.06)
                name = L.font.render(rules.LABELS[p.color], True, art.INK)
                prompt = self._prompt() if active else ""
                if prompt:
                    left = L.font_small.render(prompt, True, art.TILE_COLORS[p.color])
                else:
                    left = L.font_small.render(f"{p.tiles} tiles", True, (110, 100, 110))
                total = ts + 10 + max(name.get_width(), left.get_width())
                x = rect.centerx - total // 2
                self.screen.blit(art.tile(p.color, ts), (x, fy - ts // 2))
                self.screen.blit(name, (x + ts + 10, fy - name.get_height() + 4))
                self.screen.blit(left, (x + ts + 10, fy + 4))
            else:
                t = L.font_small.render("Empty seat", True, (150, 140, 150))
                self.screen.blit(t, t.get_rect(center=(rect.centerx, fy)))

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

    def _draw_pointer(self, rect, seat, color) -> None:
        """Small triangle on the panel edge, pointing at the board."""
        L = self.layout
        size = L.margin * 0.8
        cy = rect.y + rect.h * 0.47
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
            label = L.font.render(rules.LABELS[feature].upper(), True, art.INK)
            self.screen.blit(label, label.get_rect(midbottom=(cx, cy - L.dial / 2 - 2)))
            angle = self.angles[feature]
            if feature == spinning:
                t = ease_out_cubic(self.spin_anim.t(now))
                angle = self.spin_from + (self.spin_to - self.spin_from) * t
            art.draw_arrow(self.screen, cx, cy, L.dial, angle)

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
                    if dropping and k == len(stack) - 1:
                        size = int(ts * (1.35 - 0.35 * ease_out_cubic(self.drop[2].t(now))))
                    img = art.tile(g.players[who].color, size)
                    off = depth * L.cell * 0.04
                    self.screen.blit(img, img.get_rect(center=(rect.centerx, rect.centery + off)))
                if len(stack) > 1:
                    self._badge(rect, len(stack))
                if legal is not None and (r, c) not in legal:
                    self.screen.blit(dim, rect)
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

    def _badge(self, rect, n) -> None:
        L = self.layout
        rad = int(L.cell * 0.13)
        center = (rect.right - rad - 3, rect.top + rad + 3)
        pygame.draw.circle(self.screen, art.INK, center, rad)
        pygame.draw.circle(self.screen, art.WHITE, center, rad - 3)
        t = L.font_small.render(str(n), True, art.INK)
        self.screen.blit(t, t.get_rect(center=center))

    def _draw_message(self) -> None:
        if not self.message:
            return
        L = self.layout
        title, sub, _ = self.message
        ti = L.font_big.render(title, True, art.INK)
        si = L.font.render(sub, True, (90, 80, 95)) if sub else None
        w = max(ti.get_width(), si.get_width() if si else 0) + L.margin * 2
        h = ti.get_height() + (si.get_height() if si else 0) + L.margin
        box = pygame.Rect(0, 0, w, h)
        box.center = L.board.center
        if self.game.phase not in (WON, DRAW):
            box.top = L.board.top + L.margin
        shadow = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 70), shadow.get_rect(), border_radius=L.margin)
        self.screen.blit(shadow, box.move(4, 6))
        pygame.draw.rect(self.screen, CARD, box, border_radius=L.margin)
        pygame.draw.rect(self.screen, art.INK, box, 4, border_radius=L.margin)
        self.screen.blit(ti, ti.get_rect(midtop=(box.centerx, box.top + L.margin // 2)))
        if si:
            self.screen.blit(si, si.get_rect(midbottom=(box.centerx, box.bottom - L.margin // 2)))


KEYS = {
    pygame.K_LEFT: LEFT, pygame.K_RIGHT: RIGHT, pygame.K_UP: UP, pygame.K_DOWN: DOWN,
    pygame.K_RETURN: OK, pygame.K_SPACE: OK, pygame.K_a: OK,
    pygame.K_ESCAPE: BACK,
}


def parse_players(text: str) -> list[tuple[str, str]]:
    """"green:TL,blue:BR" -> [("green", "TL"), ("blue", "BR")]"""
    return [tuple(part.split(":", 1)) for part in text.split(",") if part]


def main() -> None:
    pygame.init()
    window = os.environ.get("SPINAZOO_WINDOW")
    if window:
        w, h = (int(v) for v in window.lower().split("x"))
        screen = pygame.display.set_mode((w, h))
    else:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("Spin-a-Zoo")
    pygame.mouse.set_visible(bool(window))
    setup = parse_players(os.environ.get("SPINAZOO_PLAYERS", "green:TL,blue:TR,yellow:BR,red:BL"))
    game = GameScreen(screen, setup)
    clock = pygame.time.Clock()
    while True:
        now = pygame.time.get_ticks() / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F4 and event.mod & pygame.KMOD_ALT:
                    return
                action = KEYS.get(event.key)
                if action == BACK:
                    return  # pause menu comes in step 3
                if action:
                    game.handle(action, now)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.click(event.pos, now)
        game.update(now)
        game.draw(now)
        pygame.display.flip()
        clock.tick(60)
