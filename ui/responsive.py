"""Responsive sizing helpers for the desktop application shell.

Qt works in device-independent pixels, so every calculation in this module is
based on the screen's ``availableGeometry`` rather than physical resolution.
This keeps windows inside the usable desktop at mixed DPI settings as well as
on short or portrait displays.
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QObject, QRect, QSize, Qt
from PyQt6.QtWidgets import QApplication


WINDOW_MARGIN = 12
REGULAR_WINDOW_SIZE = QSize(1280, 800)
COMPACT_WINDOW_SIZE = QSize(1024, 640)
WINDOW_ASPECT_RATIO = REGULAR_WINDOW_SIZE.width() / REGULAR_WINDOW_SIZE.height()


def calculate_window_rect(available: QRect) -> QRect:
    """Return a centered, fixed-profile rect contained in *available*.

    Most displays receive the same 1280x800 logical workspace. Smaller work
    areas use the same 16:10 compact profile, and only very small desktops fall
    back to an aspect-preserving fit. This keeps the composition stable across
    resolutions and per-monitor DPI settings without letting users resize it.
    """
    if available.isEmpty():
        return QRect(0, 0, REGULAR_WINDOW_SIZE.width(), REGULAR_WINDOW_SIZE.height())

    usable_width = max(1, available.width() - WINDOW_MARGIN * 2)
    usable_height = max(1, available.height() - WINDOW_MARGIN * 2)

    if (
        usable_width >= REGULAR_WINDOW_SIZE.width()
        and usable_height >= REGULAR_WINDOW_SIZE.height()
    ):
        width, height = REGULAR_WINDOW_SIZE.width(), REGULAR_WINDOW_SIZE.height()
    elif (
        usable_width >= COMPACT_WINDOW_SIZE.width()
        and usable_height >= COMPACT_WINDOW_SIZE.height()
    ):
        width, height = COMPACT_WINDOW_SIZE.width(), COMPACT_WINDOW_SIZE.height()
    else:
        width = usable_width
        height = max(1, round(width / WINDOW_ASPECT_RATIO))
        if height > usable_height:
            height = usable_height
            width = max(1, round(height * WINDOW_ASPECT_RATIO))

    x = available.x() + (available.width() - width) // 2
    y = available.y() + (available.height() - height) // 2
    return QRect(x, y, width, height)


def apply_fixed_window_geometry(window, available: QRect) -> QRect:
    """Apply the monitor profile and disable user resizing/maximizing."""
    target = calculate_window_rect(available)
    if window.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint:
        window.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
    window.setFixedSize(target.size())
    window.move(target.topLeft())
    return target


class FixedWindowController(QObject):
    """Re-fit the fixed shell only when it moves to another monitor."""

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
        return apply_fixed_window_geometry(self.window, screen.availableGeometry())

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

    if width < 1120:
        navigation_mode = "icons"
    elif width < 1240:
        navigation_mode = "compact"
    else:
        navigation_mode = "full"

    return LayoutProfile(
        navigation_mode=navigation_mode,
        show_progress_panel=height >= 740 and width >= 1200,
        content_margin_x=8 if width < 1000 else 14,
        content_margin_y=6 if height < 720 else 10,
        compact_topbar=width < 1120,
        compact_mode_page=height < 700 or width < 1100,
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
