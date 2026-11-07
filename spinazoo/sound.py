"""Spin-A-Zoo! sound: effects and a music loop, synthesised in code.

No sound files and no numpy (Batocera doesn't promise it): samples are built
with plain Python and handed to pygame.mixer as raw 16-bit mono PCM. Effects
are made at start-up (well under a second); the music loop is made in a
background thread and starts when it's ready. With no audio device the game
runs silent.

Any file in the game's sounds/ folder named <effect>.ogg or <effect>.wav
(e.g. lion.ogg, win.wav) replaces that effect; music-playful.ogg,
music-jazz.ogg or music-classical.ogg replaces that tune, and music.ogg
replaces all three.
"""

from __future__ import annotations

import array
import math
import os
import random
import threading
from pathlib import Path

import pygame

RATE = 22050
SOUNDS_DIR = Path(__file__).resolve().parent / "sounds"

# note frequencies
def _hz(n: int) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


NOTES = {name + str(octave): _hz(12 * (octave + 1) + i)
         for octave in range(2, 8)
         for i, name in enumerate(("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"))}


# --- building blocks ---------------------------------------------------------

def silence(dur: float) -> list[float]:
    return [0.0] * int(RATE * dur)


def voice(dur: float, freq, vol: float = 0.4, wave: str = "sine", attack: float = 0.005,
          release: float = 0.08, vibrato: tuple[float, float] = (0, 0),
          tremolo: tuple[float, float] = (0, 0), grit: float = 0.0, seed: int = 1,
          decay: float = 0.0) -> list[float]:
    """One note. freq is a number or a function of t (0..1) for slides.
    decay > 0 fades it like a plucked or struck string (per second)."""
    n = int(RATE * dur)
    out = [0.0] * n
    phase = 0.0
    a, r = max(1, int(RATE * attack)), max(1, int(RATE * release))
    vr, vd = vibrato
    tr, td = tremolo
    rng = random.Random(seed)
    fixed = not callable(freq)
    tau = 2 * math.pi
    for i in range(n):
        t = i / n
        f = freq if fixed else freq(t)
        if vd:
            f *= 1 + vd * math.sin(tau * vr * i / RATE)
        phase += f / RATE
        p = phase % 1.0
        if wave == "sine":
            v = math.sin(tau * p)
        elif wave == "triangle":
            v = 4 * abs(p - 0.5) - 1
        elif wave == "bell":  # inharmonic partials: a struck, glassy sound
            v = math.sin(tau * p) + 0.4 * math.sin(tau * p * 2.76) * (1 - t) + 0.2 * math.sin(tau * p * 5.4) * (1 - t) ** 2
            v *= 0.7
        elif wave == "saw":   # soft sawtooth: a few harmonics
            v = (math.sin(tau * p) + math.sin(2 * tau * p) / 2 + math.sin(3 * tau * p) / 3
                 + math.sin(4 * tau * p) / 4) * 0.6
        else:                 # soft square: odd harmonics
            v = (math.sin(tau * p) + math.sin(3 * tau * p) / 3 + math.sin(5 * tau * p) / 5) * 0.8
        if grit:
            v = v * (1 - grit) + rng.uniform(-1, 1) * grit
        env = min(1.0, i / a, (n - i) / r)
        if decay:
            env *= math.exp(-decay * i / RATE)
        if td:
            env *= 1 - td * (0.5 + 0.5 * math.sin(tau * tr * i / RATE))
        out[i] = v * vol * env
    return out


def noise(dur: float, vol: float = 0.3, start: float = 0.05, end: float = 0.4,
          shape: str = "swell", seed: int = 7) -> list[float]:
    """Filtered noise; brightness sweeps start->end. shape: swell or hit."""
    n = int(RATE * dur)
    out = [0.0] * n
    y = 0.0
    rng = random.Random(seed)
    for i in range(n):
        t = i / n
        k = start + (end - start) * t
        y += k * (rng.uniform(-1, 1) - y)
        env = math.sin(math.pi * t) if shape == "swell" else (1 - t) ** 3
        out[i] = y * vol * env * 3
    return out


def seq(*parts: list[float]) -> list[float]:
    out: list[float] = []
    for p in parts:
        out += p
    return out


