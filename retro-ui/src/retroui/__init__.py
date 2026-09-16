"""retroui: TUI-looking desktop GUI with real pixel graphics."""

import os

# pygame 은 import 하면서 버전 배너를 print 한다. 콘솔 없이 묶은 실행 파일에서는 sys.stdout 이
# None 이라 그 print 가 AttributeError 로 죽는다 - 창이 뜨기도 전에. 아래 import 가 pygame 을
# 끌어오므로 그보다 먼저 꺼 둔다. 환경변수로 직접 준 값은 건드리지 않는다.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

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
    HSplit,
    HexView,
    VSplit,
    Series,
    SizeHint,
    Spacer,
    Terminal,
    TabBar,
    TerminalScreen,
    TextArea,
    HighlightRule,
    VBox,
    Widget,
    message_box,
)

__version__ = "0.0.1"

__all__ = [
    "HSplit", "HexView", "TabBar", "TextArea", "VSplit",
    "PlotLegend",
    "EditableComboBox",
    "Link", "set_language",
    "FileDialog", "ListView",
    "App", "BOX_STYLES", "Box", "Button", "CheckBox", "ComboBox", "Dialog", "Frame", "GroupBox", "HBox", "Key",
    "Label", "LineEdit", "ListPopup", "LivePlot", "Menu", "MenuBar", "MenuItem", "Mod", "PixelWidget", "Popup",
    "Rect", "RingBuffer", "ScrollBar", "Series", "Signal", "SizeHint", "Spacer", "THEMES", "Terminal", "TerminalScreen", "HighlightRule", "Theme", "VBox", "Widget",
    "get_theme", "message_box",
]
