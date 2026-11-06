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
        self.press(K.K_RIGHT)                              # Theme: next
        self.assertEqual(self.a.settings["theme"], "Jungle")
        self.press(K.K_DOWN, K.K_a)                        # Sound effects: off
        self.assertFalse(self.a.sounds.enabled)
        self.press(K.K_DOWN, K.K_DOWN, K.K_a)              # A button: east
        self.assertEqual(self.a.settings["confirm"], "east")
        saved = self.app_mod.load_settings()
        self.assertEqual(saved["sound"], False)
        self.assertEqual(saved["theme"], "Jungle")
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

    def test_bad_settings_file_is_ignored(self):
        self.app_mod.SETTINGS.write_text('{"players": [["purple", "XX"]], "sound": "loud"}')
        s = self.app_mod.load_settings()
        self.assertEqual(s["players"], self.app_mod.DEFAULT_SETUP)
        self.assertTrue(s["sound"])
        self.assertEqual(s["theme"], "Night")


if __name__ == "__main__":
    unittest.main()