def mix(*parts: list[float], offsets: tuple[float, ...] | None = None) -> list[float]:
    offs = [int(RATE * o) for o in (offsets or [0] * len(parts))]
    n = max(len(p) + o for p, o in zip(parts, offs))
    out = [0.0] * n
    for p, o in zip(parts, offs):
        for i, v in enumerate(p):
            out[o + i] += v
    return out


def echo(samples: list[float], delay: float = 0.12, feedback: float = 0.35, taps: int = 3) -> list[float]:
    d = int(RATE * delay)
    out = samples + [0.0] * (d * taps)
    for k in range(1, taps + 1):
        g = feedback ** k
        off = d * k
        for i, v in enumerate(samples):
            out[off + i] += v * g
    return out


def arpeggio(names: str, step: float, vol: float, wave: str = "bell", hold: float = 0.25) -> list[float]:
    notes = names.split()
    parts = [voice(step * (len(notes) - i) + hold, NOTES[nm], vol, wave, release=hold)
             for i, nm in enumerate(notes)]
    return mix(*parts, offsets=tuple(i * step for i in range(len(notes))))


def glide(*points: float):
    """A frequency curve through the given points, for slides."""
    def f(t: float) -> float:
        x = t * (len(points) - 1)
        i = min(int(x), len(points) - 2)
        return points[i] + (points[i + 1] - points[i]) * (x - i)
    return f


# --- the effects -------------------------------------------------------------

def effects() -> dict[str, list[float]]:
    N = NOTES
    drum_roll = []
    for k in range(18):  # hits get closer together and louder
        gap = 0.06 - k * 0.0022
        drum_roll += noise(0.05, 0.12 + k * 0.012, 0.3, 0.5, "hit", seed=k) + silence(max(0.005, gap - 0.05))
    cheer = mix(*(voice(1.6, glide(f, f * 1.15, f * 0.95), 0.025, "saw", attack=0.3, release=0.8,
                        vibrato=(7 + i, 0.03), grit=0.6, seed=i) for i, f in enumerate((300, 380, 460, 540, 620))),
                noise(1.6, 0.12, 0.08, 0.15, "swell"))
    fanfare = echo(seq(voice(0.12, N["C5"], 0.3, "square"), voice(0.12, N["E5"], 0.3, "square"),
                       voice(0.12, N["G5"], 0.3, "square"),
                       mix(voice(0.9, N["C6"], 0.28, "square", release=0.5, vibrato=(6, 0.006)),
                           voice(0.9, N["E6"], 0.14, "bell", release=0.6),
                           voice(0.9, N["G6"], 0.1, "bell", release=0.6))), 0.14, 0.3, 2)
    return {
        # interface
        "tick": voice(0.014, 2300, 0.2, release=0.01),
        "blip": voice(0.05, 880, 0.3, "square", release=0.03),
        "back": voice(0.08, glide(520, 360), 0.28, "square", release=0.04),
        "select": seq(voice(0.05, 660, 0.3, "square", release=0.02), voice(0.1, 990, 0.3, "square", release=0.06)),
        # spinning
        "spin": noise(0.35, 0.18, 0.02, 0.35),
        "stop": mix(noise(0.05, 0.3, 0.6, 0.4, "hit"), voice(0.08, glide(420, 300), 0.3, release=0.06)),
        # results, one character per spinner
        "color": echo(arpeggio("C6 E6 G6 C7", 0.07, 0.22), 0.11, 0.3),
        "shape": seq(voice(0.32, glide(180, 640, 300), 0.35, "sine", vibrato=(14, 0.05)),
                     voice(0.12, 600, 0.15, "bell")),
        "pattern": echo(seq(*(voice(0.06, N[n], 0.4, "triangle", release=0.03) for n in "E6 G6 E6 G6 E6 G6 C7".split())), 0.1, 0.35),
        "any": seq(voice(0.09, N["E5"], 0.28, "triangle"), voice(0.16, N["C5"], 0.28, "triangle")),
        "wild": echo(mix(arpeggio("C5 E5 G5 C6 E6 G6 C7", 0.05, 0.2), noise(0.5, 0.06, 0.2, 0.6)), 0.09, 0.4, 4),
        "zoo": mix(noise(0.8, 0.3, 0.03, 0.5), echo(arpeggio("G5 C6 E6 G6 E6 C6 G5 C6", 0.07, 0.16, "triangle"), 0.1, 0.3)),
        # the animals
        "lion": mix(voice(1.0, glide(120, 95, 70), 0.42, "saw", attack=0.12, release=0.45,
                          vibrato=(5, 0.04), tremolo=(28, 0.35), grit=0.35),
                    noise(1.0, 0.18, 0.05, 0.02)),
        "cat": seq(voice(0.6, glide(520, 840, 900, 620), 0.3, "saw", attack=0.06, release=0.25,
                         vibrato=(6, 0.02))),
        "eagle": echo(voice(0.65, glide(1900, 2600, 2300, 1700), 0.18, "saw", attack=0.03, release=0.3,
                            vibrato=(32, 0.025), grit=0.2), 0.13, 0.3, 2),
        "bear": mix(voice(0.85, glide(85, 70, 60), 0.45, "saw", attack=0.08, release=0.35,
                          tremolo=(13, 0.6), grit=0.3), noise(0.85, 0.15, 0.04, 0.02)),
        "elephant": echo(voice(0.9, glide(260, 520, 560, 470), 0.3, "saw", attack=0.05, release=0.3,
                               vibrato=(7, 0.03), grit=0.08), 0.12, 0.25, 2),
        # placing and turns
        "place": mix(voice(0.14, glide(560, 240), 0.5, release=0.09), voice(0.18, N["E7"], 0.06, "bell"),
                     offsets=(0, 0.05)),
        "bonk": voice(0.15, glide(170, 135), 0.3, "square"),
        "turn": seq(voice(0.08, N["G5"], 0.28, "bell", release=0.04), voice(0.18, N["C6"], 0.28, "bell", release=0.12)),
        # endings
        "win": mix(drum_roll, fanfare, cheer, offsets=(0, 0.75, 0.9)),
        "draw": seq(*(voice(0.32, glide(f, f * 0.97), 0.26, "saw", attack=0.03, release=0.12,
                            tremolo=(5, 0.5)) for f in (N["G4"], N["F#4"], N["F4"])),
                    voice(0.6, glide(N["E4"], N["E4"] * 0.96), 0.26, "saw", release=0.3, tremolo=(5, 0.5)),
                    silence(0.1), arpeggio("C5 E5 G5 C6", 0.08, 0.2)),
    }


