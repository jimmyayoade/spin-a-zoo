"""Which key each controller's buttons send.

On Batocera, evmapy turns pad buttons into key presses using
spinazoo.pygame.keys (made from this table by tools/make_keys.py). Every
controller gets its own keys, so the game knows which one was pressed (for the
"One each" controllers option).

The keys avoid everything Batocera's default pygame mapping still sends for
player 1's other buttons (A B H L M N R S T X Y, Space, Enter, keypad 2/4/6/8)
and the keyboard keys the game uses (A, B, Enter, Backspace), so a stray press
can't act for another player.

Keys are matched by scancode (the key's place on the keyboard), so a French or
German keyboard layout doesn't change them.
"""

BUTTONS = ("up", "down", "left", "right", "south", "east", "start")

# Per controller, the key for each of BUTTONS (evdev / SDL scancode names).
PADS = (
    ("UP", "DOWN", "LEFT", "RIGHT", "J", "K", "ESCAPE"),  # player 1
    ("1", "2", "3", "4", "5", "6", "7"),                  # player 2
    ("Q", "W", "E", "U", "I", "O", "P"),                  # player 3
    ("C", "D", "F", "G", "V", "Z", "8"),                  # player 4
)

# Batocera's names for the pad inputs that send each button.
TRIGGERS = {
    "up": ("up", "joystick1up"),
    "down": ("down", "joystick1down"),
    "left": ("left", "joystick1left"),
    "right": ("right", "joystick1right"),
    "south": ("b",),   # Batocera names buttons SNES-style: "b" is the bottom one
    "east": ("a",),
    "start": ("start",),
}


def evdev(name: str) -> str:
    return "KEY_ESC" if name == "ESCAPE" else "KEY_" + name


def keys_file() -> dict:
    """The contents of spinazoo.pygame.keys."""
    out = {}
    for n, keys in enumerate(PADS, 1):
        actions = []
        for kind in ("dpad", "stick", "buttons"):
            for button, key in zip(BUTTONS, keys):
                triggers = TRIGGERS[button]
                if kind == "dpad" and button in ("up", "down", "left", "right"):
                    trigger = triggers[0]
                elif kind == "stick" and button in ("up", "down", "left", "right"):
                    trigger = triggers[1]
                elif kind == "buttons" and button in ("south", "east", "start"):
                    trigger = triggers[0]
                else:
                    continue
                actions.append({"trigger": trigger, "type": "key", "target": [evdev(key)]})
        out[f"actions_player{n}"] = actions
    return out
