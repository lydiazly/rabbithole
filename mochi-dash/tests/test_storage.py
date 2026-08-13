"""The high score, which is the only thing the game keeps between runs.

Worth testing precisely because it is the one place a bug is silent: a load that
returns zero looks exactly like a first run, so a broken read does not crash,
it just quietly forgets your best.
"""

import pytest

from mochi_dash import storage


@pytest.fixture
def scorefile(tmp_path, monkeypatch):
    path = tmp_path / "data" / "highscore"
    monkeypatch.setattr(storage, "FILE", path)
    monkeypatch.setattr(storage, "LEGACY_FILE", tmp_path / "legacy" / ".highscore")
    monkeypatch.setattr(storage, "BROWSER", False)
    return path


def test_saving_creates_the_directory_it_needs(scorefile):
    """Nothing else makes it, and a first run has nowhere to write otherwise."""
    assert not scorefile.parent.exists()
    storage.save(1)
    assert storage.load() == 1


@pytest.mark.parametrize(
    "platform,env,expected",
    [
        ("win32", {"APPDATA": "/appdata"}, ("/appdata", "Mochi Dash")),
        ("darwin", {}, ("Library", "Application Support", "Mochi Dash")),
        ("linux", {"XDG_DATA_HOME": "/xdg"}, ("/xdg", "mochi-dash")),
        ("linux", {}, (".local", "share", "mochi-dash")),
    ],
)
def test_each_platform_gets_its_own_conventional_directory(
    platform, env, expected, monkeypatch
):
    """It used to be a dotfile beside the package, which is only writable from a
    checkout: installed into site-packages, or anywhere under Program Files, the
    first score that beat the stored best would raise instead of saving. It was
    shared between accounts on one machine too.
    """
    monkeypatch.setattr(storage.sys, "platform", platform)
    for name in ("APPDATA", "XDG_DATA_HOME"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    path = storage.data_dir()
    assert path.is_absolute(), path
    parts = path.parts
    for piece in expected:
        assert piece in parts or str(path).startswith(piece), (path, piece)


def test_windows_and_linux_still_resolve_without_their_env_vars(monkeypatch):
    """APPDATA and XDG_DATA_HOME are normally set, but a service or a stripped
    environment has neither, and falling back to a relative path would put the
    score in whatever directory the game happened to be started from.
    """
    for platform in ("win32", "linux", "darwin"):
        monkeypatch.setattr(storage.sys, "platform", platform)
        for name in ("APPDATA", "XDG_DATA_HOME"):
            monkeypatch.delenv(name, raising=False)
        assert storage.data_dir().is_absolute(), platform


def test_a_score_saved_by_the_old_version_is_not_lost(scorefile):
    """The previous location is read once, so upgrading does not reset anybody."""
    storage.LEGACY_FILE.parent.mkdir(parents=True)
    storage.LEGACY_FILE.write_text("1234\n")
    assert storage.load() == 1234

    # And the new location wins once there is something in it.
    storage.save(7)
    assert storage.load() == 7
    assert storage.LEGACY_FILE.read_text() == "1234\n", "the old file was touched"


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
    scorefile.parent.mkdir(parents=True, exist_ok=True)
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


def test_a_browser_that_refuses_local_storage_is_survivable(monkeypatch):
    """Safari in a private tab hands the page a store with a quota of zero, so
    writing throws; stricter settings make touching it at all throw.

    Both are the browser's decision, and neither is worth ending a run over --
    which is the opposite of the desktop, where a failed write means a directory
    this code chose and created is broken, and that is worth seeing.
    """
    import sys
    import types

    class Hostile:
        def getItem(self, key):  # noqa: N802
            raise RuntimeError("SecurityError: the operation is insecure")

        def setItem(self, key, value):  # noqa: N802
            raise RuntimeError("QuotaExceededError")

    module = types.ModuleType("platform")
    module.window = types.SimpleNamespace(localStorage=Hostile())
    monkeypatch.setitem(sys.modules, "platform", module)
    monkeypatch.setattr(storage, "BROWSER", True)

    assert storage.load() == 0
    storage.save(99)  # must not raise


def test_a_browser_with_no_storage_object_at_all_is_survivable(monkeypatch):
    """The import itself is what fails if the page never provided one."""
    import sys

    monkeypatch.setitem(sys.modules, "platform", None)
    monkeypatch.setattr(storage, "BROWSER", True)
    assert storage.load() == 0
    storage.save(1)