# --- music -------------------------------------------------------------------

BPM = 116
CALM_BPM = 92
CHORDS = ["C4 E4 G4", "A3 C4 E4", "F3 A3 C4", "G3 B3 D4"] * 2
BASS = ["C3", "A2", "F2", "G2"] * 2
# 8 bars of eighth notes: (note or None, length in eighths)
MELODY = [
    [("E5", 2), ("G5", 2), ("C6", 2), ("G5", 2)],
    [("A5", 2), ("E5", 2), ("C5", 2), ("E5", 2)],
    [("F5", 2), ("A5", 2), ("C6", 2), ("A5", 1), ("G5", 1)],
    [("G5", 3), ("F5", 1), ("E5", 2), ("D5", 2)],
    [("E5", 1), ("E5", 1), ("G5", 2), ("C6", 3), ("B5", 1)],
    [("A5", 2), ("C6", 2), ("E6", 2), ("C6", 2)],
    [("A5", 2), ("F5", 2), ("A5", 1), ("C6", 1), ("D6", 2)],
    [("B5", 2), ("D6", 2), ("C6", 3), (None, 1)],
]


TUNES = ("playful", "jazz", "classical")


def _canvas(seconds: float):
    """A silent loop of the given length and put(samples, at) to add into
    it; anything running past the end wraps round to the start, so the loop
    joins up without a click."""
    total = int(RATE * seconds)
    out = [0.0] * total

    def put(samples, at):
        o = int(RATE * at)
        for i, v in enumerate(samples):
            out[(o + i) % total] += v
    return out, put


