"""Write spinazoo/spinazoo.pygame.keys from the table in spinazoo/pads.py."""

import json
import sys
from pathlib import Path

GAME = Path(__file__).resolve().parent.parent / "spinazoo"
sys.path.insert(0, str(GAME))

import pads  # noqa: E402

(GAME / "spinazoo.pygame.keys").write_text(json.dumps(pads.keys_file(), indent=2) + "\n")
print("wrote", GAME / "spinazoo.pygame.keys")
