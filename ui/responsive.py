"""Responsive sizing helpers for the desktop application shell.

Qt works in device-independent pixels, so every calculation in this module is
based on the screen's ``availableGeometry`` rather than physical resolution.
This keeps windows inside the usable desktop at mixed DPI settings as well as
on short or portrait displays.
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QObject, QRect, QSize


WINDOW_MARGIN = 12
MAX_WINDOW_WIDTH = 1440
MAX_WINDOW_HEIGHT = 960
PREFERRED_MIN_WIDTH = 960
PREFERRED_MIN_HEIGHT = 640


def calculate_window_rect(available: QRect) -> QRect:
    """Return a centered initial window rect fully contained in *available*.

    The preferred minimum is applied only when the desktop can accommodate it.
    Clamping to the available area happens last, which is the important part on
    Windows displays with 125-200% scaling where the logical height is small.
    """
    if available.isEmpty():
        return QRect(0, 0, 1280, 800)

    usable_width = max(1, available.width() - WINDOW_MARGIN * 2)
    usable_height = max(1, available.height() - WINDOW_MARGIN * 2)

    preferred_width = max(PREFERRED_MIN_WIDTH, round(available.width() * 0.90))
    preferred_height = max(PREFERRED_MIN_HEIGHT, round(available.height() * 0.90))

    width = min(MAX_WINDOW_WIDTH, preferred_width, usable_width)
    height = min(MAX_WINDOW_HEIGHT, preferred_height, usable_height)
    x = available.x() + (available.width() - width) // 2
    y = available.y() + (available.height() - height) // 2
    return QRect(x, y, width, height)


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


def layout_profile(size: QSize) -> LayoutProfile:
    """Choose stable breakpoints for the main application shell."""
    width = size.width()
    height = size.height()

    if width < 880:
        navigation_mode = "icons"
    elif width < 1180:
        navigation_mode = "compact"
    else:
        navigation_mode = "full"

    return LayoutProfile(
        navigation_mode=navigation_mode,
        show_progress_panel=height >= 740 and width >= 900,
        content_margin_x=8 if width < 1000 else 14,
        content_margin_y=6 if height < 720 else 10,
        compact_topbar=width < 1120,
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
    ):
        super().__init__(window)
        self.window = window
        self.step_nav = step_nav
        self.left_container = left_container
        self.progress_panel = progress_panel
        self.stack_layout = stack_layout
        self.topbar = topbar
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
