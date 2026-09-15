"""retroui: TUI-looking desktop GUI with real pixel graphics."""

from retroui.app import App
from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.i18n import set_language
from retroui.input.events import Key, Mod
from retroui.theme import BOX_STYLES, THEMES, Theme, get_theme
from retroui.widgets import (
    Box,
    Button,
    CheckBox,
    ComboBox,
    EditableComboBox,
    Dialog,
    FileDialog,
    Frame,
    GroupBox,
    HBox,
    Label,
    LineEdit,
    Link,
    ListPopup,
    ListView,
    LivePlot,
    Menu,
    MenuBar,
    MenuItem,
    PixelWidget,
    PlotLegend,
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
    "PlotLegend",
    "EditableComboBox",
    "Link", "set_language",
    "FileDialog", "ListView",
    "App", "BOX_STYLES", "Box", "Button", "CheckBox", "ComboBox", "Dialog", "Frame", "GroupBox", "HBox", "Key",
    "Label", "LineEdit", "ListPopup", "LivePlot", "Menu", "MenuBar", "MenuItem", "Mod", "PixelWidget", "Popup",
    "Rect", "RingBuffer", "ScrollBar", "Series", "Signal", "SizeHint", "Spacer", "THEMES", "Terminal", "TerminalScreen", "HighlightRule", "Theme", "VBox", "Widget",
    "get_theme", "message_box",
]
