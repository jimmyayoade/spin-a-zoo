import itertools
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "spinazoo"))

import rules  # noqa: E402
from rules import DRAW, PLACE, SIZE, SPIN, WILD, WON, ZOO, Game  # noqa: E402


def game(setup=(("green", "TL"), ("blue", "BR")), seed=1):
    return Game.new(list(setup), random.Random(seed))


def cells():
    return [(r, c) for r in range(SIZE) for c in range(SIZE)]


def put(g, r, c, who):
    """Put a tile straight onto the board, bypassing the turn rules."""
    g.stacks[r][c].append(who)
    g.players[who].tiles -= 1


class BoardTest(unittest.TestCase):
    def test_each_value_once_per_row_and_column(self):
        for seed in range(50):
            board = rules.make_board(random.Random(seed))
            for feature in rules.FEATURES:
                want = set(rules.VALUES[feature])
                for i in range(SIZE):
                    self.assertEqual({board[i][c].get(feature) for c in range(SIZE)}, want)
                    self.assertEqual({board[r][i].get(feature) for r in range(SIZE)}, want)

    def test_no_two_squares_share_a_pair_of_features(self):
        for seed in range(50):
            board = rules.make_board(random.Random(seed))
            squares = [board[r][c] for r, c in cells()]
            for f1, f2 in itertools.combinations(rules.FEATURES, 2):
                pairs = {(s.get(f1), s.get(f2)) for s in squares}
                self.assertEqual(len(pairs), 25, (seed, f1, f2))

    def test_board_changes_between_games(self):
        boards = {tuple(map(tuple, rules.make_board(random.Random(s)))) for s in range(20)}
        self.assertEqual(len(boards), 20)


class SpinnerTest(unittest.TestCase):
    def test_eight_sections(self):
        for feature in rules.FEATURES:
            sections = rules.spinner_sections(feature)
            self.assertEqual(len(sections), 8)
            self.assertEqual(sections.count(WILD), 2)
            self.assertEqual(sections.count(ZOO), 1)
            self.assertEqual(set(sections) - {WILD, ZOO}, set(rules.VALUES[feature]))

    def test_spin_lands_on_own_spinner(self):
        g = game()
        for _ in range(200):
            result = g.spin()
            self.assertIn(result, rules.spinner_sections(g.spinner))
            g.phase = SPIN

    def test_value_on_wrong_spinner_is_rejected(self):
        g = game()  # TL has the color spinner
        with self.assertRaises(ValueError):
            g.resolve("star")


class SetupTest(unittest.TestCase):
    def test_player_count(self):
        with self.assertRaises(ValueError):
            game([("green", "TL")])
        with self.assertRaises(ValueError):
            game([("green", "TL"), ("blue", "TR"), ("red", "BR"), ("yellow", "BL"), ("green", "TL")])

    def test_colors_and_seats_must_differ(self):
        with self.assertRaises(ValueError):
            game([("green", "TL"), ("green", "BR")])
        with self.assertRaises(ValueError):
            game([("green", "TL"), ("blue", "TL")])
        with self.assertRaises(ValueError):
            game([("purple", "TL"), ("blue", "BR")])

    def test_turns_go_clockwise_from_first_player(self):
        g = game([("red", "BR"), ("green", "TL"), ("blue", "BL")])
        self.assertEqual([p.seat for p in g.players], ["BR", "BL", "TL"])

    def test_everyone_starts_with_16_tiles(self):
        g = game([("red", "BR"), ("green", "TL"), ("blue", "BL"), ("yellow", "TR")])
        self.assertTrue(all(p.tiles == 16 for p in g.players))


