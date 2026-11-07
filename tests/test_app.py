"""Drive the whole app with key presses, the way pads do through Batocera.

Needs pygame (run with the project's .venv); skipped without it.
"""

import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SPINAZOO_SILENT"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "spinazoo"))

try:
    import pygame
except ImportError:  # plain python3 without the venv
    pygame = None


@unittest.skipIf(pygame is None, "pygame not installed")
class AppFlowTest(unittest.TestCase):
    def setUp(self):
        import app
        import rules
        self.app_mod, self.rules = app, rules
        self.tmp = tempfile.TemporaryDirectory()
        app.SETTINGS = Path(self.tmp.name) / "settings.json"
        pygame.init()
        self.screen = pygame.display.set_mode((1280, 720))
        self.a = app.App(self.screen)
        self.a.push(app.Title(self.a))
        self.now = 0.0
        self.played = []
        self.a.sfx = lambda name: self.played.append(name)

    def tearDown(self):
        self.tmp.cleanup()

    def press(self, *keys, wait=0.05):
        for k in keys:
            self.a.frame([pygame.event.Event(pygame.KEYDOWN, key=k, mod=0)], self.now)
            self.now += wait

    def scene(self):
        return type(self.a.scene).__name__

    def test_full_flow(self):
        K = pygame
        rules = self.rules
        self.press(K.K_DOWN, K.K_a)
        self.assertEqual(self.scene(), "HowToPlay")
        self.press(K.K_b)
        self.assertEqual(self.scene(), "Title")
        self.press(K.K_UP, K.K_a)
        self.assertEqual(self.scene(), "Setup")

        s = self.a.scene
        s.players = []
        self.press(K.K_LEFT, K.K_a)                        # top left: green
        self.press(K.K_a)                                  # top left: blue
        self.press(K.K_RIGHT, K.K_RIGHT, K.K_DOWN, K.K_a)  # bottom right: green
        self.assertEqual(s.players, [("blue", "TL"), ("green", "BR")])
        self.press(K.K_UP, K.K_a, K.K_b)                   # top right: sit, then leave
        self.assertEqual(s.players, [("blue", "TL"), ("green", "BR")])
        self.press(K.K_LEFT, K.K_a)
        self.assertEqual(self.scene(), "Play")

        g = self.a.scene.screen
        rng = random.Random(2)
        rounds = 0
        while rounds < 2:
            if g.game.phase in (rules.WON, rules.DRAW) and not g.busy():
                rounds += 1
            if g.game.phase == rules.PLACE:
                key = rng.choice([K.K_a, K.K_LEFT, K.K_UP, K.K_RIGHT, K.K_DOWN])
            else:
                key = K.K_a
            self.press(key, wait=1 / 30)
            for _ in range(3):
                self.a.frame([], self.now)
                self.now += 1 / 30
        for name in ("spin", "tick", "stop", "place", "turn", "blip"):
            self.assertIn(name, self.played)
        self.assertTrue({"win", "draw"} & set(self.played))

        self.press(K.K_ESCAPE)
        self.assertEqual(self.scene(), "Pause")
        self.press(K.K_b)
        self.assertEqual(self.scene(), "Play")
        self.press(K.K_ESCAPE, K.K_DOWN, K.K_a)            # New board
        self.assertEqual(self.scene(), "Play")
        self.assertEqual(self.a.scene.screen.game.phase, rules.SPIN)
        self.press(K.K_ESCAPE, K.K_DOWN, K.K_DOWN, K.K_a)  # Change players
        self.assertEqual(self.scene(), "Setup")
        self.assertEqual(self.a.scene.players, [("blue", "TL"), ("green", "BR")])

        self.press(K.K_ESCAPE)
        self.assertEqual(self.scene(), "Title")
        self.press(K.K_DOWN, K.K_DOWN, K.K_a)              # Options
        self.assertEqual(self.scene(), "Options")
        self.assertTrue(self.a.settings["calm"])           # calm by default
        self.press(K.K_a)                                  # Calm: off
        self.assertFalse(self.a.settings["calm"])
        self.press(K.K_DOWN, K.K_RIGHT)                    # Theme: next
        self.assertEqual(self.a.settings["theme"], "Jungle")
        self.press(K.K_DOWN, K.K_a)                        # Sound effects: off
        self.assertFalse(self.a.sounds.enabled)
        self.press(K.K_DOWN, K.K_DOWN, K.K_a)              # A button: east
        self.assertEqual(self.a.settings["confirm"], "east")
        saved = self.app_mod.load_settings()
        self.assertEqual(saved["sound"], False)
        self.assertEqual(saved["theme"], "Jungle")
        self.assertFalse(saved["calm"])
        self.assertEqual(saved["players"], [("blue", "TL"), ("green", "BR")])
        self.press(K.K_b)
        self.assertEqual(self.scene(), "Title")
        self.press(K.K_DOWN, K.K_a)                        # Exit
        self.assertFalse(self.a.running)

    def test_pad_buttons_follow_the_option(self):
        from game import BACK, OK
        a = self.a
        self.assertEqual(a.settings["confirm"], "south")
        self.assertEqual((a.action(pygame.K_j), a.action(pygame.K_k)), (OK, BACK))
        a.settings["confirm"] = "east"
        self.assertEqual((a.action(pygame.K_j), a.action(pygame.K_k)), (BACK, OK))
        self.assertEqual(a.action(pygame.K_a), OK)          # keyboard keeps A = OK
        self.assertIsNone(a.action(pygame.K_SPACE))         # select does nothing

    def scan(self, *names, wait=0.05):
        """Presses as Batocera sends them: real scancodes, and the key the
        US layout gives (other layouts give other keys; scancodes win)."""
        for name in names:
            ev = pygame.event.Event(pygame.KEYDOWN, key=0, mod=0,
                                    scancode=getattr(pygame, "KSCAN_" + name))
            self.a.frame([ev], self.now)
            self.now += wait

    def test_keys_file_matches_the_table(self):
        import json
        import pads
        path = Path(__file__).resolve().parent.parent / "spinazoo" / "spinazoo.pygame.keys"
        self.assertEqual(json.loads(path.read_text()), pads.keys_file(),
                         "run tools/make_keys.py after changing pads.py")
        sent = [k for keys in pads.PADS for k in keys]
        self.assertEqual(len(sent), len(set(sent)), "two controllers share a key")
        # nothing Batocera's default pygame mapping sends for player 1's other buttons
        self.assertFalse(set(sent) & (set("ABHLMNRSTXY") | {"SPACE", "RETURN", "KP2", "KP4", "KP6", "KP8"}))

    def test_each_controller_is_told_apart(self):
        from game import BACK, MENU, OK, UP
        a = self.a
        self.assertEqual(a.read(0, pygame.KSCAN_J), (OK, 0))
        self.assertEqual(a.read(0, pygame.KSCAN_5), (OK, 1))
        self.assertEqual(a.read(0, pygame.KSCAN_O), (BACK, 2))
        self.assertEqual(a.read(0, pygame.KSCAN_C), (UP, 3))
        self.assertEqual(a.read(0, pygame.KSCAN_8), (MENU, 3))
        # a French keyboard turns the Q key into 'a': still player 3's left, not OK
        self.assertEqual(a.read(pygame.K_a, pygame.KSCAN_Q)[1], 2)
        self.assertEqual(a.read(pygame.K_a, pygame.KSCAN_A), (OK, None))  # keyboard A
        a.settings["confirm"] = "east"
        self.assertEqual(a.read(0, pygame.KSCAN_6), (OK, 1))

    def test_one_controller_each(self):
        rules = self.rules
        self.a.settings["controllers"] = "each"
        self.press(pygame.K_a)               # Title: Play
        self.assertEqual(self.scene(), "Setup")
        s = self.a.scene
        s.players, s.pads = [], {}
        self.scan("LEFT", "J")              # controller 1 sits top left
        self.scan("2", "5")                 # controller 2 moves down, sits bottom left
        self.assertEqual(s.pads, {"TL": 0, "BL": 1})
        self.scan("1", "5")                 # controller 2 takes over top left: no color change
        self.assertEqual(s.pads, {"TL": 1, "BL": 1})
        self.assertEqual(s.seat_color("TL"), "green")
        self.scan("J")                      # controller 1 takes it back
        self.scan("RIGHT", "J")             # start
        self.assertEqual(self.scene(), "Play")
        self.assertEqual(self.a.settings["pads"], {"TL": 0, "BL": 1})

        g = self.a.scene.screen
        # whoever goes first: the other player's controller is turned away
        mine, theirs = ("J", "5") if g.game.player.seat == "TL" else ("5", "J")
        self.played.clear()
        self.scan(theirs)                   # the wrong controller
        self.assertEqual(g.game.phase, rules.SPIN)
        self.assertIsNone(g.spin_anim)
        self.assertIn("bonk", self.played)
        self.scan("8")                      # but anyone can pause
        self.assertEqual(self.scene(), "Pause")
        self.press(pygame.K_b)
        self.scan(mine)                     # the right one spins
        self.assertIsNotNone(g.spin_anim)

    def test_first_player_changes_each_round(self):
        from game import GameScreen
        setup = [("green", "TL"), ("blue", "TR"), ("red", "BR")]
        starters = []
        for seed in range(6):
            g = GameScreen(self.screen, setup, seed=seed)
            seats = [g.game.player.seat]
            for _ in range(3):
                g.new_round()
                seats.append(g.game.player.seat)
            # the next player clockwise starts each new round
            order = [p.seat for p in g.game.players]
            i = order.index(seats[0])
            self.assertEqual(seats, [order[(i + k) % 3] for k in range(4)])
            starters.append(seats[0])
        self.assertGreater(len(set(starters)), 1)  # and the first round is random

    def test_music_option_picks_a_tune(self):
        a = self.a
        a.push(self.app_mod.Options(a))
        opts = a.scene
        seen = []
        for _ in range(4):
            opts.change("Music")
            seen.append((a.settings["music"], a.settings["tune"]))
        self.assertEqual(seen, [(True, "jazz"), (True, "classical"), (False, "classical"), (True, "playful")])
        opts.change("Music", -1)
        self.assertFalse(a.settings["music"])
        self.assertEqual(self.app_mod.load_settings()["tune"], "playful")

    def test_every_tune_makes_a_loop(self):
        import sound
        for tune in sound.TUNES:
            s = sound.music(True, tune)
            self.assertGreater(len(s), sound.RATE * 10, tune)
            self.assertLess(max(abs(v) for v in s), 1.0, tune)   # no clipping
            self.assertGreater(max(abs(v) for v in s), 0.1, tune)

    def test_calm_is_the_default(self):
        self.assertTrue(self.app_mod.load_settings()["calm"])
        self.app_mod.SETTINGS.write_text('{"calm": false}')
        self.assertFalse(self.app_mod.load_settings()["calm"])

    def test_bad_settings_file_is_ignored(self):
        self.app_mod.SETTINGS.write_text('{"players": [["purple", "XX"]], "sound": "loud"}')
        s = self.app_mod.load_settings()
        self.assertEqual(s["players"], self.app_mod.DEFAULT_SETUP)
        self.assertTrue(s["sound"])
        self.assertEqual(s["theme"], "Night")


if __name__ == "__main__":
    unittest.main()