def music(calm: bool = False, tune: str = "playful") -> list[float]:
    if tune == "jazz":
        return jazz(calm)
    if tune == "classical":
        return classical(calm)
    return playful(calm)


def playful(calm: bool = False) -> list[float]:
    """An 8-bar loop: bass, offbeat chords, melody and light drums. Calm:
    slower, no drums, and a soft triangle melody instead of the square one."""
    e = 60 / (CALM_BPM if calm else BPM) / 2  # one eighth note
    bar = 8 * e
    out, put = _canvas(bar * len(MELODY))

    kick = voice(0.14, glide(130, 45), 0.32, release=0.1)
    snare = noise(0.1, 0.08, 0.5, 0.4, "hit", seed=3)
    hat = noise(0.03, 0.035, 0.9, 0.9, "hit", seed=5)
    for b in range(len(MELODY)):
        t0 = b * bar
        for beat in range(4):
            put(voice(e * 1.6, NOTES[BASS[b]] * (1 if beat % 2 == 0 else 2), 0.16, "triangle",
                      release=0.05), t0 + beat * 2 * e)
            if not calm:
                put(kick if beat % 2 == 0 else snare, t0 + beat * 2 * e)
        for k in range(8 if not calm else 0):
            put(hat, t0 + k * e)
        for k in (1, 3, 5, 7):  # offbeat chord stabs
            for nm in CHORDS[b].split():
                put(voice(e * 0.8, NOTES[nm], 0.045, "bell", release=0.08), t0 + k * e)
        pos = t0
        for note, length in MELODY[b]:
            if note:
                put(voice(e * length * 0.95, NOTES[note], 0.16 if calm else 0.1,
                          "triangle" if calm else "square", release=0.12 if calm else 0.06,
                          vibrato=(5.5, 0.004)), pos)
            pos += e * length
    return out


# A small swing tune in F: walking bass, soft piano chords, vibraphone tune,
# and (unless calm) a ride cymbal. Eighth notes swing: long-short, 2:1.
JAZZ_BPM, JAZZ_CALM_BPM = 132, 104
JAZZ_CHORDS = ["A#3 D4 F4 A4", "A#3 D4 E4 A4", "A3 C4 E4 G4", "C4 E4 F#4 B4",   # Gm7 C7 Fmaj7 D7
               "A#3 D4 F4 A4", "A#3 D4 E4 A4", "A3 C4 D4 G4", "A#3 D4 E4 A4"]    # Gm7 C7 F6 C7
JAZZ_BASS = ["G2 A#2 D3 C#3", "C3 A#2 G2 E2", "F2 A2 C3 C#3", "D3 F#2 A2 G#2",
             "G2 A#2 D3 C#3", "C3 A#2 G2 E2", "F2 A2 D3 C#3", "C3 A#2 A2 G#2"]
JAZZ_MELODY = [  # (note or None, length in eighths)
    [("D5", 2), ("F5", 1), ("A5", 1), ("G5", 3), (None, 1)],
    [("E5", 1), ("G5", 1), ("A#5", 2), ("A5", 1), ("G5", 1), ("E5", 2)],
    [("F5", 3), ("E5", 1), ("C5", 2), ("A4", 2)],
    [("F#5", 2), ("A5", 1), ("C6", 1), ("A5", 3), (None, 1)],
    [("A#5", 2), ("A5", 1), ("G5", 1), ("F5", 2), ("D5", 2)],
    [("E5", 1), ("F5", 1), ("G5", 2), ("A#5", 2), ("D6", 2)],
    [("C6", 3), ("A5", 1), ("F5", 2), ("D5", 2)],
    [("E5", 2), ("G5", 2), ("F5", 3), (None, 1)],
]


