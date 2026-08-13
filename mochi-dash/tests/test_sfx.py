"""The synthesised sounds. No asset files, so the waveforms are code too.

Tested under the dummy audio driver, which opens a real mixer against no
hardware -- enough to build a Sound and read its samples back, which is where
the two bugs this module has had both lived: a mixer already open at the wrong
rate, so every tone came out short and sharp, and a first sample that jumped
straight to full amplitude, which is what a startup pop is.
"""

import pytest

import pygame

from mochi_dash import sfx


@pytest.fixture(scope="module", autouse=True)
def mixer():
    sfx.prepare()
    pygame.init()
    sfx.init()
    yield
    pygame.quit()


def test_every_named_sound_gets_built():
    """`play` looks sounds up by name, so a typo is silent rather than loud."""
    assert sfx.BUILT, "no sounds declared"
    for name in sfx.BUILT:
        assert name in sfx._sounds, f"{name} was never built"


def test_the_mixer_opened_at_the_rate_the_tones_assume():
    """A mixer already open at another rate is not reopened by `mixer.init`.

    That is not hypothetical: it is why every sound was once a quarter of its
    intended length and an octave and a half sharp.
    """
    assert pygame.mixer.get_init() is not None, "no mixer at all"
    assert pygame.mixer.get_init() == sfx.WANTED, pygame.mixer.get_init()


def test_tones_start_from_silence():
    """A waveform that opens at full amplitude is a click on every play.

    The fade-in is a handful of samples -- inaudible as a fade, decisive as the
    difference between a clean start and a pop.
    """
    import array

    for name in sfx.BUILT:
        raw = array.array("h")
        raw.frombytes(sfx._sounds[name].get_raw())
        assert raw, name
        assert abs(raw[0]) < 2000, f"{name} opens at {raw[0]}"
        assert max(abs(s) for s in raw) > 2000, f"{name} is silent"


def test_tones_fade_out_so_nothing_is_cut_off_mid_wave():
    import array

    for name in sfx.BUILT:
        raw = array.array("h")
        raw.frombytes(sfx._sounds[name].get_raw())
        assert abs(raw[-1]) < abs(max(raw, key=abs)) // 4, f"{name} ends abruptly"


def test_playing_is_a_no_op_when_the_sound_is_switched_off(monkeypatch):
    """The menu's SOUND row flips one flag; nothing else knows about it.

    Swapped at the dictionary rather than on the Sound, whose `play` is a
    read-only C attribute.
    """
    played = []

    class Spy:
        def play(self):
            played.append(1)

    name = sfx.BUILT[0]
    monkeypatch.setitem(sfx._sounds, name, Spy())

    monkeypatch.setattr(sfx, "enabled", False)
    sfx.play(name)
    assert played == []

    monkeypatch.setattr(sfx, "enabled", True)
    sfx.play(name)
    assert played == [1]


def test_an_unknown_name_raises_rather_than_going_quiet():
    """Deliberate, and the opposite of what you would guess for decoration.

    Sounds are named at every call site and never at compile time, so a typo has
    no other way to announce itself: it would simply be a cue that never played,
    which is exactly the kind of thing nobody notices for months.
    """
    with pytest.raises(KeyError):
        sfx.play("no such sound")
