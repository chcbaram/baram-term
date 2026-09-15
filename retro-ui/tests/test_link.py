import webbrowser

import pytest

from retroui import App, Label, Link, VBox
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent
from retroui.render.cellbuffer import Attr

URL = "https://github.com/chcbaram/baram-term"


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(50, 4), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield a
    a.close()


def click(app, x, y, x_up=None):
    app.dispatch(MouseEvent("down", 1, x, y, 0, 0))
    app.dispatch(MouseEvent("up", 1, x if x_up is None else x_up, y, 0, 0))


def test_click_and_enter_emit_url_and_text_is_underlined(app):
    got = []
    link = Link("repo", URL, on_click=got.append)
    app.set_root(VBox(link, Label("below")))
    app.step()
    assert app.screen_text()[0].startswith("repo")
    assert app.buf.get(0, 0)[3] & Attr.UNDERLINE

    click(app, 1, 0)
    assert got == [URL] and app.focus is link
    app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
    assert got == [URL, URL]


def test_release_outside_does_not_open(app):
    got = []
    link = Link("repo", URL, on_click=got.append)
    app.set_root(VBox(Link("x", on_click=got.append, min_size=(10, 1)), link, Label("below")))
    app.step()
    app.dispatch(MouseEvent("down", 1, 1, 1, 0, 0))
    app.dispatch(MouseEvent("up", 1, 1, 3, 0, 0))
    assert got == []


def test_default_opens_browser(app, monkeypatch):
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda url, *a, **k: opened.append(url) or True)
    link = Link(URL)
    app.set_root(VBox(link))
    app.step()
    click(app, 2, 0)
    assert opened == [URL] and link.url == URL
