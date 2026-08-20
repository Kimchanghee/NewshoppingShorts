"""Responsive sizing helpers for the desktop application shell.

Qt works in device-independent pixels, so every calculation in this module is
based on the screen's ``availableGeometry`` rather than physical resolution.
Windows receive a useful initial size, but remain resizable and maximizable so
OS text scaling never has to fight a rigid 16:10 canvas.
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QObject, QRect, QSize, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QWIDGETSIZE_MAX


WINDOW_MARGIN = 12
REGULAR_WINDOW_SIZE = QSize(1280, 800)
MINIMUM_WINDOW_SIZE = QSize(760, 520)


def calculate_window_rect(available: QRect) -> QRect:
    """Return a centered initial rect fully contained in *available*.

    Width and height are clamped independently. On short laptop work areas this
    uses the available width instead of shrinking both dimensions just to keep
    a decorative aspect ratio, leaving more room for wrapped Korean text.
    """
    if available.isEmpty():
        return QRect(0, 0, REGULAR_WINDOW_SIZE.width(), REGULAR_WINDOW_SIZE.height())

    usable_width = max(1, available.width() - WINDOW_MARGIN * 2)
    usable_height = max(1, available.height() - WINDOW_MARGIN * 2)

    width = min(REGULAR_WINDOW_SIZE.width(), usable_width)
    height = min(REGULAR_WINDOW_SIZE.height(), usable_height)

    x = available.x() + (available.width() - width) // 2
    y = available.y() + (available.height() - height) // 2
    return QRect(x, y, width, height)


def apply_fixed_window_geometry(window, available: QRect) -> QRect:
    """Apply a safe initial geometry while keeping the window responsive.

    The historical name is retained for compatibility with existing callers.
    Any fixed minimum/maximum left by an older UI setup is cleared here.
    """
    target = calculate_window_rect(available)
    window.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
    minimum = QSize(
        min(MINIMUM_WINDOW_SIZE.width(), target.width()),
        min(MINIMUM_WINDOW_SIZE.height(), target.height()),
    )
    window.setMinimumSize(minimum)
    window.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
    window.resize(target.size())
    window.move(target.topLeft())
    return target


class FixedWindowController(QObject):
    """Keep the resizable shell inside the monitor when screens change.

    The class name is a compatibility alias used throughout the existing app.
    """

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._window_handle = None
        window.installEventFilter(self)

    def _connect_screen_signal(self) -> None:
        handle = self.window.windowHandle()
        if handle is None or handle is self._window_handle:
            return
        self._window_handle = handle
        handle.screenChanged.connect(self.apply_screen)

    def apply_screen(self, screen=None) -> QRect:
        screen = screen or self.window.screen() or QApplication.primaryScreen()
        if screen is None:
            return QRect(self.window.geometry())
        available = screen.availableGeometry()
        target = calculate_window_rect(available)
        current = self.window.frameGeometry()
        if current.width() > target.width() or current.height() > target.height():
            self.window.resize(
                min(current.width(), target.width()),
                min(current.height(), target.height()),
            )
        frame = self.window.frameGeometry()
        x = min(max(frame.x(), available.left()), available.right() - frame.width() + 1)
        y = min(max(frame.y(), available.top()), available.bottom() - frame.height() + 1)
        self.window.move(x, y)
        return QRect(self.window.geometry())

    def eventFilter(self, obj, event) -> bool:
        if obj is self.window and event.type() == QEvent.Type.Show:
            self._connect_screen_signal()
        return super().eventFilter(obj, event)


def bounded_size(
    available: QRect,
    preferred: QSize,
    minimum: QSize,
    margin: int = WINDOW_MARGIN,
) -> QSize:
    """Fit a window size to a desktop without enforcing an impossible floor."""
    if available.isEmpty():
        return preferred
    usable_width = max(1, available.width() - margin * 2)
    usable_height = max(1, available.height() - margin * 2)
    width = min(max(minimum.width(), preferred.width()), usable_width)
    height = min(max(minimum.height(), preferred.height()), usable_height)
    return QSize(width, height)


def fit_window_to_available(
    window,
    preferred: QSize,
    minimum: QSize = QSize(320, 240),
    margin: int = WINDOW_MARGIN,
) -> QSize:
    """Resize and center a dialog without imposing an impossible minimum."""
    screen = (
        window.screen()
        or QApplication.screenAt(QCursor.pos())
        or QApplication.primaryScreen()
    )
    available = screen.availableGeometry() if screen else QRect(0, 0, 1280, 800)
    size = bounded_size(available, preferred, minimum, margin)
    window.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
    window.setMinimumSize(
        min(minimum.width(), size.width()),
        min(minimum.height(), size.height()),
    )
    window.resize(size)
    window.move(
        available.x() + (available.width() - size.width()) // 2,
        available.y() + (available.height() - size.height()) // 2,
    )
    return size


@dataclass(frozen=True)
class LayoutProfile:
    """Responsive shell values selected from the current window size."""

    navigation_mode: str
    show_progress_panel: bool
    content_margin_x: int
    content_margin_y: int
    compact_topbar: bool
    compact_mode_page: bool


def layout_profile(size: QSize) -> LayoutProfile:
    """Choose stable breakpoints for the main application shell."""
    width = size.width()
    height = size.height()

    if width < 1100:
        navigation_mode = "icons"
    elif width < 1500:
        navigation_mode = "compact"
    else:
        navigation_mode = "full"

    return LayoutProfile(
        navigation_mode=navigation_mode,
        show_progress_panel=height >= 740 and width >= 1200,
        content_margin_x=8 if width < 1000 else 14,
        content_margin_y=6 if height < 720 else 10,
        compact_topbar=width < 1400,
        compact_mode_page=height < 720 or width < 1100,
    )


class ResponsiveLayoutController(QObject):
    """Apply shell breakpoints without rebuilding page widgets."""

    def __init__(
        self,
        *,
        window,
        step_nav,
        left_container,
        progress_panel,
        stack_layout,
        topbar,
        mode_selection_panel=None,
    ):
        super().__init__(window)
        self.window = window
        self.step_nav = step_nav
        self.left_container = left_container
        self.progress_panel = progress_panel
        self.stack_layout = stack_layout
        self.topbar = topbar
        self.mode_selection_panel = mode_selection_panel
        self._last_profile: LayoutProfile | None = None
        window.installEventFilter(self)

    def apply(self, size: QSize) -> LayoutProfile:
        profile = layout_profile(size)

        if hasattr(self.step_nav, "set_display_mode"):
            self.step_nav.set_display_mode(profile.navigation_mode)

        nav_width = self.step_nav.width()
        self.left_container.setMinimumWidth(nav_width)
        self.left_container.setMaximumWidth(nav_width)

        self.progress_panel.setVisible(profile.show_progress_panel)
        if profile.show_progress_panel:
            preferred_progress_height = max(150, min(300, round(size.height() * 0.30)))
            self.progress_panel.setMinimumHeight(preferred_progress_height)
            self.progress_panel.setMaximumHeight(max(preferred_progress_height, 520))

        self.stack_layout.setContentsMargins(
            profile.content_margin_x,
            profile.content_margin_y,
            profile.content_margin_x,
            profile.content_margin_y,
        )

        if hasattr(self.topbar, "set_compact_mode"):
            self.topbar.set_compact_mode(profile.compact_topbar)

        if hasattr(self.mode_selection_panel, "set_compact_mode"):
            self.mode_selection_panel.set_compact_mode(profile.compact_mode_page)

        self._last_profile = profile
        return profile

    def eventFilter(self, obj, event) -> bool:
        if obj is self.window and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.WindowStateChange,
        }:
            self.apply(self.window.size())
        return super().eventFilter(obj, event)