def jazz(calm: bool = False) -> list[float]:
    beat = 60 / (JAZZ_CALM_BPM if calm else JAZZ_BPM)
    bar = 4 * beat
    out, put = _canvas(bar * len(JAZZ_MELODY))

    def swung(eighth: int) -> float:  # time of an eighth note, in beats
        return eighth // 2 + (2 / 3 if eighth % 2 else 0)

    ride = noise(0.25, 0.022, 0.85, 0.9, "hit", seed=11)
    pedal = noise(0.05, 0.03, 0.4, 0.3, "hit", seed=12)
    for b in range(len(JAZZ_MELODY)):
        t0 = b * bar
        for k, nm in enumerate(JAZZ_BASS[b].split()):  # walking bass, one note a beat
            put(voice(beat * 0.95, NOTES[nm], 0.24, "triangle", attack=0.01, release=0.06, decay=2.5),
                t0 + k * beat)
        for at, length in ((0, 0.5), (swung(3), 1.2)):  # piano: the Charleston rhythm
            for nm in JAZZ_CHORDS[b].split():
                put(voice(beat * length, NOTES[nm], 0.035, "sine", attack=0.006, release=0.1, decay=3),
                    t0 + at * beat)
        if not calm:
            for at in (0, 1, swung(3), 2, 3, swung(7)):
                put(ride, t0 + at * beat)
            for at in (1, 3):
                put(pedal, t0 + at * beat)
        k = 0
        for note, length in JAZZ_MELODY[b]:
            if note:
                start, end = swung(k), swung(k + length)
                put(voice((end - start) * beat * 0.95, NOTES[note], 0.16, "bell", attack=0.005,
                          release=0.1, tremolo=(5, 0.25), decay=1.8), t0 + start * beat)
            k += length
    return out


# A light piece in G in the classical style: Alberti bass on a soft
# harpsichord, a flute tune on top, a low note to start each bar.
CLASSICAL_BPM, CLASSICAL_CALM_BPM = 88, 72
ALBERTI = ["G3 D4 B3 D4", "G3 E4 C4 E4", "F#3 D4 A3 D4", "G3 D4 B3 D4",   # G C D G
           "G3 E4 B3 E4", "A3 E4 C4 E4", "F#3 D4 C4 D4", "G3 D4 B3 D4"]   # Em Am D7 G
CLASSICAL_ROOTS = ["G2", "C3", "D3", "G2", "E2", "A2", "D3", "G2"]
CLASSICAL_MELODY = [  # (note or None, length in sixteenths)
    [("B4", 4), ("D5", 4), ("G5", 6), ("F#5", 2)],
    [("E5", 6), ("D5", 2), ("C5", 4), ("E5", 4)],
    [("D5", 4), ("A4", 4), ("F#5", 6), ("E5", 2)],
    [("D5", 8), ("B4", 4), (None, 4)],
    [("E5", 4), ("G5", 4), ("B5", 6), ("A5", 2)],
    [("A5", 4), ("E5", 4), ("C6", 6), ("B5", 2)],
    [("A5", 4), ("F#5", 4), ("D5", 4), ("C5", 4)],
    [("B4", 8), ("G4", 4), (None, 4)],
]


def classical(calm: bool = False) -> list[float]:
    s16 = 60 / (CLASSICAL_CALM_BPM if calm else CLASSICAL_BPM) / 4
    bar = 16 * s16
    out, put = _canvas(bar * len(CLASSICAL_MELODY))
    for b in range(len(CLASSICAL_MELODY)):
        t0 = b * bar
        put(voice(bar * 0.9, NOTES[CLASSICAL_ROOTS[b]], 0.12, "sine", attack=0.01, release=0.2, decay=1.2), t0)
        pattern = ALBERTI[b].split()
        for k in range(16):
            put(voice(s16 * 1.8, NOTES[pattern[k % 4]], 0.05, "saw", attack=0.003, release=0.05, decay=6),
                t0 + k * s16)
        pos = t0
        for note, length in CLASSICAL_MELODY[b]:
            if note:
                put(voice(length * s16 * 0.95, NOTES[note], 0.15, "sine", attack=0.04, release=0.08,
                          vibrato=(5, 0.006)), pos)
            pos += length * s16
    return out


# --- playing -----------------------------------------------------------------

def _to_sound(samples: list[float]) -> pygame.mixer.Sound:
    data = array.array("h", (int(max(-1.0, min(1.0, v)) * 32000) for v in samples))
    return pygame.mixer.Sound(buffer=data.tobytes())


def _override(name: str) -> pygame.mixer.Sound | None:
    for ext in ("ogg", "wav"):
        f = SOUNDS_DIR / f"{name}.{ext}"
        if f.is_file():
            try:
                return pygame.mixer.Sound(str(f))
            except pygame.error:
                return None
    return None