class ValueSpinTest(unittest.TestCase):
    def test_only_empty_matching_squares(self):
        g = game()
        value = "red"
        matching = [(r, c) for r, c in cells() if g.board[r][c].color == value]
        put(g, *matching[0], 1)
        g.resolve(value)
        self.assertEqual(sorted(g.legal_moves()), sorted(matching[1:]))

    def test_no_empty_match_means_any_empty_square(self):
        g = game()
        value = "red"
        matching = [(r, c) for r, c in cells() if g.board[r][c].color == value]
        for i, cell in enumerate(matching):
            put(g, *cell, i % 2)
        g.resolve(value)
        self.assertEqual(sorted(g.legal_moves()), sorted(g.empty_cells()))
        self.assertTrue(all(not g.stacks[r][c] for r, c in g.legal_moves()))

    def test_cannot_place_on_a_tile(self):
        g = game()
        r, c = next((r, c) for r, c in cells() if g.board[r][c].color == "red")
        put(g, r, c, 1)
        g.resolve("red")
        with self.assertRaises(ValueError):
            g.place(r, c)

    def test_cannot_place_on_non_matching_empty_square(self):
        g = game()
        g.resolve("red")
        r, c = next((r, c) for r, c in cells() if g.board[r][c].color != "red")
        with self.assertRaises(ValueError):
            g.place(r, c)

    def test_matching_uses_the_current_spinner(self):
        g = game()
        g.pass_spinners()  # TL now has the animal spinner
        self.assertEqual(g.spinner, "animal")
        g.resolve("lion")
        self.assertTrue(all(g.board[r][c].animal == "lion" for r, c in g.legal_moves()))


class WildTest(unittest.TestCase):
    def test_any_square_including_covered(self):
        g = game()
        put(g, 0, 0, 1)
        g.resolve(WILD)
        self.assertEqual(sorted(g.legal_moves()), sorted(cells()))
        g.place(0, 0)
        self.assertEqual(g.stacks[0][0], [1, 0])

    def test_full_stack_is_not_allowed(self):
        g = game()
        for i in range(4):
            put(g, 2, 2, i % 2)
        g.resolve(WILD)
        self.assertNotIn((2, 2), g.legal_moves())
        with self.assertRaises(ValueError):
            g.place(2, 2)


class SpinAZooTest(unittest.TestCase):
    def test_spinners_pass_clockwise_including_empty_seats(self):
        g = game()  # players at TL and BR; TR and BL are empty
        g.resolve(ZOO)
        self.assertEqual(g.spinners, {"TR": "color", "BR": "shape", "BL": "pattern", "TL": "animal"})

    def test_same_player_spins_again_without_placing(self):
        g = game()
        g.resolve(ZOO)
        self.assertEqual(g.phase, SPIN)
        self.assertEqual(g.turn, 0)
        self.assertEqual(g.legal_moves(), [])
        self.assertTrue(all(not g.stacks[r][c] for r, c in cells()))

    def test_landing_on_it_again_passes_again(self):
        g = game()
        for _ in range(4):
            g.resolve(ZOO)
        self.assertEqual(g.spinners, rules.START_SPINNERS)
        self.assertEqual(g.phase, SPIN)

    def test_spin_after_zoo_uses_new_spinner(self):
        g = game()
        g.resolve(ZOO)
        g.resolve("bear")  # TL got the animal spinner from BL
        self.assertEqual(g.phase, PLACE)


class TurnTest(unittest.TestCase):
    def test_turn_passes_after_placing(self):
        g = game([("green", "TL"), ("blue", "TR"), ("red", "BR")])
        g.resolve(WILD)
        g.place(0, 0)
        self.assertEqual(g.turn, 1)
        self.assertEqual(g.phase, SPIN)
        self.assertEqual(g.players[0].tiles, 15)

    def test_cannot_spin_while_placing(self):
        g = game()
        g.resolve(WILD)
        with self.assertRaises(RuntimeError):
            g.resolve(WILD)

    def test_player_without_tiles_is_skipped(self):
        g = game([("green", "TL"), ("blue", "TR"), ("red", "BR")])
        g.players[1].tiles = 0
        g.resolve(WILD)
        g.place(0, 0)
        self.assertEqual(g.turn, 2)


