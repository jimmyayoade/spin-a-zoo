"""Spin-A-Zoo! rules engine.

Pure Python with no pygame, so the rules can be tested anywhere. Batocera v42
ships Python 3.12, so nothing here needs anything newer.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

SIZE = 5
MAX_STACK = 4
TILES_PER_PLAYER = 16
LINE_LENGTH = 4

# Features and their values, in spinner order. The ids are internal; the game
# shows LABELS.
FEATURES = ("color", "shape", "pattern", "animal")
VALUES = {
    "color": ("green", "blue", "purple", "red", "yellow"),
    "shape": ("square", "star", "circle", "triangle", "hexagon"),
    "pattern": ("notes", "stripes", "dots", "zigzag", "leaves"),
    "animal": ("elephant", "cat", "eagle", "lion", "bear"),
}
LABELS = {
    "color": "Color", "shape": "Shape", "pattern": "Pattern", "animal": "Animal",
    "green": "Green", "blue": "Blue", "purple": "Purple", "red": "Red",
    "yellow": "Yellow",
    "square": "Square", "star": "Star", "circle": "Circle",
    "triangle": "Triangle", "hexagon": "Hexagon",
    "notes": "Musical notes", "stripes": "Stripes", "dots": "Polka dots",
    "zigzag": "Zigzag", "leaves": "Leaves",
    "elephant": "Elephant", "cat": "Tuxedo cat", "eagle": "Eagle",
    "lion": "Lion", "bear": "Bear",
}

PLAYER_COLORS = ("green", "blue", "yellow", "red")

# Seats in clockwise order: two spinners on each side of the board.
SEATS = ("TL", "TR", "BR", "BL")
SEAT_LABELS = {"TL": "Top left", "TR": "Top right", "BR": "Bottom right", "BL": "Bottom left"}
# Spinner each seat starts with.
START_SPINNERS = {"TL": "color", "TR": "shape", "BR": "pattern", "BL": "animal"}

WILD = "wild"
ZOO = "zoo"  # the "Spin-A-Zoo!" section

# Phases of a turn.
SPIN = "spin"      # current player must spin
PLACE = "place"    # current player must place a tile
WON = "won"
DRAW = "draw"      # board full or nobody has tiles: play again


def spinner_sections(feature: str) -> tuple[str, ...]:
    """The 8 sections of a spinner, in order around the dial.

    5 values, 2 Wild and 1 Spin-A-Zoo!, spaced out so the specials don't sit
    next to each other.
    """
    v = VALUES[feature]
    return (v[0], WILD, v[1], v[2], ZOO, v[3], WILD, v[4])


@dataclass(frozen=True)
class Square:
    color: str
    shape: str
    pattern: str
    animal: str

    def get(self, feature: str) -> str:
        return getattr(self, feature)


def make_board(rng: random.Random) -> list[list[Square]]:
    """A shuffled 5x5 board.

    Built from the four mutually orthogonal Latin squares of order 5,
    L_k(r, c) = (k*r + c) mod 5 for k = 1..4: each value of each feature is in
    every row and column once, and no two squares share a pair of values.
    Shuffling rows, columns, which k each feature uses, and each feature's
    values keeps all of that and gives a different board every game.
    """
    rows = list(range(SIZE))
    cols = list(range(SIZE))
    ks = [1, 2, 3, 4]
    rng.shuffle(rows)
    rng.shuffle(cols)
    rng.shuffle(ks)
    values = {}
    for feature in FEATURES:
        vals = list(VALUES[feature])
        rng.shuffle(vals)
        values[feature] = vals
    board = []
    for r in rows:
        line = []
        for c in cols:
            picks = {
                feature: values[feature][(k * r + c) % SIZE]
                for feature, k in zip(FEATURES, ks)
            }
            line.append(Square(**picks))
        board.append(line)
    return board


def winning_lines() -> list[tuple[tuple[int, int], ...]]:
    """Every run of 4 cells in a row: across, down and both diagonals."""
    lines = []
    steps = ((0, 1), (1, 0), (1, 1), (1, -1))
    for r in range(SIZE):
        for c in range(SIZE):
            for dr, dc in steps:
                cells = tuple((r + i * dr, c + i * dc) for i in range(LINE_LENGTH))
                if all(0 <= rr < SIZE and 0 <= cc < SIZE for rr, cc in cells):
                    lines.append(cells)
    return lines


LINES = winning_lines()


@dataclass
class Player:
    color: str
    seat: str
    tiles: int = TILES_PER_PLAYER


@dataclass
class Game:
    """One round of Spin-A-Zoo!

    players: (tile color, seat) pairs, 2 to 4 of them. Play goes clockwise by
    seat, starting from the first player given.
    """

    players: list[Player]
    rng: random.Random = field(default_factory=random.Random)
    board: list[list[Square]] = field(init=False)
    stacks: list[list[list[int]]] = field(init=False)
    spinners: dict[str, str] = field(init=False)
    turn: int = field(init=False)
    phase: str = field(init=False, default=SPIN)
    last_spin: str | None = field(init=False, default=None)
    winner: int | None = field(init=False, default=None)
    win_line: tuple[tuple[int, int], ...] | None = field(init=False, default=None)

    @classmethod
    def new(cls, setup: list[tuple[str, str]], rng: random.Random | None = None) -> Game:
        if not 2 <= len(setup) <= 4:
            raise ValueError("Spin-A-Zoo! needs 2 to 4 players")
        colors = [c for c, _ in setup]
        seats = [s for _, s in setup]
        if len(set(colors)) != len(colors) or not set(colors) <= set(PLAYER_COLORS):
            raise ValueError(f"each player needs a different color from {PLAYER_COLORS}")
        if len(set(seats)) != len(seats) or not set(seats) <= set(SEATS):
            raise ValueError(f"each player needs a different seat from {SEATS}")
        # Order players clockwise, starting with the first one given.
        first = SEATS.index(seats[0])
        order = sorted(setup, key=lambda p: (SEATS.index(p[1]) - first) % len(SEATS))
        return cls([Player(c, s) for c, s in order], rng or random.Random())

    def __post_init__(self) -> None:
        self.board = make_board(self.rng)
        self.stacks = [[[] for _ in range(SIZE)] for _ in range(SIZE)]
        self.spinners = dict(START_SPINNERS)
        self.turn = 0

    # --- state -----------------------------------------------------------

    @property
    def player(self) -> Player:
        return self.players[self.turn]

    @property
    def spinner(self) -> str:
        """The feature on the current player's spinner."""
        return self.spinners[self.player.seat]

    def top(self, r: int, c: int) -> int | None:
        stack = self.stacks[r][c]
        return stack[-1] if stack else None

    def empty_cells(self) -> list[tuple[int, int]]:
        return [(r, c) for r in range(SIZE) for c in range(SIZE) if not self.stacks[r][c]]

    # --- turn ------------------------------------------------------------

    def spin(self) -> str:
        """Spin the current player's spinner and apply the result."""
        section = self.rng.choice(spinner_sections(self.spinner))
        self.resolve(section)
        return section

    def resolve(self, section: str) -> None:
        """Apply a spinner result (split from spin() so tests can choose it)."""
        if self.phase != SPIN:
            raise RuntimeError(f"can't spin during {self.phase}")
        if section != ZOO and section != WILD and section not in VALUES[self.spinner]:
            raise ValueError(f"{section!r} is not on the {self.spinner} spinner")
        self.last_spin = section
        if section == ZOO:
            self.pass_spinners()
            return  # same player spins again
        self.phase = PLACE

    def pass_spinners(self) -> None:
        """Every spinner, empty seats included, moves one seat clockwise."""
        n = len(SEATS)
        self.spinners = {SEATS[(i + 1) % n]: self.spinners[SEATS[i]] for i in range(n)}

    def legal_moves(self) -> list[tuple[int, int]]:
        if self.phase != PLACE:
            return []
        if self.last_spin == WILD:
            return [(r, c) for r in range(SIZE) for c in range(SIZE)
                    if len(self.stacks[r][c]) < MAX_STACK]
        empty = self.empty_cells()
        feature = self.spinner
        matching = [(r, c) for r, c in empty if self.board[r][c].get(feature) == self.last_spin]
        return matching or empty

    def place(self, r: int, c: int) -> None:
        if (r, c) not in self.legal_moves():
            raise ValueError(f"can't place on {(r, c)} after spinning {self.last_spin!r}")
        self.stacks[r][c].append(self.turn)
        self.player.tiles -= 1
        line = self._win_line(self.turn)
        if line:
            self.phase = WON
            self.winner = self.turn
            self.win_line = line
            return
        if not self.empty_cells() or not any(p.tiles for p in self.players):
            self.phase = DRAW
            return
        self._next_player()
        self.phase = SPIN
        self.last_spin = None

    def _next_player(self) -> None:
        """Next player clockwise who still has tiles (one always does here)."""
        for _ in range(len(self.players)):
            self.turn = (self.turn + 1) % len(self.players)
            if self.player.tiles:
                return

    def _win_line(self, who: int) -> tuple[tuple[int, int], ...] | None:
        for line in LINES:
            if all(self.top(r, c) == who for r, c in line):
                return line
        return None
