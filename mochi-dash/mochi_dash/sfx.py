"""Square-wave blips, synthesised at startup rather than shipped as files.

The whole game is generated from source — the art is ASCII in a module, the
scenery is shape calls — and sound follows the same rule. These are a handful of
tones built into a buffer with the standard library and handed to the mixer, so
there are no assets to lose and nothing to keep in sync with the code.

Everything degrades to silence. A machine with no audio device is common — over
SSH, in a container, in the test suite — and a runner that refuses to start
because it could not open a mixer would be worse than one that runs quietly.
"""

import array
import math

import pygame

SAMPLE_RATE = 22050
BITS = -16  # signed 16-bit, little endian
CHANNELS = 1
# Small buffer: latency between a keypress and its blip is very audible, and
# there is no music here that would suffer from underruns.
BUFFER = 512

# A few milliseconds of ramp at the start of every tone. A square wave otherwise
# begins at full amplitude -- the first sample of the jump is +9830 out of
# silence -- and that step is an audible click in front of the note.
FADE_IN_MS = 4

# The sounds this module knows how to make. Named up front so a call site
# can be checked against it without an audio device present.
BUILT = ("jump", "double_jump", "dash", "smash", "power_down", "die", "blip")

_sounds: dict[str, pygame.mixer.Sound] = {}
_ready = False
enabled = True


def _tone(start_hz, end_hz, ms, volume=0.30, duty=0.5) -> pygame.mixer.Sound:
    """One swept square wave with a linear fade-out.

    Phase is accumulated rather than computed from `t * frequency`, which would
    tear audibly as the frequency slides.
    """
    samples = int(SAMPLE_RATE * ms / 1000)
    fade = max(1, int(SAMPLE_RATE * FADE_IN_MS / 1000))
    buf = array.array("h")
    phase = 0.0
    for i in range(samples):
        progress = i / samples
        hz = start_hz + (end_hz - start_hz) * progress
        phase = (phase + hz / SAMPLE_RATE) % 1.0
        wave = 1.0 if phase < duty else -1.0
        envelope = (1.0 - progress) * min(1.0, i / fade)
        buf.append(int(wave * envelope * volume * 32767))
    return pygame.mixer.Sound(buffer=buf.tobytes())


WANTED = (SAMPLE_RATE, BITS, CHANNELS)


def prepare() -> None:
    """Choose the mixer format. Must run before `pygame.init()`.

    `pygame.init()` opens the mixer at its own defaults, and `mixer.init` on an
    already-open mixer is a silent no-op -- which is how the tones below once
    ended up read back at 44100 stereo, a quarter of their length and an octave
    and a half sharp. Closing and reopening the device fixed the format but pops:
    a device transition is audible on most drivers, and that burst at startup was
    exactly it. Declaring the format up front opens the device once, correctly.
    """
    pygame.mixer.pre_init(SAMPLE_RATE, BITS, CHANNELS, BUFFER)


def init() -> None:
    """Build the tones. Silent, not fatal, if there is no audio device."""
    global _ready
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(SAMPLE_RATE, BITS, CHANNELS, BUFFER)
        elif pygame.mixer.get_init()[:3] != WANTED:
            # `prepare()` was skipped or overridden. Reopening pops, so this is
            # the fallback rather than the normal path.
            pygame.mixer.quit()
            pygame.mixer.init(SAMPLE_RATE, BITS, CHANNELS, BUFFER)
    except pygame.error:
        _ready = False
        return
    _sounds.update(
        # Rising blip for leaving the ground, a shorter and higher one for the
        # second jump so the two are distinguishable without looking.
        jump=_tone(430, 700, 90),
        double_jump=_tone(700, 980, 70, volume=0.24),
        # Earning a dash: the one unambiguously good news in the game, so it
        # sweeps a long way up.
        dash=_tone(330, 1250, 260, volume=0.28, duty=0.25),
        # Flattening something. Short, low and a narrow duty, which is as close
        # to a crunch as a square wave gets.
        smash=_tone(760, 190, 90, volume=0.30, duty=0.12),
        # The dash running out: the rising sweep that earned it, backwards.
        power_down=_tone(1100, 380, 200, volume=0.24, duty=0.25),
        # Falling and longer: the only sound that is bad news.
        die=_tone(420, 110, 380, volume=0.34),
        # Menu movement, kept quiet enough to hold a key down against.
        blip=_tone(560, 560, 35, volume=0.16, duty=0.25),
    )
    _ready = True


def play(name: str) -> None:
    if name not in BUILT:
        raise KeyError(f"no such sound: {name!r}")
    if _ready and enabled:
        _sounds[name].play()


def stop() -> None:
    if _ready:
        pygame.mixer.stop()