class Sounds:
    """play(name) does nothing when effects are off or there's no audio."""

    LOUD_VOLUME = 0.55
    CALM_VOLUME = 0.4

    def __init__(self, effects_on: bool = True, music_on: bool = True, calm: bool = True,
                 tune: str = "playful"):
        self.enabled = effects_on
        self.music_on = music_on
        self.calm = calm
        self.tune = tune if tune in TUNES else "playful"
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music: pygame.mixer.Sound | None = None
        self.loops: dict[tuple[str, bool], pygame.mixer.Sound] = {}  # built music, kept
        self.music_channel: pygame.mixer.Channel | None = None
        self.duck_until = 0
        self.lock = threading.Lock()
        if os.environ.get("SPINAZOO_SILENT"):  # tests and tools: skip the build
            return
        try:
            # the samples are mono 16-bit at RATE, so the mixer must match
            if pygame.mixer.get_init() != (RATE, -16, 1):
                pygame.mixer.quit()
                pygame.mixer.init(RATE, -16, 1, 512)
            pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(1)
            self.music_channel = pygame.mixer.Channel(0)
        except pygame.error:
            return
        # building the sounds takes a second or two of CPU; do it in the
        # background so the title screen shows at once (effects first)
        threading.Thread(target=self._build, daemon=True).start()

    def _build(self) -> None:
        try:
            for name, samples in effects().items():
                self.sounds[name] = _override(name) or _to_sound(samples)
            self._tick_volume()
        except pygame.error:
            return
        self._load_music()

    def _load_music(self) -> None:
        """Make (or reuse) the loop for the current tune and calm setting,
        and switch to it. Runs in a background thread."""
        with self.lock:
            key = (self.tune, self.calm)
            snd = self.loops.get(key)
            if snd is None:
                snd = _override(f"music-{self.tune}") or _override("music")
                try:
                    snd = snd or _to_sound(music(self.calm, self.tune))
                except pygame.error:
                    return
                self.loops[key] = snd
            if key != (self.tune, self.calm):
                return  # changed again while building; that call takes over
            if snd is not self.music:
                self.music = snd
                if self.music_channel and self.music_channel.get_busy():
                    self.music_channel.stop()
            self._sync_music()

    def _change_music(self) -> None:
        if self.music_channel:
            threading.Thread(target=self._load_music, daemon=True).start()

    @property
    def music_volume(self) -> float:
        return self.CALM_VOLUME if self.calm else self.LOUD_VOLUME

    def _tick_volume(self) -> None:
        if "tick" in self.sounds:  # the click as each section passes the arrow
            self.sounds["tick"].set_volume(0.4 if self.calm else 1.0)

    def set_calm(self, on: bool) -> None:
        """Swap to the calm (or lively) music; it's built in the background."""
        if on != self.calm:
            self.calm = on
            self._tick_volume()
            self._change_music()

    def set_tune(self, tune: str) -> None:
        """Playful, jazz or classical; built in the background the first time."""
        if tune in TUNES and tune != self.tune:
            self.tune = tune
            self._change_music()

    def _sync_music(self) -> None:
        ch = self.music_channel
        if not ch or not self.music:
            return
        if self.music_on and not ch.get_busy():
            ch.set_volume(self.music_volume)
            ch.play(self.music, loops=-1, fade_ms=800)
        elif not self.music_on and ch.get_busy():
            ch.fadeout(400)

    def set_music(self, on: bool) -> None:
        self.music_on = on
        self._sync_music()

    def play(self, name: str) -> None:
        if not self.enabled or name not in self.sounds:
            return
        snd = self.sounds[name]
        if name in ("win", "draw") and self.music_channel:
            # quieten the music under the big moments
            self.music_channel.set_volume(self.music_volume * 0.2)
            self.duck_until = pygame.time.get_ticks() + int(snd.get_length() * 1000) + 300
        snd.play()

    def update(self) -> None:
        if self.duck_until and pygame.time.get_ticks() > self.duck_until:
            self.duck_until = 0
            if self.music_channel:
                self.music_channel.set_volume(self.music_volume)
