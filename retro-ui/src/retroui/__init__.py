"""retroui: TUI-looking desktop GUI with real pixel graphics."""

from retroui.app import App
from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.input.events import Key, Mod
from retroui.theme import BOX_STYLES, THEMES, Theme, get_theme
from retroui.widgets import (
    Box,
    Button,
    CheckBox,
    ComboBox,
    Dialog,
    Frame,
    GroupBox,
    HBox,
    Label,
    LineEdit,
    ListPopup,
    LivePlot,
    Menu,
    MenuBar,
    MenuItem,
    PixelWidget,
    Popup,
    RingBuffer,
    ScrollBar,
    Series,
    SizeHint,
    Spacer,
    Terminal,
    TerminalScreen,
    HighlightRule,
    VBox,
    Widget,
    message_box,
)

__version__ = "0.0.1"

__all__ = [
    "App", "BOX_STYLES", "Box", "Button", "CheckBox", "ComboBox", "Dialog", "Frame", "GroupBox", "HBox", "Key",
    "Label", "LineEdit", "ListPopup", "LivePlot", "Menu", "MenuBar", "MenuItem", "Mod", "PixelWidget", "Popup",
    "Rect", "RingBuffer", "ScrollBar", "Series", "Signal", "SizeHint", "Spacer", "THEMES", "Terminal", "TerminalScreen", "HighlightRule", "Theme", "VBox", "Widget",
    "get_theme", "message_box",
]
