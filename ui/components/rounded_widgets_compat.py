# -*- coding: utf-8 -*-
"""
Compatibility wrapper for rounded_widgets → enhanced components

This file provides backward compatibility during migration.
Old code using create_rounded_button() will still work.
"""

from typing import Optional, Callable
from ui.components.base_widget_enhanced import create_button, EnhancedButton


def create_rounded_button(
    parent=None,
    text: str = "",
    command: Optional[Callable] = None,
    style: str = "primary",
    **kwargs
) -> EnhancedButton:
    """
    Compatibility wrapper for old create_rounded_button() calls

    Maps to new create_button() with enhanced features.
    """
    # Map old styles to new styles
    style_map = {
        "primary": "primary",
        "secondary": "secondary",
        "outline": "outline",
        "danger": "danger",
        "success": "accent",  # Map success → accent (coral)
    }

    mapped_style = style_map.get(style, "primary")

    return create_button(
        text=text,
        style=mapped_style,
        size="md",
        parent=parent,
        on_click=command
    )


# Alias for compatibility
RoundedButton = EnhancedButton
