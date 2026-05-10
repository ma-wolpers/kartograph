from app.adapters.gui.main_window import KartographMainWindow


class _FakeRoot:
    def __str__(self) -> str:
        return ".kartograph-root"


def test_main_window_str_delegates_to_tk_root_path() -> None:
    window = KartographMainWindow.__new__(KartographMainWindow)
    window.__dict__["_tk_root"] = _FakeRoot()

    assert str(window) == ".kartograph-root"
