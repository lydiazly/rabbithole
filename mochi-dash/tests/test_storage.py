"""The high score, which is the only thing the game keeps between runs.

Worth testing precisely because it is the one place a bug is silent: a load that
returns zero looks exactly like a first run, so a broken read does not crash,
it just quietly forgets your best.
"""

import pytest

from mochi_dash import storage


@pytest.fixture
def scorefile(tmp_path, monkeypatch):
    path = tmp_path / ".highscore"
    monkeypatch.setattr(storage, "FILE", path)
    monkeypatch.setattr(storage, "BROWSER", False)
    return path


def test_a_score_survives_a_round_trip(scorefile):
    storage.save(4210)
    assert storage.load() == 4210


def test_no_file_yet_is_a_first_run(scorefile):
    assert not scorefile.exists()
    assert storage.load() == 0


@pytest.mark.parametrize("junk", ["", "   ", "\n", "not a number", "12.5", "1 2"])
def test_unreadable_contents_mean_zero_rather_than_a_crash(scorefile, junk):
    """The file sits in the user's directory and anything may have touched it.

    A truncated write, an editor, another program with the same idea. None of
    that is worth taking the game down for, and none of it should be believed
    either.
    """
    scorefile.write_text(junk)
    assert storage.load() == 0


def test_saving_is_allowed_to_fail_loudly(scorefile, monkeypatch):
    """Deliberately uncaught, so this pins the decision rather than the code.

    A score that cannot be written is a bug worth seeing. Swallowing it would
    lose every high score on a read-only home directory and never say why.
    """
    def refuse(*args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr(type(scorefile), "write_text", refuse)
    with pytest.raises(OSError):
        storage.save(10)


def test_the_browser_backend_uses_local_storage(monkeypatch):
    """pygbag's filesystem is a throwaway unpack of the app archive, so a file
    written there is gone on the next load. Under emscripten the score has to go
    to localStorage instead, and nothing in a desktop test run would notice if
    that branch stopped working.
    """
    import sys
    import types

    store = {}

    class FakeLocalStorage:
        def getItem(self, key):  # noqa: N802 -- the browser's own spelling
            return store.get(key)

        def setItem(self, key, value):  # noqa: N802
            store[key] = value

    module = types.ModuleType("platform")
    module.window = types.SimpleNamespace(localStorage=FakeLocalStorage())
    monkeypatch.setitem(sys.modules, "platform", module)
    monkeypatch.setattr(storage, "BROWSER", True)

    assert storage.load() == 0, "nothing stored yet should read as a first run"
    storage.save(777)
    assert store == {storage.KEY: "777"}, store
    assert storage.load() == 777

    store[storage.KEY] = "scribbled on"
    assert storage.load() == 0
