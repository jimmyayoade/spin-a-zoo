# Spin-A-Zoo!

A spin-and-match board game for 2–4 players, made for [Batocera](https://batocera.org)'s Pygame system.

Spin your spinner, cover a matching square on the zoo board, and be the first to get **4 in a row**.

## Rules

**Setup:** each player picks a tile color (green, blue, yellow or red, 16 tiles each) and one of the four spinner seats, two on each side of the board. Empty seats keep their spinners: they still get passed around. The board is shuffled for every game.

The board is a 5×5 grid. Every square has a color, a pattern, a shape and an animal:

| Spinner | Values |
|---|---|
| Color | green, blue, purple, red, yellow |
| Shape | square, star, circle, triangle, hexagon |
| Pattern | musical notes, stripes, polka dots, zigzag, leaves |
| Animal | elephant, tuxedo cat, eagle, lion, bear |

Each value appears once in every row and every column, and no two squares share the same pair of features.

Each spinner has 8 sections: its 5 values, 2 **Wild** and 1 **Spin-A-Zoo!**

**On your turn, spin:**

| Result | What you do |
|---|---|
| A value | Play a tile on an **empty** square that matches. If no empty square matches, play on any empty square. You can't play on a square that already has a tile. |
| **Wild** | Play on any square, even on top of another tile, as long as the stack has fewer than 4. |
| **Spin-A-Zoo!** | Everyone passes their spinner clockwise: top left → top right → bottom right → bottom left (including the empty seats' spinners), then you spin again. |

Then it's the next player's turn, clockwise. A random player goes first in the first game; after that, the next player clockwise starts each new game.

**Win:** be the first to get 4 of your tiles in a row: across, down or diagonally. Only the top tile of a stack counts.

**No winner:** if every square has a tile and nobody has won, PLAY AGAIN! A player with no tiles left skips their turns; if nobody has tiles left, play again.

## Controls

| Pad | Keyboard | What it does |
|---|---|---|
| A (south button) | A or Enter | Spin, place a tile, choose |
| B (east button) | B or Backspace | Back; on the setup screen, leave a seat |
| D-pad / left stick | Arrow keys | Move |
| Start | Esc | Pause menu |
| Hotkey + Start | Alt+F4 | Exit to EmulationStation |

**Options > A button** swaps the pad buttons, so the east (right-hand) button confirms instead. A mouse or touch screen works too: tap your spinner to spin, then tap a square.

### More than one controller

On Batocera, `spinazoo.pygame.keys` turns every pad (players 1–4, in EmulationStation's controller order) into keys, using the button mapping set up in EmulationStation. Each controller sends its own keys, so the game knows which one was pressed. **Options > Controllers** decides what that means:

- **Shared** (default): any controller plays any turn. Handy when a grown-up helps, or when there's only one controller.
- **One each**: on the setup screen, each player presses A on their own controller to sit down, and that controller is linked to the seat (its number shows in the corner of the panel). In the game, only your own controller can spin and place on your turn; anyone else's gets a bonk, and the panel of the player whose turn it is flashes. Start pauses from any controller. A seat with no controller linked (say, from last time) can be played from any controller until someone presses A on it.

The keys are listed in `spinazoo/pads.py`; after changing them, run `python tools/make_keys.py` to rewrite `spinazoo.pygame.keys`.

## Options

**Calm** (on by default) keeps the game gentle for young players: outlines stay steady instead of pulsing, there are no flashes or bursts, a little confetti falls over the winner's panel only, and the music is slower and softer, with no drums. Turn it off for the full party.

Also: theme (Night, Jungle, Ocean, Daylight), sound effects, music (off, playful, jazz or classical: all made up for the game and played by the code), which pad button confirms, and controllers (shared or one each). They're saved in `settings.json` next to the game, with the last players and their controllers.

## Playing it on Batocera

Copy the `spinazoo` folder to `/userdata/roms/pygame/spinazoo/` and update the game list. It shows up under **Pygame**.

## Running it on a computer

Needs Python 3.12 and pygame 2.5 or newer (Batocera 42 ships 2.5.2, newer builds 2.6.1):

```
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python pygame==2.6.1
tools/run-local.sh            # 1280x720 window; SPINAZOO_WINDOW=1920x1080 for another size
python3 -m unittest discover -s tests
```

## Your own pictures and sounds

Everything is drawn and synthesised in code, so the game needs no image or sound files. You can still swap in your own:

- **Pictures:** a PNG named `elephant.png`, `cat.png`, `eagle.png`, `lion.png` or `bear.png` in `spinazoo/art/` replaces that animal's drawing everywhere.
- **Sounds:** an `.ogg` or `.wav` in `spinazoo/sounds/` named after an effect replaces it: `lion`, `cat`, `eagle`, `bear`, `elephant` (animal results), `color`, `shape`, `pattern`, `wild`, `zoo`, `any`, `spin`, `tick`, `stop`, `place`, `bonk`, `turn`, `win`, `draw`, `blip`, `select`, `back`. `music-playful.ogg`, `music-jazz.ogg` or `music-classical.ogg` replaces that tune, and `music.ogg` replaces all three.

## Credits

- Font: [Fredoka](https://github.com/hafontia/Fredoka-One) by The Fredoka Project Authors, under the SIL Open Font License 1.1 (`spinazoo/fonts/OFL.txt`). `Fredoka-SemiBold.ttf` is the SemiBold weight cut from the variable font in [google/fonts](https://github.com/google/fonts/tree/main/ofl/fredoka) with `fonttools varLib.instancer Fredoka[wdth,wght].ttf wght=600 wdth=100 --update-name-table`.
- Spinner words font: [M PLUS Rounded 1c](https://github.com/coz-m/MPLUS_FONTS) by The Rounded M+ Project Authors, under the SIL Open Font License 1.1 (`spinazoo/fonts/OFL-MPLUSRounded1c.txt`). `MPLUSRounded1c-Black.ttf` is the Black weight from [google/fonts](https://github.com/google/fonts/tree/main/ofl/mplusrounded1c), cut down to basic Latin letters with `pyftsubset MPLUSRounded1c-Black.ttf --unicodes=U+0020-007E --layout-features='*'`.

## License

The game's code is MIT. The fonts keep their own license (SIL OFL 1.1).