class WinTest(unittest.TestCase):
    def assert_wins_on(self, line):
        g = game()
        for r, c in line[:-1]:
            put(g, r, c, 0)
        g.resolve(WILD)
        g.place(*line[-1])
        self.assertEqual(g.phase, WON)
        self.assertEqual(g.winner, 0)
        self.assertEqual(sorted(g.win_line), sorted(line))

    def test_across(self):
        self.assert_wins_on([(1, 1), (1, 2), (1, 3), (1, 4)])

    def test_down(self):
        self.assert_wins_on([(0, 0), (1, 0), (2, 0), (3, 0)])

    def test_diagonal(self):
        self.assert_wins_on([(1, 1), (2, 2), (3, 3), (4, 4)])

    def test_other_diagonal(self):
        self.assert_wins_on([(0, 3), (1, 2), (2, 1), (3, 0)])

    def test_three_is_not_a_win(self):
        g = game()
        put(g, 0, 0, 0)
        put(g, 0, 1, 0)
        g.resolve(WILD)
        g.place(0, 2)
        self.assertEqual(g.phase, SPIN)

    def test_line_count(self):
        # 10 across, 10 down, 4 + 4 diagonal
        self.assertEqual(len(rules.LINES), 28)

    def test_covered_tile_does_not_count(self):
        g = game()
        for c in range(3):
            put(g, 0, c, 0)
        put(g, 0, 1, 1)  # blue covers one of green's tiles
        g.resolve(WILD)
        g.place(0, 3)
        self.assertEqual(g.phase, SPIN)

    def test_covering_can_win(self):
        g = game()
        for c in range(3):
            put(g, 0, c, 0)
        put(g, 0, 3, 1)
        g.resolve(WILD)
        g.place(0, 3)
        self.assertEqual(g.phase, WON)


class DrawTest(unittest.TestCase):
    def fill_without_line(self, g, leave):
        """Fill every cell but `leave` with players 1-3, with no 4 in a row."""
        rng = random.Random(0)
        while True:
            for r, c in cells():
                g.stacks[r][c] = [] if (r, c) == leave else [rng.choice((1, 2, 3))]
            if not any(g._win_line(who) for who in (1, 2, 3)):
                return

    def test_full_board_is_a_draw(self):
        g = game([("green", "TL"), ("blue", "TR"), ("red", "BR"), ("yellow", "BL")])
        self.fill_without_line(g, (4, 4))
        g.resolve(WILD)
        g.place(4, 4)
        self.assertEqual(g.phase, DRAW)
        self.assertIsNone(g.winner)

    def test_win_on_last_square_beats_draw(self):
        g = game([("green", "TL"), ("blue", "TR"), ("red", "BR"), ("yellow", "BL")])
        self.fill_without_line(g, (0, 3))
        for c in range(3):
            g.stacks[0][c].append(0)
        g.resolve(WILD)
        g.place(0, 3)
        self.assertEqual(g.phase, WON)

    def test_nobody_has_tiles_is_a_draw(self):
        g = game()
        g.players[0].tiles = 1
        g.players[1].tiles = 0
        g.resolve(WILD)
        g.place(0, 0)
        self.assertEqual(g.phase, DRAW)


class RandomPlayTest(unittest.TestCase):
    def test_many_random_games_end_properly(self):
        for seed in range(300):
            rng = random.Random(seed)
            n = 2 + seed % 3
            seats = rng.sample(rules.SEATS, n)
            g = Game.new(list(zip(rules.PLAYER_COLORS, seats)), rng)
            for _ in range(2000):
                if g.phase in (WON, DRAW):
                    break
                if g.phase == SPIN:
                    g.spin()
                else:
                    moves = g.legal_moves()
                    self.assertTrue(moves, seed)
                    g.place(*rng.choice(moves))
                self.assertTrue(all(len(s) <= 4 for row in g.stacks for s in row))
                self.assertTrue(all(p.tiles >= 0 for p in g.players))
            self.assertIn(g.phase, (WON, DRAW), seed)


if __name__ == "__main__":
    unittest.main()
